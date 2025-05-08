from mcp.server.fastmcp import FastMCP
import sys
import os

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)
from backend.retriever.tavily_search import TavilySearch
from backend.utils.cache_utils import CacheManager
import logging

# Set up logging
logger = logging.getLogger("TavilyServer")
mcp = FastMCP("Tavily")

@mcp.resource("data://tavily/{query}/{project_name}")
async def search_web(query: str, project_name: str = None) -> dict:
    """Search the web using Tavily for a given query."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Try to get from cache first
    cached_data = cache_manager.load("tavily", "search", query)
    if cached_data:
        logger.info(f"Using cached search data for {query}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
        
    try:
        # Initialize the TavilySearch instance with the exact query
        logger.info(f"Creating TavilySearch with exact query: '{query}'")
        searcher = TavilySearch(query=query, project_name=project_name)
        
        # Check if we have a valid API key
        api_key = searcher.api_key
        if api_key == "tavily-fallback-key":
            logger.warning(f"No valid Tavily API key available - returning empty results for {query}")
            error_response = {
                "error": "Tavily API key not configured. Please add TAVILY_API_KEY to your environment.",
                "results": []
            }
            # Cache this error to prevent repeated failures
            cache_manager.save(error_response, "tavily", "search", query)
            return error_response
        
        # Execute the search with a valid key - use the query exactly as provided
        result = await searcher.search()
        
        # Cache the result
        cache_manager.save(result, "tavily", "search", query)
        logger.info(f"Cached new search data for query: '{query}'" + (f" in project {project_name}" if project_name else ""))
        
        return result
    
    except Exception as e:
        error_response = {
            "error": str(e),
            "results": []
        }
        # Cache the error to prevent repeated failures
        cache_manager.save(error_response, "tavily", "search", query)
        logger.error(f"Error in Tavily search for query '{query}': {str(e)}")
        
        return error_response

@mcp.resource("data://tavily/research/{query}")
async def research_topic(query: str) -> dict:
    """Perform in-depth research on a topic using Tavily."""
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query:
            query_str = query["query"]
        elif "project_name" in query and isinstance(query["project_name"], str):
            query_str = query["project_name"]
        else:
            # Convert dict to string as fallback
            query_str = str(query)
            # Remove curly braces for better search results
            query_str = query_str.replace("{", "").replace("}", "")
    else:
        query_str = query
    
    # Ensure query is a non-empty string
    if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 2:
        logger.error(f"Invalid query: {query_str}")
        return {"error": f"Invalid query: {query_str}"}
    
    # Extract project name from first word for caching
    words = query_str.split()
    project_name = None
    if len(words) > 0:
        potential_project = words[0]
        # Check if first word appears to be a project name (shorter token, possibly all caps)
        if len(potential_project) < 10 or potential_project.isupper():
            project_name = potential_project
            logger.info(f"Extracted project name for caching: '{project_name}'")
    
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first with normalized query
    normalized_query = query_str.lower().strip()
    cached_data = cache_manager.load("tavily", "research", normalized_query)
    if cached_data:
        logger.info(f"Using cached research data for '{query_str}'" + (f" in project '{project_name}'" if project_name else ""))
        return cached_data
    
    try:
        # Initialize TavilySearch with the string query
        logger.info(f"Performing research on: '{query_str}' with project_name='{project_name}'")
        tavily_search = TavilySearch(query=query_str, project_name=project_name)
        
        # Perform research
        result = await tavily_search.research(query_str, project_name=project_name)
        
        # Cache the result
        cache_manager.save(result, "tavily", "research", normalized_query)
        logger.info(f"Cached research data for '{query_str}'")
        
        return result
    except Exception as e:
        error_msg = f"Error in research_topic: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "query": query_str}

@mcp.resource("data://tavily/research/{query}/{project_name}")
async def research_with_project(query: str, project_name: str) -> dict:
    """Perform in-depth research on a topic using Tavily with explicit project name."""
    logger.info(f"Research with explicit project name: query='{query}', project_name='{project_name}'")
    
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query:
            query_str = query["query"]
        elif "project_name" in query and isinstance(query["project_name"], str):
            query_str = query["project_name"]
        else:
            # Convert dict to string as fallback
            query_str = str(query)
            # Remove curly braces for better search results
            query_str = query_str.replace("{", "").replace("}", "")
    else:
        query_str = query
    
    # Ensure query is a non-empty string
    if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 2:
        logger.error(f"Invalid query: {query_str}")
        return {"error": f"Invalid query: {query_str}"}
    
    # Initialize cache manager with project-specific directory
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first with normalized query
    normalized_query = query_str.lower().strip()
    cached_data = cache_manager.load("tavily", "research", normalized_query)
    if cached_data:
        logger.info(f"Using cached research data for '{query_str}' in project '{project_name}'")
        return cached_data
    
    try:
        # Initialize TavilySearch with the string query
        logger.info(f"Performing research on: '{query_str}' with project_name='{project_name}'")
        tavily_search = TavilySearch(query=query_str, project_name=project_name)
        
        # Perform research
        result = await tavily_search.research(query_str, project_name=project_name)
        
        # Cache the result
        cache_manager.save(result, "tavily", "research", normalized_query)
        logger.info(f"Cached research data for '{query_str}' in project '{project_name}'")
        
        return result
    except Exception as e:
        error_msg = f"Error in research_with_project: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "query": query_str}

@mcp.resource("data://tavily/simple_research/{query}")
async def simple_research(query: str) -> dict:
    """
    Simplified endpoint for research that doesn't require project_name parameter.
    Maintains compatibility with the RAG retriever format.
    
    This endpoint properly handles query templates from report_config.json
    (e.g. "ondo technical architecture blockchain" where "ondo" is project_name
    and "technical architecture blockchain" is from the query_template).
    """
    logger.info(f"Processing simplified research endpoint with query: {query}")
    
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query:
            query_str = query["query"]
        elif "project_name" in query and isinstance(query["project_name"], str):
            query_str = query["project_name"]
        else:
            # Convert dict to string as fallback
            query_str = str(query)
            # Remove curly braces for better search results
            query_str = query_str.replace("{", "").replace("}", "")
    else:
        query_str = query
    
    # Ensure query is a non-empty string
    if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 2:
        logger.error(f"Invalid query: {query_str}")
        return {"error": f"Invalid query: {query_str}"}
    
    # When query template is used, we should get a full query like
    # "ondo technical architecture blockchain" for the Technical Analysis section
    
    # Extract project name from first word for caching purposes only
    words = query_str.split()
    extracted_project = None
    
    if len(words) > 0:
        # Extract project name from first word for caching purposes only
        potential_project = words[0]
        # Check if first word appears to be a project name (shorter token, possibly all caps)
        if len(potential_project) < 10 or potential_project.isupper():
            extracted_project = potential_project
            logger.info(f"Extracted project name for caching: '{extracted_project}'")
    
    # IMPORTANT: Use the ENTIRE query string to get the complete search benefits
    # from the report_config.json template, rather than just processing part of it
    logger.info(f"Calling research_topic with FULL original query: '{query_str}'")
    return await research_topic(query_str)

@mcp.tool()
async def web_search(query: str, project_name: str = None) -> list:
    """Search the web for information on a given query using Tavily."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("tavily", "tool_search", query)
    if cached_data:
        logger.info(f"Using cached tool search data for {query}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
        
    try:
        # Initialize the TavilySearch instance with project_name
        logger.info(f"Creating TavilySearch with project_name='{project_name}' for query: '{query}'")
        searcher = TavilySearch(query=query, project_name=project_name)
        
        # Check if we have a valid API key
        api_key = searcher.api_key
        if api_key == "tavily-fallback-key":
            logger.warning(f"No valid Tavily API key available - returning empty results for {query}")
            error_response = {
                "error": "Tavily API key not configured. Please add TAVILY_API_KEY to your environment.",
                "results": []
            }
            # Cache this error to prevent repeated failures
            cache_manager.save(error_response, "tavily", "tool_search", query)
            return error_response
            
        # Execute the search with a valid key
        result = await searcher.search()
        
        # Cache the result
        cache_manager.save(result, "tavily", "tool_search", query)
        logger.info(f"Cached new tool search data for {query}" + (f" in project {project_name}" if project_name else ""))
        
        return result
        
    except Exception as e:
        error_response = {
            "error": str(e),
            "results": []
        }
        # Cache the error to prevent repeated failures
        cache_manager.save(error_response, "tavily", "tool_search", query)
        logger.error(f"Error in Tavily tool search for {query}: {str(e)}")
        
        return error_response

@mcp.tool()
async def deep_research(query: str, project_name: str = None) -> dict:
    """Perform comprehensive research on a topic using Tavily Search."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query:
            query_str = query["query"]
        elif "project_name" in query and isinstance(query["project_name"], str):
            query_str = query["project_name"]
        else:
            # Convert dict to string as fallback
            query_str = str(query)
            # Remove curly braces for better search results
            query_str = query_str.replace("{", "").replace("}", "")
    else:
        query_str = query
    
    # Ensure query is a non-empty string
    if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 2:
        logger.error(f"Invalid query: {query_str}")
        return {"error": f"Invalid query: {query_str}"}
    
    # Check cache first
    cache_key = f"deep_research_{query_str.lower().replace(' ', '_')}"
    cached_data = cache_manager.load("tavily", "deep_research", query_str)
    if cached_data:
        logger.info(f"Using cached deep research data for '{query_str}'")
        return cached_data
    
    try:
        # Initialize TavilySearch with the string query
        logger.info(f"Performing deep research on: '{query_str}' with project_name='{project_name}'")
        tavily_search = TavilySearch(query=query_str, project_name=project_name)
        
        # Perform research
        result = await tavily_search.research(query_str, project_name=project_name)
        
        # Cache the result
        cache_manager.save(result, "tavily", "deep_research", query_str)
        
        return result
    except Exception as e:
        error_msg = f"Error in deep_research: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "query": query_str}

@mcp.tool()
async def batch_search(queries: list, project_name: str = None) -> dict:
    """Perform multiple searches in a single batch."""
    # Create a cache key based on the concatenated queries
    if not queries:
        return {"results": [], "count": 0, "error": "No queries provided"}
        
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # For batch searches, we need a deterministic cache key
    cache_key = "_".join([q.lower().strip()[:20] for q in queries])
    
    # Check cache first
    cached_data = cache_manager.load("tavily", "batch_search", cache_key)
    if cached_data:
        logger.info(f"Using cached batch search data for {len(queries)} queries" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    try:
        # Initialize the TavilySearch instance - using exact queries
        logger.info(f"Creating TavilySearch for batch of {len(queries)} queries - using queries exactly as provided")
        searcher = TavilySearch(project_name=project_name)
        
        # Check if we have a valid API key
        api_key = searcher.api_key
        if api_key == "tavily-fallback-key":
            logger.warning(f"No valid Tavily API key available - returning empty results for batch search")
            error_response = {
                "error": "Tavily API key not configured. Please add TAVILY_API_KEY to your environment.",
                "results": [{"results": []} for _ in queries],
                "count": len(queries)
            }
            # Cache this error to prevent repeated failures
            cache_manager.save(error_response, "tavily", "batch_search", cache_key)
            return error_response
            
        # Execute the search with a valid key - use the queries exactly as provided
        results = await searcher.search_batch(queries)
        
        # Package results with metadata
        response = {"results": results, "count": len(results)}
        
        # Cache the result
        cache_manager.save(response, "tavily", "batch_search", cache_key)
        logger.info(f"Cached new batch search data for {len(queries)} queries" + (f" in project {project_name}" if project_name else ""))
        
        return response
        
    except Exception as e:
        error_response = {
            "error": str(e),
            "results": [{"results": []} for _ in queries],
            "count": len(queries)
        }
        # Cache the error to prevent repeated failures
        cache_manager.save(error_response, "tavily", "batch_search", cache_key)
        logger.error(f"Error in Tavily batch search: {str(e)}")
        
        return error_response

@mcp.tool()
async def research(query: str, project_name: str = None) -> dict:
    """
    Tool that directly matches the data://tavily/research/{query} resource pattern.
    This makes the tools discoverable when processing this endpoint format.
    
    Args:
        query: The research query from report_config.json template
        project_name: Optional project name for project-specific caching
        
    Returns:
        Research results from Tavily
    """
    logger.info(f"Tool called: research for query={query}, project_name={project_name}")
    
    # Handle case when query is a dict
    if isinstance(query, dict):
        logger.warning(f"Received query as dict instead of string: {query}")
        # Extract query string from dict
        if "query" in query:
            query_str = query["query"]
        elif "project_name" in query and isinstance(query["project_name"], str):
            query_str = query["project_name"]
        else:
            # Convert dict to string as fallback
            query_str = str(query)
            # Remove curly braces for better search results
            query_str = query_str.replace("{", "").replace("}", "")
    else:
        query_str = query
    
    # Ensure query is a non-empty string
    if not query_str or not isinstance(query_str, str) or len(query_str.strip()) < 2:
        logger.error(f"Invalid query: {query_str}")
        return {"error": f"Invalid query: {query_str}"}
    
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("tavily", "research", query_str)
    if cached_data:
        logger.info(f"Using cached research data for '{query_str}'")
        return cached_data
    
    try:
        # Initialize TavilySearch with the string query
        logger.info(f"Performing research on: '{query_str}' with project_name='{project_name}'")
        tavily_search = TavilySearch(query=query_str, project_name=project_name)
        
        # Perform research
        result = await tavily_search.research(query_str, project_name=project_name)
        
        # Cache the result
        cache_manager.save(result, "tavily", "research", query_str)
        
        return result
    except Exception as e:
        error_msg = f"Error in research: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "query": query_str}

# Add a direct pattern for handling security audits and other common complex queries
@mcp.resource("data://tavily/security/{query}")
async def security_research(query: str) -> dict:
    """Specialized endpoint for security-related research topics."""
    logger.info(f"Security research for: {query}")
    
    # Extract project name from first word for caching
    words = query.split()
    project_name = None
    if len(words) > 0:
        potential_project = words[0]
        # Check if first word appears to be a project name
        if len(potential_project) < 10 or potential_project.isupper():
            project_name = potential_project
            logger.info(f"Extracted project name for security research: '{project_name}'")
    
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Use a more specific cache key for security research
    cache_key = f"security_{query.lower().strip()}"
    cached_data = cache_manager.load("tavily", "security", cache_key)
    if cached_data:
        logger.info(f"Using cached security research data for {query}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    try:
        # Add security-specific terms to the query
        security_query = query + " security audits vulnerabilities risks"
        logger.info(f"Enhanced security query: '{security_query}'")
        
        # Create TavilySearch instance 
        searcher = TavilySearch(project_name=project_name)
        
        # Execute the search
        result = await searcher.research(security_query, project_name=project_name)
        
        # Cache the results
        cache_manager.save(result, "tavily", "security", cache_key)
        logger.info(f"Cached security research data for {query}")
        
        return result
    except Exception as e:
        logger.error(f"Error in security research: {str(e)}")
        error_response = {"error": str(e), "query": query}
        cache_manager.save(error_response, "tavily", "security", cache_key)
        return error_response

@mcp.resource("data://tavily/technical/{query}")
async def technical_research(query: str) -> dict:
    """Specialized endpoint for technical research topics."""
    logger.info(f"Technical research for: {query}")
    
    # Extract project name from first word for caching
    words = query.split()
    project_name = None
    if len(words) > 0:
        potential_project = words[0]
        # Check if first word appears to be a project name
        if len(potential_project) < 10 or potential_project.isupper():
            project_name = potential_project
            logger.info(f"Extracted project name for technical research: '{project_name}'")
    
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Use a more specific cache key for technical research
    cache_key = f"technical_{query.lower().strip()}"
    cached_data = cache_manager.load("tavily", "technical", cache_key)
    if cached_data:
        logger.info(f"Using cached technical research data for {query}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    try:
        # Add technical-specific terms to the query
        technical_query = query + " blockchain technology architecture implementation"
        logger.info(f"Enhanced technical query: '{technical_query}'")
        
        # Create TavilySearch instance 
        searcher = TavilySearch(project_name=project_name)
        
        # Execute the search
        result = await searcher.research(technical_query, project_name=project_name)
        
        # Cache the results
        cache_manager.save(result, "tavily", "technical", cache_key)
        logger.info(f"Cached technical research data for {query}")
        
        return result
    except Exception as e:
        logger.error(f"Error in technical research: {str(e)}")
        error_response = {"error": str(e), "query": query}
        cache_manager.save(error_response, "tavily", "technical", cache_key)
        return error_response

if __name__ == "__main__":
    mcp.run(transport="stdio")
