import logging
import json
import os
from typing import Dict, Any, List, Optional, Union, Tuple
from backend.state import ResearchState

class DataStandardizer:
    """
    Utility class to standardize data formats for visualizations and ensure
    consistent access patterns across agents.
    
    This class handles:
    1. Data normalization for visualization formats
    2. Consistent section-aligned data structure
    3. Data validation and error handling
    4. Pre-processing for visualization requirements
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the DataStandardizer with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    def standardize_state_data(self, state: Union[ResearchState, Dict], report_config: Dict) -> Union[ResearchState, Dict]:
        """
        Standardize data in the state object to ensure consistent access patterns.
        
        Args:
            state: Research state object or dictionary
            report_config: Report configuration with section definitions
            
        Returns:
            Updated state with standardized data
        """
        self.logger.info("Standardizing state data")
        
        # Determine if state is dict or object
        is_state_dict = isinstance(state, dict)
        
        # Get project name for cache files
        project_name = state.get("project_name", "unknown") if is_state_dict else getattr(state, "project_name", "unknown")
        
        # Initialize cache manager
        try:
            from backend.utils.cache_utils import CacheManager
            cache_mgr = CacheManager(project_name=project_name, logger=self.logger)
        except ImportError:
            self.logger.warning("CacheManager not available, skipping cache writing")
            cache_mgr = None
        
        # Ensure visualization_data exists
        if is_state_dict:
            if "visualization_data" not in state:
                state["visualization_data"] = {}
        else:
            if not hasattr(state, "visualization_data"):
                state.visualization_data = {}
                
        # Process each section in report_config
        sections = report_config.get("sections", [])
        for section in sections:
            section_title = section.get("title", "")
            if not section_title:
                continue
                
            # Normalize section title for consistent keys
            normalized_section = self._normalize_section_name(section_title)
            
            # Get data sources required for this section
            data_sources = section.get("data_sources", [])
            
            # Get visualizations for this section
            visualizations = section.get("visualizations", [])
            
            # Standardize data for each visualization
            for viz in visualizations:
                # Check if viz is a dictionary before trying to access it
                if not isinstance(viz, dict):
                    self.logger.warning(f"Visualization in section '{section_title}' is not a dictionary: {viz}")
                    continue
                    
                viz_type = viz.get("type", "")
                viz_id = viz.get("id", "")
                data_source = viz.get("data_source", "")
                data_field = viz.get("data_field", "")
                
                if not viz_type or not viz_id:
                    continue
                    
                # Prepare visualization data
                viz_data = self._prepare_visualization_data(state, viz, section_title, data_sources)
                
                # Store standardized data in state.visualization_data
                if viz_data:
                    if is_state_dict:
                        if normalized_section not in state["visualization_data"]:
                            state["visualization_data"][normalized_section] = {}
                        state["visualization_data"][normalized_section][viz_id] = viz_data
                    else:
                        if not hasattr(state.visualization_data, normalized_section):
                            setattr(state.visualization_data, normalized_section, {})
                        section_viz_data = getattr(state.visualization_data, normalized_section)
                        section_viz_data[viz_id] = viz_data
                    
                    # Write to cache if cache manager is available
                    if cache_mgr and data_source and data_field:
                        try:
                            # Save standardized data to cache
                            cache_key = f"{data_source}/{data_field}"
                            self.logger.info(f"Writing standardized data to cache: {cache_key}")
                            cache_mgr.save(viz_data, data_source, data_field, "")
                        except Exception as e:
                            self.logger.error(f"Error writing to cache: {str(e)}")
        
        self.logger.info("State data standardization complete")
        return state
    
    def _normalize_section_name(self, section_title: str) -> str:
        """
        Normalize section title for consistent key naming.
        
        Args:
            section_title: Original section title
            
        Returns:
            Normalized section name (lowercase with underscores)
        """
        return section_title.lower().replace(" ", "_")
    
    def _prepare_visualization_data(self, state: Union[ResearchState, Dict], 
                                   viz_config: Dict, 
                                   section_title: str,
                                   data_sources: List[str]) -> Dict:
        """
        Prepare standardized data for a specific visualization.
        
        Args:
            state: Research state
            viz_config: Visualization configuration
            section_title: Section title
            data_sources: List of data sources for this section
            
        Returns:
            Standardized data for the visualization
        """
        viz_type = viz_config.get("type", "")
        viz_id = viz_config.get("id", "")
        data_field = viz_config.get("data_field", "")
        
        self.logger.info(f"Preparing data for visualization: {viz_id} ({viz_type})")
        
        # Get data from state based on data sources
        raw_data = self._extract_data_from_state(state, data_sources, data_field)
        
        # If no data found, return empty dict
        if not raw_data:
            self.logger.warning(f"No data found for visualization: {viz_id}")
            return {}
            
        # Standardize data based on visualization type
        if viz_type == "line_chart":
            return self._standardize_line_chart_data(raw_data, viz_config)
        elif viz_type == "bar_chart":
            return self._standardize_bar_chart_data(raw_data, viz_config)
        elif viz_type == "pie_chart":
            return self._standardize_pie_chart_data(raw_data, viz_config)
        elif viz_type == "table":
            return self._standardize_table_data(raw_data, viz_config)
        elif viz_type == "candlestick":
            return self._standardize_candlestick_data(raw_data, viz_config)
        else:
            # For unknown types, return raw data with minimal processing
            return self._standardize_generic_data(raw_data, viz_config)
    
    def _extract_data_from_state(self, state: Union[ResearchState, Dict], 
                               data_sources: List[str],
                               data_field: str) -> Dict:
        """
        Extract relevant data from state based on data sources.
        
        Args:
            state: Research state
            data_sources: List of data sources to check
            data_field: Specific data field to extract
            
        Returns:
            Dictionary of extracted data
        """
        result = {}
        is_state_dict = isinstance(state, dict)
        
        # First try to get data from state.data
        if is_state_dict:
            state_data = state.get("data", {})
            
            # Check each data source
            for source in data_sources:
                if source in state_data:
                    source_data = state_data[source]
                    
                    # If data_field specified, look for it
                    if data_field and isinstance(source_data, dict):
                        found = False
                        # First look for exact match
                        if data_field in source_data:
                            result[source] = {data_field: source_data[data_field]}
                            found = True
                        else:
                            # Then look for field names containing the data_field
                            for field, field_data in source_data.items():
                                if data_field.lower() in field.lower():
                                    self.logger.info(f"Found field '{field}' matching data_field '{data_field}'")
                                    result[source] = {field: field_data}
                                    found = True
                                    break
                        
                        # If still not found, log and continue
                        if not found:
                            self.logger.warning(f"Could not find data field '{data_field}' in source '{source}'")
                    else:
                        # Otherwise take all data for this source
                        result[source] = source_data
        else:
            # Handle ResearchState object
            if hasattr(state, "data"):
                state_data = state.data
                
                # Check each data source
                for source in data_sources:
                    if hasattr(state_data, source):
                        source_data = getattr(state_data, source)
                        
                        # If data_field specified, look for it
                        if data_field and isinstance(source_data, dict):
                            found = False
                            # First look for exact match
                            if data_field in source_data:
                                result[source] = {data_field: source_data[data_field]}
                                found = True
                            else:
                                # Then look for field names containing the data_field
                                for field, field_data in source_data.items():
                                    if data_field.lower() in field.lower():
                                        self.logger.info(f"Found field '{field}' matching data_field '{data_field}'")
                                        result[source] = {field: field_data}
                                        found = True
                                        break
                            
                            # If still not found, log and continue
                            if not found:
                                self.logger.warning(f"Could not find data field '{data_field}' in source '{source}'")
                        else:
                            # Otherwise take all data for this source
                            result[source] = source_data
        
        return result
    
    def _standardize_line_chart_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for line charts."""
        result = {
            "type": "line_chart",
            "title": viz_config.get("title", ""),
            "x_title": viz_config.get("x_title", "Date"),
            "y_title": viz_config.get("y_title", "Value"),
            "series": []
        }
        
        # Process raw data to extract time series
        for source, source_data in raw_data.items():
            if isinstance(source_data, dict):
                for field, field_data in source_data.items():
                    # Look for time series data (list of dicts with date/time and value)
                    if isinstance(field_data, list):
                        series = {
                            "name": field,
                            "data": []
                        }
                        
                        # Process each data point
                        for point in field_data:
                            if isinstance(point, dict):
                                # Look for common time series formats
                                x_value = None
                                y_value = None
                                
                                # Try different key patterns for x-axis (date/time)
                                for x_key in ["date", "timestamp", "time", "x"]:
                                    if x_key in point:
                                        x_value = point[x_key]
                                        break
                                
                                # Try different key patterns for y-axis (value)
                                for y_key in ["value", "price", "amount", "y"]:
                                    if y_key in point:
                                        y_value = point[y_key]
                                        break
                                
                                # If both x and y found, add to series
                                if x_value is not None and y_value is not None:
                                    series["data"].append({"x": x_value, "y": y_value})
                        
                        # Only add series if it has data
                        if series["data"]:
                            result["series"].append(series)
        
        return result
    
    def _standardize_bar_chart_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for bar charts."""
        result = {
            "type": "bar_chart",
            "title": viz_config.get("title", ""),
            "x_title": viz_config.get("x_title", "Category"),
            "y_title": viz_config.get("y_title", "Value"),
            "categories": [],
            "series": []
        }
        
        # Process raw data to extract categories and values
        for source, source_data in raw_data.items():
            if isinstance(source_data, dict):
                for field, field_data in source_data.items():
                    # Handle dictionary format (category: value)
                    if isinstance(field_data, dict):
                        categories = []
                        values = []
                        
                        for category, value in field_data.items():
                            if isinstance(value, (int, float)):
                                categories.append(category)
                                values.append(value)
                        
                        if categories and values:
                            result["categories"] = categories
                            result["series"].append({
                                "name": field,
                                "data": values
                            })
                    
                    # Handle list of dicts format
                    elif isinstance(field_data, list):
                        categories = []
                        values = []
                        
                        for item in field_data:
                            if isinstance(item, dict):
                                # Try to find category and value keys
                                category = None
                                value = None
                                
                                for cat_key in ["category", "name", "label"]:
                                    if cat_key in item:
                                        category = item[cat_key]
                                        break
                                
                                for val_key in ["value", "amount", "count"]:
                                    if val_key in item:
                                        value = item[val_key]
                                        break
                                
                                if category is not None and value is not None:
                                    categories.append(category)
                                    values.append(value)
                        
                        if categories and values:
                            result["categories"] = categories
                            result["series"].append({
                                "name": field,
                                "data": values
                            })
        
        return result
    
    def _standardize_pie_chart_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for pie charts."""
        result = {
            "type": "pie_chart",
            "title": viz_config.get("title", ""),
            "data": []
        }
        
        # Process raw data to extract labels and values
        for source, source_data in raw_data.items():
            if isinstance(source_data, dict):
                for field, field_data in source_data.items():
                    # Handle dictionary format (label: value)
                    if isinstance(field_data, dict):
                        for label, value in field_data.items():
                            if isinstance(value, (int, float)):
                                result["data"].append({
                                    "name": label,
                                    "value": value
                                })
                    
                    # Handle list of dicts format
                    elif isinstance(field_data, list):
                        for item in field_data:
                            if isinstance(item, dict):
                                # Try to find label and value keys
                                label = None
                                value = None
                                
                                for label_key in ["name", "label", "category"]:
                                    if label_key in item:
                                        label = item[label_key]
                                        break
                                
                                for value_key in ["value", "amount", "percentage"]:
                                    if value_key in item:
                                        value = item[value_key]
                                        break
                                
                                if label is not None and value is not None:
                                    result["data"].append({
                                        "name": label,
                                        "value": value
                                    })
        
        return result
    
    def _standardize_table_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for tables."""
        result = {
            "type": "table",
            "title": viz_config.get("title", ""),
            "headers": [],
            "rows": []
        }
        
        # Process raw data to extract table data
        for source, source_data in raw_data.items():
            if isinstance(source_data, dict):
                for field, field_data in source_data.items():
                    # Handle list of dicts format
                    if isinstance(field_data, list) and field_data:
                        # Extract headers from first item
                        first_item = field_data[0]
                        if isinstance(first_item, dict):
                            result["headers"] = list(first_item.keys())
                            
                            # Extract rows
                            for item in field_data:
                                if isinstance(item, dict):
                                    row = [item.get(header, "") for header in result["headers"]]
                                    result["rows"].append(row)
                        
                        # If we found table data, break out of the loop
                        if result["headers"] and result["rows"]:
                            break
        
        return result
    
    def _standardize_candlestick_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for candlestick charts."""
        result = {
            "type": "candlestick",
            "title": viz_config.get("title", ""),
            "data": []
        }
        
        # Process raw data to extract OHLC data
        for source, source_data in raw_data.items():
            if isinstance(source_data, dict):
                for field, field_data in source_data.items():
                    # Handle list of dicts format
                    if isinstance(field_data, list):
                        for item in field_data:
                            if isinstance(item, dict):
                                # Look for OHLC data
                                date = None
                                open_price = None
                                high_price = None
                                low_price = None
                                close_price = None
                                
                                # Try to find date
                                for date_key in ["date", "timestamp", "time"]:
                                    if date_key in item:
                                        date = item[date_key]
                                        break
                                
                                # Try to find OHLC values
                                for open_key in ["open", "open_price"]:
                                    if open_key in item:
                                        open_price = item[open_key]
                                        break
                                
                                for high_key in ["high", "high_price"]:
                                    if high_key in item:
                                        high_price = item[high_key]
                                        break
                                
                                for low_key in ["low", "low_price"]:
                                    if low_key in item:
                                        low_price = item[low_key]
                                        break
                                
                                for close_key in ["close", "close_price"]:
                                    if close_key in item:
                                        close_price = item[close_key]
                                        break
                                
                                # If all OHLC values found, add to result
                                if all([date, open_price, high_price, low_price, close_price]):
                                    result["data"].append({
                                        "date": date,
                                        "open": open_price,
                                        "high": high_price,
                                        "low": low_price,
                                        "close": close_price
                                    })
        
        return result
    
    def _standardize_generic_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """
        Standardize data for unknown visualization types.
        This is a fallback method for custom or unsupported visualization types.
        """
        result = {
            "type": viz_config.get("type", "unknown"),
            "title": viz_config.get("title", ""),
            "raw_data": raw_data
        }
        
        return result
    
    def validate_visualization_data(self, viz_data: Dict, viz_type: str) -> Tuple[bool, str]:
        """
        Validate visualization data to ensure it meets requirements.
        
        Args:
            viz_data: Standardized visualization data
            viz_type: Type of visualization
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not viz_data:
            return False, "No data available"
            
        if viz_type == "line_chart":
            if not viz_data.get("series"):
                return False, "No series data available for line chart"
            for series in viz_data.get("series", []):
                if not series.get("data"):
                    return False, f"No data points in series '{series.get('name', 'unknown')}'"
            return True, ""
            
        elif viz_type == "bar_chart":
            if not viz_data.get("categories"):
                return False, "No categories available for bar chart"
            if not viz_data.get("series"):
                return False, "No series data available for bar chart"
            return True, ""
            
        elif viz_type == "pie_chart":
            if not viz_data.get("data"):
                return False, "No data available for pie chart"
            return True, ""
            
        elif viz_type == "table":
            if not viz_data.get("headers"):
                return False, "No headers available for table"
            if not viz_data.get("rows"):
                return False, "No rows available for table"
            return True, ""
            
        elif viz_type == "candlestick":
            if not viz_data.get("data"):
                return False, "No data available for candlestick chart"
            return True, ""
            
        # For unknown types, just check if raw_data exists
        return "raw_data" in viz_data, "No raw data available" 