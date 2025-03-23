import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.research.data_modules import DataGatherer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RealDataTest")

def test_data_collection(project_name, clear_cache=True):
    """Test data collection for a project with real-time API data."""
    logger.info(f"Testing real-time data collection for {project_name}")
    
    # Clear cache if requested
    if clear_cache:
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.startswith(project_name.lower()):
                    cache_path = os.path.join(cache_dir, file)
                    os.remove(cache_path)
                    logger.info(f"Cleared cache: {file}")
    
    # Gather data from all sources
    gatherer = DataGatherer(project_name, logger)
    data = gatherer.gather_all_data(use_cache=False)
    
    # Log a summary of collected data
    logger.info(f"=== Data Collection Summary for {project_name} ===")
    
    # Check for key fields that might cause visualization warnings
    key_fields = {
        "current_price": "Current Price",
        "market_cap": "Market Cap",
        "circulating_supply": "Circulating Supply",
        "total_supply": "Total Supply",
        "max_supply": "Max Supply",
        "price_history": "Price History",
        "volume_history": "Volume History",
        "tvl": "Total Value Locked",
        "tvl_history": "TVL History",
        "token_distribution": "Token Distribution",
        "competitors": "Competitors"
    }
    
    for field, label in key_fields.items():
        if field in data:
            if isinstance(data[field], list):
                logger.info(f"✅ {label}: Found with {len(data[field])} data points")
            elif isinstance(data[field], dict):
                logger.info(f"✅ {label}: Found with {len(data[field])} entries")
            else:
                logger.info(f"✅ {label}: {data[field]}")
        else:
            logger.error(f"❌ {label}: Missing")
    
    # Log total fields
    logger.info(f"Total fields: {len(data)}")
    logger.info(f"Fields: {', '.join(sorted(data.keys()))}")
    
    # Check for visualization readiness
    visualization_ready = all(field in data for field in [
        "price_history", "volume_history", "current_price", "market_cap"
    ])
    
    if visualization_ready:
        logger.info("✅ Basic visualizations are ready with real data")
    else:
        logger.warning("⚠️ Some basic visualizations may use synthetic data")
    
    if "token_distribution" in data:
        logger.info("✅ Token distribution chart is ready with real data")
    else:
        logger.warning("⚠️ Token distribution chart will use synthetic data")
    
    if "tvl_history" in data:
        logger.info("✅ TVL chart is ready with real data")
    else:
        logger.warning("⚠️ TVL chart will use synthetic data")
    
    if "competitors" in data:
        logger.info("✅ Competitor comparison chart is ready with real data")
    else:
        logger.warning("⚠️ Competitor comparison chart will use synthetic data")
    
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test real-time data collection")
    parser.add_argument("--project", type=str, default="ONDO", help="Project name to test")
    parser.add_argument("--cache", action="store_true", help="Use cached data if available")
    args = parser.parse_args()
    
    # Run the test
    result = test_data_collection(args.project, clear_cache=not args.cache)
    
    if result:
        logger.info(f"Successfully gathered data for {args.project} with {len(result)} fields")
    else:
        logger.error(f"Failed to gather data for {args.project}") 