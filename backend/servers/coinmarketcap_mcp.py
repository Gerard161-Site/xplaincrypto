# backend/servers/coinmarketcap_mcp.py
import logging
import os
import sys
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Optional, List
import aiohttp
import json
import time
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
import asyncio
import selectors

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
print("Starting coinmarketcap_mcp.py", flush=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("CoinMarketCapMCP")
logging.getLogger("mcp").setLevel(logging.DEBUG)
logger.info("Logging configured")

# Load .env file
load_dotenv()
print("Loaded .env file", flush=True)
logger.info("Loaded .env file")

print("Importing dependencies", flush=True)
logger.info("Imported dependencies")
print("Imported dependencies", flush=True)

mcp = FastMCP("CoinMarketCap")
logger.info("Initialized FastMCP")
print("Initialized FastMCP", flush=True)

class CoinMarketCapMCP:
    def __init__(self, project_name: str = "default"):
        logger.info("Entering CoinMarketCapMCP.__init__")
        print("Entering CoinMarketCapMCP.__init__", flush=True)
        self.api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not self.api_key:
            logger.error("COINMARKETCAP_API_KEY not set")
            raise ValueError("API key missing")
        logger.info("COINMARKETCAP_API_KEY: set")
        print("COINMARKETCAP_API_KEY: set", flush=True)
        self.project_name = project_name
        self.cache_dir = Path("cache") / project_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://pro-api.coinmarketcap.com"
        logger.info("CoinMarketCapMCP initialized")
        print("CoinMarketCapMCP initialized", flush=True)

    def _load_cache(self, category: str, key: str, ttl: int = 3600) -> Optional[Dict[str, Any]]:
        cache_file = self.cache_dir / f"{category}_{key}.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                data = json.load(f)
            if time.time() - data["timestamp"] < ttl:
                logger.info(f"Using cached {category} data for {key}")
                return data["response"]
        return None

    def _save_cache(self, category: str, key: str, response: Dict[str, Any]):
        cache_file = self.cache_dir / f"{category}_{key}.json"
        with open(cache_file, "w") as f:
            json.dump({"response": response, "timestamp": time.time()}, f, indent=2)

    async def _find_cmc_id(self, symbol: str) -> Optional[int]:
        async with aiohttp.ClientSession() as session:
            headers = {"X-CMC_PRO_API_KEY": self.api_key}
            url = f"{self.base_url}/v1/cryptocurrency/map"
            params = {"symbol": symbol.upper()}
            async with session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"Symbol search HTTP error: {response.status}")
                    return None
                data = await response.json()
                results = data.get("data", [])
                if not results:
                    logger.error(f"No results for symbol {symbol}")
                    return None
                active_results = [r for r in results if r.get("is_active", 0) == 1]
                if not active_results:
                    logger.error(f"No active coins for {symbol}")
                    return None
                best_result = min(active_results, key=lambda r: r.get("rank", 9999))
                return best_result["id"]

    async def fetch_price_data(self, coin: str) -> Dict[str, Any]:
        cache_key = coin.lower()
        cached = self._load_cache("price", cache_key)
        if cached:
            return cached
        cmc_id = await self._find_cmc_id(coin)
        if not cmc_id:
            return {"error": f"No valid coin found for {coin}"}
        async with aiohttp.ClientSession() as session:
            headers = {"X-CMC_PRO_API_KEY": self.api_key}
            url = f"{self.base_url}/v1/cryptocurrency/quotes/latest"
            params = {"id": cmc_id, "convert": "USD"}
            async with session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status != 200:
                    return {"error": f"API error: {response.status}"}
                data = await response.json()
                coin_data = data.get("data", {}).get(str(cmc_id), {})
                quote = coin_data.get("quote", {}).get("USD", {})
                result = {
                    "current_price": quote.get("price", 0),
                    "price_change_percentage_24h": quote.get("percent_change_24h", 0),
                    "volume_24h": quote.get("volume_24h", 0)
                }
                self._save_cache("price", cache_key, result)
                return result

    async def fetch_market_data(self, coin: str) -> Dict[str, Any]:
        cache_key = coin.lower()
        cached = self._load_cache("market", cache_key)
        if cached:
            return cached
        cmc_id = await self._find_cmc_id(coin)
        if not cmc_id:
            return {"error": f"No valid coin found for {coin}"}
        async with aiohttp.ClientSession() as session:
            headers = {"X-CMC_PRO_API_KEY": self.api_key}
            url = f"{self.base_url}/v1/cryptocurrency/quotes/latest"
            params = {"id": cmc_id, "convert": "USD"}
            async with session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status != 200:
                    return {"error": f"API error: {response.status}"}
                data = await response.json()
                coin_data = data.get("data", {}).get(str(cmc_id), {})
                result = {
                    "market_cap": coin_data.get("quote", {}).get("USD", {}).get("market_cap", 0),
                    "circulating_supply": coin_data.get("circulating_supply", 0),
                    "total_supply": coin_data.get("total_supply", 0),
                    "max_supply": coin_data.get("max_supply", 0)
                }
                self._save_cache("market", cache_key, result)
                return result

    async def fetch_ohlcv_data(self, coin: str, days: int = 30) -> Dict[str, Any]:
        cache_key = f"{coin.lower()}_{days}"
        cached = self._load_cache("ohlcv", cache_key)
        if cached:
            return cached
        cmc_id = await self._find_cmc_id(coin)
        if not cmc_id:
            return {"error": f"No valid coin found for {coin}"}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_str = end_date.strftime("%Y-%m-%dT23:59:59.000Z")
        async with aiohttp.ClientSession() as session:
            headers = {"X-CMC_PRO_API_KEY": self.api_key}
            url = f"{self.base_url}/v1/cryptocurrency/quotes/historical"
            params = {"id": cmc_id, "time_start": start_str, "time_end": end_str, "interval": "daily", "convert": "USD"}
            async with session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status != 200:
                    return {"error": f"API error: {response.status}"}
                data = await response.json()
                quotes = data.get("data", {}).get("quotes", [])
                ohlcv = [
                    {
                        "date": q["timestamp"],
                        "open": q["quote"]["USD"]["open"],
                        "high": q["quote"]["USD"]["high"],
                        "low": q["quote"]["USD"]["low"],
                        "close": q["quote"]["USD"]["close"],
                        "volume": q["quote"]["USD"]["volume_24h"]
                    } for q in quotes
                ]
                result = {"symbol": coin.upper(), "ohlcv": ohlcv}
                self._save_cache("ohlcv", cache_key, result)
                return result

