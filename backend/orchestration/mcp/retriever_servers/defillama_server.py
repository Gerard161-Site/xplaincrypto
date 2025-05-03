from mcp.server.fastmcp import FastMCP
import sys
import os
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, List

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)
from backend.retriever.defillama_api import DeFiLlamaAPI

# Import our cache utility
from backend.utils.cache_utils import CacheManager

# Set up logging
logger = logging.getLogger("DeFiLlamaServer")

# Initialize MCP server
mcp = FastMCP("DeFiLlama")

# Add a debug tool to verify registration
@mcp.tool()
def debug_test():
    """Simple debug test to verify tool registration."""
    logger.info("Debug test tool called successfully")
    return {"status": "success", "message": "DeFiLlama server tools are registering correctly"}

# Initialize cache manager - properly initialized in each endpoint call
cache_manager = None

# Set project-specific cache manager
def init_with_project(project_name):
    """Initialize with project-specific cache."""
    global cache_manager
    if not project_name or project_name == "default":
        raise ValueError("Valid project_name is required for DeFiLlama server initialization")
        
    logger.info(f"Initializing DeFiLlama server with project: {project_name}")
    # Create the project directory to ensure it exists
    project_cache_dir = os.path.join("docs", project_name, "cache")
    os.makedirs(project_cache_dir, exist_ok=True)
    # Now initialize the cache manager with the project name
    cache_manager = CacheManager(project_name=project_name, logger=logger)

# Special cases mapping for common protocols
SPECIAL_CASES = {
    "BTC": "bitcoin-staking", 
    "ETH": "ethereum-staking", 
    "ONDO": "ondo-finance", 
    "MKR": "makerdao", 
    "UNI": "uniswap",
    "AAVE": "aave-v3",
    "COMP": "compound-v3",
    "SNX": "synthetix"
}

@mcp.resource("data://defillama/{protocol}")
async def get_defillama_data(protocol: str) -> dict:
    """Fetch TVL and protocol data from DeFiLlama for a given protocol."""
    # For simple resource endpoints, we need to use a real project name
    # We'll use the protocol name itself as the project
    project_name = protocol
        
    # Set project-specific cache
    init_with_project(project_name)
        
    # Check cache first
    cached_data = cache_manager.load("defillama", "general", protocol.lower(), ttl_seconds=10800)  # 3 hour TTL
    if cached_data:
        logger.info(f"Using cached DeFiLlama data for {protocol}")
        return cached_data
        
    try:
        # Fetch the data
        data = await fetch_protocol_data(protocol, project_name)
        
        # Cache the result if successful
        if "error" not in data:
            cache_manager.save(data, "defillama", "general", protocol.lower(), ttl_seconds=10800)
            logger.info(f"Cached DeFiLlama data for {protocol}")
        else:
            logger.warning(f"Not caching error response for {protocol}: {data['error']}")
            
        return data
    except Exception as e:
        error_response = {"error": f"Failed to fetch DeFiLlama data: {str(e)}"}
        logger.error(f"Error in get_defillama_data for {protocol}: {str(e)}")
        return error_response

@mcp.resource("data://defillama/{protocol}/{project_name}")
async def get_defillama_data_with_project(protocol: str, project_name: str) -> dict:
    """Fetch TVL and protocol data from DeFiLlama for a given protocol with project-specific caching."""
    if not project_name:
        return {"error": "project_name is required for DeFiLlama data retrieval"}
        
    # Set project-specific cache
    init_with_project(project_name)
        
    # Check cache first
    cached_data = cache_manager.load("defillama", "general", protocol.lower(), ttl_seconds=10800)  # 3 hour TTL
    if cached_data:
        logger.info(f"Using cached DeFiLlama data for {protocol} in project {project_name}")
        return cached_data
        
    try:
        # Fetch the data
        data = await fetch_protocol_data(protocol, project_name)
        
        # Cache the result if successful
        if "error" not in data:
            cache_manager.save(data, "defillama", "general", protocol.lower(), ttl_seconds=10800)
            logger.info(f"Cached DeFiLlama data for {protocol} in project {project_name}")
        else:
            logger.warning(f"Not caching error response for {protocol}: {data['error']}")
            
        return data
    except Exception as e:
        error_response = {"error": f"Failed to fetch DeFiLlama data: {str(e)}"}
        logger.error(f"Error in get_defillama_data for {protocol}: {str(e)}")
        return error_response

