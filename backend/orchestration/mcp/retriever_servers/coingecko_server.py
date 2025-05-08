from mcp.server.fastmcp import FastMCP
import sys
import os
import json
import aiohttp
import time
import logging
import mcp
import traceback
import asyncio
from typing import Dict, Any, Optional, List
import re
from datetime import datetime, timedelta

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)

# Import our new cache utility
from backend.utils.cache_utils import CacheManager

# Setup logging
logger = logging.getLogger("CoinGeckoServer")

# Initialize MCP server
mcp = FastMCP("CoinGecko")

@mcp.resource("data://coingecko/price/{coin}/{project_name}")
async def get_coin_price_data(coin: str, project_name: str = None) -> list:
    """Get basic price data for a coin from CoinGecko."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("coingecko", "price", coin, ttl_seconds=3600)  # 1 hour TTL
    if cached_data:
        logger.info(f"Using cached price data for {coin}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    # If not in cache, fetch from API
    try:
        async with aiohttp.ClientSession() as session:
            # Search for the coin
            search_url = f"https://api.coingecko.com/api/v3/search?query={coin}"
            async with session.get(search_url) as response:
                if response.status != 200:
                    error_msg = f"CoinGecko API error: {response.status}"
                    logger.error(error_msg)
                    return [json.dumps({"error": error_msg})]
                
                search_data = await response.json()
                
                # Get coins from search results
                coins = search_data.get("coins", [])
                if not coins:
                    logger.warning(f"No coins found for query: {coin}")
                    return [json.dumps({"error": "No coins found"})]
                
                # Return top results
                top_results = []
                for c in coins[:10]:  # Return up to 10 results
                    coin_data = {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "symbol": c.get("symbol"),
                        "market_cap_rank": c.get("market_cap_rank")
                    }
                    top_results.append(json.dumps(coin_data))
                
                # Cache the results
                cache_manager.save(top_results, "coingecko", "price", coin, ttl_seconds=3600)
                logger.info(f"Cached price data for {coin}" + (f" in project {project_name}" if project_name else ""))
                
                return top_results
    except Exception as e:
        error_msg = f"Error fetching CoinGecko data: {str(e)}"
        logger.error(error_msg)
        return [json.dumps({"error": error_msg})]

@mcp.resource("data://coingecko/market/{coin}/{project_name}")
async def get_coin_market_data(coin: str, project_name: str = None) -> dict:
    """Get detailed market data for a coin from CoinGecko."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("coingecko", "market", coin, ttl_seconds=3600)  # 1 hour TTL
    if cached_data:
        logger.info(f"Using cached market data for {coin}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    # If not in cache, fetch from API
    try:
        # First find the coin ID
        coin_id = await _get_coin_id(coin, project_name)
        if not coin_id:
            error_msg = f"Could not find CoinGecko ID for: {coin}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Now get market data for the specific coin
        async with aiohttp.ClientSession() as session:
            market_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
            async with session.get(market_url) as response:
                if response.status != 200:
                    error_msg = f"CoinGecko API error: {response.status}"
                    logger.error(error_msg)
                    return {"error": error_msg}
                
                data = await response.json()
                
                # Extract relevant market data
                result = {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "symbol": data.get("symbol"),
                    "price": data.get("market_data", {}).get("current_price", {}).get("usd"),
                    "market_cap": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                    "market_cap_rank": data.get("market_cap_rank"),
                    "total_volume": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                    "high_24h": data.get("market_data", {}).get("high_24h", {}).get("usd"),
                    "low_24h": data.get("market_data", {}).get("low_24h", {}).get("usd"),
                    "price_change_24h": data.get("market_data", {}).get("price_change_24h"),
                    "price_change_percentage_24h": data.get("market_data", {}).get("price_change_percentage_24h"),
                    "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
                    "total_supply": data.get("market_data", {}).get("total_supply"),
                    "max_supply": data.get("market_data", {}).get("max_supply"),
                }
                
                # Cache the results
                cache_manager.save(result, "coingecko", "market", coin, ttl_seconds=3600)
                logger.info(f"Cached market data for {coin}" + (f" in project {project_name}" if project_name else ""))
                
                return result
    except Exception as e:
        error_msg = f"Error fetching CoinGecko market data: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

async def _get_coin_id(coin: str, project_name: str = None) -> str:
    """Helper to get CoinGecko ID for a coin."""
    try:
        # Initialize cache manager with project-specific directory if provided
        cache_manager = CacheManager(project_name=project_name, logger=logger)
        
        # Try cache first to avoid duplicate API calls
        cached_data = cache_manager.load("coingecko", "id_lookup", coin)
        if cached_data and "id" in cached_data:
            return cached_data["id"]
        
        async with aiohttp.ClientSession() as session:
            # Search for the coin
            search_url = f"https://api.coingecko.com/api/v3/search?query={coin}"
            async with session.get(search_url) as response:
                if response.status != 200:
                    logger.error(f"CoinGecko API error in _get_coin_id: {response.status}")
                    return None
                
                search_data = await response.json()
                
                # Get top result
                coins = search_data.get("coins", [])
                if not coins:
                    logger.warning(f"No coins found for query: {coin}")
                    return None
                
                # Get the best match (usually the one with highest market cap rank)
                best_match = None
                best_rank = float('inf')
                
                for c in coins:
                    # Check if symbol or id matches exactly (case insensitive)
                    if (c.get("symbol", "").lower() == coin.lower() or 
                        c.get("id", "").lower() == coin.lower()):
                        rank = c.get("market_cap_rank", float('inf'))
                        if rank is not None and rank < best_rank:
                            best_match = c
                            best_rank = rank
                
                # If no exact match found, use the top result
                if best_match is None and coins:
                    best_match = coins[0]
                
                if best_match:
                    result = {"id": best_match.get("id")}
                    # Cache the ID mapping
                    cache_manager.save(result, "coingecko", "id_lookup", coin, ttl_seconds=3600)
                    return best_match.get("id")
                
                return None
    except Exception as e:
        logger.error(f"Error in _get_coin_id: {str(e)}")
        return None

@mcp.resource("data://coingecko/history/{coin}/{project_name}")
async def get_coin_history(coin: str, project_name: str = None) -> dict:
    """Get historical price data for a coin from CoinGecko."""
    # Initialize cache manager with project-specific directory if provided
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("coingecko", "history", coin, ttl_seconds=86400)  # 24 hour TTL for historical data
    if cached_data:
        logger.info(f"Using cached history data for {coin}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    try:
        # First find the coin ID
        coin_id = await _get_coin_id(coin, project_name)
        if not coin_id:
            error_msg = f"Could not find CoinGecko ID for: {coin}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Get market chart data (30 days)
        async with aiohttp.ClientSession() as session:
            history_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30&interval=daily"
            async with session.get(history_url) as response:
                if response.status != 200:
                    error_msg = f"CoinGecko API error: {response.status}"
                    logger.error(error_msg)
                    return {"error": error_msg}
                
                data = await response.json()
                
                # Process the data into a more usable format
                prices = data.get("prices", [])
                volumes = data.get("total_volumes", [])
                market_caps = data.get("market_caps", [])
                
                result = {
                    "id": coin_id,
                    "name": coin,
                    "days": 30,
                    "currency": "usd",
                    "price_data": [],
                    "volume_data": [],
                    "market_cap_data": []
                }
                
                # Format price data
                for price_point in prices:
                    if len(price_point) >= 2:
                        timestamp = price_point[0]
                        price = price_point[1]
                        date = time.strftime('%Y-%m-%d', time.localtime(timestamp/1000))
                        result["price_data"].append({
                            "date": date,
                            "price": price
                        })
                
                # Format volume data
                for volume_point in volumes:
                    if len(volume_point) >= 2:
                        timestamp = volume_point[0]
                        volume = volume_point[1]
                        date = time.strftime('%Y-%m-%d', time.localtime(timestamp/1000))
                        result["volume_data"].append({
                            "date": date,
                            "volume": volume
                        })
                
                # Format market cap data
                for mc_point in market_caps:
                    if len(mc_point) >= 2:
                        timestamp = mc_point[0]
                        market_cap = mc_point[1]
                        date = time.strftime('%Y-%m-%d', time.localtime(timestamp/1000))
                        result["market_cap_data"].append({
                            "date": date,
                            "market_cap": market_cap
                        })
                
                # Cache the results
                cache_manager.save(result, "coingecko", "history", coin, ttl_seconds=86400)
                logger.info(f"Cached history data for {coin}" + (f" in project {project_name}" if project_name else ""))
                
                return result
    except Exception as e:
        error_msg = f"Error fetching CoinGecko history data: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

# Remove the server class and use individual tool methods instead

@mcp.tool()
async def get_market_data(coin: str, project_name: str = None) -> Dict[str, Any]:
    """
    Get market data for a cryptocurrency from CoinGecko.
    
    Args:
        coin: Name or symbol of the cryptocurrency
        project_name: Optional project name for project-specific caching
        
    Returns:
        Dictionary containing market data including price, market cap, volume, etc.
    """
    logger.info(f"Getting market data for {coin}" + (f" in project {project_name}" if project_name else ""))
    
    # Call the existing resource function
    return await get_coin_market_data(coin, project_name)

@mcp.tool()
async def search_coins(query: str, project_name: str = None) -> Dict[str, Any]:
    """
    Search for cryptocurrencies by name or symbol.
    
    Args:
        query: Name or symbol to search for
        project_name: Optional project name for project-specific caching
        
    Returns:
        Dictionary with search results
    """
    logger.info(f"Searching coins for {query}" + (f" in project {project_name}" if project_name else ""))
    
    # Initialize project-specific cache manager
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    
    # Check cache first
    cached_data = cache_manager.load("coingecko", "search", query, ttl_seconds=86400)  # 24 hour TTL
    if cached_data:
        logger.info(f"Using cached search data for {query}" + (f" in project {project_name}" if project_name else ""))
        return cached_data
    
    # If not in cache, fetch from API
    try:
        async with aiohttp.ClientSession() as session:
            # Search for the coin
            search_url = f"https://api.coingecko.com/api/v3/search?query={query}"
            async with session.get(search_url) as response:
                if response.status != 200:
                    error_msg = f"CoinGecko API error: {response.status}"
                    logger.error(error_msg)
                    return {"error": error_msg, "results": []}
                
                search_data = await response.json()
                
                # Get coins from search results
                coins = search_data.get("coins", [])
                if not coins:
                    logger.warning(f"No coins found for query: {query}")
                    return {"error": "No coins found", "results": []}
                
                # Format results
                results = []
                for c in coins[:10]:  # Return up to 10 results
                    results.append({
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "symbol": c.get("symbol"),
                        "market_cap_rank": c.get("market_cap_rank")
                    })
                
                response_data = {"results": results, "count": len(results)}
                
                # Cache the results
                cache_manager.save(response_data, "coingecko", "search", query, ttl_seconds=86400)
                logger.info(f"Cached search data for {query}" + (f" in project {project_name}" if project_name else ""))
                
                return response_data
    except Exception as e:
        error_msg = f"Error searching CoinGecko: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "results": []}

@mcp.tool()
async def get_history(coin: str, project_name: str = None) -> Dict[str, Any]:
    """
    Get historical price data for a cryptocurrency from CoinGecko.
    
    Args:
        coin: Name or symbol of the cryptocurrency
        project_name: Optional project name for project-specific caching
        
    Returns:
        Dictionary containing historical price, volume, and market cap data
    """
    logger.info(f"Getting historical data for {coin}" + (f" in project {project_name}" if project_name else ""))
    
    # Call the existing resource function
    return await get_coin_history(coin, project_name)

if __name__ == "__main__":
    mcp.run(transport="stdio")
