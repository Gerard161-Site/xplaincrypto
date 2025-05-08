import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple
import time
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages caching of data with TTL (time-to-live) functionality.
    All caches are stored in docs/{project_name}/cache/ directories.
    """
    
    # Define source-specific TTL values in hours
    TTL_BY_SOURCE = {
        'coingecko': 1,      # 1 hour for price data
        'coinmarketcap': 1,  # 1 hour for market data
        'defillama': 4,      # 4 hours for TVL data
        'tavily': 24,        # 24 hours for research data
        'tokenomics': 24,    # 24 hours for tokenomics data
        'huggingface': 24,   # 24 hours for ML-based data
        'writer': 24,        # 24 hours for writer-generated content
        'writer_hf': 24,     # 24 hours for HuggingFace-generated content
    }

    def __init__(self, project_name: str = None, logger=None):
        """
        Initialize the cache manager with a project name.
        
        Args:
            project_name: The project name for project-specific caching
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Use a default project name if none provided
        if project_name is None:
            self.project_name = "default"
            self.logger.warning(f"No project_name provided to CacheManager, using '{self.project_name}'")
        elif project_name.lower() == "default" or project_name.lower() == "unknown" or project_name.strip() == "":
            self.logger.error(f"Invalid project_name provided to CacheManager: '{project_name}'")
            raise ValueError(f"Invalid project_name provided to CacheManager: '{project_name}'")
        else:
            self.project_name = project_name.lower()
            
        # Create cache directory if it doesn't exist
        self.base_cache_dir = os.path.join("docs", self.project_name, "cache")
        os.makedirs(self.base_cache_dir, exist_ok=True)
        
        self.logger.info(f"Cache directory set to: {self.base_cache_dir}")

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string to make it safe for use in a filename.
        Allows valid characters like dots and spaces while removing illegal characters.
        
        Args:
            name: The string to sanitize
            
        Returns:
            A sanitized string
        """
        # Remove invalid filename characters but preserve useful ones like dots and spaces
        return re.sub(r'[<>:"/\\|?*]', '_', name.strip())

    def get_cache_path(self, source: str, endpoint: str, query: str) -> str:
        """
        Generate a standardized cache path for a given query.
        
        Args:
            source: Data source (e.g., 'coingecko', 'defillama')
            endpoint: Endpoint type (e.g., 'price', 'tvl')
            query: Query parameter (e.g., 'ethereum')
            
        Returns:
            Path to the cache file
        """
        # Create source-specific directory
        source_dir = os.path.join(self.base_cache_dir, source)
        os.makedirs(source_dir, exist_ok=True)
        
        # Sanitize the query for filename
        safe_query = self._sanitize_filename(query)
        
        # Create standardized filename
        filename = f"{endpoint}_{safe_query}.json"
        return os.path.join(source_dir, filename)

    def save_to_cache(self, data: Dict[str, Any], source: str, endpoint: str, query: str, ttl_hours: int = None) -> str:
        """
        Save data to cache with metadata including TTL.
        Uses source-specific TTL values if ttl_hours is not provided.
        
        Args:
            data: Data to cache
            source: Data source (e.g., 'coingecko', 'defillama')
            endpoint: Endpoint type (e.g., 'price', 'tvl')
            query: Query parameter (e.g., 'ethereum')
            ttl_hours: Time-to-live in hours (default: None, uses source-specific TTL)
            
        Returns:
            Path to the cache file
        """
        cache_path = self.get_cache_path(source, endpoint, query)
        
        # Use source-specific TTL if not provided
        if ttl_hours is None:
            ttl_hours = self.TTL_BY_SOURCE.get(source, 24)  # Default to 24 hours if source not found
            self.logger.info(f"Using source-specific TTL for {source}: {ttl_hours} hours")
        
        # Add metadata including expiration time
        cache_entry = {
            "data": data,
            "metadata": {
                "source": source,
                "endpoint": endpoint,
                "query": query,
                "cached_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=ttl_hours)).isoformat(),
                "ttl_hours": ttl_hours
            }
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_entry, f, indent=2)
            self.logger.info(f"Cached data saved to {cache_path} with TTL of {ttl_hours} hours")
            return cache_path
        except Exception as e:
            self.logger.error(f"Error saving to cache: {str(e)}")
            return ""

    def load_from_cache(self, source: str, endpoint: str, query: str, 
                         check_ttl: bool = True) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Load data from cache if available and not expired.
        
        Args:
            source: Data source (e.g., 'coingecko', 'defillama')
            endpoint: Endpoint type (e.g., 'price', 'tvl')
            query: Query parameter (e.g., 'ethereum')
            check_ttl: Whether to check if cache is expired (default: True)
            
        Returns:
            Tuple of (data, from_cache) where data is the cached data (or None if not found)
            and from_cache is a boolean indicating if data was loaded from cache
        """
        cache_path = self.get_cache_path(source, endpoint, query)
        
        if not os.path.exists(cache_path):
            self.logger.info(f"No cache found at {cache_path}")
            return None, False
            
        try:
            with open(cache_path, 'r') as f:
                cache_entry = json.load(f)
                
            # Check if cache is expired
            if check_ttl and "metadata" in cache_entry and "expires_at" in cache_entry["metadata"]:
                expires_at = datetime.fromisoformat(cache_entry["metadata"]["expires_at"])
                if datetime.now() > expires_at:
                    self.logger.info(f"Cache expired at {cache_path}. Expired at: {expires_at.isoformat()}")
                    return None, True  # Return None but indicate it was cached (expired)
                    
            self.logger.info(f"Loaded data from cache: {cache_path}")
            return cache_entry.get("data"), True
            
        except Exception as e:
            self.logger.error(f"Error loading from cache: {str(e)}")
            return None, False

    # Simplified save method with ttl_seconds for backward compatibility
    def save(self, data: Dict[str, Any], source: str, endpoint: str, query: str, **kwargs) -> str:
        """
        Save data to cache with default TTL (simplified version).
        
        Args:
            data: Data to cache
            source: Data source (e.g., 'coingecko', 'defillama')
            endpoint: Endpoint type (e.g., 'price', 'tvl')
            query: Query parameter (e.g., 'ethereum')
            **kwargs: Additional parameters including ttl_seconds for backward compatibility
            
        Returns:
            Path to the cache file
        """
        # Convert ttl_seconds to ttl_hours if provided
        ttl_hours = None
        if 'ttl_seconds' in kwargs:
            ttl_hours = kwargs['ttl_seconds'] / 3600  # Convert seconds to hours
        
        return self.save_to_cache(data, source, endpoint, query, ttl_hours=ttl_hours)

    # Simplified load method that only returns the data
    def load(self, source: str, endpoint: str, query: str, check_ttl: bool = True, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Load data from cache if available and not expired (simplified version).
        
        Args:
            source: The data source (e.g., "coingecko", "coinmarketcap")
            endpoint: The specific endpoint used (e.g., "price", "markets")
            query: The query string or identifier (e.g., "bitcoin", "solana")
            check_ttl: Whether to check if cache is expired (default: True)
            **kwargs: Additional arguments (including ttl_seconds) that are ignored for backward compatibility
            
        Returns:
            The cached data if found and not expired, None otherwise
        """
        data, from_cache = self.load_from_cache(source, endpoint, query, check_ttl=check_ttl)
        return data if from_cache else None

    def is_cache_valid(self, source: str, endpoint: str, query: str) -> bool:
        """
        Check if cache exists and is not expired.
        
        Args:
            source: Data source (e.g., 'coingecko', 'defillama')
            endpoint: Endpoint type (e.g., 'price', 'tvl')
            query: Query parameter (e.g., 'ethereum')
            
        Returns:
            True if cache is valid, False otherwise
        """
        cache_path = self.get_cache_path(source, endpoint, query)
        
        if not os.path.exists(cache_path):
            return False
            
        try:
            with open(cache_path, 'r') as f:
                cache_entry = json.load(f)
                
            # Check if cache is expired
            if "metadata" in cache_entry and "expires_at" in cache_entry["metadata"]:
                expires_at = datetime.fromisoformat(cache_entry["metadata"]["expires_at"])
                if datetime.now() > expires_at:
                    self.logger.info(f"Cache at {cache_path} is expired. Expired at: {expires_at.isoformat()}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking cache validity: {str(e)}")
            return False

    def get_all_cache_files(self, source: Optional[str] = None) -> List[str]:
        """
        Get list of all cache files, optionally filtered by source.
        
        Args:
            source: Optional data source to filter by
            
        Returns:
            List of cache file paths
        """
        if source:
            source_dir = os.path.join(self.base_cache_dir, source)
            if not os.path.exists(source_dir):
                return []
            return [os.path.join(source_dir, f) for f in os.listdir(source_dir) 
                    if os.path.isfile(os.path.join(source_dir, f)) and f.endswith('.json')]
        else:
            cache_files = []
            for root, _, files in os.walk(self.base_cache_dir):
                for file in files:
                    if file.endswith('.json'):
                        cache_files.append(os.path.join(root, file))
            return cache_files

    def clear_expired_cache(self) -> int:
        """
        Clear all expired cache entries.
        
        Returns:
            Number of cache entries cleared
        """
        cleared_count = 0
        cache_files = self.get_all_cache_files()
        
        for cache_path in cache_files:
            try:
                with open(cache_path, 'r') as f:
                    cache_entry = json.load(f)
                    
                # Check if cache is expired
                if "metadata" in cache_entry and "expires_at" in cache_entry["metadata"]:
                    expires_at = datetime.fromisoformat(cache_entry["metadata"]["expires_at"])
                    if datetime.now() > expires_at:
                        os.remove(cache_path)
                        cleared_count += 1
                        self.logger.info(f"Cleared expired cache: {cache_path}")
            except Exception as e:
                self.logger.error(f"Error clearing expired cache {cache_path}: {str(e)}")
                
        return cleared_count

    def clear_all_cache(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of cache entries cleared
        """
        cleared_count = 0
        cache_files = self.get_all_cache_files()
        
        for cache_path in cache_files:
            try:
                os.remove(cache_path)
                cleared_count += 1
                self.logger.info(f"Cleared cache: {cache_path}")
            except Exception as e:
                self.logger.error(f"Error clearing cache {cache_path}: {str(e)}")
                
        return cleared_count

# Simple helper functions
def save_to_cache(data, source, endpoint, query, project_name):
    """
    Save data to cache using project name.
    
    Args:
        data: The data to cache
        source: The data source (e.g., "coingecko", "coinmarketcap")
        endpoint: The specific endpoint used (e.g., "price", "markets")
        query: The query string or identifier (e.g., "bitcoin", "solana")
        project_name: Name of the project for organizing caches
        
    Returns:
        The path to the cache file
    """
    # Let the CacheManager handle any invalid project_name values
    cache_mgr = CacheManager(project_name)
    return cache_mgr.save_to_cache(data, source, endpoint, query)

def load_from_cache(source, endpoint, query, project_name, **kwargs):
    """
    Load data from cache using project name.
    
    Args:
        source: The data source (e.g., "coingecko", "coinmarketcap")
        endpoint: The specific endpoint used (e.g., "price", "markets")
        query: The query string or identifier (e.g., "bitcoin", "solana")
        project_name: Name of the project for organizing caches
        **kwargs: Additional parameters for backward compatibility
        
    Returns:
        The cached data if found, None otherwise
    """
    # Let the CacheManager handle any invalid project_name values
    cache_mgr = CacheManager(project_name)
    result, _ = cache_mgr.load_from_cache(source, endpoint, query)
    return result

def clear_cache(project_name, source=None):
    """
    Clear cache files for a specific source or all sources.
    
    Args:
        project_name: Name of the project for organizing caches
        source: The specific source to clear, or None to clear all
        
    Returns:
        True if operation successful, False otherwise
    """
    # Let the CacheManager handle any invalid project_name values
    cache_mgr = CacheManager(project_name)
    return cache_mgr.clear_all_cache() > 0 