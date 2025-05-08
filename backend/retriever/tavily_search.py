import os
import aiohttp
import asyncio
from typing import Literal, Sequence, List, Dict
import logging
import random
from backend.utils.cache_utils import CacheManager

class TavilySearch:
    def __init__(self, query=None, headers=None, topic="general", include_domains=None, exclude_domains=None, logger=None, search_depth="basic", project_name=None, api_key=None):
        self.query = query
        self.headers = headers or {}
        self.topic = topic
        self.include_domains = include_domains
        self.exclude_domains = exclude_domains
        self.base_url = "https://api.tavily.com/search"
        self.logger = logger or logging.getLogger("TavilySearch")
        
        # Use provided API key if passed, otherwise get from environment
        self.api_key = api_key if api_key else self.get_api_key()
        
        self.headers.update({"Content-Type": "application/json"})
        self._tavily_available = True  # Flag to track if Tavily is working
        self.search_depth = search_depth  # Add search_depth parameter
        
        # Project name for caching - try to infer it if not provided
        if not project_name:
            # Try to get project name from environment
            project_name = os.getenv("XPLAINCRYPTO_PROJECT_NAME", "")
            
            # If running from a script with a path like "/project_name/cache/..." 
            # Try to extract project name from current working directory
            if not project_name:
                try:
                    cwd = os.getcwd()
                    if "/docs/" in cwd:
                        # Extract project_name from path like ".../docs/PROJECT_NAME/..."
                        parts = cwd.split("/docs/")
                        if len(parts) > 1 and "/" in parts[1]:
                            project_name = parts[1].split("/")[0]
                except Exception:
                    pass
        
        # If still no project name after all attempts, force it to 'unknown' instead of 'default'
        # This will help identify and fix issues where project_name isn't being passed properly
        self.project_name = project_name if project_name else "unknown_project"
        
        # Initialize cache manager
        self.cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        if self.project_name == "unknown_project":
            self.logger.warning(f"⚠️ No project_name provided to TavilySearch, using '{self.project_name}' for cache. This may indicate a bug in the calling code.")

    def get_api_key(self):
        """
        Get the Tavily API key from various sources with appropriate fallbacks.
        
        Returns:
            The API key as a string, or an empty string if not found.
        """
        # First try to get from env var
        api_key = os.getenv("TAVILY_API_KEY", "")
        if api_key:
            self.logger.debug("Using Tavily API key from environment")
            return api_key
            
        # Try to get from .env file if it exists
        try:
            from dotenv import load_dotenv
            # Try to load from .env file
            load_dotenv()
            api_key = os.getenv("TAVILY_API_KEY", "")
            if api_key:
                self.logger.info("Loaded Tavily API key from .env file")
                return api_key
        except ImportError:
            self.logger.debug("python-dotenv not installed, skipping .env file check")
        except Exception as e:
            self.logger.debug(f"Error loading from .env: {str(e)}")
            
        # Check for development key
        api_key = os.environ.get("TAVILY_DEV_KEY", "")
        if api_key:
            self.logger.warning("Using TAVILY_DEV_KEY - this is intended for development only")
            return api_key
            
        # As a last resort, use a placeholder key
        self.logger.warning("⚠️ No Tavily API key found - to use Tavily search, please:")
        self.logger.warning("1. Create an account at https://tavily.com")
        self.logger.warning("2. Add TAVILY_API_KEY=your_key to your .env file or environment")
        self.logger.warning("3. Restart the application")
        
        # Return a fallback key that won't work but prevents errors
        # This will allow the cache to be used even without a real key
        return "tavily-fallback-key"

    async def _search_async(self, session, query: str, search_depth: Literal["basic", "advanced"] = "basic",
                            topic: str = "general", days: int = 2, max_results: int = 5,
                            include_domains: Sequence[str] = None, exclude_domains: Sequence[str] = None,
                            include_answer: bool = False, include_raw_content: bool = False,
                            include_images: bool = False, use_cache: bool = True) -> Dict:
        # If Tavily is known to be unavailable, return empty results
        if not self._tavily_available:
            self.logger.warning(f"Skipping Tavily API (known to be unavailable) for: {query[:50]}...")
            return {"results": [], "error": "Tavily API unavailable"}
        
        # Check cache first if project_name is available
        if use_cache and self.cache_manager:
            cache_key = f"{query[:100].lower().replace(' ', '_')}"
            cached_data = self.cache_manager.load("tavily", "search", cache_key)
            if cached_data:
                self.logger.info(f"Using cached Tavily search results for: {query[:50]}...")
                return cached_data
            
        data = {
            "query": query, "search_depth": search_depth, "topic": topic, "days": days,
            "max_results": max_results, "include_domains": include_domains or self.include_domains,
            "exclude_domains": exclude_domains or self.exclude_domains, "include_answer": include_answer,
            "include_raw_content": include_raw_content, "include_images": include_images,
            "api_key": self.api_key, "use_cache": use_cache
        }
        self.logger.debug(f"Executing async Tavily search for query: {query[:50]}...")
        
        # Add a direct log of the API key being used (first few characters only)
        self.logger.info(f"Using Tavily API key: {self.api_key[:5]}...")
        
        try:
            # Log more details about the request
            self.logger.debug(f"Request URL: {self.base_url}, Headers: {self.headers}")
            self.logger.info(f"Making Tavily API request to {self.base_url}")
            
            # Check API key before making request
            if not self.api_key or len(self.api_key) < 10:
                self.logger.error(f"Invalid Tavily API key: {self.api_key}")
                return {"results": [], "error": "Invalid Tavily API key"}
            
            # Always use direct debug for debugging in development
            print(f"DEBUG: Making Tavily API request with key: {self.api_key[:5]}...")
            
            async with session.post(self.base_url, json=data, headers=self.headers, timeout=aiohttp.ClientTimeout(total=100)) as response:
                self.logger.info(f"Tavily API response status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    self.logger.debug(f"Async search successful, received {len(result.get('results', []))} results")
                    
                    # Cache the result if project_name is available
                    if self.cache_manager:
                        # Ensure the result is properly formatted before saving
                        if isinstance(result, dict):
                            # Make sure we have a valid structure
                            if "results" not in result:
                                result["results"] = []
                            # Ensure all content is properly sanitized for JSON
                            for item in result.get("results", []):
                                if "content" in item and item["content"] is not None:
                                    # Remove any control characters that might break JSON
                                    item["content"] = ''.join(c for c in item["content"] if ord(c) >= 32 or c in '\n\r\t')
                                if "raw_content" in item and item["raw_content"] is not None:
                                    # Remove any control characters that might break JSON
                                    item["raw_content"] = ''.join(c for c in item["raw_content"] if ord(c) >= 32 or c in '\n\r\t')
                                    
                        self.cache_manager.save(result, "tavily", "search", cache_key)
                        self.logger.info(f"Cached Tavily search results for: {query[:50]}...")
                    
                    return result
                else:
                    response_text = await response.text()
                    self.logger.warning(f"Tavily API error: {response.status} - {response_text}")
                    self.logger.debug(f"Request details - URL: {self.base_url}, HTTP Status: {response.status}, Headers: {dict(response.headers)}")
                    
                    # Check for specific error types
                    if response.status == 401:
                        self.logger.error("Tavily API authentication error - check API key")
                    elif response.status == 429:
                        self.logger.error("Tavily API rate limit exceeded")
                    elif response.status >= 500:
                        self.logger.error("Tavily API server error")
                        
                    return {"results": [], "error": f"Tavily API error: {response.status} - {response_text}"}
        except aiohttp.ClientConnectorError as e:
            self.logger.warning(f"Tavily connection error: {str(e)}")
            self._tavily_available = False
            return {"results": [], "error": f"Tavily connection error: {str(e)}"}
        except asyncio.TimeoutError:
            self.logger.warning("Tavily request timed out after 100 seconds")
            return {"results": [], "error": "Tavily request timed out"}
        except Exception as e:
            self.logger.warning(f"Async Tavily search failed: {str(e)} ({type(e).__name__})")
            # Mark Tavily as unavailable to avoid further attempts
            self._tavily_available = False
            return {"results": [], "error": f"Tavily search failed: {str(e)}"}

    async def search_batch(self, queries: List[str], max_results: int = 7) -> List[Dict]:
        # Process and prepare queries
        processed_queries = []
        for query in queries:
            # Handle dictionary queries
            if isinstance(query, dict):
                self.logger.warning(f"Received query as dict in search_batch: {query}")
                if "query" in query and isinstance(query["query"], str):
                    query_str = query["query"]
                elif "topic" in query and isinstance(query["topic"], str):
                    query_str = query["topic"]
                else:
                    # Convert dict to string as fallback
                    query_str = str(query)
                    # Remove curly braces for better search
                    query_str = query_str.strip('{}')
                
                self.logger.info(f"Extracted query string from dictionary: '{query_str}'")
            else:
                query_str = str(query) if query is not None else ""
            
            # Validate query
            if not query_str or len(query_str.strip()) < 3:
                self.logger.warning(f"Invalid query in batch: '{query_str}' is too short or empty")
                raise ValueError("Query too short or empty")
                
            processed_queries.append(query_str)
        
        # If Tavily is known to be unavailable, return empty results
        if not self._tavily_available:
            self.logger.warning(f"Using empty results for all {len(processed_queries)} queries (Tavily unavailable)")
            return [{"results": [], "error": "Tavily API unavailable"} for _ in processed_queries]
            
        # Try with Tavily API
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [self._search_async(session, q, search_depth=self.search_depth, 
                                           max_results=max_results, topic=self.topic) 
                         for q in processed_queries]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                processed_results = []
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        self.logger.warning(f"Exception in query {i}: {str(res)}")
                        processed_results.append({
                            "results": [], 
                            "error": f"Exception: {str(res)}"
                        })
                    else:
                        processed_results.append(res)
                        
                return processed_results
                
        except Exception as e:
            self.logger.error(f"Batch search failed completely: {str(e)}")
            self._tavily_available = False
            return [{"results": [], "error": f"Batch search failed: {str(e)}"} for _ in processed_queries]

    async def search(self) -> List[Dict[str, str]]:
        """Perform an async search using the query provided during initialization."""
        # Handle case when query is a dict
        query = self.query
        
        if isinstance(query, dict):
            self.logger.warning(f"Received query as dict in search method: {query}")
            if "query" in query and isinstance(query["query"], str):
                query_str = query["query"]
            elif "topic" in query and isinstance(query["topic"], str):
                query_str = query["topic"]
            else:
                # Convert dict to string as fallback
                query_str = str(query)
                # Remove curly braces for better search
                query_str = query_str.strip('{}')
            
            self.logger.info(f"Extracted query string from dictionary: '{query_str}'")
            # Update the query attribute
            self.query = query_str
        else:
            query_str = str(query) if query is not None else ""
        
        if not query_str or len(query_str.strip()) < 3:
            self.logger.warning("Search query too short or empty")
            raise ValueError("Query too short or empty")
        
        # Use search_batch with a single query
        result = await self.search_batch([query_str])
        return result[0] if result else {"results": [], "error": "Search failed"}

    def batch_queries(self, queries: List[str], batch_size: int = 4) -> List[List[str]]:
        return [queries[i:i + batch_size] for i in range(0, len(queries), batch_size)]

    async def research(self, query: str, project_name=None, cache_key=None) -> Dict:
        """
        Perform in-depth research on a topic using Tavily's advanced search.
        This returns more comprehensive results than regular search.
        
        Args:
            query: The research query
            project_name: Optional project name for caching
            cache_key: Optional key to use for caching (defaults to query)
            
        Returns:
            Dictionary with research data
        """
        # Handle case when query is a dict
        if isinstance(query, dict):
            self.logger.warning(f"Received query as dict in research method: {query}")
            if "query" in query and isinstance(query["query"], str):
                query_str = query["query"]
            elif "topic" in query and isinstance(query["topic"], str):
                query_str = query["topic"]
            else:
                # Convert dict to string as fallback
                query_str = str(query)
                # Remove curly braces for better search
                query_str = query_str.strip('{}')
            
            self.logger.info(f"Extracted query string from dictionary: '{query_str}'")
        else:
            query_str = str(query) if query is not None else ""

        # Ensure query is a non-empty string
        if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 3:
            self.logger.warning("Research query too short or empty")
            raise ValueError("Query too short or empty")
        
        # Use the provided project_name or fallback to the one from init
        project_name = project_name or self.project_name
        
        # Handle case when project_name is a dict
        if isinstance(project_name, dict):
            self.logger.warning(f"Received project_name as dict: {project_name}")
            if "project_name" in project_name and isinstance(project_name["project_name"], str):
                project_name_str = project_name["project_name"]
            else:
                # Use a default project name
                project_name_str = "default_project"
                self.logger.warning(f"Using default project name: {project_name_str}")
        else:
            project_name_str = str(project_name) if project_name is not None else "default_project"
        
        # Save the original query, unmodified - CRITICAL
        self.query = query_str
        self.logger.info(f"Using query EXACTLY as provided: '{query_str}' with project_name='{project_name_str}'")
        
        # Use the provided cache_key or fallback to query_str
        cache_key = cache_key or query_str
        self.logger.info(f"Using cache key: '{cache_key}' for query '{query_str}'")
        
        # First check cache if we have a project_name
        if project_name_str:
            # Initialize cache manager with project-specific directory
            cache_manager = CacheManager(project_name=project_name_str, logger=self.logger)
            
            # Try to get from cache before API call - use cache_key
            cached_data = cache_manager.load("tavily", "research", cache_key)
            if cached_data:
                self.logger.info(f"Using cached research data for key '{cache_key}' in project '{project_name_str}'")
                return cached_data
        
        # Prevent excessive API calls for the same query
        research_result = await self._tavily_research(query_str)
        
        # Enhanced sanitization for the research result to ensure proper JSON formatting
        if isinstance(research_result, dict):
            # Make sure we have a valid structure
            if "results" not in research_result:
                research_result["results"] = []
            
            # Sanitize the results array
            for item in research_result.get("results", []):
                # Sanitize content field
                if "content" in item:
                    if item["content"] is None:
                        item["content"] = ""
                    else:
                        # Remove control characters and ensure proper UTF-8 encoding
                        item["content"] = self._sanitize_text(item["content"])
                
                # Sanitize raw_content field
                if "raw_content" in item:
                    if item["raw_content"] is None:
                        item["raw_content"] = ""
                    else:
                        # Remove control characters and ensure proper UTF-8 encoding
                        item["raw_content"] = self._sanitize_text(item["raw_content"])
                
                # Sanitize title field
                if "title" in item and item["title"] is not None:
                    item["title"] = self._sanitize_text(item["title"])
                
                # Sanitize url field
                if "url" in item and item["url"] is not None:
                    item["url"] = self._sanitize_text(item["url"])
                
                # Sanitize score field
                if "score" in item and not isinstance(item["score"], (int, float)):
                    item["score"] = 0.0
            
            # Sanitize answer field if present
            if "answer" in research_result:
                if research_result["answer"] is None:
                    research_result["answer"] = ""
                else:
                    research_result["answer"] = self._sanitize_text(research_result["answer"])
            
            # Sanitize follow_up_questions field if present
            if "follow_up_questions" in research_result and research_result["follow_up_questions"] is not None:
                if isinstance(research_result["follow_up_questions"], list):
                    research_result["follow_up_questions"] = [
                        self._sanitize_text(q) if q is not None else "" 
                        for q in research_result["follow_up_questions"]
                    ]
                else:
                    research_result["follow_up_questions"] = None
            
            # Sanitize query field if present
            if "query" in research_result and research_result["query"] is not None:
                research_result["query"] = self._sanitize_text(research_result["query"])
            
            # Ensure images is a list if present
            if "images" in research_result and not isinstance(research_result["images"], list):
                research_result["images"] = []
        
        # Always cache the result if we have a project_name
        if project_name_str:
            cache_manager = CacheManager(project_name=project_name_str, logger=self.logger)
            # Use the cache_key parameter for saving to cache
            cache_manager.save(research_result, "tavily", "research", cache_key)
        
        return research_result

    def _sanitize_text(self, text):
        """
        Thoroughly sanitize text to ensure it can be properly serialized to JSON.
        
        Args:
            text: The text to sanitize
            
        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            return str(text)
        
        try:
            # First encode and decode to handle any encoding issues
            text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            
            # Remove control characters but keep basic whitespace
            sanitized = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
            
            # Replace any remaining problematic characters
            sanitized = sanitized.replace('\u2028', ' ').replace('\u2029', ' ')
            
            return sanitized
        except Exception as e:
            self.logger.warning(f"Error sanitizing text: {str(e)}")
            # Return a safe fallback
            return ""

    async def _tavily_research(self, query: str) -> Dict:
        """
        Internal method to make the actual API call to Tavily for research.
        
        Args:
            query: The raw query string to research
            
        Returns:
            Dictionary with research results
        """
        # Set up common parameters
        url = "https://api.tavily.com/search"  # Changed from /research to /search
        
        # Important: Use the query exactly as is without adding "cryptocurrency finance token"
        # This ensures we get relevant results for tokens/projects as specified
        payload = {
            "api_key": self.api_key,
            "query": query,  # Use query exactly as provided
            "search_depth": "advanced",
            "include_answer": True, 
            "include_raw_content": True,
            "include_images": False
        }
        
        # Log more details about the request
        self.logger.debug(f"Request URL: {url}, Headers: {self.headers}")
        self.logger.info(f"Making Tavily API request to {url}")
        
        try:
            # Check API key before making request
            if not self.api_key or len(self.api_key) < 10:
                self.logger.error(f"Invalid Tavily API key: {self.api_key}")
                return {"error": "Invalid Tavily API key"}
            
            # Always use direct debug for debugging in development
            print(f"DEBUG: Making Tavily API request with key: {self.api_key[:5]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=100)) as response:
                    self.logger.info(f"Tavily API response status: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        self.logger.debug(f"Async research successful, received {len(result.get('results', []))} results")
                        
                        return result
                    else:
                        response_text = await response.text()
                        self.logger.warning(f"Tavily API error: {response.status} - {response_text}")
                        self.logger.debug(f"Request details - URL: {url}, HTTP Status: {response.status}, Headers: {dict(response.headers)}")
                        
                        # Check for specific error types
                        if response.status == 401:
                            self.logger.error("Tavily API authentication error - check API key")
                        elif response.status == 429:
                            self.logger.error("Tavily API rate limit exceeded")
                        elif response.status >= 500:
                            self.logger.error("Tavily API server error")
                            
                        return {"error": f"Tavily API error: {response.status} - {response_text}"}
        except aiohttp.ClientConnectorError as e:
            self.logger.warning(f"Tavily connection error: {str(e)}")
            self._tavily_available = False
            return {"error": f"Tavily connection error: {str(e)}"}
        except asyncio.TimeoutError:
            self.logger.warning("Tavily request timed out after 100 seconds")
            return {"error": "Tavily request timed out"}
        except Exception as e:
            self.logger.warning(f"Async research failed: {str(e)} ({type(e).__name__})")
            # Mark Tavily as unavailable to avoid further attempts
            self._tavily_available = False
            return {"error": f"Tavily search failed: {str(e)}"}