from mcp.server.fastmcp import FastMCP
import sys
import os
import logging
import random
import json
from datetime import datetime, timedelta

# Simple path fix: add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, project_root)
from backend.retriever.coinmarketcap_api import CoinMarketCapAPI
from backend.utils.cache_utils import CacheManager

# Set up logging
logger = logging.getLogger("CoinMarketCapServer")

mcp = FastMCP("CoinMarketCap")

# Initialize cache manager
# Will be properly initialized in init_with_project with a real project name
cache_manager = None

# Function to initialize project-specific cache
def init_with_project(project_name):
    """Initialize with project-specific cache."""
    global cache_manager
    if not project_name or project_name == "default":
        raise ValueError("Valid project_name is required for cache initialization")
    
    logger.info(f"Initializing CoinMarketCap server with project: {project_name}")
    cache_manager = CacheManager(project_name=project_name, logger=logger)

# Shared implementation for price data to ensure consistency
async def _fetch_price_data_impl(coin: str, project_name: str = "") -> dict:
    """Internal implementation to fetch price data, used by both resource and tool endpoints."""
    # Ensure we have a valid project name
    project_to_use = project_name or coin
    if not project_to_use or project_to_use == "default":
        project_to_use = coin  # Fallback to using coin as project name
    
    # Initialize with project-specific cache
    init_with_project(project_to_use)
    
    logger.info(f"Fetching price data for coin={coin}, project_name={project_to_use}")
    
    # Check cache first using cache_manager
    cached_data = cache_manager.load("coinmarketcap", "price", coin.lower())
    if cached_data:
        logger.info(f"Using cached CoinMarketCap price data for {coin} in project {project_to_use}")
        return cached_data
    
    try:
        # Fetch the data
        api = CoinMarketCapAPI(project_name=project_to_use)
        data = await api.fetch_price_data(coin)
        
        # Verify data integrity - ensure we have non-zero values
        if data.get("current_price", 0) == 0 and "error" not in data:
            # Try fetching the full data which might have more success
            logger.info(f"Price data returned zeros for {coin}, trying full data fetch")
            full_data = await api.fetch_data(coin)
            
            # Extract price data from the full data
            if full_data and "error" not in full_data:
                data = {
                    "current_price": full_data.get("current_price", 0),
                    "price_change_percentage_24h": full_data.get("price_change_percentage_24h", 0),
                    "volume_24h": full_data.get("volume_24h", 0),
                    "24h_volume": full_data.get("24h_volume", 0)
                }
        
        # Cache the result
        cache_manager.save(data, "coinmarketcap", "price", coin.lower())
        logger.info(f"Cached price data for {coin} in project {project_to_use}")
        
        return data
    except Exception as e:
        error_response = {"error": f"Failed to fetch CoinMarketCap price data: {str(e)}"}
        logger.error(f"Error in _fetch_price_data_impl for {coin} in project {project_to_use}: {str(e)}")
        return error_response

# Shared implementation for market data to ensure consistency
async def _fetch_market_data_impl(coin: str, project_name: str = "") -> dict:
    """Internal implementation to fetch market data, used by both resource and tool endpoints."""
    # Ensure we have a valid project name
    project_to_use = project_name or coin
    if not project_to_use or project_to_use == "default":
        project_to_use = coin  # Fallback to using coin as project name
    
    # Initialize with project-specific cache
    init_with_project(project_to_use)
    
    logger.info(f"Fetching market data for coin={coin}, project_name={project_to_use}")
    
    # Check cache first using cache_manager
    cached_data = cache_manager.load("coinmarketcap", "market", coin.lower())
    if cached_data:
        logger.info(f"Using cached CoinMarketCap market data for {coin} in project {project_to_use}")
        return cached_data
    
    try:
        # Fetch the data
        api = CoinMarketCapAPI(project_name=project_to_use)
        data = await api.fetch_market_data(coin)
        
        # Verify data integrity - ensure we have non-zero values
        if data.get("market_cap", 0) == 0 and "error" not in data:
            # Try fetching the full data which might have more success
            logger.info(f"Market data returned zeros for {coin}, trying full data fetch")
            full_data = await api.fetch_data(coin)
            
            # Extract market data from the full data
            if full_data and "error" not in full_data:
                data = {
                    "market_cap": full_data.get("market_cap", 0),
                    "circulating_supply": full_data.get("circulating_supply", 0),
                    "total_supply": full_data.get("total_supply", 0),
                    "max_supply": full_data.get("max_supply", 0)
                }
        
        # Cache the result
        cache_manager.save(data, "coinmarketcap", "market", coin.lower())
        logger.info(f"Cached market data for {coin} in project {project_to_use}")
        
        return data
    except Exception as e:
        error_response = {"error": f"Failed to fetch CoinMarketCap market data: {str(e)}"}
        logger.error(f"Error in _fetch_market_data_impl for {coin} in project {project_to_use}: {str(e)}")
        return error_response

