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

class DeFiLlamaAPI(DataModule):
    """DeFi Llama API retriever for cryptocurrency TVL and protocol data"""
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        cache_path = f"cache/{self.project_name}_DeFiLlamaAPI.json"
        
        # Check if DeFiLlama API is enabled
        api_enabled = os.getenv("DEFILLAMA_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"DeFiLlama API is disabled by environment settings, returning cache or empty data")
            # Try to use cached data if available, otherwise return empty result
            if use_cache and os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        data = json.load(f)
                        self.logger.info(f"Using cached DeFiLlama data for {self.project_name} as API is disabled")
                        return data
                except Exception as e:
                    self.logger.warning(f"Error reading cached DeFiLlama data: {str(e)}")
            return {"defillama_disabled": "DeFiLlama API disabled by configuration"}
        
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
            base_url = "https://api.llama.fi"
            protocols_url = f"{base_url}/protocols"
            protocols_response = requests.get(protocols_url, timeout=15)
            if protocols_response.status_code != 200:
                self.logger.warning(f"DeFi Llama protocols API error: Status code {protocols_response.status_code}")
                return {"error": f"API error: {protocols_response.status_code}"}
                
            protocols = protocols_response.json()
            protocol_slug = None
            protocol_data = None
            special_cases = {"BTC": "bitcoin-staking", "ETH": "ethereum-staking", "ONDO": "ondo-finance", "MKR": "makerdao", "UNI": "uniswap"}
            
            if self.token_symbol in special_cases:
                protocol_slug = special_cases[self.token_symbol]
                self.logger.info(f"Using known slug for {self.token_symbol}: {protocol_slug}")
            
            if not protocol_slug:
                search_terms = [self.coin_id.lower(), self.project_name.lower(), self.token_symbol.lower(), f"{self.project_name.lower()}-finance"]
                for protocol in protocols:
                    protocol_name = protocol.get("name", "").lower()
                    protocol_symbol = protocol.get("symbol", "").lower()
                    slug = protocol.get("slug", "").lower()
                    if (protocol_symbol == self.token_symbol.lower() or 
                        self.project_name.lower() in protocol_name or
                        any(term in slug for term in search_terms)):
                        protocol_slug = protocol.get("slug")
                        protocol_data = protocol
                        self.logger.info(f"Found protocol: {protocol.get('name')} with slug {protocol_slug}")
                        break
            
            if protocol_slug:
                if protocol_data and "tvl" in protocol_data:
                    result["tvl"] = protocol_data.get("tvl", 0)
                protocol_url = f"{base_url}/protocol/{protocol_slug}"
                protocol_response = requests.get(protocol_url, timeout=15)
                if protocol_response.status_code == 200:
                    data = protocol_response.json()
                    if "tvl" not in result:
                        if isinstance(data.get("tvl"), (int, float)):
                            result["tvl"] = data.get("tvl", 0)
                        elif "currentChainTvls" in data:
                            chain_tvls = data.get("currentChainTvls", {})
                            total_tvl = sum(v for k, v in chain_tvls.items() if isinstance(v, (int, float)))
                            if total_tvl > 0:
                                result["tvl"] = total_tvl
                    tvl_history = []
                    tvl_data = None
                    if isinstance(data.get("tvl"), list):
                        tvl_data = data.get("tvl")
                    elif isinstance(data.get("chainTvls"), dict) and "all" in data.get("chainTvls", {}):
                        tvl_data = data.get("chainTvls", {}).get("all", {}).get("tvl", [])
                    if tvl_data:
                        for item in tvl_data:
                            if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                                timestamp = int(item["date"]) * 1000
                                tvl_history.append([timestamp, item["totalLiquidityUSD"]])
                    if tvl_history:
                        result["tvl_history"] = tvl_history
                        self.logger.info(f"Retrieved TVL history with {len(tvl_history)} data points")
                        if "tvl" not in result or result["tvl"] == 0:
                            sorted_history = sorted(tvl_history, key=lambda x: x[0])
                            if sorted_history:
                                result["tvl"] = sorted_history[-1][1]
                                self.logger.info(f"Extracted TVL from history: ${result['tvl']:.0f}")
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