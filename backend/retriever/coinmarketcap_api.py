from typing import Dict, Any, Optional
import requests
import logging
import os
import json
import time
from datetime import datetime
import re
from abc import ABC, abstractmethod
from backend.retriever.coingecko_api import DataModule

class CoinMarketCapAPI(DataModule):
    """CoinMarketCap API retriever for cryptocurrency data"""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_CoinMarketCapAPI.json"
        
        # Check if CoinMarketCap API is enabled
        api_enabled = os.getenv("COINMARKETCAP_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"CoinMarketCap API is disabled by environment settings, returning cache or empty data")
            # Try to use cached data if available, otherwise return empty result
            if use_cache and os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        self.logger.info(f"Using cached CoinMarketCap data for {self.project_name} as API is disabled")
                        return data
                except Exception as e:
                    self.logger.warning(f"Error reading cached CoinMarketCap data: {str(e)}")
            return {"coinmarketcap_disabled": "CoinMarketCap API disabled by configuration"}
        
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
        
        search_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        search_params = {"symbol": self._normalize_project_name()}
        
        result = {}
        try:
            search_response = requests.get(search_url, headers=headers, params=search_params, timeout=15)
            search_data = search_response.json()
            
            if search_response.status_code != 200 or "data" not in search_data or not search_data["data"]:
                self.logger.error(f"Failed to find CMC ID for {self._normalize_project_name()}")
                return {"error": f"Symbol not found in CoinMarketCap: {self._normalize_project_name()}"}
            
            well_known = {"BTC": 1, "ETH": 1027, "SOL": 5426, "BNB": 1839}
            cmc_id = None
            if self._normalize_project_name() in well_known:
                for coin in search_data["data"]:
                    if coin.get("id") == well_known[self._normalize_project_name()]:
                        cmc_id = coin.get("id")
                        self.logger.info(f"Found well-known coin {self._normalize_project_name()} with ID {cmc_id}")
                        break
            
            if not cmc_id:
                best_match = None
                lowest_rank = float('inf')
                for coin in search_data["data"]:
                    if coin.get("is_active", 0) != 1:
                        continue
                    if coin.get("symbol") == self._normalize_project_name():
                        rank = coin.get("rank", 9999)
                        if rank < lowest_rank:
                            best_match = coin
                            lowest_rank = rank
                if not best_match and search_data["data"]:
                    best_match = search_data["data"][0]
                    self.logger.warning(f"No active coin found for {self._normalize_project_name()}, using first result")
                if not best_match:
                    self.logger.error(f"No valid coin found for {self._normalize_project_name()}")
                    return {"error": f"No valid coin in CoinMarketCap for: {self._normalize_project_name()}"}
                cmc_id = best_match.get("id")
            
            self.logger.info(f"Found CMC ID for {self._normalize_project_name()}: {cmc_id}")
            
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
                result["24h_volume"] = quote.get("volume_24h", 0)
                result["percent_change_24h"] = quote.get("percent_change_24h", 0)
                result["price_change_percentage_24h"] = quote.get("percent_change_24h", 0)
                result["circulating_supply"] = coin_data.get("circulating_supply", 0)
                result["total_supply"] = coin_data.get("total_supply", 0)
                result["max_supply"] = coin_data.get("max_supply", 0)
                result["cmc_rank"] = coin_data.get("cmc_rank", 0)
                result["cmc_id"] = cmc_id
                
                for key in ["last_updated", "date_added", "slug", "num_market_pairs"]:
                    if key in coin_data:
                        result[key] = coin_data[key]
                
                # Get market dominance and other metrics if available
                metrics_url = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
                try:
                    metrics_response = requests.get(metrics_url, headers=headers, timeout=15)
                    metrics_data = metrics_response.json()
                    
                    if metrics_response.status_code == 200 and "data" in metrics_data:
                        global_data = metrics_data.get("data", {})
                        if "btc_dominance" in global_data:
                            result["btc_dominance"] = global_data["btc_dominance"]
                        if "eth_dominance" in global_data:
                            result["eth_dominance"] = global_data["eth_dominance"]
                        if "total_market_cap" in global_data:
                            result["total_market_cap"] = global_data["total_market_cap"]
                except Exception as e:
                    self.logger.error(f"Error fetching global metrics: {str(e)}")
                
                try:
                    listing_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
                    listing_params = {"limit": 20, "convert": "USD", "sort": "market_cap", "sort_dir": "desc"}
                    listing_response = requests.get(listing_url, headers=headers, params=listing_params, timeout=15)
                    if listing_response.status_code == 200:
                        listing_data = listing_response.json()
                        competitors = {}
                        count = 0
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

    def _normalize_project_name(self) -> str:
        """
        Normalize project name to a likely cryptocurrency symbol.
        
        Returns:
            A string representing the best guess at the crypto symbol
        """
        # Handle known cryptocurrencies
        known_projects = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "solana": "SOL",
            "cardano": "ADA",
            "binance": "BNB",
            "polygon": "MATIC",
            "avalanche": "AVAX",
            "polkadot": "DOT",
            "chainlink": "LINK",
            "uniswap": "UNI",
            "aave": "AAVE",
            "maker": "MKR",
            "compound": "COMP",
            "shiba inu": "SHIB",
            "dogecoin": "DOGE"
        }
        
        # If project name is directly known, return the symbol
        project_lower = self.project_name.lower()
        if project_lower in known_projects:
            self.logger.info(f"Using known symbol {known_projects[project_lower]} for {self.project_name}")
            return known_projects[project_lower]
        
        # If project name already looks like a symbol (all uppercase), return it
        if self.project_name.isupper() and len(self.project_name) <= 10:
            return self.project_name
        
        # Try to extract likely symbol
        possible_symbol = self.project_name.strip().upper()
        
        # Remove common suffixes
        for suffix in [" TOKEN", " COIN", " PROTOCOL", " NETWORK", " FINANCE", " CHAIN"]:
            if possible_symbol.endswith(suffix):
                possible_symbol = possible_symbol.replace(suffix, "")
                break

        # If still too long, just use the first word
        if len(possible_symbol) > 10 and " " in possible_symbol:
            possible_symbol = possible_symbol.split()[0]
        
        # If still too long, use first few characters
        if len(possible_symbol) > 10:
            possible_symbol = possible_symbol[:5]
            
        self.logger.info(f"Normalized project name {self.project_name} to symbol {possible_symbol}")
        return possible_symbol 