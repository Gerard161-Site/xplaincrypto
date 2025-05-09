#!/usr/bin/env python3
"""
This script tests all the visualizer fixes to ensure there are no more warnings.
"""
import os
import json
import logging
from datetime import datetime, timedelta
import random
import pandas as pd
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_visualizer")

# Import visualization components
try:
    from backend.visualizations.visualization_factory import VisualizationFactory
    from backend.visualizations.base_visualizer import BaseVisualizer
    logger.info("Successfully imported from backend.visualizations")
except ImportError:
    try:
        from visualizations.visualization_factory import VisualizationFactory
        from visualizations.base_visualizer import BaseVisualizer
        logger.info("Successfully imported from visualizations")
    except ImportError:
        logger.error("Could not import visualization components")
        sys.exit(1)

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
    """Generate comprehensive test data for all chart types."""
    # Create timestamps for the past 12 months
    now = datetime.now()
    start_date = now - timedelta(days=365)
    dates = pd.date_range(start=start_date, end=now, freq='D')
    timestamps = [int(date.timestamp() * 1000) for date in dates]
    
    # Generate price history
    price_start = 100
    price_history = []
    current_price = price_start
    for timestamp in timestamps:
        # Add some randomness to price
        change = random.uniform(-0.03, 0.03)  # -3% to +3% daily change
        current_price = current_price * (1 + change)
        price_history.append([timestamp, current_price])
    
    # Generate volume history
    volume_history = []
    for timestamp in timestamps:
        # Random daily volume between $1M and $10M
        volume = random.uniform(1_000_000, 10_000_000)
        volume_history.append([timestamp, volume])
    
    # Generate TVL history
    tvl_history = []
    tvl_value = 100_000_000  # Start at $100M
    for timestamp in timestamps:
        # Add some randomness to TVL
        change = random.uniform(-0.02, 0.04)  # -2% to +4% daily change
        tvl_value = tvl_value * (1 + change)
        tvl_history.append([timestamp, tvl_value])
    
    # Generate OHLCV data
    ohlcv_data = []
    current_price = price_start
    for timestamp in timestamps:
        # Generate OHLCV data point
        open_price = current_price
        high_price = open_price * random.uniform(1.0, 1.05)
        low_price = open_price * random.uniform(0.95, 1.0)
        close_price = random.uniform(low_price, high_price)
        volume = random.uniform(1_000_000, 10_000_000)
        
        ohlcv_data.append({
            'timestamp': timestamp,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
        
        current_price = close_price
    
    # Generate token distribution data
    token_distribution = [
        {'name': 'Team', 'value': 20},
        {'name': 'Foundation', 'value': 15},
        {'name': 'Community', 'value': 25},
        {'name': 'Ecosystem', 'value': 30},
        {'name': 'Investors', 'value': 10}
    ]
    
    # Create full data structure
    data = {
        'coingecko': {
            'price_history': price_history,
            'volume_history': volume_history,
            'market_cap': current_price * 100_000_000,
            'current_price': current_price,
            'price_change_24h': random.uniform(-5, 5),
            'volume_24h': random.uniform(1_000_000, 10_000_000)
        },
        'coinmarketcap': {
            'price_history': price_history,
            'volume_history': volume_history,
            'market_cap': current_price * 100_000_000,
            'current_price': current_price,
            'price_change_24h': random.uniform(-5, 5),
            'volume_24h': random.uniform(1_000_000, 10_000_000),
            'ohlcv_data': ohlcv_data
        },
        'defillama': {
            'tvl_history': tvl_history,
            'name': 'Test Project',
            'symbol': 'TEST',
            'description': 'Test data for visualization',
            'category': 'DeFi',
            'chains': ['Ethereum', 'Arbitrum', 'Optimism'],
            'source': 'defillama'
        },
        'tokenomics': {
            'token_distribution': token_distribution,
            'total_supply': 100_000_000,
            'circulating_supply': 65_000_000,
            'name': 'Test Token',
            'symbol': 'TEST'
        }
    }
    
    return data

def test_visualizations():
    """Test all visualization types with the generated data."""
    # Create style manager and visualization factory
    logger.info("Creating visualization factory")
    style_manager = SimpleStyleManager()
    visualization_factory = VisualizationFactory(
        project_name="TEST_FIXES",
        style_manager=style_manager,
        logger=logger
    )
    
    # Generate test data
    logger.info("Generating test data")
    data = generate_test_data()
    
    # Create output directory
    output_dir = "docs/test_fixes"
    os.makedirs(output_dir, exist_ok=True)
    
    # Try all visualization types
    visualizations = [
        ("line_chart", "Price History"),
        ("volume_chart", "Volume History"),
        ("candlestick_chart", "OHLCV Chart"),
        ("pie_chart", "Token Distribution"),
        ("tokenomics_pie_chart", "Tokenomics Distribution"),
        ("bar_chart", "Key Metrics"),
        ("key_metrics_table", "Key Metrics Table"),
        ("tvl_milestone_chart", "TVL Milestones"),
        ("tvl_phases_chart", "TVL Phases"),
        ("monthly_growth_chart", "Monthly Growth"),
        ("liquidity_trends_chart", "Liquidity Trends"),
    ]
    
    logger.info(f"Testing {len(visualizations)} visualization types")
    results = {}
    
    for viz_type, title in visualizations:
        logger.info(f"Creating {viz_type}: {title}")
        result = visualization_factory.create(
            viz_type=viz_type,
            viz_config={"title": title},
            data=data
        )
        
        success, path, message = result
        results[viz_type] = {
            "success": success,
            "path": path,
            "message": message
        }
        
        logger.info(f"Result for {viz_type}: {success}, {message}")
    
    # Summary of results
    logger.info("===== SUMMARY =====")
    successful = 0
    failed = 0
    for viz_type, result in results.items():
        status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
        logger.info(f"{status}: {viz_type} - {result['message']}")
        if result["success"]:
            successful += 1
        else:
            failed += 1
    
    logger.info(f"Total: {len(results)}, Successful: {successful}, Failed: {failed}")
    return successful == len(results)  # Return True if all visualizations successful

if __name__ == "__main__":
    success = test_visualizations()
    sys.exit(0 if success else 1) 