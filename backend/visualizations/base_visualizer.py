import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
from datetime import datetime

# Plotly imports
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

class BaseVisualizer:
    """
    Base class for all visualizers that provides common functionality.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """
        Initialize the base visualizer.
        
        Args:
            project_name: Name of the project
            style_manager: StyleManager instance for consistent styling
            logger: Optional logger instance
        """
        self.project_name = project_name
        self.style_manager = style_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Define visualization color schemes
        self.colors = self.style_manager.get_colors()
        self.visualization_config = self.style_manager.get_visualization_config()
        
        # Default chart dimensions
        self.width = self.visualization_config.get("width", 900)
        self.height = self.visualization_config.get("height", 600)
        
        # Default theme (light or dark)
        self.theme = "light"
        self.output_dir = os.path.join("reports", self.project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Ensure kaleido is configured for high-quality exports
        pio.kaleido.scope.default_scale = 2.0  # 2x scaling for higher resolution
        pio.kaleido.scope.default_format = "png"
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a visualization. This method should be implemented by subclasses.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, error_message: str)
        """
        raise NotImplementedError("Subclasses must implement create_visualization")
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the provided data is usable for visualization.
        
        Args:
            data: Data to check
            viz_type: Optional visualization type for specific checks
            
        Returns:
            True if data is usable, False otherwise
        """
        if not data:
            return False
            
        # Check data is a dictionary or potentially usable list
        if not isinstance(data, dict) and not (isinstance(data, list) and len(data) > 0):
            return False
            
        # Handle direct list inputs (common for time series data)
        if isinstance(data, list) and len(data) > 1:
            # If it's a list of lists or dicts, it might be time series data
            if all(isinstance(item, list) for item in data) or all(isinstance(item, dict) for item in data):
                return True
                
        # From here on, treat as dictionary
        if not isinstance(data, dict):
            return False
            
        # Check for explicit unavailability flag
        if data.get("data_unavailable", False):
            return False
            
        # Check for error-only dictionaries
        keys = set(data.keys())
        if keys.issubset({'error', 'errors', 'available_tools', 'message', 'data_unavailable'}):
            return False
            
        # General check - is there meaningful data?
        for source, source_data in data.items():
            if source_data:
                # Handle when source_data is a dictionary
                if isinstance(source_data, dict) and not source_data.get("data_unavailable", False):
                    # Check if the dict has any meaningful data
                    for key, value in source_data.items():
                        if value and key not in {'error', 'errors', 'available_tools', 'message', 'data_unavailable'}:
                            return True
                            
                # Handle when source_data is a list (e.g., direct time series data)
                elif isinstance(source_data, list) and len(source_data) > 0:
                    return True
                
        # If data contains a direct tvl_history or price_history key with list values
        if ('tvl_history' in data and isinstance(data['tvl_history'], list) and data['tvl_history']) or \
           ('price_history' in data and isinstance(data['price_history'], list) and data['price_history']) or \
           ('volume_history' in data and isinstance(data['volume_history'], list) and data['volume_history']):
            return True
                
        return False
    
    def _prepare_timeseries_data(self, time_series_data: Any) -> pd.DataFrame:
        """
        Convert various time series data formats to a standardized DataFrame.
        
        Args:
            time_series_data: Time series data in various formats
            
        Returns:
            Pandas DataFrame with 'date' and 'value' columns
        """
        if time_series_data is None:
            return None
            
        # If it's already a DataFrame, ensure it has date and value columns
        if isinstance(time_series_data, pd.DataFrame):
            df = time_series_data.copy()
            # Rename columns if needed
            if 'date' not in df.columns and 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp'])
            elif 'date' not in df.columns and 'time' in df.columns:
                df['date'] = pd.to_datetime(df['time'])
                
            if 'value' not in df.columns:
                # Try to find a value column
                value_columns = [c for c in df.columns if c in ['value', 'price', 'tvl', 'volume', 'close']]
                if value_columns:
                    df['value'] = df[value_columns[0]]
                    
            return df[['date', 'value']].sort_values('date') if 'date' in df.columns and 'value' in df.columns else None
        
        # Handle DeFi Llama TVL history format: [[timestamp, tvl], ...]
        # This is a special case for DeFi Llama data
        if isinstance(time_series_data, list) and time_series_data and len(time_series_data) > 0:
            # Handle the specific format from DeFi Llama: [timestamp, tvl]
            if isinstance(time_series_data[0], list) and len(time_series_data[0]) == 2:
                self.logger.info(f"Detected DeFi Llama TVL format with {len(time_series_data)} data points")
                dates = []
                values = []
                
                for point in time_series_data:
                    if len(point) == 2:
                        # Convert timestamp to datetime
                        if isinstance(point[0], (int, float)):
                            # Check if milliseconds or seconds
                            timestamp = point[0]
                            if timestamp > 1_000_000_000_000:  # Likely milliseconds
                                date = pd.to_datetime(timestamp, unit='ms')
                            else:  # Likely seconds
                                date = pd.to_datetime(timestamp, unit='s')
                        else:
                            # Try to parse as string
                            date = pd.to_datetime(point[0])
                            
                        dates.append(date)
                        values.append(float(point[1]) if isinstance(point[1], (int, float)) else None)
                
                df = pd.DataFrame({'date': dates, 'value': values})
                return df.sort_values('date')
            
            # Handle another common TVL history format: [{'date': timestamp, 'totalLiquidityUSD': value}, ...]
            if isinstance(time_series_data[0], dict) and 'date' in time_series_data[0] and 'totalLiquidityUSD' in time_series_data[0]:
                self.logger.info(f"Detected DeFi Llama totalLiquidityUSD format with {len(time_series_data)} data points")
                dates = []
                values = []
                
                for point in time_series_data:
                    # Convert timestamp to datetime
                    timestamp = point['date']
                    if isinstance(timestamp, (int, float)):
                        # Check if milliseconds or seconds
                        if timestamp > 1_000_000_000_000:  # Likely milliseconds
                            date = pd.to_datetime(timestamp, unit='ms')
                        else:  # Likely seconds
                            date = pd.to_datetime(timestamp, unit='s')
                    else:
                        # Try to parse as string
                        date = pd.to_datetime(timestamp)
                        
                    dates.append(date)
                    values.append(float(point['totalLiquidityUSD']) if isinstance(point['totalLiquidityUSD'], (int, float)) else None)
                
                df = pd.DataFrame({'date': dates, 'value': values})
                return df.sort_values('date')
            
        # Handle list of lists format: [[timestamp, value], ...]
        if isinstance(time_series_data, list) and time_series_data:
            if isinstance(time_series_data[0], list) and len(time_series_data[0]) >= 2:
                dates = []
                values = []
                
                for point in time_series_data:
                    if len(point) >= 2:
                        # Convert timestamp to datetime
                        if isinstance(point[0], (int, float)):
                            # Check if milliseconds or seconds
                            timestamp = point[0]
                            if timestamp > 1_000_000_000_000:  # Likely milliseconds
                                date = pd.to_datetime(timestamp, unit='ms')
                            else:  # Likely seconds
                                date = pd.to_datetime(timestamp, unit='s')
                        else:
                            # Try to parse as string
                            date = pd.to_datetime(point[0])
                            
                        dates.append(date)
                        values.append(float(point[1]) if isinstance(point[1], (int, float)) else None)
                
                df = pd.DataFrame({'date': dates, 'value': values})
                return df.sort_values('date')
            
        # Handle list of dicts format: [{'timestamp': t, 'value': v}, ...]
        if isinstance(time_series_data, list) and time_series_data:
            if isinstance(time_series_data[0], dict):
                # Determine the timestamp key
                timestamp_keys = [k for k in time_series_data[0] if k in ['timestamp', 'date', 'time']]
                if not timestamp_keys:
                    return None
                    
                timestamp_key = timestamp_keys[0]
                
                # Determine the value key
                value_keys = [k for k in time_series_data[0] if k in ['value', 'price', 'tvl', 'volume', 'close', 'totalLiquidityUSD']]
                if not value_keys:
                    # Try to find any numeric values for fallback
                    for k, v in time_series_data[0].items():
                        if isinstance(v, (int, float)) and k != timestamp_key:
                            value_keys = [k]
                            break
                
                if not value_keys:
                    return None
                    
                value_key = value_keys[0]
                
                dates = []
                values = []
                
                for point in time_series_data:
                    if timestamp_key in point and value_key in point:
                        # Convert timestamp to datetime
                        timestamp = point[timestamp_key]
                        if isinstance(timestamp, (int, float)):
                            # Check if milliseconds or seconds
                            if timestamp > 1_000_000_000_000:  # Likely milliseconds
                                date = pd.to_datetime(timestamp, unit='ms')
                            else:  # Likely seconds
                                date = pd.to_datetime(timestamp, unit='s')
                        else:
                            # Try to parse as string
                            date = pd.to_datetime(timestamp)
                            
                        dates.append(date)
                        values.append(float(point[value_key]) if isinstance(point[value_key], (int, float)) else None)
                
                df = pd.DataFrame({'date': dates, 'value': values})
                return df.sort_values('date')
        
        # Handle dictionary format: {'timestamp1': value1, 'timestamp2': value2, ...}
        if isinstance(time_series_data, dict):
            # If the dict has 'tvl_history' key, extract that
            if 'tvl_history' in time_series_data and isinstance(time_series_data['tvl_history'], list):
                return self._prepare_timeseries_data(time_series_data['tvl_history'])
            
            dates = []
            values = []
            
            for timestamp, value in time_series_data.items():
                if isinstance(value, (int, float)):
                    # Try to parse timestamp
                    try:
                        date = pd.to_datetime(timestamp)
                        dates.append(date)
                        values.append(float(value))
                    except:
                        # Skip invalid dates
                        pass
            
            if dates and values:
                df = pd.DataFrame({'date': dates, 'value': values})
                return df.sort_values('date')
        
        # Could not parse data
        self.logger.warning(f"Could not parse time series data of type {type(time_series_data)}")
        if isinstance(time_series_data, list) and time_series_data:
            self.logger.warning(f"First element type: {type(time_series_data[0])}")
            if isinstance(time_series_data[0], dict):
                self.logger.warning(f"First element keys: {time_series_data[0].keys()}")
        return None
    
    def _extract_data_source(self, data: Dict[str, Any], source_name: str, field_name: Optional[str] = None) -> Any:
        """
        Extract data from a specific source and field.
        
        Args:
            data: Data dictionary
            source_name: Name of the source to extract from
            field_name: Optional field name to extract
            
        Returns:
            Extracted data or None if not found
        """
        if source_name in data:
            source_data = data[source_name]
            if field_name and field_name in source_data:
                return source_data[field_name]
            return source_data
        return None 