@mcp.resource("data://defillama/tvl/{protocol}/{project_name}")
async def get_tvl_data(protocol: str, project_name: str = ""):
    """Get TVL data for a protocol.
    
    Args:
        protocol: The protocol name or slug.
        project_name: The project name (required for caching).
        
    Returns:
        TVL data for the protocol.
    """
    if not project_name:
        return {"error": "project_name is required for getting TVL data"}
    
    # Initialize the project for this request
    init_with_project(project_name)
    
    # Check cache first
    cache_key = f"tvl_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)  # 3 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached TVL data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Call the implementation 
    return await _fetch_tvl_data_impl(protocol, project_name)

@mcp.resource("data://defillama/yields/{protocol}/{project_name}")
async def get_yields_data(protocol: str, project_name: str = ""):
    """Get yields data for a protocol."""
    if not project_name:
        return {"error": "project_name is required for DeFiLlama yields data retrieval"}
        
    init_with_project(project_name)
    return await get_protocol_yields_data(protocol, project_name)

@mcp.resource("data://defillama/protocol/{protocol}/{project_name}")
async def get_protocol_data(protocol: str, project_name: str = ""):
    """Get protocol data from DeFiLlama."""
    if not project_name:
        return {"error": "project_name is required for DeFiLlama protocol data retrieval"}
        
    init_with_project(project_name)
        
    # Check cache first
    cache_key = f"protocol_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "protocol", cache_key, ttl_seconds=24 * 60 * 60)  # 24 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached protocol data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Fetch data
    api = DeFiLlamaAPI(project_name=project_name)
    try:
        data = await api.get_protocol_data(protocol_id)
        if data:
            # Cache data
            cache_manager.save(data, "defillama", "protocol", cache_key, ttl_seconds=24 * 60 * 60)
            return data
        else:
            return {"error": f"Failed to fetch protocol data for {protocol}"}
    except Exception as e:
        logger.error(f"Error fetching protocol data for {protocol}: {e}")
        return {"error": f"Error fetching protocol data: {str(e)}"}

