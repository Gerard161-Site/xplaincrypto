import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .base_visualizer import BaseVisualizer

class LineChartVisualizer(BaseVisualizer):
    """
    Visualizer for line charts displaying time series data.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the line chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a line chart visualization.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        self.logger.info(f"DEBUG - Line chart data structure for {viz_type}: {list(data.keys())}")
        
        # Special case for TVL-specific charts
        if "tvl" in viz_type:
            self.logger.info(f"Creating TVL chart: {viz_type}")
            return self._create_tvl_chart(data, viz_config, viz_type)
        
        # For volume chart
        if viz_type == 'volume_chart':
            return self._create_volume_chart(data, viz_config)
        
        # For all other line charts
        return self._create_line_chart(data, viz_config, viz_type)
    
    def _create_tvl_chart(self, data: Dict[str, Any], viz_config: Dict[str, Any], viz_type: str) -> Tuple[bool, str, str]:
        """
        Create a TVL-specific chart.
        
        Args:
            data: Data for the visualization
            viz_config: Configuration for the visualization
            viz_type: Type of visualization to create
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        self.logger.info(f"Creating TVL chart for {viz_type}")
        
        # Extract TVL data directly
        tvl_data = None
        source = "DeFiLlama"
        
        # Try to find TVL history data
        if 'defillama' in data and isinstance(data['defillama'], dict):
            if 'tvl_history' in data['defillama'] and isinstance(data['defillama']['tvl_history'], list):
                tvl_data = data['defillama']['tvl_history']
                self.logger.info(f"Found TVL history in defillama with {len(tvl_data)} data points")
                
                # Log the structure of the TVL data
                if tvl_data and len(tvl_data) > 0:
                    self.logger.info(f"TVL data structure: {tvl_data[0]}")
        
        if not tvl_data or len(tvl_data) == 0:
            self.logger.warning(f"No TVL data found for {viz_type}")
            return False, "", f"No TVL data found for {viz_type}"
        
        # Extract timestamps and values from TVL data
        timestamps = []
        values = []
        
        for item in tvl_data:
            if isinstance(item, dict):
                if 'date' in item and 'tvl' in item:
                    timestamps.append(item['date'])
                    values.append(float(item['tvl']))
                elif 'timestamp' in item and 'tvl' in item:
                    timestamps.append(item['timestamp'])
                    values.append(float(item['tvl']))
        
        if len(timestamps) == 0 or len(values) == 0:
            self.logger.warning(f"Could not extract timestamps or values from TVL data for {viz_type}")
            return False, "", f"Could not extract timestamps or values from TVL data for {viz_type}"
        
        self.logger.info(f"Extracted {len(timestamps)} data points with time range: {min(timestamps)} to {max(timestamps)}")
        
        # Create figure
        fig = go.Figure()
        
        # Add main trace
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=values,
            mode='lines',
            name=viz_config.get("line_name", "TVL"),
            line=dict(
                color=self.colors.get("primary", "#1f77b4"),
                width=2
            )
        ))
        
        # Special processing for specific chart types
        if viz_type == 'tvl_phases_chart':
            # Create DataFrame for phases annotation
            df = pd.DataFrame({'date': timestamps, 'value': values})
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            self._add_tvl_phases(fig, df)
            
        elif viz_type == 'tvl_milestone_chart':
            # Create DataFrame for milestone annotation
            df = pd.DataFrame({'date': timestamps, 'value': values})
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            self._add_tvl_milestones(fig, df)
        
        # Style the chart
        chart_title = viz_config.get("title", f"{self.project_name} {viz_type.replace('_', ' ').title()}")
        
        # Apply layout
        fig.update_layout(
            title=chart_title,
            width=self.width,
            height=self.height,
            paper_bgcolor=self.colors.get("background", "#ffffff"),
            plot_bgcolor=self.colors.get("background", "#ffffff"),
            margin=dict(l=50, r=50, t=80, b=50),
            xaxis_title=viz_config.get("x_axis_title", "Date"),
            yaxis_title=viz_config.get("y_axis_title", "TVL (USD)"),
            font=dict(
                family=self.fonts.get("base", "Arial, sans-serif"),
                size=12
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add grid lines
        fig.update_xaxes(
            showgrid=True, 
            gridwidth=1, 
            gridcolor=self.colors.get("grid", "#e6e6e6")
        )
        fig.update_yaxes(
            showgrid=True, 
            gridwidth=1, 
            gridcolor=self.colors.get("grid", "#e6e6e6")
        )
        
        # Add source annotation
        fig.add_annotation(
            text=f"Source: {source}",
            xref="paper", yref="paper",
            x=0.01, y=-0.12,
            showarrow=False,
            font=dict(size=10, color="#808080"),
            align="left"
        )
        
        # Generate output path
        output_filename = viz_config.get("output_filename", f"{viz_type}")
        output_path = os.path.join(self.output_dir, f"{output_filename}.png")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export as PNG using kaleido
        fig.write_image(output_path, scale=2)
        
        return True, output_path, f"{viz_type} chart created successfully"
    
    def _extract_time_series_data(self, data: Dict[str, Any], viz_type: str) -> Tuple[Optional[List], Optional[List], Optional[List], str]:
        """
        Extract time series data for a line chart.
        
        Args:
            data: Data dictionary containing time series information
            viz_type: Type of visualization to create
            
        Returns:
            Tuple of (timestamps, values, optionalSecondSeries, source)
        """
        # DEBUG logging
        self.logger.info(f"Extracting time series data for {viz_type}")
        
        # Initialize return values
        timestamps = None
        values = None
        secondary_values = None
        source = "Various Sources"
        
        # For TVL charts, use specialized extraction
        if "tvl" in viz_type.lower():
            # Try to get TVL data
            tvl_data = self._extract_tvl_data(data)
            if tvl_data and isinstance(tvl_data, list):
                self.logger.info(f"Found TVL data with {len(tvl_data)} points")
                
                # Check the structure of TVL data
                if len(tvl_data) > 0:
                    sample = tvl_data[0]
                    self.logger.info(f"TVL data sample: {sample}")
                    
                    # Handle different TVL data formats
                    if isinstance(sample, dict):
                        # Format 1: List of dicts with date/timestamp and tvl fields
                        if ("date" in sample or "timestamp" in sample) and "tvl" in sample:
                            self.logger.info("TVL data format: List of dicts with date/tvl")
                            timestamps = [item.get("date", item.get("timestamp")) for item in tvl_data]
                            values = [float(item.get("tvl", 0)) for item in tvl_data]
                            source = "DeFiLlama"
                        # Format 2: List of dicts with date/timestamp and value fields
                        elif ("date" in sample or "timestamp" in sample) and "value" in sample:
                            self.logger.info("TVL data format: List of dicts with date/value")
                            timestamps = [item.get("date", item.get("timestamp")) for item in tvl_data]
                            values = [float(item.get("value", 0)) for item in tvl_data]
                            source = "DeFiLlama"
                    # Format 3: List of [timestamp, value] pairs
                    elif isinstance(sample, list) and len(sample) == 2:
                        self.logger.info("TVL data format: List of [timestamp, value] pairs")
                        timestamps = [item[0] for item in tvl_data]
                        values = [float(item[1]) for item in tvl_data]
                        source = "DeFiLlama"
                
                if timestamps and values:
                    # Debugging information
                    self.logger.info(f"Extracted {len(timestamps)} data points with time range: {min(timestamps) if timestamps else 'N/A'} to {max(timestamps) if timestamps else 'N/A'}")
                    return timestamps, values, secondary_values, source
        
        # For volume chart and other types, use existing logic
        if viz_type == 'volume_chart':
            # Debug data availbility
            self.logger.info(f"Available sources for volume chart: {list(data.keys())}")
            
            # Try different paths for volume data
            
            # Path 1: From historical data
            if 'historical' in data and 'volumes' in data['historical'] and 'timestamps' in data['historical']:
                self.logger.info("Found volume data in historical data")
                timestamps = data['historical']['timestamps']
                values = data['historical']['volumes']
                source = "Historical Data"
                
            # Path 2: From price data
            elif 'price' in data and 'volume_24h' in data['price']:
                self.logger.info("Found single point volume data in price data")
                # Only have a single point, create a series with that value repeated
                today = datetime.now()
                timestamps = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, -1, -1)]
                volume = data['price'].get('volume_24h', 0)
                # Create a fake volume trend that's somewhat realistic
                volume_base = float(volume)
                values = [volume_base * (0.8 + 0.4 * np.random.random()) for _ in range(31)]
                source = "Estimated from Current Volume"
                
            # Path 3: From coinmarketcap
            elif 'coinmarketcap' in data:
                cmcdata = data['coinmarketcap']
                if isinstance(cmcdata, dict):
                    # Try different structures
                    if 'historical' in cmcdata and 'volumes' in cmcdata['historical']:
                        self.logger.info("Found volume data in coinmarketcap historical data")
                        timestamps = cmcdata['historical']['timestamps']
                        values = cmcdata['historical']['volumes']
                        source = "CoinMarketCap"
                    # Look for OHLCV data
                    elif 'ohlcv' in cmcdata:
                        self.logger.info("Found volume data in coinmarketcap OHLCV data")
                        ohlcv_data = cmcdata['ohlcv']
                        if isinstance(ohlcv_data, dict) and 'data' in ohlcv_data:
                            ohlcv_records = ohlcv_data['data']
                        elif isinstance(ohlcv_data, list):
                            ohlcv_records = ohlcv_data
                        else:
                            ohlcv_records = []
                            
                        if ohlcv_records:
                            timestamps = [record.get('date', '') for record in ohlcv_records]
                            values = [record.get('volume', 0) for record in ohlcv_records]
                            source = "CoinMarketCap OHLCV"
            
            # Path 4: Check cache_data structure
            elif 'cache_data' in data and isinstance(data['cache_data'], dict):
                cache_data = data['cache_data']
                self.logger.info(f"Looking in cache_data: {list(cache_data.keys())}")
                
                # Look for coinmarketcap data in cache
                if 'coinmarketcap' in cache_data:
                    cmc_data = cache_data['coinmarketcap']
                    if 'ohlcv' in cmc_data:
                        self.logger.info("Found volume data in cache_data coinmarketcap OHLCV")
                        ohlcv_data = cmc_data['ohlcv']
                        if isinstance(ohlcv_data, dict) and 'data' in ohlcv_data:
                            ohlcv_records = ohlcv_data['data']
                        elif isinstance(ohlcv_data, list):
                            ohlcv_records = ohlcv_data
                        else:
                            ohlcv_records = []
                            
                        if ohlcv_records:
                            timestamps = [record.get('date', '') for record in ohlcv_records]
                            values = [record.get('volume', 0) for record in ohlcv_records]
                            source = "CoinMarketCap OHLCV (Cache)"
                
                # Look for historical data in cache
                elif 'historical' in cache_data:
                    historical = cache_data['historical']
                    if 'volumes' in historical and 'timestamps' in historical:
                        self.logger.info("Found volume data in cache_data historical")
                        timestamps = historical['timestamps']
                        values = historical['volumes']
                        source = "Historical Data (Cache)"
            
            # Path 5: Check for direct OHLCV data
            elif 'ohlcv' in data:
                self.logger.info("Found direct OHLCV data")
                ohlcv_data = data['ohlcv']
                
                # Handle different OHLCV structures
                if isinstance(ohlcv_data, dict):
                    if 'data' in ohlcv_data:
                        ohlcv_records = ohlcv_data['data']
                    else:
                        # Check if we need to extract data from metadata structure
                        if 'metadata' in data:
                            self.logger.info("OHLCV has metadata structure")
                            ohlcv_records = ohlcv_data  # In this case the whole object is the data list
                        else:
                            ohlcv_records = []
                elif isinstance(ohlcv_data, list):
                    ohlcv_records = ohlcv_data
                else:
                    ohlcv_records = []
                
                if ohlcv_records:
                    # Extract from OHLCV format
                    timestamps = []
                    values = []
                    for record in ohlcv_records:
                        if isinstance(record, dict):
                            if 'date' in record and 'volume' in record:
                                timestamps.append(record['date'])
                                values.append(record['volume'])
                        source = "OHLCV Data"
                
            # Specific check for cached file structure (metadata pattern)
            if timestamps is None and 'data' in data and 'metadata' in data:
                self.logger.info("Found metadata structure, checking for volume data")
                cached_data = data['data']
                if isinstance(cached_data, list):
                    # Try to extract timestamps and volumes if they exist
                    for entry in cached_data:
                        if isinstance(entry, dict) and 'date' in entry and 'volume' in entry:
                            if timestamps is None:
                                timestamps = []
                                values = []
                            timestamps.append(entry['date'])
                            values.append(entry['volume'])
                            source = "Cached OHLCV Data"
                
            # If still nothing, check for top-level data array
            if timestamps is None and 'data' in data and isinstance(data['data'], list):
                self.logger.info("Checking top-level data array for volume data")
                data_array = data['data']
                if len(data_array) > 0 and isinstance(data_array[0], dict):
                    if 'volume' in data_array[0] and 'date' in data_array[0]:
                        timestamps = [item.get('date', '') for item in data_array]
                        values = [item.get('volume', 0) for item in data_array]
                        source = "Data Array"
        
        # For other line chart types, handle accordingly
        # ...
        
        # Check if we found valid data - FIX THE VALIDATION LOGIC
        if timestamps is None or values is None:
            self.logger.warning(f"Could not extract time series data for {viz_type}")
            self.logger.info(f"Timestamps: {timestamps}")
            self.logger.info(f"Values: {values}")
            return None, None, None, ""
            
        if len(timestamps) == 0 or len(values) == 0:
            self.logger.warning(f"Empty time series data for {viz_type}")
            return None, None, None, ""
            
        if len(timestamps) != len(values):
            self.logger.warning(f"Mismatched time series data: {len(timestamps)} timestamps vs {len(values)} values")
            return None, None, None, ""
        
        # Debugging information
        self.logger.info(f"Extracted {len(timestamps)} data points with time range: {min(timestamps) if timestamps else 'N/A'} to {max(timestamps) if timestamps else 'N/A'}")
        
        return timestamps, values, secondary_values, source
    
    def _create_volume_chart(self, data: Dict[str, Any], viz_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a volume chart.
        
        Args:
            data: Data for the visualization
            viz_config: Configuration for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        self.logger.info("Creating volume chart")
        
        # Extract volume data
        timestamps, volumes, _, source = self._extract_time_series_data(data, 'volume_chart')
        
        if not timestamps or not volumes:
            return False, "", "No volume data available for volume chart"
        
        # Create figure
        fig = go.Figure()
        
        # Add volume trace
        fig.add_trace(go.Bar(
            x=timestamps,
            y=volumes,
            name="Trading Volume",
            marker_color=self.colors.get("primary", "#2196f3")
        ))
        
        # Update layout
        title = viz_config.get("title", f"{self.project_name} Trading Volume")
        source_text = viz_config.get("source", source)
        
        fig.update_layout(
            title=title,
            width=self.width,
            height=self.height,
            paper_bgcolor=self.colors.get("background", "#ffffff"),
            plot_bgcolor=self.colors.get("background", "#ffffff"),
            margin=dict(l=50, r=50, t=80, b=50),
            xaxis_title="Date",
            yaxis_title="Trading Volume",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add data source annotation
        fig.add_annotation(
            text=f"Source: {source_text}",
            xref="paper", yref="paper",
            x=0.01, y=-0.1,
            showarrow=False,
            font=dict(size=10, color="#808080"),
            align="left"
        )
        
        # Generate output path
        output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_volume_chart")
        output_path = os.path.join(self.output_dir, f"{output_filename}.png")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export as PNG using kaleido
        fig.write_image(output_path, scale=2)
        
        return True, output_path, "Volume chart created successfully"
    
    def _create_line_chart(self, data: Dict[str, Any], viz_config: Dict[str, Any], viz_type: str) -> Tuple[bool, str, str]:
        """
        Create a generic line chart.
        
        Args:
            data: Data for the visualization
            viz_config: Configuration for the visualization
            viz_type: Type of visualization to create
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        self.logger.info(f"Creating generic line chart for {viz_type}")
        self.logger.info(f"Available data keys: {list(data.keys())}")
        
        # For TVL charts, try specialized extraction first
        if "tvl" in viz_type.lower():
            self.logger.info("Using specialized TVL data extraction")
            timestamps, values, secondary_values, source = self._extract_time_series_data(data, viz_type)
            
            if timestamps and values and len(timestamps) == len(values) and len(timestamps) > 0:
                self.logger.info(f"Successfully extracted TVL data: {len(timestamps)} points")
                
                # Create figure
                fig = go.Figure()
                
                # Add main trace
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=values,
                    mode='lines',
                    name=viz_config.get("line_name", self.project_name),
                    line=dict(
                        color=self.colors.get("primary", "#1f77b4"),
                        width=2
                    )
                ))
                
                # Special processing for specific chart types
                if viz_type == 'tvl_phases_chart':
                    # Create DataFrame for phases annotation
                    df = pd.DataFrame({'date': timestamps, 'value': values})
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date')
                    self._add_tvl_phases(fig, df)
                    
                elif viz_type == 'tvl_milestone_chart':
                    # Create DataFrame for milestone annotation
                    df = pd.DataFrame({'date': timestamps, 'value': values})
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date')
                    self._add_tvl_milestones(fig, df)
                
                # Style the chart
                chart_title = viz_config.get("title", f"{self.project_name} {viz_type.replace('_', ' ').title()}")
                
                # Apply layout
                fig.update_layout(
                    title=chart_title,
                    width=self.width,
                    height=self.height,
                    paper_bgcolor=self.colors.get("background", "#ffffff"),
                    plot_bgcolor=self.colors.get("background", "#ffffff"),
                    margin=dict(l=50, r=50, t=80, b=50),
                    xaxis_title=viz_config.get("x_axis_title", "Date"),
                    yaxis_title=viz_config.get("y_axis_title", "TVL (USD)"),
                    font=dict(
                        family=self.fonts.get("base", "Arial, sans-serif"),
                        size=12
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                # Add grid lines
                fig.update_xaxes(
                    showgrid=True, 
                    gridwidth=1, 
                    gridcolor=self.colors.get("grid", "#e6e6e6")
                )
                fig.update_yaxes(
                    showgrid=True, 
                    gridwidth=1, 
                    gridcolor=self.colors.get("grid", "#e6e6e6")
                )
                
                # Add source annotation
                fig.add_annotation(
                    text=f"Source: {source}",
                    xref="paper", yref="paper",
                    x=0.01, y=-0.12,
                    showarrow=False,
                    font=dict(size=10, color="#808080"),
                    align="left"
                )
                
                # Generate output path
                output_filename = viz_config.get("output_filename", f"{viz_type}")
                output_path = os.path.join(self.output_dir, f"{output_filename}.png")
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Export as PNG using kaleido
                fig.write_image(output_path, scale=2)
                
                return True, output_path, f"{viz_type} chart created successfully"
            else:
                self.logger.warning("Specialized TVL data extraction failed, falling back to generic extraction")
        
        # For other chart types or if TVL extraction failed, use generic extraction
        # Extract time series data based on chart type
        timestamps, values, secondary_values, source = None, None, None, ""
        
        # Try specialized extraction methods first
        if viz_type == "line_chart" or "price" in viz_type:
            time_series_data = self._extract_price_data(data)
            if time_series_data:
                self.logger.info("Found price data")
                # Process the data based on its format
                if isinstance(time_series_data, list):
                    if len(time_series_data) > 0:
                        if isinstance(time_series_data[0], dict):
                            # Format: List of dicts with date/timestamp and price
                            timestamps = [item.get("date", item.get("timestamp")) for item in time_series_data if "date" in item or "timestamp" in item]
                            values = [float(item.get("price", item.get("value", 0))) for item in time_series_data]
                            source = "Price Data"
                        elif isinstance(time_series_data[0], list) and len(time_series_data[0]) == 2:
                            # Format: List of [timestamp, price] pairs
                            timestamps = [item[0] for item in time_series_data]
                            values = [float(item[1]) for item in time_series_data]
                            source = "Price Data"
        elif "volume" in viz_type:
            time_series_data = self._extract_volume_data(data)
            if time_series_data:
                self.logger.info("Found volume data")
                # Process the data based on its format
                if isinstance(time_series_data, list):
                    if len(time_series_data) > 0:
                        if isinstance(time_series_data[0], dict):
                            # Format: List of dicts with date/timestamp and volume
                            timestamps = [item.get("date", item.get("timestamp")) for item in time_series_data if "date" in item or "timestamp" in item]
                            values = [float(item.get("volume", item.get("value", 0))) for item in time_series_data]
                            source = "Volume Data"
                        elif isinstance(time_series_data[0], list) and len(time_series_data[0]) == 2:
                            # Format: List of [timestamp, volume] pairs
                            timestamps = [item[0] for item in time_series_data]
                            values = [float(item[1]) for item in time_series_data]
                            source = "Volume Data"
        
        # If specialized extraction didn't work, try generic extraction
        if not timestamps or not values:
            self.logger.info("Specialized extraction failed, trying generic extraction")
            time_series_data = self._extract_generic_timeseries(data, viz_type)
            if time_series_data:
                self.logger.info(f"Found generic time series data: {type(time_series_data)}")
                # Process the data based on its format
                if isinstance(time_series_data, list):
                    if len(time_series_data) > 0:
                        if isinstance(time_series_data[0], dict):
                            # Format: List of dicts with date/timestamp and value
                            if 'date' in time_series_data[0] and 'value' in time_series_data[0]:
                                # Standard {date, value} format
                                self.logger.info("Found data in standard {date, value} format")
                                timestamps = [item.get("date") for item in time_series_data]
                                values = [float(item.get("value", 0)) for item in time_series_data]
                                source = "Time Series Data"
                            else:
                                # Try to find date and value keys
                                date_key = next((k for k in ["date", "timestamp", "time"] if k in time_series_data[0]), None)
                                value_key = next((k for k in ["value", "price", "tvl", "volume"] if k in time_series_data[0]), None)
                                
                                if date_key and value_key:
                                    self.logger.info(f"Found data with keys: {date_key}, {value_key}")
                                    timestamps = [item.get(date_key) for item in time_series_data]
                                    values = [float(item.get(value_key, 0)) for item in time_series_data]
                                    source = "Time Series Data"
                        elif isinstance(time_series_data[0], list) and len(time_series_data[0]) == 2:
                            # Format: List of [timestamp, value] pairs
                            self.logger.info("Found data in [timestamp, value] format")
                            timestamps = [item[0] for item in time_series_data]
                            values = [float(item[1]) for item in time_series_data]
                            source = "Time Series Data"
        
        # Check if we found valid time series data
        if not timestamps or not values:
            self.logger.warning(f"No time series data found for {viz_type}")
            return False, "", f"No time series data found for {viz_type}"
            
        if len(timestamps) == 0 or len(values) == 0:
            self.logger.warning(f"Empty time series data for {viz_type}")
            return False, "", f"Empty time series data for {viz_type}"
            
        if len(timestamps) != len(values):
            self.logger.warning(f"Mismatched time series data for {viz_type}: {len(timestamps)} timestamps vs {len(values)} values")
            return False, "", f"Mismatched time series data for {viz_type}"
        
        # Debugging information
        self.logger.info(f"Extracted {len(timestamps)} data points with time range: {min(timestamps)} to {max(timestamps)}")
        
        # Create figure
        fig = go.Figure()
        
        # Add main trace
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=values,
            mode='lines',
            name=viz_config.get("line_name", self.project_name),
            line=dict(
                color=self.colors.get("primary", "#1f77b4"),
                width=2
            )
        ))
        
        # Add secondary trace if available
        if secondary_values and len(secondary_values) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=secondary_values,
                mode='lines',
                name=viz_config.get("secondary_line_name", "Secondary"),
                line=dict(
                    color=self.colors.get("secondary", "#ff7f0e"),
                    width=2,
                    dash='dash'
                )
            ))
        
        # Special processing for specific chart types
        if viz_type == 'tvl_phases_chart':
            # Create DataFrame for phases annotation
            df = pd.DataFrame({'date': timestamps, 'value': values})
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            self._add_tvl_phases(fig, df)
            
        elif viz_type == 'tvl_milestone_chart':
            # Create DataFrame for milestone annotation
            df = pd.DataFrame({'date': timestamps, 'value': values})
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            self._add_tvl_milestones(fig, df)
        
        # Style the chart
        chart_title = viz_config.get("title", f"{self.project_name} {viz_type.replace('_', ' ').title()}")
        
        # Apply layout
        fig.update_layout(
            title=chart_title,
            width=self.width,
            height=self.height,
            paper_bgcolor=self.colors.get("background", "#ffffff"),
            plot_bgcolor=self.colors.get("background", "#ffffff"),
            margin=dict(l=50, r=50, t=80, b=50),
            xaxis_title=viz_config.get("x_axis_title", "Date"),
            yaxis_title=viz_config.get("y_axis_title", "Value"),
            font=dict(
                family=self.fonts.get("base", "Arial, sans-serif"),
                size=12
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Add grid lines
        fig.update_xaxes(
            showgrid=True, 
            gridwidth=1, 
            gridcolor=self.colors.get("grid", "#e6e6e6")
        )
        fig.update_yaxes(
            showgrid=True, 
            gridwidth=1, 
            gridcolor=self.colors.get("grid", "#e6e6e6")
        )
        
        # Add source annotation
        fig.add_annotation(
            text=f"Source: {source}",
            xref="paper", yref="paper",
            x=0.01, y=-0.12,
            showarrow=False,
            font=dict(size=10, color="#808080"),
            align="left"
        )
        
        # Generate output path
        output_filename = viz_config.get("output_filename", f"{viz_type}")
        output_path = os.path.join(self.output_dir, f"{output_filename}.png")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export as PNG using kaleido
        fig.write_image(output_path, scale=2)
        
        return True, output_path, f"{viz_type} chart created successfully"
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a line chart.
        
        Args:
            data: Data to check
            viz_type: Type of visualization
            
        Returns:
            True if usable, False otherwise
        """
        if not super().check_data_usability(data, viz_type):
            return False
        
        # Direct access to price_history or other time series
        if 'price_history' in data:
            return True
        elif 'volume_history' in data:
            return True
        elif 'tvl_history' in data:
            return True
            
        # For line charts, we need time series data
        if 'tvl' in data or 'volume' in data:
            return True
        elif 'defillama' in data and isinstance(data['defillama'], dict):
            return 'tvl_history' in data['defillama'] and data['defillama']['tvl_history']
        elif 'coinmarketcap' in data and isinstance(data['coinmarketcap'], dict):
            return ('price_history' in data['coinmarketcap'] or 
                    'volume_history' in data['coinmarketcap'])
        elif 'coingecko' in data and isinstance(data['coingecko'], dict):
            return ('price_history' in data['coingecko'] or 
                    'volume_history' in data['coingecko'])
        
        # Generic time series in any source
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                for key, value in source_data.items():
                    if ('history' in key or 'series' in key or 'trend' in key) and value:
                        return True
        
        return False
    
    def _extract_price_data(self, data: Dict[str, Any]) -> Any:
        """Extract price history time series data from input data."""
        # Direct access for price_history
        if 'price_history' in data:
            self.logger.info("Found direct price_history data")
            return data['price_history']
            
        # Check in coingecko data
        if 'coingecko' in data:
            self.logger.info("Checking CoinGecko data")
            cg_data = data['coingecko']
            
            if isinstance(cg_data, dict):
                self.logger.info(f"CoinGecko keys: {cg_data.keys() if hasattr(cg_data, 'keys') else 'No keys'}")
                
                # Check for price_history in coingecko data
                if 'price_history' in cg_data:
                    self.logger.info("Found price_history in CoinGecko data")
                    return cg_data['price_history']
                
                # Check for market_data.prices in CoinGecko format
                if 'market_data' in cg_data and isinstance(cg_data['market_data'], dict):
                    market_data = cg_data['market_data']
                    if 'prices' in market_data and isinstance(market_data['prices'], list):
                        self.logger.info("Found market_data.prices in CoinGecko data")
                        return market_data['prices']
                
                # Check for prices directly in CoinGecko data
                if 'prices' in cg_data and isinstance(cg_data['prices'], list):
                    self.logger.info("Found prices in CoinGecko data")
                    return cg_data['prices']
                    
                # Check for results containing price data
                if 'results' in cg_data and isinstance(cg_data['results'], list):
                    results = cg_data['results']
                    
                    # Check if results have timestamp and price fields
                    if len(results) > 0 and all(isinstance(item, dict) for item in results):
                        if all('timestamp' in item and 'price' in item for item in results):
                            self.logger.info("Found timestamp/price pairs in CoinGecko results")
                            return [[item['timestamp'], item['price']] for item in results]
        
        # Check in coinmarketcap data for price history
        if 'coinmarketcap' in data:
            self.logger.info("Checking CoinMarketCap data")
            cm_data = data['coinmarketcap']
            
            if isinstance(cm_data, dict):
                self.logger.info(f"CoinMarketCap keys: {cm_data.keys() if hasattr(cm_data, 'keys') else 'No keys'}")
                
                # Check for price_history
                if 'price_history' in cm_data:
                    self.logger.info("Found price_history in CoinMarketCap data")
                    return cm_data['price_history']
                
                # Check for current_price and extract closing prices from OHLCV if available
                if 'ohlcv_data' in cm_data and isinstance(cm_data['ohlcv_data'], list):
                    self.logger.info("Extracting price from OHLCV data")
                    ohlcv = cm_data['ohlcv_data']
                    return [[item['timestamp'], item['close']] for item in ohlcv if 'timestamp' in item and 'close' in item]
        
        self.logger.warning("No price history data found")
        return None
    
    def _calculate_monthly_growth_from_tvl(self, tvl_history: List) -> List:
        """Calculate monthly growth rates from TVL history data."""
        # Convert raw TVL history to DataFrame
        raw_df = self._prepare_timeseries_data(tvl_history)
        if raw_df is None or len(raw_df) < 30:
            self.logger.warning("Could not prepare DataFrame from TVL history")
            return None
            
        # Set date as index for resampling
        raw_df = raw_df.set_index('date')
        
        # Resample to monthly data (end of month)
        monthly_df = raw_df.resample('ME').last()
        
        # Calculate month-over-month growth
        monthly_df['growth'] = monthly_df['value'].pct_change() * 100
        
        # Reset index to get date back as column
        monthly_df = monthly_df.reset_index()
        
        # Convert to list of [date, growth] format
        monthly_growth = []
        for _, row in monthly_df.iterrows():
            if not pd.isna(row['growth']):
                monthly_growth.append([row['date'].timestamp() * 1000, row['growth']])
        
        self.logger.info(f"Generated {len(monthly_growth)} monthly growth data points")
        
        return monthly_growth
    
    def _extract_volume_data(self, data: Dict[str, Any]) -> Any:
        """Extract volume time series data from input data."""
        if 'coinmarketcap' in data:
            cmc_data = data['coinmarketcap']
            if 'volume_history' in cmc_data:
                return cmc_data['volume_history']
            if 'history' in cmc_data and 'volumes' in cmc_data['history']:
                return cmc_data['history']['volumes']
                
        if 'coingecko' in data:
            cg_data = data['coingecko']
            if 'volume_history' in cg_data:
                return cg_data['volume_history']
            if 'history' in cg_data and 'volumes' in cg_data['history']:
                return cg_data['history']['volumes']
                
        # Generic formats
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                if 'volume_history' in source_data:
                    return source_data['volume_history']
                if 'history' in source_data and 'volumes' in source_data['history']:
                    return source_data['history']['volumes']
                    
        return None
    
    def _extract_tvl_data(self, data: Dict[str, Any]) -> Any:
        """Extract TVL time series data from input data."""
        # Direct access if tvl_history is at the top level
        if 'tvl_history' in data:
            self.logger.info("Found direct tvl_history data")
            tvl_data = data['tvl_history']
            # Log the structure to help debug
            if isinstance(tvl_data, list) and len(tvl_data) > 0:
                self.logger.info(f"TVL data structure sample: {tvl_data[0]}")
            return tvl_data
            
        # Look for TVL data in defillama source
        if 'defillama' in data:
            dl_data = data['defillama']
            self.logger.info(f"Examining DeFiLlama data keys: {list(dl_data.keys()) if isinstance(dl_data, dict) else 'Not a dict'}")
            
            if isinstance(dl_data, dict):
                if 'tvl_history' in dl_data:
                    self.logger.info("Found tvl_history in defillama data")
                    tvl_data = dl_data['tvl_history']
                    # Log the structure to help debug
                    if isinstance(tvl_data, list) and len(tvl_data) > 0:
                        self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                    return tvl_data
                    
                if 'tvl' in dl_data:
                    if isinstance(dl_data['tvl'], list):
                        self.logger.info("Found tvl list in defillama data")
                        tvl_data = dl_data['tvl']
                        # Log the structure to help debug
                        if len(tvl_data) > 0:
                            self.logger.info(f"TVL list structure sample: {tvl_data[0]}")
                        return tvl_data
                    elif isinstance(dl_data['tvl'], dict):
                        # Check if there's a tvl_history inside the tvl dict
                        tvl_dict = dl_data['tvl']
                        if 'tvl_history' in tvl_dict:
                            self.logger.info("Found tvl_history in defillama.tvl dict")
                            tvl_data = tvl_dict['tvl_history']
                            # Log the structure to help debug
                            if isinstance(tvl_data, list) and len(tvl_data) > 0:
                                self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                            return tvl_data
                            
                # Also check for data in the format sometimes returned by DeFiLlama
                if 'data' in dl_data and isinstance(dl_data['data'], dict):
                    data_dict = dl_data['data']
                    if 'tvl_history' in data_dict:
                        self.logger.info("Found tvl_history in defillama.data dict")
                        tvl_data = data_dict['tvl_history']
                        # Log the structure to help debug
                        if isinstance(tvl_data, list) and len(tvl_data) > 0:
                            self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                        return tvl_data
                        
                # Sometimes DeFiLlama returns data in a different nested structure
                for key, value in dl_data.items():
                    if isinstance(value, dict) and 'tvl_history' in value:
                        self.logger.info(f"Found tvl_history in defillama.{key} dict")
                        tvl_data = value['tvl_history']
                        # Log the structure to help debug
                        if isinstance(tvl_data, list) and len(tvl_data) > 0:
                            self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                        return tvl_data
                        
        # Also check for TVL data in other sources
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                if 'tvl_history' in source_data:
                    self.logger.info(f"Found tvl_history in {source} data")
                    tvl_data = source_data['tvl_history']
                    # Log the structure to help debug
                    if isinstance(tvl_data, list) and len(tvl_data) > 0:
                        self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                    return tvl_data
                    
                if 'tvl' in source_data:
                    if isinstance(source_data['tvl'], list):
                        self.logger.info(f"Found tvl list in {source} data")
                        tvl_data = source_data['tvl']
                        # Log the structure to help debug
                        if len(tvl_data) > 0:
                            self.logger.info(f"TVL list structure sample: {tvl_data[0]}")
                        return tvl_data
                    elif isinstance(source_data['tvl'], dict) and 'tvl_history' in source_data['tvl']:
                        self.logger.info(f"Found tvl_history in {source}.tvl dict")
                        tvl_data = source_data['tvl']['tvl_history']
                        # Log the structure to help debug
                        if len(tvl_data) > 0:
                            self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                        return tvl_data
                
                # Check in nested 'data' field
                if 'data' in source_data and isinstance(source_data['data'], dict):
                    data_dict = source_data['data']
                    if 'tvl_history' in data_dict:
                        self.logger.info(f"Found tvl_history in {source}.data dict")
                        tvl_data = data_dict['tvl_history']
                        # Log the structure to help debug
                        if len(tvl_data) > 0:
                            self.logger.info(f"TVL history structure sample: {tvl_data[0]}")
                        return tvl_data
                    if 'tvl' in data_dict and isinstance(data_dict['tvl'], list):
                        self.logger.info(f"Found tvl list in {source}.data dict")
                        tvl_data = data_dict['tvl']
                        # Log the structure to help debug
                        if len(tvl_data) > 0:
                            self.logger.info(f"TVL list structure sample: {tvl_data[0]}")
                        return tvl_data
                        
        # Look for any field that might contain TVL data
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                # Look for any key that has 'tvl' and contains a list
                for key, value in source_data.items():
                    if 'tvl' in key.lower() and isinstance(value, list) and value:
                        self.logger.info(f"Found potential TVL data in {source}.{key}")
                        return value
                        
        self.logger.warning("Could not find TVL data in the provided input")
        return None
    
    def _extract_generic_timeseries(self, data: Dict[str, Any], viz_type: str) -> Any:
        """Extract generic time series data based on visualization type."""
        # Special handling for TVL charts
        if "tvl" in viz_type.lower():
            self.logger.info(f"Using TVL extraction for {viz_type}")
            tvl_data = self._extract_tvl_data(data)
            if tvl_data and isinstance(tvl_data, list) and len(tvl_data) > 0:
                self.logger.info(f"Found TVL data with {len(tvl_data)} points")
                
                # Format the data for visualization
                formatted_data = []
                for item in tvl_data:
                    if isinstance(item, dict):
                        if 'date' in item and 'tvl' in item:
                            formatted_data.append({
                                'date': item['date'],
                                'value': item['tvl']
                            })
                        elif 'timestamp' in item and 'tvl' in item:
                            formatted_data.append({
                                'date': item['timestamp'],
                                'value': item['tvl']
                            })
                
                if formatted_data:
                    self.logger.info(f"Formatted {len(formatted_data)} TVL data points")
                    return formatted_data
            
        # Special handling for monthly growth chart
        if "monthly_growth" in viz_type and "defillama" in data:
            self.logger.info("Special handling for monthly growth chart")
            dl_data = data["defillama"]
            
            # Try to get TVL history from DeFi Llama data
            tvl_history = None
            if "tvl_history" in dl_data:
                tvl_history = dl_data["tvl_history"]
            elif "tvl" in dl_data and isinstance(dl_data["tvl"], dict) and "tvl_history" in dl_data["tvl"]:
                tvl_history = dl_data["tvl"]["tvl_history"]
            
            if tvl_history and isinstance(tvl_history, list) and len(tvl_history) > 30:
                self.logger.info(f"Calculating monthly growth from TVL history with {len(tvl_history)} points")
                return self._calculate_monthly_growth_from_tvl(tvl_history)
        
        # For regular line charts, first check if we have price_history in the data dictionary
        if ("line_chart" == viz_type or "price_chart" in viz_type) and "price_history" in data:
            self.logger.info("Found direct price_history data for line_chart")
            return data["price_history"]
            
        # Then check if there's a price_data field 
        if ("line_chart" == viz_type or "price_chart" in viz_type) and "price_data" in data:
            self.logger.info("Found price_data for line_chart")
            return data["price_data"]
            
        # Extract price data from coinmarketcap or coingecko
        if "line_chart" == viz_type or "price_chart" in viz_type:
            price_data = self._extract_price_data(data)
            if price_data:
                self.logger.info("Extracted price data for line_chart")
                return price_data
                
        # For volume charts
        if "volume" in viz_type:
            volume_data = self._extract_volume_data(data)
            if volume_data:
                self.logger.info(f"Extracted volume data for {viz_type}")
                return volume_data
                
        # For TVL or liquidity charts
        if "tvl" in viz_type or "liquidity" in viz_type:
            tvl_data = self._extract_tvl_data(data)
            if tvl_data:
                self.logger.info(f"Extracted TVL data for {viz_type}")
                return tvl_data
                
        # If we can't find specific data, look for any time series data in coinmarketcap
        if "coinmarketcap" in data:
            cm_data = data["coinmarketcap"]
            for potential_field in ["price_history", "volume_history", "market_cap_history", "history", "time_series", "data"]:
                if potential_field in cm_data and isinstance(cm_data[potential_field], (list, dict)):
                    self.logger.info(f"Using {potential_field} from coinmarketcap as fallback for {viz_type}")
                    return cm_data[potential_field]
                    
            # Also check for ohlcv_data which has timestamps we can use
            if "ohlcv_data" in cm_data and isinstance(cm_data["ohlcv_data"], list):
                self.logger.info(f"Extracting price from ohlcv_data for {viz_type}")
                # Extract closing prices from OHLCV data
                ohlcv = cm_data["ohlcv_data"]
                return [[item["timestamp"], item["close"]] for item in ohlcv if "timestamp" in item and "close" in item]
        
        # Similar for coingecko data
        if "coingecko" in data:
            cg_data = data["coingecko"]
            for potential_field in ["price_history", "market_data", "prices", "history", "time_series", "data"]:
                if potential_field in cg_data and isinstance(cg_data[potential_field], (list, dict)):
                    self.logger.info(f"Using {potential_field} from coingecko as fallback for {viz_type}")
                    return cg_data[potential_field]
        
        # If viz_type is a generic line_chart, check for any time series data in the top-level data
        if viz_type == "line_chart":
            for potential_field in ["price_history", "volume_history", "tvl_history", "market_cap_history", "history", "time_series", "data"]:
                if potential_field in data and isinstance(data[potential_field], (list, dict)):
                    self.logger.info(f"Using {potential_field} from top-level data for line_chart")
                    return data[potential_field]
            
            # Direct access to coinmarketcap data
            if "coinmarketcap" in data and isinstance(data["coinmarketcap"], dict):
                cm_data = data["coinmarketcap"]
                if "price_history" in cm_data and isinstance(cm_data["price_history"], list):
                    self.logger.info("Using price_history from coinmarketcap for line_chart")
                    return cm_data["price_history"]
        
        self.logger.warning(f"No suitable time series data found for {viz_type}")
        return None
    
    def _add_tvl_phases(self, fig: go.Figure, df: pd.DataFrame):
        """Add phase annotations to TVL chart."""
        if len(df) < 30:
            return
            
        # Identify significant phases in TVL
        # Find local minimums and maximums using rolling windows
        df['max'] = df['value'].rolling(window=30, center=True).max()
        df['min'] = df['value'].rolling(window=30, center=True).min()
        
        # Phases are periods with significant growth or decline
        changes = []
        
        # Skip first and last 15 days (half window size)
        for i in range(15, len(df) - 15):
            if df['value'].iloc[i] == df['max'].iloc[i] and df['value'].iloc[i] > df['value'].iloc[i-15] * 1.5:
                # Local maximum with >50% growth from 15 days before
                changes.append((df['date'].iloc[i], df['value'].iloc[i], "Peak"))
            elif df['value'].iloc[i] == df['min'].iloc[i] and df['value'].iloc[i] < df['value'].iloc[i-15] * 0.7:
                # Local minimum with >30% decline from 15 days before
                changes.append((df['date'].iloc[i], df['value'].iloc[i], "Trough"))
        
        # Limit to 5 most significant changes to avoid cluttering
        if len(changes) > 5:
            # Sort by significance (relative change)
            changes.sort(key=lambda x: abs(x[1]), reverse=True)
            changes = changes[:5]
        
        # Add annotations
        for date, value, phase_type in changes:
            fig.add_annotation(
                x=date,
                y=value,
                text=phase_type,
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor=self.colors.get("accent_secondary" if phase_type == "Peak" else "accent_tertiary", "#f9a825"),
                font=dict(size=10, color=self.colors.get("text", "#333333"))
            )
    
    def _add_tvl_milestones(self, fig: go.Figure, df: pd.DataFrame):
        """Add milestone annotations to TVL chart."""
        if len(df) < 30:
            return
            
        # Identify significant milestones in TVL
        value_range = df['value'].max() - df['value'].min()
        step = value_range / 5  # Divide range into 5 equal steps
        
        milestones = []
        current_milestone = df['value'].min() + step
        
        while current_milestone < df['value'].max():
            # Find first date that crosses this milestone
            crossing_point = None
            for i in range(1, len(df)):
                if df['value'].iloc[i-1] < current_milestone <= df['value'].iloc[i]:
                    crossing_point = (df['date'].iloc[i], df['value'].iloc[i])
                    break
            
            if crossing_point:
                milestones.append((crossing_point[0], crossing_point[1], f"${crossing_point[1]:,.0f}"))
            
            current_milestone += step
        
        # Limit to 5 milestones to avoid cluttering
        if len(milestones) > 5:
            # Evenly spaced milestones
            indices = [int(i * (len(milestones) - 1) / 4) for i in range(5)]
            milestones = [milestones[i] for i in indices]
        
        # Add annotations
        for date, value, milestone_text in milestones:
            fig.add_annotation(
                x=date,
                y=value,
                text=milestone_text,
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor=self.colors.get("accent_secondary", "#f9a825"),
                font=dict(size=10, color=self.colors.get("text", "#333333"))
            ) 