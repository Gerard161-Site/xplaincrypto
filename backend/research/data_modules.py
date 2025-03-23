from typing import Dict, Any, Optional, List
import requests
import logging
import os
import json
import time
from datetime import datetime
import re
from abc import ABC, abstractmethod

class DataModule(ABC):
    """Base abstract class for data gathering modules."""
    
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        self.coin_id = project_name.lower().replace(" ", "-")
        self.token_symbol = project_name.upper()
    
    @abstractmethod
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        """Execute data gathering from the specific source."""
        pass
    
    def _handle_error(self, source: str, error: Exception) -> Dict[str, str]:
        """Handle errors in a consistent way."""
        self.logger.error(f"{source} error: {str(error)}")
        return {f"{source.lower()}_error": str(error)}

class CoinGeckoModule(DataModule):
    """Gathers data from CoinGecko API."""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_{self.__class__.__name__}.json"
        
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
        elif api_key.startswith("CG-Z"):
            self.logger.warning("CoinGecko API key looks like a placeholder, using free API")
            api_key = ""
        
        base_url = "https://api.coingecko.com/api/v3"
        coin_data_url = f"{base_url}/coins/{self.coin_id}"
        headers = {"x-cg-pro-api-key": api_key} if api_key else {}
        
        result = {}
        try:
            coin_response = requests.get(coin_data_url, headers=headers, timeout=10)
            if coin_response.status_code == 200:
                coin_data = coin_response.json()
                market_data = coin_data.get("market_data", {})
                result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
                result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
                result["total_supply"] = market_data.get("total_supply", 0)
                result["circulating_supply"] = market_data.get("circulating_supply", 0)
                result["max_supply"] = market_data.get("max_supply", 0)
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached CoinGecko data for {self.project_name}")
                return result
            else:
                self.logger.warning(f"CoinGecko API error: Status code {coin_response.status_code}")
                return {"error": f"API error: {coin_response.status_code}"}
        except Exception as e:
            self.logger.error(f"Error in CoinGecko module: {str(e)}", exc_info=True)
            return {"error": str(e)}

class CoinMarketCapModule(DataModule):
    """Gathers data from CoinMarketCap API."""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_{self.__class__.__name__}.json"
        
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        if 'current_price' in data and 'market_cap' in data:
                            self.logger.info(f"Using cached CoinMarketCap data for {self.project_name} (price: ${data['current_price']})")
                            return data
                        else:
                            self.logger.warning(f"Cached CoinMarketCap data for {self.project_name} is incomplete, refreshing")
                except:
                    self.logger.warning(f"Error reading cached CoinMarketCap data for {self.project_name}, refreshing")
        
        self.logger.info(f"Gathering fresh CoinMarketCap data for {self.project_name}")
        
        api_key = os.getenv("COINMARKETCAP_API_KEY", "")
        if not api_key:
            self.logger.warning("CoinMarketCap API key not found in environment")
            return {"error": "API key missing"}
        
        base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"symbol": self.token_symbol}
        
        result = {}
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                quote = data.get("data", {}).get(self.token_symbol, {}).get("quote", {}).get("USD", {})
                result["current_price"] = quote.get("price", 0)
                result["market_cap"] = quote.get("market_cap", 0)
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached CoinMarketCap data for {self.project_name}")
                return result
            else:
                self.logger.warning(f"CoinMarketCap API error: Status code {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            self.logger.error(f"Error in CoinMarketCap module: {str(e)}", exc_info=True)
            return {"error": str(e)}

class DeFiLlamaModule(DataModule):
    """Gathers data from DeFi Llama API."""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_{self.__class__.__name__}.json"
        
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        if 'tvl' in data:
                            self.logger.info(f"Using cached DeFi Llama data for {self.project_name} (TVL: ${data['tvl']})")
                            return data
                        else:
                            self.logger.warning(f"Cached DeFi Llama data for {self.project_name} is incomplete, refreshing")
                except:
                    self.logger.warning(f"Error reading cached DeFi Llama data for {self.project_name}, refreshing")
        
        self.logger.info(f"Gathering fresh DeFi Llama data for {self.project_name}")
        
        base_url = "https://api.llama.fi"
        tvl_url = f"{base_url}/protocol/{self.coin_id}"
        
        result = {}
        try:
            tvl_response = requests.get(tvl_url, timeout=10)
            if tvl_response.status_code == 200:
                tvl_data = tvl_response.json()
                result["tvl"] = tvl_data.get("tvl", 0)
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached DeFi Llama data for {self.project_name}")
                return result
            else:
                self.logger.warning(f"DeFi Llama API error: Status code {tvl_response.status_code}")
                return {"error": f"API error: {tvl_response.status_code}"}
        except Exception as e:
            self.logger.error(f"Error in DeFi Llama module: {str(e)}", exc_info=True)
            return {"error": str(e)}

class DataGatherer:
    """Manages data gathering from various modules."""
    
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        self.modules = [
            CoinGeckoModule(project_name, logger),
            CoinMarketCapModule(project_name, logger),
            DeFiLlamaModule(project_name, logger)
            # Add other modules here if needed
        ]
    
    def gather_all_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        """Gather data from all modules and combine results."""
        all_data = {}
        for module in self.modules:
            try:
                data = module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                all_data.update(data)
            except Exception as e:
                self.logger.error(f"Error gathering data from {module.__class__.__name__}: {str(e)}")
        return all_data