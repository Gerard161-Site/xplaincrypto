import os
import json
import logging
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the visualizer
from backend.agents.visualizer import Visualizer

def create_sample_state() -> Dict[str, Any]:
    """
    Create a sample state with test data for each chart type.
    """
    return {
        "project_name": "ondo",
        "data": {
            "defillama": {
                "tvl_history": [
                    {"date": "2023-01-01", "tvl": 1000000},
                    {"date": "2023-01-02", "tvl": 1050000},
                    {"date": "2023-01-03", "tvl": 1100000}
                ],
                "currentChainTvls": {
                    "ethereum": 800000,
                    "polygon": 200000,
                    "arbitrum": 100000
                }
            },
            "coinmarketcap": {
                "ohlcv": [
                    {"date": "2023-01-01", "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 1000000},
                    {"date": "2023-01-02", "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2, "volume": 1200000},
                    {"date": "2023-01-03", "open": 1.2, "high": 1.4, "low": 1.1, "close": 1.3, "volume": 1500000}
                ],
                "volume_history": [
                    {"date": "2023-01-01", "volume": 1000000},
                    {"date": "2023-01-02", "volume": 1200000},
                    {"date": "2023-01-03", "volume": 1500000}
                ]
            },
            "tokenomics": {
                "token_distribution": {
                    "token_allocation": {
                        "Coinlist Tranche 1": 0.3,
                        "Coinlist Tranche 2": 1.7,
                        "Seed Investors": 7.0,
                        "Series A Investors": 7.0,
                        "Core Team": None
                    }
                }
            },
            "competitors": {
                "ondo": {
                    "tvl": 1000000,
                    "market_cap": 50000000,
                    "volume_24h": 1000000
                },
                "maker": {
                    "tvl": 5000000,
                    "market_cap": 800000000,
                    "volume_24h": 5000000
                },
                "aave": {
                    "tvl": 4000000,
                    "market_cap": 700000000,
                    "volume_24h": 4000000
                }
            },
            "metrics_table": [
                {"metric": "TVL", "value": "$1,000,000", "change_7d": "+5%"},
                {"metric": "Market Cap", "value": "$50,000,000", "change_7d": "+2%"},
                {"metric": "Volume (24h)", "value": "$1,000,000", "change_7d": "+10%"}
            ]
        },
        "report_config": {
            "sections": [
                {
                    "title": "Market Analysis",
                    "visualizations": [
                        {"type": "tvl_chart", "title": "TVL History"},
                        {"type": "price_chart", "title": "Price History (30-day)"},
                        {"type": "volume_chart", "title": "Volume History"}
                    ]
                },
                {
                    "title": "Tokenomics",
                    "visualizations": [
                        {"type": "tokenomics_chart", "title": "Token Distribution"}
                    ]
                },
                {
                    "title": "Ecosystem",
                    "visualizations": [
                        {"type": "chain_distribution_chart", "title": "Chain Distribution"}
                    ]
                },
                {
                    "title": "Competitor Analysis",
                    "visualizations": [
                        {"type": "comparison_chart", "title": "Competitor Comparison"}
                    ]
                },
                {
                    "title": "Key Metrics",
                    "visualizations": [
                        {"type": "metrics_table", "title": "Key Metrics"}
                    ]
                }
            ]
        }
    }

def test_data_mapping():
    """
    Test the data mapping functionality.
    """
    logger.info("Starting data mapping test")
    
    # Create the visualizer
    visualizer = Visualizer(project_name="ondo", logger=logger)
    
    # Create sample state
    state = create_sample_state()
    
    # Test each visualization type
    visualization_types = [
        "tvl_chart",
        "price_chart",
        "volume_chart",
        "tokenomics_chart",
        "chain_distribution_chart",
        "comparison_chart",
        "metrics_table"
    ]
    
    results = {}
    
    for viz_type in visualization_types:
        logger.info(f"Testing mapping for {viz_type}")
        viz_config = {"type": viz_type, "title": f"Test {viz_type.replace('_', ' ').title()}"}
        
        # Map data using our new method
        mapped_data = visualizer._map_data_to_visualization(viz_type, viz_config, state)
        results[viz_type] = {
            "success": mapped_data is not None,
            "data_keys": list(mapped_data.keys()) if mapped_data else None
        }
        
        if mapped_data:
            logger.info(f"Successfully mapped data for {viz_type}: {list(mapped_data.keys())}")
        else:
            logger.warning(f"Failed to map data for {viz_type}")
    
    # Print summary
    logger.info("Data mapping test results:")
    for viz_type, result in results.items():
        status = "SUCCESS" if result["success"] else "FAILED"
        logger.info(f"{viz_type}: {status} - Keys: {result['data_keys']}")
    
    return results

if __name__ == "__main__":
    test_results = test_data_mapping()
    logger.info("Test completed") 