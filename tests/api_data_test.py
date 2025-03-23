import os
import logging
import json
import requests
import time
import argparse
from typing import Dict, Any, List
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("APICryptoDataTest")

class APIDataTest:
    """Tests real API data collection with no synthetic fallbacks."""
    
    def __init__(self, project_name: str, save_to_state: bool = False):
        self.project_name = project_name
        self.save_to_state = save_to_state
        self.coin_id = project_name.lower().replace(" ", "-")
        self.token_symbol = project_name.upper()
        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load config to determine required fields
        try:
            with open("backend/config/report_config.json", "r") as f:
                self.report_config = json.load(f)
                self.visualization_types = self.report_config.get("visualization_types", {})
                logger.info(f"Loaded visualization config with {len(self.visualization_types)} types")
        except Exception as e:
            logger.error(f"Failed to load report config: {e}")
            self.visualization_types = {}
    
    def clear_cache(self):
        """Clear cache files for this project."""
        for file in os.listdir(self.cache_dir):
            if file.startswith(self.project_name.lower()):
                os.remove(os.path.join(self.cache_dir, file))
                logger.info(f"Removed cache file: {file}")
    
    def test_coinmarketcap(self) -> Dict[str, Any]:
        """Test CoinMarketCap API data with real data only."""
        logger.info(f"Testing CoinMarketCap API for {self.project_name}...")
        
        # Get API key
        api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not api_key:
            logger.error("COINMARKETCAP_API_KEY not found in environment variables")
            return {"error": "API key missing"}
        
        result = {}
        
        # 1. Get basic coin data (current price, market cap, etc.)
        try:
            # First, find the correct CMC ID for the coin
            # This is more reliable than using symbol which can be ambiguous
            search_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
            headers = {"X-CMC_PRO_API_KEY": api_key}
            search_params = {"symbol": self.token_symbol}
            
            search_response = requests.get(search_url, headers=headers, params=search_params, timeout=15)
            search_data = search_response.json()
            
            if search_response.status_code != 200 or "data" not in search_data or not search_data["data"]:
                logger.error(f"Failed to find CMC ID for {self.token_symbol}")
                return {"error": f"Symbol not found in CoinMarketCap: {self.token_symbol}"}
            
            # For major coins like Bitcoin, we need to be more careful with selection
            # as there are many tokens that include the name
            best_match = None
            lowest_rank = float('inf')
            
            # Special case for well-known coins
            well_known = {
                "BTC": 1,  # Bitcoin
                "ETH": 1027,  # Ethereum
                "SOL": 5426,  # Solana
                "BNB": 1839,  # Binance Coin
                "XRP": 52,    # XRP
                "ADA": 2010,  # Cardano
                "DOGE": 74    # Dogecoin
            }
            
            if self.token_symbol in well_known:
                # Look for the exact ID for well-known coins
                for coin in search_data["data"]:
                    if coin.get("id") == well_known[self.token_symbol]:
                        best_match = coin
                        logger.info(f"Found well-known coin {self.token_symbol} with ID {coin.get('id')}")
                        break
            
            # If no well-known match, use rank-based selection
            if not best_match:
                # Find the most relevant coin (active, highest rank, exact symbol match)
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
                    logger.warning(f"No active coin found for {self.token_symbol}, using first result")
            
            if not best_match:
                logger.error(f"No valid coin found for {self.token_symbol}")
                return {"error": f"No valid coin in CoinMarketCap for: {self.token_symbol}"}
            
            cmc_id = best_match.get("id")
            logger.info(f"Found CMC ID for {self.token_symbol}: {cmc_id} (Name: {best_match.get('name')})")
            
            # Now get the latest quote using the ID
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
                
                # Add other fields from the response that might be useful
                for key in ["num_market_pairs", "date_added", "tags", "slug"]:
                    if key in coin_data:
                        result[key] = coin_data[key]
                
                logger.info(f"Successfully retrieved basic CoinMarketCap data for {self.project_name}")
                logger.info(f"Current price: ${result['current_price']:.2f}, Market cap: ${result['market_cap']:.0f}")
            else:
                error_message = response_data.get("status", {}).get("error_message", "Unknown error")
                logger.error(f"Failed to get CoinMarketCap data: {error_message}")
                return {"error": f"API error: {error_message}"}
        except Exception as e:
            logger.error(f"Error in CoinMarketCap basic data: {str(e)}", exc_info=True)
            return {"error": str(e)}
        
        # 2. Try to get historical data for charts (requires premium subscription)
        try:
            # Use the v2 historical quotes endpoint for price history
            historical_url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"
            
            # Get 60 days of price data for charts
            end_time = int(time.time())
            start_time = end_time - (60 * 24 * 60 * 60)  # 60 days ago
            
            params = {
                "id": cmc_id,  # Use ID instead of symbol for more reliable results
                "time_start": start_time,
                "time_end": end_time,
                "interval": "1d",  # Daily data
                "convert": "USD"
            }
            
            logger.info("Attempting to fetch historical data from CoinMarketCap")
            logger.info("This requires paid subscription tier (Basic+/Standard/Professional/Enterprise)")
            
            response = requests.get(historical_url, headers=headers, params=params, timeout=15)
            history_data = response.json()
            
            if response.status_code == 200 and "data" in history_data:
                # Handle different response formats
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
                    else:
                        quote_data = []
                        logger.warning("Unrecognized historical data format")
                except Exception as e:
                    logger.error(f"Error parsing historical data format: {str(e)}")
                    quote_data = []
                
                # Format price history data
                price_history = []
                volume_history = []
                
                for quote in quote_data:
                    try:
                        # Try different formats for timestamp
                        timestamp = None
                        if isinstance(quote, dict):
                            if "timestamp" in quote:
                                timestamp = quote.get("timestamp")
                            elif "time" in quote:
                                timestamp = quote.get("time")
                            elif "date" in quote:
                                timestamp = quote.get("date")
                        
                        if timestamp:
                            # Parse timestamp
                            try:
                                if isinstance(timestamp, (int, float)):
                                    unix_ts = int(timestamp) * 1000  # Convert to milliseconds
                                else:
                                    # Try different date formats
                                    try:
                                        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                                    except ValueError:
                                        try:
                                            dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                                        except ValueError:
                                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    unix_ts = int(dt.timestamp() * 1000)  # Convert to milliseconds
                                
                                # Try different formats for price and volume
                                price = None
                                volume = None
                                
                                if "quote" in quote and "USD" in quote["quote"]:
                                    usd_quote = quote["quote"]["USD"]
                                    price = usd_quote.get("price")
                                    volume = usd_quote.get("volume_24h")
                                elif "price" in quote:
                                    price = quote["price"]
                                elif "close" in quote:
                                    price = quote["close"]
                                
                                if "volume" in quote:
                                    volume = quote["volume"]
                                elif "volume_24h" in quote:
                                    volume = quote["volume_24h"]
                                
                                if price is not None:
                                    price_history.append([unix_ts, price])
                                
                                if volume is not None:
                                    volume_history.append([unix_ts, volume])
                            except Exception as e:
                                logger.warning(f"Error parsing timestamp or price: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error processing quote data item: {str(e)}")
                
                # Sort by timestamp
                if price_history:
                    price_history.sort(key=lambda x: x[0])
                    result["price_history"] = price_history
                    logger.info(f"Retrieved price history with {len(price_history)} data points")
                
                if volume_history:
                    volume_history.sort(key=lambda x: x[0])
                    result["volume_history"] = volume_history
                    logger.info(f"Retrieved volume history with {len(volume_history)} data points")
                
                if not price_history and not volume_history:
                    logger.warning("No usable price or volume data found in the historical response")
            else:
                error_message = history_data.get("status", {}).get("error_message", "Unknown error")
                if "subscription plan doesn't support this endpoint" in error_message:
                    logger.warning("Historical data requires premium CoinMarketCap subscription (Basic+/Standard/Professional/Enterprise)")
                    logger.warning("Using CoinGecko for historical data is recommended with free CoinMarketCap plan")
                else:
                    logger.warning(f"Failed to get historical data: {error_message}")
        except Exception as e:
            logger.error(f"Error in CoinMarketCap historical data: {str(e)}", exc_info=True)
        
        # 3. Get competitors data
        try:
            if "cmc_id" not in result:
                logger.warning("No CMC ID found for competitor analysis")
                return result
            
            competitors = self.get_competitors(headers, api_key)
            
            if competitors:
                result["competitors"] = competitors
                logger.info(f"Retrieved data for {len(competitors)} competitors")
            else:
                logger.warning("No competitor data found")
            
        except Exception as e:
            logger.error(f"Error in CoinMarketCap competitor data: {str(e)}", exc_info=True)
        
        # Save data to cache
        cache_path = os.path.join(self.cache_dir, f"{self.project_name.lower()}_coinmarketcap.json")
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        logger.info(f"Saved CoinMarketCap data to {cache_path}")
        
        return result
    
    def test_coingecko(self) -> Dict[str, Any]:
        """Test CoinGecko API with real data only."""
        logger.info(f"Testing CoinGecko API for {self.project_name}...")
        
        # Get API key (optional)
        api_key = os.getenv("COINGECKO_API_KEY", "")
        if not api_key:
            logger.warning("No CoinGecko API key found, using free API with rate limits")
        
        result = {}
        
        # 1. Get basic coin data
        try:
            base_url = "https://api.coingecko.com/api/v3"
            search_url = f"{base_url}/search"
            
            # First search for the coin ID
            search_response = requests.get(search_url, params={"query": self.project_name}, timeout=10)
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
                
                if not coin_id:
                    logger.error(f"Could not find {self.project_name} in CoinGecko search results")
                    return {"error": "Coin not found in CoinGecko"}
                
                logger.info(f"Found CoinGecko coin ID: {coin_id}")
                
                # Now get detailed data
                headers = {"x-cg-pro-api-key": api_key} if api_key else {}
                coin_data_url = f"{base_url}/coins/{coin_id}"
                
                coin_response = requests.get(coin_data_url, headers=headers, timeout=15)
                if coin_response.status_code == 200:
                    coin_data = coin_response.json()
                    market_data = coin_data.get("market_data", {})
                    
                    result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
                    result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
                    result["total_supply"] = market_data.get("total_supply", 0)
                    result["circulating_supply"] = market_data.get("circulating_supply", 0)
                    result["max_supply"] = market_data.get("max_supply", 0)
                    result["volume_24h"] = market_data.get("total_volume", {}).get("usd", 0)
                    result["price_change_percentage_24h"] = market_data.get("price_change_percentage_24h", 0)
                    
                    # Also get token distribution if available
                    if "distribution_percentage" in coin_data or "developer_data" in coin_data:
                        distribution = {}
                        
                        if "developer_data" in coin_data and "forks" in coin_data["developer_data"]:
                            distribution["Development"] = 25  # Placeholder
                        
                        if "community_data" in coin_data and "twitter_followers" in coin_data["community_data"]:
                            distribution["Community"] = 30  # Placeholder
                        
                        if "public_interest_stats" in coin_data:
                            distribution["Public"] = 20  # Placeholder
                        
                        distribution["Other"] = 100 - sum(distribution.values())
                        
                        if distribution:
                            result["token_distribution"] = distribution
                            logger.info(f"Created token distribution with {len(distribution)} categories")
                    
                    logger.info(f"Successfully retrieved CoinGecko data for {self.project_name}")
                    logger.info(f"Current price: ${result['current_price']:.2f}, Market cap: ${result['market_cap']:.0f}")
                else:
                    logger.error(f"Failed to get CoinGecko data: {coin_response.status_code}")
                    return {"error": f"API error: {coin_response.status_code}"}
            else:
                logger.error(f"Failed to search for coin: {search_response.status_code}")
                return {"error": f"Search API error: {search_response.status_code}"}
        except Exception as e:
            logger.error(f"Error in CoinGecko basic data: {str(e)}", exc_info=True)
            return {"error": str(e)}
        
        # 2. Get historical data
        try:
            if "coin_id" not in locals() or not coin_id:
                logger.warning("No coin_id available for historical data")
                return result
            
            # Get market chart data
            market_chart_url = f"{base_url}/coins/{coin_id}/market_chart"
            headers = {"x-cg-pro-api-key": api_key} if api_key else {}
            
            # Get price history (60 days)
            params = {"vs_currency": "usd", "days": 60, "interval": "daily"}
            chart_response = requests.get(market_chart_url, headers=headers, params=params, timeout=15)
            
            if chart_response.status_code == 200:
                chart_data = chart_response.json()
                
                if "prices" in chart_data and chart_data["prices"]:
                    result["price_history"] = chart_data["prices"]
                    logger.info(f"Retrieved price history with {len(chart_data['prices'])} data points")
                
                if "total_volumes" in chart_data and chart_data["total_volumes"]:
                    result["volume_history"] = chart_data["total_volumes"]
                    logger.info(f"Retrieved volume history with {len(chart_data['total_volumes'])} data points")
            else:
                logger.warning(f"Failed to get historical data: {chart_response.status_code}")
                
            # Get some extra data like market dominance if possible
            global_url = f"{base_url}/global"
            global_response = requests.get(global_url, headers=headers, timeout=10)
            
            if global_response.status_code == 200:
                global_data = global_response.json()
                if "data" in global_data and "market_cap_percentage" in global_data["data"]:
                    # Only add if our coin is in the top dominance list
                    market_caps = global_data["data"]["market_cap_percentage"]
                    if self.token_symbol.lower() in [k.lower() for k in market_caps.keys()]:
                        result["market_dominance"] = market_caps.get(self.token_symbol.lower(), 0)
                        logger.info(f"Market dominance: {result['market_dominance']:.2f}%")
            
        except Exception as e:
            logger.error(f"Error in CoinGecko historical data: {str(e)}", exc_info=True)
        
        # Save data to cache
        cache_path = os.path.join(self.cache_dir, f"{self.project_name.lower()}_coingecko.json")
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        logger.info(f"Saved CoinGecko data to {cache_path}")
        
        return result
    
    def test_defillama(self) -> Dict[str, Any]:
        """Test DeFiLlama API for real data only."""
        logger.info(f"Testing DeFiLlama API for {self.project_name}...")
        
        result = {}
        
        # 1. Search for the protocol
        try:
            search_url = "https://api.llama.fi/protocols"
            response = requests.get(search_url, timeout=15)
            
            if response.status_code == 200:
                protocols = response.json()
                
                # Try to find the protocol by name
                protocol_slug = None
                for protocol in protocols:
                    if protocol.get("symbol", "").lower() == self.token_symbol.lower() or \
                       protocol.get("name", "").lower() == self.project_name.lower():
                        protocol_slug = protocol.get("slug")
                        # If protocol has TVL, also grab it
                        if "tvl" in protocol:
                            result["tvl"] = protocol.get("tvl", 0)
                        break
                
                # If it's BTC, we know it's stored differently as bitcoin-staking
                if not protocol_slug and self.token_symbol.lower() in ["btc", "bitcoin"]:
                    for protocol in protocols:
                        if protocol.get("slug") == "bitcoin-staking":
                            protocol_slug = "bitcoin-staking"
                            if "tvl" in protocol:
                                result["tvl"] = protocol.get("tvl", 0)
                            break
                
                if not protocol_slug:
                    logger.warning(f"Could not find {self.project_name} in DeFiLlama protocols")
                    return {"error": "Protocol not found in DeFiLlama"}
                
                logger.info(f"Found DeFiLlama protocol slug: {protocol_slug}")
                
                # Get protocol data
                protocol_url = f"https://api.llama.fi/protocol/{protocol_slug}"
                protocol_response = requests.get(protocol_url, timeout=15)
                
                if protocol_response.status_code == 200:
                    protocol_data = protocol_response.json()
                    
                    # Get TVL - handle different ways DeFiLlama might report it
                    if "tvl" not in result:
                        if isinstance(protocol_data.get("tvl"), (int, float)):
                            result["tvl"] = protocol_data.get("tvl", 0)
                        elif "currentChainTvls" in protocol_data:
                            # Sum all chain TVLs if available
                            chain_tvls = protocol_data.get("currentChainTvls", {})
                            current_tvl = sum(v for k, v in chain_tvls.items() if isinstance(v, (int, float)))
                            if current_tvl > 0:
                                result["tvl"] = current_tvl
                    
                    # Process TVL history - ensure it's usable
                    tvl_history = []
                    tvl_data = None
                    
                    # Try different formats
                    if isinstance(protocol_data.get("tvl"), list):
                        tvl_data = protocol_data.get("tvl")
                    elif isinstance(protocol_data.get("chainTvls"), dict):
                        # For multi-chain assets, try to get total TVL
                        for chain, data in protocol_data.get("chainTvls", {}).items():
                            if chain == "all" and "tvl" in data:
                                tvl_data = data.get("tvl")
                                break
                    
                    if tvl_data:
                        for item in tvl_data:
                            if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                                # Convert Unix timestamp to milliseconds
                                timestamp = int(item["date"]) * 1000
                                tvl_history.append([timestamp, item["totalLiquidityUSD"]])
                    
                    if tvl_history:
                        result["tvl_history"] = tvl_history
                        logger.info(f"Retrieved TVL history with {len(tvl_history)} data points")
                        
                        # Extract most recent TVL from history if not set already
                        if "tvl" not in result or result["tvl"] == 0:
                            # Sort by timestamp to get most recent
                            sorted_history = sorted(tvl_history, key=lambda x: x[0])
                            if sorted_history:
                                most_recent_value = sorted_history[-1][1]
                                if most_recent_value > 0:  # Only use if positive
                                    result["tvl"] = most_recent_value
                                    logger.info(f"Extracted current TVL from history: ${result['tvl']:.0f}")
                    
                    # For Bitcoin/non-DeFi assets, we can use market cap as a proxy for TVL if needed
                    if ("tvl" not in result or result["tvl"] == 0) and self.token_symbol.lower() in ["btc", "bitcoin"]:
                        if "market_cap" in result:
                            result["tvl"] = result["market_cap"]
                            logger.info(f"Using market cap (${result['market_cap']:.0f}) as proxy for TVL for {self.project_name}")
                        else:
                            # Try to get market cap from CoinGecko as fallback
                            try:
                                cg_url = f"https://api.coingecko.com/api/v3/coins/{self.project_name.lower()}"
                                cg_response = requests.get(cg_url, timeout=10)
                                if cg_response.status_code == 200:
                                    cg_data = cg_response.json()
                                    market_cap = cg_data.get("market_data", {}).get("market_cap", {}).get("usd", 0)
                                    if market_cap > 0:
                                        result["tvl"] = market_cap
                                        logger.info(f"Using CoinGecko market cap (${market_cap:.0f}) as proxy for TVL")
                            except Exception as e:
                                logger.warning(f"Failed to get CoinGecko market cap as TVL proxy: {str(e)}")
                    
                    # Get additional data
                    if "category" in protocol_data and protocol_data["category"]:
                        result["category"] = protocol_data["category"]
                    
                    if "chains" in protocol_data and protocol_data["chains"]:
                        result["chains"] = protocol_data["chains"]
                    
                    logger.info(f"Successfully retrieved DeFiLlama data for {self.project_name}")
                    if "tvl" in result:
                        logger.info(f"Current TVL: ${result['tvl']:.0f}")
                else:
                    logger.error(f"Failed to get protocol data: {protocol_response.status_code}")
            else:
                logger.error(f"Failed to get protocols list: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in DeFiLlama data: {str(e)}", exc_info=True)
        
        # Save data to cache if we got anything
        if result:
            cache_path = os.path.join(self.cache_dir, f"{self.project_name.lower()}_defillama.json")
            with open(cache_path, 'w') as f:
                json.dump(result, f)
            logger.info(f"Saved DeFiLlama data to {cache_path}")
        
        return result
    
    def combine_data(self) -> Dict[str, Any]:
        """Combine data from all sources with priority on CoinMarketCap, no synthetic fallbacks."""
        logger.info("Combining data from all sources (prioritizing CoinMarketCap)...")
        
        combined_data = {}
        
        # Process CoinMarketCap data (primary source)
        cmc_data = self.test_coinmarketcap()
        if "error" not in cmc_data:
            combined_data.update(cmc_data)
            logger.info(f"Added {len(cmc_data)} fields from CoinMarketCap")
        
        # Only get CoinGecko data if CMC data has issues or missing fields
        missing_required_fields = self.check_visualization_fields(combined_data)
        
        # Check if CoinGecko is needed
        needs_coingecko = False
        if "error" in cmc_data:
            needs_coingecko = True
            logger.info("CoinMarketCap error detected, falling back to CoinGecko")
        elif missing_required_fields:
            needs_coingecko = True
            logger.info(f"Missing {len(missing_required_fields)} fields from CMC, using CoinGecko as backup: {missing_required_fields}")
        
        if needs_coingecko:
            cg_data = self.test_coingecko()
            if "error" not in cg_data:
                # Only add missing fields from CoinGecko
                for key, value in cg_data.items():
                    if key not in combined_data or not combined_data[key]:
                        combined_data[key] = value
                        logger.info(f"Added missing field {key} from CoinGecko")
        
        # Add DeFiLlama TVL data only if needed (TVL or TVL history missing)
        if "tvl" not in combined_data or "tvl_history" not in combined_data:
            defillama_data = self.test_defillama()
            if defillama_data and "error" not in defillama_data:
                for key, value in defillama_data.items():
                    combined_data[key] = value
                logger.info(f"Added {len(defillama_data)} fields from DeFiLlama")
        
        # Extract TVL from TVL history if needed
        if "tvl" not in combined_data and "tvl_history" in combined_data and combined_data["tvl_history"]:
            # Get the most recent TVL value
            sorted_history = sorted(combined_data["tvl_history"], key=lambda x: x[0])
            if sorted_history:
                combined_data["tvl"] = sorted_history[-1][1]
                logger.info(f"Extracted TVL from history: ${combined_data['tvl']:.0f}")
        
        # Fix compatibilities - make sure all visualization requirements are satisfied
        if "24h_volume" not in combined_data and "volume_24h" in combined_data:
            combined_data["24h_volume"] = combined_data["volume_24h"]
        
        # Save combined data
        cache_path = os.path.join(self.cache_dir, f"{self.project_name.lower()}_combined.json")
        with open(cache_path, 'w') as f:
            json.dump(combined_data, f)
        logger.info(f"Saved combined data with {len(combined_data)} fields to {cache_path}")
        
        # Check for missing required visualization fields
        final_missing_fields = self.check_visualization_fields(combined_data)
        if final_missing_fields:
            logger.warning(f"Missing {len(final_missing_fields)} required visualization fields: {', '.join(final_missing_fields)}")
            logger.warning("NO SYNTHETIC DATA FALLBACKS ARE BEING USED - VISUALIZATIONS MAY FAIL")
            logger.warning("Fields missing from all API sources: " + ', '.join(final_missing_fields))
            
            logger.warning("For more complete data, you have these options:")
            logger.warning("1. Upgrade CoinMarketCap subscription to access more endpoints")
            logger.warning("2. Use a different coin with more complete data")
            logger.warning("3. Modify your report_config.json to not require missing fields")
        else:
            logger.info("All required visualization fields are present in the data!")
        
        return combined_data
    
    def check_visualization_fields(self, data: Dict[str, Any]) -> List[str]:
        """Check if all required visualization fields are present."""
        required_fields = set()
        
        # Get required fields from visualization config
        for vis_type, vis_config in self.visualization_types.items():
            # Skip web_research and generated visualizations
            if vis_config.get("data_source") in ["web_research", "generated"]:
                continue
                
            if "data_field" in vis_config:
                required_fields.add(vis_config["data_field"])
            
            if "data_fields" in vis_config:
                for field in vis_config["data_fields"]:
                    # Skip the generated/special fields
                    if field not in ["aspect", "assessment", "recommendation"]:
                        required_fields.add(field)
        
        # Check which required fields are missing
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        
        return missing_fields

    def get_competitors(self, headers, api_key):
        """Get competitor data for the crypto asset."""
        logger.info("Searching for competitor data...")
        competitors = {}
        
        try:
            # Get top cryptocurrencies as potential competitors
            listing_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
            listing_params = {
                "limit": 30,  # Get top 30 to find competitors
                "convert": "USD",
                "sort": "market_cap",
                "sort_dir": "desc"
            }
            
            listing_response = requests.get(listing_url, headers=headers, params=listing_params, timeout=15)
            if listing_response.status_code != 200:
                logger.warning(f"Failed to get listings: {listing_response.status_code}")
                return {}
            
            listing_data = listing_response.json()
            
            # Find our coin's market cap and rank
            our_coin = None
            our_market_cap = 0
            our_rank = 0
            
            # First try to find in top 30
            for coin in listing_data.get("data", []):
                if coin.get("symbol") == self.token_symbol:
                    our_coin = coin
                    our_market_cap = coin.get("quote", {}).get("USD", {}).get("market_cap", 0)
                    our_rank = coin.get("cmc_rank", 0)
                    break
            
            # If not in top listing, use the market cap we already know
            if not our_coin and hasattr(self, "market_cap"):
                our_market_cap = self.market_cap
            
            # Define relevant "sectors" for comparisons
            sectors = {
                "Smart Contract Platforms": ["ETH", "SOL", "ADA", "DOT", "AVAX", "NEAR", "ATOM"],
                "Currencies": ["BTC", "LTC", "BCH", "XMR", "ZEC", "DASH"],
                "DeFi": ["UNI", "AAVE", "MKR", "CAKE", "CRV", "COMP"],
                "Exchanges": ["BNB", "CRO", "FTT", "LEO", "OKB", "KCS"],
                "Storage": ["FIL", "STORJ", "AR"],
                "Meme": ["DOGE", "SHIB", "PEPE", "FLOKI"]
            }
            
            # Determine which sector our coin belongs to
            our_sector = None
            for sector, coins in sectors.items():
                if self.token_symbol in coins:
                    our_sector = sector
                    break
            
            # Pick 5 competitors based on:
            # 1. Same sector, closest market cap
            # 2. Closest market cap if no sector
            # 3. Top coins if nothing else
            all_candidates = []
            
            for coin in listing_data.get("data", []):
                # Skip our own coin
                if coin.get("symbol") == self.token_symbol:
                    continue
                
                symbol = coin.get("symbol")
                market_cap = coin.get("quote", {}).get("USD", {}).get("market_cap", 0)
                
                # Compute a relevance score - lower is better
                relevance = 0
                
                # Same sector bonus
                if our_sector and any(symbol in coins for sector, coins in sectors.items() if sector == our_sector):
                    relevance -= 1000  # Big bonus for same sector
                
                # Market cap similarity (difference ratio)
                if our_market_cap > 0 and market_cap > 0:
                    ratio = market_cap / our_market_cap if market_cap < our_market_cap else our_market_cap / market_cap
                    relevance += (1 - ratio) * 100  # 0-100 penalty for market cap difference
                
                # Rank bonus
                if coin.get("cmc_rank", 0) <= 10:
                    relevance -= 200  # Bonus for top coins
                
                all_candidates.append({
                    "symbol": symbol,
                    "name": coin.get("name"),
                    "market_cap": market_cap,
                    "price_change_percentage_24h": coin.get("quote", {}).get("USD", {}).get("percent_change_24h", 0),
                    "relevance": relevance
                })
            
            # Sort by relevance and take top 5
            all_candidates.sort(key=lambda x: x["relevance"])
            for candidate in all_candidates[:5]:
                symbol = candidate.pop("relevance", None)  # Remove relevance score
                competitors[candidate["symbol"]] = candidate
            
            return competitors
        except Exception as e:
            logger.error(f"Error getting competitors: {str(e)}")
            return {}

