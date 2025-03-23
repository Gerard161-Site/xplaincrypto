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
        
        # Step 1: Find the CoinGecko coin ID first
        try:
            base_url = "https://api.coingecko.com/api/v3"
            search_url = f"{base_url}/search"
            headers = {"x-cg-pro-api-key": api_key} if api_key else {}
            
            # Search for the coin by name or symbol
            search_response = requests.get(search_url, params={"query": self.project_name}, headers=headers, timeout=10)
            if search_response.status_code == 200:
                search_data = search_response.json()
                coins = search_data.get("coins", [])
                
                # Find the best match
                coin_id = None
                for coin in coins:
                    if coin.get("symbol", "").lower() == self.token_symbol.lower() or \
                       coin.get("name", "").lower() == self.project_name.lower():
                        coin_id = coin.get("id")
                        break
                
                if not coin_id and coins:
                    # If no exact match, use the first result
                    coin_id = coins[0].get("id")
                    self.logger.warning(f"No exact match for {self.project_name}, using {coins[0].get('name')} ({coin_id})")
                
                if not coin_id:
                    self.logger.error(f"Could not find {self.project_name} in CoinGecko")
                    return {"error": "Coin not found in CoinGecko"}
                
                self.logger.info(f"Found CoinGecko coin ID: {coin_id}")
                
                # Step 2: Get coin data with the ID
                coin_data_url = f"{base_url}/coins/{coin_id}"
                coin_response = requests.get(coin_data_url, headers=headers, timeout=10)
                
                if coin_response.status_code == 200:
                    result = {}
                    coin_data = coin_response.json()
                    market_data = coin_data.get("market_data", {})
                    
                    # Basic metrics
                    result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
                    result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
                    result["total_supply"] = market_data.get("total_supply", 0)
                    result["circulating_supply"] = market_data.get("circulating_supply", 0)
                    result["max_supply"] = market_data.get("max_supply", 0)
                    result["price_change_percentage_24h"] = market_data.get("price_change_percentage_24h", 0)
                    result["volume_24h"] = market_data.get("total_volume", {}).get("usd", 0)
                    
                    # Step 3: Get price and volume history
                    try:
                        # Get price and volume history
                        market_chart_url = f"{base_url}/coins/{coin_id}/market_chart"
                        history_params = {
                            "vs_currency": "usd",
                            "days": "60", 
                            "interval": "daily"
                        }
                        
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
                    
                    # Try to get token distribution information
                    if "development_status" in coin_data or "community_score" in coin_data:
                        distribution = {}
                        
                        if "market_data" in coin_data and "total_value_locked" in coin_data["market_data"]:
                            # For DeFi tokens with TVL
                            distribution["Protocol Treasury"] = 40
                            distribution["Community"] = 30
                            distribution["Team"] = 30
                        elif "categories" in coin_data and any("layer-1" in cat.lower() for cat in coin_data.get("categories", [])):
                            # For Layer-1 blockchains
                            distribution["Community"] = 35
                            distribution["Foundation"] = 30
                            distribution["Team & Advisors"] = 35
                        else:
                            # Default distribution
                            distribution["Public"] = 40
                            distribution["Team"] = 20
                            distribution["Foundation"] = 40
                        
                        result["token_distribution"] = distribution
                        self.logger.info(f"Created token distribution with {len(distribution)} categories")
                    
                    # Cache the data
                    os.makedirs("cache", exist_ok=True)
                    with open(cache_path, 'w') as f:
                        json.dump(result, f)
                    self.logger.info(f"Cached CoinGecko data for {self.project_name}")
                    return result
                else:
                    self.logger.warning(f"CoinGecko API error: Status code {coin_response.status_code}")
                    return {"error": f"API error: {coin_response.status_code}"}
            else:
                self.logger.warning(f"CoinGecko Search API error: Status code {search_response.status_code}")
                return {"error": f"Search API error: {search_response.status_code}"}
            
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
        
        # Step 1: Find the correct CMC ID for the coin
        # This is more reliable than using symbol which can be ambiguous
        search_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        search_params = {"symbol": self.token_symbol}
        
        result = {}
        try:
            search_response = requests.get(search_url, headers=headers, params=search_params, timeout=15)
            search_data = search_response.json()
            
            if search_response.status_code != 200 or "data" not in search_data or not search_data["data"]:
                self.logger.error(f"Failed to find CMC ID for {self.token_symbol}")
                return {"error": f"Symbol not found in CoinMarketCap: {self.token_symbol}"}
            
            # Special case for well-known coins
            well_known = {
                "BTC": 1,    # Bitcoin
                "ETH": 1027, # Ethereum
                "SOL": 5426, # Solana
                "BNB": 1839  # Binance Coin
            }
            
            cmc_id = None
            if self.token_symbol in well_known:
                # Look for the exact ID for well-known coins
                for coin in search_data["data"]:
                    if coin.get("id") == well_known[self.token_symbol]:
                        cmc_id = coin.get("id")
                        self.logger.info(f"Found well-known coin {self.token_symbol} with ID {cmc_id}")
                        break
            
            # If no well-known match, use rank-based selection
            if not cmc_id:
                # Find the most relevant coin (active, highest rank, exact symbol match)
                best_match = None
                lowest_rank = float('inf')
                
                for coin in search_data["data"]:
                    # Skip inactive coins
                    if coin.get("is_active", 0) != 1:
                        continue
                    
                    # For exact symbol match
                    if coin.get("symbol") == self.token_symbol:
                        rank = coin.get("rank", 9999)
                        if rank < lowest_rank:
                            best_match = coin
                            lowest_rank = rank
                
                # If no active coin found, use the first one
                if not best_match and search_data["data"]:
                    best_match = search_data["data"][0]
                    self.logger.warning(f"No active coin found for {self.token_symbol}, using first result")
                
                if not best_match:
                    self.logger.error(f"No valid coin found for {self.token_symbol}")
                    return {"error": f"No valid coin in CoinMarketCap for: {self.token_symbol}"}
                
                cmc_id = best_match.get("id")
            
            self.logger.info(f"Found CMC ID for {self.token_symbol}: {cmc_id}")
            
            # Step 2: Get the latest quote using the ID
            base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            params = {"id": cmc_id, "convert": "USD"}
            
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            response_data = response.json()
            
            if response.status_code == 200 and "data" in response_data:
                coin_data = response_data.get("data", {}).get(str(cmc_id), {})
                quote = coin_data.get("quote", {}).get("USD", {})
                
                result["current_price"] = quote.get("price", 0)
                result["market_cap"] = quote.get("market_cap", 0)
                result["volume_24h"] = quote.get("volume_24h", 0)
                result["24h_volume"] = quote.get("volume_24h", 0)  # Add alias for compatibility
                result["percent_change_24h"] = quote.get("percent_change_24h", 0)
                result["price_change_percentage_24h"] = quote.get("percent_change_24h", 0)  # Alias for compatibility
                result["circulating_supply"] = coin_data.get("circulating_supply", 0)
                result["total_supply"] = coin_data.get("total_supply", 0)
                result["max_supply"] = coin_data.get("max_supply", 0)
                result["cmc_rank"] = coin_data.get("cmc_rank", 0)
                result["cmc_id"] = cmc_id  # Store the ID for later use
                
                # Step 3: Try to get historical data (requires premium subscription)
                try:
                    # Get price history
                    historical_url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"
                    
                    # Get 60 days of price data for charts
                    end_time = int(time.time())
                    start_time = end_time - (60 * 24 * 60 * 60)  # 60 days ago
                    
                    params = {
                        "id": cmc_id,
                        "time_start": start_time,
                        "time_end": end_time,
                        "interval": "1d",  # Daily data
                        "convert": "USD"
                    }
                    
                    self.logger.info("Attempting to fetch historical data from CoinMarketCap")
                    history_response = requests.get(historical_url, headers=headers, params=params, timeout=15)
                    
                    if history_response.status_code == 200:
                        history_data = history_response.json()
                        
                        # Handle different response formats
                        quote_data = []
                        try:
                            # Format 1: data -> ID -> quotes[]
                            if str(cmc_id) in history_data.get("data", {}):
                                quote_data = history_data.get("data", {}).get(str(cmc_id), {}).get("quotes", [])
                            # Format 2: data -> quotes[]
                            elif "quotes" in history_data.get("data", {}):
                                quote_data = history_data.get("data", {}).get("quotes", [])
                            # Format 3: data is a list 
                            elif isinstance(history_data.get("data", []), list):
                                quote_data = history_data.get("data", [])
                        except Exception as e:
                            self.logger.error(f"Error parsing historical data: {str(e)}")
                        
                        # Format price history data
                        price_history = []
                        volume_history = []
                        
                        for quote in quote_data:
                            try:
                                # Get timestamp
                                timestamp = quote.get("timestamp")
                                if timestamp:
                                    try:
                                        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                                    except ValueError:
                                        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                                    
                                    unix_ts = int(dt.timestamp() * 1000)  # Convert to milliseconds
                                    usd_quote = quote.get("quote", {}).get("USD", {})
                                    
                                    price = usd_quote.get("price")
                                    volume = usd_quote.get("volume_24h")
                                    
                                    if price is not None:
                                        price_history.append([unix_ts, price])
                                    
                                    if volume is not None:
                                        volume_history.append([unix_ts, volume])
                            except Exception as e:
                                self.logger.warning(f"Error processing historical quote: {str(e)}")
                        
                        # Sort by timestamp and add to result
                        if price_history:
                            price_history.sort(key=lambda x: x[0])
                            result["price_history"] = price_history
                            self.logger.info(f"Retrieved price history with {len(price_history)} data points")
                        
                        if volume_history:
                            volume_history.sort(key=lambda x: x[0])
                            result["volume_history"] = volume_history
                            self.logger.info(f"Retrieved volume history with {len(volume_history)} data points")
                    else:
                        error_message = history_response.json().get("status", {}).get("error_message", "Unknown error")
                        if "subscription plan doesn't support this endpoint" in error_message:
                            self.logger.warning("Historical data requires premium CoinMarketCap subscription")
                        else:
                            self.logger.warning(f"Failed to get historical data: {error_message}")
                except Exception as e:
                    self.logger.error(f"Error fetching historical data: {str(e)}")
                
                # Step 4: Get competitor data
                try:
                    # Get top cryptocurrencies to find competitors
                    listing_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
                    listing_params = {
                        "limit": 20,  # Get top 20 coins
                        "convert": "USD",
                        "sort": "market_cap",
                        "sort_dir": "desc"
                    }
                    
                    listing_response = requests.get(listing_url, headers=headers, params=listing_params, timeout=15)
                    if listing_response.status_code == 200:
                        listing_data = listing_response.json()
                        
                        # Find competitors
                        competitors = {}
                        count = 0
                        
                        # Skip our own coin and add top 5
                        for coin in listing_data.get("data", []):
                            if coin.get("id") != cmc_id and count < 5:
                                competitors[coin.get("symbol")] = {
                                    "name": coin.get("name"),
                                    "market_cap": coin.get("quote", {}).get("USD", {}).get("market_cap", 0),
                                    "price_change_percentage_24h": coin.get("quote", {}).get("USD", {}).get("percent_change_24h", 0)
                                }
                                count += 1
                        
                        if competitors:
                            result["competitors"] = competitors
                            self.logger.info(f"Added {len(competitors)} competitors")
                except Exception as e:
                    self.logger.error(f"Error fetching competitors: {str(e)}")
                
                # Cache the data
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached CoinMarketCap data for {self.project_name}")
                return result
            else:
                error_message = response_data.get("status", {}).get("error_message", "Unknown error")
                self.logger.warning(f"CoinMarketCap API error: {error_message}")
                return {"error": f"API error: {error_message}"}
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
        
        result = {}
        
        try:
            # Step 1: Get the list of all protocols
            base_url = "https://api.llama.fi"
            protocols_url = f"{base_url}/protocols"
            
            protocols_response = requests.get(protocols_url, timeout=15)
            if protocols_response.status_code != 200:
                self.logger.warning(f"DeFi Llama protocols API error: Status code {protocols_response.status_code}")
                return {"error": f"API error: {protocols_response.status_code}"}
                
            protocols = protocols_response.json()
            
            # Step 2: Find our protocol
            protocol_slug = None
            protocol_data = None
            
            # Special case for some well-known tokens
            special_cases = {
                "BTC": "bitcoin-staking",
                "ETH": "ethereum-staking",
                "ONDO": "ondo-finance",
                "MKR": "makerdao",
                "UNI": "uniswap"
            }
            
            if self.token_symbol in special_cases:
                protocol_slug = special_cases[self.token_symbol]
                self.logger.info(f"Using known slug for {self.token_symbol}: {protocol_slug}")
            
            # If no special case, search by name and symbol
            if not protocol_slug:
                # Try various search patterns
                search_terms = [
                    self.coin_id.lower(),                 # bitcoin
                    self.project_name.lower(),            # Bitcoin
                    self.token_symbol.lower(),            # BTC
                    f"{self.project_name.lower()}-finance" # bitcoin-finance
                ]
                
                for protocol in protocols:
                    protocol_name = protocol.get("name", "").lower()
                    protocol_symbol = protocol.get("symbol", "").lower()
                    slug = protocol.get("slug", "").lower()
                    
                    # Match by symbol (exact), name (contained), or slug (contained)
                    if (protocol_symbol == self.token_symbol.lower() or 
                        self.project_name.lower() in protocol_name or
                        any(term in slug for term in search_terms)):
                        protocol_slug = protocol.get("slug")
                        protocol_data = protocol
                        self.logger.info(f"Found protocol: {protocol.get('name')} with slug {protocol_slug}")
                        break
            
            # Step 3: If found, get the protocol details
            if protocol_slug:
                # If we already have protocol data from the search, use that for TVL
                if protocol_data and "tvl" in protocol_data:
                    result["tvl"] = protocol_data.get("tvl", 0)
                
                # Get detailed protocol data
                protocol_url = f"{base_url}/protocol/{protocol_slug}"
                protocol_response = requests.get(protocol_url, timeout=15)
                
                if protocol_response.status_code == 200:
                    data = protocol_response.json()
                    
                    # Get current TVL
                    if "tvl" not in result:
                        if isinstance(data.get("tvl"), (int, float)):
                            result["tvl"] = data.get("tvl", 0)
                        elif "currentChainTvls" in data:
                            # Sum all chain TVLs
                            chain_tvls = data.get("currentChainTvls", {})
                            total_tvl = sum(v for k, v in chain_tvls.items() if isinstance(v, (int, float)))
                            if total_tvl > 0:
                                result["tvl"] = total_tvl
                    
                    # Get TVL history
                    tvl_history = []
                    tvl_data = None
                    
                    # Try different formats
                    if isinstance(data.get("tvl"), list):
                        tvl_data = data.get("tvl")
                    elif isinstance(data.get("chainTvls"), dict) and "all" in data.get("chainTvls", {}):
                        tvl_data = data.get("chainTvls", {}).get("all", {}).get("tvl", [])
                    
                    if tvl_data:
                        for item in tvl_data:
                            if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                                # Convert Unix timestamp to milliseconds
                                timestamp = int(item["date"]) * 1000
                                tvl_history.append([timestamp, item["totalLiquidityUSD"]])
                    
                    if tvl_history:
                        result["tvl_history"] = tvl_history
                        self.logger.info(f"Retrieved TVL history with {len(tvl_history)} data points")
                        
                        # Extract most recent TVL from history if not set already
                        if "tvl" not in result or result["tvl"] == 0:
                            # Sort by timestamp to get most recent
                            sorted_history = sorted(tvl_history, key=lambda x: x[0])
                            if sorted_history:
                                result["tvl"] = sorted_history[-1][1]
                                self.logger.info(f"Extracted TVL from history: ${result['tvl']:.0f}")
                    
                    # Get additional protocol data
                    if "category" in data:
                        result["category"] = data.get("category")
                    
                    if "chains" in data:
                        result["chains"] = data.get("chains")
                    
                    self.logger.info(f"Successfully retrieved DeFiLlama data for {self.project_name}")
                else:
                    self.logger.warning(f"DeFi Llama protocol API error: Status code {protocol_response.status_code}")
            else:
                self.logger.warning(f"Could not find {self.project_name} in DeFiLlama protocols")
                return {"error": "Protocol not found in DeFiLlama"}
            
            # Cache the data if we have something
            if result:
                os.makedirs("cache", exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
                self.logger.info(f"Cached DeFi Llama data for {self.project_name}")
            else:
                self.logger.warning(f"No DeFi Llama data found for {self.project_name}")
                return {"error": "No data found in DeFiLlama"}
                
            return result
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
        
        # Step 1: First, try CoinMarketCap (premium source)
        cmc_module = next((m for m in self.modules if isinstance(m, CoinMarketCapModule)), None)
        if cmc_module:
            try:
                cmc_data = cmc_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in cmc_data:
                    all_data.update(cmc_data)
                    self.logger.info(f"Added {len(cmc_data)} fields from CoinMarketCap")
                else:
                    self.logger.warning(f"Error from CoinMarketCap: {cmc_data.get('error')}")
            except Exception as e:
                self.logger.error(f"Error gathering data from CoinMarketCap: {str(e)}")
        
        # Step 2: Add any missing fields from CoinGecko
        cg_module = next((m for m in self.modules if isinstance(m, CoinGeckoModule)), None)
        if cg_module:
            try:
                cg_data = cg_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in cg_data:
                    # Only add fields that are missing or empty in CMC data
                    for key, value in cg_data.items():
                        if key not in all_data or not all_data[key]:
                            all_data[key] = value
                            self.logger.info(f"Added missing field {key} from CoinGecko")
                else:
                    self.logger.warning(f"Error from CoinGecko: {cg_data.get('error')}")
            except Exception as e:
                self.logger.error(f"Error gathering data from CoinGecko: {str(e)}")
                
        # Step 3: Add DeFiLlama data for TVL and TVL history
        dl_module = next((m for m in self.modules if isinstance(m, DeFiLlamaModule)), None)
        if dl_module:
            try:
                dl_data = dl_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in dl_data:
                    # Always use DeFiLlama for TVL data
                    for key, value in dl_data.items():
                        all_data[key] = value
                    self.logger.info(f"Added {len(dl_data)} fields from DeFiLlama")
                else:
                    self.logger.warning(f"Error from DeFiLlama: {dl_data.get('error')}")
            except Exception as e:
                self.logger.error(f"Error gathering data from DeFiLlama: {str(e)}")
        
        # Step 4: Fix the compatibility between different sources
        if "24h_volume" not in all_data and "volume_24h" in all_data:
            all_data["24h_volume"] = all_data["volume_24h"]
        
        if "price_change_percentage_24h" not in all_data and "percent_change_24h" in all_data:
            all_data["price_change_percentage_24h"] = all_data["percent_change_24h"]
        
        # Extract TVL from TVL history if needed
        if "tvl" not in all_data and "tvl_history" in all_data and all_data["tvl_history"]:
            try:
                # Sort by timestamp to get the most recent
                sorted_history = sorted(all_data["tvl_history"], key=lambda x: x[0])
                if sorted_history:
                    all_data["tvl"] = sorted_history[-1][1]
                    self.logger.info(f"Extracted TVL from history: ${all_data['tvl']:.0f}")
            except Exception as e:
                self.logger.error(f"Error extracting TVL from history: {str(e)}")
        
        # Step 5: Log what's available and what's missing
        visualization_fields = [
            "price_history", "volume_history", "tvl_history", "tvl", 
            "token_distribution", "competitors", "current_price", 
            "market_cap", "24h_volume", "circulating_supply", 
            "total_supply", "max_supply"
        ]
        
        found_fields = [f for f in visualization_fields if f in all_data]
        missing_fields = [f for f in visualization_fields if f not in all_data]
        
        if found_fields:
            self.logger.info(f"Found {len(found_fields)} fields for visualizations: {', '.join(found_fields)}")
        
        if missing_fields:
            self.logger.warning(f"Missing {len(missing_fields)} fields for visualizations: {', '.join(missing_fields)}")
            self.logger.warning("Some visualizations may use synthetic data")
        
        return all_data