from mcp.server.fastmcp import FastMCP
import sys
import os
import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)
from backend.retriever.tavily_search import TavilySearch
from backend.utils.cache_utils import CacheManager

# Set up logging
logger = logging.getLogger("TavilyServer")
mcp = FastMCP("Tavily")

# Create a cache for API responses
CACHE_DIR = os.path.join("docs", "cache", "tavily")
os.makedirs(CACHE_DIR, exist_ok=True)

# Default project name to use when none is provided
DEFAULT_PROJECT_NAME = "default_project"

# Shared implementation for both research and deep_research endpoints
async def _perform_tavily_search(query: str, project_name: str = None, cache_key: str = None) -> dict:
    """
    Shared implementation for all Tavily search functions to avoid duplicate API calls.
    Uses a single caching mechanism and API call path.
    """
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query and isinstance(query["query"], str):
            query_str = query["query"]
        elif "topic" in query and isinstance(query["topic"], str):
            query_str = query["topic"]
        else:
            # Convert dict to string as fallback
            query_str = str(query).strip('{}')
            
        # Preserve the original query object for cache key
        original_query = query
    else:
        query_str = str(query) if query is not None else ""
        # For string queries, use the query directly as cache key
        original_query = query
    
    # Basic validation
    if not query_str or len(query_str.strip()) < 3:
        logger.warning(f"Query too short or empty: '{query_str}'")
        return {"error": f"Invalid query: {query_str}"}
    
    # Handle case when project_name is None or empty
    if project_name is None or project_name == "":
        project_name_str = DEFAULT_PROJECT_NAME
        logger.warning(f"Received empty project_name, using default: '{project_name_str}'")
    # Handle case when project_name is a dict
    elif isinstance(project_name, dict):
        logger.warning(f"Received project_name as dict instead of string: {project_name}")
        if "project_name" in project_name and isinstance(project_name["project_name"], str):
            project_name_str = project_name["project_name"]
        else:
            # Use a default project name
            project_name_str = DEFAULT_PROJECT_NAME
            logger.warning(f"Using default project name: {project_name_str}")
    else:
        project_name_str = str(project_name)
    
    # Use provided cache_key if available, otherwise use original_query
    cache_key_to_use = cache_key if cache_key is not None else original_query
    logger.info(f"Using cache key: '{cache_key_to_use}' for query '{query_str}'")
    
    # Initialize cache manager with project-specific directory if provided
    try:
        cache_manager = CacheManager(project_name=project_name_str, logger=logger)
        
        # Check cache first - use cache_key_to_use for lookup
        cached_data = cache_manager.load("tavily", "research", cache_key_to_use)
        if cached_data:
            logger.info(f"Using cached research data for '{cache_key_to_use}' with project_name='{project_name_str}'")
            return cached_data
    except ValueError as e:
        logger.warning(f"Cache manager initialization failed: {str(e)}. Using fallback cache.")
        # If CacheManager fails, continue without caching
        cached_data = None
    
    try:
        # Initialize TavilySearch with the string query
        logger.info(f"Performing research on: '{query_str}' with project_name='{project_name_str}'")
        tavily_search = TavilySearch(query=query_str, project_name=project_name_str)
        
        # Perform research - pass cache_key_to_use as cache_key
        result = await tavily_search.research(query_str, project_name=project_name_str, cache_key=cache_key_to_use)
        
        return result
    except Exception as e:
        error_msg = f"Error in tavily search: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "query": query_str}

