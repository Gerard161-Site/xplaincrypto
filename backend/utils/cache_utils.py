import os
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple
import time
from datetime import datetime, timedelta

# Import the CacheCleanupManager
try:
    from backend.utils.cache_manager import CacheCleanupManager
except ImportError:
    # When running from inside backend directory
    try:
        from utils.cache_manager import CacheCleanupManager
    except ImportError:
        # Define a stub if the class is not available
        class CacheCleanupManager:
            def __init__(self, *args, **kwargs):
                pass
            def run_maintenance(self, *args, **kwargs):
                return {"expired": 0, "lru": 0, "project_limits": 0}

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages caching of data with TTL (time-to-live) functionality.
    All caches are stored in reports/{project_name}/cache/ directories.
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
        'rag': 24,           # 24 hours for RAG results
    }

    def __init__(self, project_name: str, logger=None):
        """
        Initialize the cache manager for a specific project.
        
        Args:
            project_name: The name of the project (e.g., "ondo", "bitcoin")
            logger: Optional logger instance
        """
        if not project_name or project_name.lower() == "default" or project_name.lower() == "unknown":
            raise ValueError(f"Invalid project_name provided: '{project_name}'. Must be a valid project name.")
            
        self.project_name = project_name.lower()
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up cache directory
        self.cache_dir = os.path.join("reports", self.project_name, "cache")
        self.logger.info(f"Cache directory set to: {self.cache_dir}")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cleanup manager
        self.cleanup_manager = CacheCleanupManager(base_cache_dir="reports", logger=self.logger)
        
        # Maintenance counter to avoid running cleanup too frequently
        self._maintenance_counter = 0
        self._maintenance_threshold = 10  # Run maintenance every 10 cache operations
        
    def _maybe_run_maintenance(self):
        """Run cache maintenance periodically."""
        self._maintenance_counter += 1
        if self._maintenance_counter >= self._maintenance_threshold:
            self._maintenance_counter = 0
            try:
                # Run maintenance in a non-blocking way
                import threading
                threading.Thread(target=self.cleanup_manager.run_maintenance).start()
            except Exception as e:
                self.logger.warning(f"Failed to run cache maintenance: {str(e)}")

    def _sanitize_filename(self, value):
        """
        Sanitize a string to be used as a filename.
        
        Args:
            value: String to sanitize
            
        Returns:
            Sanitized string safe for use in filenames
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Replace characters that are problematic in filenames
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t', '#', '%', '&', '{', '}', '+', '`', '=', '$', '@', '!', '^']
        for char in invalid_chars:
            value = value.replace(char, '_')
            
        # Replace multiple spaces with a single underscore
        value = re.sub(r'\s+', '_', value)
        
        # Remove any leading or trailing underscores
        value = value.strip('_')
        
        # Limit length to avoid overly long filenames
        if len(value) > 100:
            value = value[:100]
            
        return value

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
        source_dir = os.path.join(self.cache_dir, source)
        os.makedirs(source_dir, exist_ok=True)
        
        # Sanitize the query for filename
        safe_query = self._sanitize_filename(query)
        
        # Create standardized filename
        filename = f"{endpoint}_{safe_query}.json"
        return os.path.join(source_dir, filename)

    def save(self, data, source, endpoint, query, ttl_hours=None):
        """
        Save data to cache file.
        
        Args:
            data: Data to cache
            source: Source name (e.g., "coingecko", "coinmarketcap")
            endpoint: Endpoint name (e.g., "price", "market")
            query: Query string or identifier
            ttl_hours: Optional TTL in hours (defaults to class default)
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.project_name or not source or not endpoint or not query:
            if self.logger:
                self.logger.warning(f"Invalid parameters for cache save: project_name={self.project_name}, source={source}, endpoint={endpoint}, query={query}")
            return False
            
        try:
            # Use source-specific TTL if not provided
            if ttl_hours is None:
                ttl_hours = self.TTL_BY_SOURCE.get(source, 24)  # Default to 24 hours
                self.logger.info(f"Using source-specific TTL for {source}: {ttl_hours} hours")
            
            # Create source directory if it doesn't exist
            source_dir = os.path.join(self.cache_dir, source)
            os.makedirs(source_dir, exist_ok=True)
            
            # Generate cache file path - sanitize the query for filename safety
            cache_key = f"{endpoint}_{self._sanitize_filename(query)}"
            cache_file = os.path.join(source_dir, f"{cache_key}.json")
            
            # Sanitize data for JSON serialization
            sanitized_data = self._sanitize_for_json(data)
            
            # Add metadata
            now = datetime.now()
            expires_at = now + timedelta(hours=ttl_hours)
            
            metadata = {
                "source": source,
                "endpoint": endpoint,
                "query": query,
                "cached_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "last_accessed": now.isoformat(),
                "ttl_hours": ttl_hours
            }
            
            # Create cache entry with metadata
            cache_entry = {
                "data": sanitized_data,
                "metadata": metadata
            }
            
            # Save to file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, ensure_ascii=True, default=str, indent=None)
                
            if self.logger:
                self.logger.debug(f"Saved cache file: {cache_file}")
                
            # Maybe run maintenance
            self._maybe_run_maintenance()
                
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save cache: {str(e)}", exc_info=True)
            return False
    
    def _sanitize_for_json(self, data):
        """
        Recursively sanitize data to ensure it can be properly serialized to JSON.
        
        Args:
            data: The data to sanitize
            
        Returns:
            The sanitized data
        """
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_for_json(item) for item in data]
        elif isinstance(data, str):
            try:
                # First encode and decode to handle any encoding issues
                text = data.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                
                # Remove control characters but keep basic whitespace
                sanitized = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')
                
                # Replace any remaining problematic characters
                sanitized = sanitized.replace('\u2028', ' ').replace('\u2029', ' ')
                
                return sanitized
            except Exception as e:
                self.logger.warning(f"Error sanitizing string for JSON: {str(e)}")
                # Return a safe fallback
                return ""
        elif isinstance(data, (int, float, bool)) or data is None:
            # Return as is for basic types
            return data
        else:
            # For any other types, convert to string
            try:
                return str(data)
            except Exception as e:
                self.logger.warning(f"Error converting to string for JSON: {str(e)}")
                return ""
    
    def load(self, source, endpoint, query, check_freshness=True):
        """
        Load data from cache file.
        
        Args:
            source: Source name (e.g., "coingecko", "coinmarketcap")
            endpoint: Endpoint name (e.g., "price", "market")
            query: Query string or identifier
            check_freshness: Whether to check if the cache is fresh (default: True)
            
        Returns:
            Cached data if available, None otherwise
        """
        if not self.project_name or not source or not endpoint or not query:
            if self.logger:
                self.logger.warning(f"Invalid parameters for cache load: project_name={self.project_name}, source={source}, endpoint={endpoint}, query={query}")
            return None
            
        try:
            # Generate cache file path using sanitized query
            cache_key = f"{endpoint}_{self._sanitize_filename(query)}"
            cache_file = os.path.join(self.cache_dir, source, f"{cache_key}.json")
            
            if not os.path.exists(cache_file):
                if self.logger:
                    self.logger.debug(f"Cache miss: {cache_file} does not exist")
                return None
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_entry = json.load(f)
                
            # Update last accessed time
            metadata = cache_entry.get('metadata', {})
            now = datetime.now()
            metadata['last_accessed'] = now.isoformat()
            
            # Check freshness if requested
            if check_freshness and 'expires_at' in metadata:
                expires_at = datetime.fromisoformat(metadata['expires_at'])
                if now > expires_at:
                    if self.logger:
                        self.logger.debug(f"Cache stale: {cache_file} expired at {expires_at.isoformat()}")
                    return None
            
            # Update cache file with new last_accessed time
            cache_entry['metadata'] = metadata
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, ensure_ascii=True, default=str, indent=None)
                
            # Return the cached data
            return cache_entry.get('data')
        except Exception as e:
            self.logger.error(f"Error loading cache file {cache_file}: {str(e)}")
            return None
    
    def invalidate(self, source: str = None, endpoint: str = None, query: str = None) -> int:
        """
        Invalidate cache entries based on filters.
        
        Args:
            source: Optional source filter
            endpoint: Optional endpoint filter
            query: Optional query filter
            
        Returns:
            Number of cache entries invalidated
        """
        count = 0
        base_path = self.cache_dir
        
        if source:
            base_path = os.path.join(base_path, source)
        
        if not os.path.exists(base_path):
            return 0
        
        # Find matching cache files
        for root, _, files in os.walk(base_path):
            for file in files:
                if not file.endswith('.json'):
                    continue
                    
                # Check if file matches filters
                if endpoint and not file.startswith(f"{endpoint}_"):
                    continue
                    
                if query:
                    sanitized_query = self._sanitize_filename(query)
                    if f"_{sanitized_query}." not in file:
                        continue
                
                # Delete the file
                try:
                    os.remove(os.path.join(root, file))
                    count += 1
                    self.logger.info(f"Invalidated cache file: {os.path.join(root, file)}")
                except Exception as e:
                    self.logger.error(f"Error invalidating cache file {file}: {str(e)}")
        
        return count
    
    def clear_all(self) -> int:
        """
        Clear all cache entries for this project.
        
        Returns:
            Number of cache entries cleared
        """
        count = 0
        
        if not os.path.exists(self.cache_dir):
            return 0
        
        # Delete all files in cache directory
        for root, _, files in os.walk(self.cache_dir):
            for file in files:
                if file.endswith('.json'):
                    try:
                        os.remove(os.path.join(root, file))
                        count += 1
                    except Exception as e:
                        self.logger.error(f"Error clearing cache file {file}: {str(e)}")
        
        self.logger.info(f"Cleared {count} cache entries for project {self.project_name}")
        return count
    
    def run_cleanup(self, force: bool = False) -> Dict[str, int]:
        """
        Run cache cleanup operations.
        
        Args:
            force: Whether to force cleanup regardless of threshold
            
        Returns:
            Results of cleanup operations
        """
        return self.cleanup_manager.run_maintenance(force=force)

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
            source_dir = os.path.join(self.cache_dir, source)
            if not os.path.exists(source_dir):
                return []
            return [os.path.join(source_dir, f) for f in os.listdir(source_dir) 
                    if os.path.isfile(os.path.join(source_dir, f)) and f.endswith('.json')]
        else:
            cache_files = []
            for root, _, files in os.walk(self.cache_dir):
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
        True if saved successfully, False otherwise
    """
    # Let the CacheManager handle any invalid project_name values
    cache_mgr = CacheManager(project_name)
    return cache_mgr.save(data, source, endpoint, query)

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
        Tuple of (cached_data, is_valid) where cached_data is the data if found, None otherwise
        and is_valid is True if cache is valid, False otherwise
    """
    # Let the CacheManager handle any invalid project_name values
    cache_mgr = CacheManager(project_name)
    cached_data = cache_mgr.load(source, endpoint, query)
    return cached_data, cached_data is not None

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