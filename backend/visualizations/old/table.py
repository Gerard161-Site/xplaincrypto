"""
Table visualization module.

This module provides the TableVisualizer class for creating table visualizations
for key metrics, supply metrics, and other tabular data.
"""

import os
import logging
import math
import re
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime, timedelta
import json
import asyncio
import traceback
from backend.utils.cache_utils import CacheManager
from backend.utils.plotly_styler import PlotlyStyler
from backend.utils.style_utils import StyleManager
from .base import BaseVisualizer

# Simple number formatter class
class NumberFormatter:
    """Format numbers for display in visualizations."""
    
    @staticmethod
    def format_number(value, precision=2, currency=False, percentage=False, compact=True):
        """Format a number with appropriate suffixes (K, M, B, T) and precision."""
        if value is None or pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
            return "N/A"
        
        try:
            value = float(value)
            if value == 0:
                return "0"
                
            if percentage:
                # Format as percentage
                value = value * 100 if abs(value) < 10 else value  # Assume decimal if < 10
                return f"{value:.{precision}f}%"
                
            # Handle negative values
            sign = "-" if value < 0 else ""
            abs_value = abs(value)
            
            if compact and abs_value >= 1_000_000_000_000:
                # Trillions
                formatted = f"{sign}{abs_value / 1_000_000_000_000:.{precision}f}T"
            elif compact and abs_value >= 1_000_000_000:
                # Billions
                formatted = f"{sign}{abs_value / 1_000_000_000:.{precision}f}B"
            elif compact and abs_value >= 1_000_000:
                # Millions
                formatted = f"{sign}{abs_value / 1_000_000:.{precision}f}M"
            elif compact and abs_value >= 1_000:
                # Thousands
                formatted = f"{sign}{abs_value / 1_000:.{precision}f}K"
            else:
                # Regular
                formatted = f"{sign}{abs_value:.{precision}f}"
                
            # Strip trailing zeros and decimal point if applicable
            if "." in formatted:
                formatted = formatted.rstrip("0").rstrip(".")
                
            # Add currency symbol if requested
            if currency:
                formatted = f"${formatted}"
                
            return formatted
            
        except (ValueError, TypeError):
            # Return original value if it can't be converted to float
            return str(value)

# Configure logging
logger = logging.getLogger(__name__)

