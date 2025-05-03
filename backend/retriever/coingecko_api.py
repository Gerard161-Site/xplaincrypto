from typing import Dict, Any, Optional
import requests
import logging
import os
import json
import time
from datetime import datetime
import re
from abc import ABC, abstractmethod
from backend.utils.cache_utils import CacheManager

class DataModule(ABC):
    def __init__(self, project_name: str, logger: logging.Logger = None):
        if not project_name:
            raise ValueError("A valid project_name is required for DataModule initialization")
            
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.coin_id = self.project_name.lower().replace(" ", "-")
        self.token_symbol = self.project_name.upper()
    
    @abstractmethod
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        pass
    
    def _handle_error(self, source: str, error: Exception) -> Dict[str, str]:
        self.logger.error(f"{source} error: {str(error)}")
        return {f"{source.lower()}_error": str(error)}

class CoinGeckoAPI(DataModule):
    """CoinGecko API retriever for cryptocurrency data"""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        # Create a cache manager instance
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Check if CoinGecko API is enabled
        api_enabled = os.getenv("COINGECKO_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"CoinGecko API is disabled by environment settings, returning cache or empty data")
            # Try to use cached data if available, otherwise return empty result
            cached_data = cache_manager.load("coingecko", "data", self.project_name.lower(), ttl_seconds=cache_ttl)
            if cached_data:
                self.logger.info(f"Using cached CoinGecko data for {self.project_name} as API is disabled")
                return cached_data
            return {"coingecko_disabled": "CoinGecko API disabled by configuration"}
        
        # Check cache using CacheManager
        cached_data = cache_manager.load("coingecko", "data", self.project_name.lower(), ttl_seconds=cache_ttl)
        if cached_data and 'current_price' in cached_data and 'market_cap' in cached_data:
            self.logger.info(f"Using cached CoinGecko data for {self.project_name} (price: ${cached_data['current_price']})")
            return cached_data
        
        self.logger.info(f"Gathering fresh CoinGecko data for {self.project_name}")
        
        api_key = os.getenv("COINGECKO_API_KEY", "")
        if not api_key:
            self.logger.warning("CoinGecko API key not found in environment")
        
        try:
            base_url = "https://api.coingecko.com/api/v3"
            search_url = f"{base_url}/search"
            headers = {"x-cg-pro-api-key": api_key} if api_key else {}
            
            search_response = requests.get(search_url, params={"query": self.project_name}, headers=headers, timeout=10)
            if search_response.status_code == 200:
                search_data = search_response.json()
                coins = search_data.get("coins", [])
                
                coin_id = None
                for coin in coins:
                    if coin.get("symbol", "").lower() == self.token_symbol.lower() or \
                       coin.get("name", "").lower() == self.project_name.lower():
                        coin_id = coin.get("id")
                        break
                
                if not coin_id and coins:
                    coin_id = coins[0].get("id")
                    self.logger.warning(f"No exact match for {self.project_name}, using {coins[0].get('name')} ({coin_id})")
                
                if not coin_id:
                    self.logger.error(f"Could not find {self.project_name} in CoinGecko")
                    return {"error": "Coin not found in CoinGecko"}
                
                self.logger.info(f"Found CoinGecko coin ID: {coin_id}")
                
                coin_data_url = f"{base_url}/coins/{coin_id}"
                coin_response = requests.get(coin_data_url, headers=headers, timeout=10)
                
                if coin_response.status_code == 200:
                    result = {}
                    coin_data = coin_response.json()
                    market_data = coin_data.get("market_data", {})
                    
                    result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
                    result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
                    result["total_supply"] = market_data.get("total_supply", 0)
                    result["circulating_supply"] = market_data.get("circulating_supply", 0)
                    result["max_supply"] = market_data.get("max_supply", 0)
                    result["price_change_percentage_24h"] = market_data.get("price_change_percentage_24h", 0)
                    result["volume_24h"] = market_data.get("total_volume", {}).get("usd", 0)
                    
                    try:
                        market_chart_url = f"{base_url}/coins/{coin_id}/market_chart"
                        history_params = {"vs_currency": "usd", "days": "60", "interval": "daily"}
                        chart_response = requests.get(market_chart_url, headers=headers, params=history_params, timeout=10)
                        if chart_response.status_code == 200:
                            chart_data = chart_response.json()
                            if "prices" in chart_data and chart_data["prices"]:
                                result["price_history"] = chart_data["prices"]
                                self.logger.info(f"Retrieved price history with {len(chart_data['prices'])} data points")
                            if "total_volumes" in chart_data and chart_data["total_volumes"]:
                                result["volume_history"] = chart_data["total_volumes"]
                                self.logger.info(f"Retrieved volume history with {len(chart_data['total_volumes'])} data points")
                        else:
                            self.logger.warning(f"Failed to get price history: {chart_response.status_code}")
                    except Exception as e:
                        self.logger.error(f"Error fetching price history: {str(e)}")
                    
                    # Save to cache using CacheManager
                    cache_manager.save(result, "coingecko", "data", self.project_name.lower(), ttl_seconds=cache_ttl)
                    self.logger.info(f"Cached CoinGecko data for {self.project_name}")
                    return result
                else:
                    self.logger.warning(f"CoinGecko API error: Status code {coin_response.status_code}")
                    return {"error": f"API error: {coin_response.status_code}"}
            else:
                self.logger.warning(f"CoinGecko search API error: Status code {search_response.status_code}")
                return {"error": f"Search API error: {search_response.status_code}"}
        except Exception as e:
            self.logger.error(f"Error in CoinGecko module: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def fetch_data(self, coin: str) -> dict:
        """Fetch comprehensive data from CoinGecko for a given coin."""
        self.project_name = coin
        logger = logging.getLogger(__name__)
        self.logger = logger
        
        # Create a cache manager instance
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Check cache first for quick response
        cached_data = cache_manager.load("coingecko", "data", coin.lower(), ttl_seconds=10800)
        if cached_data:
            logger.info(f"Using cached CoinGecko data for {coin} (price: ${cached_data.get('current_price', 'N/A')})")
            return cached_data
        
        # Check if API is enabled
        api_enabled = os.getenv("COINGECKO_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            logger.info(f"CoinGecko API is disabled, returning empty data")
            return {"coingecko_disabled": "CoinGecko API disabled by configuration"}
            
        # Get API key
        api_key = os.getenv("COINGECKO_API_KEY", "")
        if not api_key:
            logger.warning("CoinGecko API key not found in environment")
        
        try:
            import aiohttp
            
            # Use aiohttp for async requests
            async with aiohttp.ClientSession() as session:
                base_url = "https://api.coingecko.com/api/v3"
                search_url = f"{base_url}/search"
                headers = {"x-cg-pro-api-key": api_key} if api_key else {}
                
                async with session.get(search_url, params={"query": coin}, headers=headers, timeout=10) as response:
                    search_data = await response.json()
                    
                    coins = search_data.get("coins", [])
                    
                    coin_id = None
                    for c in coins:
                        if c.get("symbol", "").lower() == coin.lower() or c.get("name", "").lower() == coin.lower():
                            coin_id = c.get("id")
                            break
                    
                    if not coin_id and coins:
                        coin_id = coins[0].get("id")
                        logger.warning(f"No exact match for {coin}, using {coins[0].get('name')} ({coin_id})")
                    
                    if not coin_id:
                        logger.error(f"Could not find {coin} in CoinGecko")
                        return {"error": "Coin not found in CoinGecko"}
                    
                    logger.info(f"Found CoinGecko coin ID: {coin_id}")
                    
                    coin_data_url = f"{base_url}/coins/{coin_id}"
                    async with session.get(coin_data_url, headers=headers, timeout=10) as response:
                        coin_data = await response.json()
                        
                        result = {}
                        market_data = coin_data.get("market_data", {})
                        
                        result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
                        result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
                        result["total_supply"] = market_data.get("total_supply", 0)
                        result["circulating_supply"] = market_data.get("circulating_supply", 0)
                        result["max_supply"] = market_data.get("max_supply", 0)
                        result["price_change_percentage_24h"] = market_data.get("price_change_percentage_24h", 0)
                        result["volume_24h"] = market_data.get("total_volume", {}).get("usd", 0)
                        
                        try:
                            market_chart_url = f"{base_url}/coins/{coin_id}/market_chart"
                            history_params = {"vs_currency": "usd", "days": "60", "interval": "daily"}
                            async with session.get(market_chart_url, headers=headers, params=history_params, timeout=10) as chart_response:
                                chart_data = await chart_response.json()
                                if "prices" in chart_data and chart_data["prices"]:
                                    result["price_history"] = chart_data["prices"]
                                    logger.info(f"Retrieved price history with {len(chart_data['prices'])} data points")
                                if "total_volumes" in chart_data and chart_data["total_volumes"]:
                                    result["volume_history"] = chart_data["total_volumes"]
                                    logger.info(f"Retrieved volume history with {len(chart_data['total_volumes'])} data points")
                        except Exception as e:
                            logger.error(f"Error fetching price history: {str(e)}")
                        
                        # Save to cache using CacheManager
                        cache_manager.save(result, "coingecko", "data", coin.lower(), ttl_seconds=10800)
                        logger.info(f"Cached CoinGecko data for {coin}")
                        return result
                        
        except Exception as e:
            logger.error(f"Error in async CoinGecko fetch: {str(e)}", exc_info=True)
            return {"error": str(e)}
            
    async def fetch_market_data(self, coin: str) -> dict:
        """Fetch market data from CoinGecko for a given coin."""
        data = await self.fetch_data(coin)
        market_data = {
            "market_cap": data.get("market_cap", 0),
            "circulating_supply": data.get("circulating_supply", 0),
            "total_supply": data.get("total_supply", 0),
            "max_supply": data.get("max_supply", 0)
        }
        return market_data
        
    async def fetch_price_data(self, coin: str) -> dict:
        """Fetch price data from CoinGecko for a given coin."""
        data = await self.fetch_data(coin)
        price_data = {
            "current_price": data.get("current_price", 0),
            "price_change_percentage_24h": data.get("price_change_percentage_24h", 0),
            "volume_24h": data.get("volume_24h", 0)
        }
        return price_data
        
    async def search_coins(self, query: str) -> list:
        """Search for coins on CoinGecko by name or symbol."""
        logger = logging.getLogger(__name__)
        api_key = os.getenv("COINGECKO_API_KEY", "")
        
        try:
            import aiohttp
            
            base_url = "https://api.coingecko.com/api/v3"
            search_url = f"{base_url}/search"
            headers = {"x-cg-pro-api-key": api_key} if api_key else {}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params={"query": query}, headers=headers, timeout=10) as response:
                    search_data = await response.json()
                    
                    coins = []
                    for coin in search_data.get("coins", [])[:10]:  # Return top 10 matches
                        coins.append({
                            "id": coin.get("id"),
                            "name": coin.get("name"),
                            "symbol": coin.get("symbol"),
                            "market_cap_rank": coin.get("market_cap_rank")
                        })
                    
                    return coins
        except Exception as e:
            logger.error(f"Error searching coins: {str(e)}")
            return [{"error": str(e)}] 