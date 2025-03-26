from typing import Dict, List, Optional, Any, Union
from backend.research.core import ResearchNode
import os

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
        
        # Source information for data points
        self.data_sources: Dict[str, Dict[str, str]] = {}  # Format: {data_key: {"value": value, "source": source}}
        
        # Visualizations generated
        self.visualizations: Dict[str, Dict[str, Any]] = {}
        
        # Report configuration
        self.report_config: Dict[str, Any] = {}
        
        # Missing attributes needed for compatibility with research orchestrator
        self.root_node: Optional[ResearchNode] = None
        self.errors: List[str] = []
        self.query: str = ""
        self.current_node_id: Optional[str] = None
        self.tree_generated: bool = False
        self.research_complete: bool = False
        self.data_gathered: bool = False
        self.synthesis_complete: bool = False
        self.structured_data: Dict[str, Any] = {}
        self.team_and_development: str = ""
        self.missing_data_fields: List[str] = []
        self.outputDir: str = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
        
        # Create output directory if it doesn't exist
        os.makedirs(self.outputDir, exist_ok=True)

    def update_progress(self, message: str):
        self.progress = message
        
    def add_data_with_source(self, key: str, value: Any, source: str):
        """Add a data point with its source information"""
        # Store in research_data for backward compatibility
        self.research_data[key] = value
        
        # Store in data_sources with source information
        self.data_sources[key] = {"value": value, "source": source}
        
    def get_data_with_source(self, key: str) -> Optional[Dict[str, Union[Any, str]]]:
        """Get a data point with its source information if available"""
        if key in self.data_sources:
            return self.data_sources[key]
        elif key in self.research_data:
            # For backward compatibility with existing data
            return {"value": self.research_data[key], "source": "Unknown"}
        return None