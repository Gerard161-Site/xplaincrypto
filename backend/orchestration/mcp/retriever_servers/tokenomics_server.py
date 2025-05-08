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
    from backend.retriever.token_info_extractor import TokenInfoExtractor
    from backend.utils.cache_utils import CacheManager
except ImportError:
    from utils.whitepaper_extractor import WhitepaperExtractor
    from retriever.token_info_extractor import TokenInfoExtractor
    from utils.cache_utils import CacheManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TokenomicsServer")
logger.info("TokenomicsServer starting up")

# Add a handler to ensure logs are flushed immediately
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

try:
    from mcp.server.fastmcp import FastMCP
    logger.info("Successfully imported FastMCP")
    mcp = FastMCP("Tokenomics")
    logger.info("Created FastMCP instance")
except Exception as e:
    logger.error(f"Error importing or creating FastMCP: {str(e)}")
    raise

# Initialize cache manager and extractors with default values
# These will be properly initialized with project-specific values when needed
try:
    # Don't initialize with default project name - wait for actual project name
    cache_manager = None
    whitepaper_extractor = None
    token_info_extractor = None
    tokenomics_extractor = None
    logger.info("Extractors and cache manager will be initialized when a project name is provided")
except Exception as e:
    logger.error(f"Error initializing default extractors: {str(e)}")
    # Continue with None values, they will be initialized properly when needed
    cache_manager = None
    whitepaper_extractor = None
    token_info_extractor = None
    tokenomics_extractor = None

# Function to initialize project-specific cache and extractor
def init_with_project(project_name):
    """Initialize with project-specific cache."""
    global cache_manager, tokenomics_extractor, token_info_extractor, whitepaper_extractor, current_project
    
    logger.info(f"init_with_project called with project_name: {project_name}")
    
    # Use the provided project name, ensure it's not empty or None
    if not project_name or project_name.lower() == "default" or project_name.lower() == "unknown":
        logger.error(f"Invalid project_name provided: '{project_name}'")
        raise ValueError(f"Invalid project_name provided: '{project_name}'")
    
    try:
        logger.info(f"Initializing Tokenomics server with project: {project_name}")
        
        # Import required classes with better error handling
        try:
            from backend.utils.cache_utils import CacheManager
            logger.info("Successfully imported CacheManager")
        except ImportError:
            try:
                from utils.cache_utils import CacheManager
                logger.info("Successfully imported CacheManager from alternative path")
            except ImportError as e:
                logger.error(f"Failed to import CacheManager: {str(e)}")
                raise
        
        try:
            from backend.retriever.token_info_extractor import TokenInfoExtractor
            logger.info("Successfully imported TokenInfoExtractor")
        except ImportError:
            try:
                from retriever.token_info_extractor import TokenInfoExtractor
                logger.info("Successfully imported TokenInfoExtractor from alternative path")
            except ImportError as e:
                logger.error(f"Failed to import TokenInfoExtractor: {str(e)}")
                raise
                
        try:
            from backend.utils.whitepaper_extractor import WhitepaperExtractor
            logger.info("Successfully imported WhitepaperExtractor")
        except ImportError:
            try:
                from utils.whitepaper_extractor import WhitepaperExtractor
                logger.info("Successfully imported WhitepaperExtractor from alternative path")
            except ImportError as e:
                logger.error(f"Failed to import WhitepaperExtractor: {str(e)}")
                raise
        
        # Create instances with error handling
        try:
            cache_manager = CacheManager(project_name=project_name, logger=logger)
            logger.info("Successfully created CacheManager instance")
        except Exception as e:
            logger.error(f"Error creating CacheManager: {str(e)}")
            raise
            
        try:
            tokenomics_extractor = TokenInfoExtractor(logger=logger, project_name=project_name)
            logger.info("Successfully created TokenInfoExtractor instance for tokenomics_extractor")
        except Exception as e:
            logger.error(f"Error creating TokenInfoExtractor for tokenomics_extractor: {str(e)}")
            raise
            
        try:
            token_info_extractor = TokenInfoExtractor(logger=logger, project_name=project_name)
            logger.info("Successfully created TokenInfoExtractor instance for token_info_extractor")
        except Exception as e:
            logger.error(f"Error creating TokenInfoExtractor for token_info_extractor: {str(e)}")
            raise
            
        try:
            whitepaper_extractor = WhitepaperExtractor(logger=logger, project_name=project_name)
            logger.info("Successfully created WhitepaperExtractor instance")
        except Exception as e:
            logger.error(f"Error creating WhitepaperExtractor: {str(e)}")
            raise
            
        # Store the current project name in a global variable for context
        current_project = project_name
        
        logger.info(f"Successfully initialized all components for project: {project_name}")
    except Exception as e:
        logger.error(f"Error in init_with_project for {project_name}: {str(e)}", exc_info=True)
        # Re-raise to ensure calling code knows initialization failed
        raise

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
            # Try searching for docs using TokenInfoExtractor's method
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
    # Get from cache manager - use project_name as the cache key
    cache_key = project_name.lower()
    cached_data = cache_manager.load("tokenomics", "distribution", cache_key)
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
            # Save to cache manager using the project-specific cache key
            cache_manager.save(result, "tokenomics", "distribution", cache_key)
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
    """Get token distribution data for a project.
    
    Args:
        project: The project name or symbol
        
    Returns:
        Token distribution data in a standardized format
    """
    if not project:
        return {"error": "Project name is required"}
    
    # Initialize with project
    try:
        init_with_project(project)
    except ValueError as e:
        return {"error": str(e)}
    
    # Check cache first - use project as the cache key without redundant prefixes
    cache_key = project.lower()
    cached_data = cache_manager.load("tokenomics", "distribution", cache_key)
    
    if cached_data:
        logger.info(f"Returning cached token distribution for {project}")
        
        # Ensure the data structure is standardized
        if not _is_standardized_format(cached_data):
            cached_data = _standardize_data_format(cached_data, "tokenomics", "distribution", project)
        
        return cached_data
    
    # Get whitepaper URL first
    whitepaper_url = await get_whitepaper_url(project)
    if isinstance(whitepaper_url, dict) and "data" in whitepaper_url:
        whitepaper_url = whitepaper_url["data"]
    
    if not whitepaper_url or (isinstance(whitepaper_url, dict) and "error" in whitepaper_url):
        logger.warning(f"No whitepaper URL found for {project}")
        return {"error": f"No whitepaper URL found for {project}"}
    
    # Extract token distribution
    distribution_data = await extract_token_distribution(project, whitepaper_url)
    
    # Standardize the data format
    standardized_data = _standardize_data_format(distribution_data, "tokenomics", "distribution", project)
    
    # Cache the standardized result
    cache_manager.save(standardized_data, "tokenomics", "distribution", cache_key)
    
    return standardized_data

