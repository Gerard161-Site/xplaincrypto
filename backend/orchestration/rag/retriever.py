from langchain_openai import ChatOpenAI
# Fix imports to handle different import paths
try:
    from backend.orchestration.rag.vector_store import VectorStore
    from backend.utils.cache_utils import CacheManager
except ImportError:
    # When running from inside backend directory
    from orchestration.rag.vector_store import VectorStore
    from utils.cache_utils import CacheManager
import os
import logging
import datetime
import sys
import hashlib
import json
from typing import List, Dict, Any, Tuple, Optional
from langchain.prompts import ChatPromptTemplate

class RAGRetriever:
    def __init__(self, vector_store: VectorStore, llm_model: str = "gpt-4o-mini"):
        # Initialize logger for this class
        self.logger = logging.getLogger(__name__)
        
        self.vector_store = vector_store
        
        # Initialize cache manager for RAG results
        try:
            self.cache_manager = CacheManager(project_name="system", logger=self.logger)
            self.logger.info("Initialized cache manager for RAG results")
        except Exception as e:
            self.logger.error(f"Error initializing cache manager: {str(e)}")
            self.cache_manager = None
        
        # Load API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logging.error("OPENAI_API_KEY not found in environment variables")
        
        # Configure LLM with more robust error handling
        try:
            self.llm = ChatOpenAI(model=llm_model, api_key=api_key)
            logging.info(f"Initialized RAGRetriever with model: {llm_model}")
        except Exception as e:
            logging.error(f"Error initializing ChatOpenAI: {str(e)}")
            # Set to None to allow fallback behavior
            self.llm = None

    def _generate_cache_key(self, query: str) -> str:
        """Generate a deterministic cache key from a query string."""
        # Normalize the query by lowercasing and removing extra whitespace
        normalized_query = " ".join(query.lower().split())
        # Create a hash of the normalized query
        query_hash = hashlib.md5(normalized_query.encode()).hexdigest()
        return query_hash
    
    async def process_query(self, query: str, data_sources: List[str] = None) -> list[str]:
        """
        Process a query and return a list of MCP endpoints to call.
        
        Args:
            query: The search query
            data_sources: Optional list of specific data sources to include
            
        Returns:
            List of endpoint patterns
        """
        try:
            # Log the query for debugging
            self.logger.info(f"Processing RAG query: {query}")
            
            # Check cache first if available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                cached_endpoints = self.cache_manager.load("rag", "endpoints", cache_key)
                if cached_endpoints:
                    self.logger.info(f"Using cached endpoints for query: {query}")
                    return cached_endpoints
            
            # Filter candidate pool if specific data sources requested
            preselected_endpoints = []
            if data_sources:
                self.logger.info(f"Using preselected data sources: {data_sources}")
                for source in data_sources:
                    if source == "coinmarketcap":
                        preselected_endpoints.extend([
                            "data://coinmarketcap/price/{coin}",
                            "data://coinmarketcap/market/{coin}"
                        ])
                    elif source == "coingecko":
                        preselected_endpoints.extend([
                            "data://coingecko/price/{coin}",
                            "data://coingecko/market/{coin}"
                        ])
                    elif source == "defillama":
                        preselected_endpoints.extend([
                            "data://defillama/tvl/{protocol}",
                            "data://defillama/yields/{protocol}"
                        ])
                    elif source == "tokenomics":
                        preselected_endpoints.extend([
                            "data://tokenomics/{project}",
                            "data://tokenomics/distribution/{project}"
                        ])
                    elif source == "web_research" or source == "tavily" or source == "research":
                        preselected_endpoints.extend([
                            "data://tavily/research/{query}",
                            "data://tavily/security/{query}",
                            "data://tavily/technical/{query}"
                        ])
                    
                if preselected_endpoints:
                    self.logger.info(f"Preselected {len(preselected_endpoints)} endpoints: {preselected_endpoints}")
                    # Cache the preselected endpoints if cache manager is available
                    if self.cache_manager:
                        cache_key = self._generate_cache_key(query)
                        self.cache_manager.save(preselected_endpoints, "rag", "endpoints", cache_key)
                        self.logger.info(f"Cached preselected endpoints for query: {query}")
                    return preselected_endpoints
                    
            # If no preselected endpoints, use both vector store and LLM for endpoint selection
            # Get initial candidate endpoints from vector store
            candidates = self.vector_store.query(query, top_k=10)
            
            # Extract just the endpoint strings - fix unpacking error
            candidate_endpoints = [endpoint_id for endpoint_id, _, _ in candidates]
            
            # Filter out problematic endpoints
            filtered_candidates = []
            for endpoint in candidate_endpoints:
                if "://project/" in endpoint or "://multi/" in endpoint or endpoint == "data://huggingface/model/{model_id}":
                    self.logger.warning(f"Filtering out problematic endpoint: {endpoint}")
                    continue
                filtered_candidates.append(endpoint)
                
            # Check if we have enough candidates, if not, use sensible defaults
            if len(filtered_candidates) < 2:
                default_endpoints = ["data://tavily/research/{query}", "data://huggingface/research/{query}"]
                # Cache the default endpoints if cache manager is available
                if self.cache_manager:
                    cache_key = self._generate_cache_key(query)
                    self.cache_manager.save(default_endpoints, "rag", "endpoints", cache_key)
                    self.logger.info(f"Cached default endpoints for query: {query}")
                return default_endpoints
            
            # Format candidate endpoints for LLM ranking
            endpoint_data = "\n".join([f"- {endpoint}" for endpoint in filtered_candidates])
            
            # Create prompt for LLM to rank endpoints
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant that selects the most relevant data endpoints for a given query. Return only the endpoints, no explanations."),
                ("user", f"""Select 2-3 most relevant endpoints for the query: "{query}"
                
                Available endpoints:
                {endpoint_data}
                
                Return ONLY a comma-separated list of the selected endpoints, with no explanation or additional text.""")
            ])
            
            # Invoke LLM for endpoint ranking
            try:
                chain = prompt | self.llm
                result = await chain.ainvoke({})
                
                # Extract content from the result
                if isinstance(result, dict) and "content" in result:
                    selected_text = result["content"]
                else:
                    selected_text = str(result)
                
                # Parse comma-separated list
                selected_endpoints = [endpoint.strip() for endpoint in selected_text.split(",")]
                
                # Validate the endpoints
                valid_selected = [endpoint for endpoint in selected_endpoints if endpoint in filtered_candidates]
                
                if valid_selected:
                    self.logger.info(f"LLM selected endpoints: {valid_selected}")
                    # Cache the selected endpoints if cache manager is available
                    if self.cache_manager:
                        cache_key = self._generate_cache_key(query)
                        self.cache_manager.save(valid_selected, "rag", "endpoints", cache_key)
                        self.logger.info(f"Cached LLM-selected endpoints for query: {query}")
                    return valid_selected
                else:
                    self.logger.warning("LLM didn't select valid endpoints, returning filtered candidates")
                    # Cache the filtered candidates if cache manager is available
                    if self.cache_manager:
                        cache_key = self._generate_cache_key(query)
                        self.cache_manager.save(filtered_candidates, "rag", "endpoints", cache_key)
                        self.logger.info(f"Cached filtered candidates for query: {query}")
                    return filtered_candidates
                    
            except Exception as e:
                self.logger.warning(f"Error in LLM endpoint selection: {str(e)}")
                # Cache the filtered candidates if cache manager is available
                if self.cache_manager:
                    cache_key = self._generate_cache_key(query)
                    self.cache_manager.save(filtered_candidates, "rag", "endpoints", cache_key)
                    self.logger.info(f"Cached filtered candidates after LLM error for query: {query}")
                return filtered_candidates
                
        except Exception as e:
            self.logger.error(f"Error in process_query: {str(e)}")
            # Return safe defaults
            default_endpoints = ["data://tavily/research/{query}", "data://huggingface/research/{query}"]
            # Cache the default endpoints if cache manager is available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                self.cache_manager.save(default_endpoints, "rag", "endpoints", cache_key)
                self.logger.info(f"Cached default endpoints after error for query: {query}")
            return default_endpoints
    
    async def format_endpoint_for_query(self, endpoint_pattern: str, project_name: str, query: Optional[str] = None) -> str:
        """
        Format endpoint pattern by replacing placeholders with provided values.
        
        Args:
            endpoint_pattern: The endpoint pattern with placeholders (e.g., data://coingecko/price/{coin}/{project_name})
            project_name: The name of the project to use for {coin}, {protocol}, {project}, {project_name}.
            query: The original search query (used for {query} placeholders).
            
        Returns:
            Formatted endpoint string ready for use.
        """
        if not endpoint_pattern:
            return ""
            
        # Normalize project name
        safe_name = project_name.lower().strip()
        
        # Start with the raw pattern
        formatted_endpoint = endpoint_pattern 

        # Replace placeholders based on their presence in the pattern
        if '{coin}' in formatted_endpoint:
            formatted_endpoint = formatted_endpoint.replace('{coin}', safe_name)
        if '{protocol}' in formatted_endpoint:
            formatted_endpoint = formatted_endpoint.replace('{protocol}', safe_name)
        if '{project}' in formatted_endpoint:
            formatted_endpoint = formatted_endpoint.replace('{project}', safe_name)
        if '{project_name}' in formatted_endpoint:
             formatted_endpoint = formatted_endpoint.replace('{project_name}', safe_name)

        # Replace {query} placeholder using the actual query string
        if '{query}' in formatted_endpoint:
            if query:
                # TODO: Consider URL encoding the query if needed
                formatted_endpoint = formatted_endpoint.replace('{query}', query)
            else:
                self.logger.warning(f"No query string provided for pattern '{endpoint_pattern}'. Using project name '{safe_name}' for {{query}} placeholder.")
                formatted_endpoint = formatted_endpoint.replace('{query}', safe_name)
                
        # Log the transformation
        self.logger.info(f"Formatted endpoint: Pattern='{endpoint_pattern}', Query='{query}', Proj='{project_name}' -> Final='{formatted_endpoint}'")
        
        # Return the endpoint with only the existing placeholders filled
        return formatted_endpoint
    
    def _get_specialized_endpoint(self, query: str, endpoint: str) -> str:
        """
        Optimize endpoints for specific query types to use more specialized endpoints.
        For example, redirect security-related queries to security-specific endpoints.
        
        Args:
            query: The search query
            endpoint: The original endpoint pattern
            
        Returns:
            Potentially updated endpoint pattern for specialized handling
        """
        query_lower = query.lower()
        
        # Special handling for tavily research endpoints
        if "data://tavily/research/" in endpoint:
            # Security-related queries
            if any(term in query_lower for term in ["security", "audit", "vulnerability", "risk", "exploit"]):
                self.logger.info(f"Redirecting query to specialized security endpoint: {query}")
                return "data://tavily/security/{query}"
                
            # Technical-related queries  
            if any(term in query_lower for term in ["technical", "architecture", "implementation", "protocol", "blockchain"]):
                self.logger.info(f"Redirecting query to specialized technical endpoint: {query}")
                return "data://tavily/technical/{query}"
        
        # Return original endpoint if no specialization applies
        return endpoint

    async def get_endpoints_for_project(self, query: str, project_name: Optional[str] = None) -> List[str]:
        """Get the most relevant data endpoints for a project and query."""
        try:
            # Ensure the vectorstore is initialized
            if not self.vector_store:
                self.vector_store = get_vector_store()

            # Add project name to query if provided
            enhanced_query = query
            if project_name and project_name.lower() not in query.lower():
                enhanced_query = f"{project_name} {query}"
            
            self.logger.info(f"RAG query: '{enhanced_query}'")
            
            # Check cache first if available
            if self.cache_manager:
                # Include project name in cache key if available
                cache_key = self._generate_cache_key(enhanced_query)
                if project_name:
                    cache_key = f"{project_name.lower()}_{cache_key}"
                
                cached_endpoints = self.cache_manager.load("rag", "project_endpoints", cache_key)
                if cached_endpoints:
                    self.logger.info(f"Using cached endpoints for project query: '{enhanced_query}'")
                    return cached_endpoints
            
            # Get endpoints from vectorstore
            raw_endpoints = self.vector_store.query(enhanced_query, top_k=10)
            
            # Extract just the endpoint strings
            endpoint_strings = [endpoint_id for endpoint_id, _, _ in raw_endpoints]
            
            # FILTER OUT PROBLEMATIC ENDPOINTS - important fix for recursion and timeout issues
            filtered_endpoints = []
            for endpoint in endpoint_strings:
                # Skip invalid server endpoints that cause recursion
                if "://project/" in endpoint or "://multi/" in endpoint or endpoint == "data://huggingface/model/{model_id}":
                    self.logger.warning(f"Filtering out problematic endpoint: {endpoint}")
                    continue
                    
                # Check for specialized endpoints
                specialized_endpoint = self._get_specialized_endpoint(query, endpoint)
                if specialized_endpoint != endpoint:
                    filtered_endpoints.append(specialized_endpoint)
                else:
                    filtered_endpoints.append(endpoint)
                
            self.logger.info(f"Vector store returned {len(filtered_endpoints)} candidate endpoints")
            
            # Process endpoints through LLM for selection and refinement if we have enough candidates
            if len(filtered_endpoints) > 2:
                try:
                    llm_selected_endpoints = await self.process_query(enhanced_query)
                    if llm_selected_endpoints and len(llm_selected_endpoints) > 0:
                        self.logger.info(f"LLM selected {len(llm_selected_endpoints)} endpoints")
                        
                        # Cache the selected endpoints if cache manager is available
                        if self.cache_manager:
                            cache_key = self._generate_cache_key(enhanced_query)
                            if project_name:
                                cache_key = f"{project_name.lower()}_{cache_key}"
                            self.cache_manager.save(llm_selected_endpoints, "rag", "project_endpoints", cache_key)
                            self.logger.info(f"Cached LLM-selected endpoints for project query: '{enhanced_query}'")
                            
                        return llm_selected_endpoints
                    self.logger.warning("LLM didn't return valid endpoints, falling back to vector search results")
                except Exception as e:
                    self.logger.error(f"Error in LLM endpoint selection: {str(e)}")
                    # Fall back to vector store results
            
            # Cache the filtered endpoints if cache manager is available
            if self.cache_manager:
                cache_key = self._generate_cache_key(enhanced_query)
                if project_name:
                    cache_key = f"{project_name.lower()}_{cache_key}"
                self.cache_manager.save(filtered_endpoints, "rag", "project_endpoints", cache_key)
                self.logger.info(f"Cached filtered endpoints for project query: '{enhanced_query}'")
                
            return filtered_endpoints
            
        except Exception as e:
            self.logger.error(f"Error in get_endpoints_for_project: {str(e)}")
            # Return a small set of fallback endpoints that should work for most queries
            default_endpoints = ["data://tavily/research/{query}", "data://huggingface/research/{query}"]
            
            # Cache the default endpoints if cache manager is available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                if project_name:
                    cache_key = f"{project_name.lower()}_{cache_key}"
                self.cache_manager.save(default_endpoints, "rag", "project_endpoints", cache_key)
                self.logger.info(f"Cached default endpoints after error for project query: '{query}'")
                
            return default_endpoints
    
    async def retrieve_relevant_endpoints(self, query: str, top_k: int = 5) -> dict:
        """
        Retrieve relevant endpoints for a query and organize them by category.
        Returns a dictionary with endpoints and metadata.
        """
        try:
            # Check cache first if available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                cached_result = self.cache_manager.load("rag", "relevant_endpoints", cache_key)
                if cached_result:
                    self.logger.info(f"Using cached relevant endpoints for query: '{query}'")
                    return cached_result
            
            # Retrieve relevant endpoints from vector store
            candidate_tuples = self.vector_store.query(query, top_k=top_k)
            
            result = {
                "query": query,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "endpoints": [],
                "categories": {}
            }
            
            if not candidate_tuples:
                self.logger.warning(f"No endpoints found in vector store for query: {query}")
                
                # Cache the empty result if cache manager is available
                if self.cache_manager:
                    cache_key = self._generate_cache_key(query)
                    self.cache_manager.save(result, "rag", "relevant_endpoints", cache_key)
                    self.logger.info(f"Cached empty result for query: '{query}'")
                    
                return result
            
            # Process candidates
            for endpoint_id, description, score in candidate_tuples:
                # Parse endpoint parts (e.g., "data://coingecko/price" -> ["data", "coingecko", "price"])
                parts = endpoint_id.split("://")
                if len(parts) == 2:
                    endpoint_type = parts[0]  # e.g., "data"
                    endpoint_path = parts[1]  # e.g., "coingecko/price"
                    
                    # Determine category
                    if "/" in endpoint_path:
                        category = endpoint_path.split("/")[0]  # e.g., "coingecko"
                    else:
                        category = endpoint_path
                    
                    # Add to endpoints list
                    endpoint_info = {
                        "id": endpoint_id,
                        "description": description,
                        "score": score,
                        "type": endpoint_type,
                        "category": category
                    }
                    
                    result["endpoints"].append(endpoint_info)
                    
                    # Organize by category
                    if category not in result["categories"]:
                        result["categories"][category] = []
                    
                    result["categories"][category].append(endpoint_info)
            
            # Sort endpoints by score
            result["endpoints"].sort(key=lambda x: x["score"], reverse=True)
            
            # Sort within each category
            for category in result["categories"]:
                result["categories"][category].sort(key=lambda x: x["score"], reverse=True)
            
            # Cache the result if cache manager is available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                self.cache_manager.save(result, "rag", "relevant_endpoints", cache_key)
                self.logger.info(f"Cached relevant endpoints for query: '{query}'")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving relevant endpoints: {str(e)}")
            error_result = {
                "query": query,
                "error": str(e),
                "endpoints": [],
                "categories": {}
            }
            
            # Cache the error result if cache manager is available
            if self.cache_manager:
                cache_key = self._generate_cache_key(query)
                self.cache_manager.save(error_result, "rag", "relevant_endpoints", cache_key)
                self.logger.info(f"Cached error result for query: '{query}'")
                
            return error_result

class LLMDecision:
    @staticmethod
    async def refine_endpoints(query: str, endpoints: list[str], llm=None) -> list[str]:
        """Refine the list of endpoints based on query context."""
        if not llm:
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
            
        # For now, return as-is; in the future, this could be enhanced with more sophisticated logic
        return endpoints
