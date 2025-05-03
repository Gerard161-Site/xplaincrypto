import os
import logging
from typing import Dict, Any, Optional, List, Union

# Try importing datasets, but don't fail if not available
try:
    from datasets import load_dataset
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False

logger = logging.getLogger(__name__)

class HuggingFaceLoader:
    """Utility class for loading datasets from Hugging Face as a fallback data source."""
    
    def __init__(self, project_name: str = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the HuggingFace loader.
        
        Args:
            project_name: Project name to use in dataset paths
            logger: Optional logger instance to use
        """
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.available = HAS_DATASETS
        
        # Default dataset mappings
        self.dataset_mappings = {
            "coinmarketcap": {
                "price_history": "crypto_metrics/price_history",
                "volume_history": "crypto_metrics/volume_history",
                "market_cap": "crypto_metrics/market_metrics",
                "current_price": "crypto_metrics/current_metrics"
            },
            "defillama": {
                "tvl_history": "crypto_metrics/tvl_history",
                "tvl": "crypto_metrics/tvl_metrics",
                "chains": "crypto_metrics/chains"
            },
            "tokenomics": {
                "token_distribution": "crypto_metrics/token_distribution"
            }
        }
    
    def is_available(self) -> bool:
        """Check if HuggingFace datasets library is available."""
        return self.available
    
    def get_dataset_path(self, data_source: str, data_field: str) -> Optional[str]:
        """
        Map data source and field to a HuggingFace dataset path.
        
        Args:
            data_source: Source name (e.g., 'coinmarketcap', 'defillama')
            data_field: Field name (e.g., 'price_history', 'tvl')
            
        Returns:
            HuggingFace dataset path or None if not mapped
        """
        # First try source-specific mapping
        if data_source in self.dataset_mappings and data_field in self.dataset_mappings[data_source]:
            return self.dataset_mappings[data_source][data_field]
        
        # Then try project-specific dataset
        if self.project_name:
            return f"crypto_metrics/{self.project_name.lower()}_{data_field}"
        
        return None
    
    def load_data(self, data_source: str, data_field: str) -> Dict[str, Any]:
        """
        Load data from HuggingFace datasets.
        
        Args:
            data_source: Source name (e.g., 'coinmarketcap', 'defillama')
            data_field: Field name (e.g., 'price_history', 'tvl')
            
        Returns:
            Dictionary with loaded data or empty dict if not available
        """
        if not self.available:
            self.logger.warning("HuggingFace datasets library not available")
            return {}
        
        dataset_path = self.get_dataset_path(data_source, data_field)
        if not dataset_path:
            self.logger.warning(f"No dataset mapping found for {data_source}/{data_field}")
            return {}
        
        try:
            self.logger.info(f"Loading data from HuggingFace dataset: {dataset_path}")
            
            # Try loading the dataset
            try:
                # Check for HF_TOKEN in environment
                auth_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
                
                # Load dataset with token if available
                if auth_token:
                    dataset = load_dataset(dataset_path, split="train", use_auth_token=auth_token)
                else:
                    dataset = load_dataset(dataset_path, split="train")
                
                # Convert to dictionary
                if hasattr(dataset, "to_dict"):
                    data_dict = dataset.to_dict()
                elif hasattr(dataset, "to_pandas"):
                    data_dict = dataset.to_pandas().to_dict(orient="records")
                else:
                    data_dict = {col: dataset[col] for col in dataset.column_names}
                
                # Format return value to match expected nested structure
                self.logger.info(f"Successfully loaded data from HuggingFace dataset: {dataset_path}")
                return {data_source: {data_field: data_dict}}
                
            except Exception as e:
                self.logger.error(f"Error loading from HuggingFace dataset: {str(e)}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error in HuggingFace data loading: {str(e)}")
            return {}

# Convenience function for loading data
def load_from_huggingface(data_source: str, data_field: str, project_name: str = None) -> Dict[str, Any]:
    """
    Load data from HuggingFace datasets (convenience function).
    
    Args:
        data_source: Source name (e.g., 'coinmarketcap', 'defillama')
        data_field: Field name (e.g., 'price_history', 'tvl')
        project_name: Optional project name for dataset paths
        
    Returns:
        Dictionary with loaded data or empty dict if not available
    """
    loader = HuggingFaceLoader(project_name=project_name)
    return loader.load_data(data_source, data_field) 