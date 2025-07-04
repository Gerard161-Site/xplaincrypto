"""Utilities and constants for the XplainCrypto application."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple


def ensure_dir_exists(dir_path: str) -> str:
    """Ensure a directory exists, creating it if necessary.
    
    Args:
        dir_path: Path to the directory to ensure exists
        
    Returns:
        The path to the directory that was created or verified
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return str(path.absolute())


def get_project_root() -> str:
    """Get the root directory of the project.
    
    Returns:
        Path to the project root
    """
    # This assumes this file is in backend/utils
    return str(Path(__file__).parent.parent.parent)


def get_reports_dir(project_name: str) -> str:
    """Get the reports directory for a project.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Path to the reports directory for the project
    """
    normalized_name = project_name.lower().replace(" ", "_")
    reports_dir = os.path.join(get_project_root(), "reports", normalized_name)
    ensure_dir_exists(reports_dir)
    return reports_dir


def get_cache_dir(project_name: str) -> str:
    """Get the cache directory for a project.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Path to the cache directory for the project
    """
    reports_dir = get_reports_dir(project_name)
    cache_dir = os.path.join(reports_dir, "cache")
    ensure_dir_exists(cache_dir)
    return cache_dir


# Default configurations
DEFAULT_COLORS = {
    "primary": "#3A86FF",
    "secondary": "#FF006E",
    "accent": "#FB5607",
    "highlight": "#FFBE0B",
    "background": "#FFFFFF",
    "text": "#333333",
    "grid": "#EEEEEE",
    "border": "#DDDDDD",
    "primary_light": "rgba(58, 134, 255, 0.2)"
}

DEFAULT_FONTS = {
    "headings": "Inter, sans-serif",
    "body": "Source Sans Pro, sans-serif",
    "data_labels": "Source Sans Pro, sans-serif"
}

DEFAULT_CHART_PROPERTIES = {
    "line_width": 2,
    "marker_size": 6,
    "bar_width": 0.7,
    "opacity": 0.8,
    "border_color": "#FFFFFF",
    "grid_color": "#EEEEEE",
    "width": 800,
    "height": 500
}

# Standard cache TTLs (in hours)
CACHE_TTL = {
    "coinmarketcap": 1,   # 1 hour for price data
    "coingecko": 1,       # 1 hour for price data
    "defillama": 4,       # 4 hours for TVL data
    "tokenomics": 168,    # 1 week for tokenomics data (rarely changes)
    "default": 24         # 24 hours for everything else
} 