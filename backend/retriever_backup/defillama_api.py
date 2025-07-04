from typing import Dict, Any, Optional
import requests
import logging
import os
import json
import time
from datetime import datetime
import re
from abc import ABC, abstractmethod
from backend.retriever_backup.coingecko_api import DataModule
from backend.utils.cache_utils import CacheManager

class DeFiLlamaAPI(DataModule):
    """DeFi Llama API retriever for cryptocurrency TVL and protocol data"""
    
    def __init__(self, project_name=None, token_symbol=None, coin_id=None):
        """Initialize DeFiLlamaAPI with project information."""
        # Require project_name for caching
        if not project_name or not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("project_name is required for DeFiLlamaAPI initialization")
            
        # Initialize with project info
        self.project_name = project_name.strip()
        self.token_symbol = token_symbol or project_name or ""
        self.coin_id = coin_id or project_name or ""
        
        # Set up logging
        self.logger = logging.getLogger("DeFiLlamaAPI")
        
        # For API calls that need a unified identifier
        if isinstance(self.token_symbol, str) and self.token_symbol:
            # Use token_symbol as primary identifier
            self.identifier = self.token_symbol.lower().strip()
        else:
            # Use project_name as fallback
            self.identifier = self.project_name.lower().strip()

        # Create cache manager
        self.cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
    
    def gather_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        # Check if DeFiLlama API is enabled
        api_enabled = os.getenv("DEFILLAMA_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
        if not api_enabled:
            self.logger.info(f"DeFiLlama API is disabled by environment settings, returning cache or empty data")
            # Try to use cached data if available, otherwise return empty result
            cached_data = self.cache_manager.load("defillama", "tvl", self.project_name.lower())
            if cached_data:
                self.logger.info(f"Using cached DeFiLlama data for {self.project_name} as API is disabled")
                return cached_data
            return {"defillama_disabled": "DeFiLlama API disabled by configuration"}
        
        # Check cache if use_cache is enabled
        if use_cache:
            cached_data = self.cache_manager.load("defillama", "tvl", self.project_name.lower())
            if cached_data and 'tvl' in cached_data:
                self.logger.info(f"Using cached DeFi Llama data for {self.project_name} (TVL: ${cached_data['tvl']})")
                return cached_data
        
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
            
            # Define special cases for known protocols - ensure ONDO is mapped correctly
            special_cases = {
                "BTC": "bitcoin-staking", 
                "ETH": "ethereum-staking", 
                "ONDO": "ondo-finance", 
                "ONDO FINANCE": "ondo-finance",
                "MKR": "makerdao", 
                "UNI": "uniswap"
            }
            
            # Check if this is a special case protocol - normalize case
            if self.token_symbol.upper() in special_cases:
                protocol_slug = special_cases[self.token_symbol.upper()]
                self.logger.info(f"Using known slug for {self.token_symbol}: {protocol_slug}")
            elif self.project_name.upper() in special_cases:
                protocol_slug = special_cases[self.project_name.upper()]
                self.logger.info(f"Using known slug for {self.project_name}: {protocol_slug}")
            
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
                # Cache the result
                cache_path = self.cache_manager.save(result, "defillama", "tvl", self.project_name.lower())
                if cache_path:
                    self.logger.info(f"Cached DeFi Llama data for {self.project_name} at {cache_path}")
                else:
                    self.logger.error(f"Failed to cache DeFi Llama data for {self.project_name}")
            else:
                self.logger.warning(f"No DeFi Llama data found for {self.project_name}")
                return {"error": "No data found in DeFiLlama"}
            return result
        except Exception as e:
            self.logger.error(f"Error in DeFi Llama module: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def fetch_tvl_data(self, protocol: str) -> Dict[str, Any]:
        """Fetch TVL data for a specific protocol."""
        try:
            self.logger.info(f"Fetching TVL data for {protocol} from DeFiLlama")
            
            # Set project name to ensure cache manager uses correct path
            self.project_name = protocol
            
            # Check cache first
            cached_data = self.cache_manager.load("defillama", "tvl", protocol.lower())
            if cached_data:
                self.logger.info(f"Using cached TVL data for {protocol}")
                return cached_data
            
            base_url = "https://api.llama.fi"
            protocols_url = f"{base_url}/protocols"
            
            # First get the protocol slug
            response = requests.get(protocols_url, timeout=15)
            if response.status_code != 200:
                error_msg = f"Failed to fetch protocols: {response.status_code}"
                self.logger.error(error_msg)
                error_result = {"error": error_msg}
                
                # Cache the error to prevent repeated failures
                self.cache_manager.save(error_result, "defillama", "data", protocol.lower())
                return error_result
                
            protocols = response.json()
            protocol_slug = None
            
            # Check for exact matches or special cases - normalize case
            special_cases = {
                "BTC": "bitcoin-staking", 
                "ETH": "ethereum-staking", 
                "ONDO": "ondo-finance",
                "ONDO FINANCE": "ondo-finance",
                "MKR": "makerdao", 
                "UNI": "uniswap"
            }
            
            if protocol.upper() in special_cases:
                protocol_slug = special_cases[protocol.upper()]
                self.logger.info(f"Using known slug for {protocol}: {protocol_slug}")
            
            # If no special case, search for the protocol
            if not protocol_slug:
                for p in protocols:
                    if p.get("name", "").lower() == protocol.lower() or \
                       p.get("symbol", "").lower() == protocol.lower() or \
                       p.get("slug", "").lower() == protocol.lower():
                        protocol_slug = p.get("slug")
                        self.logger.info(f"Found protocol slug: {protocol_slug}")
                        break
            
            if not protocol_slug:
                error_msg = f"Protocol {protocol} not found in DeFiLlama"
                self.logger.warning(error_msg)
                error_result = {"error": error_msg}
                
                # Cache the error to prevent repeated failures
                self.cache_manager.save(error_result, "defillama", "data", protocol.lower())
                return error_result
            
            # Now fetch the protocol data
            protocol_url = f"{base_url}/protocol/{protocol_slug}"
            protocol_response = requests.get(protocol_url, timeout=15)
            
            if protocol_response.status_code != 200:
                return {"error": f"Failed to fetch protocol data: {protocol_response.status_code}"}
                
            data = protocol_response.json()
            
            result = {
                "name": data.get("name", protocol),
                "slug": protocol_slug,
                "tvl": data.get("tvl", 0)
            }
            
            # Extract TVL history
            tvl_history = []
            tvl_data = None
            
            if isinstance(data.get("tvl"), list):
                tvl_data = data.get("tvl")
            elif isinstance(data.get("chainTvls"), dict) and "all" in data.get("chainTvls", {}):
                tvl_data = data.get("chainTvls", {}).get("all", {}).get("tvl", [])
                
            if tvl_data:
                timestamps = []
                values = []
                
                for item in tvl_data:
                    if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                        timestamp = int(item["date"]) * 1000  # Convert to milliseconds
                        timestamps.append(timestamp)
                        values.append(item["totalLiquidityUSD"])
                        tvl_history.append([timestamp, item["totalLiquidityUSD"]])
                
                result["tvl_history"] = tvl_history
                result["timestamps"] = timestamps
                result["values"] = values
                
                self.logger.info(f"Retrieved TVL history with {len(timestamps)} data points")
            
            # Add category and chains if available
            if "category" in data:
                result["category"] = data.get("category")
            if "chains" in data:
                result["chains"] = data.get("chains")
            
            # Cache the result
            cache_path = self.cache_manager.save(result, "defillama", "tvl", protocol.lower())
            if cache_path:
                self.logger.info(f"Cached TVL data for {protocol} at {cache_path}")
            else:
                self.logger.error(f"Failed to cache TVL data for {protocol}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching TVL data: {str(e)}")
            error_result = {"error": f"Failed to fetch TVL data: {str(e)}"}
            
            # Cache the error to prevent repeated failures
            self.cache_manager.save(error_result, "defillama", "tvl", protocol.lower())
            return error_result
    
    async def fetch_data(self, protocol: str) -> Dict[str, Any]:
        """General fetch data method that combines multiple data sources."""
        return await self.fetch_tvl_data(protocol)
        
    async def fetch_yields_data(self, protocol: str) -> Dict[str, Any]:
        """Fetch yields data for a specific protocol."""
        try:
            self.logger.info(f"Fetching yields data for {protocol} from DeFiLlama")
            
            # Set project name to ensure cache manager uses correct path
            self.project_name = protocol
            
            # Check cache first
            cached_data = self.cache_manager.load("defillama", "yields", protocol.lower())
            if cached_data:
                self.logger.info(f"Using cached yields data for {protocol}")
                return cached_data
            
            # Placeholder for future implementation
            result = {"message": "Yields data not implemented yet"}
            
            # Cache the result
            self.cache_manager.save(result, "defillama", "yields", protocol.lower())
            self.logger.info(f"Cached yields data for {protocol}")
            
            return result
        except Exception as e:
            self.logger.error(f"Error fetching yields data: {str(e)}")
            return {"error": f"Failed to fetch yields data: {str(e)}"}
            
    async def get_protocol_data(self, protocol_id: str) -> dict:
        """Get protocol data from DeFiLlama API."""
        url = f"https://api.llama.fi/protocol/{protocol_id}"
        return await self._make_request(url)
        
    async def get_yields_data(self, protocol_id: str) -> dict:
        """Get yields data from DeFiLlama API."""
        # For now, just return a placeholder
        return {"message": "Yields data not implemented yet for protocol ID"}
        
    async def search_protocols(self, query: str) -> list:
        """Search for protocols by name."""
        protocols_url = "https://api.llama.fi/protocols"
        
        try:
            # Get all protocols
            data = await self._make_request(protocols_url)
            if not data or "error" in data:
                return []
                
            # Filter protocols by query
            results = []
            query_lower = query.lower()
            
            for protocol in data:
                name = protocol.get("name", "").lower()
                symbol = protocol.get("symbol", "").lower()
                slug = protocol.get("slug", "").lower()
                
                if query_lower in name or query_lower in symbol or query_lower in slug:
                    results.append(protocol.get("slug"))
                    
            return results[:10]  # Return top 10 matches
            
        except Exception as e:
            self.logger.error(f"Error searching for protocols: {str(e)}")
            return []
            
    async def _make_request(self, url: str) -> dict:
        """Make a request to the DeFiLlama API."""
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Request error: {str(e)}"}

    async def get_tvl_data(self, protocol_id: str) -> dict:
        """Get TVL data for a specific protocol from DeFiLlama API."""
        self.logger.info(f"Fetching TVL data for protocol ID: {protocol_id}")
        
        # First, try to use cache
        cache_key = f"tvl_{protocol_id.lower()}"
        cached_data = self.cache_manager.load("defillama", "tvl", cache_key)
        
        if cached_data:
            self.logger.info(f"Using cached TVL data for {protocol_id}")
            return cached_data
            
        try:
            # Make the API request
            url = f"https://api.llama.fi/protocol/{protocol_id}"
            response = requests.get(url, timeout=15)
            
            # Check for successful response
            if response.status_code != 200:
                error_msg = f"DeFiLlama API request failed with status code: {response.status_code}"
                self.logger.error(error_msg)
                return {"error": error_msg}
                
            data = response.json()
            
            # Process the data
            result = {
                "name": data.get("name", protocol_id),
                "symbol": data.get("symbol", ""),
                "tvl": data.get("tvl", 0),
                "category": data.get("category", ""),
                "chains": data.get("chains", []),
                "source": "DeFiLlama"
            }
            
            # Process TVL history
            tvl_history = []
            if "tvl" in data and isinstance(data["tvl"], list):
                for item in data["tvl"]:
                    if isinstance(item, dict) and "date" in item and "totalLiquidityUSD" in item:
                        timestamp = int(item["date"]) * 1000  # Convert to milliseconds
                        tvl_history.append([timestamp, item["totalLiquidityUSD"]])
                        
            result["tvl_history"] = tvl_history
            
            # Add chain-specific TVL if available
            if "chainTvls" in data:
                chain_tvls = {}
                for chain, chain_data in data["chainTvls"].items():
                    if chain != "all" and isinstance(chain_data, dict):
                        chain_tvls[chain] = chain_data.get("tvl", 0)
                result["tvlByChain"] = chain_tvls
            
            # Cache the successful result
            self.cache_manager.save(result, "defillama", "tvl", cache_key)
            self.logger.info(f"Successfully fetched and cached TVL data for {protocol_id} with {len(tvl_history)} history points")
            
            return result
        except Exception as e:
            error_msg = f"Error fetching TVL data for {protocol_id}: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg} 