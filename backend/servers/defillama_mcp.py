from mcp.server.fastmcp import FastMCP
import aiohttp
import logging
import os
import json
import uvicorn
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger("DeFiLlamaMCP") 
mcp = FastMCP("DeFiLlama")

# Special cases mapping for common protocols, can be expanded
SPECIAL_CASES = {
    "BTC": "bitcoin", # Note: DeFiLlama might not track BTC itself but BTC-related protocols
    "ETH": "ethereum",
    "ONDO": "ondo-finance",
    "ONDO FINANCE": "ondo-finance",
    "MKR": "makerdao",
    "UNI": "uniswap",
    "AAVE": "aave-v3", # Or specific Aave version
    "COMP": "compound-v3", # Or specific Compound version
    "SNX": "synthetix"
}

class DeFiLlamaApiClient:
    """
    An asynchronous client for interacting with the DeFiLlama API.
    Handles API requests for protocol data, TVL, and yields.
    """
    BASE_URL = "https://api.llama.fi"
    YIELDS_URL = "https://yields.llama.fi" # For yields specific data

    async def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Union[Dict[str, Any], List[Any]]:
        """
        Makes an asynchronous GET request to the specified DeFiLlama API URL.

        Args:
            url: The full API URL to request.
            params: A dictionary of query parameters for the request.

        Returns:
            The JSON response from the API as a dictionary or list.

        Raises:
            aiohttp.ClientResponseError: If the API returns an error status.
            Exception: For other network or parsing errors.
        """
        async with aiohttp.ClientSession() as session:
            try:
                logger.debug(f"Requesting DeFiLlama URL: {url} with params: {params}")
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    if 'application/json' in response.headers.get('Content-Type', ''):
                        return await response.json()
                    else:
                        logger.error(f"Non-JSON response from {url}: {await response.text()}")
                        return {"error": "Non-JSON response", "status_code": response.status, "content_type": response.headers.get('Content-Type')}
            except aiohttp.ClientResponseError as e:
                logger.error(f"DeFiLlama API error at {url}: {e.status} - {e.message}")
                return {"error": e.message, "status_code": e.status}
            except aiohttp.ClientConnectionError as e:
                logger.error(f"DeFiLlama connection error for {url}: {str(e)}")
                return {"error": f"Connection error: {str(e)}"}
            except json.JSONDecodeError as e:
                logger.error(f"DeFiLlama JSON decode error for {url}: {str(e)}")
                return {"error": f"JSON decode error: {str(e)}"}
            except Exception as e:
                logger.error(f"Unexpected error requesting DeFiLlama API {url}: {str(e)}")
                return {"error": f"Unexpected error: {str(e)}"}

    async def find_protocol_slug(self, protocol_query: str) -> Optional[str]:
        """
        Finds the DeFiLlama slug for a given protocol name or symbol.
        It checks special cases first, then searches all protocols.

        Args:
            protocol_query: The name, symbol, or potential slug of the protocol.

        Returns:
            The DeFiLlama protocol slug if found, otherwise None.
        """
        protocol_query_upper = protocol_query.upper()
        if protocol_query_upper in SPECIAL_CASES:
            logger.info(f"Using special case slug '{SPECIAL_CASES[protocol_query_upper]}' for '{protocol_query}'")
            return SPECIAL_CASES[protocol_query_upper]

        logger.info(f"Searching for protocol slug for: {protocol_query}")
        all_protocols = await self._request(f"{self.BASE_URL}/protocols")

        if isinstance(all_protocols, dict) and "error" in all_protocols:
            logger.error(f"Failed to fetch protocol list: {all_protocols['error']}")
            return None
        
        if not isinstance(all_protocols, list):
            logger.error(f"Unexpected format for protocol list: {type(all_protocols)}")
            return None

        query_lower = protocol_query.lower()
        for p_data in all_protocols:
            if isinstance(p_data, dict):
                name = p_data.get("name", "").lower()
                symbol = p_data.get("symbol", "").lower()
                slug = p_data.get("slug", "").lower()
                if query_lower == name or query_lower == symbol or query_lower == slug:
                    logger.info(f"Found matching slug '{p_data.get('slug')}' for '{protocol_query}'")
                    return p_data.get("slug")
        
        # More lenient search if no exact match
        for p_data in all_protocols:
             if isinstance(p_data, dict):
                name = p_data.get("name", "").lower()
                slug = p_data.get("slug", "").lower()
                if query_lower in name or query_lower in slug:
                    logger.info(f"Found partial matching slug '{p_data.get('slug')}' for '{protocol_query}'")
                    return p_data.get("slug")

        logger.warning(f"Could not find slug for protocol: {protocol_query}")
        return None

    async def get_protocol_details(self, protocol_slug_or_query: str) -> Dict[str, Any]:
        """Fetches detailed data for a specific protocol by its slug or a query string."""
        slug = await self.find_protocol_slug(protocol_slug_or_query)
        if not slug:
            return {"error": f"Protocol '{protocol_slug_or_query}' not found or slug could not be determined."}

        logger.info(f"Fetching details for protocol slug: {slug}")
        data = await self._request(f"{self.BASE_URL}/protocol/{slug}")
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        # Basic check for expected data structure
        if not isinstance(data, dict):
             return {"error": f"Unexpected data format for protocol {slug}", "received_type": str(type(data))}

        # Add TVL history processing similar to coingecko_server.py
        tvl_history_raw = data.get("tvl", []) # Can be a list of dicts or a simple TVL value
        current_tvl = None
        processed_tvl_history = []

        if isinstance(tvl_history_raw, list):
            for item in tvl_history_raw:
                if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                    # DeFiLlama provides timestamps in seconds, convert to ms for consistency if needed by frontend
                    # For backend consistency, let's keep them as seconds for now.
                    processed_tvl_history.append([item["date"], item["totalLiquidityUSD"]]) 
            if processed_tvl_history:
                current_tvl = processed_tvl_history[-1][1] # Last entry is most recent TVL
        elif isinstance(tvl_history_raw, (int, float)):
            current_tvl = tvl_history_raw # If TVL is just a number

        return {
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "slug": slug,
            "description": data.get("description"),
            "category": data.get("category"),
            "chains": data.get("chains", []),
            "tvl": current_tvl if current_tvl is not None else data.get("tvl"), # Prioritize from history
            "tvl_history": processed_tvl_history,
            "chainTvls": data.get("chainTvls"),
            "mcap": data.get("mcap"), # Market Cap
            "url": data.get("url"),
            "twitter": data.get("twitter"),
            "gecko_id": data.get("gecko_id"),
            "last_updated_timestamp": data.get("lastUpdateTime")
        }

    async def get_protocol_tvl(self, protocol_slug_or_query: str) -> Dict[str, Any]:
        """Fetches TVL data for a specific protocol."""
        details = await self.get_protocol_details(protocol_slug_or_query)
        if "error" in details:
            return details
        return {
            "name": details.get("name"),
            "slug": details.get("slug"),
            "tvl": details.get("tvl"),
            "tvl_history": details.get("tvl_history", [])
        }

    async def search_protocols(self, query: str) -> Dict[str, Any]:
        """Searches for protocols on DeFiLlama."""
        logger.info(f"Searching protocols with query: {query}")
        all_protocols = await self._request(f"{self.BASE_URL}/protocols")

        if isinstance(all_protocols, dict) and "error" in all_protocols:
            return all_protocols
        
        if not isinstance(all_protocols, list):
             return {"error": "Unexpected format for protocol list", "received_type": str(type(all_protocols))}

        results = []
        query_lower = query.lower()
        for p_data in all_protocols:
            if isinstance(p_data, dict):
                name = p_data.get("name", "").lower()
                symbol = p_data.get("symbol", "").lower()
                slug = p_data.get("slug", "").lower()
                if query_lower in name or query_lower in symbol or query_lower in slug:
                    results.append({
                        "name": p_data.get("name"),
                        "symbol": p_data.get("symbol"),
                        "slug": p_data.get("slug"),
                        "category": p_data.get("category"),
                        "chains": p_data.get("chains", []),
                        "tvl": p_data.get("tvl")
                    })
        return {"results": results[:20], "count": len(results)} # Limit to top 20

    async def get_protocol_yields(self, protocol_slug_or_query: str) -> Dict[str, Any]:
        """Fetches yields data for a specific protocol from yields.llama.fi."""
        slug = await self.find_protocol_slug(protocol_slug_or_query)
        if not slug:
            return {"error": f"Protocol '{protocol_slug_or_query}' not found or slug could not be determined."}
        
        logger.info(f"Fetching yields for protocol slug: {slug}")
        # The /pools endpoint lists all pools, we need to filter by project slug
        all_pools_data = await self._request(f"{self.YIELDS_URL}/pools")

        if isinstance(all_pools_data, dict) and "error" in all_pools_data:
            return all_pools_data
        
        if not isinstance(all_pools_data, dict) or "data" not in all_pools_data or not isinstance(all_pools_data["data"], list):
            logger.error(f"Unexpected format for yields data: {type(all_pools_data)}")
            return {"error": "Unexpected format for yields data", "received_data": str(all_pools_data)[:200]}

        protocol_pools = []
        for pool in all_pools_data["data"]:
            if isinstance(pool, dict) and pool.get("project", "").lower() == slug.lower():
                protocol_pools.append(pool)
        
        if not protocol_pools:
            return {"error": f"No yield pools found for protocol slug '{slug}'"}

        return {
            "protocol_slug": slug,
            "pools": protocol_pools,
            "pool_count": len(protocol_pools)
        }