@mcp.resource("data://tavily/{query}/{project_name}")
async def search_web(query: str, project_name: str = None) -> dict:
    """Search the web using Tavily for a given query."""
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict in search_web: {query}")
        if "query" in query and isinstance(query["query"], str):
            query_str = query["query"]
        else:
            # Convert dict to string as fallback
            query_str = str(query).strip('{}')
    else:
        query_str = str(query) if query is not None else ""
    
    # Handle case when project_name is None or empty
    if project_name is None or project_name == "":
        project_name_str = DEFAULT_PROJECT_NAME
        logger.warning(f"Received empty project_name in search_web, using default: '{project_name_str}'")
    # Handle case when project_name is a dict
    elif isinstance(project_name, dict):
        logger.warning(f"Received project_name as dict: {project_name}")
        if "project_name" in project_name and isinstance(project_name["project_name"], str):
            project_name_str = project_name["project_name"]
        else:
            project_name_str = DEFAULT_PROJECT_NAME
    else:
        project_name_str = str(project_name)
    
    # Initialize cache manager with project-specific directory if provided
    try:
        cache_manager = CacheManager(project_name=project_name_str, logger=logger)
        
        # Try to get from cache first
        cached_data = cache_manager.load("tavily", "search", query_str)
        if cached_data:
            logger.info(f"Using cached search data for {query_str}" + (f" in project {project_name_str}" if project_name_str else ""))
            return cached_data
    except ValueError as e:
        logger.warning(f"Cache manager initialization failed: {str(e)}. Using fallback cache.")
        # If CacheManager fails, continue without caching
        cached_data = None
        
    try:
        # Initialize the TavilySearch instance with the exact query
        logger.info(f"Creating TavilySearch with exact query: '{query_str}'")
        searcher = TavilySearch(query=query_str, project_name=project_name_str)
        
        # Check if we have a valid API key
        api_key = searcher.api_key
        if api_key == "tavily-fallback-key":
            logger.warning(f"No valid Tavily API key available - returning empty results for {query_str}")
            error_response = {
                "error": "Tavily API key not configured. Please add TAVILY_API_KEY to your environment.",
                "results": []
            }
            # Cache this error to prevent repeated failures
            if cached_data is not None:  # Only save if cache manager was created successfully
                cache_manager.save(error_response, "tavily", "search", query_str)
            return error_response
        
        # Execute the search with a valid key - use the query exactly as provided
        result = await searcher.search()
        
        # Cache the result
        if cached_data is not None:  # Only save if cache manager was created successfully
            cache_manager.save(result, "tavily", "search", query_str)
            logger.info(f"Cached new search data for query: '{query_str}'" + (f" in project {project_name_str}" if project_name_str else ""))
        
        return result
    
    except Exception as e:
        error_response = {
            "error": str(e),
            "results": []
        }
        # Cache the error to prevent repeated failures
        if cached_data is not None:  # Only save if cache manager was created successfully
            cache_manager.save(error_response, "tavily", "search", query_str)
        logger.error(f"Error in Tavily search for query '{query_str}': {str(e)}")
        
        return error_response

@mcp.tool("research")
async def research(query: str, project_name: str = None, cache_key: str = None) -> Dict[str, Any]:
    """
    Perform a research query using Tavily.
    
    Args:
        query: The query to search for
        project_name: The project name for cache organization (e.g., "ondo", "bitcoin")
        cache_key: Optional custom cache key to use instead of the query (useful for section-based caching)
        
    Returns:
        Dictionary containing search results with sources
    """
    start_time = time.time()
    logger.info(f"Tavily research query: {query}")
    
    try:
        # Validate project_name
        if not project_name:
            logger.warning(f"No project_name provided for Tavily research, using query as fallback")
            # Instead of using a default, we'll use the first word of the query as project_name
            project_name = query.split()[0].lower() if query else "default"
        
        # Use provided cache_key or generate one from the query
        # This allows for section-specific caching with the same project
        cache_key_to_use = cache_key or query
        logger.info(f"Using cache_key: {cache_key_to_use} for project: {project_name}")
        
        # Initialize cache manager with the project name
        cache_manager = CacheManager(project_name=project_name)
        
        # Check if we have cached results for this query or cache_key
        cached_results = cache_manager.load("tavily", "research", cache_key_to_use)
        
        if cached_results:
            logger.info(f"Using cached Tavily results for '{cache_key_to_use}'")
            # Ensure we always return a dictionary
            if not isinstance(cached_results, dict):
                logger.warning(f"Cached results for '{cache_key_to_use}' is not a dictionary. Converting.")
                return {"results": [{"content": str(cached_results)}]}
            return cached_results
        
        # Create a Tavily search instance
        tavily_search = TavilySearch(project_name=project_name)
        
        # Perform the search - pass project_name and cache_key to research method
        results = await tavily_search.research(query=query, project_name=project_name, cache_key=cache_key_to_use)
        
        # Ensure results is a dictionary
        if not isinstance(results, dict):
            logger.warning(f"Tavily results for '{query}' is not a dictionary. Converting.")
            results = {"results": [{"content": str(results)}]}
        else:
            # Make sure results has a "results" key even if empty
            if "results" not in results:
                results["results"] = []
        
        # Save to cache
        logger.info(f"Saving Tavily results to cache with key: {cache_key_to_use}")
        cache_manager.save(results, "tavily", "research", cache_key_to_use)
        
        # Check if cache was successfully created
        cache_path = os.path.join("docs", project_name.lower(), "cache", "tavily", f"research_{cache_key_to_use}.json")
        if os.path.exists(cache_path):
            logger.info(f"✅ Verified cache file exists at: {cache_path}")
        else:
            logger.warning(f"❌ Failed to create cache file at: {cache_path}")
        
        end_time = time.time()
        logger.info(f"Tavily search completed in {end_time - start_time:.2f} seconds")
        
        return results
    except Exception as e:
        logger.error(f"Error in Tavily research: {str(e)}", exc_info=True)
        return {"error": str(e), "results": []}

