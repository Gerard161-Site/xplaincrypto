import os
import json
import logging
import asyncio
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the visualizer
from backend.agents.visualizer import Visualizer, visualizer_sync
from backend.test_visualization_mapper import create_sample_state

def run_full_visualization_test(use_mapper=True):
    """
    Run a full visualization test with the sample state.
    
    Args:
        use_mapper: Whether to use the data mapper (True) or rely on direct config (False)
    """
    logger.info(f"Starting full visualization test (use_mapper={use_mapper})")
    
    # Create the visualizer
    visualizer = Visualizer(project_name="ondo", logger=logger)
    
    # Create sample state
    state = create_sample_state()
    
    # For testing without mapper, add explicit data source configs
    if not use_mapper:
        section_index = 0
        for section in state["report_config"]["sections"]:
            if section["title"] == "Market Analysis":
                for i, viz in enumerate(section["visualizations"]):
                    if viz["type"] == "tvl_chart":
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_source"] = "defillama"
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_field"] = "tvl_history"
                    elif viz["type"] == "price_chart":
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_source"] = "coinmarketcap"
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_field"] = "ohlcv"
                    elif viz["type"] == "volume_chart":
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_source"] = "coinmarketcap"
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_field"] = "volume_history"
            elif section["title"] == "Tokenomics":
                for i, viz in enumerate(section["visualizations"]):
                    if viz["type"] == "tokenomics_chart":
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_source"] = "tokenomics"
                        state["report_config"]["sections"][section_index]["visualizations"][i]["data_field"] = "token_distribution"
            section_index += 1
                
    # Run the visualizer
    try:
        logger.info("Running visualizer with sample state")
        updated_state = visualizer_sync(state, logger=logger)
        
        # Check results
        visualizations = updated_state.get("visualizations", {})
        visualization_list = updated_state.get("visualization_list", [])
        errors = updated_state.get("errors", {}).get("visualization", {})
        
        # Print summary
        logger.info(f"Visualization test completed with {len(visualization_list)} visualizations created")
        logger.info(f"Visualization paths: {json.dumps(visualizations, indent=2)}")
        
        if errors:
            logger.error(f"Errors during visualization: {json.dumps(errors, indent=2)}")
        else:
            logger.info("No errors reported during visualization")
            
        return updated_state
        
    except Exception as e:
        logger.error(f"Error running visualizer: {str(e)}")
        return None

if __name__ == "__main__":
    # First run with mapper enabled
    logger.info("=== TEST 1: WITH DATA MAPPER ===")
    with_mapper_state = run_full_visualization_test(use_mapper=True)
    
    # Then run with explicit data source configs
    logger.info("\n\n=== TEST 2: WITHOUT DATA MAPPER (DIRECT CONFIG) ===")
    without_mapper_state = run_full_visualization_test(use_mapper=False)
    
    # Compare results
    if with_mapper_state and without_mapper_state:
        with_mapper_vis = with_mapper_state.get("visualization_list", [])
        without_mapper_vis = without_mapper_state.get("visualization_list", [])
        
        logger.info(f"With mapper: {len(with_mapper_vis)} visualizations")
        logger.info(f"Without mapper: {len(without_mapper_vis)} visualizations")
        
        # Print visualization types created in each test
        with_mapper_types = [v.get("type") for v in with_mapper_vis]
        without_mapper_types = [v.get("type") for v in without_mapper_vis]
        
        logger.info(f"With mapper types: {with_mapper_types}")
        logger.info(f"Without mapper types: {without_mapper_types}")
    
    logger.info("Test completed") 