class TableVisualizer(BaseVisualizer):
    """Creates tabular visualizations using Plotly."""

    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the table visualizer
        
        Args:
            theme: Visual theme to use
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for labeling
            logger: Optional logger instance
        """
        super().__init__(theme, pdf_optimized, project_name, logger)
        self.project_name = project_name or "default"
        self.logger = logger or logging.getLogger(__name__)
        self.style_manager = StyleManager(logger=self.logger)
        self.styler = PlotlyStyler(theme=theme, project_name=self.project_name, logger=self.logger)
        
        # Get visualization config
        self.viz_config = self.style_manager.get_visualization_config()
        self.table_config = self.viz_config.get("table", {})
        
        # Set figure dimensions
        self.figure_config = self.viz_config.get("figure", {})
        self.width = self.figure_config.get("width", 5) * 2 * 100
        self.height = self.figure_config.get("height", 3.5) * 100
        
        # Set up output directory
        self.output_dir = os.path.join("docs", self.project_name)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize cache manager
        self.cache_manager = CacheManager(project_name=self.project_name, logger=self.logger)
        
        # Initialize formatter
        self.formatter = NumberFormatter()
        
    def validate_output_dir(self, output_dir):
        """Validate the output directory exists."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        self.logger.info(f"Validated output directory: {output_dir}")
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a table visualization.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating table {viz_type} for {self.project_name}")
            
            # Get title from config
            title = config.get("title", f"{viz_type.replace('_', ' ').title()}")
            
            # Extract the section title from viz_type
            section = viz_type.split('_')[0] if '_' in viz_type else viz_type
            
            # Output filename
            output_filename = f"{self.project_name.lower()}_{viz_type}.png"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Create table based on viz_type
            if viz_type == "key_metrics_table":
                table_data = self._extract_key_metrics_multi_source()
                if not table_data:
                    self.logger.warning(f"No key metrics data found for {self.project_name}")
                    return {
                        "success": False,
                        "message": f"No key metrics data found for {self.project_name}"
                    }
                
                return self._create_plotly_table(
                    headers=["Metric", "Value"], 
                    data=[[k, v] for k, v in table_data.items()],
                    title=title,
                    output_path=output_path,
                    source=config.get("source", "CoinMarketCap, CoinGecko, DeFiLlama")
                )
                
            elif viz_type == "adoption_metrics_table":
                table_data = self._load_adoption_metrics_from_cache()
                if not table_data:
                    self.logger.warning(f"No adoption metrics data found for {self.project_name}")
                    return {
                        "success": False,
                        "message": f"No adoption metrics data found for {self.project_name}"
                    }
                
                return self._create_plotly_table(
                    headers=["Metric", "Value"], 
                    data=[[k, v] for k, v in table_data.items()],
                    title=title,
                    output_path=output_path,
                    source=config.get("source", "DeFiLlama, CoinMarketCap, CoinGecko")
                )
                
            elif viz_type == "allocation_table":
                # Extract allocation data (placeholder)
                table_data = data.get("allocation", {})
                if not table_data:
                    self.logger.warning(f"No allocation data found for {self.project_name}")
                    return {
                        "success": False,
                        "message": f"No allocation data found for {self.project_name}"
                    }
                
                return self._create_plotly_table(
                    headers=["Category", "Allocation"], 
                    data=[[k, v] for k, v in table_data.items()],
                    title=title,
                    output_path=output_path,
                    source=config.get("source", "Project Documentation")
                )
                
            else:
                # Generic table handling
                if not data:
                    self.logger.warning(f"No data provided for {viz_type}")
                    return {
                        "success": False,
                        "message": f"No data provided for {viz_type}"
                    }
                
                # Extract headers and data
                if isinstance(data, dict):
                    headers = ["Key", "Value"]
                    data_rows = [[k, v] for k, v in data.items()]
                elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    # List of dictionaries
                    if data:
                        headers = list(data[0].keys())
                        data_rows = [[item.get(h) for h in headers] for item in data]
                    else:
                        headers = ["No Data"]
                        data_rows = []
                else:
                    self.logger.warning(f"Unsupported data format for {viz_type}")
                    return {
                        "success": False,
                        "message": f"Unsupported data format for {viz_type}"
                    }
                
                return self._create_plotly_table(
                    headers=headers, 
                    data=data_rows,
                    title=title,
                    output_path=output_path,
                    source=config.get("source", "Various Sources")
                )
                
        except Exception as e:
            self.logger.error(f"Error creating table visualization: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_plotly_table(self, headers: List[str], data: List[List[Any]], 
                             title: str, output_path: str, source: str = None,
                             note: str = None) -> Dict[str, Any]:
        """
        Create a Plotly table visualization
        
        Args:
            headers: List of column headers
            data: List of data rows
            title: Table title
            output_path: Path to save the output file
            source: Data source attribution
            note: Optional note to display
            
        Returns:
            Dict with visualization result
        """
        try:
            # Format values for better display
            formatted_data = []
            for row in data:
                formatted_row = []
                for value in row:
                    if isinstance(value, (int, float)):
                        if row[0] and "percent" in str(row[0]).lower():
                            # Format as percentage
                            formatted_row.append(self.formatter.format_number(value, precision=2, percentage=True))
                        elif row[0] and any(keyword in str(row[0]).lower() for keyword in ["price", "market cap", "volume", "tvl", "value"]):
                            # Format as currency
                            formatted_row.append(self.formatter.format_number(value, precision=2, currency=True))
                        else:
                            # Format as regular number with appropriate suffixes
                            formatted_row.append(self.formatter.format_number(value, precision=2))
                    else:
                        # Pass through non-numeric values
                        formatted_row.append(str(value) if value is not None else "N/A")
                formatted_data.append(formatted_row)
            
            # Create figure
            fig = go.Figure(data=[go.Table(
                header=dict(values=headers),
                cells=dict(values=list(zip(*formatted_data)) if formatted_data else [[] for _ in headers])
            )])
            
            # Apply styling
            fig = self.styler.style_table(fig)
            fig = self.styler.apply_layout(
                fig=fig, 
                title=title,
                width=self.width, 
                height=self.height, # Dynamic height based on row count
                showlegend=False
            )
            
            # Add source if provided
            if source:
                fig = self.styler.add_source_annotation(fig, source)
            
            # Add note if provided
            if note:
                fig = self.styler.add_note_annotation(fig, note)
                
            # Increase bottom margin to accommodate annotations
            if source or note:
                fig.update_layout(margin=dict(b=100))
            
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the figure
            fig.write_image(output_path, scale=2)
            
            return {
                "success": True,
                "file_path": output_path,
                "title": title
            }
        except Exception as e:
            self.logger.error(f"Error creating Plotly table: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_key_metrics_multi_source(self) -> Dict[str, Any]:
        """Extract and combine key metrics from multiple data sources."""
        metrics = {}
        
        # According to report_config.json, primary metrics should come from coinmarketcap
        # with defillama only used for TVL metrics
        
        # First priority: Load data from coinmarketcap cache
        try:
            self.logger.info(f"Loading coinmarketcap data for key_metrics_table of {self.project_name}")
            coinmarketcap_data = self.cache_manager.load("coinmarketcap", "", self.project_name.lower())
            if not coinmarketcap_data:
                # Try looking for specific files
                coinmarketcap_dir = os.path.join("docs", self.project_name, "cache", "coinmarketcap")
                if os.path.exists(coinmarketcap_dir):
                    for filename in os.listdir(coinmarketcap_dir):
                        if filename.endswith('.json'):
                            with open(os.path.join(coinmarketcap_dir, filename), 'r') as f:
                                try:
                                    file_data = json.load(f)
                                    if 'data' in file_data and isinstance(file_data['data'], dict):
                                        self._extract_metric(file_data['data'], 'price', metrics)
                                        self._extract_metric(file_data['data'], 'market_cap', metrics)
                                        self._extract_metric(file_data['data'], 'volume', metrics)
                                        self._extract_metric(file_data['data'], 'supply', metrics)
                                        self._extract_metric(file_data['data'], 'rank', metrics)
                                except json.JSONDecodeError:
                                    continue
            else:
                # Data found through cache manager
                if isinstance(coinmarketcap_data, dict):
                    if 'data' in coinmarketcap_data and isinstance(coinmarketcap_data['data'], dict):
                        self._extract_metric(coinmarketcap_data['data'], 'price', metrics)
                        self._extract_metric(coinmarketcap_data['data'], 'market_cap', metrics)
                        self._extract_metric(coinmarketcap_data['data'], 'volume', metrics)
                        self._extract_metric(coinmarketcap_data['data'], 'supply', metrics)
                        self._extract_metric(coinmarketcap_data['data'], 'rank', metrics)
        except Exception as e:
            self.logger.error(f"Error loading coinmarketcap data: {str(e)}")
            
        # Second priority: Load data from coingecko cache (as backup if coinmarketcap data is missing)
        if not metrics or len(metrics) < 3:  # If we have few or no metrics from coinmarketcap
            try:
                self.logger.info(f"Loading coingecko data for key_metrics_table of {self.project_name}")
                coingecko_data = self.cache_manager.load("coingecko", "", self.project_name.lower())
                if not coingecko_data:
                    # Try looking for specific files
                    coingecko_dir = os.path.join("docs", self.project_name, "cache", "coingecko")
                    if os.path.exists(coingecko_dir):
                        for filename in os.listdir(coingecko_dir):
                            if filename.endswith('.json'):
                                with open(os.path.join(coingecko_dir, filename), 'r') as f:
                                    try:
                                        file_data = json.load(f)
                                        if 'data' in file_data and isinstance(file_data['data'], dict):
                                            # Only extract metrics that are missing from coinmarketcap
                                            for metric_type in ['price', 'market_cap', 'volume', 'supply']:
                                                if not any(metric.lower().startswith(metric_type) for metric in metrics.keys()):
                                                    self._extract_metric(file_data['data'], metric_type, metrics)
                                    except json.JSONDecodeError:
                                        continue
                else:
                    # Data found through cache manager
                    if isinstance(coingecko_data, dict):
                        if 'data' in coingecko_data and isinstance(coingecko_data['data'], dict):
                            # Only extract metrics that are missing from coinmarketcap
                            for metric_type in ['price', 'market_cap', 'volume', 'supply']:
                                if not any(metric.lower().startswith(metric_type) for metric in metrics.keys()):
                                    self._extract_metric(coingecko_data['data'], metric_type, metrics)
            except Exception as e:
                self.logger.error(f"Error loading coingecko data: {str(e)}")
            
        # Last: Load TVL data only from defillama cache (as per report_config.json)
        try:
            self.logger.info(f"Loading TVL data from defillama for key_metrics_table of {self.project_name}")
            defillama_data = None
            defillama_dir = os.path.join("docs", self.project_name, "cache", "defillama")
            if os.path.exists(defillama_dir):
                # Try using cache manager first
                defillama_data = self.cache_manager.load("defillama", "tvl", self.project_name.lower())
                
                if not defillama_data:
                    # Try direct file access as backup
                    for filename in os.listdir(defillama_dir):
                        if "tvl" in filename.lower() and filename.endswith('.json'):
                            with open(os.path.join(defillama_dir, filename), 'r') as f:
                                try:
                                    file_data = json.load(f)
                                    defillama_data = file_data
                                    break
                                except json.JSONDecodeError:
                                    continue
            
            # Extract TVL data if available
            if defillama_data:
                if 'tvl' in defillama_data:
                    metrics['TVL'] = defillama_data['tvl']
                elif 'data' in defillama_data and 'tvl' in defillama_data['data']:
                    if isinstance(defillama_data['data']['tvl'], (int, float)):
                        metrics['TVL'] = defillama_data['data']['tvl']
                    elif isinstance(defillama_data['data']['tvl'], list) and len(defillama_data['data']['tvl']) > 0:
                        # Get the most recent TVL value if it's a time series
                        latest_tvl = defillama_data['data']['tvl'][-1]
                        if isinstance(latest_tvl, dict) and 'totalLiquidityUSD' in latest_tvl:
                            metrics['TVL'] = latest_tvl['totalLiquidityUSD']
                        elif isinstance(latest_tvl, list) and len(latest_tvl) >= 2:
                            metrics['TVL'] = latest_tvl[1]  # Assuming [timestamp, value] format
        except Exception as e:
            self.logger.error(f"Error loading defillama data: {str(e)}")
                
        return metrics if metrics else None
    
    def _extract_table_data(self, data: Dict[str, Any], section_title: str) -> Any:
        """Extract table data from the input data based on section title."""
        self.logger.info(f"Extracting table data for: {section_title}")
        
        # Check if section_title is a dictionary (which would indicate direct data)
        if isinstance(section_title, dict):
            self.logger.info("Section title is actually a data dictionary, using directly")
            return section_title
            
        # Normalize section title for matching
        section_key = section_title.lower().replace(' ', '_')
        
        # Check for section-specific extraction methods
        if "key_metrics" in section_key or "key_statistics" in section_key:
            return self._extract_key_metrics(data)
        elif "market" in section_key:
            return self._extract_market_data(data)
        elif "tokenomics" in section_key or "token_metrics" in section_key:
            return self._extract_tokenomics_data(data)
        elif "liquidity" in section_key or "volume" in section_key:
            return self._extract_liquidity_data(data)
            
        # Generic extraction approach
        # Check if data contains this section directly
        if section_key in data:
            return data[section_key]
            
        # Check if it's in a nested 'data' field
        if 'data' in data:
            if section_key in data['data']:
                return data['data'][section_key]
            
            # Try to find a closely matching key
            for key in data['data']:
                if section_key in key.lower() or key.lower() in section_key:
                    return data['data'][key]
        
        # Try to find a closely matching key at the top level
        for key in data:
            if section_key in key.lower() or key.lower() in section_key:
                return data[key]
                
        self.logger.warning(f"Could not find relevant data for section: {section_key}")
        return None
    
    def _extract_key_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics data from the input data."""
        metrics = {}
        
        # Check for common paths where key metrics might be found
        paths_to_check = [
            ('key_metrics', None),
            ('key_statistics', None),
            ('data', 'key_metrics'),
            ('data', 'key_statistics'),
            ('market_data', 'key_metrics'),
            ('price_data', None),
            ('tokenomics', 'metrics'),
            ('token', 'metrics')
        ]
        
        for path in paths_to_check:
            current_data = data
            valid_path = True
            
            # Navigate through the path
            for key in path:
                if key is None:
                    break
                    
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                else:
                    valid_path = False
                    break
            
            if valid_path and isinstance(current_data, dict):
                # Look for common metric keys
                for metric in ['market_cap', 'volume', 'supply', 'price', 'rank']:
                    self._extract_metric(current_data, metric, metrics)
                
                # If we found some metrics, return them
                if metrics:
                    break
        
        # If no metrics found, try the general data object
        if not metrics and isinstance(data, dict):
            for metric in ['market_cap', 'volume', 'supply', 'price', 'rank']:
                self._extract_metric(data, metric, metrics)
        
        return metrics
    
    def _extract_metric(self, data: Dict[str, Any], metric_base: str, target: Dict[str, Any]):
        """Helper method to extract a specific metric from various possible keys."""
        # Different ways the metric might be named
        possible_keys = [
            metric_base,
            f"{metric_base}s",
            f"{metric_base}_usd",
            f"{metric_base}_data",
            f"total_{metric_base}",
            f"circulating_{metric_base}"
        ]
        
        # Check for all possible keys
        for key in possible_keys:
            for data_key in data:
                if key.lower() in data_key.lower():
                    # Found a matching key
                    value = data[data_key]
                    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                        clean_key = data_key.replace('_', ' ').title()
                        target[clean_key] = value
                        break
    
    def _extract_market_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """Extract market data from the input data."""
        market_data = {}
        
        # Check for common paths where market data might be found
        paths_to_check = [
            ('market_data', None),
            ('data', 'market_data'),
            ('market', None),
            ('price_data', None),
            ('coingecko', 'market_data'),
            ('coinmarketcap', 'market_data')
        ]
        
        for path in paths_to_check:
            current_data = data
            valid_path = True
            
            # Navigate through the path
            for key in path:
                if key is None:
                    break
                    
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                else:
                    valid_path = False
                    break
            
            if valid_path and isinstance(current_data, dict):
                # Look for market data
                market_fields = [
                    'market_cap', 'fully_diluted_valuation', 'volume', 
                    'price', 'high', 'low', 'ath', 'atl', 'change'
                ]
                
                for field in market_fields:
                    self._extract_market_field(current_data, field, market_data)
                
                # If we found market data, format and return
                if market_data:
                    df = pd.DataFrame(list(market_data.items()), columns=['Metric', 'Value'])
                    return df
        
        # If nothing found, return empty DataFrame
        return pd.DataFrame()
    
    def _extract_market_field(self, data: Dict[str, Any], field_base: str, target: Dict[str, Any]):
        """Helper method to extract a specific market field."""
        # Different ways the field might be named
        possible_keys = [
            field_base,
            f"{field_base}_usd",
            f"{field_base}_24h",
            f"{field_base}_change",
            f"{field_base}_change_percentage",
            f"{field_base}_change_24h",
            f"{field_base}_change_percentage_24h",
            f"total_{field_base}",
            f"max_{field_base}"
        ]
        
        # Check for all possible keys
        for key in possible_keys:
            for data_key in data:
                if key.lower() in data_key.lower():
                    # Found a matching key
                    value = data[data_key]
                    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                        clean_key = data_key.replace('_', ' ').title()
                        target[clean_key] = value
    
    def _extract_tokenomics_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """Extract tokenomics data from the input data."""
        tokenomics_data = {}
        
        # Check for common paths where tokenomics data might be found
        paths_to_check = [
            ('tokenomics', None),
            ('token_metrics', None),
            ('data', 'tokenomics'),
            ('data', 'token_metrics'),
            ('supply', None),
            ('allocation', None)
        ]
        
        for path in paths_to_check:
            current_data = data
            valid_path = True
            
            # Navigate through the path
            for key in path:
                if key is None:
                    break
                    
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                else:
                    valid_path = False
                    break
            
            if valid_path and isinstance(current_data, dict):
                # Look for tokenomics data
                token_fields = [
                    'supply', 'circulating_supply', 'total_supply', 'max_supply',
                    'inflation', 'staking', 'token_type', 'algorithm'
                ]
                
                for field in token_fields:
                    self._extract_tokenomics_field(current_data, field, tokenomics_data)
                
                # If we found tokenomics data, format and return
                if tokenomics_data:
                    df = pd.DataFrame(list(tokenomics_data.items()), columns=['Metric', 'Value'])
                    return df
        
        # If nothing found, return empty DataFrame
        return pd.DataFrame()
    
    def _extract_tokenomics_field(self, data: Dict[str, Any], field_base: str, target: Dict[str, Any]):
        """Helper method to extract a specific tokenomics field."""
        # Different ways the field might be named
        possible_keys = [
            field_base,
            f"{field_base}_rate",
            f"{field_base}_percentage",
            f"token_{field_base}",
            f"initial_{field_base}"
        ]
        
        # Check for all possible keys
        for key in possible_keys:
            for data_key in data:
                if key.lower() in data_key.lower():
                    # Found a matching key
                    value = data[data_key]
                    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                        clean_key = data_key.replace('_', ' ').title()
                        target[clean_key] = value
    
    def _extract_liquidity_data(self, data: Dict[str, Any]) -> pd.DataFrame:
        """Extract liquidity and volume data from the input data."""
        liquidity_data = {}
        
        # Check for common paths where liquidity data might be found
        paths_to_check = [
            ('liquidity', None),
            ('volume', None),
            ('data', 'liquidity'),
            ('data', 'volume'),
            ('market_data', 'liquidity'),
            ('market_data', 'volume')
        ]
        
        for path in paths_to_check:
            current_data = data
            valid_path = True
            
            # Navigate through the path
            for key in path:
                if key is None:
                    break
                    
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                else:
                    valid_path = False
                    break
            
            if valid_path and isinstance(current_data, dict):
                # Look for liquidity and volume data
                liquidity_fields = [
                    'volume', 'liquidity', 'volume_24h', 'liquidity_24h',
                    'dex_volume', 'cex_volume', 'tvl'
                ]
                
                for field in liquidity_fields:
                    self._extract_liquidity_field(current_data, field, liquidity_data)
                
                # If we found liquidity data, format and return
                if liquidity_data:
                    df = pd.DataFrame(list(liquidity_data.items()), columns=['Metric', 'Value'])
                    return df
        
        # If nothing found, return empty DataFrame
        return pd.DataFrame()
    
    def _extract_liquidity_field(self, data: Dict[str, Any], field_base: str, target: Dict[str, Any]):
        """Helper method to extract a specific liquidity field."""
        # Different ways the field might be named
        possible_keys = [
            field_base,
            f"{field_base}_usd",
            f"{field_base}_change",
            f"{field_base}_change_percentage",
            f"{field_base}_change_24h",
            f"total_{field_base}",
            f"average_{field_base}"
        ]
        
        # Check for all possible keys
        for key in possible_keys:
            for data_key in data:
                if key.lower() in data_key.lower():
                    # Found a matching key
                    value = data[data_key]
                    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                        clean_key = data_key.replace('_', ' ').title()
                        target[clean_key] = value
    
    def _convert_to_dataframe(self, data: Any, section_title: str) -> pd.DataFrame:
        """Convert various data formats to a DataFrame for table visualization."""
        if isinstance(data, pd.DataFrame):
            return data
            
        if data is None or not data:
            return pd.DataFrame()
            
        try:
            if isinstance(data, dict):
                # Convert dictionary to dataframe
                if all(isinstance(v, dict) for v in data.values()):
                    # Handle nested dictionaries
                    df = pd.DataFrame.from_dict(data, orient='index')
                else:
                    # Handle flat dictionary
                    df = pd.DataFrame(list(data.items()), columns=['Metric', 'Value'])
                return df
                
            elif isinstance(data, list):
                # Handle list of dicts
                if all(isinstance(item, dict) for item in data):
                    return pd.DataFrame(data)
                
                # Handle list of lists/tuples
                if all(isinstance(item, (list, tuple)) for item in data):
                    # Determine if first row is headers
                    if all(isinstance(item[0], str) for item in data):
                        headers = [item[0] for item in data]
                        if len(set(headers)) == len(headers):  # Unique headers
                            # First column is headers
                            return pd.DataFrame({item[0]: [item[1]] for item in data})
                    
                    # Just convert to dataframe with default column names
                    return pd.DataFrame(data)
                    
            # Default empty dataframe
            return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error converting data to DataFrame: {e}")
            return pd.DataFrame()
    
    def _format_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format the DataFrame for table visualization."""
        # Format numeric columns using NumberFormatter
        for col in df.columns:
            df[col] = df[col].apply(lambda x: NumberFormatter.format_number(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x)
        
        return df

    def _load_adoption_metrics_from_cache(self) -> Dict[str, Any]:
        """Load adoption metrics data from various cache sources according to report_config.json."""
        metrics = {}
        
        # According to report_config.json, adoption metrics should come from multiple sources:
        # coinmarketcap (for exchange listings, market data) and defillama (for TVL data)
        
        # First: Load TVL and chain data from defillama
        try:
            self.logger.info(f"Loading TVL data from defillama for adoption_metrics_table of {self.project_name}")
            defillama_data = None
            defillama_dir = os.path.join("docs", self.project_name, "cache", "defillama")
            
            if os.path.exists(defillama_dir):
                # Try using cache manager first
                defillama_data = self.cache_manager.load("defillama", "tvl", self.project_name.lower())
                
                if not defillama_data:
                    # Try direct file access as backup
                    for filename in os.listdir(defillama_dir):
                        if "tvl" in filename.lower() and filename.endswith('.json'):
                            with open(os.path.join(defillama_dir, filename), 'r') as f:
                                try:
                                    data = json.load(f)
                                    defillama_data = data
                                    break
                                except json.JSONDecodeError:
                                    continue
            
            # Extract TVL and chain data if available
            if defillama_data:
                # Get TVL data
                if 'tvl' in defillama_data:
                    metrics["TVL (USD)"] = defillama_data['tvl']
                elif 'data' in defillama_data and 'tvl' in defillama_data['data']:
                    if isinstance(defillama_data['data']['tvl'], (int, float)):
                        metrics["TVL (USD)"] = defillama_data['data']['tvl']
                    elif isinstance(defillama_data['data']['tvl'], list) and len(defillama_data['data']['tvl']) > 0:
                        # Get the most recent TVL value if it's a time series
                        latest_entry = defillama_data['data']['tvl'][-1]
                        if isinstance(latest_entry, dict) and 'totalLiquidityUSD' in latest_entry:
                            metrics["TVL (USD)"] = latest_entry['totalLiquidityUSD']
                        elif isinstance(latest_entry, list) and len(latest_entry) >= 2:
                            metrics["TVL (USD)"] = latest_entry[1]  # Assuming [timestamp, value] format
                
                # Get chain distribution data
                if 'chains' in defillama_data:
                    chain_count = len(defillama_data['chains']) if isinstance(defillama_data['chains'], list) else 1
                    metrics["Blockchain Networks"] = chain_count
                elif 'data' in defillama_data and 'chains' in defillama_data['data']:
                    chain_count = len(defillama_data['data']['chains']) if isinstance(defillama_data['data']['chains'], list) else 1
                    metrics["Blockchain Networks"] = chain_count
        except Exception as e:
            self.logger.error(f"Error extracting TVL data from defillama: {e}")
        
        # Second: Load exchange and market data from coinmarketcap
        try:
            self.logger.info(f"Loading coinmarketcap data for adoption_metrics_table of {self.project_name}")
            cmc_data = None
            cmc_dir = os.path.join("docs", self.project_name, "cache", "coinmarketcap")
            
            if os.path.exists(cmc_dir):
                # Try using cache manager first
                cmc_data = self.cache_manager.load("coinmarketcap", "", self.project_name.lower())
                
                if not cmc_data:
                    # Try direct file access as backup
                    for filename in os.listdir(cmc_dir):
                        if filename.endswith('.json'):
                            with open(os.path.join(cmc_dir, filename), 'r') as f:
                                try:
                                    data = json.load(f)
                                    if 'data' in data:
                                        cmc_data = data
                                        break
                                except json.JSONDecodeError:
                                    continue
            
            # Extract exchange listings and market data if available
            if cmc_data and 'data' in cmc_data:
                # Extract exchange count
                if 'exchange_count' in cmc_data['data']:
                    metrics["Exchange Listings"] = cmc_data['data']['exchange_count']
                elif 'num_market_pairs' in cmc_data['data']:
                    metrics["Exchange Listings"] = cmc_data['data']['num_market_pairs']
                
                # Extract market data
                if 'market_cap' in cmc_data['data']:
                    metrics["Market Cap (USD)"] = cmc_data['data']['market_cap']
                elif 'market_data' in cmc_data['data'] and 'market_cap' in cmc_data['data']['market_data']:
                    metrics["Market Cap (USD)"] = cmc_data['data']['market_data']['market_cap']
                
                # Extract volume
                if 'volume_24h' in cmc_data['data']:
                    metrics["24h Volume (USD)"] = cmc_data['data']['volume_24h']
                elif 'market_data' in cmc_data['data'] and 'volume_24h' in cmc_data['data']['market_data']:
                    metrics["24h Volume (USD)"] = cmc_data['data']['market_data']['volume_24h']
                
                # Extract active addresses if available (more rare, but useful)
                if 'active_addresses' in cmc_data['data']:
                    metrics["Active Addresses"] = cmc_data['data']['active_addresses']
                elif 'active_wallets' in cmc_data['data']:
                    metrics["Active Addresses"] = cmc_data['data']['active_wallets']
        except Exception as e:
            self.logger.error(f"Error extracting market data from coinmarketcap: {e}")
        
        # If we have very limited data, add minimum reasonable defaults for testing
        if len(metrics) < 2:
            if "TVL (USD)" not in metrics:
                self.logger.warning("No TVL data found, using placeholder")
                metrics["TVL (USD)"] = "Data unavailable"
            
            if "Exchange Listings" not in metrics:
                self.logger.warning("No exchange listing data found, using placeholder")
                metrics["Exchange Listings"] = "Data unavailable"
        
        # Return metrics in a format ready for conversion to dataframe
        result = {"Metric": [], "Value": []}
        for key, value in metrics.items():
            result["Metric"].append(key)
            result["Value"].append(value)
            
        return result

def visualizer_sync(state: Dict[str, Any], section: str = "", logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for the TableVisualizer class to be used in the workflow.
    
    Args:
        state: Dictionary containing the state data including visualization data
        section: Section name for the visualization
        logger: Optional logger instance
        
    Returns:
        Updated state dictionary with visualization information
    """
    # Initialize state copy to avoid modifying the input state
    updated_state = state.copy()
    
    # Extract project name from state
    project_name = state.get("project_name", "")
    if not project_name and "context" in state and isinstance(state["context"], dict):
        project_name = state["context"].get("project_name", "unknown_project")
    
    # Set up logging
    if not logger:
        logger = logging.getLogger(__name__)
    
    logger.info(f"Running table visualizer for project: {project_name}")
    
    try:
        # Initialize visualizer
        visualizer = TableVisualizer(project_name=project_name, logger=logger)
        
        # Ensure output directory exists
        output_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract data for visualization from state
        viz_data = state.get("data", {})
        if not viz_data:
            logger.warning("No visualization data found in state")
            updated_state["errors"] = updated_state.get("errors", {})
            updated_state["errors"]["table_visualizer"] = "No visualization data found"
            return updated_state
        
        # Create the table visualization
        output_path = visualizer.create(section, {}, viz_data)
        
        if not output_path:
            logger.warning("Failed to create table visualization")
            updated_state["errors"] = updated_state.get("errors", {})
            updated_state["errors"]["table_visualizer"] = "Failed to create table visualization"
            return updated_state
        
        # Store visualization path in state
        if "visualizations" not in updated_state:
            updated_state["visualizations"] = {}
        
        viz_key = f"{section}_table"
        updated_state["visualizations"][viz_key] = output_path
        
        # Add to visualization list if it exists
        if "visualization_list" in updated_state:
            updated_state["visualization_list"].append({
                "type": "table",
                "section": section,
                "path": output_path
            })
        else:
            updated_state["visualization_list"] = [{
                "type": "table",
                "section": section,
                "path": output_path
            }]
        
        logger.info(f"Successfully created table visualization: {output_path}")
        return updated_state
        
    except Exception as e:
        logger.error(f"Error in table visualizer_sync: {str(e)}")
        
        # Add error to state
        updated_state["errors"] = updated_state.get("errors", {})
        updated_state["errors"]["table_visualizer"] = f"Table visualizer error: {str(e)}"
        
        return updated_state