@mcp.resource("data://tokenomics/distribution/{project}/{project_name}")
async def get_token_distribution_with_project(project: str, project_name: str) -> dict:
    """
    Get token distribution data for a project with explicit project name parameter.
    
    Args:
        project: The name or symbol of the project to research
        project_name: The project name for project-specific caching
        
    Returns:
        Token distribution data in a standardized format
    """
    logger.info(f"Resource called: data://tokenomics/distribution/{project}/{project_name}")
    
    if not project:
        return {"error": "Project name is required"}
        
    if not project_name:
        logger.warning(f"No project_name provided for {project}, using project as project_name")
        project_name = project
    
    # Initialize with project_name for proper caching
    try:
        init_with_project(project_name)
    except ValueError as e:
        return {"error": str(e)}
    
    # Check cache first - use project as the cache key without redundant prefixes
    cache_key = project.lower()
    cached_data = cache_manager.load("tokenomics", "distribution", cache_key)
    
    if cached_data:
        logger.info(f"Using cached token distribution for {project} in project {project_name}")
        
        # Ensure the data is in standardized format
        if not _is_standardized_format(cached_data):
            cached_data = _standardize_data_format(cached_data, "tokenomics", "distribution", project)
            
        return cached_data
    
    # Get whitepaper URL first
    whitepaper_url = await get_whitepaper_url(project)
    if isinstance(whitepaper_url, dict) and "data" in whitepaper_url:
        whitepaper_url = whitepaper_url["data"]
    
    if not whitepaper_url or (isinstance(whitepaper_url, dict) and "error" in whitepaper_url):
        logger.warning(f"No whitepaper URL found for {project}")
        return {"error": f"No whitepaper URL found for {project}"}
    
    # Extract token distribution
    distribution_data = await extract_token_distribution(project, whitepaper_url)
    
    # Standardize the data format
    standardized_data = _standardize_data_format(distribution_data, "tokenomics", "distribution", project)
    
    # Cache the standardized result
    cache_manager.save(standardized_data, "tokenomics", "distribution", cache_key)
    
    return standardized_data

def _is_standardized_format(data):
    """Check if the data is already in the standardized format."""
    return (
        isinstance(data, dict) and
        "data" in data and
        "metadata" in data and
        isinstance(data["metadata"], dict) and
        "source" in data["metadata"] and
        "endpoint" in data["metadata"] and
        "query" in data["metadata"]
    )

