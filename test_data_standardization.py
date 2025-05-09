#!/usr/bin/env python
import asyncio
import logging
import os
import json
from backend.state import ResearchState
from backend.utils.data_standardizer import DataStandardizer
from backend.agents.researcher import Researcher
from backend.agents.visualizer import Visualizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataStandardizationTest")

# Test data
PROJECT_NAME = "test_standardization"
REPORT_CONFIG = {
    "sections": [
        {
            "title": "Market Analysis",
            "data_sources": ["coinmarketcap", "defillama"],
            "visualizations": [
                {
                    "id": "price_chart",
                    "type": "line_chart",
                    "title": "Price History",
                    "data_source": "coinmarketcap",
                    "data_field": "price_history"
                },
                {
                    "id": "volume_chart",
                    "type": "bar_chart",
                    "title": "Trading Volume",
                    "data_source": "coinmarketcap",
                    "data_field": "volume_data"
                }
            ]
        },
        {
            "title": "Tokenomics",
            "data_sources": ["tokenomics"],
            "visualizations": [
                {
                    "id": "distribution_chart",
                    "type": "pie_chart",
                    "title": "Token Distribution",
                    "data_source": "tokenomics",
                    "data_field": "token_distribution"
                }
            ]
        }
    ]
}

# Sample data for testing
SAMPLE_DATA = {
    "coinmarketcap": {
        "price_data": {
            "price_history": [
                {"date": "2023-01-01", "price": 100},
                {"date": "2023-02-01", "price": 120},
                {"date": "2023-03-01", "price": 90},
                {"date": "2023-04-01", "price": 150}
            ]
        },
        "volume_data": [
            {"date": "2023-01-01", "volume": 1000000},
            {"date": "2023-02-01", "volume": 1200000},
            {"date": "2023-03-01", "volume": 900000},
            {"date": "2023-04-01", "volume": 1500000}
        ]
    },
    "defillama": {
        "tvl_data": {
            "tvl_history": [
                {"date": "2023-01-01", "tvl": 5000000},
                {"date": "2023-02-01", "tvl": 6000000},
                {"date": "2023-03-01", "tvl": 5500000},
                {"date": "2023-04-01", "tvl": 7000000}
            ]
        }
    },
    "tokenomics": {
        "token_distribution": {
            "Team": 20,
            "Investors": 30,
            "Community": 40,
            "Foundation": 10
        }
    }
}

async def test_data_standardization():
    """Test the DataStandardizer class."""
    logger.info("=== Testing Data Standardization ===")
    
    # Create a test state
    state = ResearchState(project_name=PROJECT_NAME)
    state.report_config = REPORT_CONFIG
    state.data = SAMPLE_DATA
    
    # Create DataStandardizer
    standardizer = DataStandardizer(logger=logger)
    
    # Standardize data
    logger.info("Standardizing data...")
    standardized_state = standardizer.standardize_state_data(state, REPORT_CONFIG)
    
    # Verify standardized data
    if hasattr(standardized_state, "visualization_data"):
        logger.info("Checking visualization_data...")
        viz_data = standardized_state.visualization_data
        
        # Check Market Analysis section
        market_analysis = getattr(viz_data, "market_analysis", {})
        if "price_chart" in market_analysis:
            logger.info("✅ Found standardized price_chart data")
            logger.info(f"  Type: {market_analysis['price_chart'].get('type')}")
            logger.info(f"  Series count: {len(market_analysis['price_chart'].get('series', []))}")
        else:
            logger.error("❌ Missing price_chart data")
        
        if "volume_chart" in market_analysis:
            logger.info("✅ Found standardized volume_chart data")
            logger.info(f"  Type: {market_analysis['volume_chart'].get('type')}")
            logger.info(f"  Series count: {len(market_analysis['volume_chart'].get('series', []))}")
        else:
            logger.error("❌ Missing volume_chart data")
        
        # Check Tokenomics section
        tokenomics = getattr(viz_data, "tokenomics", {})
        if "distribution_chart" in tokenomics:
            logger.info("✅ Found standardized distribution_chart data")
            logger.info(f"  Type: {tokenomics['distribution_chart'].get('type')}")
            logger.info(f"  Data points: {len(tokenomics['distribution_chart'].get('data', []))}")
        else:
            logger.error("❌ Missing distribution_chart data")
    else:
        logger.error("❌ No visualization_data found in state")
        
    return standardized_state

async def test_visualizer_with_standardized_data(state):
    """Test the Visualizer with standardized data."""
    logger.info("=== Testing Visualizer with Standardized Data ===")
    
    # Create Visualizer
    visualizer = Visualizer(project_name=PROJECT_NAME)
    
    # Try to create visualizations
    for section in REPORT_CONFIG["sections"]:
        section_title = section["title"]
        for viz in section["visualizations"]:
            viz_id = viz["id"]
            logger.info(f"Creating visualization: {viz_id} in section {section_title}")
            
            # Create visualization
            result = visualizer._handle_visualization(section_title, viz_id, viz, state.to_dict())
            
            # Check result
            if result["success"]:
                logger.info(f"✅ Successfully created visualization: {viz_id}")
                logger.info(f"  Path: {result['path']}")
                logger.info(f"  Data source: {result['data_source']}")
            else:
                logger.error(f"❌ Failed to create visualization: {viz_id}")
                logger.error(f"  Error: {result['error']}")

async def main():
    """Run the tests."""
    logger.info("Starting data standardization tests...")
    
    # Test data standardization
    standardized_state = await test_data_standardization()
    
    # Test visualizer with standardized data
    await test_visualizer_with_standardized_data(standardized_state)
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 