@mcp.resource("data://defillama/protocol/tvl/{protocol}/{project_name}")
@mcp.tool()
async def get_protocol_tvl_data(protocol: str, project_name: str = ""):
    """Get TVL data for a protocol.
    
    Args:
        protocol: The protocol name or slug.
        project_name: The project name (required for caching).
        
    Returns:
        TVL data for the protocol.
    """
    if not project_name:
        return {"error": "project_name is required for getting protocol TVL data"}
    
    # Initialize the project for this request
    init_with_project(project_name)
    
    # Check cache first
    cache_key = f"tvl_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)  # 3 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached TVL data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Fetch data
    api = DeFiLlamaAPI(project_name=project_name)
    try:
        data = await api.get_tvl_data(protocol_id)
        if data:
            # Cache data
            cache_manager.save(data, "defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)
            return data
        else:
            return {"error": f"Failed to fetch TVL data for {protocol}"}
    except Exception as e:
        logger.error(f"Error fetching TVL data for {protocol}: {e}")
        return {"error": f"Error fetching TVL data: {str(e)}"}

# Also register directly as a tool without the resource path to ensure it's accessible
@mcp.tool(name="get_tvl_data")
async def get_tvl_data_tool(protocol: str, project_name: str = ""):
    """Get TVL data for a protocol through a direct tool call.
    
    Args:
        protocol: The protocol name or slug.
        project_name: The project name (required for caching).
        
    Returns:
        TVL data for the protocol.
    """
    # Delegate to the main implementation
    return await get_protocol_tvl_data(protocol, project_name)

@mcp.resource("data://defillama/protocol/yields/{protocol}/{project_name}")
async def get_protocol_yields_data(protocol: str, project_name: str = ""):
    """Get yields data for a specific protocol."""
    if not project_name:
        return {"error": "project_name is required for DeFiLlama protocol yields data retrieval"}
        
    init_with_project(project_name)
        
    # Check cache first
    cache_key = f"yields_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "yields", cache_key, ttl_seconds=3 * 60 * 60)  # 3 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached yields data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Fetch data
    api = DeFiLlamaAPI(project_name=project_name)
    try:
        data = await api.get_yields_data(protocol_id)
        if data:
            # Cache data
            cache_manager.save(data, "defillama", "yields", cache_key, ttl_seconds=3 * 60 * 60)
            return data
        else:
            return {"error": f"Failed to fetch yields data for {protocol}"}
    except Exception as e:
        logger.error(f"Error fetching yields data for {protocol}: {e}")
        return {"error": f"Error fetching yields data: {str(e)}"}

@mcp.resource("data://defillama/search/{query}/{project_name}")
async def search_protocols(query: str, project_name: str = ""):
    """Search for protocols by name."""
    if not project_name:
        return {"error": "project_name is required for DeFiLlama protocol search"}
        
    init_with_project(project_name)
        
    # Check cache first
    cache_key = f"search_{query.lower()}"
    cached_data = cache_manager.load("defillama", "search", cache_key, ttl_seconds=24 * 60 * 60)  # 24 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached protocol search for {query}")
        return cached_data
    
    # Special case handling
    if query.upper() in SPECIAL_CASES:
        return {"protocols": [SPECIAL_CASES[query.upper()]]}
    
    # Fetch data
    api = DeFiLlamaAPI(project_name=project_name)
    try:
        results = await api.search_protocols(query)
        if results:
            data = {"protocols": results}
            # Cache data
            cache_manager.save(data, "defillama", "search", cache_key, ttl_seconds=24 * 60 * 60)
            return data
        else:
            return {"protocols": []}
    except Exception as e:
        logger.error(f"Error searching for protocols with query {query}: {e}")
        return {"error": f"Error searching for protocols: {str(e)}"}

# Helper functions for fetching data from the DeFiLlama API

async def fetch_protocol_data(protocol: str, project_name: str = "") -> Dict[str, Any]:
    """Fetch detailed protocol data from DeFiLlama."""
    if not project_name:
        return {"error": "project_name is required for fetching protocol data"}
        
    try:
        logger.info(f"Fetching protocol data for {protocol} from DeFiLlama")
        
        # Find the protocol slug
        slug = await find_protocol_slug(protocol, project_name)
        if not slug:
            return {"error": f"Protocol {protocol} not found in DeFiLlama"}
            
        # Fetch protocol details
        async with aiohttp.ClientSession() as session:
            base_url = "https://api.llama.fi"
            protocol_url = f"{base_url}/protocol/{slug}"
            
            async with session.get(protocol_url) as response:
                if response.status != 200:
                    return {"error": f"Failed to fetch protocol data: Status {response.status}"}
                    
                data = await response.json()
                
        # Extract useful information
        result = {
            "name": data.get("name", protocol),
            "slug": slug,
            "tvl": data.get("tvl", 0),
            "symbol": data.get("symbol", ""),
            "category": data.get("category", ""),
            "chains": data.get("chains", []),
            "description": data.get("description", "")
        }
        
        # Extract TVL history
        tvl_history = []
        tvl_data = None
        
        if isinstance(data.get("tvl"), list):
            tvl_data = data.get("tvl")
        elif isinstance(data.get("chainTvls"), dict) and "all" in data.get("chainTvls", {}):
            tvl_data = data.get("chainTvls", {}).get("all", {}).get("tvl", [])
            
        if tvl_data:
            timestamps = []
            values = []
            
            for item in tvl_data:
                if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                    timestamp = int(item["date"]) * 1000  # Convert to milliseconds
                    tvl_value = item["totalLiquidityUSD"]
                    timestamps.append(timestamp)
                    values.append(tvl_value)
                    tvl_history.append([timestamp, tvl_value])
            
            result["tvl_history"] = tvl_history
            result["timestamps"] = timestamps
            result["values"] = values
            
            logger.info(f"Retrieved TVL history with {len(timestamps)} data points")
            
        # Cache the result if successful
        if result and "error" not in result:
            cache_key = f"protocol_{protocol.lower()}"
            cache_manager.save(result, "defillama", "protocol", cache_key, ttl_seconds=24 * 60 * 60)
            logger.info(f"Cached protocol data for {protocol} with project {project_name}")
            
        return result
            
    except Exception as e:
        logger.error(f"Error in fetch_protocol_data: {str(e)}")
        return {"error": f"Failed to fetch protocol data: {str(e)}"}

async def fetch_tvl_data(protocol: str, project_name: str = "") -> Dict[str, Any]:
    """Fetch TVL data for a specific protocol."""
    if not project_name:
        return {"error": "project_name is required for fetching TVL data"}
        
    try:
        # Normalize protocol name and handle special cases
        protocol_name = protocol.lower()
        
        # Use project_name if provided
        if project_name and project_name.strip():
            # Keep project_name separate from protocol
            # Just ensure we have a valid project_name for caching
            pass
            
        # Apply special case mappings
        if protocol.upper() in SPECIAL_CASES:
            protocol_name = SPECIAL_CASES[protocol.upper()].lower()
            logger.info(f"Using special case mapping for {protocol}: {protocol_name}")
            
        # Initialize the DeFiLlama API
        api = DeFiLlamaAPI(project_name=project_name)
        
        # Use the direct fetch_tvl_data method from DeFiLlamaAPI
        result = await api.fetch_tvl_data(protocol_name)
        
        # Add debug logs to track what's being returned
        logger.info(f"DeFiLlama TVL data for {protocol_name} returned: {type(result)}")
        if isinstance(result, dict):
            keys = list(result.keys())
            logger.info(f"Result keys: {keys}")
            if "error" in result:
                logger.warning(f"Error from DeFiLlama API: {result['error']}")
            if "tvl" in result:
                logger.info(f"TVL value: {result['tvl']}")
                
            # Cache the result if successful
            if "error" not in result:
                cache_key = f"tvl_{protocol.lower()}"
                cache_manager.save(result, "defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)
                logger.info(f"Cached TVL data for {protocol} with project {project_name}")
                
        return result
    except Exception as e:
        logger.error(f"Error in fetch_tvl_data for {protocol}: {str(e)}")
        return {"error": f"Failed to fetch TVL data: {str(e)}"}

async def fetch_yields_data(protocol: str, project_name: str = "") -> Dict[str, Any]:
    """Fetch yields data for a specific protocol."""
    if not project_name:
        return {"error": "project_name is required for fetching yields data"}
        
    try:
        logger.info(f"Fetching yields data for {protocol} from DeFiLlama")
        
        # Find the protocol slug
        slug = await find_protocol_slug(protocol, project_name)
        if not slug:
            return {"error": f"Protocol {protocol} not found in DeFiLlama"}
        
        # DeFiLlama doesn't have a dedicated yields API that's easily accessible
        # For now, return a message that this isn't implemented yet
        return {
            "name": project_name or protocol,
            "slug": slug,
            "message": "Detailed yields data not available yet",
            "yields": []
        }
            
    except Exception as e:
        logger.error(f"Error in fetch_yields_data: {str(e)}")
        return {"error": f"Failed to fetch yields data: {str(e)}"}

async def find_protocol_slug(protocol: str, project_name: str = "") -> Optional[str]:
    """Find the DeFiLlama protocol slug for a given protocol name or symbol."""
    if not project_name:
        logger.warning("project_name is required for finding protocol slug")
        return None
        
    try:
        # Check for special cases first
        protocol_upper = protocol.upper()
        if protocol_upper in SPECIAL_CASES:
            slug = SPECIAL_CASES[protocol_upper]
            logger.info(f"Using known slug for {protocol}: {slug}")
            return slug
            
        # Fetch all protocols from DeFiLlama
        async with aiohttp.ClientSession() as session:
            base_url = "https://api.llama.fi"
            protocols_url = f"{base_url}/protocols"
            
            async with session.get(protocols_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch protocols from DeFiLlama: Status {response.status}")
                    return None
                    
                protocols = await response.json()
        
        # Try to find a match
        protocol_names = [protocol.lower()]
        if project_name:
            protocol_names.append(project_name.lower())
            
        # Add variations
        for name in list(protocol_names):  # Create a copy to avoid modifying during iteration
            protocol_names.append(f"{name}-finance")
            protocol_names.append(f"{name}-protocol")
        
        for p in protocols:
            p_name = p.get("name", "").lower()
            p_symbol = p.get("symbol", "").lower()
            p_slug = p.get("slug", "").lower()
            
            # Check for exact matches
            if protocol.lower() == p_name or protocol.lower() == p_symbol or protocol.lower() == p_slug:
                logger.info(f"Found exact match for {protocol}: {p.get('slug')}")
                return p.get("slug")
                
            # Check for partial matches
            for name in protocol_names:
                if name in p_name or name in p_slug:
                    logger.info(f"Found partial match for {protocol}/{project_name}: {p.get('slug')}")
                    return p.get("slug")
                    
        logger.warning(f"Could not find protocol slug for {protocol}")
        return None
            
    except Exception as e:
        logger.error(f"Error in find_protocol_slug: {str(e)}")
        return None

async def _get_protocol_id(protocol: str, project_name: str = "") -> str:
    """Get the protocol ID for a given protocol name."""
    if not project_name:
        logger.warning("project_name is required for getting protocol ID")
        return ""
        
    # Special case handling
    if protocol.upper() in SPECIAL_CASES:
        return SPECIAL_CASES[protocol.upper()]
    
    # Search for the protocol
    api = DeFiLlamaAPI(project_name=project_name)
    search_results = await api.search_protocols(protocol)
    
    if not search_results:
        return ""
    
    # Return the first result
    if isinstance(search_results, list) and len(search_results) > 0:
        return search_results[0].get("slug", "")
    elif isinstance(search_results, dict) and "protocols" in search_results:
        protocols = search_results["protocols"]
        if protocols and len(protocols) > 0:
            return protocols[0].get("slug", "")
    
    return ""

async def _fetch_tvl_data_impl(protocol: str, project_name: str = ""):
    """Internal implementation to fetch TVL data."""
    if not project_name:
        return {"error": "project_name is required for fetching TVL data"}
        
    # Check cache first
    cache_key = f"tvl_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)  # 3 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached TVL data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Fetch data - pass project_name to the API
    api = DeFiLlamaAPI(project_name=project_name)
    try:
        data = await api.get_tvl_data(protocol_id)
        if data:
            # Cache data
            cache_manager.save(data, "defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)
            return data
        else:
            return {"error": f"Failed to fetch TVL data for {protocol}"}
    except Exception as e:
        logger.error(f"Error fetching TVL data for {protocol}: {e}")
        return {"error": f"Error fetching TVL data: {str(e)}"}

@mcp.tool()
async def get_tvl(protocol: str, project_name: str = None) -> Dict[str, Any]:
    """
    Get TVL data for a protocol directly matching the data://defillama/tvl/{protocol} pattern.
    
    Args:
        protocol: The protocol name or slug
        project_name: Project name for caching (will default to protocol if not provided)
        
    Returns:
        TVL data for the protocol
    """
    # Use the protocol as project_name if none is provided
    effective_project_name = project_name or protocol
    
    logger.info(f"Tool called: get_tvl for protocol={protocol}, project_name={effective_project_name}")
    
    # Initialize with project-specific cache
    init_with_project(effective_project_name)
    
    # Check cache first
    cache_key = f"tvl_{protocol.lower()}"
    cached_data = cache_manager.load("defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)  # 3 hours TTL
    
    if cached_data:
        logger.info(f"Returning cached TVL data for {protocol}")
        return cached_data
    
    # Get the protocol_id
    protocol_id = await _get_protocol_id(protocol, effective_project_name)
    if not protocol_id:
        logger.warning(f"Protocol {protocol} not found in DeFiLlama")
        
        # Try with special cases
        if protocol.upper() in SPECIAL_CASES:
            protocol_id = SPECIAL_CASES[protocol.upper()]
            logger.info(f"Using special case mapping for {protocol}: {protocol_id}")
        else:
            return {"error": f"Protocol {protocol} not found in DeFiLlama"}
    
    # Fetch data using the existing API
    api = DeFiLlamaAPI(project_name=effective_project_name)
    try:
        data = await api.get_tvl_data(protocol_id)
        if data:
            # Cache data
            cache_manager.save(data, "defillama", "tvl", cache_key, ttl_seconds=3 * 60 * 60)
            logger.info(f"Cached TVL data for {protocol}")
            return data
        else:
            return {"error": f"Failed to fetch TVL data for {protocol}"}
    except Exception as e:
        logger.error(f"Error fetching TVL data for {protocol}: {e}")
    def __init__(self, project_name=None):
        """Initialize DeFiLlama API with project name."""
        if not project_name:
            raise ValueError("project_name is required for DeFiLlamaAPI initialization")
            
        self.base_url = "https://api.llama.fi"
        self.yields_url = "https://yields.llama.fi"
        self.project_name = project_name
    
    async def get_protocol_data(self, protocol_id: str) -> dict:
        """Get protocol data for a specific protocol."""
        url = f"{self.base_url}/protocol/{protocol_id}"
        return await self._make_request(url)
    
    async def get_tvl_data(self, protocol_id: str) -> dict:
        """Get TVL data for a specific protocol."""
        url = f"{self.base_url}/protocol/{protocol_id}"
        data = await self._make_request(url)
        if not data or "error" in data:
            return data
        
        # Process TVL history into the expected format
        tvl_history = []
        if "tvl" in data and isinstance(data["tvl"], list):
            for item in data["tvl"]:
                if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                    timestamp = int(item["date"]) * 1000  # Convert to milliseconds
                    tvl_history.append([timestamp, item["totalLiquidityUSD"]])
        
        # Extract just the TVL data from the protocol data
        tvl_data = {
            "tvl": data.get("tvl", 0),
            "tvlByChain": data.get("chainTvls", {}),
            "tvl_history": tvl_history,  # Use the processed history
            "name": data.get("name", ""),
            "symbol": data.get("symbol", ""),
            "description": data.get("description", ""),
            "category": data.get("category", ""),
            "chains": data.get("chains", []),
            "source": "DeFiLlama"
        }
        return tvl_data
    
    async def get_yields_data(self, protocol_id: str) -> dict:
        """Get yields data for a specific protocol."""
        url = f"{self.yields_url}/pools"
        all_pools = await self._make_request(url)
        
        if not all_pools or "error" in all_pools:
            return all_pools
        
        # Filter pools by protocol
        protocol_pools = [
            pool for pool in all_pools
            if pool.get("project", "").lower() == protocol_id.lower()
        ]
        
        if not protocol_pools:
            return {"error": f"No yield pools found for {protocol_id}"}
        
        # Get protocol name from first pool
        project_name = protocol_pools[0].get("project", protocol_id) if protocol_pools else protocol_id
        
        # Format the data
        yield_data = {
            "pools": protocol_pools,
            "protocolName": project_name,
            "totalPools": len(protocol_pools),
            "source": "DeFiLlama Yields"
        }
        
        # Add average APY if pools exist
        if protocol_pools:
            apys = [pool.get("apy", 0) for pool in protocol_pools]
            yield_data["averageApy"] = sum(apys) / len(apys) if apys else 0
        
        return yield_data
    
    async def search_protocols(self, query: str) -> list:
        """Search for protocols by name."""
        url = f"{self.base_url}/protocols"
        all_protocols = await self._make_request(url)
        
        if not all_protocols or "error" in all_protocols:
            return all_protocols
        
        # Search for matching protocols
        query = query.lower()
        results = []
        
        for protocol in all_protocols:
            protocol_name = protocol.get("name", "").lower()
            protocol_symbol = protocol.get("symbol", "").lower()
            slug = protocol.get("slug", "").lower()
            
            if query in protocol_name or query in protocol_symbol or query in slug:
                results.append({
                    "name": protocol.get("name", ""),
                    "symbol": protocol.get("symbol", ""),
                    "slug": protocol.get("slug", ""),
                    "tvl": protocol.get("tvl", 0),
                    "category": protocol.get("category", ""),
                    "chains": protocol.get("chains", [])
                })
        
        # Sort results by TVL (descending)
        results = sorted(results, key=lambda x: x.get("tvl", 0), reverse=True)
        return results
    
    async def _make_request(self, url: str) -> dict:
        """Make a request to the DeFiLlama API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {"error": f"DeFiLlama API error: {response.status}"}
                
                return await response.json()

if __name__ == "__main__":
    mcp.run(transport="stdio")
