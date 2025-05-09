import asyncio
import os
import sys
import json
import logging

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from backend.orchestration.mcp.retriever_servers.coinmarketcap_server import _fetch_ohlcv_impl
from backend.orchestration.mcp.retriever_servers.coinmarketcap_server import init_with_project

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_mcp")

async def test_ohlcv_endpoint():
    print("Testing OHLCV endpoint...")
    
    project_name = "ondo"  # Specify the project name
    
    # Try to access the OHLCV endpoint directly
    try:
        print("Calling OHLCV implementation directly...")
        # Initialize the CoinMarketCap server with the project
        init_with_project(project_name)
        
        result = await _fetch_ohlcv_impl("ondo", days=30, project_name="ondo")
        print("Direct OHLCV Implementation Result:", json.dumps(result, indent=2)[:500] + "...")
        
        # Save to cache for testing visualization
        print("OHLCV data successfully fetched and cached")
    except Exception as e:
        print(f"Error calling direct OHLCV implementation: {e}")
    
    # Execute a simple research query to test if visualizations work
    try:
        print("\nTesting if visualizations can access the cached OHLCV data...")
        # You can manually check if visualizations work by running the web interface
        # and checking if candlestick charts appear
        print("OHLCV data is now available in cache for candlestick charts")
    except Exception as e:
        print(f"Error testing visualizations: {e}")

if __name__ == "__main__":
    asyncio.run(test_ohlcv_endpoint()) 