# --- MCP Resources ---
@mcp.resource("data://defillama/protocol/{protocol_query}")
async def get_protocol_data_mcp(protocol_query: str) -> Dict[str, Any]:
    """Get detailed data for a specific DeFi protocol."""
    client = DeFiLlamaApiClient()
    return await client.get_protocol_details(protocol_query)

@mcp.resource("data://defillama/tvl/{protocol_query}")
async def get_tvl_data_mcp(protocol_query: str) -> Dict[str, Any]:
    """Get TVL (Total Value Locked) data for a DeFi protocol."""
    client = DeFiLlamaApiClient()
    return await client.get_protocol_tvl(protocol_query)

@mcp.resource("data://defillama/search/{query}")
async def search_protocols_mcp(query: str) -> Dict[str, Any]:
    """Search for DeFi protocols by name or symbol."""
    client = DeFiLlamaApiClient()
    return await client.search_protocols(query)

@mcp.resource("data://defillama/yields/{protocol_query}")
async def get_yields_data_mcp(protocol_query: str) -> Dict[str, Any]:
    """Get current yield/APY data for pools on a DeFi protocol."""
    client = DeFiLlamaApiClient()
    return await client.get_protocol_yields(protocol_query)

# --- MCP Tools ---
@mcp.tool()
async def get_protocol_info(protocol_identifier: str) -> Dict[str, Any]:
    """
    Tool to fetch detailed information about a specific DeFi protocol from DeFiLlama.
    Args:
        protocol_identifier: Name, symbol, or slug of the protocol (e.g., "Uniswap", "UNI", "uniswap").
    Returns:
        Dictionary containing protocol details like TVL, category, chains, description, etc.
    """
    logger.info(f"Tool 'get_protocol_info' called for: {protocol_identifier}")
    client = DeFiLlamaApiClient()
    return await client.get_protocol_details(protocol_identifier)

