import os
import json
import logging
from backend.utils.cache_utils import CacheManager
from backend.utils.state_manager import StateManager
from backend.state import ResearchState
from backend.utils.style_utils import StyleManager
from backend.visualizations.candlestick_chart import CandlestickChartVisualizer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_visualization_data():
    """Diagnose why visualization data isn't working properly."""
    project_name = "ondo"
    
    # Create state
    state = ResearchState(project_name)
    state_manager = StateManager(logger=logger)
    
    # Set up other required components
    style_manager = StyleManager(logger=logger)
    
    # Create cache manager and load OHLCV data
    cache_manager = CacheManager(project_name=project_name, logger=logger)
    ohlcv_data = cache_manager.load("coinmarketcap", "ohlcv", f"{project_name}_30")
    
    if not ohlcv_data:
        logger.error("OHLCV data not found in cache")
        return
    
    logger.info(f"Successfully loaded OHLCV data from cache: keys={list(ohlcv_data.keys())}")
    
    # Print the structure of the data
    try:
        if 'ohlcv' in ohlcv_data:
            logger.info(f"Found {len(ohlcv_data['ohlcv'])} OHLCV entries")
        elif 'data' in ohlcv_data and 'ohlcv' in ohlcv_data['data']:
            logger.info(f"Found {len(ohlcv_data['data']['ohlcv'])} OHLCV entries in data.ohlcv")
    except Exception as e:
        logger.error(f"Error inspecting OHLCV data: {e}")
    
    # Let's examine the structure more carefully
    logger.info(f"Full OHLCV data structure (first 500 chars): {json.dumps(ohlcv_data, indent=2)[:500]}...")
    
    # Prepare data structures as expected by candlestick chart visualizer
    # Option 1: Put data in the coinmarketcap.ohlcv structure
    visualization_data = {
        "coinmarketcap": {
            "ohlcv": ohlcv_data['ohlcv']
        }
    }
    
    logger.info("Testing visualization with data structure 1...")
    try:
        visualizer = CandlestickChartVisualizer(project_name, style_manager, logger)
        usable = visualizer.check_data_usability(visualization_data)
        logger.info(f"Data structure 1 usability: {usable}")
    except Exception as e:
        logger.error(f"Error checking data structure 1: {e}")
    
    # Option 2: Put data in the direct ohlcv structure
    visualization_data2 = {
        "ohlcv": ohlcv_data['ohlcv']
    }
    
    logger.info("Testing visualization with data structure 2...")
    try:
        visualizer = CandlestickChartVisualizer(project_name, style_manager, logger)
        usable2 = visualizer.check_data_usability(visualization_data2)
        logger.info(f"Data structure 2 usability: {usable2}")
    except Exception as e:
        logger.error(f"Error checking data structure 2: {e}")
    
    # Option 3: Use data field format from cache
    visualization_data3 = {
        "data": ohlcv_data
    }
    
    logger.info("Testing visualization with data structure 3...")
    try:
        visualizer = CandlestickChartVisualizer(project_name, style_manager, logger)
        usable3 = visualizer.check_data_usability(visualization_data3)
        logger.info(f"Data structure 3 usability: {usable3}")
    except Exception as e:
        logger.error(f"Error checking data structure 3: {e}")
    
    # Option 4: Put the entire cached data directly
    visualization_data4 = ohlcv_data
    
    logger.info("Testing visualization with data structure 4...")
    try:
        visualizer = CandlestickChartVisualizer(project_name, style_manager, logger)
        usable4 = visualizer.check_data_usability(visualization_data4)
        logger.info(f"Data structure 4 usability: {usable4}")
    except Exception as e:
        logger.error(f"Error checking data structure 4: {e}")
    
    # Option 5: Add metadata structure with the right format
    visualization_data5 = {
        "metadata": ohlcv_data.get('metadata', {}),
        "data": ohlcv_data
    }
    
    logger.info("Testing visualization with data structure 5...")
    try:
        visualizer = CandlestickChartVisualizer(project_name, style_manager, logger)
        usable5 = visualizer.check_data_usability(visualization_data5)
        logger.info(f"Data structure 5 usability: {usable5}")
    except Exception as e:
        logger.error(f"Error checking data structure 5: {e}")
    
    # If all checks fail, print detailed data structure to help debug
    if not any([usable, usable2, usable3, usable4, usable5]):
        logger.error("All data structure patterns failed")
    else:
        logger.info("Found usable data structure(s)!")
        
        # Check creation with the first usable structure
        if usable:
            logger.info("Attempting to create visualization with data structure 1...")
            result, path, msg = visualizer.create_visualization("candlestick", {"title": "ONDO Price Chart"}, visualization_data)
            logger.info(f"Creation result: {result}, path: {path}, message: {msg}")
        elif usable2:
            logger.info("Attempting to create visualization with data structure 2...")
            result, path, msg = visualizer.create_visualization("candlestick", {"title": "ONDO Price Chart"}, visualization_data2)
            logger.info(f"Creation result: {result}, path: {path}, message: {msg}")
        elif usable3:
            logger.info("Attempting to create visualization with data structure 3...")
            result, path, msg = visualizer.create_visualization("candlestick", {"title": "ONDO Price Chart"}, visualization_data3)
            logger.info(f"Creation result: {result}, path: {path}, message: {msg}")
        elif usable4:
            logger.info("Attempting to create visualization with data structure 4...")
            result, path, msg = visualizer.create_visualization("candlestick", {"title": "ONDO Price Chart"}, visualization_data4)
            logger.info(f"Creation result: {result}, path: {path}, message: {msg}")
        elif usable5:
            logger.info("Attempting to create visualization with data structure 5...")
            result, path, msg = visualizer.create_visualization("candlestick", {"title": "ONDO Price Chart"}, visualization_data5)
            logger.info(f"Creation result: {result}, path: {path}, message: {msg}")

if __name__ == "__main__":
    diagnose_visualization_data() 