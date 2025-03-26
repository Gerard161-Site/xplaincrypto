#!/usr/bin/env python
"""
Diagnostic script to check for and fix visualization issues.
"""

import os
import sys
import json
import glob
import logging
import shutil
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('visualization_diagnosis')

def check_output_directories():
    """Check if output directories exist and are writable."""
    logger.info("Checking output directories...")
    
    # Check docs directory
    if not os.path.exists("docs"):
        logger.error("docs directory does not exist, creating it...")
        try:
            os.makedirs("docs", exist_ok=True)
            logger.info("Created docs directory")
        except Exception as e:
            logger.error(f"Failed to create docs directory: {str(e)}")
            return False
    
    # Check project directories
    config_path = "backend/config/report_config.json"
    project_dirs = []
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                if "project_name" in config:
                    project_name = config["project_name"].lower().replace(" ", "_")
                    project_dirs.append(project_name)
        
        # Check any existing project directories in docs
        for path in glob.glob("docs/*/"):
            project_dir = os.path.basename(os.path.normpath(path))
            if project_dir and project_dir not in project_dirs:
                project_dirs.append(project_dir)
        
        if not project_dirs:
            logger.warning("No project directories found, creating a test one...")
            project_dirs.append("test_project")
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        # Create a test directory as fallback
        project_dirs = ["test_project"]
    
    # Check each project directory
    for project_dir in project_dirs:
        full_path = f"docs/{project_dir}"
        try:
            os.makedirs(full_path, exist_ok=True)
            logger.info(f"Ensuring directory exists: {full_path}")
            
            # Test if writable
            test_file = os.path.join(full_path, ".test_write")
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"Directory is writable: {full_path}")
        except Exception as e:
            logger.error(f"Problem with directory {full_path}: {str(e)}")
            return False
    
    return True

def test_matplotlib():
    """Test if matplotlib can create images correctly."""
    logger.info("Testing matplotlib...")
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        logger.info(f"Matplotlib version: {matplotlib.__version__}")
        logger.info(f"Matplotlib backend: {plt.get_backend()}")
        
        # Create a simple test plot
        test_dir = "docs/test_matplotlib"
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test_plot.png")
        
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3, 4], [1, 4, 2, 3])
        ax.set_title("Test Plot")
        
        logger.info(f"Saving test plot to {test_file}")
        plt.savefig(test_file)
        plt.close()
        
        # Verify file exists and has content
        if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            logger.info(f"Successfully created test plot: {test_file} ({os.path.getsize(test_file)/1024:.1f} KB)")
            return True
        else:
            logger.error(f"Failed to create test plot or file is empty")
            return False
            
    except ImportError:
        logger.error("Matplotlib is not installed or cannot be imported")
        return False
    except Exception as e:
        logger.error(f"Error testing matplotlib: {str(e)}")
        return False

def check_visualization_imports():
    """Check if visualization modules can be imported."""
    logger.info("Checking visualization imports...")
    
    try:
        import backend.visualizations
        from backend.visualizations import (
            BaseVisualizer,
            LineChartVisualizer, 
            BarChartVisualizer,
            PieChartVisualizer,
            TableVisualizer
        )
        logger.info("Successfully imported visualization modules")
        return True
    except ImportError as e:
        logger.error(f"Error importing visualization modules: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking visualization imports: {str(e)}")
        return False

def fix_permissions():
    """Fix permissions on the docs directory."""
    logger.info("Fixing permissions on docs directory...")
    
    try:
        # Make docs directory and all subdirectories writable
        for root, dirs, files in os.walk("docs"):
            os.chmod(root, 0o755)  # rwxr-xr-x
            for file in files:
                os.chmod(os.path.join(root, file), 0o644)  # rw-r--r--
        logger.info("Fixed permissions on docs directory")
        return True
    except Exception as e:
        logger.error(f"Error fixing permissions: {str(e)}")
        return False

def check_for_images():
    """Check if any images exist in project directories."""
    logger.info("Checking for existing visualization images...")
    
    found_images = []
    for path in glob.glob("docs/*/*.png"):
        found_images.append(path)
    
    if found_images:
        logger.info(f"Found {len(found_images)} existing visualization images:")
        for image in found_images[:10]:  # Show first 10
            logger.info(f"  - {image} ({os.path.getsize(image)/1024:.1f} KB)")
        if len(found_images) > 10:
            logger.info(f"  ... and {len(found_images) - 10} more")
    else:
        logger.warning("No visualization images found")
    
    return found_images

def main():
    """Run all diagnostic checks and fixes."""
    logger.info("Starting visualization diagnostic")
    
    # Check current working directory
    cwd = os.getcwd()
    logger.info(f"Current working directory: {cwd}")
    
    # Check if we're in the right directory
    expected_dirs = ["backend", "docs"]
    if not all(os.path.isdir(d) for d in expected_dirs):
        logger.error(f"Not in the correct project directory. Missing one of: {expected_dirs}")
        logger.info("Please run this script from the project root directory")
        return False
    
    checks = [
        ("Output directories", check_output_directories),
        ("Matplotlib", test_matplotlib),
        ("Visualization imports", check_visualization_imports)
    ]
    
    all_passed = True
    for name, check in checks:
        logger.info(f"Running check: {name}")
        if check():
            logger.info(f"✅ Check passed: {name}")
        else:
            logger.error(f"❌ Check failed: {name}")
            all_passed = False
    
    if not all_passed:
        logger.info("Attempting to fix issues...")
        fix_permissions()
        
        # Re-run checks that failed
        for name, check in checks:
            if not check():
                logger.error(f"Still failing: {name}")
    
    # Check for existing images
    found_images = check_for_images()
    
    if all_passed:
        logger.info("✅ All checks passed!")
    else:
        logger.warning("⚠️ Some checks failed, see above for details")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 