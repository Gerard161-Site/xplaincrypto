# backend/state.py
from typing import Dict, List, Optional, Any, Union
import os

class ResearchState(dict):
    def __init__(self, project_name: str):
        # Initialize the dict base class
        super().__init__()
        
        # Initialize attributes
        self["project_name"] = project_name
        self["research_summary"] = ""
        self["key_features"] = ""
        self["tokenomics"] = ""
        self["price_analysis"] = ""
        self["governance"] = ""
        self["draft"] = ""
        self["final_report"] = ""
        self["references"] = []  # List of dicts with 'title' and 'url'
        self["progress"] = "Starting research..."
        self["queries"] = []  # Added for storing generated queries
        
        # Data from API sources
        self["data"] = {}  # All data combined (deprecated, use research_data instead)
        self["coingecko_data"] = {}  # CoinGecko-specific data
        self["coinmarketcap_data"] = {}  # CoinMarketCap-specific data
        self["defillama_data"] = {}  # DeFiLlama-specific data
        
        # Research data from web and other sources
        self["web_research"] = {}  # Raw web research summaries
        self["structured_data"] = {}  # Parsed data from web research
        self["research_data"] = {}  # Combined data after extraction/inference
        
        # Source information for data points
        self["data_sources"] = {}  # Format: {data_key: {"value": value, "source": source}}
        
        # Visualizations generated
        self["visualizations"] = {}
        
        # Report configuration
        self["report_config"] = {}
        
        # Missing attributes needed for compatibility with research orchestrator
        self["root_node"] = None
        self["errors"] = []
        self["query"] = ""
        self["current_node_id"] = None
        self["tree_generated"] = False
        self["research_complete"] = False
        self["data_gathered"] = False
        self["synthesis_complete"] = False
        self["team_and_development"] = ""
        self["missing_data_fields"] = []
        self["outputDir"] = os.path.join("docs", project_name.lower().replace(" ", "_"))
        
        # Create output directory if it doesn't exist
        os.makedirs(self["outputDir"], exist_ok=True)
        
        # Also set attributes for easy access as properties
        self.project_name = project_name
        self.research_summary = ""
        self.key_features = ""
        self.tokenomics = ""
        self.price_analysis = ""
        self.governance = ""
        self.draft = ""
        self.final_report = ""
        self.references = []
        self.progress = "Starting research..."
        self.queries = []
        self.data = {}
        self.coingecko_data = {}
        self.coinmarketcap_data = {}
        self.defillama_data = {}
        self.web_research = {}
        self.structured_data = {}
        self.research_data = {}
        self.data_sources = {}
        self.visualizations = {}
        self.report_config = {}
        self.root_node = None
        self.errors = []
        self.query = ""
        self.current_node_id = None
        self.tree_generated = False
        self.research_complete = False
        self.data_gathered = False
        self.synthesis_complete = False
        self.team_and_development = ""
        self.missing_data_fields = []
        self.outputDir = os.path.join("docs", project_name.lower().replace(" ", "_"))

    def update_progress(self, message: str):
        self.progress = message
        self["progress"] = message
        
    def add_data_with_source(self, key: str, value: Any, source: str):
        """Add a data point with its source information"""
        self.research_data[key] = value
        self["research_data"][key] = value
        self.data_sources[key] = {"value": value, "source": source}
        self["data_sources"][key] = {"value": value, "source": source}
        
    def get_data_with_source(self, key: str) -> Optional[Dict[str, Union[Any, str]]]:
        """Get a data point with its source information if available"""
        if key in self.data_sources:
            return self.data_sources[key]
        elif key in self.research_data:
            return {"value": self.research_data[key], "source": "Unknown"}
        return None

    def to_dict(self) -> Dict:
        """Convert state to dictionary."""
        # Since we're already a dict, just return a copy of ourselves
        return dict(self)
        
    def __setattr__(self, key, value):
        """Override to set both attribute and dictionary key when an attribute is set."""
        super().__setattr__(key, value)
        if key != "__dict__" and not key.startswith("_"):
            self[key] = value

    def __getattr__(self, key):
        """Override to get from dictionary if attribute doesn't exist."""
        if key in self:
            return self[key]
        raise AttributeError(f"'ResearchState' object has no attribute '{key}'")