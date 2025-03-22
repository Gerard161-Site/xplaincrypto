from typing import Dict, Any, Optional, List
import requests
import logging
import os
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
import json
import time
import re
from datetime import datetime

class DataModule(ABC):
    """Base abstract class for data gathering modules."""
    
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        # Normalize project name for API calls
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
        
        # Check cache first if enabled
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
        
        # Only proceed with API call if cache missed
        self.logger.info(f"Gathering fresh CoinGecko data for {self.project_name}")
        
        # Get API key from environment
        api_key = os.getenv("COINGECKO_API_KEY", "")
        if not api_key:
            self.logger.warning("CoinGecko API key not found in environment")
        elif api_key.startswith("CG-Z"):
            self.logger.warning("CoinGecko API key looks like a placeholder, using free API")
            api_key = ""
        
        # Base URLs for CoinGecko API
        base_url = "https://api.coingecko.com/api/v3"
        coin_data_url = f"{base_url}/coins/{self.coin_id}"
        price_history_url = f"{base_url}/coins/{self.coin_id}/market_chart?vs_currency=usd&days=60"
        
        # Set up headers if API key is available
        headers = {}
        if api_key:
            headers["x-cg-pro-api-key"] = api_key
            self.logger.info("Using authenticated CoinGecko API")
        
        result = {}
        coin_found = False
        
        try:
            # Get coin data
            self.logger.debug(f"Fetching CoinGecko data from: {coin_data_url}")
            self.logger.info(f"Coin ID: {self.coin_id}")
            
            # Try with a fallback coin ID if needed (lowercase)
            try_coin_ids = [self.coin_id]
            if self.coin_id != self.coin_id.lower():
                try_coin_ids.append(self.coin_id.lower())
            
            # Also try with token symbol as a fallback
            if self.token_symbol.lower() != self.coin_id.lower():
                try_coin_ids.append(self.token_symbol.lower())
            
            coin_response = None
            coin_data = None
            
            for coin_id in try_coin_ids:
                try:
                    current_url = f"{base_url}/coins/{coin_id}"
                    self.logger.info(f"Trying CoinGecko with coin ID: {coin_id}")
                    coin_response = requests.get(current_url, headers=headers, timeout=10)
                    
                    # Check if we got a successful response
                    if coin_response.status_code == 200:
                        coin_data = coin_response.json()
                        if "market_data" in coin_data:
                            self.logger.info(f"Successfully found {coin_id} on CoinGecko")
                            self.coin_id = coin_id  # Update the coin ID to the one that worked
                            break
                except Exception as e:
                    self.logger.warning(f"Error fetching CoinGecko data for {coin_id}: {e}")
            
            if not coin_response or coin_response.status_code != 200:
                status_code = coin_response.status_code if coin_response else "No response"
                self.logger.warning(f"CoinGecko API error: Status code {status_code}")
                if coin_response and coin_response.status_code == 429:
                    self.logger.warning("CoinGecko API rate limit reached, using fallback data")
                return {"error": f"CoinGecko API error: {status_code}"}
            
            if not coin_data or "market_data" not in coin_data:
                self.logger.warning("No market data found in CoinGecko response")
                return {"error": "No market data found"}
            
            coin_found = True
            
            # Extract market data
            market_data = coin_data["market_data"]
            result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
            result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
            result["total_supply"] = market_data.get("total_supply", 0)
            result["circulating_supply"] = market_data.get("circulating_supply", 0)
            result["max_supply"] = market_data.get("max_supply", 0)
            
            # Extract price history (update URL with the coin ID that worked)
            current_price_history_url = f"{base_url}/coins/{self.coin_id}/market_chart?vs_currency=usd&days=60"
            self.logger.debug(f"Fetching CoinGecko price history from: {current_price_history_url}")
            price_response = requests.get(current_price_history_url, headers=headers, timeout=10)
            
            # Check for rate limiting
            if price_response.status_code == 429:
                self.logger.warning("CoinGecko price history API rate limit reached")
                # Still continue with the coin data we have
            elif price_response.status_code == 200:
                price_data = price_response.json()
                
                # Process price history
                if "prices" in price_data:
                    result["price_history"] = price_data["prices"]
                    # Calculate price change over period
                    if len(price_data["prices"]) >= 2:
                        start_price = price_data["prices"][0][1]
                        end_price = price_data["prices"][-1][1]
                        price_change = ((end_price - start_price) / start_price) * 100
                        result["price_change_60d"] = price_change
                
                # Process volume history
                if "total_volumes" in price_data:
                    result["volume_history"] = price_data["total_volumes"]
            else:
                self.logger.warning(f"Error getting price history: {price_response.status_code}")
                    
            # Only cache if we got actual coin data
            if coin_found and result:
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached CoinGecko data for {self.project_name}")
                
                # Log key data points found
                self.logger.info(f"Retrieved data: price=${result.get('current_price', 'N/A')}, " 
                               f"market cap=${result.get('market_cap', 'N/A')}")
                if 'price_history' in result:
                    self.logger.info(f"Retrieved {len(result['price_history'])} price history data points")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in CoinGecko module: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def get_enhanced_market_data(self, use_cache=True, cache_ttl=3600) -> Dict[str, Any]:
        """
        Get enhanced market data including specific data points
        like current price, market cap, and percentage changes.
        
        Uses a shorter cache TTL (1 hour) to ensure data is relatively fresh.
        """
        cache_path = f"cache/{self.project_name}_enhanced_market_data.json"
        
        # Check cache first (with shorter TTL for market data)
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        self.logger.info(f"Using cached enhanced market data for {self.project_name}")
                        return data
                except Exception as e:
                    self.logger.warning(f"Error reading cached enhanced market data: {str(e)}")
        
        # Get API key (optional)
        api_key = os.getenv("COINGECKO_API_KEY", "")
        headers = {}
        if api_key and not api_key.startswith("CG-Z"):
            headers["x-cg-pro-api-key"] = api_key
        
        # API URLs
        base_url = "https://api.coingecko.com/api/v3"
        coin_url = f"{base_url}/coins/{self.coin_id}"
        market_chart_url = f"{base_url}/coins/{self.coin_id}/market_chart?vs_currency=usd&days=60"
        
        try:
            # Get basic data
            self.logger.info(f"Fetching enhanced market data for {self.project_name} (ID: {self.coin_id})")
            coin_response = requests.get(coin_url, headers=headers, timeout=10)
            if coin_response.status_code != 200:
                self.logger.warning(f"CoinGecko API error: {coin_response.status_code}")
                return {"error": f"API error: {coin_response.status_code}"}
            
            coin_data = coin_response.json()
            
            # Get market chart data
            chart_response = requests.get(market_chart_url, headers=headers, timeout=10)
            chart_data = {}
            if chart_response.status_code == 200:
                chart_data = chart_response.json()
            
            # Extract specific data points
            market_data = coin_data.get("market_data", {})
            
            enhanced_data = {
                "name": coin_data.get("name", self.project_name),
                "symbol": coin_data.get("symbol", "").upper(),
                "current_price": market_data.get("current_price", {}).get("usd", 0),
                "market_cap": market_data.get("market_cap", {}).get("usd", 0),
                "total_volume": market_data.get("total_volume", {}).get("usd", 0),
                "circulating_supply": market_data.get("circulating_supply", 0),
                "total_supply": market_data.get("total_supply", 0),
                "max_supply": market_data.get("max_supply", 0),
                "ath": market_data.get("ath", {}).get("usd", 0),
                "ath_change_percentage": market_data.get("ath_change_percentage", {}).get("usd", 0),
                "price_change_24h": market_data.get("price_change_percentage_24h", 0),
                "price_change_7d": market_data.get("price_change_percentage_7d", 0),
                "price_change_30d": market_data.get("price_change_percentage_30d", 0),
                "price_change_60d": 0,  # Calculate from chart data
                "price_change_200d": market_data.get("price_change_percentage_200d", 0),
                "price_change_1y": market_data.get("price_change_percentage_1y", 0),
                "price_history": chart_data.get("prices", []),
                "volume_history": chart_data.get("total_volumes", []),
                "market_cap_history": chart_data.get("market_caps", []),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Calculate 60-day price change if we have chart data
            if "prices" in chart_data and len(chart_data["prices"]) >= 2:
                start_price = chart_data["prices"][0][1]
                end_price = chart_data["prices"][-1][1]
                if start_price > 0:
                    price_change_60d = ((end_price - start_price) / start_price) * 100
                    enhanced_data["price_change_60d"] = price_change_60d
            
            # Format some values for readability
            enhanced_data["formatted"] = {
                "current_price": f"${enhanced_data['current_price']:.4f}",
                "market_cap": f"${enhanced_data['market_cap']:,}",
                "total_volume": f"${enhanced_data['total_volume']:,}",
                "price_change_24h": f"{enhanced_data['price_change_24h']:.2f}%",
                "price_change_7d": f"{enhanced_data['price_change_7d']:.2f}%",
                "price_change_30d": f"{enhanced_data['price_change_30d']:.2f}%",
                "price_change_60d": f"{enhanced_data['price_change_60d']:.2f}%",
            }
            
            # Cache the enhanced data
            os.makedirs("cache", exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump(enhanced_data, f)
            
            self.logger.info(f"Retrieved and cached enhanced market data for {self.project_name}")
            return enhanced_data
            
        except Exception as e:
            self.logger.error(f"Error getting enhanced market data: {str(e)}")
            return {"error": str(e)}


class CoinMarketCapModule(DataModule):
    """Gathers data from CoinMarketCap API."""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_{self.__class__.__name__}.json"
        
        # Check cache first if enabled
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        if 'cmc_price' in data and 'cmc_market_cap' in data:
                            self.logger.info(f"Using cached CoinMarketCap data for {self.project_name} (price: ${data['cmc_price']})")
                            return data
                        else:
                            self.logger.warning(f"Cached CoinMarketCap data for {self.project_name} is incomplete, refreshing")
                except:
                    self.logger.warning(f"Error reading cached CoinMarketCap data for {self.project_name}, refreshing")
                
        # Only proceed with API call if cache missed
        self.logger.info(f"Gathering fresh CoinMarketCap data for {self.project_name}")
        
        # Get API key
        api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not api_key:
            self.logger.warning("CoinMarketCap API key not found in environment")
            return {"error": "API key not found"}
        
        self.logger.info(f"Using CoinMarketCap API key: {api_key[:4]}...{api_key[-4:]}")
        
        result = {}
        
        # Try both symbol and slug-based lookup
        try:
            # First try with symbol
            symbol_data = self._get_token_data_by_symbol(api_key)
            if symbol_data and "error" not in symbol_data:
                result = symbol_data
                self.logger.info(f"Successfully retrieved CMC data by symbol: {self.token_symbol}")
            else:
                # If symbol lookup fails, try by slug (project name)
                slug = self.project_name.lower().replace(" ", "-")
                slug_data = self._get_token_data_by_slug(api_key, slug)
                if slug_data and "error" not in slug_data:
                    result = slug_data
                    self.logger.info(f"Successfully retrieved CMC data by slug: {slug}")
                else:
                    # Final attempt: Try with token_symbol as a slug
                    token_slug = self.token_symbol.lower()
                    token_data = self._get_token_data_by_slug(api_key, token_slug)
                    if token_data and "error" not in token_data:
                        result = token_data
                        self.logger.info(f"Successfully retrieved CMC data by token slug: {token_slug}")
                    else:
                        self.logger.warning(f"Failed to find {self.project_name} on CoinMarketCap")
                        return {"error": "Token not found on CoinMarketCap"}
            
            # Cache the result if we have data
            if result and "cmc_price" in result:
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached CoinMarketCap data for {self.project_name}")
                
                # Log successful data retrieval
                self.logger.info(f"Retrieved CMC data: price=${result.get('cmc_price', 'N/A')}, " 
                               f"market cap=${result.get('cmc_market_cap', 'N/A')}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in CoinMarketCap module: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _get_token_data_by_symbol(self, api_key):
        """Get token data using the symbol endpoint"""
        result = {}
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"symbol": self.token_symbol}
        
        try:
            self.logger.debug(f"Fetching CoinMarketCap data with symbol: {self.token_symbol}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # Check for rate limiting or errors
            if response.status_code != 200:
                self.logger.warning(f"CoinMarketCap API error: Status code {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
                
            data = response.json()
            
            # Check for errors
            if data.get("status", {}).get("error_code") != 0:
                error_message = data.get("status", {}).get("error_message", "Unknown error")
                self.logger.warning(f"CoinMarketCap API error: {error_message}")
                return {"error": f"API Error: {error_message}"}
            
            # Extract token data
            if self.token_symbol in data.get("data", {}):
                token_data = data["data"][self.token_symbol]
                
                if "quote" in token_data and "USD" in token_data["quote"]:
                    usd_data = token_data["quote"]["USD"]
                    result["cmc_price"] = usd_data.get("price", 0)
                    result["cmc_market_cap"] = usd_data.get("market_cap", 0)
                    result["cmc_volume_24h"] = usd_data.get("volume_24h", 0)
                    result["cmc_percent_change_24h"] = usd_data.get("percent_change_24h", 0)
                    result["cmc_percent_change_7d"] = usd_data.get("percent_change_7d", 0)
                    result["cmc_percent_change_30d"] = usd_data.get("percent_change_30d", 0)
                
                result["cmc_circulating_supply"] = token_data.get("circulating_supply", 0)
                result["cmc_total_supply"] = token_data.get("total_supply", 0)
                result["cmc_max_supply"] = token_data.get("max_supply", 0)
                result["name"] = token_data.get("name", self.project_name)
                result["slug"] = token_data.get("slug", "")
                
                # Add competitor data for comparison
                result["competitors"] = []
                
                return result
            else:
                self.logger.warning(f"Symbol {self.token_symbol} not found in CMC response")
                return {"error": "Symbol not found"}
        
        except Exception as e:
            self.logger.error(f"Error fetching by symbol: {str(e)}")
            return {"error": str(e)}
    
    def _get_token_data_by_slug(self, api_key, slug):
        """Get token data using the slug endpoint"""
        result = {}
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"slug": slug}
        
        try:
            self.logger.debug(f"Fetching CoinMarketCap data with slug: {slug}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # Check for rate limiting or errors
            if response.status_code != 200:
                self.logger.warning(f"CoinMarketCap API error: Status code {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
                
            data = response.json()
            
            # Check for errors
            if data.get("status", {}).get("error_code") != 0:
                error_message = data.get("status", {}).get("error_message", "Unknown error")
                self.logger.warning(f"CoinMarketCap API error: {error_message}")
                return {"error": f"API Error: {error_message}"}
            
            # Extract token data - with slug we get a list of tokens
            if "data" in data and len(data["data"]) > 0:
                # Get the first token ID
                token_id = list(data["data"].keys())[0]
                token_data = data["data"][token_id]
                
                if "quote" in token_data and "USD" in token_data["quote"]:
                    usd_data = token_data["quote"]["USD"]
                    result["cmc_price"] = usd_data.get("price", 0)
                    result["cmc_market_cap"] = usd_data.get("market_cap", 0)
                    result["cmc_volume_24h"] = usd_data.get("volume_24h", 0)
                    result["cmc_percent_change_24h"] = usd_data.get("percent_change_24h", 0)
                    result["cmc_percent_change_7d"] = usd_data.get("percent_change_7d", 0)
                    result["cmc_percent_change_30d"] = usd_data.get("percent_change_30d", 0)
                
                result["cmc_circulating_supply"] = token_data.get("circulating_supply", 0)
                result["cmc_total_supply"] = token_data.get("total_supply", 0)
                result["cmc_max_supply"] = token_data.get("max_supply", 0)
                result["name"] = token_data.get("name", self.project_name)
                result["symbol"] = token_data.get("symbol", self.token_symbol)
                
                # Add competitor data for comparison
                result["competitors"] = []
                
                return result
            else:
                self.logger.warning(f"Slug {slug} not found in CMC response")
                return {"error": "Slug not found"}
        
        except Exception as e:
            self.logger.error(f"Error fetching by slug: {str(e)}")
            return {"error": str(e)}


class DeFiLlamaModule(DataModule):
    """Gathers data from DeFiLlama API."""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_{self.__class__.__name__}.json"
        
        # Check cache first if enabled
        if use_cache and os.path.exists(cache_path):
            cache_time = os.path.getmtime(cache_path)
            if time.time() - cache_time < cache_ttl:
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        if 'tvl' in data:
                            self.logger.info(f"Using cached DeFiLlama data for {self.project_name} (TVL: ${data['tvl']})")
                            return data
                        else:
                            self.logger.warning(f"Cached DeFiLlama data for {self.project_name} is incomplete, refreshing")
                except:
                    self.logger.warning(f"Error reading cached DeFiLlama data for {self.project_name}, refreshing")
                
        # Only proceed with API call if cache missed
        self.logger.info(f"Gathering fresh DeFiLlama data for {self.project_name}")
        
        result = {}
        protocols_url = "https://api.llama.fi/v2/protocols"
        
        try:
            self.logger.debug(f"Fetching DeFiLlama protocols data")
            response = requests.get(protocols_url, timeout=15)  # Longer timeout for DefiLlama
            
            if response.status_code != 200:
                self.logger.warning(f"DeFiLlama API error: Status code {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
                
            protocols = response.json()
            self.logger.info(f"Retrieved {len(protocols)} protocols from DeFiLlama")
            
            # Try different name variations to find the project
            protocol = None
            
            # Create a list of possible identifiers to search
            name_variations = [
                self.project_name.lower(),
                self.coin_id.lower(),
                self.token_symbol.lower(),
                # Also try with hyphens instead of spaces
                self.project_name.lower().replace(" ", "-"),
                # And without punctuation
                re.sub(r'[^\w\s]', '', self.project_name.lower()),
                # And first word only (for multi-word project names)
                self.project_name.lower().split()[0] if ' ' in self.project_name else ''
            ]
            
            # Filter out empty strings
            name_variations = [name for name in name_variations if name]
            
            self.logger.info(f"Searching DeFiLlama for: {', '.join(name_variations)}")
            
            # First pass - exact match on name or symbol
            for name in name_variations:
                protocol = next((p for p in protocols if p["name"].lower() == name or 
                                p.get("symbol", "").lower() == name), None)
                if protocol:
                    self.logger.info(f"Found exact match in DeFiLlama under: {name}")
                    break
            
            # Second pass - contains match if exact match failed
            if not protocol:
                for name in name_variations:
                    protocol = next((p for p in protocols if name in p["name"].lower() or 
                                    name in p.get("symbol", "").lower()), None)
                    if protocol:
                        self.logger.info(f"Found partial match in DeFiLlama under: {name}")
                        break
            
            if protocol:
                self.logger.info(f"Found project in DeFiLlama: {protocol['name']} (ID: {protocol.get('slug', 'N/A')})")
                
                result["tvl"] = protocol.get("tvl", 0)
                result["tvl_change_1d"] = protocol.get("change_1d", 0)
                result["tvl_change_7d"] = protocol.get("change_7d", 0)
                result["category"] = protocol.get("category", "Unknown")
                result["chains"] = protocol.get("chains", [])
                
                # Add project details
                result["defillama_name"] = protocol.get("name", self.project_name)
                result["defillama_symbol"] = protocol.get("symbol", self.token_symbol)
                
                # Try to get TVL history
                if "slug" in protocol:
                    try:
                        tvl_history_url = f"https://api.llama.fi/v2/protocol/{protocol['slug']}"
                        self.logger.info(f"Fetching TVL history from: {tvl_history_url}")
                        
                        history_response = requests.get(tvl_history_url, timeout=15)
                        if history_response.status_code == 200:
                            history_data = history_response.json()
                            
                            # Process TVL history data
                            if "tvl" in history_data:
                                # Get last 60 days if available
                                tvl_points = history_data["tvl"][-60:] if len(history_data["tvl"]) > 60 else history_data["tvl"]
                                
                                # Format data for chart generation
                                formatted_tvl = []
                                for point in tvl_points:
                                    if "date" in point and "totalLiquidityUSD" in point:
                                        formatted_tvl.append([point["date"] * 1000, point["totalLiquidityUSD"]])
                                
                                result["tvl_history"] = formatted_tvl
                                self.logger.info(f"Retrieved {len(formatted_tvl)} TVL history data points")
                    except Exception as history_error:
                        self.logger.warning(f"Error getting TVL history: {history_error}")
                
                # Log successful data retrieval
                self.logger.info(f"Retrieved DeFiLlama data: TVL=${result.get('tvl', 'N/A')}, " 
                               f"category={result.get('category', 'N/A')}")
                
                # Cache the result
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached DeFiLlama data for {self.project_name}")
                
                return result
            else:
                self.logger.warning(f"Project {self.project_name} not found in DeFiLlama")
                # Create a minimal result rather than an error
                result = {
                    "not_found": True,
                    "tvl": 0,
                    "category": "Unknown"
                }
                return result
                
        except Exception as e:
            self.logger.error(f"Error in DeFiLlama module: {str(e)}", exc_info=True)
            return {"error": str(e)}


class DataGatherer:
    """Orchestrates data gathering from multiple sources."""
    
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        
        # Initialize all data modules
        self.modules = [
            CoinGeckoModule(project_name, logger),
            CoinMarketCapModule(project_name, logger),
            DeFiLlamaModule(project_name, logger)
        ]
    
    def gather_all_data(self) -> Dict[str, Any]:
        """Gather data from all sources."""
        self.logger.info(f"Starting comprehensive data gathering for {self.project_name}")
        
        # Collect data from all modules
        all_data = {}
        
        for module in self.modules:
            module_name = module.__class__.__name__.replace("Module", "").lower()
            self.logger.info(f"Running {module_name} data module")
            
            try:
                module_data = module.gather_data()
                all_data[module_name] = module_data
            except Exception as e:
                self.logger.error(f"Error in {module_name} module: {str(e)}")
                all_data[module_name] = {"error": str(e)}
        
        # Also gather enhanced market data specifically for better reports
        try:
            coingecko_module = next((m for m in self.modules if isinstance(m, CoinGeckoModule)), None)
            if coingecko_module:
                enhanced_data = coingecko_module.get_enhanced_market_data()
                if "error" not in enhanced_data:
                    all_data["enhanced_market"] = enhanced_data
                    self.logger.info("Successfully added enhanced market data")
                else:
                    self.logger.warning(f"Error getting enhanced market data: {enhanced_data.get('error')}")
        except Exception as e:
            self.logger.error(f"Error getting enhanced market data: {str(e)}")
        
        return all_data
    
    def get_enhanced_market_data(self) -> Dict[str, Any]:
        """Get enhanced market data specifically."""
        try:
            coingecko_module = next((m for m in self.modules if isinstance(m, CoinGeckoModule)), None)
            if coingecko_module:
                return coingecko_module.get_enhanced_market_data()
            else:
                self.logger.warning("CoinGecko module not found")
                return {"error": "CoinGecko module not found"}
        except Exception as e:
            self.logger.error(f"Error getting enhanced market data: {str(e)}")
            return {"error": str(e)}
    
    def get_formatted_tokenomics(self, data: Dict[str, Any]) -> str:
        """Format tokenomics data into a readable string with comprehensive details."""
        lines = [f"# {self.project_name} Tokenomics"]
        
        # Prioritize data sources: Enhanced data first, then CoinGecko, then CMC
        enhanced = data.get("enhanced_market", {})
        coingecko = data.get("coingecko", {})
        coinmarketcap = data.get("coinmarketcap", {})
        
        # Use best available data, prioritizing enhanced data
        
        # Basic Supply Information
        lines.append("\n## Supply Details")
        
        # Symbol
        symbol = enhanced.get("symbol") or coingecko.get("symbol", "").upper() or self.project_name.upper()
        lines.append(f"- Symbol: {symbol}")
        
        # Total Supply
        total_supply = None
        if "total_supply" in enhanced:
            total_supply = enhanced["total_supply"]
        elif "total_supply" in coingecko:
            total_supply = coingecko["total_supply"]
        elif "cmc_total_supply" in coinmarketcap:
            total_supply = coinmarketcap["cmc_total_supply"]
            
        if total_supply:
            lines.append(f"- Total Supply: {self._format_number(total_supply)} {symbol}")
        
        # Circulating Supply
        circulating_supply = None
        if "circulating_supply" in enhanced:
            circulating_supply = enhanced["circulating_supply"]
        elif "circulating_supply" in coingecko:
            circulating_supply = coingecko["circulating_supply"]
        elif "cmc_circulating_supply" in coinmarketcap:
            circulating_supply = coinmarketcap["cmc_circulating_supply"]
            
        if circulating_supply:
            lines.append(f"- Circulating Supply: {self._format_number(circulating_supply)} {symbol}")
        
        # Calculate circulation ratio if possible
        if total_supply and circulating_supply and total_supply > 0:
            ratio = (circulating_supply / total_supply) * 100
            lines.append(f"- Circulating/Total Ratio: {ratio:.2f}%")
        
        # Market Metrics
        lines.append("\n## Market Metrics")
        
        # Current Price
        price = None
        if "current_price" in enhanced:
            price = enhanced["current_price"]
        elif "current_price" in coingecko:
            price = coingecko["current_price"]
        elif "cmc_price" in coinmarketcap:
            price = coinmarketcap["cmc_price"]
            
        if price:
            lines.append(f"- Current Price: ${price:.4f}")
        
        # Market Cap
        market_cap = None
        if "market_cap" in enhanced:
            market_cap = enhanced["market_cap"]
        elif "market_cap" in coingecko:
            market_cap = coingecko["market_cap"]
        elif "cmc_market_cap" in coinmarketcap:
            market_cap = coinmarketcap["cmc_market_cap"]
            
        if market_cap:
            lines.append(f"- Market Cap: ${self._format_number(market_cap)}")
        
        # Price Changes
        if "price_change_24h" in enhanced:
            lines.append(f"- 24-Hour Change: {enhanced['price_change_24h']:.2f}%")
        if "price_change_7d" in enhanced:
            lines.append(f"- 7-Day Change: {enhanced['price_change_7d']:.2f}%")
        if "price_change_30d" in enhanced:
            lines.append(f"- 30-Day Change: {enhanced['price_change_30d']:.2f}%")
        if "price_change_60d" in enhanced:
            lines.append(f"- 60-Day Change: {enhanced['price_change_60d']:.2f}%")
        
        # Add DeFi data if available
        defillama = data.get("defillama", {})
        if "tvl" in defillama and defillama["tvl"]:
            lines.append("\n## DeFi Metrics")
            lines.append(f"- Total Value Locked: ${self._format_number(defillama['tvl'])}")
            
            if "tvl_change_1d" in defillama:
                lines.append(f"- TVL 24h Change: {defillama['tvl_change_1d']:.2f}%")
            if "tvl_change_7d" in defillama:
                lines.append(f"- TVL 7d Change: {defillama['tvl_change_7d']:.2f}%")
            
            if "category" in defillama:
                lines.append(f"- DeFi Category: {defillama['category']}")
            
            if "chains" in defillama and defillama["chains"]:
                lines.append(f"- Blockchain(s): {', '.join(defillama['chains'])}")
        
        return "\n".join(lines)
    
    def _format_number(self, number: float) -> str:
        """Format large numbers for readability."""
        if number is None:
            return "N/A"
            
        try:
            if number >= 1_000_000_000:
                return f"{number/1_000_000_000:.2f}B"
            elif number >= 1_000_000:
                return f"{number/1_000_000:.2f}M"
            elif number >= 1_000:
                return f"{number/1_000:.2f}K"
            else:
                return f"{number:.2f}"
        except:
            return str(number) 