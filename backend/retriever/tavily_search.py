import os
import aiohttp
import asyncio
from typing import Literal, Sequence, List, Dict
import logging
import random

class TavilySearch:
    def __init__(self, query=None, headers=None, topic="general", include_domains=None, exclude_domains=None, logger=None):
        self.query = query
        self.headers = headers or {}
        self.topic = topic
        self.include_domains = include_domains
        self.exclude_domains = exclude_domains
        self.base_url = "https://api.tavily.com/search"
        self.logger = logger or logging.getLogger("TavilySearch")
        self.api_key = self.get_api_key()
        self.headers.update({"Content-Type": "application/json"})
        self._tavily_available = True  # Flag to track if Tavily is working

    def get_api_key(self):
        # First try to get from env var
        api_key = os.getenv("TAVILY_API_KEY", "")
        if api_key:
            self.logger.debug("Using Tavily API key from environment")
            return api_key
            
        # Use the hardcoded key as fallback
        api_key = "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"
        if not api_key:
            self.logger.error("TAVILY_API_KEY not set and no fallback available")
            raise KeyError("TAVILY_API_KEY not set")
        
        self.logger.warning("Using default Tavily API key - not recommended for production")
        return api_key

    async def _search_async(self, session, query: str, search_depth: Literal["basic", "advanced"] = "basic",
                            topic: str = "general", days: int = 2, max_results: int = 5,
                            include_domains: Sequence[str] = None, exclude_domains: Sequence[str] = None,
                            include_answer: bool = False, include_raw_content: bool = False,
                            include_images: bool = False, use_cache: bool = True) -> Dict:
        # If Tavily is known to be unavailable, return empty results
        if not self._tavily_available:
            self.logger.warning(f"Skipping Tavily API (known to be unavailable) for: {query[:50]}...")
            return {"results": [], "error": "Tavily API unavailable"}
            
        data = {
            "query": query, "search_depth": search_depth, "topic": topic, "days": days,
            "max_results": max_results, "include_domains": include_domains or self.include_domains,
            "exclude_domains": exclude_domains or self.exclude_domains, "include_answer": include_answer,
            "include_raw_content": include_raw_content, "include_images": include_images,
            "api_key": self.api_key, "use_cache": use_cache
        }
        self.logger.debug(f"Executing async Tavily search for query: {query[:50]}...")
        try:
            # Log more details about the request
            self.logger.debug(f"Request URL: {self.base_url}, Headers: {self.headers}")
            
            async with session.post(self.base_url, json=data, headers=self.headers, timeout=aiohttp.ClientTimeout(total=100)) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.debug(f"Async search successful, received {len(result.get('results', []))} results")
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
                tasks = [self._search_async(session, q, max_results=max_results, topic=self.topic) for q in queries]
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

    def search(self) -> List[Dict[str, str]]:
        if not self.query or len(self.query.strip()) < 3:
            self.logger.warning("Search query too short or empty")
            raise ValueError("Query too short or empty")
        result = asyncio.run(self.search_batch([self.query]))[0]
        return result.get("results", [])

    def batch_queries(self, queries: List[str], batch_size: int = 4) -> List[List[str]]:
        return [queries[i:i + batch_size] for i in range(0, len(queries), batch_size)]