from typing import Dict, Any, Optional
import requests
import logging
import os
import json
import time
from datetime import datetime
import re
from abc import ABC, abstractmethod

class DataModule(ABC):
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        self.coin_id = project_name.lower().replace(" ", "-")
        self.token_symbol = project_name.upper()
    
    @abstractmethod
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        pass
    
    def _handle_error(self, source: str, error: Exception) -> Dict[str, str]:
        self.logger.error(f"{source} error: {str(error)}")
        return {f"{source.lower()}_error": str(error)}

class CoinGeckoAPI(DataModule):
    """CoinGecko API retriever for cryptocurrency data"""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_CoinGeckoAPI.json"
        
        # Check if CoinGecko API is enabled
        api_enabled = os.getenv("COINGECKO_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"CoinGecko API is disabled by environment settings, returning cache or empty data")
            # Try to use cached data if available, otherwise return empty result
            if use_cache and os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        self.logger.info(f"Using cached CoinGecko data for {self.project_name} as API is disabled")
                        return data
                except Exception as e:
                    self.logger.warning(f"Error reading cached CoinGecko data: {str(e)}")
            return {"coingecko_disabled": "CoinGecko API disabled by configuration"}
        
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        if 'current_price' in data and 'market_cap' in data:
                            self.logger.info(f"Using cached CoinGecko data for {self.project_name} (price: ${data['current_price']})")
                            return data
                        else:
                            self.logger.warning(f"Cached CoinGecko data for {self.project_name} is incomplete, refreshing")
                except:
                    self.logger.warning(f"Error reading cached CoinGecko data for {self.project_name}, refreshing")
        
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
                    
                    os.makedirs("cache", exist_ok=True)
                    with open(cache_path, 'w') as f:
                        json.dump(result, f)
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