@mcp.tool()
async def deep_research(query: str, project_name: str = DEFAULT_PROJECT_NAME, cache_key: str = None) -> dict:
    """
    Perform comprehensive research on a topic using Tavily Search.
    
    This function uses the same shared implementation as research() to avoid duplicate API calls.
    """
    return await _perform_tavily_search(query, project_name, cache_key)

@mcp.tool()
async def research_topic(topic: str, project_name: str = DEFAULT_PROJECT_NAME, cache_key: str = None) -> dict:
    """
    Research a topic using Tavily Search.
    
    This function is an alias for research() to maintain backward compatibility.
    """
    # Handle case when topic is a dict
    if isinstance(topic, dict):
        logger.warning(f"Received topic as dict in research_topic: {topic}")
        if "topic" in topic and isinstance(topic["topic"], str):
            topic_str = topic["topic"]
        elif "query" in topic and isinstance(topic["query"], str):
            topic_str = topic["query"]
        else:
            # Convert dict to string as fallback
            topic_str = str(topic).strip('{}')
    else:
        topic_str = str(topic) if topic is not None else ""
    
    return await _perform_tavily_search(topic_str, project_name, cache_key)

@mcp.tool()
async def research_with_project(query: str, project_name: str = DEFAULT_PROJECT_NAME, cache_key: str = None) -> dict:
    """
    Perform research with an explicit project name parameter.
    
    This function is useful when you need to specify both query and project_name.
    """
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict in research_with_project: {query}")
        if "query" in query and isinstance(query["query"], str):
            query_str = query["query"]
        else:
            # Convert dict to string as fallback
            query_str = str(query).strip('{}')
    else:
        query_str = str(query) if query is not None else ""
    
    # Handle case when project_name is None or empty
    if project_name is None or project_name == "":
        project_name_str = DEFAULT_PROJECT_NAME
        logger.warning(f"Received empty project_name in research_with_project, using default: '{project_name_str}'")
    # Handle case when project_name is a dict
    elif isinstance(project_name, dict):
        logger.warning(f"Received project_name as dict in research_with_project: {project_name}")
        if "project_name" in project_name and isinstance(project_name["project_name"], str):
            project_name_str = project_name["project_name"]
        else:
            project_name_str = DEFAULT_PROJECT_NAME
    else:
        project_name_str = str(project_name)
    
    return await _perform_tavily_search(query_str, project_name_str, cache_key)

@mcp.tool()
async def simple_research(query: str, cache_key: str = None) -> dict:
    """
    Perform basic research without project context.
    
    This is a simplified interface for research() without the project_name parameter.
    """
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict in simple_research: {query}")
        if "query" in query and isinstance(query["query"], str):
            query_str = query["query"]
        else:
            # Convert dict to string as fallback
            query_str = str(query).strip('{}')
    else:
        query_str = str(query) if query is not None else ""
    
    return await _perform_tavily_search(query_str, DEFAULT_PROJECT_NAME, cache_key)

if __name__ == "__main__":
    mcp.run(transport="stdio")