def _standardize_data_format(data, source, endpoint, query):
    """Standardize the data format to ensure consistency."""
    if _is_standardized_format(data):
        return data
        
    # Get current timestamp for caching metadata
    now = datetime.datetime.now()
    
    # Extract the actual content
    if isinstance(data, dict) and "data" in data and "token_allocation" in data["data"]:
        content = data
    elif isinstance(data, dict) and "token_allocation" in data:
        # Data is directly in the root object
        content = {
            "project_name": query,
            "data": {
                "token_allocation": data.get("token_allocation", {}),
                "total_supply": data.get("total_supply"),
                "vesting_details": data.get("vesting_details", {}),
                "additional_info": data.get("additional_info", "")
            },
            "sources": [
                {
                    "title": f"{query.capitalize()} Documentation",
                    "url": data.get("source", "")
                }
            ],
            "extraction_timestamp": data.get("extraction_timestamp", now.isoformat()),
            "documentation_url": data.get("source", "")
        }
    else:
        # Fallback for unexpected structures
        content = {
            "project_name": query,
            "data": data,
            "extraction_timestamp": now.isoformat()
        }
    
    # Build the standardized structure
    standardized = {
        "data": content,
        "metadata": {
            "source": source,
            "endpoint": endpoint,
            "query": query.lower(),
            "cached_at": now.isoformat(),
            "expires_at": (now + datetime.timedelta(hours=24)).isoformat(),
            "ttl_hours": 24.0
        }
    }
    
    return standardized

@mcp.resource("data://tokenomics/details/{project}")
async def get_project_details(project: str) -> dict:
    """
    Get comprehensive tokenomics details for a project.
    
    Args:
        project: The project name or symbol
        
    Returns:
        Comprehensive tokenomics details in a standardized format
    """
    if not project:
        return {"error": "Project name is required"}
    
    # Initialize with project
    init_with_project(project)
    
    # Check cache first
    cache_key = f"details_{project.lower()}"
    cached_data = cache_manager.load("tokenomics", "details", cache_key)
    
    if cached_data:
        logger.info(f"Returning cached tokenomics details for {project}")
        
        # Ensure the data is in standardized format
        if not _is_standardized_format(cached_data):
            cached_data = _standardize_data_format(cached_data, "tokenomics", "details", project)
        
        return cached_data
    
    # First get the distribution data
    distribution_data = await get_token_distribution(project)
    if isinstance(distribution_data, dict) and "data" in distribution_data:
        distribution = distribution_data.get("data", {})
    else:
        distribution = {}
    
    # Get whitepaper URL
    whitepaper_response = await get_whitepaper_url(project)
    whitepaper_url = ""
    if isinstance(whitepaper_response, dict) and "data" in whitepaper_response:
        whitepaper_url = whitepaper_response.get("data", "")
    
    # Compile comprehensive tokenomics data
    try:
        token_info = token_info_extractor.get_token_info(project)
        
        # Combine all available data
        comprehensive_data = {
            "project_name": project,
            "token_symbol": project.upper(),  # Default to uppercase project name
            "data": {
                "token_allocation": distribution.get("data", {}).get("token_allocation", {}),
                "total_supply": distribution.get("data", {}).get("total_supply", "Unavailable"),
                "circulating_supply": token_info.get("circulating_supply", "Unavailable"),
                "max_supply": token_info.get("max_supply", "Unavailable"),
                "market_cap": token_info.get("market_cap", "Unavailable"),
                "fully_diluted_valuation": token_info.get("fully_diluted_valuation", "Unavailable"),
                "genesis_date": token_info.get("genesis_date", "Unavailable"),
                "token_type": token_info.get("token_type", "Unavailable"),
                "vesting_details": distribution.get("data", {}).get("vesting_details", {}),
                "token_utilities": token_info.get("token_utilities", []),
                "governance_rights": token_info.get("governance_rights", "Unavailable"),
                "staking_details": token_info.get("staking_details", {}),
                "emission_schedule": token_info.get("emission_schedule", "Unavailable"),
                "burn_mechanisms": token_info.get("burn_mechanisms", "Unavailable"),
                "additional_info": distribution.get("data", {}).get("additional_info", "")
            },
            "sources": [
                {
                    "title": f"{project.capitalize()} Documentation",
                    "url": whitepaper_url
                }
            ],
            "extraction_timestamp": datetime.datetime.now().isoformat()
        }
        
        # Clean up any None values
        for key, value in list(comprehensive_data["data"].items()):
            if value is None:
                comprehensive_data["data"][key] = "Unavailable"
        
        # Standardize the data format
        standardized_data = _standardize_data_format(comprehensive_data, "tokenomics", "details", project)
        
        # Cache the result
        cache_manager.save(standardized_data, "tokenomics", "details", cache_key)
        logger.info(f"Cached comprehensive tokenomics details for {project}")
        
        return standardized_data
        
    except Exception as e:
        logger.error(f"Error compiling tokenomics details for {project}: {str(e)}")
        error_response = {"error": f"Failed to compile tokenomics details: {str(e)}"}
        return _standardize_data_format(error_response, "tokenomics", "details", project)

