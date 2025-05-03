import logging
from typing import Dict, Any

class DataGatherer:
    """
    Gathers data from various sources for research workflows.
    Used as a fallback when MCP/RAG methods are unavailable.
    """

    def __init__(self, project_name: str, logger=None):
        """
        Initialize the data gatherer.
        
        Args:
            project_name: The name of the project to gather data for
            logger: Optional logger instance
        """
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        
    def gather_all_data(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Gather all data for the specified project.
        
        Args:
            use_cache: Whether to use cached data when available
            
        Returns:
            Dictionary containing all gathered data
        """
        self.logger.info(f"Using classic data gathering for project: {self.project_name}")
        
        # Return basic data to allow _classic_research to function
        return {
            "market_data": {
                "price": None,
                "market_cap": None,
                "volume": None,
                "data_unavailable": True
            },
            "tokenomics": {
                "token_allocation": {},
                "data_unavailable": True
            }
        } 