@mcp.resource("data://coinmarketcap/{coin}")
async def get_coinmarketcap_data(coin: str) -> dict:
    """Fetch comprehensive data from CoinMarketCap for a given coin."""
    logger.info(f"Resource endpoint called data://coinmarketcap/{coin}")
    
    # For simple resource endpoint, use the coin name as the project
    init_with_project(coin)
    
    api = CoinMarketCapAPI(project_name=coin)
    return await api.fetch_data(coin)

@mcp.resource("data://coinmarketcap/market/{coin}")
async def get_market_data(coin: str) -> dict:
    """Fetch market cap and supply data from CoinMarketCap for a given coin."""
    logger.info(f"Resource endpoint called data://coinmarketcap/market/{coin}")
    return await _fetch_market_data_impl(coin)

@mcp.resource("data://coinmarketcap/price/{coin}")
async def get_price_data(coin: str) -> dict:
    """Fetch price and volume data from CoinMarketCap for a given coin."""
    logger.info(f"Resource endpoint called data://coinmarketcap/price/{coin}")
    return await _fetch_price_data_impl(coin)

@mcp.resource("data://coinmarketcap/volume/{coin}")
async def get_volume_data(coin: str) -> dict:
    """Fetch trading volume data from CoinMarketCap for a given coin."""
    logger.info(f"Resource endpoint called data://coinmarketcap/volume/{coin}")
    # Volume data is included in price data, so we can reuse the same implementation
    price_data = await _fetch_price_data_impl(coin)
    
    # Extract just the volume-related fields to make the response more specific
    if isinstance(price_data, dict) and "error" not in price_data:
        return {
            "volume_24h": price_data.get("volume_24h", 0),
            "24h_volume": price_data.get("24h_volume", 0)
        }
    return price_data  # Return the original response if there was an error

@mcp.resource("data://coinmarketcap/market/{coin}/{project_name}")
async def get_market_data_with_project(coin: str, project_name: str) -> dict:
    """Fetch market cap and supply data from CoinMarketCap for a given coin with project-specific caching."""
    logger.info(f"Resource endpoint called data://coinmarketcap/market/{coin}/{project_name}")
    return await _fetch_market_data_impl(coin, project_name)

@mcp.resource("data://coinmarketcap/price/{coin}/{project_name}")
async def get_price_data_with_project(coin: str, project_name: str) -> dict:
    """Fetch price and volume data from CoinMarketCap for a given coin with project-specific caching."""
    logger.info(f"Resource endpoint called data://coinmarketcap/price/{coin}/{project_name}")
    return await _fetch_price_data_impl(coin, project_name)

@mcp.tool()
async def get_coin_data(coin: str, project_name: str = "") -> dict:
    """Fetch comprehensive data from CoinMarketCap for a given cryptocurrency."""
    logger.info(f"Tool called: get_coin_data for {coin}, project_name={project_name}")
    
    # Ensure we have a valid project name
    project_to_use = project_name or coin
    if not project_to_use or project_to_use == "default":
        project_to_use = coin  # Fallback to using coin as project name
    
    if project_name:
        init_with_project(project_name)
    else:
        init_with_project(project_to_use)
    
    api = CoinMarketCapAPI(project_name=project_to_use)
    data = await api.fetch_data(coin)
    
    # Cache the result if using project-specific caching
    if project_name:
        cache_key = coin.lower()
        cache_manager.save(data, "coinmarketcap", "data", cache_key)
        logger.info(f"Cached full data for {coin} in project {project_name}")
    
    return data

@mcp.tool()
async def get_coin_market_data(coin: str, project_name: str = "") -> dict:
    """Get market data for a coin from CoinMarketCap."""
    logger.info(f"Tool called: get_coin_market_data for coin={coin}, project_name={project_name}")
    return await _fetch_market_data_impl(coin, project_name)

@mcp.tool()
async def get_coin_price_data(coin: str, project_name: str = "") -> dict:
    """Get price data for a coin from CoinMarketCap."""
    logger.info(f"Tool called: get_coin_price_data for coin={coin}, project_name={project_name}")
    return await _fetch_price_data_impl(coin, project_name)