@mcp.tool()
async def get_tvl(protocol_identifier: str) -> Dict[str, Any]:
    """
    Tool to fetch TVL (Total Value Locked) data for a specific DeFi protocol from DeFiLlama.
    Args:
        protocol_identifier: Name, symbol, or slug of the protocol.
    Returns:
        Dictionary containing current TVL and historical TVL data.
    """
    logger.info(f"Tool 'get_tvl' called for: {protocol_identifier}")
    client = DeFiLlamaApiClient()
    return await client.get_protocol_tvl(protocol_identifier)

@mcp.tool()
async def find_protocols(search_term: str) -> Dict[str, Any]:
    """
    Tool to search for DeFi protocols on DeFiLlama based on a search term.
    Args:
        search_term: The term to search for (e.g., "lending", "MakerDAO").
    Returns:
        A list of matching protocols with their basic information.
    """
    logger.info(f"Tool 'find_protocols' called with search_term: {search_term}")
    client = DeFiLlamaApiClient()
    return await client.search_protocols(search_term)

@mcp.tool()
async def get_yield_opportunities(protocol_identifier: str) -> Dict[str, Any]:
    """
    Tool to fetch yield farming opportunities (pools, APYs) for a specific DeFi protocol.
    Args:
        protocol_identifier: Name, symbol, or slug of the protocol.
    Returns:
        Dictionary containing a list of yield pools and their APYs for the protocol.
    """
    logger.info(f"Tool 'get_yield_opportunities' called for: {protocol_identifier}")
    client = DeFiLlamaApiClient()
    return await client.get_protocol_yields(protocol_identifier)

async def run_mcp_server(port: int):
    """
    Run the MCP server with Uvicorn on the specified port.
    """
    config = uvicorn.Config(app=mcp.get_asgi_app(), host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    import selectors
    selectors.DefaultSelector = selectors.PollSelector
    print("Entered main block", flush=True)
    logger.info("Entered main block")
    logger.info("Starting DeFiLlama MCP server with stdio")
    print("Starting DeFiLlama MCP server with stdio", flush=True)
    try:
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        logger.debug("New event loop set")
        print("New event loop set", flush=True)
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        logger.debug("Calling mcp.run with stdio")
        print("Calling mcp.run with stdio", flush=True)
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"Error in mcp.run: {str(e)}")
            print(f"Error in mcp.run: {str(e)}", flush=True)
            raise
        logger.debug("MCP server running")
        print("MCP server running", flush=True)
    except Exception as e:
        logger.error(f"Error in mcp.run: {str(e)}")
        print(f"Error in mcp.run: {str(e)}", flush=True)
        raise