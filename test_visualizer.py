import asyncio
import logging
import json
import os
from backend.agents.visualizer import visualizer_async
from backend.utils.state_manager import StateManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample OHLCV data
sample_ohlcv_data = [
    {"date": "2023-05-01", "open": 100.0, "high": 105.0, "low": 98.0, "close": 103.0, "volume": 1000},
    {"date": "2023-05-02", "open": 103.0, "high": 110.0, "low": 102.0, "close": 108.0, "volume": 1200},
    {"date": "2023-05-03", "open": 108.0, "high": 115.0, "low": 107.0, "close": 112.0, "volume": 1500},
    {"date": "2023-05-04", "open": 112.0, "high": 118.0, "low": 110.0, "close": 116.0, "volume": 1800},
    {"date": "2023-05-05", "open": 116.0, "high": 120.0, "low": 115.0, "close": 119.0, "volume": 2000},
    {"date": "2023-05-06", "open": 119.0, "high": 122.0, "low": 117.0, "close": 120.0, "volume": 1600},
    {"date": "2023-05-07", "open": 120.0, "high": 125.0, "low": 119.0, "close": 124.0, "volume": 1900},
]

async def test_visualizer():
    # Initialize state with sample data
    project_name = "test_project"
    state = {
        "project_name": project_name,
        "data": {
            "market_analysis": {
                "coinmarketcap": {
                    "ohlcv": sample_ohlcv_data
                }
            }
        },
        "visualization_request": [
            {
                "type": "candlestick_chart",
                "title": "Price Chart",
                "section": "Market Analysis",
                "data_source": "coinmarketcap",
                "data_field": "ohlcv"
            }
        ],
        "report_config": {
            "report_name": "Test Project Report",
            "prompt": "A comprehensive analysis of the test project",
            "version": "1.0",
            "fallback_template": "Data unavailable for {project_name} report.",
            "sections": [
                {
                    "title": "Market Analysis",
                    "required": True,
                    "min_words": 200,
                    "max_words": 300,
                    "query_template": "{project_name} market analysis",
                    "prompt": "Provide market analysis for the project",
                    "fallback_template": "Data unavailable for {section_title}.",
                    "fallback_fields": ["market_cap", "current_price"],
                    "data_sources": ["coinmarketcap", "coingecko"],
                    "visualizations": [
                        {
                            "type": "candlestick_chart",
                            "title": "Price Chart",
                            "id": "price_chart",
                            "data_source": "coinmarketcap",
                            "data_field": "ohlcv"
                        }
                    ]
                }
            ]
        }
    }
    
    # Set up output directory
    os.makedirs(f"docs/{project_name}", exist_ok=True)
    
    # Run visualizer
    logger.info("Running visualizer with test data...")
    result = await visualizer_async(state, logger=logger)
    
    # Print results
    logger.info(f"Visualizer finished with result keys: {list(result.keys())}")
    if "visualization_list" in result:
        logger.info(f"Generated visualizations: {json.dumps(result['visualization_list'], indent=2)}")
    
    # Print errors if any
    if "errors" in result and result["errors"]:
        logger.error(f"Errors: {json.dumps(result['errors'], indent=2)}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_visualizer()) 