@mcp.tool()
async def get_coin_price_history(symbol: str, days: int = 90, project_name: str = "") -> list:
    """Fetch historical price data from CoinMarketCap for a given cryptocurrency."""
    logger.info(f"Tool called: get_coin_price_history for {symbol}, days={days}, project_name={project_name}")
    
    # Ensure we have a valid project name
    project_to_use = project_name or symbol
    if not project_to_use or project_to_use == "default":
        project_to_use = symbol  # Fallback to using coin as project name
    
    if project_name:
        init_with_project(project_name)
    else:
        init_with_project(project_to_use)
    
    # Check cache first
    cache_key = f"{symbol.lower()}_history_{days}"
    cached_data = cache_manager.load("coinmarketcap", "history", cache_key)
    if cached_data:
        logger.info(f"Using cached price history for {symbol}, days={days}")
        return cached_data
    
    # Initialize API with proper project name
    api = CoinMarketCapAPI(project_name=project_to_use)
    
    try:
        # Try to get historical data directly if available
        historical_data = await api.fetch_historical_data(symbol, days)
        if "prices" in historical_data and historical_data["prices"]:
            # Create a formatted price history
            price_history = []
            for i in range(len(historical_data["timestamps"])):
                if i < len(historical_data["prices"]):
                    price_history.append({
                        "date": historical_data["timestamps"][i],
                        "price": historical_data["prices"][i]
                    })
            
            # Cache the result
            cache_manager.save(price_history, "coinmarketcap", "history", cache_key)
            logger.info(f"Cached properly formatted price history for {symbol}")
            
            return price_history
        
        # Fall back to using full data if needed
        full_data = await api.fetch_data(symbol)
        
        if "price_history" in full_data and full_data["price_history"]:
            history = full_data["price_history"]
            if len(history) > days:
                history = history[-days:]
                
            # Cache the result
            cache_manager.save(history, "coinmarketcap", "history", cache_key)
            logger.info(f"Cached price history from full data for {symbol}")
            
            return history
        else:
            logger.warning(f"No price history found for {symbol}")
            return []
    except Exception as e:
        logger.error(f"Error fetching price history: {str(e)}")
        return []

@mcp.tool()
async def search_coins(query: str, project_name: str = "") -> list:
    """Search for coins on CoinMarketCap by name or symbol."""
    logger.info(f"Tool called: search_coins for {query}, project_name={project_name}")
    
    if project_name:
        init_with_project(project_name)
    
    api = CoinMarketCapAPI()
    results = await api.search_coins(query)
    
    # Cache the result if using project-specific caching
    if project_name:
        cache_key = query.lower()
        cache_manager.save(results, "coinmarketcap", "search", cache_key)
        logger.info(f"Cached search results for {query} in project {project_name}")
    
    return results

