import os
import sys
import json
import logging
import time
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CacheCleanupTest")

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Import necessary modules
try:
    from backend.utils.cache_manager import CacheCleanupManager
except ImportError:
    logger.error("Failed to import CacheCleanupManager. Make sure you're running from the project root.")
    sys.exit(1)

def create_test_cache_files(test_dir, num_files=20, projects=None):
    """Create test cache files for testing the cleanup functionality."""
    if projects is None:
        projects = ["ondo", "bitcoin", "ethereum", "solana", "dogecoin"]
    
    base_dir = Path(test_dir)
    
    # Create cache structure
    for project in projects:
        project_dir = base_dir / project / "cache"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create cache subdirectories
        for source in ["coingecko", "tokenomics", "rag"]:
            source_dir = project_dir / source
            source_dir.mkdir(exist_ok=True)
            
            # Create cache files with different timestamps
            for i in range(num_files // len(projects) // len(["coingecko", "tokenomics", "rag"])):
                # Create with different timestamps to simulate access patterns
                access_time = time.time() - (i * 3600)  # Each file is 1 hour older
                
                # Create metadata with different TTLs
                if source == "coingecko":
                    ttl_hours = 1  # 1 hour for price data
                elif source == "tokenomics":
                    ttl_hours = 24  # 24 hours for tokenomics data
                else:
                    ttl_hours = 12  # 12 hours for other data
                
                expires_at = time.time() + (ttl_hours * 3600)
                if i % 5 == 0:  # Make some files expired
                    expires_at = time.time() - 3600
                
                # Create cache file
                file_path = source_dir / f"test_cache_{i}.json"
                data = {
                    "data": {"test": f"data for {project} {source} {i}"},
                    "metadata": {
                        "source": source,
                        "endpoint": f"test_endpoint_{i}",
                        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(access_time)),
                        "last_accessed": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(access_time)),
                        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(expires_at)),
                        "ttl_hours": ttl_hours
                    }
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Set file access time to simulate different access patterns
                os.utime(file_path, (access_time, access_time))
    
    return base_dir

def test_cache_cleanup():
    """Test the cache cleanup functionality."""
    logger.info("Starting cache cleanup test")
    
    # Create test directory
    test_dir = "test_cache_cleanup"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    # Create test cache files
    logger.info("Creating test cache files...")
    create_test_cache_files(test_dir, num_files=100)
    
    # Initialize cache cleanup manager
    cleanup_manager = CacheCleanupManager(base_cache_dir=test_dir)
    
    # Override default settings for testing
    cleanup_manager.max_cache_size_mb = 1  # 1MB
    cleanup_manager.max_files_per_project = 5
    cleanup_manager.cleanup_threshold_mb = 0.5  # 0.5MB
    
    # Get initial cache size
    initial_size = cleanup_manager.get_cache_size()
    logger.info(f"Initial cache size: {initial_size:.2f}MB")
    
    # Get initial file count
    initial_files = len(cleanup_manager.get_cache_files_info())
    logger.info(f"Initial file count: {initial_files}")
    
    # Test cleanup_expired
    logger.info("\nTesting cleanup_expired...")
    expired_count = cleanup_manager.cleanup_expired()
    logger.info(f"Deleted {expired_count} expired files")
    
    # Test cleanup_by_project
    logger.info("\nTesting cleanup_by_project...")
    project_count = cleanup_manager.cleanup_by_project("ondo", max_files=3)
    logger.info(f"Deleted {project_count} excess files for project 'ondo'")
    
    # Test cleanup_lru
    logger.info("\nTesting cleanup_lru...")
    lru_count = cleanup_manager.cleanup_lru(target_size_mb=0.2)
    logger.info(f"Deleted {lru_count} LRU files")
    
    # Get final cache size
    final_size = cleanup_manager.get_cache_size()
    logger.info(f"Final cache size: {final_size:.2f}MB")
    
    # Get final file count
    final_files = len(cleanup_manager.get_cache_files_info())
    logger.info(f"Final file count: {final_files}")
    
    # Test run_maintenance
    logger.info("\nTesting run_maintenance...")
    maintenance_results = cleanup_manager.run_maintenance(force=True)
    logger.info(f"Maintenance results: {maintenance_results}")
    
    # Clean up test directory
    shutil.rmtree(test_dir)
    logger.info("\nCache cleanup test completed")

if __name__ == "__main__":
    test_cache_cleanup() 