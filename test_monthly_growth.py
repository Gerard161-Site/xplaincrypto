#!/usr/bin/env python3
import os
import json
import logging
import time
from datetime import datetime, timedelta
import random

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_monthly_growth")

# Find correct import path
try:
    from backend.visualizations.visualization_factory import VisualizationFactory
    from backend.visualizations.base_visualizer import BaseVisualizer
    logger.info("Successfully imported from backend.visualizations")
except ImportError:
    from visualizations.visualization_factory import VisualizationFactory
    from visualizations.base_visualizer import BaseVisualizer
    logger.info("Successfully imported from visualizations")

class SimpleStyleManager:
    """A simplified style manager for testing."""
    
    def get_colors(self):
        return {
            "primary": "#2196f3",
            "secondary": "#f44336",
            "accent": "#4caf50",
            "accent_secondary": "#f9a825",
            "accent_tertiary": "#7b1fa2",
            "background": "#ffffff",
            "grid": "#dddddd",
            "text": "#333333"
        }
    
    def get_visualization_config(self):
        return {
            "width": 900,
            "height": 600,
            "font": "Arial",
            "title_font_size": 18,
            "label_font_size": 12,
            "theme": "light"
        }

def generate_test_data():
    """Create test data with TVL history."""
    # Create TVL history for the past 12 months
    tvl_history = []
    now = datetime.now()
    
    # Start 12 months ago
    current_time = now - timedelta(days=365)
    
    # Generate 365 days of data
    tvl_value = 100_000_000  # Start at $100M
    
    for _ in range(365):
        # Convert datetime to timestamp in milliseconds
        timestamp = int(current_time.timestamp() * 1000)
        
        # Add some randomness to TVL
        change = random.uniform(-0.02, 0.04)  # -2% to +4% daily change
        tvl_value = tvl_value * (1 + change)
        
        # Add data point
        tvl_history.append([timestamp, tvl_value])
        
        # Move to next day
        current_time += timedelta(days=1)
    
    # Create full data structure
    data = {
        "defillama": {
            "tvl_history": tvl_history,
            "name": "Test Project",
            "symbol": "TEST",
            "description": "Test data for visualization",
            "category": "DeFi",
            "chains": ["Ethereum", "Arbitrum", "Optimism"],
            "source": "defillama"
        }
    }
    
    return data

def main():
    # Create style manager and visualization factory
    logger.info("Creating visualization factory")
    style_manager = SimpleStyleManager()
    visualization_factory = VisualizationFactory(
        project_name="TEST",
        style_manager=style_manager,
        logger=logger
    )
    
    # Check if DeFi Llama cache exists
    cache_file = "docs/cache/defillama.json"
    data = None
    
    if os.path.exists(cache_file):
        # Load DeFi Llama data
        logger.info(f"Loading data from {cache_file}")
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            logger.info(f"Data keys: {list(data.keys())}")
        except Exception as e:
            logger.error(f"Error loading cache file: {e}")
            data = None
    
    # If no data from cache, generate test data
    if data is None:
        logger.info("Generating test data")
        data = generate_test_data()
    
    # Create monthly growth chart
    logger.info("Creating monthly growth chart")
    result = visualization_factory.create(
        viz_type="monthly_growth_chart",
        viz_config={"title": "Monthly Growth"},
        data=data
    )
    
    logger.info(f"Visualization result: {result}")
    
    # Try a line chart with TVL history specifically
    logger.info("Creating line chart with tvl_history directly")
    if "defillama" in data and "tvl_history" in data["defillama"]:
        tvl_data = {"tvl_history": data["defillama"]["tvl_history"]}
        result = visualization_factory.create(
            viz_type="line_chart",
            viz_config={"title": "TVL History"},
            data=tvl_data
        )
        logger.info(f"TVL line chart result: {result}")

if __name__ == "__main__":
    main() 