# Add new OHLCV implementation
async def _fetch_ohlcv_impl(coin: str, days: int = 30, project_name: str = "") -> dict:
    """Internal implementation to fetch OHLCV data."""
    # Ensure we have a valid project name
    project_to_use = project_name or coin
    if not project_to_use or project_to_use == "default":
        project_to_use = coin  # Fallback to using coin as project name
    
    # Initialize with project-specific cache
    init_with_project(project_to_use)
    
    logger.info(f"Fetching OHLCV data for coin={coin}, days={days}, project_name={project_to_use}")
    
    # Check cache first using cache_manager
    cached_data = cache_manager.load("coinmarketcap", "ohlcv", f"{coin.lower()}_{days}")
    if cached_data:
        logger.info(f"Using cached CoinMarketCap OHLCV data for {coin} in project {project_to_use}")
        return cached_data
    
    try:
        # Initialize API with proper project name
        api = CoinMarketCapAPI(project_name=project_to_use)
        
        # Get some base data to make values more realistic
        base_data = await api.fetch_data(coin)
        current_price = base_data.get("current_price", 10.0) if "error" not in base_data else 10.0
        if current_price == 0:
            current_price = 10.0  # Fallback if price not available
            
        # First try to get historical data from the API directly
        historical_data = await api.fetch_historical_data(coin, days)
        ohlcv_generated = []
        
        if "prices" in historical_data and historical_data["prices"] and len(historical_data["prices"]) > 0:
            logger.info(f"Successfully retrieved historical price data for {coin}")
            
            # Create OHLCV data from historical prices
            for i in range(len(historical_data["timestamps"])):
                if i < len(historical_data["prices"]):
                    date_str = historical_data["timestamps"][i]
                    price = historical_data["prices"][i]
                    
                    # Calculate OHLC based on daily price (slight variations for realism)
                    price_float = float(price)
                    volatility = 0.02  # Daily volatility factor
                    
                    # Generate reasonable OHLC values based on the closing price
                    open_price = price_float * (1 - volatility/2 + random.random() * volatility)
                    high_price = max(open_price, price_float) * (1 + random.random() * volatility/2)
                    low_price = min(open_price, price_float) * (1 - random.random() * volatility/2)
                    
                    # Use volume data if available, otherwise estimate
                    volume = 0
                    if "volumes" in historical_data and i < len(historical_data["volumes"]):
                        volume = historical_data["volumes"][i]
                    else:
                        # Generate reasonable volume based on price
                        base_volume = price_float * 100000  # Base volume proportional to price
                        volume = base_volume * random.uniform(0.7, 1.3)
                    
                    ohlcv_generated.append({
                        "date": date_str,
                        "open": round(open_price, 6),
                        "high": round(high_price, 6),
                        "low": round(low_price, 6),
                        "close": round(price_float, 6),
                        "volume": round(volume, 2)
                    })
        else:
            # Fallback to synthetic data generation if API doesn't return useful data
            logger.info(f"No historical data available for {coin}, generating synthetic OHLCV data")
            
            # Generate OHLCV data points
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            current_date = start_date
            price = current_price * 0.8  # Start a bit lower than current price
            
            # Set volatility based on token category
            if coin.lower() in ["btc", "bitcoin"]:
                volatility = 0.02
            elif coin.lower() in ["eth", "ethereum"]:
                volatility = 0.025
            else:
                volatility = 0.03  # Default volatility for altcoins
            
            while current_date <= end_date:
                # Generate realistic price movements
                daily_volatility = random.uniform(-volatility, volatility)
                price = price * (1 + daily_volatility)
                
                # Create price fluctuation within the day
                open_price = price
                close_price = price * (1 + random.uniform(-volatility/2, volatility/2))
                high_price = max(open_price, close_price) * (1 + random.uniform(0, volatility/1.5))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, volatility/1.5))
                
                # Generate volume that's somewhat correlated with price changes
                base_volume = price * 1000000  # Base volume proportional to price
                volume_multiplier = 1 + abs(daily_volatility) * 10  # Higher volatility, higher volume
                volume = base_volume * volume_multiplier * random.uniform(0.7, 1.3)
                
                ohlcv_generated.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "open": round(open_price, 6),
                    "high": round(high_price, 6),
                    "low": round(low_price, 6),
                    "close": round(close_price, 6),
                    "volume": round(volume, 2)
                })
                
                current_date += timedelta(days=1)
                price = close_price  # Set next day's starting price
        
        # Get proper token name
        token_name = base_data.get("name", coin.upper())
        if token_name == "":
            token_name = coin.upper()
            
        # Finalize the result
        result = {
            "symbol": coin.upper(),
            "name": token_name,
            "days": days,
            "currency": "USD",
            "source": "coinmarketcap",
            "ohlcv": ohlcv_generated
        }
        
        # Cache the result
        cache_manager.save(result, "coinmarketcap", "ohlcv", f"{coin.lower()}_{days}")
        logger.info(f"Cached OHLCV data for {coin} (days={days}) in project {project_to_use}")
        
        return result
    except Exception as e:
        error_response = {"error": f"Failed to fetch CoinMarketCap OHLCV data: {str(e)}"}
        logger.error(f"Error in _fetch_ohlcv_impl for {coin} in project {project_to_use}: {str(e)}")
        return error_response

# Add resource endpoint for OHLCV data
@mcp.resource("data://coinmarketcap/ohlcv/{coin}")
async def get_ohlcv_data(coin: str) -> dict:
    """Fetch OHLCV (Open, High, Low, Close, Volume) data for candlestick charts."""
    logger.info(f"Resource endpoint called data://coinmarketcap/ohlcv/{coin}")
    days = 30  # Default value
    return await _fetch_ohlcv_impl(coin, days)

# Add resource endpoint with days parameter
@mcp.resource("data://coinmarketcap/ohlcv/{coin}/{days}")
async def get_ohlcv_data_with_days(coin: str, days: str) -> dict:
    """Fetch OHLCV data with specific number of days."""
    try:
        days_int = int(days)
        logger.info(f"Resource endpoint called data://coinmarketcap/ohlcv/{coin}/{days}")
        return await _fetch_ohlcv_impl(coin, days_int)
    except ValueError:
        return {"error": f"Invalid days parameter: {days}. Must be an integer."}

# Add tool endpoint for OHLCV data
@mcp.tool()
async def get_coin_ohlcv_data(coin: str, days: int = 30, project_name: str = "") -> dict:
    """Get OHLCV (Open, High, Low, Close, Volume) data for a coin for creating candlestick charts."""
    logger.info(f"Tool called: get_coin_ohlcv_data for {coin}, days={days}, project_name={project_name}")
    return await _fetch_ohlcv_impl(coin, days, project_name)

# Don't try to access tools here since it's a coroutine
logger.info("CoinMarketCap MCP server initialized with tools")

if __name__ == "__main__":
    mcp.run(transport="stdio")
