# Tavily API Retriever

# libraries
import os
from typing import Literal, Sequence, Optional, List, Dict
import requests
import json
import logging


class TavilySearch():
    """
    Tavily API Retriever
    """

    def __init__(self, query, headers=None, topic="general", include_domains=None, exclude_domains=None, logger=None):
        """
        Initializes the TavilySearch object
        Args:
            query: The search query
            headers: Optional headers
            topic: The topic of the search
            include_domains: List of domains to include in the search
            exclude_domains: List of domains to exclude from the search
            logger: Optional logger instance
        """
        self.query = query
        self.headers = headers or {}
        self.topic = topic
        self.include_domains = include_domains
        self.exclude_domains = exclude_domains
        self.base_url = "https://api.tavily.com/search"
        self.logger = logger or logging.getLogger("TavilySearch")
        
        try:
            self.api_key = self.get_api_key()
            self.headers.update({
                "Content-Type": "application/json",
            })
        except Exception as e:
            self.logger.error(f"Error initializing TavilySearch: {str(e)}")
            raise

    def get_api_key(self):
        """
        Gets the Tavily API key
        Returns:
            The API key
        """
        api_key = self.headers.get("tavily_api_key")
        if not api_key:
            try:
                api_key = os.environ.get("TAVILY_API_KEY")
                if not api_key:
                    raise KeyError("TAVILY_API_KEY environment variable not set")
                self.logger.debug("Using Tavily API key from environment variables")
            except KeyError as e:
                self.logger.error("Tavily API key not found in environment variables")
                raise Exception(
                    "Tavily API key not found. Please set the TAVILY_API_KEY environment variable.") from e
        return api_key

    def _search(self,
                query: str,
                search_depth: Literal["basic", "advanced"] = "basic",
                topic: str = "general",
                days: int = 2,
                max_results: int = 5,
                include_domains: Sequence[str] = None,
                exclude_domains: Sequence[str] = None,
                include_answer: bool = False,
                include_raw_content: bool = False,
                include_images: bool = False,
                use_cache: bool = True,
                ) -> dict:
        """
        Internal search method to send the request to the API.
        """
        self.logger.debug(f"Executing Tavily search for query: {query[:50]}...")

        data = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "days": days,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "max_results": max_results,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_images": include_images,
            "api_key": self.api_key,
            "use_cache": use_cache,
        }

        try:
            response = requests.post(
                self.base_url, 
                data=json.dumps(data), 
                headers=self.headers, 
                timeout=100
            )

            if response.status_code == 200:
                result = response.json()
                self.logger.debug(f"Tavily search successful, received {len(result.get('results', []))} results")
                return result
            else:
                self.logger.error(f"Tavily API returned error: {response.status_code} - {response.text}")
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error in Tavily search: {str(e)}")
            raise

    def search(self, max_results=7) -> List[Dict[str, str]]:
        """
        Searches the query
        Args:
            max_results: Maximum number of results to return
        Returns:
            List of search results with href and body
        """
        search_response = []
        
        try:
            # Search the query
            self.logger.info(f"Performing Tavily search: {self.query[:50]}...")
            results = self._search(
                self.query, 
                search_depth="basic", 
                max_results=max_results, 
                topic=self.topic,
                include_domains=self.include_domains,
                exclude_domains=self.exclude_domains
            )
            
            sources = results.get("results", [])
            self.logger.info(f"Tavily search returned {len(sources)} sources")
            
            if not sources:
                self.logger.warning("No results found with Tavily API search")
                return []
                
            # Return the results
            search_response = [{"href": obj["url"],
                                "body": obj["content"]} for obj in sources]
        except Exception as e:
            self.logger.error(f"Error in Tavily search: {str(e)}")
            search_response = []
            
        return search_response
