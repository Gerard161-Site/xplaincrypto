from typing import Dict, Any, List
import logging
import os
from backend.retriever.coingecko_api import CoinGeckoAPI
from backend.retriever.coinmarketcap_api import CoinMarketCapAPI
from backend.retriever.defillama_api import DeFiLlamaAPI
from backend.utils.api_config import APIConfig

class DataGatherer:
    """
    Centralized data gathering service that coordinates multiple cryptocurrency API retrievers.
    Each retriever can be run as a separate service in a microservices architecture.
    """
    
    def __init__(self, project_name: str, logger: logging.Logger):
        """
        Initialize the DataGatherer with a project name and logger.
        
        Args:
            project_name: Name of the cryptocurrency project to gather data for
            logger: Logger instance for recording operations
        """
        self.project_name = project_name
        self.logger = logger
        self.modules = []
        
        # Only initialize modules that are enabled
        if APIConfig.is_api_enabled("coingecko"):
            self.modules.append(CoinGeckoAPI(project_name, logger))
        else:
            self.logger.info("CoinGecko API is disabled in configuration")
            
        if APIConfig.is_api_enabled("coinmarketcap"):
            self.modules.append(CoinMarketCapAPI(project_name, logger))
        else:
            self.logger.info("CoinMarketCap API is disabled in configuration")
            
        if APIConfig.is_api_enabled("defillama"):
            self.modules.append(DeFiLlamaAPI(project_name, logger))
        else:
            self.logger.info("DeFiLlama API is disabled in configuration")
            
        # Log the enabled data sources
        enabled_modules = [m.__class__.__name__ for m in self.modules]
        self.logger.info(f"Enabled data modules: {', '.join(enabled_modules) if enabled_modules else 'None'}")
    
    def gather_all_data(self, use_cache=True, cache_ttl=10800) -> Dict[str, Any]:
        """
        Gather data from all available API modules and consolidate the results.
        
        Args:
            use_cache: Whether to use cached data if available
            cache_ttl: Time-to-live for cached data in seconds (default: 3 hours)
            
        Returns:
            Dictionary containing consolidated cryptocurrency data
        """
        all_data = {}
        
        # Add the project name to the data
        all_data["project_name"] = self.project_name
        self.logger.info(f"Gathering data for project: '{self.project_name}'")
        
        # Gather data from CoinMarketCap
        cmc_module = next((m for m in self.modules if isinstance(m, CoinMarketCapAPI)), None)
        if cmc_module:
            try:
                cmc_data = cmc_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in cmc_data and "coinmarketcap_disabled" not in cmc_data:
                    all_data["coinmarketcap"] = cmc_data
                    # Add key fields to the top level for backward compatibility
                    all_data.update(cmc_data)
                    self.logger.info(f"Added {len(cmc_data)} fields from CoinMarketCap")
                else:
                    error_msg = cmc_data.get('error') or cmc_data.get('coinmarketcap_disabled')
                    self.logger.warning(f"CoinMarketCap data not available: {error_msg}")
                    # Add placeholder data to avoid errors
                    all_data["coinmarketcap"] = {"error": error_msg}
            except Exception as e:
                self.logger.error(f"Error gathering data from CoinMarketCap: {str(e)}")
                all_data["coinmarketcap"] = {"error": str(e)}
        else:
            self.logger.info("CoinMarketCap API is disabled or not available")
            all_data["coinmarketcap"] = {"error": "API disabled"}
        
        # Gather data from CoinGecko
        cg_module = next((m for m in self.modules if isinstance(m, CoinGeckoAPI)), None)
        if cg_module:
            try:
                cg_data = cg_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in cg_data and "coingecko_disabled" not in cg_data:
                    all_data["coingecko"] = cg_data
                    # Add missing fields to the top level
                    for key, value in cg_data.items():
                        if key not in all_data or not all_data[key]:
                            all_data[key] = value
                            self.logger.info(f"Added missing field {key} from CoinGecko")
                else:
                    error_msg = cg_data.get('error') or cg_data.get('coingecko_disabled')
                    self.logger.warning(f"CoinGecko data not available: {error_msg}")
                    all_data["coingecko"] = {"error": error_msg}
            except Exception as e:
                self.logger.error(f"Error gathering data from CoinGecko: {str(e)}")
                all_data["coingecko"] = {"error": str(e)}
        else:
            self.logger.info("CoinGecko API is disabled or not available")
            all_data["coingecko"] = {"error": "API disabled"}
        
        # Gather data from DeFiLlama
        dl_module = next((m for m in self.modules if isinstance(m, DeFiLlamaAPI)), None)
        if dl_module:
            try:
                dl_data = dl_module.gather_data(use_cache=use_cache, cache_ttl=cache_ttl)
                if "error" not in dl_data and "defillama_disabled" not in dl_data:
                    all_data["defillama"] = dl_data
                    # Add fields to the top level
                    for key, value in dl_data.items():
                        all_data[key] = value
                    self.logger.info(f"Added {len(dl_data)} fields from DeFiLlama")
                else:
                    error_msg = dl_data.get('error') or dl_data.get('defillama_disabled')
                    self.logger.warning(f"DeFiLlama data not available: {error_msg}")
                    all_data["defillama"] = {"error": error_msg}
            except Exception as e:
                self.logger.error(f"Error gathering data from DeFiLlama: {str(e)}")
                all_data["defillama"] = {"error": str(e)}
        else:
            self.logger.info("DeFiLlama API is disabled or not available")
            all_data["defillama"] = {"error": "API disabled"}
        
        # If no API data was found, use synthetic data to avoid errors
        if not any(key in all_data for key in ["current_price", "market_cap"]):
            self.logger.warning(f"No real price data found for {self.project_name}, using synthetic data")
            all_data["current_price"] = 1.0
            all_data["market_cap"] = 1000000.0
            all_data["total_supply"] = 100000000.0
            all_data["circulating_supply"] = 50000000.0
            all_data["max_supply"] = 100000000.0
            all_data["24h_volume"] = 500000.0
            all_data["price_change_percentage_24h"] = 0.0
            
            # Generate synthetic price history
            from datetime import datetime, timedelta
            import random
            
            price_history = []
            volume_history = []
            current_price = 1.0
            current_volume = 500000.0
            
            # Generate 60 days of synthetic data
            for i in range(60):
                dt = datetime.now() - timedelta(days=60-i)
                timestamp = int(dt.timestamp() * 1000)
                
                # Random price fluctuation
                price_change = random.uniform(-0.05, 0.05)  # -5% to +5%
                current_price = max(0.01, current_price * (1 + price_change))
                price_history.append([timestamp, current_price])
                
                # Random volume fluctuation
                volume_change = random.uniform(-0.2, 0.2)  # -20% to +20%
                current_volume = max(10000, current_volume * (1 + volume_change))
                volume_history.append([timestamp, current_volume])
            
            all_data["price_history"] = price_history
            all_data["volume_history"] = volume_history
            all_data["data_source"] = "synthetic"
            self.logger.info("Generated synthetic historical data")
        
        # Normalize field names for consistency
        self._normalize_field_names(all_data)
        
        # Check for available visualization fields
        self._check_visualization_fields(all_data)
        
        return all_data
    
    def _normalize_field_names(self, data: Dict[str, Any]) -> None:
        """
        Normalize field names to ensure consistency across different API sources.
        
        Args:
            data: Dictionary of data to normalize
        """
        # Normalize volume
        if "24h_volume" not in data and "volume_24h" in data:
            data["24h_volume"] = data["volume_24h"]
        
        # Normalize price change
        if "price_change_percentage_24h" not in data and "percent_change_24h" in data:
            data["price_change_percentage_24h"] = data["percent_change_24h"]
        
        # Extract TVL from history if not available directly
        if "tvl" not in data and "tvl_history" in data and data["tvl_history"]:
            try:
                sorted_history = sorted(data["tvl_history"], key=lambda x: x[0])
                if sorted_history:
                    data["tvl"] = sorted_history[-1][1]
                    self.logger.info(f"Extracted TVL from history: ${data['tvl']:.0f}")
            except Exception as e:
                self.logger.error(f"Error extracting TVL from history: {str(e)}")
    
    def _check_visualization_fields(self, data: Dict[str, Any]) -> None:
        """
        Check for available visualization fields and log their presence.
        
        Args:
            data: Dictionary of data to check
        """
        visualization_fields = [
            "price_history", "volume_history", "tvl_history", "tvl", 
            "token_distribution", "competitors", "current_price", 
            "market_cap", "24h_volume", "circulating_supply", 
            "total_supply", "max_supply"
        ]
        
        found_fields = [f for f in visualization_fields if f in data]
        missing_fields = [f for f in visualization_fields if f not in data]
        
        if found_fields:
            self.logger.info(f"Found {len(found_fields)} fields for visualizations: {', '.join(found_fields)}")
        
        if missing_fields:
            self.logger.warning(f"Missing {len(missing_fields)} fields for visualizations: {', '.join(missing_fields)}")
            self.logger.warning("Some visualizations may use synthetic data") 