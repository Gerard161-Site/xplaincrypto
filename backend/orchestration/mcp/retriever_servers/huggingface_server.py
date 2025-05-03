from mcp.server.fastmcp import FastMCP
import sys
import os

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)
from backend.retriever.huggingface_search import HuggingFaceSearch
from backend.utils.cache_utils import CacheManager
import logging

# Set up logging
logger = logging.getLogger("HuggingFaceServer")

mcp = FastMCP("HuggingFace")

@mcp.resource("data://huggingface/model/{model_id}")
async def get_model_info(model_id: str) -> dict:
    """Fetch model information from HuggingFace for a given model ID."""
    api = HuggingFaceSearch()
    return await api.get_model_info(model_id)

@mcp.resource("data://huggingface/dataset/{dataset_id}")
async def get_dataset_info(dataset_id: str) -> dict:
    """Fetch dataset information from HuggingFace for a given dataset ID."""
    api = HuggingFaceSearch()
    return await api.get_dataset_info(dataset_id)

@mcp.resource("data://huggingface/research/{query}")
async def research_query(query: str) -> dict:
    """
    Perform comprehensive research on a query using HuggingFace resources.
    
    This endpoint properly handles query templates from report_config.json
    (e.g. "ondo technical architecture blockchain") by using the full query text
    while extracting the project name for caching purposes.
    
    Args:
        query: The full research query from the formatted query_template
        
    Returns:
        Research results including relevant models and datasets
    """
    logger.info(f"Processing HuggingFace research with query: {query}")
    
    # Extract project name for caching purposes but use the full query for search
    extracted_project = None
    search_query = query  # Use the complete query for research
    
    words = query.split()
    if len(words) > 1:
        # Assume first word might be project name for caching purposes
        potential_project = words[0]
        # Check if first word appears to be a project name (shorter token, possibly all caps)
        if len(potential_project) < 10 or potential_project.isupper():
            extracted_project = potential_project
            logger.info(f"Extracted project name for caching: '{extracted_project}'")
    
    # Initialize cache manager
    cache_manager = CacheManager(project_name=extracted_project, logger=logger)
    
    # Check cache first - use more specific key with project name when available
    cache_key = f"{query}_{extracted_project}" if extracted_project else query
    cached_data = cache_manager.load("huggingface", "research", cache_key)
    if cached_data:
        logger.info(f"Using cached research data for {cache_key}")
        return cached_data
    
    # Initialize HuggingFace API
    api = HuggingFaceSearch(project_name=extracted_project)
    
    try:
        # Search using the FULL query to properly utilize the query template
        # Search for models related to the query
        models = await api.search_models(search_query, limit=5)
        
        # Search for datasets related to the query
        datasets = await api.search_datasets(search_query, limit=5)
        
        # Combine results
        result = {
            "query": search_query,
            "project": extracted_project,
            "models": models,
            "datasets": datasets,
            "summary": f"Found {len(models)} models and {len(datasets)} datasets related to '{search_query}'"
        }
        
        # Cache the result
        cache_manager.save(result, "huggingface", "research", cache_key)
        logger.info(f"Cached research data for {cache_key}")
        
        return result
    except Exception as e:
        logger.error(f"Error in HuggingFace research: {str(e)}")
        return {"error": str(e), "query": search_query, "project": extracted_project}

@mcp.tool()
async def search_models(query: str, task: str = None, library: str = None) -> list:
    """Search for models on HuggingFace."""
    api = HuggingFaceSearch()
    return await api.search_models(query, task=task, library=library)

@mcp.tool()
async def search_datasets(query: str, task: str = None) -> list:
    """Search for datasets on HuggingFace."""
    api = HuggingFaceSearch()
    return await api.search_datasets(query, task=task)

@mcp.tool()
async def research(query: str, project_name: str = None) -> dict:
    """
    Perform comprehensive research on a topic using HuggingFace resources.
    
    Args:
        query: The research query
        project_name: Optional project name for project-specific caching
        
    Returns:
        Research results including relevant models and datasets
    """
    logger.info(f"Processing HuggingFace research with query: {query}")
    
    # Ensure project_name is treated as a string to avoid os.path.join() issues
    safe_project_name = str(project_name) if project_name is not None else ""
    
    # First extract project and subject from query if it contains them
    # This allows handling queries like "ondo technical details"
    words = query.split()
    extracted_project = None
    search_query = query
    
    if len(words) > 1:
        potential_project = words[0]
        subject = " ".join(words[1:])
        
        # If project_name not provided, use the extracted one
        if not safe_project_name and (len(potential_project) < 10 or potential_project.isupper()):
            extracted_project = potential_project
            search_query = subject
            logger.info(f"Extracted project: '{extracted_project}', subject: '{search_query}'")
    
    # If we extracted a project name and don't have a project_name parameter, use it
    if extracted_project and not safe_project_name:
        safe_project_name = extracted_project
    
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=safe_project_name, logger=logger)
    
    # Use normalized query for caching
    normalized_query = search_query.lower().strip()
    cache_key = f"research_{normalized_query}_{safe_project_name}"
    
    # Try to get from cache first
    cached_data = cache_manager.load("huggingface", "research", cache_key)
    if cached_data:
        logger.info(f"Using cached research data for {search_query}")
        return cached_data
        
    try:
        # Create research result from available information
        # Since we're missing the actual HuggingFace implementation, make a basic result
        api = HuggingFaceSearch()
        
        # Get datasets related to the query
        datasets = await api.search_datasets(search_query)
        
        # Assemble the results
        result = {
            "query": search_query,
            "datasets": datasets,
            "summary": f"Research results for {search_query}"
        }
        
        # Cache the result
        cache_manager.save(result, "huggingface", "research", cache_key)
        logger.info(f"Cached new research data for {search_query}")
        
        return result
    except Exception as e:
        error_response = {
            "error": str(e),
            "query": search_query
        }
        logger.error(f"Error in HuggingFace research: {str(e)}")
        return error_response

# Add a research_topic tool that also matches the resource pattern - providing multiple options
@mcp.tool()
async def research_topic(query: str) -> dict:
    """
    Alternative tool that directly matches the data://huggingface/research/{query} resource.
    Makes the tools discoverable when the system looks for this pattern.
    
    Args:
        query: The research query
        
    Returns:
        Research results from HuggingFace
    """
    return await research_query(query)

if __name__ == "__main__":
    mcp.run(transport="stdio")
