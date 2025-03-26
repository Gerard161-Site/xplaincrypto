"""
Visualization utilities for XplainCrypto reports.

This package contains specialized visualization modules for different chart types and data presentations.
Each module follows a consistent interface but handles a specific type of visualization.
"""

from backend.visualizations.base import BaseVisualizer
from backend.visualizations.line_chart import LineChartVisualizer
from backend.visualizations.bar_chart import BarChartVisualizer
from backend.visualizations.pie_chart import PieChartVisualizer
from backend.visualizations.table import TableVisualizer
from backend.visualizations.timeline import TimelineVisualizer

__all__ = [
    'BaseVisualizer',
    'LineChartVisualizer',
    'BarChartVisualizer', 
    'PieChartVisualizer',
    'TableVisualizer',
    'TimelineVisualizer'
] 