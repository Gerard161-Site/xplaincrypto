import os
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List, Optional, Union, Tuple
from .base import BaseVisualizer
import logging
import matplotlib.pyplot as plt
import re
import json
import numpy as np
from datetime import datetime
import time
import traceback
import uuid
from backend.utils.cache_utils import CacheManager
from backend.utils.plotly_styler import PlotlyStyler
from backend.utils.style_utils import StyleManager

class LineChartVisualizer(BaseVisualizer):
    """Creates line chart visualizations."""

    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, logger=None):
        """Initialize the line chart visualizer with theme and project settings."""
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name or "default"
        self.logger = logger or logging.getLogger(__name__)
        self.output_dir = os.path.join("docs", self.project_name.lower()) if project_name else "docs"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize cache directory path
        self.cache_dir = os.path.join("docs", self.project_name, "cache") if project_name else "docs/cache"
        self.logger.info(f"Cache directory set to: {self.cache_dir}")
        
        # Initialize cache manager
        self.cache_manager = CacheManager(project_name=self.project_name)
        
        # Initialize plotly styler
        self.plotly_styler = PlotlyStyler(theme=theme, project_name=self.project_name, logger=self.logger)
        
        # Initialize style manager
        self.style_manager = StyleManager(logger=self.logger)
        
        # Get visualization config
        self.viz_config = self.style_manager.get_visualization_config()
        self.chart_config = self.viz_config.get("line_chart", {})
        
        # Set figure dimensions
        self.figure_config = self.viz_config.get("figure", {})
        self.width = self.figure_config.get("width", 5) * 2 * 100  # Convert from inches to pixels
        self.height = self.figure_config.get("height", 3.5) * 100  # Convert from inches to pixels
        
        # Create alias for plotly_styler to match other visualizers
        self.styler = self.plotly_styler

    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any], is_mobile: bool = False) -> Dict[str, Any]:
        """
        Create a line chart visualization based on the provided data.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            is_mobile: Whether the visualization is for mobile
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating line chart {viz_type} for {self.project_name}")
            
            # Get layout configuration based on device type
            layout_config = self.get_layout_config(is_mobile)
            
            # Get title from config
            title = config.get("title", f"{viz_type.replace('_', ' ').title()}")
            
            # Special handling for volume chart - needs its own implementation
            if "volume" in viz_type.lower():
                output_filename = f"{self.project_name.lower()}_{viz_type}"
                self.logger.info(f"Creating volume chart: {title}")
                return self._create_volume_chart(title, output_filename)
                
            # Extract data based on visualization type
            line_data = {}
            
            # Get data source and data field from config
            data_source = config.get("data_source", "")
            data_field = config.get("data_field", "")
            
            # Special handling for different visualization types
            if "price" in viz_type.lower():
                line_data = self._extract_price_data(data)
            elif "volume" in viz_type.lower():
                line_data = self._extract_volume_data(data)
            elif "market" in viz_type.lower() and "cap" in viz_type.lower():
                line_data = self._extract_marketcap_data(data)
            elif "tvl" in viz_type.lower():
                line_data = self._extract_tvl_data(data)
            elif viz_type == "candlestick_chart":
                # Candlestick chart needs OHLC data
                candlestick_data = self._load_candlestick_data_from_cache()
                if candlestick_data:
                    return self._create_candlestick_chart(candlestick_data, title, f"{self.project_name.lower()}_{viz_type}")
                else:
                    self.logger.warning(f"No candlestick data found for {viz_type}")
                    return self._create_error_chart(f"No data available for {title}", 
                                                   os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            elif viz_type == "tvl_milestone_chart":
                # Create a regular TVL chart first
                tvl_data = self._load_tvl_data_from_cache()
                if tvl_data:
                    # Plot the main line chart with tvl_data
                    if isinstance(tvl_data, list) and len(tvl_data) > 0:
                        if isinstance(tvl_data[0], list) and len(tvl_data[0]) == 2:
                            # Format is [[timestamp, value], ...]
                            x_values = [pd.to_datetime(item[0], unit='ms' if item[0] > 1e12 else 's') for item in tvl_data]
                            y_values = [item[1] for item in tvl_data]
                            
                            # Create figure
                            fig = go.Figure()
                            
                            # Add main TVL line
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='lines',
                                name='TVL',
                                line=dict(width=2, color=self.styler.theme_colors["accent"])
                            ))
                            
                            # Generate milestone annotations for specific TVL values
                            milestones = self._generate_milestone_annotations(tvl_data)
                            for milestone in milestones:
                                # Add milestone point
                                milestone_date = pd.to_datetime(milestone["date"], unit='ms' if milestone["date"] > 1e12 else 's')
                                fig.add_trace(go.Scatter(
                                    x=[milestone_date],
                                    y=[milestone["tvl"]],
                                    mode='markers',
                                    marker=dict(
                                        size=12,
                                        symbol='circle',
                                        color=self.styler.theme_colors["accent_palette"][1],
                                        line=dict(width=2, color='white')
                                    ),
                                    name=milestone["label"],
                                    showlegend=False
                                ))
                                
                                # Add annotation
                                fig.add_annotation(
                                    x=milestone_date,
                                    y=milestone["tvl"],
                                    text=milestone["label"],
                                    showarrow=True,
                                    arrowhead=2,
                                    arrowsize=1,
                                    arrowwidth=2,
                                    arrowcolor="#636363",
                                    ax=0,
                                    ay=-40,
                                    bgcolor="white",
                                    bordercolor="#c7c7c7",
                                    borderwidth=1,
                                    borderpad=4,
                                    font=dict(size=10)
                                )
                            
                            # Apply styling
                            fig = self.styler.style_line_chart(fig, x_title="Date", y_title="TVL (USD)")
                            fig = self.styler.apply_layout(
                                fig=fig,
                                title=title,
                                width=900, 
                                height=500,
                                showlegend=True
                            )
                            
                            # Add source
                            fig = self.styler.add_source_annotation(
                                fig, 
                                source=config.get("source", "DeFiLlama")
                            )
                            
                            # Save the chart
                            output_path = os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
                            fig.write_image(output_path, scale=2)
                            
                            return {
                                "success": True,
                                "file_path": output_path,
                                "title": title
                            }
                    
                    self.logger.warning(f"Could not process TVL data for milestones chart: {tvl_data[:5]}")
                    return self._create_error_chart(f"Could not process data for {title}", 
                                                   os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
                else:
                    self.logger.warning(f"No TVL data found for {viz_type}")
                    return self._create_error_chart(f"No data available for {title}", 
                                                   os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            elif viz_type == "tvl_phases_chart":
                tvl_data = self._load_tvl_data_from_cache()
                # Process data to show growth phases
                line_data = self._process_tvl_phases(tvl_data)
                
            elif viz_type == "monthly_growth_chart":
                line_data = self._load_growth_data_from_cache()
                
            elif "liquidity_trends" in viz_type.lower():
                # Load data from cache
                liquidity_data = self._load_liquidity_data_from_cache()
                
                # Use liquidity_data to make the chart
                if isinstance(liquidity_data, list) and len(liquidity_data) > 0:
                    if isinstance(liquidity_data[0], list) and len(liquidity_data[0]) == 2:
                        # Format is [[timestamp, value], ...]
                        x_values = [pd.to_datetime(item[0], unit='ms' if item[0] > 1e12 else 's') for item in liquidity_data]
                        y_values = [item[1] for item in liquidity_data]
                        
                        # Create figure
                        fig = go.Figure()
                        
                        # Add main line
                        fig.add_trace(go.Scatter(
                            x=x_values,
                            y=y_values,
                            mode='lines',
                            name='Liquidity',
                            line=dict(width=2, color=self.styler.theme_colors["accent"])
                        ))
                        
                        # Calculate and add 30-day moving average
                        if len(y_values) > 30:
                            values_series = pd.Series(y_values)
                            ma30 = values_series.rolling(window=30).mean()
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=ma30,
                                mode='lines',
                                name='30-Day MA',
                                line=dict(
                                    width=2, 
                                    color=self.styler.theme_colors["accent_palette"][1], 
                                    dash='dash'
                                )
                            ))
                        
                        # Apply styling
                        fig = self.styler.style_line_chart(fig, x_title="Date", y_title="Liquidity (USD)")
                        fig = self.styler.apply_layout(
                            fig=fig,
                            title=title,
                            width=900, 
                            height=500,
                            showlegend=True
                        )
                        
                        # Add source and note
                        fig = self.styler.add_source_annotation(
                            fig, 
                            source=config.get("source", "DeFiLlama")
                        )
                        
                        fig = self.styler.add_note_annotation(
                            fig,
                            note="Liquidity is measured as Total Value Locked (TVL)"
                        )
                        fig.update_layout(margin=dict(b=100))
                        
                        # Save the chart
                        output_path = os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
                        fig.write_image(output_path, scale=2)
                        
                        return {
                            "success": True,
                            "file_path": output_path,
                            "title": title
                        }
                
                self.logger.warning(f"No liquidity data found for {viz_type}")
                return self._create_error_chart(f"No data available for {title}", 
                                               os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            else:
                # Generic line chart, extract data from the provided data object
                line_data = self._extract_line_data(data, viz_type)
            
            # If no specific data could be extracted, use the data directly or check cache
            if not line_data and data_source:
                line_data = self.cache_manager.load(data_source, viz_type, self.project_name.lower())
                
                if not line_data and data_field:
                    # Try to load with data_field
                    line_data = self.cache_manager.load(data_source, data_field, self.project_name.lower())
            
            if not line_data:
                self.logger.warning(f"No data found for {viz_type}")
                return self._create_error_chart(f"No data available for {title}", 
                                               os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            
            # Convert data to DataFrame if it's not already
            df = self._convert_to_dataframe(line_data)
            
            if df is None or df.empty:
                self.logger.warning(f"Failed to convert {viz_type} data to DataFrame")
                return self._create_error_chart(f"Could not process data for {title}", 
                                               os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            
            # Get date and value columns
            date_col = self._get_date_column(df, config)
            value_col = self._get_value_column(df, config)
            
            if not date_col or not value_col:
                self.logger.warning(f"Could not identify date or value columns for {viz_type}")
                return self._create_error_chart(f"Could not identify date or value columns for {title}", 
                                               os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))
            
            # Create the figure
            fig = go.Figure()
            
            # Add main line trace
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[value_col],
                mode='lines',
                name=value_col.replace('_', ' ').title(),
                line=dict(width=2, color=self.styler.theme_colors["accent"])
            ))
            
            # Special formatting for monthly growth chart
            if viz_type == "monthly_growth_chart":
                # Format y-axis as percentage for growth chart
                fig.update_yaxes(
                    tickformat=".1%"
                )
                
                # Add zero line with different styling
                fig.add_shape(
                    type="line",
                    x0=df[date_col].min(),
                    y0=0,
                    x1=df[date_col].max(),
                    y1=0,
                    line=dict(
                        color="red",
                        width=1,
                        dash="dot",
                    )
                )
            
            # Style the chart
            x_title = "Date"
            y_title = value_col.replace('_', ' ').title() if value_col else None
            
            # Override y_title for specific chart types
            if viz_type == "price_chart":
                y_title = "Price (USD)"
            elif viz_type == "volume_chart":
                y_title = "Volume (USD)"
            elif viz_type == "marketcap_chart":
                y_title = "Market Cap (USD)"
            elif viz_type == "tvl_chart" or viz_type == "tvl_phases_chart":
                y_title = "TVL (USD)"
            elif viz_type == "monthly_growth_chart":
                y_title = "Monthly Growth Rate (%)"
            
            # Apply styling
            fig = self.styler.style_line_chart(fig, x_title=x_title, y_title=y_title)
            fig = self.styler.apply_layout(
                fig=fig,
                title=title,
                width=900, 
                height=500,
                showlegend=True if len(fig.data) > 1 else False
            )
            
            # Add source attribution
            if data_source:
                source_name = data_source.capitalize()
                fig = self.styler.add_source_annotation(fig, source=config.get("source", source_name))
            
            # Save the chart
            output_path = os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            fig.write_image(output_path, scale=2)
            
            return {
                "success": True,
                "file_path": output_path,
                "title": title
            }
            
        except Exception as e:
            self.logger.error(f"Error creating line chart: {str(e)}")
            traceback.print_exc()
            return self._create_error_chart(f"Error: {str(e)}", 
                                           os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png"))

    def _load_volume_data_from_cache(self) -> Optional[Dict[str, Any]]:
        """Load volume data from cache files."""
        volume_data = None
        
        try:
            # First look in coinmarketcap cache
            coinmarketcap_dir = os.path.join("docs", self.project_name, "cache", "coinmarketcap")
            if os.path.exists(coinmarketcap_dir):
                for filename in os.listdir(coinmarketcap_dir):
                    if "volume" in filename.lower() and filename.endswith('.json'):
                        with open(os.path.join(coinmarketcap_dir, filename), 'r') as f:
                            try:
                                data = json.load(f)
                                if 'data' in data:
                                    volume_data = data['data']
                                    self.logger.info(f"Found volume data in {filename}")
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    # Also check in price/market data files
                    if ("price" in filename.lower() or "market" in filename.lower()) and filename.endswith('.json'):
                        with open(os.path.join(coinmarketcap_dir, filename), 'r') as f:
                            try:
                                data = json.load(f)
                                if 'data' in data:
                                    # See if volume data is in this file
                                    if isinstance(data['data'], dict):
                                        for key, value in data['data'].items():
                                            if isinstance(value, dict) and ('volume_24h' in value or 'volume' in value):
                                                # Found volume data
                                                volume_data = data['data']
                                                self.logger.info(f"Found volume data in {filename}")
                                                break
                            except json.JSONDecodeError:
                                continue
            
            # If still no data, try coingecko
            if not volume_data:
                coingecko_dir = os.path.join("docs", self.project_name, "cache", "coingecko")
                if os.path.exists(coingecko_dir):
                    for filename in os.listdir(coingecko_dir):
                        if ("volume" in filename.lower() or "market" in filename.lower() or "price" in filename.lower()) and filename.endswith('.json'):
                            with open(os.path.join(coingecko_dir, filename), 'r') as f:
                                try:
                                    data = json.load(f)
                                    # Check various CoinGecko data formats
                                    if 'total_volumes' in data:
                                        # This is a time series of volumes
                                        volume_data = data
                                        self.logger.info(f"Found volume data in {filename}")
                                        break
                                    elif 'market_data' in data and 'total_volume' in data['market_data']:
                                        # This is a coin details with volume
                                        volume_data = data
                                        self.logger.info(f"Found volume data in {filename}")
                                        break
                                except json.JSONDecodeError:
                                    continue
            
            return volume_data
            
        except Exception as e:
            self.logger.error(f"Error loading volume data: {str(e)}")
            traceback.print_exc()
            return None
    
    def _load_tvl_data_from_cache(self) -> Optional[Dict[str, Any]]:
        """Load TVL data from cache files."""
        tvl_data = None
        
        try:
            # Try to load from cache manager
            defillama_data = self.cache_manager.load("defillama", "tvl", self.project_name.lower())
            
            if not defillama_data:
                # Try direct file access
                defillama_dir = os.path.join("docs", self.project_name, "cache", "defillama")
                if os.path.exists(defillama_dir):
                    for filename in os.listdir(defillama_dir):
                        if not filename.endswith('.json'):
                            continue
                            
                        with open(os.path.join(defillama_dir, filename), 'r') as f:
                            try:
                                data = json.load(f)
                                if 'data' in data:
                                    # Check for tvl data
                                    if 'tvl' in data['data'] and isinstance(data['data']['tvl'], list):
                                        tvl_data = data['data']['tvl']
                                        break
                                    elif 'tvl_history' in data['data'] and isinstance(data['data']['tvl_history'], list):
                                        tvl_data = data['data']['tvl_history']
                                        break
                                    # If tvl is a dictionary with date:value pairs
                                    elif 'tvl' in data['data'] and isinstance(data['data']['tvl'], dict):
                                        # Convert to list of dictionaries
                                        tvl_data = []
                                        for date, value in data['data']['tvl'].items():
                                            tvl_data.append({
                                                'date': date,
                                                'tvl': value
                                            })
                                        break
                            except json.JSONDecodeError:
                                continue
            else:
                # Data found through cache manager
                if 'data' in defillama_data:
                    if 'tvl' in defillama_data['data'] and isinstance(defillama_data['data']['tvl'], list):
                        tvl_data = defillama_data['data']['tvl']
                    elif 'tvl_history' in defillama_data['data'] and isinstance(defillama_data['data']['tvl_history'], list):
                        tvl_data = defillama_data['data']['tvl_history']
                    # If tvl is a dictionary with date:value pairs
                    elif 'tvl' in defillama_data['data'] and isinstance(defillama_data['data']['tvl'], dict):
                        # Convert to list of dictionaries
                        tvl_data = []
                        for date, value in defillama_data['data']['tvl'].items():
                            tvl_data.append({
                                'date': date,
                                'tvl': value
                            })
        except Exception as e:
            self.logger.error(f"Error loading TVL data from defillama cache: {str(e)}")
        
        # If we found no real data, create sample data for testing
        if not tvl_data:
            self.logger.warning("No TVL data found, generating sample data")
            # Generate sample data for testing
            today = datetime.now()
            tvl_data = []
            
            # Start with $1M and increase gradually
            tvl = 1000000
            
            # Generate 90 days of sample data
            for i in range(90):
                date = today - pd.Timedelta(days=i)
                # Random percent change between -2% and +5%
                change = np.random.uniform(-0.02, 0.05)
                tvl = tvl * (1 + change)
                tvl_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'tvl': tvl
                })
                
            # Reverse to get chronological order
            tvl_data.reverse()
            
        return tvl_data
    
    def _load_growth_data_from_cache(self) -> Optional[Dict[str, Any]]:
        """Load monthly growth data from cache files."""
        # For monthly growth charts, we'll derive growth rates from TVL data
        try:
            # First, try to load the raw DeFiLlama data
            defillama_data = None
            defillama_dir = os.path.join("docs", self.project_name, "cache", "defillama")
            
            if os.path.exists(defillama_dir):
                for filename in os.listdir(defillama_dir):
                    if "tvl" in filename.lower() and filename.endswith('.json'):
                        with open(os.path.join(defillama_dir, filename), 'r') as f:
                            try:
                                raw_data = json.load(f)
                                # Check for different TVL data formats
                                if 'tvl_history' in raw_data:
                                    defillama_data = raw_data['tvl_history']
                                    self.logger.info(f"Found TVL history data in {filename}")
                                    break
                                elif 'data' in raw_data and 'tvl' in raw_data['data']:
                                    defillama_data = raw_data['data']['tvl']
                                    self.logger.info(f"Found TVL data in {filename}")
                                    break
                            except json.JSONDecodeError:
                                self.logger.warning(f"Failed to parse JSON from {filename}")
                                continue
            
            if defillama_data:
                # Process based on data format
                if isinstance(defillama_data, list):
                    if len(defillama_data) > 0:
                        if isinstance(defillama_data[0], list) and len(defillama_data[0]) == 2:
                            # Format is [[timestamp, value], ...]
                            df = pd.DataFrame(defillama_data, columns=['date', 'tvl'])
                            # Convert timestamp to datetime (timestamps could be in seconds or milliseconds)
                            if df['date'].iloc[0] > 1e12:  # Milliseconds
                                df['date'] = pd.to_datetime(df['date'], unit='ms')
                            else:  # Seconds
                                df['date'] = pd.to_datetime(df['date'], unit='s')
                        elif isinstance(defillama_data[0], dict) and 'date' in defillama_data[0]:
                            # Format is [{'date': date, 'totalLiquidityUSD': value}, ...]
                            df = pd.DataFrame(defillama_data)
                            # Find the value column
                            value_cols = [col for col in df.columns if col != 'date' and 'liquid' in col.lower() or 'tvl' in col.lower() or 'value' in col.lower()]
                            if value_cols:
                                value_col = value_cols[0]
                                df = df.rename(columns={value_col: 'tvl'})
                            # Convert timestamp if needed
                            if pd.api.types.is_numeric_dtype(df['date']):
                                if df['date'].iloc[0] > 1e12:  # Milliseconds
                                    df['date'] = pd.to_datetime(df['date'], unit='ms')
                                else:  # Seconds
                                    df['date'] = pd.to_datetime(df['date'], unit='s')
                            else:
                                df['date'] = pd.to_datetime(df['date'])
                        else:
                            self.logger.warning("Unrecognized TVL data format")
                            return None
                    else:
                        self.logger.warning("Empty TVL data list")
                        return None
                else:
                    self.logger.warning("TVL data is not a list")
                    return None
                
                # Create month column for aggregation
                df['month'] = df['date'].dt.strftime('%Y-%m')
                
                # Calculate monthly average TVL
                monthly_tvl = df.groupby('month')['tvl'].mean().reset_index()
                
                # Sort by month to ensure chronological order
                monthly_tvl = monthly_tvl.sort_values('month')
                
                # Calculate month-over-month growth rate
                monthly_tvl['previous'] = monthly_tvl['tvl'].shift(1)
                monthly_tvl['growth_rate'] = (monthly_tvl['tvl'] - monthly_tvl['previous']) / monthly_tvl['previous']
                
                # Drop first row (no growth rate available)
                monthly_tvl = monthly_tvl.dropna().reset_index(drop=True)
                
                # Convert month string back to a date (first day of the month)
                monthly_tvl['date'] = pd.to_datetime(monthly_tvl['month'] + '-01')
                
                # Keep only date and growth_rate columns for the final result
                growth_data = monthly_tvl[['date', 'growth_rate']]
                
                self.logger.info(f"Calculated monthly growth rates from {len(df)} data points")
                return growth_data.to_dict('records')
            else:
                self.logger.warning("No TVL data found in cache")
                return None
                
        except Exception as e:
            self.logger.error(f"Error calculating growth data: {str(e)}")
            traceback.print_exc()
            return None

    def _create_error_chart(self, message: str, layout_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an error chart with a message.
        
        Args:
            message: Error message to display
            layout_config: Layout configuration
            
        Returns:
            Dict with visualization result information
        """
        try:
            # Create a blank figure with error message
            fig = go.Figure()
            
            # Add error annotation
            fig.add_annotation(
                text=message,
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(
                    family="Arial, sans-serif",
                    size=14,
                    color="#E15759"  # Error red color
                )
            )
            
            # Update layout
            fig.update_layout(
                height=layout_config["height"],
                width=layout_config["width"],
                paper_bgcolor=self.theme_colors['background'],
                plot_bgcolor=self.theme_colors['background'],
                margin=layout_config["margin"]
            )
            
            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Save error chart
            error_filename = f"error_chart_{int(time.time())}.png"
            error_path = os.path.join(self.output_dir, error_filename)
            fig.write_image(error_path)
            
            return {
                "success": False,
                "error": message,
                "output_path": error_path,
                "filename": error_filename
            }
        except Exception as e:
            self.logger.error(f"Error creating error chart: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to create error chart: {str(e)}"
            }
            
    def _get_date_column(self, df: pd.DataFrame, config: Dict[str, Any]) -> Optional[str]:
        """
        Identify the date column in the DataFrame.
        
        Args:
            df: DataFrame to analyze
            config: Configuration that might specify the date column
            
        Returns:
            Name of the date column or None if not found
        """
        # Check if specified in config
        if config.get("date_column") and config["date_column"] in df.columns:
            return config["date_column"]
            
        # Check for common date column names
        date_columns = ["date", "timestamp", "time", "datetime", "day", "period"]
        for col in date_columns:
            if col in df.columns:
                return col
                
        # Check for columns with datetime objects
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
                
        # Last resort: Check if any column name contains date-related terms
        for col in df.columns:
            if any(date_term in str(col).lower() for date_term in ["date", "time", "day", "period"]):
                return col
                
        return None
        
    def _get_value_column(self, df: pd.DataFrame, config: Dict[str, Any]) -> Optional[str]:
        """
        Identify the value column in the DataFrame.
        
        Args:
            df: DataFrame to analyze
            config: Configuration that might specify the value column
            
        Returns:
            Name of the value column or None if not found
        """
        # Check if specified in config
        if config.get("value_column") and config["value_column"] in df.columns:
            return config["value_column"]
            
        # Check for common value column names
        value_columns = ["value", "price", "amount", "total", "tvl", "totalLiquidityUSD", "usd", "volume"]
        for col in value_columns:
            if col in df.columns:
                return col
                
        # Check for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        # Exclude columns that look like dates (if they're numeric)
        date_like_cols = [col for col in numeric_cols if "date" in str(col).lower() or "time" in str(col).lower()]
        potential_value_cols = [col for col in numeric_cols if col not in date_like_cols]
        
        if potential_value_cols:
            return potential_value_cols[0]
            
        # If we still don't have a value column but have numeric columns, use the first one
        if numeric_cols.any():
            return numeric_cols[0]
            
        return None

    def get_layout_config(self, is_mobile: bool = False) -> Dict[str, Any]:
        """Get layout configuration based on device type."""
        chart_sizes = self.viz_config.get("chart_sizes", {})
        if is_mobile:
            mobile_sizes = chart_sizes.get("mobile", {})
            return {
                "width": mobile_sizes.get("width", 350),
                "height": mobile_sizes.get("height", 250)
            }
        else:
            desktop_sizes = chart_sizes.get("desktop", {})
            return {
                "width": desktop_sizes.get("width", self.width),
                "height": desktop_sizes.get("height", self.height)
            }

    def _extract_line_data(self, data: Dict[str, Any], viz_type: str) -> Any:
        """Extract line chart data from the input data based on visualization type."""
        self.logger.info(f"Extracting line data for: {viz_type}")
        
        # Normalize chart type for matching
        chart_type = viz_type.lower().replace(' ', '_')
        
        # Check for visualization-specific extraction methods
        if "price" in chart_type:
            return self._extract_price_data(data)
        elif "volume" in chart_type:
            return self._extract_volume_data(data)
        elif "market_cap" in chart_type:
            return self._extract_marketcap_data(data)
        elif "tvl" in chart_type or "liquidity" in chart_type:
            return self._extract_tvl_data(data)
            
        # Generic extraction approach
        # Check if data contains this specific visualization type
        if viz_type in data:
            return data[viz_type]
            
        # Check if it's in a nested 'data' field
        if 'data' in data:
            if viz_type in data['data']:
                return data['data'][viz_type]
            
            # Try to find a closely matching key
            for key in data['data']:
                if viz_type in key or key in viz_type:
                    return data['data'][key]
        
        # Try to find a closely matching key at the top level
        for key in data:
            if viz_type in key or key in viz_type:
                return data[key]
        
        self.logger.warning(f"Could not find relevant data for visualization: {viz_type}")
        return None
    
    def _extract_price_data(self, data: Dict[str, Any]) -> Any:
        """Extract price data from various potential sources."""
        # Check common paths where price data might be found
        paths_to_check = [
            ('price_data', None),
            ('data', 'price_data'),
            ('prices', None),
            ('coingecko', 'prices'),
            ('coingecko', 'market_data', 'prices'),
            ('coinmarketcap', 'prices'),
            ('market_data', 'price_history')
        ]
        
        return self._check_data_paths(data, paths_to_check)
    
    def _extract_volume_data(self, data: Dict[str, Any]) -> Any:
        """Extract volume data from various potential sources."""
        # Check common paths where volume data might be found
        paths_to_check = [
            ('volume_data', None),
            ('data', 'volume_data'),
            ('volumes', None),
            ('coingecko', 'volumes'),
            ('coingecko', 'market_data', 'volumes'),
            ('coinmarketcap', 'volumes'),
            ('market_data', 'volume_history')
        ]
        
        return self._check_data_paths(data, paths_to_check)
    
    def _extract_marketcap_data(self, data: Dict[str, Any]) -> Any:
        """Extract market cap data from various potential sources."""
        # Check common paths where market cap data might be found
        paths_to_check = [
            ('marketcap_data', None),
            ('market_cap_data', None),
            ('data', 'marketcap_data'),
            ('data', 'market_cap_data'),
            ('market_caps', None),
            ('coingecko', 'market_caps'),
            ('coingecko', 'market_data', 'market_caps'),
            ('coinmarketcap', 'market_caps'),
            ('market_data', 'marketcap_history')
        ]
        
        return self._check_data_paths(data, paths_to_check)
    
    def _extract_tvl_data(self, data: Dict[str, Any]) -> Any:
        """Extract TVL data from various potential sources."""
        # Special case: Check if this is a DeFiLlama TVL data format
        if isinstance(data, dict) and 'data' in data and 'tvl' in data['data'] and isinstance(data['data']['tvl'], list):
            self.logger.info("Detected DeFiLlama TVL data format")
            return data['data']['tvl']
        
        # Otherwise continue with standard path checks
        paths_to_check = [
            ('tvl_data', None),
            ('data', 'tvl_data'),
            ('tvl', None),
            ('data', 'tvl'),
            ('liquidity_data', None),
            ('data', 'liquidity_data'),
            ('defillama', 'tvl'),
            ('defillama', 'tvl_history')
        ]
        
        return self._check_data_paths(data, paths_to_check)
    
    def _check_data_paths(self, data: Dict[str, Any], paths_to_check: List[tuple]) -> Any:
        """Helper method to check multiple potential data paths."""
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
            
            if valid_path and (
                isinstance(current_data, dict) or 
                isinstance(current_data, list) or 
                isinstance(current_data, pd.DataFrame)
            ):
                return current_data
                
        # No valid paths found, try to load from cache if data has a cache_file property
        if isinstance(data, dict) and 'cache_file' in data:
            cache_file = data['cache_file']
            try:
                if os.path.exists(cache_file):
                    self.logger.info(f"Loading data from cache file: {cache_file}")
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    return cache_data
            except Exception as e:
                self.logger.error(f"Error loading cache file: {e}")
        
        return None
    
    def _convert_to_dataframe(self, data: Any) -> Optional[pd.DataFrame]:
        """
        Convert various data formats to a pandas DataFrame suitable for line charts.
        
        Handles multiple formats:
        - List of dictionaries
        - Nested dictionaries (CoinGecko, CoinMarketCap formats)
        - Simple key-value pairs
        - List of [timestamp, value] pairs (DeFiLlama format)
        
        Args:
            data: Input data in various formats
            
        Returns:
            Pandas DataFrame or None if conversion fails
        """
        try:
            # Extract the data from the input
            if not data:
                self.logger.warning("Empty data provided to _convert_to_dataframe")
                return None
            
            # If data is already a DataFrame, return it
            if isinstance(data, pd.DataFrame):
                self.logger.info("Data is already a DataFrame")
                return data
            
            # Get line_data
            line_data = None
            if isinstance(data, dict) and 'data' in data:
                line_data = data['data']
            else:
                line_data = data
            
            if not line_data:
                self.logger.warning("No valid data available")
                return None
            
            # Handle different formats
            df = None
            
            # Case 1: List of dictionaries (most common format)
            if isinstance(line_data, list):
                self.logger.info("Converting list data to DataFrame")
                if all(isinstance(item, dict) for item in line_data):
                    df = pd.DataFrame(line_data)
                else:
                    # It's a list but not of dictionaries
                    if len(line_data) > 0 and all(isinstance(x, (int, float, str)) for x in line_data):
                        # List of values - create a simple DataFrame with index as x
                        df = pd.DataFrame({
                            'index': list(range(len(line_data))),
                            'value': line_data
                        })
                    elif len(line_data) > 0 and all(isinstance(x, list) for x in line_data):
                        # List of lists - try to interpret as [timestamp, value] pairs (DeFiLlama format)
                        if all(len(x) >= 2 for x in line_data):
                            # This is likely a timestamp, value pair format
                            dates = [x[0] for x in line_data]
                            values = [x[1] for x in line_data]
                            
                            # Check if timestamps are in milliseconds (large numbers) or seconds
                            if all(isinstance(d, (int, float)) for d in dates):
                                # Convert timestamps to datetime
                                if all(d > 1000000000000 for d in dates):  # Milliseconds
                                    dates = pd.to_datetime(dates, unit='ms')
                                else:  # Seconds
                                    dates = pd.to_datetime(dates, unit='s')
                                    
                            df = pd.DataFrame({
                                'date': dates,
                                'value': values
                            })
            
            # Case 2: Dictionary format (CoinGecko, CoinMarketCap, etc.)
            elif isinstance(line_data, dict):
                self.logger.info("Converting dictionary data to DataFrame")
                
                # Case 2.1: CoinGecko price format {timestamp: price}
                if all(isinstance(k, (str, int)) and isinstance(v, (int, float)) for k, v in line_data.items()):
                    self.logger.info("Detected timestamp:price dictionary format")
                    # Simple time series data
                    df = pd.DataFrame({
                        'date': list(line_data.keys()),
                        'value': list(line_data.values())
                    })
                
                # Case 2.2: Nested dictionary format (common in crypto APIs)
                elif any(isinstance(v, dict) for v in line_data.values()):
                    self.logger.info("Detected nested dictionary format")
                    # Try to flatten the nested structure
                    flat_data = {}
                    
                    # CoinGecko market_data format
                    if 'market_data' in line_data and isinstance(line_data['market_data'], dict):
                        self.logger.info("Detected CoinGecko market_data format")
                        market_data = line_data['market_data']
                        
                        # CoinGecko price history format
                        if 'current_price' in market_data and isinstance(market_data['current_price'], dict):
                            flat_data = {
                                'date': pd.Timestamp.now(),
                                'value': market_data['current_price'].get('usd', 0)
                            }
                        # Other nested CoinGecko formats
                        else:
                            for key, value in market_data.items():
                                if not isinstance(value, dict):
                                    flat_data[key] = value
                    
                    # CoinMarketCap format
                    elif 'data' in line_data and isinstance(line_data['data'], dict):
                        self.logger.info("Detected CoinMarketCap data format")
                        coin_data = line_data['data']
                        
                        # Flatten first-level dict
                        for key, value in coin_data.items():
                            if not isinstance(value, dict):
                                flat_data[key] = value
                            elif key == 'quote' and isinstance(value, dict) and 'USD' in value:
                                # Special handling for CoinMarketCap quote.USD structure
                                for usd_key, usd_value in value['USD'].items():
                                    flat_data[usd_key] = usd_value
                    
                    # General case for nested dictionaries
                    else:
                        for key, value in line_data.items():
                            if not isinstance(value, dict):
                                flat_data[key] = value
                            else:
                                # For nested dictionaries, flatten one level with dot notation
                                for subkey, subvalue in value.items():
                                    if not isinstance(subvalue, (dict, list)):
                                        flat_data[f"{key}.{subkey}"] = subvalue
                    
                    if flat_data:
                        df = pd.DataFrame([flat_data])
                
                # Case 2.3: Dictionary of lists (time series data)
                elif any(isinstance(v, list) for v in line_data.values()):
                    self.logger.info("Detected dictionary of lists format")
                    # If the values are lists of the same length, create a DataFrame
                    lengths = [len(v) for v in line_data.values() if isinstance(v, list)]
                    if lengths and all(l == lengths[0] for l in lengths):
                        df = pd.DataFrame(line_data)
                
                # Case 2.4: Simple key-value pairs
                else:
                    # Convert dictionary to dataframe with keys as one column and values as another
                    df = pd.DataFrame({
                        'key': list(line_data.keys()),
                        'value': list(line_data.values())
                    })
            
            # If conversion failed or resulted in an empty DataFrame
            if df is None or df.empty:
                self.logger.warning("Conversion resulted in None or empty DataFrame")
                return None
            
            # Try to convert string date columns to datetime
            for col in df.columns:
                if col.lower() in ['date', 'time', 'timestamp', 'datetime']:
                    try:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                    except Exception as e:
                        self.logger.warning(f"Failed to convert {col} to datetime: {str(e)}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error converting data to DataFrame: {str(e)}")
            traceback.print_exc()
            return None

    def _process_tvl_phases(self, tvl_data: Any) -> List[Dict[str, Any]]:
        """Process TVL data to identify distinct growth phases."""
        try:
            # Convert tvl_data to DataFrame for analysis
            df = None
            
            # Handle different TVL data formats
            if isinstance(tvl_data, list):
                if len(tvl_data) > 0:
                    if isinstance(tvl_data[0], list) and len(tvl_data[0]) == 2:
                        # Format is [[timestamp, value], ...]
                        df = pd.DataFrame(tvl_data, columns=['date', 'tvl'])
                        # Convert timestamp to datetime
                        if df['date'].iloc[0] > 1e12:  # milliseconds
                            df['date'] = pd.to_datetime(df['date'], unit='ms')
                        else:  # seconds
                            df['date'] = pd.to_datetime(df['date'], unit='s')
                    elif isinstance(tvl_data[0], dict):
                        # Format is [{'date': date, 'totalLiquidityUSD': value}, ...]
                        df = pd.DataFrame(tvl_data)
                        # Find the value column
                        value_cols = [col for col in df.columns if col != 'date' and ('liquid' in col.lower() or 'tvl' in col.lower() or 'value' in col.lower())]
                        if value_cols:
                            df = df.rename(columns={value_cols[0]: 'tvl'})
                        else:
                            self.logger.warning("Could not identify TVL column in data")
                            return []
                        
                        # Convert date column to datetime if needed
                        if pd.api.types.is_numeric_dtype(df['date']):
                            if df['date'].iloc[0] > 1e12:  # Milliseconds
                                df['date'] = pd.to_datetime(df['date'], unit='ms')
                            else:  # Seconds
                                df['date'] = pd.to_datetime(df['date'], unit='s')
                        else:
                            df['date'] = pd.to_datetime(df['date'])
            
            if df is None or len(df) < 10:
                self.logger.warning("Insufficient TVL data for phase analysis")
                return []
                
            # Sort by date
            df = df.sort_values('date')
            
            # Calculate log returns for TVL (better for identifying phases)
            df['log_tvl'] = np.log(df['tvl'])
            df['log_return'] = df['log_tvl'].diff()
            
            # Smooth the returns to reduce noise
            df['smooth_return'] = df['log_return'].rolling(window=7, min_periods=1).mean()
            
            # Use changepoint detection to identify phases
            try:
                from ruptures.detection import Pelt
                from ruptures.costs import CostL2
                
                # Prepare data for changepoint detection
                signal = df['smooth_return'].fillna(0).values.reshape(-1, 1)
                
                # Detect changepoints
                model = Pelt(model="l2", min_size=30)  # min_size = minimum phase length of 30 days
                result = model.fit_predict(signal, pen=0.5)
                
                # Get the changepoints indices
                changepoints = result[:-1]  # Last point is just the length of the signal
            except ImportError:
                # Fallback if ruptures is not available: simple rolling window method
                window_size = 30
                threshold = 2.0  # Standard deviations
                
                # Calculate rolling mean and std
                df['roll_mean'] = df['smooth_return'].rolling(window=window_size, min_periods=1).mean()
                df['roll_std'] = df['smooth_return'].rolling(window=window_size, min_periods=1).std()
                
                # Identify potential changepoints (where return exceeds threshold stds from mean)
                potential_changes = df[abs(df['smooth_return'] - df['roll_mean']) > threshold * df['roll_std']].index.tolist()
                
                # Only keep changes that are at least window_size apart
                changepoints = []
                if potential_changes:
                    changepoints = [potential_changes[0]]
                    for idx in potential_changes[1:]:
                        if idx - changepoints[-1] >= window_size:
                            changepoints.append(idx)
            
            # If too many changepoints, keep only the most significant ones (maximum 5)
            if len(changepoints) > 5:
                # Calculate changes in trend at each changepoint
                change_magnitude = []
                for cp in changepoints:
                    if cp < window_size or cp >= len(df) - window_size:
                        change_magnitude.append(0)
                        continue
                    
                    before = df.iloc[cp-window_size:cp]['smooth_return'].mean()
                    after = df.iloc[cp:cp+window_size]['smooth_return'].mean()
                    change_magnitude.append(abs(after - before))
                
                # Keep the top 5 changepoints by magnitude
                top_indices = np.argsort(change_magnitude)[-5:]
                changepoints = [changepoints[i] for i in sorted(top_indices)]
            
            # Define phases based on changepoints
            phases = []
            start_idx = 0
            
            # Convert changepoints from indices to dates
            changepoint_dates = [df.iloc[cp]['date'] for cp in changepoints if cp < len(df)]
            
            # Add end of data
            all_boundaries = [df.iloc[0]['date']] + changepoint_dates + [df.iloc[-1]['date']]
            
            # Create phases
            for i in range(len(all_boundaries) - 1):
                start_date = all_boundaries[i]
                end_date = all_boundaries[i+1]
                
                # Calculate average growth rate during this phase
                phase_data = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                
                if len(phase_data) < 2:
                    continue
                
                start_tvl = phase_data.iloc[0]['tvl']
                end_tvl = phase_data.iloc[-1]['tvl']
                
                # Calculate compound growth rate
                days = (end_date - start_date).days
                if days <= 0 or start_tvl <= 0:
                    continue
                
                # Compound Annual Growth Rate formula
                if end_tvl > 0:
                    cagr = ((end_tvl / start_tvl) ** (365.0 / max(days, 1))) - 1
                else:
                    cagr = -1  # Decline to zero
                
                # Determine phase type based on CAGR
                if cagr > 0.5:
                    phase_type = "Hypergrowth"
                    color = "#3D9970"  # Green
                elif cagr > 0.1:
                    phase_type = "Growth"
                    color = "#2ECC40"  # Light green
                elif cagr > -0.1:
                    phase_type = "Stability"
                    color = "#FFDC00"  # Yellow
                elif cagr > -0.5:
                    phase_type = "Decline"
                    color = "#FF851B"  # Orange
                else:
                    phase_type = "Contraction"
                    color = "#FF4136"  # Red
                
                phases.append({
                    "start_date": start_date,
                    "end_date": end_date, 
                    "growth_rate": cagr,
                    "phase_type": phase_type,
                    "color": color,
                    "start_tvl": start_tvl,
                    "end_tvl": end_tvl
                })
            
            self.logger.info(f"Identified {len(phases)} TVL growth phases")
            return phases
            
        except Exception as e:
            self.logger.error(f"Error processing TVL phases: {str(e)}")
            traceback.print_exc()
            return []
        
    def _generate_milestone_annotations(self, tvl_data: Any) -> List[Dict[str, Any]]:
        """Generate milestone annotations for significant TVL values."""
        try:
            # Convert tvl_data to DataFrame for analysis
            df = None
            
            # Handle different TVL data formats
            if isinstance(tvl_data, list):
                if len(tvl_data) > 0:
                    if isinstance(tvl_data[0], list) and len(tvl_data[0]) == 2:
                        # Format is [[timestamp, value], ...]
                        df = pd.DataFrame(tvl_data, columns=['date', 'tvl'])
                        # Convert timestamp to datetime
                        if df['date'].iloc[0] > 1e12:  # Milliseconds
                            df['date'] = pd.to_datetime(df['date'], unit='ms')
                        else:  # Seconds
                            df['date'] = pd.to_datetime(df['date'], unit='s')
                    elif isinstance(tvl_data[0], dict):
                        # Format is [{'date': date, 'totalLiquidityUSD': value}, ...]
                        df = pd.DataFrame(tvl_data)
                        # Find the value column
                        value_cols = [col for col in df.columns if col != 'date' and ('liquid' in col.lower() or 'tvl' in col.lower() or 'value' in col.lower())]
                        if value_cols:
                            df = df.rename(columns={value_cols[0]: 'tvl'})
                        else:
                            self.logger.warning("Could not identify TVL column in data")
                            return []
                        
                        # Convert date column to datetime if needed
                        if pd.api.types.is_numeric_dtype(df['date']):
                            if df['date'].iloc[0] > 1e12:  # Milliseconds
                                df['date'] = pd.to_datetime(df['date'], unit='ms')
                            else:  # Seconds
                                df['date'] = pd.to_datetime(df['date'], unit='s')
                        else:
                            df['date'] = pd.to_datetime(df['date'])
            
            if df is None or len(df) < 10:
                self.logger.warning("Insufficient TVL data for milestone analysis")
                return []
                
            # Sort by date
            df = df.sort_values('date')
            
            # Find maximum TVL
            max_tvl = df['tvl'].max()
            
            # Define milestone levels based on max TVL
            if max_tvl >= 1_000_000_000:  # Billions range
                milestones = [100_000_000, 250_000_000, 500_000_000, 1_000_000_000]
                milestone_labels = ["$100M", "$250M", "$500M", "$1B"]
                # Add additional billion milestones
                billions = int(max_tvl / 1_000_000_000)
                for i in range(2, billions + 1):
                    milestones.append(i * 1_000_000_000)
                    milestone_labels.append(f"${i}B")
            elif max_tvl >= 100_000_000:  # Hundred millions range
                milestones = [10_000_000, 25_000_000, 50_000_000, 100_000_000]
                milestone_labels = ["$10M", "$25M", "$50M", "$100M"]
                # Add additional hundred million milestones
                if max_tvl >= 250_000_000:
                    milestones.append(250_000_000)
                    milestone_labels.append("$250M")
                if max_tvl >= 500_000_000:
                    milestones.append(500_000_000)
                    milestone_labels.append("$500M")
            elif max_tvl >= 10_000_000:  # Tens of millions range
                milestones = [1_000_000, 2_500_000, 5_000_000, 10_000_000]
                milestone_labels = ["$1M", "$2.5M", "$5M", "$10M"]
                # Add additional milestones
                if max_tvl >= 25_000_000:
                    milestones.append(25_000_000)
                    milestone_labels.append("$25M")
                if max_tvl >= 50_000_000:
                    milestones.append(50_000_000)
                    milestone_labels.append("$50M")
            elif max_tvl >= 1_000_000:  # Millions range
                milestones = [100_000, 250_000, 500_000, 1_000_000]
                milestone_labels = ["$100K", "$250K", "$500K", "$1M"]
                # Add additional milestones
                if max_tvl >= 2_500_000:
                    milestones.append(2_500_000)
                    milestone_labels.append("$2.5M")
                if max_tvl >= 5_000_000:
                    milestones.append(5_000_000)
                    milestone_labels.append("$5M")
            else:  # Less than $1M
                milestones = [10_000, 50_000, 100_000, 500_000]
                milestone_labels = ["$10K", "$50K", "$100K", "$500K"]
            
            # Find the first date when each milestone was reached
            annotations = []
            for milestone, label in zip(milestones, milestone_labels):
                # Skip milestones that were never reached
                if milestone > max_tvl:
                    continue
                    
                # Find first date above the milestone
                milestone_reached = df[df['tvl'] >= milestone].sort_values('date').iloc[0]
                
                annotations.append({
                    "date": milestone_reached['date'],
                    "tvl": milestone_reached['tvl'],
                    "label": label,
                    "description": f"{label} TVL reached on {milestone_reached['date'].strftime('%b %d, %Y')}"
                })
            
            self.logger.info(f"Generated {len(annotations)} milestone annotations")
            return annotations
            
        except Exception as e:
            self.logger.error(f"Error generating milestone annotations: {str(e)}")
            traceback.print_exc()
            return []

    def _load_liquidity_data_from_cache(self) -> Optional[Dict[str, Any]]:
        """Load liquidity data from cache files - uses TVL data as a proxy for liquidity."""
        # For liquidity trends, we'll use the TVL data as it's the closest proxy we have
        return self._load_tvl_data_from_cache()

    def _create_volume_chart(self, title: str, output_filename: str = None) -> Dict[str, Any]:
        """Create a volume chart with sample data when real data isn't available."""
        try:
            self.logger.info(f"Creating volume chart with title: {title}")
            
            # Generate sample volume data with our current 24h volume as reference
            current_volume = None
            
            # Try to extract the current volume value from available data
            try:
                coinmarketcap_dir = os.path.join("docs", self.project_name, "cache", "coinmarketcap")
                self.logger.info(f"Looking for volume data in: {coinmarketcap_dir}")
                
                if os.path.exists(coinmarketcap_dir):
                    for filename in os.listdir(coinmarketcap_dir):
                        if filename.endswith('.json'):
                            self.logger.info(f"Checking file: {filename}")
                            with open(os.path.join(coinmarketcap_dir, filename), 'r') as f:
                                try:
                                    data = json.load(f)
                                    self.logger.info(f"Loaded data from {filename}: {str(data)[:100]}...")
                                    # Check various fields
                                    if isinstance(data, dict):
                                        if 'volume_24h' in data:
                                            current_volume = float(data['volume_24h'])
                                            self.logger.info(f"Found volume_24h: {current_volume}")
                                            break
                                        elif '24h_volume' in data:
                                            current_volume = float(data['24h_volume'])
                                            self.logger.info(f"Found 24h_volume: {current_volume}")
                                            break
                                except Exception as e:
                                    self.logger.error(f"Error parsing {filename}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error reading volume data from coinmarketcap: {str(e)}")
                traceback.print_exc()
            
            # Default volume if not found
            if not current_volume:
                self.logger.warning("No volume data found, using default value")
                current_volume = 5000000
            
            # Generate sample data
            self.logger.info(f"Generating sample volume data with base volume: {current_volume}")
            end_date = pd.Timestamp.now()
            start_date = end_date - pd.Timedelta(days=90)
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Create volume pattern
            base_volume = np.random.normal(current_volume, current_volume * 0.2, size=len(dates))
            
            # Add weekly cycle and ensure no negative values
            for i, date in enumerate(dates):
                if date.dayofweek >= 5:  # Weekend
                    base_volume[i] *= 0.7
            base_volume = np.maximum(base_volume, 0)
            
            # Create figure
            fig = go.Figure()
            
            # Use a safe default color that works in both light/dark modes
            bar_color = '#4c78a8'  # Blue
            line_color = '#FF851B'  # Orange
            
            # Plot the volume bars
            fig.add_trace(go.Bar(
                x=dates,
                y=base_volume,
                name='Volume',
                marker_color=bar_color
            ))
            
            # Add 7-day moving average line
            ma7 = pd.Series(base_volume).rolling(window=7).mean()
            fig.add_trace(go.Scatter(
                x=dates,
                y=ma7,
                mode='lines',
                name='7-Day MA',
                line=dict(color=line_color, width=2)
            ))
            
            # Add annotation explaining this is sample data
            fig.add_annotation(
                x=0.5,
                y=0.95,
                xref="paper",
                yref="paper",
                text="Note: Historical volume data not available. Sample visualization based on current 24h volume.",
                showarrow=False,
                font=dict(size=10, color="#888888"),
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="#CCCCCC",
                borderwidth=1,
                borderpad=4
            )
            
            # Update layout
            fig.update_layout(
                title=title,
                xaxis_title="Date",
                yaxis_title="Volume (USD)",
                legend_title="Legend",
                font=dict(
                    family="Arial, sans-serif",
                    size=12,
                    color="#333333"  # Safe default text color
                ),
                plot_bgcolor="#FFFFFF",  # Safe white background
                paper_bgcolor="#FFFFFF",  # Safe white paper background
                margin=dict(l=50, r=50, t=80, b=50),
                width=900,
                height=500,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Format y-axis
            fig.update_yaxes(
                title_text="Volume (USD)",
                gridcolor='rgba(220, 220, 220, 0.5)',
                tickprefix="$",
                tickformat=",.0f"
            )
            
            # Format x-axis
            fig.update_xaxes(
                title_text="Date",
                gridcolor='rgba(220, 220, 220, 0.5)',
                linecolor='rgba(220, 220, 220, 0.5)'
            )
            
            # Generate output path
            if not output_filename:
                output_filename = f"{self.project_name.lower()}_volume_chart"
            
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            self.logger.info(f"Saving volume chart to: {output_path}")
            
            # Make sure output dir exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the figure
            fig.write_image(output_path, scale=2)
            
            self.logger.info(f"Successfully created volume chart at {output_path}")
            
            return {
                "success": True,
                "file_path": output_path,
                "title": title
            }
            
        except Exception as e:
            self.logger.error(f"Error creating volume chart: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "file_path": None
            }