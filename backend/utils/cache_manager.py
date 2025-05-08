import os
import json
import time
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import heapq

class CacheCleanupManager:
    """
    Manages cache cleanup operations to prevent excessive disk usage.
    Implements a Least Recently Used (LRU) strategy for cache eviction.
    """
    
    def __init__(self, base_cache_dir: str = "docs", logger=None):
        self.base_cache_dir = base_cache_dir
        self.logger = logger or logging.getLogger(__name__)
        
        # Default limits
        self.max_cache_size_mb = 500  # 500MB default max cache size
        self.max_files_per_project = 1000
        self.cleanup_threshold_mb = 400  # Start cleanup when cache reaches this size
        
        # Load config if available
        self.load_config()
    
    def load_config(self):
        """Load cache configuration from app_config.json if available."""
        try:
            config_path = os.path.join("backend", "config", "app_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                cache_config = config.get("cache", {})
                self.max_cache_size_mb = cache_config.get("max_size_mb", self.max_cache_size_mb)
                self.max_files_per_project = cache_config.get("max_files_per_project", self.max_files_per_project)
                self.cleanup_threshold_mb = cache_config.get("cleanup_threshold_mb", self.cleanup_threshold_mb)
                
                self.logger.info(f"Loaded cache config: max_size={self.max_cache_size_mb}MB, "
                                f"max_files_per_project={self.max_files_per_project}, "
                                f"cleanup_threshold={self.cleanup_threshold_mb}MB")
        except Exception as e:
            self.logger.warning(f"Failed to load cache config: {str(e)}")
    
    def get_cache_size(self) -> float:
        """Get the total size of all cache directories in MB."""
        total_size = 0
        base_dir = Path(self.base_cache_dir)
        
        if not base_dir.exists():
            return 0
            
        for path in base_dir.glob("**/cache/**/*"):
            if path.is_file():
                total_size += path.stat().st_size
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def get_cache_files_info(self) -> List[Dict[str, Any]]:
        """Get information about all cache files for LRU eviction."""
        files_info = []
        base_dir = Path(self.base_cache_dir)
        
        if not base_dir.exists():
            return []
            
        for path in base_dir.glob("**/cache/**/*.json"):
            if path.is_file():
                try:
                    # Read the metadata to get last access time
                    with open(path, 'r') as f:
                        data = json.load(f)
                        metadata = data.get("metadata", {})
                        
                    # Extract project name from path
                    parts = path.parts
                    project_name = "unknown"
                    for i, part in enumerate(parts):
                        if part == "docs" and i+1 < len(parts):
                            project_name = parts[i+1]
                            break
                    
                    # Get access time from metadata or file stats
                    last_accessed = metadata.get("last_accessed", 
                                               metadata.get("cached_at", 
                                                          datetime.fromtimestamp(path.stat().st_atime).isoformat()))
                    
                    # Parse ISO datetime string to timestamp
                    if isinstance(last_accessed, str):
                        try:
                            dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                            last_accessed = dt.timestamp()
                        except:
                            last_accessed = path.stat().st_atime
                    
                    # Get TTL from metadata or default to 24 hours
                    ttl_hours = metadata.get("ttl_hours", 24)
                    
                    # Calculate expiration time
                    expires_at = metadata.get("expires_at", None)
                    if expires_at:
                        try:
                            dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                            expires_at = dt.timestamp()
                        except:
                            expires_at = time.time() + (ttl_hours * 3600)
                    else:
                        expires_at = time.time() + (ttl_hours * 3600)
                    
                    files_info.append({
                        "path": path,
                        "size": path.stat().st_size,
                        "last_accessed": last_accessed,
                        "expires_at": expires_at,
                        "project": project_name,
                        "source": metadata.get("source", "unknown"),
                        "endpoint": metadata.get("endpoint", "unknown"),
                    })
                except Exception as e:
                    self.logger.warning(f"Error processing cache file {path}: {str(e)}")
        
        return files_info
    
    def cleanup_expired(self) -> int:
        """Delete expired cache files and return count of deleted files."""
        files_info = self.get_cache_files_info()
        now = time.time()
        deleted_count = 0
        
        for file_info in files_info:
            if file_info["expires_at"] < now:
                try:
                    os.remove(file_info["path"])
                    deleted_count += 1
                    self.logger.info(f"Deleted expired cache file: {file_info['path']}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete expired cache file {file_info['path']}: {str(e)}")
        
        return deleted_count
    
    def cleanup_lru(self, target_size_mb: Optional[float] = None) -> int:
        """
        Delete least recently used cache files until cache size is below target.
        Returns count of deleted files.
        """
        if target_size_mb is None:
            target_size_mb = self.cleanup_threshold_mb
            
        current_size_mb = self.get_cache_size()
        if current_size_mb <= target_size_mb:
            return 0
            
        files_info = self.get_cache_files_info()
        
        # Sort by last accessed time (oldest first)
        files_info.sort(key=lambda x: x["last_accessed"])
        
        deleted_count = 0
        deleted_size = 0
        target_delete_size = (current_size_mb - target_size_mb) * 1024 * 1024  # Convert to bytes
        
        for file_info in files_info:
            if deleted_size >= target_delete_size:
                break
                
            try:
                os.remove(file_info["path"])
                deleted_count += 1
                deleted_size += file_info["size"]
                self.logger.info(f"Deleted LRU cache file: {file_info['path']} (last accessed: {datetime.fromtimestamp(file_info['last_accessed']).isoformat()})")
            except Exception as e:
                self.logger.warning(f"Failed to delete LRU cache file {file_info['path']}: {str(e)}")
        
        return deleted_count
    
    def cleanup_by_project(self, project_name: str, max_files: Optional[int] = None) -> int:
        """
        Ensure a project doesn't have too many cache files.
        Returns count of deleted files.
        """
        if max_files is None:
            max_files = self.max_files_per_project
            
        files_info = [f for f in self.get_cache_files_info() if f["project"].lower() == project_name.lower()]
        
        if len(files_info) <= max_files:
            return 0
            
        # Sort by last accessed time (oldest first)
        files_info.sort(key=lambda x: x["last_accessed"])
        
        # Keep only the newest max_files files
        files_to_delete = files_info[:-max_files] if max_files > 0 else files_info
        
        deleted_count = 0
        for file_info in files_to_delete:
            try:
                os.remove(file_info["path"])
                deleted_count += 1
                self.logger.info(f"Deleted excess cache file for project {project_name}: {file_info['path']}")
            except Exception as e:
                self.logger.warning(f"Failed to delete excess cache file {file_info['path']}: {str(e)}")
        
        return deleted_count
    
    def run_maintenance(self, force: bool = False) -> Dict[str, int]:
        """
        Run all cache maintenance tasks.
        Returns counts of deleted files by category.
        """
        results = {
            "expired": 0,
            "lru": 0,
            "project_limits": 0
        }
        
        # Always clean expired files
        results["expired"] = self.cleanup_expired()
        
        # Check if we need to run LRU cleanup
        current_size_mb = self.get_cache_size()
        if force or current_size_mb > self.cleanup_threshold_mb:
            results["lru"] = self.cleanup_lru()
            
        # Check project limits
        project_counts = {}
        for file_info in self.get_cache_files_info():
            project = file_info["project"]
            if project not in project_counts:
                project_counts[project] = 0
            project_counts[project] += 1
        
        # Clean up projects that exceed limits
        for project, count in project_counts.items():
            if count > self.max_files_per_project:
                deleted = self.cleanup_by_project(project)
                results["project_limits"] += deleted
        
        self.logger.info(f"Cache maintenance completed: {results}")
        return results

# Example usage:
# cleanup_manager = CacheCleanupManager()
# cleanup_manager.run_maintenance() 