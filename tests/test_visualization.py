#!/usr/bin/env python
"""
Test script to verify visualization functionality.
This will test creating and saving images for each visualization type.
"""

import os
import logging
import matplotlib
matplotlib.use('Agg')  # Force non-interactive backend
import matplotlib.pyplot as plt
from backend.visualizations import (
    LineChartVisualizer,
    BarChartVisualizer,
    PieChartVisualizer,
    TableVisualizer,
    TimelineVisualizer
)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('visualization_test')

# Test project name
PROJECT_NAME = "test_project"

# Ensure test output directory exists
output_dir = os.path.join("docs", PROJECT_NAME)
os.makedirs(output_dir, exist_ok=True)

def test_line_chart():
    """Test the line chart visualizer"""
    logger.info("Testing line chart visualization")
    
    # Sample data
    data = {
        "prices": [[1609459200, 100], [1609545600, 110], [1609632000, 105], [1609718400, 115]]
    }
    
    # Create visualizer
    visualizer = LineChartVisualizer(PROJECT_NAME, logger)
    
    # Config
    config = {
        "type": "line_chart",
        "data_field": "prices",
        "title": "Test Line Chart"
    }
    
    # Create visualization
    result = visualizer.create("test_line_chart", config, data)
    
    # Check result
    if "error" in result:
        logger.error(f"Line chart test failed: {result['error']}")
    else:
        logger.info(f"Line chart test succeeded: {result['file_path']}")
    
    return result

def test_pie_chart():
    """Test the pie chart visualizer"""
    logger.info("Testing pie chart visualization")
    
    # Sample data
    data = {
        "token_distribution": {
            "Team": 20,
            "Community": 30,
            "Investors": 25,
            "Foundation": 25
        }
    }
    
    # Create visualizer
    visualizer = PieChartVisualizer(PROJECT_NAME, logger)
    
    # Config
    config = {
        "type": "pie_chart",
        "data_field": "token_distribution",
        "title": "Test Pie Chart"
    }
    
    # Create visualization
    result = visualizer.create("test_pie_chart", config, data)
    
    # Check result
    if "error" in result:
        logger.error(f"Pie chart test failed: {result['error']}")
    else:
        logger.info(f"Pie chart test succeeded: {result['file_path']}")
    
    return result

def test_bar_chart():
    """Test the bar chart visualizer"""
    logger.info("Testing bar chart visualization")
    
    # Sample data
    data = {
        "comparison": {
            "Project A": 30,
            "Project B": 45,
            "Project C": 25
        }
    }
    
    # Create visualizer
    visualizer = BarChartVisualizer(PROJECT_NAME, logger)
    
    # Config
    config = {
        "type": "bar_chart",
        "data_field": "comparison",
        "title": "Test Bar Chart"
    }
    
    # Create visualization
    result = visualizer.create("test_bar_chart", config, data)
    
    # Check result
    if "error" in result:
        logger.error(f"Bar chart test failed: {result['error']}")
    else:
        logger.info(f"Bar chart test succeeded: {result['file_path']}")
    
    return result

def main():
    """Run all visualization tests"""
    logger.info("Starting visualization tests")
    
    # Print matplotlib configuration
    logger.info(f"Matplotlib backend: {plt.get_backend()}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Test output directory: {output_dir}")
    
    # Verify output directory is writable
    test_file = os.path.join(output_dir, "test_write.txt")
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info("Output directory is writable")
    except Exception as e:
        logger.error(f"Output directory is not writable: {str(e)}")
    
    # Run tests
    results = []
    results.append(("Line Chart", test_line_chart()))
    results.append(("Pie Chart", test_pie_chart()))
    results.append(("Bar Chart", test_bar_chart()))
    
    # Print summary
    logger.info("=== Test Summary ===")
    success_count = 0
    for name, result in results:
        status = "SUCCESS" if "file_path" in result else "FAILED"
        if status == "SUCCESS":
            success_count += 1
        logger.info(f"{name}: {status}")
    
    logger.info(f"Tests completed: {success_count}/{len(results)} successful")

    # Create visualizer
    visualizer = TableVisualizer("test_project", logger)
    
    # Create test visualization
    result = visualizer.create_test_visualization()
    
    if result:
        logger.info(f"Successfully created test visualization at: {result}")
        if os.path.exists(result):
            logger.info("File exists and is accessible")
            logger.info(f"File size: {os.path.getsize(result)} bytes")
        else:
            logger.error("File does not exist!")
    else:
        logger.error("Failed to create test visualization")

if __name__ == "__main__":
    main() 