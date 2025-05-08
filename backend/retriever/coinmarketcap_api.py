from typing import Dict, Any, Optional, List
import aiohttp
import logging
import os
import json
import time
import asyncio
from datetime import datetime, timedelta
# Add dotenv at the top to ensure API key is loaded
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Debug output for environment variables
    print(f"Environment loaded in coinmarketcap_api.py")
    print(f"API key available: {os.getenv('COINMARKETCAP_API_KEY') is not None}")
except ImportError:
    print("python-dotenv not installed, using environment variables as is")

from backend.retriever.coingecko_api import DataModule
from backend.utils.cache_utils import CacheManager

class CoinMarketCapAPI(DataModule):
    """CoinMarketCap API retriever for cryptocurrency data"""

    def __init__(self, project_name=None, token_symbol=None, coin_id=None):
        """Initialize with project information."""
        # Validate project_name before calling parent init
        if not project_name or not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("A valid project_name is required for DataModule initialization")
            
        # Call parent's init with validated project_name
        super().__init__(project_name=project_name.strip())
        
        # Set up token symbol and coin ID
        self.token_symbol = token_symbol or self._normalize_project_name()
        self.coin_id = coin_id or self.project_name
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Try to create the cache directory if it doesn't exist
        try:
            cache_dir = os.path.join("docs", self.project_name, "cache", "coinmarketcap")
            os.makedirs(cache_dir, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"Failed to create cache directory: {str(e)}")

    def gather_data(self, use_cache: bool = True, cache_ttl: int = 10800) -> Dict[str, Any]:
        """Synchronous data gathering method required by DataModule."""
        self.logger.info(f"Gathering synchronous CoinMarketCap data for {self.project_name}")
        
        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Check cache first if use_cache is enabled
        if use_cache:
            coin_key = self.project_name.lower()
            cached_data = cache_manager.load("coinmarketcap", "data", coin_key)
            if cached_data and self._is_valid_data(cached_data):
                self.logger.info(f"Using cached data for {self.project_name} in gather_data")
                return cached_data
                
        try:
            return asyncio.run(self.fetch_data(self.project_name))
        except Exception as e:
            self.logger.error(f"Error in synchronous gather_data: {str(e)}")
            return {"error": f"Synchronous data gathering failed: {str(e)}"}

    async def fetch_data(self, coin: str) -> dict:
        """Fetch comprehensive data from CoinMarketCap for a given coin."""
        self.project_name = coin
        self.logger.info(f"Fetching CoinMarketCap data for {coin}")

        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Check cache first
        coin_key = coin.lower()
        cached_data = cache_manager.load("coinmarketcap", "data", coin_key)
        if cached_data and self._is_valid_data(cached_data):
            self.logger.info(f"Using cached data for {coin} (price: ${cached_data.get('current_price', 'N/A')})")
            return cached_data

        # Check if API is enabled
        api_enabled = os.getenv("COINMARKETCAP_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"CoinMarketCap API is disabled")
            return {"coinmarketcap_disabled": "CoinMarketCap API disabled by configuration"}

        # Get API key with more explicit debugging
        api_key = os.getenv("COINMARKETCAP_API_KEY", "")
        self.logger.info(f"COINMARKETCAP_API_KEY is {'set' if api_key else 'NOT SET'}")
        self.logger.info(f"API key value length: {len(api_key)}")
        
        # Print all environment variables for debugging
        for env_var in ['COINMARKETCAP_API_KEY', 'COINMARKETCAP_ENABLED', 'OPENAI_API_KEY']:
            value = os.getenv(env_var)
            self.logger.info(f"Env variable check - {env_var}: {'set (length: ' + str(len(value)) + ')' if value else 'NOT SET'}")
        
        if not api_key:
            self.logger.error("CoinMarketCap API key not found in environment")
            return {"error": "API key missing"}

        try:
            # Normalize input to symbol
            symbol = self._normalize_project_name()
            self.logger.info(f"Normalized symbol: {coin} -> {symbol}")

            # Search for coin ID by symbol
            cmc_id = await self._find_cmc_id(symbol, api_key)
            if not cmc_id:
                self.logger.error(f"No valid CMC ID found for symbol {symbol}")
                return {"error": f"No valid coin found in CoinMarketCap for symbol: {symbol}"}

            self.logger.info(f"Selected CMC ID: {cmc_id}")

            # Fetch coin data
            base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            params = {"id": cmc_id, "convert": "USD"}
            headers = {"X-CMC_PRO_API_KEY": api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, headers=headers, params=params, timeout=15) as response:
                    response_data = await response.json()
                    self.logger.info(f"API response status: {response.status}")
                    self.logger.debug(f"API response data: {json.dumps(response_data, indent=2)}")

                    if response.status != 200:
                        error_message = response_data.get("status", {}).get("error_message", "Unknown error")
                        self.logger.error(f"API error: {error_message}")
                        return {"error": f"API error: {error_message}"}

                    coin_data = response_data.get("data", {}).get(str(cmc_id), {})
                    if not coin_data:
                        self.logger.error(f"No coin data found for ID {cmc_id}")
                        return {"error": f"No data returned for CMC ID: {cmc_id}"}

                    quote = coin_data.get("quote", {}).get("USD", {})
                    if not quote:
                        self.logger.error(f"No USD quote data for ID {cmc_id}")
                        return {"error": f"No USD quote data for {coin}"}

                    # Build result
                    result = {
                        "current_price": quote.get("price", 0),
                        "market_cap": quote.get("market_cap", 0),
                        "volume_24h": quote.get("volume_24h", 0),
                        "24h_volume": quote.get("volume_24h", 0),
                        "percent_change_24h": quote.get("percent_change_24h", 0),
                        "price_change_percentage_24h": quote.get("percent_change_24h", 0),
                        "circulating_supply": coin_data.get("circulating_supply", 0),
                        "total_supply": coin_data.get("total_supply", 0),
                        "max_supply": coin_data.get("max_supply", 0),
                        "cmc_rank": coin_data.get("cmc_rank", 0),
                        "cmc_id": cmc_id,
                        "name": coin_data.get("name", ""),
                        "symbol": coin_data.get("symbol", "")
                    }

                    for key in ["last_updated", "date_added", "slug", "num_market_pairs"]:
                        if key in coin_data:
                            result[key] = coin_data[key]

                    # Validate data
                    if not self._is_valid_data(result):
                        self.logger.error(f"Invalid data for {coin} (ID: {cmc_id}): {result}")
                        return {"error": f"Invalid data returned for {coin}: all critical fields are zero"}

                    # Cache the result
                    cache_manager.save(result, "coinmarketcap", "data", coin_key)
                    self.logger.info(f"Cached data for {coin}")

                    return result

        except Exception as e:
            self.logger.error(f"Error in CoinMarketCap fetch: {str(e)}", exc_info=True)
            return {"error": f"Tool execution error: {str(e)}"}

    async def _find_cmc_id(self, symbol: str, api_key: str) -> Optional[int]:
        """Find the CoinMarketCap ID for a given coin symbol."""
        self.logger.info(f"Searching for CMC ID for symbol {symbol}")
        async with aiohttp.ClientSession() as session:
            headers = {"X-CMC_PRO_API_KEY": api_key}
            search_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"

            # Search by symbol
            params = {"symbol": symbol.upper()}
            async with session.get(search_url, headers=headers, params=params, timeout=15) as response:
                if response.status != 200:
                    self.logger.error(f"Symbol search HTTP error: {response.status}")
                    return None

                data = await response.json()
                self.logger.debug(f"Symbol search response: {json.dumps(data, indent=2)}")

                if not isinstance(data.get("data"), list):
                    self.logger.error(f"Symbol search failed: data is not a list, got {type(data.get('data'))}: {data.get('status', {}).get('error_message', 'No data')}")
                    return None

                results = data["data"]
                log_results = ', '.join(f"{r['name']} ({r['symbol']}, ID: {r['id']})" for r in results[:5])
                self.logger.info(f"Symbol search for '{symbol}' found {len(results)} results: {log_results}")

                if not results:
                    self.logger.error(f"No results found for symbol {symbol}")
                    return None

                # Filter active coins and select the best match by rank
                active_results = [r for r in results if r.get("is_active", 0) == 1]
                if not active_results:
                    self.logger.error(f"No active coins found for symbol {symbol}")
                    return None

                # Sort by rank (lower is better) and select the top result
                best_result = min(active_results, key=lambda r: r.get("rank", 9999))
                cmc_id = best_result["id"]
                self.logger.info(f"Selected coin: {best_result['name']} ({best_result['symbol']}) with ID {cmc_id} (rank: {best_result.get('rank', 'N/A')})")

                return cmc_id

    def _is_valid_data(self, data: dict) -> bool:
        """Validate that the data contains meaningful values."""
        critical_fields = ["current_price", "market_cap", "volume_24h"]
        return all(data.get(field, 0) > 0 for field in critical_fields)

    def _normalize_project_name(self) -> str:
        """Normalize the project name to a CMC-compatible token symbol."""
        project_name = self.project_name.strip().upper()
        special_cases = {
            "BITCOIN": "BTC",
            "ETHEREUM": "ETH",
            "CARDANO": "ADA",
            "SOLANA": "SOL",
            "BINANCE": "BNB",
            "MONERO": "XMR",
            "ONDO FINANCE": "ONDO",
            "ONDO": "ONDO",
            "AERODROME FINANCE": "AERO",
            "AERO": "AERO"
        }
        if project_name in special_cases:
            return special_cases[project_name]
        if "." in project_name:
            return project_name.split('.')[0]
        return project_name

    async def fetch_market_data(self, coin: str) -> dict:
        """Fetch market cap and supply data from CoinMarketCap for a given coin."""
        self.logger.info(f"Fetching CoinMarketCap market data for {coin}")
        
        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)

        # Check cache first
        coin_key = coin.lower()
        cached_data = cache_manager.load("coinmarketcap", "market", coin_key)
        if cached_data:
            self.logger.info(f"Using cached market data for {coin}")
            return cached_data

        try:
            # Try full API fetch first and extract market data
            full_data = await self.fetch_data(coin)
            
            if "error" in full_data:
                self.logger.error(f"Error in fetch_market_data via full fetch: {full_data['error']}")
                return {"error": full_data["error"]}
            
            # Extract only market-related data
            market_data = {
                "market_cap": full_data.get("market_cap", 0),
                "circulating_supply": full_data.get("circulating_supply", 0),
                "total_supply": full_data.get("total_supply", 0),
                "max_supply": full_data.get("max_supply", 0)
            }
            
            # Cache the result
            cache_manager.save(market_data, "coinmarketcap", "market", coin_key)
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Error in fetch_market_data: {str(e)}")
            return {"error": f"Failed to fetch market data: {str(e)}"}

    async def fetch_price_data(self, coin: str) -> dict:
        """Fetch price and volume data from CoinMarketCap for a given coin."""
        self.logger.info(f"Fetching CoinMarketCap price data for {coin}")
        
        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)

        # Check cache first
        coin_key = coin.lower()
        cached_data = cache_manager.load("coinmarketcap", "price", coin_key)
        if cached_data:
            self.logger.info(f"Using cached price data for {coin}")
            return cached_data

        try:
            # Try full API fetch first and extract price data
            full_data = await self.fetch_data(coin)
            
            if "error" in full_data:
                self.logger.error(f"Error in fetch_price_data via full fetch: {full_data['error']}")
                return {"error": full_data["error"]}
            
            # Extract only price-related data
            price_data = {
                "current_price": full_data.get("current_price", 0),
                "price_change_percentage_24h": full_data.get("price_change_percentage_24h", 0),
                "volume_24h": full_data.get("volume_24h", 0),
                "24h_volume": full_data.get("24h_volume", 0)
            }
            
            # Cache the result
            cache_manager.save(price_data, "coinmarketcap", "price", coin_key)
            
            return price_data
            
        except Exception as e:
            self.logger.error(f"Error in fetch_price_data: {str(e)}")
            return {"error": f"Failed to fetch price data: {str(e)}"}

    async def fetch_historical_data(self, coin: str, days: int = 30) -> dict:
        """Fetch historical price data from CoinMarketCap for a given coin."""
        self.logger.info(f"Fetching CoinMarketCap historical data for {coin}, days={days}")
        
        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        self.project_name = coin  # Set for _normalize_project_name use

        # Use days in cache key to allow different time ranges
        cache_key = f"{coin.lower()}_days_{days}"
        cached_data = cache_manager.load("coinmarketcap", "historical", cache_key)
        if cached_data:
            self.logger.info(f"Using cached historical data for {coin} ({days} days)")
            return cached_data

        try:
            # Normalize input to symbol
            symbol = self._normalize_project_name()
            
            # Get coin ID
            api_key = os.getenv("COINMARKETCAP_API_KEY", "")
            if not api_key:
                self.logger.error("CoinMarketCap API key not found in environment")
                return {"error": "API key missing"}
                
            cmc_id = await self._find_cmc_id(symbol, api_key)
            if not cmc_id:
                self.logger.error(f"No valid CMC ID found for symbol {symbol}")
                return {"error": f"No valid CMC ID found for {symbol}"}

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Format dates for API
            start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
            end_str = end_date.strftime("%Y-%m-%dT23:59:59.000Z")
            
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/historical"
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            params = {
                "id": cmc_id,
                "time_start": start_str,
                "time_end": end_str,
                "interval": "daily",
                "convert": "USD"
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"API error: {response.status}, {error_text}")
                        return {"error": f"API error: {response.status}"}
                    
                    data = await response.json()
            
            # Extract time series data
            if "data" not in data:
                self.logger.error(f"Unexpected API response format: {data}")
                return {"error": "Unexpected API response format"}
                
            quotes = data["data"].get("quotes", [])
            
            # Format into time series
            prices = []
            volumes = []
            timestamps = []
            
            for quote in quotes:
                timestamp = quote.get("timestamp")
                if not timestamp:
                    continue
                    
                quote_data = quote.get("quote", {}).get("USD", {})
                price = quote_data.get("price")
                volume = quote_data.get("volume_24h")
                
                if price is not None:
                    timestamps.append(timestamp)
                    prices.append(price)
                    volumes.append(volume if volume is not None else 0)
            
            result = {
                "timestamps": timestamps,
                "prices": prices,
                "volumes": volumes
            }
            
            # Cache the result
            cache_manager.save(result, "coinmarketcap", "historical", cache_key)
            self.logger.info(f"Cached historical data for {coin}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {str(e)}")
            return {"error": f"Failed to fetch historical data: {str(e)}"}

    async def search_coins(self, query: str, limit: int = 10) -> list:
        """Search for coins on CoinMarketCap by name or symbol."""
        self.logger.info(f"Searching CoinMarketCap for coins matching '{query}'")
        
        # Create a local cache manager
        cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Check cache first
        cache_key = f"{query.lower()}_limit_{limit}"
        cached_data = cache_manager.load("coinmarketcap", "search", cache_key)
        if cached_data:
            self.logger.info(f"Using cached search results for '{query}'")
            return cached_data

        api_key = os.getenv("COINMARKETCAP_API_KEY", "")
        if not api_key:
            self.logger.error("CoinMarketCap API key not found in environment")
            return [{"error": "API key missing"}]

        try:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"API error: {response.status}, {error_text}")
                        return [{"error": f"API error: {response.status}"}]
                    
                    data = await response.json()
            
            # Filter results by query
            results = []
            query_lower = query.lower()
            
            if "data" in data:
                for coin in data["data"]:
                    name = coin.get("name", "").lower()
                    symbol = coin.get("symbol", "").lower()
                    
                    # Prioritize exact matches and then partial matches
                    if name == query_lower or symbol == query_lower:
                        score = 100
                    elif query_lower in name or query_lower in symbol:
                        score = 50
                    else:
                        continue  # No match
                        
                    results.append({
                        "id": coin.get("id"),
                        "name": coin.get("name"),
                        "symbol": coin.get("symbol"),
                        "slug": coin.get("slug"),
                        "rank": coin.get("rank", 9999),
                        "score": score
                    })
            
            # Sort by score (desc) and rank (asc)
            results.sort(key=lambda x: (-x.get("score", 0), x.get("rank", 9999)))
            
            # Limit results
            limited_results = results[:limit]
            
            # Cache the result
            cache_manager.save(limited_results, "coinmarketcap", "search", cache_key)
            self.logger.info(f"Cached search results for '{query}'")
            
            return limited_results
            
        except Exception as e:
            self.logger.error(f"Error searching coins: {str(e)}")
            return [{"error": f"Failed to search coins: {str(e)}"}]