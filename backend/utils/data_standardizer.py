# backend/data_standardizer.py
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
    
    def __init__(self, logger: Optional[logging.Logger] = None, state_manager: Optional[Any] = None):
        """Initialize the DataStandardizer with optional logger and state_manager."""
        self.logger = logger or logging.getLogger(__name__)
        self.state_manager = state_manager
        if not self.state_manager:
            # Try to import and instantiate a default StateManager if not provided
            try:
                from backend.utils.state_manager import StateManager
                self.state_manager = StateManager(logger=self.logger)
                self.logger.info("DataStandardizer initialized with a new default StateManager instance.")
            except ImportError:
                self.logger.error("StateManager could not be imported for DataStandardizer, and none was provided. State access will fail.")
                # This will likely lead to AttributeErrors later if state_manager methods are called.
        else:
            self.logger.info("DataStandardizer initialized with a provided StateManager instance.")
        
        # Default visualization mappings in case visualization_mapping.json is missing
        self.default_viz_mapping = {
            "key_metrics_table": {
                "type": "table",
                "data_source": "coinmarketcap",
                "data_field": ""
            },
            "price_trend_chart": {
                "type": "line_chart",
                "data_source": "coinmarketcap",
                "data_field": "price_history",
                "x_field": "date",
                "y_field": "price",
                "line_name": "Price"
            },
            "whitepaper_link": {
                "type": "table",
                "data_source": "tokenomics",
                "data_field": "documentation_url"
            },
            "tokenomics_pie_chart": {
                "type": "pie_chart",
                "data_source": "tokenomics",
                "data_field": "data"
            },
            "chain_distribution_chart": {
                "type": "pie_chart",
                "data_source": "defillama",
                "data_field": "currentChainTvls"
            },
            "candlestick_chart": {
                "type": "candlestick_chart",
                "data_source": "coinmarketcap",
                "data_field": "ohlcv"
            },
            "volume_chart": {
                "type": "line_chart",
                "data_source": "coinmarketcap",
                "data_field": "volume_history",
                "x_field": "date",
                "y_field": "volume",
                "line_name": "Volume"
            },
            "competitor_comparison_chart": {
                "type": "comparison_chart",
                "data_source": "multi",
                "data_field": "competitors"
            },
            "liquidity_trends_chart": {
                "type": "line_chart",
                "data_source": "coinmarketcap",
                "data_field": "volume_history"
            },
            "adoption_metrics_table": {
                "type": "table",
                "data_source": "multi",
                "data_field": ""
            },
            "tvl_chart": {
                "type": "line_chart",
                "data_source": "defillama",
                "data_field": "tvl_history"
            },
            "tvl_milestone_chart": {
                "type": "line_chart",
                "data_source": "defillama",
                "data_field": "tvl_history"
            },
            "tvl_phases_chart": {
                "type": "line_chart",
                "data_source": "defillama",
                "data_field": "tvl_history"
            },
            "monthly_growth_chart": {
                "type": "line_chart",
                "data_source": "defillama",
                "data_field": "tvl_history"
            }
        }
    
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
        
        # Load visualization mapping
        viz_mapping = self.default_viz_mapping.copy() # Start with defaults, use .copy() to avoid modifying class default
        try:
            # Construct path to visualization_mapping.json
            # Assuming data_standardizer.py is in backend/utils/
            # and visualization_mapping.json is in config/ at the project root
            current_file_path = os.path.abspath(__file__)
            utils_dir = os.path.dirname(current_file_path)
            backend_dir = os.path.dirname(utils_dir)
            project_root = os.path.dirname(backend_dir)
            
            mapping_file_name = "visualization_mapping.json"
            mapping_file_path = os.path.join(backend_dir, "config", mapping_file_name)
            
            self.logger.info(f"Attempting to load visualization mapping from: {mapping_file_path}")
            with open(mapping_file_path, "r") as f:
                external_mapping = json.load(f).get("visualization_types", {})
                viz_mapping.update(external_mapping) # Update with loaded ones
                self.logger.info(f"Successfully loaded and merged {mapping_file_name} from {mapping_file_path}")
        except FileNotFoundError:
            self.logger.warning(f"{mapping_file_name} not found at {mapping_file_path}. Using default mappings.")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding {mapping_file_name} from {mapping_file_path}: {str(e)}. Using default mappings.")
        except Exception as e:
            self.logger.error(f"Unexpected error loading {mapping_file_name} from {mapping_file_path}: {str(e)}. Using default mappings.")
        
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
                # Handle both dictionary and string visualizations
                if isinstance(viz, dict):
                    viz_config = viz
                    viz_id = viz_config.get("id", "")
                    viz_type = viz_config.get("type", "")
                    data_source = viz_config.get("data_source", "")
                    data_field = viz_config.get("data_field", "")
                elif isinstance(viz, str):
                    self.logger.info(f"Processing string visualization: {viz}")
                    viz_id = viz
                    viz_config = viz_mapping.get(viz_id, {})
                    if not viz_config:
                        self.logger.warning(f"No mapping found for visualization: {viz_id}")
                        continue
                    viz_type = viz_config.get("type", "")
                    data_source = viz_config.get("data_source", "")
                    data_field = viz_config.get("data_field", "")
                else:
                    self.logger.warning(f"Invalid visualization format in section '{section_title}': {viz}")
                    continue
                
                if not viz_type or not viz_id:
                    self.logger.warning(f"Skipping visualization with missing type or id: {viz_id}")
                    continue
                    
                # Prepare visualization data
                self.logger.debug(f"Preparing data for viz_id: {viz_id}, type: {viz_type}, source: {data_source}, field: {data_field}")
                viz_data = self._prepare_visualization_data(state, viz_config, viz_id, section_title, data_sources)
                
                # Store standardized data in state.visualization_data
                if viz_data:
                    self.logger.debug(f"Storing viz_data for {viz_id}: {viz_data}")
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
                            cache_key_display = f"{data_source}/{data_field}" # For logging
                            self.logger.info(f"Writing standardized data to cache: {cache_key_display}")
                            # Use viz_id as query parameter to make cache key more specific for standardized viz data
                            query_for_cache = viz_id if viz_id else "general"
                            cache_mgr.save(viz_data, data_source, data_field, query_for_cache)
                        except Exception as e:
                            self.logger.error(f"Error writing to cache: {str(e)}")
                else:
                    self.logger.warning(f"No viz_data prepared for {viz_id}")
        
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
                                   viz_id: str,
                                   section_title: str,
                                   section_data_sources: List[str]) -> Dict:
        """
        Prepare standardized data for a specific visualization.
        
        Args:
            state: Research state
            viz_config: Visualization configuration
            viz_id: The unique identifier for the visualization (e.g., "key_metrics_table")
            section_title: Section title
            section_data_sources: List of data sources available for this section (from report_config)
            
        Returns:
            Standardized data for the visualization
        """
        viz_type = viz_config.get("type", "")
        data_field = viz_config.get("data_field", "")
        specific_source_for_viz = viz_config.get("data_source")
        normalized_section = self._normalize_section_name(section_title)

        self.logger.info(f"Preparing data for visualization: {viz_id} (type: {viz_type}, field: '{data_field}', specific_source_config: {specific_source_for_viz}) in section '{section_title}' (normalized: {normalized_section})")

        effective_data_sources_to_check = []
        if specific_source_for_viz and specific_source_for_viz != "multi":
            if specific_source_for_viz in section_data_sources:
                effective_data_sources_to_check = [specific_source_for_viz]
                self.logger.info(f"Viz '{viz_id}' uses specific source '{specific_source_for_viz}', which is available in section.")
            else:
                self.logger.warning(f"Visualization '{viz_id}' requests specific source '{specific_source_for_viz}', but it's NOT listed in section's available sources: {section_data_sources}. Data extraction for this field from this source will likely fail or be skipped.")
                effective_data_sources_to_check = [specific_source_for_viz]

        elif specific_source_for_viz == "multi":
            effective_data_sources_to_check = section_data_sources
            self.logger.info(f"Viz '{viz_id}' uses 'multi' source, checking all section sources: {section_data_sources}")
        else:
            effective_data_sources_to_check = section_data_sources
            self.logger.info(f"Viz '{viz_id}' has no specific_source or it's empty, defaulting to all section sources: {section_data_sources}")
        
        self.logger.debug(f"Effective sources to check for viz '{viz_id}': {effective_data_sources_to_check} for data_field '{data_field}'")
        
        # Get data from state based on data sources
        raw_data = self._extract_data_from_state(state, effective_data_sources_to_check, data_field, normalized_section)
        
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
    
    def _extract_data_from_state(self, state: ResearchState,
                                 sources_to_check: List[str],
                                 data_field: str,
                                 normalized_section_name: str) -> Any:
        self.logger.debug(f"Attempting to extract '{data_field}' from sources {sources_to_check} in section '{normalized_section_name}'")
        
        top_level_data_dict = None
        if hasattr(state, "data") and isinstance(state.data, dict):
            top_level_data_dict = state.data
        elif isinstance(state, dict) and "data" in state and isinstance(state["data"], dict):
            top_level_data_dict = state["data"]
        else:
            self.logger.warning(f"state.data is not a dictionary or not found. Cannot extract batch_data effectively.")
            return None

        batch_data_sources = top_level_data_dict.get("batch_data")
        if not isinstance(batch_data_sources, dict):
            self.logger.debug("state.data.batch_data is not a dictionary or not found.")
            batch_data_sources = {}

        section_specific_data_root = None
        if hasattr(state, "sections") and isinstance(state.sections, dict):
            section_specific_data_root = state.sections.get(normalized_section_name)
        elif isinstance(state, dict) and "sections" in state and isinstance(state.get("sections"), dict):
            section_specific_data_root = state.get("sections", {}).get(normalized_section_name)
        
        if not isinstance(section_specific_data_root, dict):
            self.logger.debug(f"No section-specific data found or not a dict for section '{normalized_section_name}'.")
            section_specific_data_root = {}

        for current_source_name in sources_to_check:
            self.logger.debug(f"Checking source: '{current_source_name}' for data_field: '{data_field}'")
            source_data_to_inspect = None
            data_location_message = ""

            # Attempt 1: Check batch_data for the current_source_name
            if current_source_name in batch_data_sources:
                source_data_to_inspect = batch_data_sources.get(current_source_name)
                data_location_message = f"from 'state.data.batch_data.{current_source_name}'"
                self.logger.debug(f"Found source '{current_source_name}' in batch_data. Type: {type(source_data_to_inspect)}")
            
            # Attempt 2: If not in batch_data, check section-specific data for the current_source_name
            if source_data_to_inspect is None and current_source_name in section_specific_data_root:
                source_data_to_inspect = section_specific_data_root.get(current_source_name)
                data_location_message = f"from section '{normalized_section_name}' specific data for source '{current_source_name}'"
                self.logger.debug(f"Found source '{current_source_name}' in section-specific data for '{normalized_section_name}'. Type: {type(source_data_to_inspect)}")

            if source_data_to_inspect is None:
                self.logger.debug(f"Source '{current_source_name}' not found in batch_data or section '{normalized_section_name}'. Trying next source.")
                continue # Try the next source in the list

            # Ensure source_data_to_inspect is a dictionary for consistent field extraction,
            # unless it's a special case like a direct string URL for tokenomics.
            if not isinstance(source_data_to_inspect, dict):
                if current_source_name == "tokenomics" and data_field in ["documentation_url", "whitepaper_url"] and isinstance(source_data_to_inspect, str):
                    self.logger.info(f"Treating raw string data from tokenomics {data_location_message} as value for '{data_field}'. Returning for source '{current_source_name}'.")
                    return source_data_to_inspect
                self.logger.warning(f"Data for source '{current_source_name}' {data_location_message} is not a dictionary (type: {type(source_data_to_inspect)}). Cannot extract specific fields.")
                if not data_field:
                    self.logger.info(f"Data_field is empty, returning the non-dict data found for '{current_source_name}' {data_location_message}.")
                    return source_data_to_inspect
                continue # Try next source if this one isn't a dict and data_field is expected
            
            self.logger.debug(f"Inspecting data for source '{current_source_name}' {data_location_message}. Keys: {list(source_data_to_inspect.keys())}")

            extracted_value = None
            if not data_field:  # For key_metrics_table etc., where the whole source_data is needed
                extracted_value = source_data_to_inspect
                self.logger.info(f"Using entire source_data from '{current_source_name}' {data_location_message} as data_field is empty.")
            else:
                extracted_value = source_data_to_inspect.get(data_field)
                if extracted_value is not None:
                    self.logger.info(f"Directly extracted '{data_field}' from source '{current_source_name}' {data_location_message}.")
                else:
                    if current_source_name == "tokenomics":
                        tokenomics_payload_to_check = source_data_to_inspect.get("data", source_data_to_inspect)
                        if isinstance(tokenomics_payload_to_check, dict):
                            if data_field == "data":
                                extracted_value = tokenomics_payload_to_check
                                self.logger.info(f"Extracted entire 'data' object for 'tokenomics' from '{current_source_name}' {data_location_message}.")
                            else:
                                extracted_value = tokenomics_payload_to_check.get(data_field)
                                if extracted_value is not None:
                                    self.logger.info(f"Extracted '{data_field}' for 'tokenomics' from its payload from '{current_source_name}' {data_location_message}.")
                                elif "data" in tokenomics_payload_to_check and isinstance(tokenomics_payload_to_check["data"], dict):
                                    extracted_value = tokenomics_payload_to_check["data"].get(data_field)
                                    if extracted_value is not None:
                                        self.logger.info(f"Extracted '{data_field}' for 'tokenomics' from its nested 'data.data' payload from '{current_source_name}' {data_location_message}.")
                        elif isinstance(tokenomics_payload_to_check, str) and data_field in ["documentation_url", "whitepaper_url"]:
                            extracted_value = tokenomics_payload_to_check
                            self.logger.info(f"Extracted '{data_field}' (string URL) directly for 'tokenomics' from '{current_source_name}' {data_location_message}.")

                    elif current_source_name == "coinmarketcap" and data_field in ["price_history", "volume_history"]:
                        self.logger.info(f"Attempting CoinMarketCap specific lookup for '{data_field}' from '{current_source_name}' {data_location_message}.")
                        cmc_actual_payload = source_data_to_inspect.get("data", source_data_to_inspect)
                        if isinstance(cmc_actual_payload, dict):
                            lookup_key_for_cmc = "ohlcv" if data_field == "price_history" else data_field
                            extracted_value = cmc_actual_payload.get(lookup_key_for_cmc)
                            if extracted_value is not None:
                                self.logger.info(f"Extracted CoinMarketCap '{lookup_key_for_cmc}' (for requested '{data_field}') from '{current_source_name}' {data_location_message}. Type: {type(extracted_value)}")
                            else:
                                self.logger.warning(f"Could not find '{lookup_key_for_cmc}' in CoinMarketCap payload from '{current_source_name}' {data_location_message}. Keys: {list(cmc_actual_payload.keys())}")
                        else:
                            self.logger.warning(f"CoinMarketCap data payload for '{data_field}' from '{current_source_name}' {data_location_message} is not a dict. Type: {type(cmc_actual_payload)}")

                    if extracted_value is None: # Generic fallback if not found by specific handlers for this source
                        data_payload_generic = source_data_to_inspect.get("data")
                        if isinstance(data_payload_generic, dict):
                            extracted_value = data_payload_generic.get(data_field)
                            if extracted_value is not None:
                                self.logger.info(f"Extracted '{data_field}' from nested 'data' key for source '{current_source_name}' {data_location_message}.")
            
            if extracted_value is not None:
                self.logger.info(f"Successfully extracted '{data_field if data_field else 'entire blob'}' from source '{current_source_name}'. Returning this value.")
                return extracted_value # Return as soon as data is found from one of the sources
            else:
                self.logger.debug(f"Data field '{data_field}' not found in source '{current_source_name}' {data_location_message}. Trying next source.")

        # If loop completes without returning, data_field was not found in any of the sources_to_check
        self.logger.warning(f"Could not find data field '{data_field}' in any of the specified sources: {sources_to_check} for section '{normalized_section_name}'.")
        return None
    
    def _standardize_line_chart_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for line charts."""
        result = {
            "type": "line_chart",
            "title": viz_config.get("title", ""),
            "x_title": viz_config.get("x_axis_title", "Date"),
            "y_title": viz_config.get("y_axis_title", "Value"),
            "series": []
        }

        # Get x and y field keys from viz_config, default to common names
        config_x_key = viz_config.get("x_field", "date")
        config_y_key = viz_config.get("y_field") # This is the semantic key like 'price' or 'volume'

        for source, data_payload in raw_data.items():
            series_data_points = []
            # Use line_name from viz_config if available, otherwise default to source or field name
            series_name = viz_config.get("line_name", source)

            if isinstance(data_payload, list):
                for point in data_payload:
                    if isinstance(point, dict):
                        x_value = point.get(config_x_key, point.get("timestamp", point.get("time")))
                        
                        y_value_candidate = None
                        if config_y_key == "price": # Semantic y_field for price
                            y_value_candidate = point.get("close", point.get("price"))
                        elif config_y_key == "volume": # Semantic y_field for volume
                            y_value_candidate = point.get("volume")
                        elif config_y_key: # Specific y_field provided in viz_config
                            y_value_candidate = point.get(config_y_key)
                        else: # Generic fallback if no y_field in viz_config
                            for generic_y_key in ["value", "tvl", "amount"]:
                                if generic_y_key in point:
                                    y_value_candidate = point[generic_y_key]
                                    break
                        
                        if x_value is not None and y_value_candidate is not None:
                            try:
                                y_value_numeric = float(y_value_candidate)
                                series_data_points.append({"x": x_value, "y": y_value_numeric})
                            except (ValueError, TypeError):
                                self.logger.debug(f"Skipping invalid y_value: {y_value_candidate} for x_value: {x_value} in series {series_name}")
                        else:
                            self.logger.debug(f"Skipping point in series {series_name} due to missing x ({x_value}) or y ({y_value_candidate}). Point: {point}")
                            
                    elif isinstance(point, (list, tuple)) and len(point) >= 2:
                        # Handle [timestamp, value] format if config_x_key and config_y_key are not specific enough
                        # This path might be less used if ohlcv data is dicts
                        x_value, y_value_candidate = point[0], point[1]
                        try:
                            y_value_numeric = float(y_value_candidate)
                            series_data_points.append({"x": x_value, "y": y_value_numeric})
                        except (ValueError, TypeError):
                             self.logger.debug(f"Skipping invalid y_value for [timestamp, value] pair: {y_value_candidate}")
            
            elif isinstance(data_payload, dict): # Handle cases where data_payload is a dict of values (less common for time series)
                self.logger.debug(f"Data_payload for source {source} is a dict, attempting to process if suitable for line chart.")
                # This part would need specific logic if a dict is meant to be a single series.
                # For now, primarily focusing on list of data points.

            if series_data_points:
                result["series"].append({
                    "name": series_name,
                    "data": series_data_points
                })
        
        self.logger.debug(f"Standardized line chart data: {result}")
        return result
    
    def _standardize_bar_chart_data(self, raw_data: Dict, viz_config: Dict) -> Dict:
        """Standardize data for bar charts."""
        result = {
            "type": "bar_chart",
            "title": viz_config.get("title", ""),
            "x_title": viz_config.get("x_axis_title", "Category"),
            "y_title": viz_config.get("y_axis_title", "Value"),
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