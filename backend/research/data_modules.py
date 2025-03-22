from typing import Dict, Any, Optional, List
import requests
import logging
import os
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod

class DataModule(ABC):
    """Base abstract class for data gathering modules."""
    
    def __init__(self, project_name: str, logger: logging.Logger):
        self.project_name = project_name
        self.logger = logger
        # Normalize project name for API calls
        self.coin_id = project_name.lower().replace(" ", "-")
        self.token_symbol = project_name.upper()
    
    @abstractmethod
    def gather_data(self) -> Dict[str, Any]:
        """Execute data gathering from the specific source."""
        pass
    
    def _handle_error(self, source: str, error: Exception) -> Dict[str, str]:
        """Handle errors in a consistent way."""
        self.logger.error(f"{source} error: {str(error)}")
        return {f"{source.lower()}_error": str(error)}


class CoinGeckoModule(DataModule):
    """Gathers data from CoinGecko API."""
    
    def gather_data(self) -> Dict[str, Any]:
        self.logger.info(f"Gathering CoinGecko data for {self.project_name}")
        
        result = {}
        
        # Define API endpoints
        coin_data_url = f"https://api.coingecko.com/api/v3/coins/{self.coin_id}"
        price_history_url = f"https://api.coingecko.com/api/v3/coins/{self.coin_id}/market_chart?vs_currency=usd&days=60"
        
        try:
            # Get coin data
            self.logger.debug(f"Fetching CoinGecko data from: {coin_data_url}")
            coin_response = requests.get(coin_data_url, timeout=10)
            coin_data = coin_response.json()
            
            if "market_data" not in coin_data:
                raise KeyError("Market data not found in CoinGecko response")
            
            # Extract market data
            market_data = coin_data["market_data"]
            result["current_price"] = market_data.get("current_price", {}).get("usd", 0)
            result["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)
            result["total_supply"] = market_data.get("total_supply", 0)
            result["circulating_supply"] = market_data.get("circulating_supply", 0)
            result["max_supply"] = market_data.get("max_supply", 0)
            
            # Extract price history
            self.logger.debug(f"Fetching CoinGecko price history from: {price_history_url}")
            price_response = requests.get(price_history_url, timeout=10)
            price_data = price_response.json()
            
            if "prices" in price_data:
                prices = [p[1] for p in price_data["prices"]]
                result["price_history"] = prices
                
                # Calculate price change
                if prices and prices[0] != 0:
                    change = ((prices[-1] - prices[0]) / prices[0] * 100)
                    result["price_change_60d"] = change
                
                # Generate price chart
                try:
                    plt.figure(figsize=(6, 4))
                    plt.plot(prices, label=f"{self.project_name} Price (USD)")
                    plt.title("60-Day Price Trend (CoinGecko)")
                    plt.xlabel("Days")
                    plt.ylabel("Price (USD)")
                    plt.legend()
                    
                    # Ensure docs directory exists
                    os.makedirs("docs", exist_ok=True)
                    chart_path = f"docs/{self.project_name}_price_chart.png"
                    plt.savefig(chart_path)
                    plt.close()
                    result["price_chart_path"] = chart_path
                except Exception as e:
                    self.logger.error(f"Error generating price chart: {str(e)}")
            
            return result
        except Exception as e:
            return self._handle_error("CoinGecko", e)


class CoinMarketCapModule(DataModule):
    """Gathers data from CoinMarketCap API."""
    
    def gather_data(self) -> Dict[str, Any]:
        self.logger.info(f"Gathering CoinMarketCap data for {self.project_name}")
        
        # Get API key
        api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not api_key:
            self.logger.warning("CoinMarketCap API key not found in environment")
            return {"coinmarketcap_error": "API key not found"}
        
        result = {}
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"symbol": self.token_symbol}
        
        try:
            self.logger.debug(f"Fetching CoinMarketCap data with params: {params}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            data = response.json()
            
            # Check for errors
            if data.get("status", {}).get("error_code") != 0:
                error_message = data.get("status", {}).get("error_message", "Unknown error")
                raise Exception(f"API Error: {error_message}")
            
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
            
            return result
        except Exception as e:
            return self._handle_error("CoinMarketCap", e)


class DeFiLlamaModule(DataModule):
    """Gathers data from DeFiLlama API."""
    
    def gather_data(self) -> Dict[str, Any]:
        self.logger.info(f"Gathering DeFiLlama data for {self.project_name}")
        
        result = {}
        protocols_url = "https://api.llama.fi/v2/protocols"
        
        try:
            self.logger.debug(f"Fetching DeFiLlama protocols data")
            response = requests.get(protocols_url, timeout=10)
            protocols = response.json()
            
            # Try different name variations to find the project
            protocol = None
            name_variations = [
                self.project_name.lower(),
                self.coin_id,
                self.token_symbol.lower()
            ]
            
            for name in name_variations:
                protocol = next((p for p in protocols if p["name"].lower() == name), None)
                if protocol:
                    break
            
            if protocol:
                result["tvl"] = protocol.get("tvl", 0)
                result["tvl_change_1d"] = protocol.get("change_1d", 0)
                result["tvl_change_7d"] = protocol.get("change_7d", 0)
                result["category"] = protocol.get("category", "Unknown")
                result["chains"] = protocol.get("chains", [])
                
                # Get historical TVL data if available
                try:
                    slug = protocol.get("slug")
                    if slug:
                        tvl_url = f"https://api.llama.fi/protocol/{slug}"
                        tvl_response = requests.get(tvl_url, timeout=10)
                        tvl_data = tvl_response.json()
                        
                        if "tvl" in tvl_data:
                            # Only keep recent data points to avoid overloading
                            tvl_history = tvl_data["tvl"][-60:]  # Last 60 days
                            result["tvl_history"] = tvl_history
                            
                            # Generate TVL chart
                            try:
                                tvl_values = [day["totalLiquidityUSD"] for day in tvl_history]
                                plt.figure(figsize=(6, 4))
                                plt.plot(tvl_values, label=f"{self.project_name} TVL (USD)")
                                plt.title("Recent TVL Trend (DeFiLlama)")
                                plt.xlabel("Days")
                                plt.ylabel("TVL (USD)")
                                plt.legend()
                                
                                # Ensure docs directory exists
                                os.makedirs("docs", exist_ok=True)
                                chart_path = f"docs/{self.project_name}_tvl_chart.png"
                                plt.savefig(chart_path)
                                plt.close()
                                result["tvl_chart_path"] = chart_path
                            except Exception as e:
                                self.logger.error(f"Error generating TVL chart: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Error fetching TVL history: {str(e)}")
            else:
                result["defi_llama_status"] = "Protocol not found"
            
            return result
        except Exception as e:
            return self._handle_error("DeFiLlama", e)


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
        
        return all_data
    
    def get_formatted_tokenomics(self, data: Dict[str, Any]) -> str:
        """Format tokenomics data into a readable string."""
        lines = [f"Tokenomics for {self.project_name}:"]
        
        # Prioritize data sources: CoinGecko first, then CMC
        coingecko = data.get("coingecko", {})
        coinmarketcap = data.get("coinmarketcap", {})
        
        # Total Supply
        if "total_supply" in coingecko:
            lines.append(f"Total Supply: {self._format_number(coingecko['total_supply'])}")
        elif "cmc_total_supply" in coinmarketcap:
            lines.append(f"Total Supply: {self._format_number(coinmarketcap['cmc_total_supply'])}")
        
        # Circulating Supply
        if "circulating_supply" in coingecko:
            lines.append(f"Circulating Supply: {self._format_number(coingecko['circulating_supply'])}")
        elif "cmc_circulating_supply" in coinmarketcap:
            lines.append(f"Circulating Supply: {self._format_number(coinmarketcap['cmc_circulating_supply'])}")
        
        # Current Price
        if "current_price" in coingecko:
            lines.append(f"Current Price: ${coingecko['current_price']:.4f}")
        elif "cmc_price" in coinmarketcap:
            lines.append(f"Current Price: ${coinmarketcap['cmc_price']:.4f}")
        
        # Market Cap
        if "market_cap" in coingecko:
            lines.append(f"Market Cap: ${self._format_number(coingecko['market_cap'])}")
        elif "cmc_market_cap" in coinmarketcap:
            lines.append(f"Market Cap: ${self._format_number(coinmarketcap['cmc_market_cap'])}")
        
        # Price Change
        if "price_change_60d" in coingecko:
            lines.append(f"60-Day Price Change: {coingecko['price_change_60d']:.2f}%")
        
        # Add DeFi data if available
        defillama = data.get("defillama", {})
        if "tvl" in defillama:
            lines.append(f"Total Value Locked: ${self._format_number(defillama['tvl'])}")
        
        if "category" in defillama:
            lines.append(f"DeFi Category: {defillama['category']}")
        
        if "chains" in defillama and defillama["chains"]:
            lines.append(f"Blockchain(s): {', '.join(defillama['chains'])}")
        
        return "\n".join(lines)
    
    def _format_number(self, number: float) -> str:
        """Format large numbers for readability."""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.2f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.2f}M"
        elif number >= 1_000:
            return f"{number/1_000:.2f}K"
        else:
            return f"{number:.2f}" 