@mcp.resource("data://coinmarketcap/price/{coin}")
async def get_price_data(coin: str):
    return await CoinMarketCapMCP(coin).fetch_price_data(coin)

@mcp.resource("data://coinmarketcap/market/{coin}")
async def get_market_data(coin: str):
    return await CoinMarketCapMCP(coin).fetch_market_data(coin)

@mcp.resource("data://coinmarketcap/ohlcv/{coin}/{days}")
async def get_ohlcv_data(coin: str, days: str):
    try:
        days_int = int(days)
        return await CoinMarketCapMCP(coin).fetch_ohlcv_data(coin, days_int)
    except ValueError:
        return {"error": f"Invalid days parameter: {days}"}

@mcp.tool(name="get_coin_price_data")
async def get_coin_price_data(coin: str):
    return await CoinMarketCapMCP(coin).fetch_price_data(coin)

@mcp.tool(name="get_coin_market_data")
async def get_coin_market_data(coin: str):
    return await CoinMarketCapMCP(coin).fetch_market_data(coin)

@mcp.tool(name="get_coin_ohlcv_data")
async def get_coin_ohlcv_data(coin: str, days: int = 30):
    return await CoinMarketCapMCP(coin).fetch_ohlcv_data(coin, days)

if __name__ == "__main__":
    # Set PollSelector to avoid KqueueSelector hang (CPython #95600)
    selectors.DefaultSelector = selectors.PollSelector
    print("Entered main block", flush=True)
    logger.info("Entered main block")
    try:
        logger.info("Creating CoinMarketCapMCP instance")
        print("Creating CoinMarketCapMCP instance", flush=True)
        cmc = CoinMarketCapMCP(project_name="test")
        logger.info("CoinMarketCapMCP instance created")
        print("CoinMarketCapMCP instance created", flush=True)
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        print(f"Error during initialization: {str(e)}", flush=True)
        raise
    logger.info("Starting MCP server with stdio transport")
    print("Starting MCP server with stdio transport", flush=True)
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