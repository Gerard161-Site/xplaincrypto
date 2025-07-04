from mcp.server.fastmcp import FastMCP
import sys
import os
import json
import logging
from pathlib import Path
import requests
from typing import Dict, Any, Optional
import datetime

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)

# Import utility classes for extraction
try:
    from backend.utils.whitepaper_extractor import WhitepaperExtractor
    from backend.retriever_backup.token_info_extractor import TokenInfoExtractor
    from backend.utils.cache_utils import CacheManager
except ImportError:
    from utils.whitepaper_extractor import WhitepaperExtractor
    from retriever_backup.token_info_extractor import TokenInfoExtractor
    from utils.cache_utils import CacheManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TokenomicsServer")

# Initialize cache manager and extractors
cache_manager = None # Will be properly initialized in init_with_project with a real project name
whitepaper_extractor = None # Will be properly initialized in init_with_project
token_info_extractor = None # Will be properly initialized in init_with_project

mcp = FastMCP("Tokenomics")

# Tokenomics extractor instance will be initialized properly in init_with_project
tokenomics_extractor = None

# Function to initialize project-specific cache and extractor
def init_with_project(project_name):
    """Initialize with project-specific cache."""
    global cache_manager, tokenomics_extractor, token_info_extractor, whitepaper_extractor
    if not project_name or project_name == "default":
        raise ValueError("Valid project_name is required for Tokenomics server initialization")
        
    logger.info(f"Initializing Tokenomics server with project: {project_name}")
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    tokenomics_extractor = TokenInfoExtractor(logger=logger, project_name=project_name)
    token_info_extractor = TokenInfoExtractor(logger=logger, project_name=project_name)
    whitepaper_extractor = WhitepaperExtractor(logger=logger, project_name=project_name)