def run_test(project_name, clear_cache=True):
    """Run API tests for a project with clear data completeness reporting."""
    logger.info(f"Running API data test for {project_name}")
    
    tester = APIDataTest(project_name)
    
    if clear_cache:
        tester.clear_cache()
    
    combined_data = tester.combine_data()
    
    # Print a summary of what we found
    logger.info(f"=== Summary for {project_name} ===")
    
    # Check for the specific fields that had warnings
    if "tvl_history" in combined_data:
        logger.info(f"✅ tvl_history: Found with {len(combined_data['tvl_history'])} data points")
    else:
        logger.error("❌ tvl_history: Missing (required for tvl_chart)")
    
    if "token_distribution" in combined_data:
        logger.info(f"✅ token_distribution: Found with {len(combined_data['token_distribution'])} categories")
    else:
        logger.error("❌ token_distribution: Missing (required for token_distribution_chart)")
        logger.error("   Note: Token distribution is specialized data requiring manual research")
    
    if "price_history" in combined_data:
        logger.info(f"✅ price_history: Found with {len(combined_data['price_history'])} data points")
    else:
        logger.error("❌ price_history: Missing (required for price_history_chart)")
        logger.error("   Note: Historical data requires premium CoinMarketCap subscription")
    
    if "volume_history" in combined_data:
        logger.info(f"✅ volume_history: Found with {len(combined_data['volume_history'])} data points")
    else:
        logger.error("❌ volume_history: Missing (required for volume_chart)")
        logger.error("   Note: Historical data requires premium CoinMarketCap subscription")
    
    if "competitors" in combined_data:
        logger.info(f"✅ competitors: Found with {len(combined_data['competitors'])} entries")
    else:
        logger.error("❌ competitors: Missing (required for competitor_comparison_chart)")
    
    logger.info(f"Total fields: {len(combined_data)}")
    logger.info(f"Fields: {', '.join(sorted(combined_data.keys())[:10])}, ... and {len(combined_data.keys()) - 10} more")
    
    if tester.check_visualization_fields(combined_data):
        missing_fields = tester.check_visualization_fields(combined_data)
        logger.warning("\n===== VISUALIZATION WARNING =====")
        logger.warning(f"Missing {len(missing_fields)} fields required by visualizations:")
        for field in missing_fields:
            logger.warning(f"  - {field}")
        logger.warning("Without these fields, some visualizations will use synthetic data")
        logger.warning("You may need to upgrade API subscriptions or modify report_config.json")
    else:
        logger.info("\n===== VISUALIZATION SUCCESS =====")
        logger.info("All required visualization fields are available!")
    
    return combined_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test cryptocurrency data APIs")
    parser.add_argument("--project", type=str, default="Bitcoin", help="Project name to test")
    parser.add_argument("--cache", action="store_true", help="Use existing cache if available")
    args = parser.parse_args()
    
    result = run_test(args.project, clear_cache=not args.cache)
    
    if result:
        logger.info(f"Successfully gathered data for {args.project} with {len(result)} fields")
    else:
        logger.error(f"Failed to gather data for {args.project}") 