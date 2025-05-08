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
    
    async def process_query(self, query: str, candidate_endpoints: List[str] = None) -> List[str]:
        """
        Process a query through the LLM to select appropriate endpoints.
        
        Args:
            query: The query to process
            candidate_endpoints: Optional list of candidate endpoints to choose from
            
        Returns:
            A list of selected endpoints
        """
        if not self.llm:
            self.logger.warning("No LLM available for endpoint selection")
            return candidate_endpoints or []
            
        try:
            # If no candidate endpoints provided, use all available endpoints
            if not candidate_endpoints:
                candidate_endpoints = self.all_endpoints
                
            # Use the LLM to select the best endpoints for this query
            prompt = f"""
            You are an AI assistant that helps select appropriate API endpoints for cryptocurrency research queries.
            Given the user query: "{query}"
            
            Select the most relevant endpoints from this list:
            {', '.join(candidate_endpoints)}
            
            Return only the endpoint strings that are most appropriate for this query, separated by commas.
            Do not return any explanation or additional text.
            """
            
            response = await self.llm.ainvoke(prompt)
            if not response:
                self.logger.warning("Empty response from LLM")
                return candidate_endpoints
                
            # Parse the response to extract endpoints
            selected_endpoints = []
            for line in response.strip().split('\n'):
                for endpoint in line.split(','):
                    cleaned = endpoint.strip()
                    if cleaned and cleaned in candidate_endpoints:
                        selected_endpoints.append(cleaned)
            
            if not selected_endpoints:
                self.logger.warning("No valid endpoints found in LLM response")
                return candidate_endpoints
                
            return selected_endpoints
            
        except Exception as e:
            self.logger.error(f"Error processing query with LLM: {str(e)}", exc_info=True)
            return candidate_endpoints
    
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

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text.
        
        Args:
            text: The text to embed
            
        Returns:
            A list of floats representing the embedding
        """
        try:
            # Use sentence-transformers to generate embeddings
            return await self.vector_store.embed_text(text)
        except Exception as e:
            self.logger.error(f"Error generating embedding: {str(e)}", exc_info=True)
            return None
            
    async def refine_endpoints_with_llm(self, query: str, endpoints: List[str]) -> List[str]:
        """
        Use the LLM to refine and rank the endpoints based on the query.
        
        Args:
            query: The original query
            endpoints: The list of candidate endpoints
            
        Returns:
            A filtered and ranked list of endpoints
        """
        try:
            if not self.llm:
                return endpoints
                
            # Process endpoints through LLM for selection and refinement
            llm_selected_endpoints = await self.process_query(query, endpoints)
            if llm_selected_endpoints and len(llm_selected_endpoints) > 0:
                self.logger.info(f"LLM selected {len(llm_selected_endpoints)} endpoints")
                return llm_selected_endpoints
                
            self.logger.warning("LLM didn't return valid endpoints, falling back to vector search results")
            return endpoints
        except Exception as e:
            self.logger.error(f"Error in LLM endpoint refinement: {str(e)}")
            return endpoints
            
    async def get_endpoints_for_project(self, query: str) -> List[str]:
        """
        Retrieve relevant endpoints for a given project query.
        
        Args:
            query: The query to find relevant endpoints for
            
        Returns:
            A list of endpoint strings that are relevant to the query
        """
        if not query:
            self.logger.warning("Empty query provided to RAGRetriever")
            return self.get_fallback_endpoints()
            
        try:
            # Use semantic search to find relevant endpoints
            self.logger.info(f"Performing RAG retrieval for query: {query}")
            
            # Get embeddings for the query
            query_embedding = await self.get_embedding(query)
            if not query_embedding:
                self.logger.warning("Failed to generate embedding for query, using fallback endpoints")
                return self.get_fallback_endpoints()
                
            # Search for similar vectors in the vector store
            search_results = await self.vector_store.search(query_embedding)
            if not search_results:
                self.logger.warning("No search results found in vector store, using fallback endpoints")
                return self.get_fallback_endpoints()
                
            # Extract endpoints from search results
            candidate_endpoints = [result.get("metadata", {}).get("endpoint") for result in search_results if "metadata" in result and "endpoint" in result["metadata"]]
            candidate_endpoints = [e for e in candidate_endpoints if e]  # Remove None/empty values
            
            if not candidate_endpoints:
                self.logger.warning("No valid endpoints found in search results, using fallback endpoints")
                return self.get_fallback_endpoints()
                
            # Filter out HuggingFace endpoints - we'll use them only as fallbacks
            candidate_endpoints = [endpoint for endpoint in candidate_endpoints if "huggingface" not in endpoint]
            
            # Use LLM to refine the endpoint selection based on the query context
            refined_endpoints = await self.process_query(query, candidate_endpoints)
            
            if refined_endpoints:
                self.logger.info(f"Retrieved {len(refined_endpoints)} refined endpoints for query: {refined_endpoints}")
                return refined_endpoints
            else:
                self.logger.warning("No endpoints after refinement, using original candidates")
                return candidate_endpoints
                
        except Exception as e:
            self.logger.error(f"Error in RAG retrieval: {str(e)}", exc_info=True)
            return self.get_fallback_endpoints()
    
    def get_fallback_endpoints(self) -> List[str]:
        """
        Get a list of fallback endpoints to use when RAG retrieval fails.
        
        Returns:
            A list of fallback endpoint strings
        """
        # Return a minimal set of endpoints that should work for most queries
        return [
            "data://coingecko/price/{coin}",
            "data://coingecko/market/{coin}",
            "data://coinmarketcap/price/{coin}",
            "data://defillama/tvl/{protocol}",
            "data://tavily/research/{query}"
        ]

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

    @property
    def all_endpoints(self) -> List[str]:
        """
        Get a list of all available endpoints.
        
        Returns:
            A list of endpoint strings
        """
        # Return a comprehensive list of available endpoints
        return [
            "data://tavily/research/{query}",
            "data://tavily/deep_research/{query}",
            "data://coingecko/price/{coin}",
            "data://coingecko/market/{coin}",
            "data://coingecko/historical/{coin}",
            "data://coinmarketcap/price/{coin}",
            "data://coinmarketcap/market/{coin}",
            "data://defillama/tvl/{protocol}",
            "data://defillama/yields/{protocol}",
            "data://huggingface/research/{query}",
            "data://tokenomics/distribution/{project}"
        ]

class LLMDecision:
    @staticmethod
    async def refine_endpoints(query: str, endpoints: list[str], llm=None) -> list[str]:
        """Refine the list of endpoints based on query context."""
        if not llm:
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
            
        # For now, return as-is; in the future, this could be enhanced with more sophisticated logic
        return endpoints
