from typing import Dict, List, Optional, Any

class ResearchState:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.research_summary: str = ""
        self.key_features: str = ""
        self.tokenomics: str = ""
        self.price_analysis: str = ""
        self.governance: str = ""
        self.draft: str = ""
        self.final_report: str = ""
        self.references: List[Dict[str, str]] = []  # List of dicts with 'title' and 'url'
        self.progress: str = "Starting research..."
        
        # Data from API sources
        self.data: Dict[str, Any] = {}  # All data combined
        self.coingecko_data: Dict[str, Any] = {}  # CoinGecko-specific data
        self.coinmarketcap_data: Dict[str, Any] = {}  # CoinMarketCap-specific data
        self.defillama_data: Dict[str, Any] = {}  # DeFiLlama-specific data
        
        # Research data from web and other sources
        self.research_data: Dict[str, Any] = {}
        
        # Visualizations generated
        self.visualizations: Dict[str, Dict[str, Any]] = {}
        
        # Report configuration
        self.report_config: Dict[str, Any] = {}

    def update_progress(self, message: str):
        self.progress = message