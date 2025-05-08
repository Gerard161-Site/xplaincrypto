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
            cached_data = self.cache_manager.load("tavily", "search", cache_key, ttl_seconds=86400)  # 24 hour TTL
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
        for query in queries:
            if not query or len(query.strip()) < 3:
                self.logger.warning(f"Invalid query in batch: '{query}' is too short or empty")
                raise ValueError("Query too short or empty")
        
        # If Tavily is known to be unavailable, return empty results
        if not self._tavily_available:
            self.logger.warning(f"Using empty results for all {len(queries)} queries (Tavily unavailable)")
            return [{"results": [], "error": "Tavily API unavailable"} for _ in queries]
            
        # Try with Tavily API
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [self._search_async(session, q, search_depth=self.search_depth, 
                                            max_results=max_results, topic=self.topic) 
                         for q in queries]
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
                        processed_results.append({
                            "results": [{"href": r["url"], "body": r["content"]} for r in res.get("results", [])]
                        })
                        
                return processed_results
                
        except Exception as e:
            self.logger.error(f"Batch search failed completely: {str(e)}")
            self._tavily_available = False
            return [{"results": [], "error": f"Batch search failed: {str(e)}"} for _ in queries]

    async def search(self) -> List[Dict[str, str]]:
        """Perform an async search using the query provided during initialization."""
        if not self.query or len(self.query.strip()) < 3:
            self.logger.warning("Search query too short or empty")
            raise ValueError("Query too short or empty")
        
        # Use search_batch with a single query
        result = await self.search_batch([self.query])
        return result[0] if result else {"results": [], "error": "Search failed"}

    def batch_queries(self, queries: List[str], batch_size: int = 4) -> List[List[str]]:
        return [queries[i:i + batch_size] for i in range(0, len(queries), batch_size)]

    async def research(self, query: str, project_name=None) -> Dict:
        """
        Perform in-depth research on a topic using Tavily's advanced search.
        This returns more comprehensive results than regular search.
        
        Args:
            query: The research query
            project_name: Optional project name for caching
            
        Returns:
            Dictionary with research data
        """
        if not query or len(query.strip()) < 3:
            self.logger.warning("Research query too short or empty")
            raise ValueError("Query too short or empty")
        
        # Use the provided project_name or fallback to the one from init
        project_name = project_name or self.project_name
        
        # Save the original query, unmodified - CRITICAL
        self.query = query
        self.logger.info(f"Using query EXACTLY as provided: '{query}' with project_name='{project_name}'")
        
        # First check cache if we have a project_name
        if project_name:
            # Initialize cache manager with project-specific directory
            cache_manager = CacheManager(project_name=project_name, logger=self.logger)
            
            # Try to get from cache before API call
            cached_data = cache_manager.load("tavily", "research", query)
            if cached_data:
                self.logger.info(f"Using cached research data for '{query}' in project '{project_name}'")
                return cached_data
        
        # Prevent excessive API calls for the same query
        research_result = await self._tavily_research(query)
        
        # Always cache the result if we have a project_name
        if project_name:
            cache_manager = CacheManager(project_name=project_name, logger=self.logger)
            cache_manager.save(research_result, "tavily", "research", query)
        
        return research_result

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