@mcp.resource("data://tokenomics/whitepaper/{project}")
async def get_whitepaper_url(project: str) -> dict:
    """
    Get whitepaper URL for a project.
    
    Args:
        project: The project name or symbol
        
    Returns:
        Whitepaper URL in a standardized format
    """
    if not project:
        return {"error": "Project name is required"}
    
    # Initialize with project
    init_with_project(project)
    
    # Check cache first - use a simple cache key without redundant prefixes
    cache_key = project.lower()
    cached_data = cache_manager.load("tokenomics", "whitepaper_url", cache_key)
    
    if cached_data:
        logger.info(f"Returning cached whitepaper URL for {project}")
        
        # Ensure the data is in standardized format
        if not _is_standardized_format(cached_data):
            cached_data = _standardize_data_format(cached_data, "tokenomics", "whitepaper_url", project)
        
        return cached_data
    
    # Get whitepaper URL from CoinMarketCap
    whitepaper_url = await get_whitepaper_url_from_cmc(project)
    
    if not whitepaper_url:
        logger.warning(f"No whitepaper URL found for {project}")
        
        # Try with TokenInfoExtractor as a fallback
        try:
            whitepaper_url = token_info_extractor._get_whitepaper_url(project)
        except Exception as e:
            logger.error(f"Error getting whitepaper URL with TokenInfoExtractor: {str(e)}")
    
    if not whitepaper_url:
        error_response = {"error": f"No whitepaper URL found for {project}"}
        return _standardize_data_format(error_response, "tokenomics", "whitepaper_url", project)
    
    # Standardize data format
    now = datetime.datetime.now()
    standardized_data = {
        "data": whitepaper_url,
        "metadata": {
            "source": "tokenomics",
            "endpoint": "whitepaper_url",
            "query": project.lower(),
            "cached_at": now.isoformat(),
            "expires_at": (now + datetime.timedelta(hours=24)).isoformat(),
            "ttl_hours": 24.0
        }
    }
    
    # Cache the result
    cache_manager.save(standardized_data, "tokenomics", "whitepaper_url", cache_key)
    logger.info(f"Cached whitepaper URL for {project}: {whitepaper_url}")
    
    return standardized_data

@mcp.resource("data://tokenomics/{project}")
async def get_tokenomics(project: str) -> dict:
    """
    Get comprehensive tokenomics data for a project.
    This is a convenience endpoint that combines distribution and details.
    
    Args:
        project: The project name or symbol
        
    Returns:
        Comprehensive tokenomics data in a standardized format
    """
    if not project:
        return {"error": "Project name is required"}
    
    # Initialize with project
    try:
        init_with_project(project)
    except ValueError as e:
        return {"error": str(e)}
    
    # Check cache first
    cache_key = f"{project.lower()}"
    cached_data = cache_manager.load("tokenomics", "tokenomics", cache_key)
    
    if cached_data:
        logger.info(f"Returning cached tokenomics data for {project}")
        return cached_data
    
    # First get the distribution data
    distribution_data = await get_token_distribution(project)
    if isinstance(distribution_data, dict) and "data" in distribution_data:
        distribution = distribution_data.get("data", {})
    else:
        distribution = {}
    
    # Then get the details data
    details_data = await get_project_details(project)
    if isinstance(details_data, dict) and "data" in details_data:
        details = details_data.get("data", {})
    else:
        details = {}
    
    # Combine the data
    combined_data = {
        "project_name": project,
        "distribution": distribution,
        "details": details,
        "extraction_timestamp": datetime.datetime.now().isoformat(),
        "source": "tokenomics"
    }
    
    # Standardize the data format
    standardized_data = _standardize_data_format(combined_data, "tokenomics", project, project)
    
    # Cache the standardized result
    cache_manager.save(standardized_data, "tokenomics", "tokenomics", cache_key)
    
    return standardized_data

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
    
    # Use project as project_name if none provided
    if not project_name:
        project_name = project
    
    try:
        # Use the resource endpoint that handles project_name
        result = await get_token_distribution_with_project(project, project_name)
        return result
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
    
    # Use project as project_name if none provided
    if not project_name:
        project_name = project
    
    try:
        # Initialize with project_name for proper caching
        init_with_project(project_name)
        
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
    
    # Use project as project_name if none provided
    if not project_name:
        project_name = project
    
    try:
        # Initialize with project_name for proper caching
        init_with_project(project_name)
        
        # Get whitepaper URL using TokenInfoExtractor
        url = tokenomics_extractor._get_whitepaper_url(project)
        return {"url": url} if url else {"error": f"No whitepaper URL found for {project}"}
    except Exception as e:
        error_response = {"error": f"Failed to fetch whitepaper URL: {str(e)}"}
        logger.error(f"Error in get_whitepaper tool for {project}: {str(e)}")
        return error_response

if __name__ == "__main__":
    mcp.run(transport="stdio") 