async def get_whitepaper_url_from_cmc(project_name: str) -> Optional[str]:
    """
    Retrieve whitepaper URL from CoinMarketCap API.
    
    Args:
        project_name: The name of the cryptocurrency project
        
    Returns:
        Whitepaper URL if found, None otherwise
    """
    # Check cache first
    cached_data = cache_manager.load("coinmarketcap", "whitepaper", project_name.lower())
    if cached_data and cached_data.get("whitepaper_url"):
        logger.info(f"Retrieved whitepaper URL for {project_name} from cache")
        return cached_data.get("whitepaper_url")
    
    # Try to use CoinMarketCap API
    cmc_api_key = os.environ.get("CMC_API_KEY")
    if not cmc_api_key:
        logger.warning("CMC_API_KEY not found in environment variables")
        
        # Search for documentation URLs without API key
        logger.info(f"Attempting to find documentation URL for {project_name} without API key")
        try:
            # Try searching for reports using TokenInfoExtractor's method
            doc_url = token_info_extractor._get_whitepaper_url(project_name)
            if doc_url:
                logger.info(f"Found documentation URL for {project_name}: {doc_url}")
                # Cache the result
                cache_data = {
                    "whitepaper_url": doc_url,
                    "project_name": project_name,
                    "source": "web_search"
                }
                cache_manager.save(cache_data, "coinmarketcap", "whitepaper", project_name.lower())
                return doc_url
        except Exception as e:
            logger.error(f"Error finding documentation URL: {str(e)}")
        
        return None
    
    try:
        logger.info(f"Looking up whitepaper URL for {project_name} via CoinMarketCap")
        
        headers = {
            'X-CMC_PRO_API_KEY': cmc_api_key,
            'Accept': 'application/json'
        }
        
        params = {'slug': project_name.lower()}
        response = requests.get(
            'https://pro-api.coinmarketcap.com/v2/cryptocurrency/info',
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            # Extract the first data item
            if data.get('data') and len(data['data']) > 0:
                coin_data = next(iter(data['data'].values()))
                urls = coin_data.get('urls', {})
                
                whitepaper_url = None
                # First try technical doc, then whitepaper, then website
                if urls.get('technical_doc') and urls['technical_doc']:
                    whitepaper_url = urls['technical_doc'][0]
                    logger.info(f"Found technical doc URL from CMC: {whitepaper_url}")
                elif urls.get('whitepaper') and urls['whitepaper']:
                    whitepaper_url = urls['whitepaper'][0]
                    logger.info(f"Found whitepaper URL from CMC: {whitepaper_url}")
                elif urls.get('website') and urls['website']:
                    whitepaper_url = urls['website'][0]
                    logger.info(f"Using website URL from CMC: {whitepaper_url}")
                
                # Cache the result
                if whitepaper_url:
                    cache_data = {
                        "whitepaper_url": whitepaper_url,
                        "project_name": project_name,
                        "source": "coinmarketcap"
                    }
                    cache_manager.save(cache_data, "coinmarketcap", "whitepaper", project_name.lower())
                
                return whitepaper_url
    
    except Exception as e:
        logger.error(f"Error getting whitepaper URL from CMC: {str(e)}")
    
    return None

async def extract_token_distribution(project_name: str, whitepaper_url: str) -> Dict[str, Any]:
    """
    Extract token distribution data from a whitepaper URL.
    
    Args:
        project_name: The name of the cryptocurrency project
        whitepaper_url: URL to the project's whitepaper
        
    Returns:
        Token distribution data dictionary
    """
    # Use the cache manager instead of direct path access
    # Get from cache manager
    cached_data = cache_manager.load("tokenomics", "distribution", project_name.lower())
    if cached_data:
        logger.info(f"Retrieved token distribution for {project_name} from cache manager")
        return cached_data
    
    try:
        # Extract token distribution using WhitepaperExtractor
        logger.info(f"Extracting token distribution for {project_name} from {whitepaper_url}")
        extracted_data = whitepaper_extractor.extract_data(
            url=whitepaper_url,
            data_type="token_distribution",
            project_name=project_name
        )
        
        # Format the data appropriately for API response
        token_allocation = extracted_data.get("data", {}).get("token_allocation", {})
        total_supply = extracted_data.get("data", {}).get("total_supply", "Unavailable")
        vesting_details = extracted_data.get("data", {}).get("vesting_details", {})
        
        # If whitepaper extraction didn't yield results, try TokenInfoExtractor as backup
        if not token_allocation:
            logger.info(f"No token allocation found in whitepaper, trying TokenInfoExtractor for {project_name}")
            token_info = token_info_extractor.get_token_distribution(project_name, whitepaper_url)
            if token_info and "data" in token_info:
                token_allocation = token_info.get("data", {}).get("token_allocation", {})
                total_supply = token_info.get("data", {}).get("total_supply", total_supply)
                vesting_details = token_info.get("data", {}).get("vesting_details", vesting_details)
        
        # Format response
        result = {
            "token_allocation": token_allocation,
            "token_symbol": project_name.upper(),  # Default to uppercase project name
            "total_supply": total_supply,
            "vesting_details": vesting_details,
            "source": whitepaper_url,
            "extraction_timestamp": extracted_data.get("extraction_timestamp", ""),
            "data_completeness": extracted_data.get("data", {}).get("data_completeness", {})
        }
        
        # Only cache if we have actual token allocation data
        if token_allocation:
            # Save to cache manager
            cache_manager.save(result, "tokenomics", "distribution", project_name.lower())
            logger.info(f"Cached token distribution data for {project_name}")
        else:
            logger.warning(f"No token allocation data found for {project_name}")
            result["data_unavailable"] = True
            result["message"] = f"Could not extract token allocation data for {project_name}"
        
        return result
    except Exception as e:
        logger.error(f"Error extracting token distribution: {str(e)}")
        return {
            "error": str(e),
            "data_unavailable": True,
            "message": f"Failed to extract token distribution for {project_name}"
        }

@mcp.resource("data://tokenomics/distribution/{project}")
async def get_token_distribution(project: str) -> dict:
    """
    Get token distribution data for a project.
    Includes allocation percentages, total supply, and vesting schedules.
    """
    logger.info(f"Resource called: data://tokenomics/distribution/{project}")
    
    # Use default cache manager
    init_with_project(project)
    
    # Check cache first
    cached_data = cache_manager.load("tokenomics", "distribution", project.lower())
    if cached_data:
        logger.info(f"Using cached tokenomics distribution data for {project}")
        return cached_data
    
    try:
        # Get token distribution using TokenInfoExtractor
        data = tokenomics_extractor.get_token_distribution(project)
        
        # Cache the result
        if data and "error" not in data:
            cache_manager.save(data, "tokenomics", "distribution", project.lower())
            logger.info(f"Cached tokenomics distribution data for {project}")
        
        return data or {"error": f"No token distribution found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch token distribution data: {str(e)}"}
        logger.error(f"Error in get_token_distribution for {project}: {str(e)}")
        return error_response

@mcp.resource("data://tokenomics/details/{project}")
async def get_project_details(project: str) -> dict:
    """
    Get comprehensive project details.
    Includes token utility, governance, roadmap, and partnerships.
    """
    logger.info(f"Resource called: data://tokenomics/details/{project}")
    
    # Use default cache manager
    init_with_project(project)
    
    # Check cache first
    cached_data = cache_manager.load("tokenomics", "details", project.lower())
    if cached_data:
        logger.info(f"Using cached tokenomics details for {project}")
        return cached_data
    
    try:
        # Get project details using TokenInfoExtractor
        data = tokenomics_extractor.get_project_details(project)
        
        # Cache the result
        if data and "error" not in data:
            cache_manager.save(data, "tokenomics", "details", project.lower())
            logger.info(f"Cached tokenomics details data for {project}")
        
        return data or {"error": f"No project details found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch project details: {str(e)}"}
        logger.error(f"Error in get_project_details for {project}: {str(e)}")
        return error_response

@mcp.resource("data://tokenomics/whitepaper/{project}")
async def get_whitepaper_url(project: str) -> dict:
    """
    Get whitepaper URL for a project.
    """
    logger.info(f"Resource called: data://tokenomics/whitepaper/{project}")
    
    # Use default cache manager
    init_with_project(project)
    
    # Check cache first
    cached_data = cache_manager.load("tokenomics", "whitepaper_url", project.lower())
    if cached_data:
        logger.info(f"Using cached whitepaper URL for {project}")
        return cached_data
    
    try:
        # Get whitepaper URL using TokenInfoExtractor
        url = tokenomics_extractor._get_whitepaper_url(project)
        
        # Cache the result
        if url:
            cache_manager.save(url, "tokenomics", "whitepaper_url", project.lower())
            logger.info(f"Cached whitepaper URL for {project}")
            return {"url": url}
        else:
            return {"error": f"No whitepaper URL found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch whitepaper URL: {str(e)}"}
        logger.error(f"Error in get_whitepaper_url for {project}: {str(e)}")
        return error_response

@mcp.resource("data://tokenomics/distribution/{project}/{project_name}")
async def get_token_distribution_with_project(project: str, project_name: str) -> dict:
    """
    Get token distribution data with project-specific caching.
    """
    logger.info(f"Resource called: data://tokenomics/distribution/{project}/{project_name}")
    
    # Initialize with project-specific cache
    init_with_project(project_name)
    
    # Rest of implementation similar to get_token_distribution
    try:
        # Get token distribution using TokenInfoExtractor
        data = tokenomics_extractor.get_token_distribution(project)
        
        # Cache the result if needed (tokenomics_extractor does this automatically now)
        return data or {"error": f"No token distribution found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch token distribution data: {str(e)}"}
        logger.error(f"Error in get_token_distribution_with_project for {project}/{project_name}: {str(e)}")
        return error_response

@mcp.tool()
async def get_distribution(project: str, project_name: str = "") -> dict:
    """
    Get token distribution data for a cryptocurrency project.
    
    Args:
        project: The name or symbol of the project
        project_name: Optional project name for project-specific caching
    
    Returns:
        Dictionary with token allocation, total supply, and vesting details
    """
    logger.info(f"Tool called: get_distribution for {project}, project_name={project_name}")
    
    if project_name:
        init_with_project(project_name)
    
    try:
        # Get token distribution using TokenInfoExtractor
        data = tokenomics_extractor.get_token_distribution(project)
        return data or {"error": f"No token distribution found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch token distribution data: {str(e)}"}
        logger.error(f"Error in get_distribution tool for {project}: {str(e)}")
        return error_response

@mcp.tool()
async def get_details(project: str, project_name: str = "") -> dict:
    """
    Get comprehensive details for a cryptocurrency project.
    
    Args:
        project: The name or symbol of the project
        project_name: Optional project name for project-specific caching
    
    Returns:
        Dictionary with project details including utility, governance, and roadmap
    """
    logger.info(f"Tool called: get_details for {project}, project_name={project_name}")
    
    if project_name:
        init_with_project(project_name)
    
    try:
        # Get project details using TokenInfoExtractor
        data = tokenomics_extractor.get_project_details(project)
        return data or {"error": f"No project details found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch project details: {str(e)}"}
        logger.error(f"Error in get_details tool for {project}: {str(e)}")
        return error_response

@mcp.tool()
async def get_whitepaper(project: str, project_name: str = "") -> dict:
    """
    Get whitepaper URL for a cryptocurrency project.
    
    Args:
        project: The name or symbol of the project
        project_name: Optional project name for project-specific caching
    
    Returns:
        Dictionary with whitepaper URL or error message
    """
    logger.info(f"Tool called: get_whitepaper for {project}, project_name={project_name}")
    
    if project_name:
        init_with_project(project_name)
    
    try:
        # Get whitepaper URL using TokenInfoExtractor
        url = tokenomics_extractor._get_whitepaper_url(project)
        return {"url": url} if url else {"error": f"No whitepaper URL found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch whitepaper URL: {str(e)}"}
        logger.error(f"Error in get_whitepaper tool for {project}: {str(e)}")
        return error_response

if __name__ == "__main__":
    mcp.run(transport="stdio") 