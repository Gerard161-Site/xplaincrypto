"""
Utility module for managing API configurations and access controls.
This centralizes the logic for enabling/disabling various data providers.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class APIConfig:
    """
    Central configuration for API access and settings across the application.
    This allows for a single source of truth for API availability.
    """
    
    @staticmethod
    def is_api_enabled(api_name: str) -> bool:
        """
        Check if a specific API is enabled via environment variables.
        
        Args:
            api_name: The name of the API to check (e.g., 'coingecko', 'coinmarketcap')
            
        Returns:
            bool: Whether the API is enabled
        """
        env_var = f"{api_name.upper()}_ENABLED"
        return os.getenv(env_var, "true").lower() in ["true", "1", "yes", "y"]
    
    @staticmethod
    def get_api_key(api_name: str) -> Optional[str]:
        """
        Get the API key for a specific service.
        
        Args:
            api_name: The name of the API (e.g., 'coingecko', 'coinmarketcap')
            
        Returns:
            Optional[str]: The API key if available, None otherwise
        """
        env_var = f"{api_name.upper()}_API_KEY"
        api_key = os.getenv(env_var, "")
        
        if not api_key:
            logger.warning(f"{api_name.title()} API key not found in environment")
            return None
            
        return api_key
    
    @staticmethod
    def get_api_config() -> Dict[str, Dict[str, Any]]:
        """
        Get the configuration status of all supported APIs.
        
        Returns:
            Dict: Configuration status of all APIs
        """
        apis = ["coingecko", "coinmarketcap", "defillama", "dune", "huggingface"]
        config = {}
        
        for api in apis:
            config[api] = {
                "enabled": APIConfig.is_api_enabled(api),
                "has_key": APIConfig.get_api_key(api) is not None,
            }
            
        return config
    
    @staticmethod
    def check_rate_limits():
        """
        Check rate limit status for APIs and log warnings if approaching limits.
        This is a placeholder for future implementation of rate limit tracking.
        """
        # This would be implemented to track API usage across the application
        # and provide warnings when nearing limits
        pass 