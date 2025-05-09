import os
import logging
import json
import time
import asyncio
import math
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
import sys

# Import the visualization components
from backend.visualizations import VisualizationFactory
from backend.visualizations.base_visualizer import BaseVisualizer

# Import managers for state, cache, and styling
try:
    from backend.utils.cache_utils import CacheManager
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import CacheManager: {str(e)}")
    raise

try:
    from backend.utils.style_utils import StyleManager
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import StyleManager: {str(e)}")
    raise

try:
    from backend.utils.state_manager import StateManager
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import StateManager: {str(e)}")
    raise

# Configure logger
logger = logging.getLogger(__name__)
for handler in logger.handlers:
    handler.flush = sys.stdout.flush
logger.info("Visualizer logger configured with immediate flush")

class Visualizer:
    """
    Visualizer that generates high-quality visualizations using Plotly and Dash.
    Uses StateManager for consistent state access and creates PDF-ready PNG exports.
    """
    
    def __init__(self, project_name: str, logger: Optional[logging.Logger] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the visualizer.
        
        Args:
            project_name: Name of the project
            logger: Optional logger instance
            config: Optional configuration dictionary
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Visualizer constructor started")
        
        # Handle project name from different formats
        if isinstance(project_name, dict) and 'project_name' in project_name:
            project_name = project_name['project_name']
            
        self.project_name = project_name
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize supporting managers
        self.state_manager = StateManager(logger=self.logger)
        self.cache_manager = CacheManager(project_name=project_name, logger=self.logger)
        self.style_manager = StyleManager(logger=self.logger)
        
        # Create visualization factory
        self.viz_factory = VisualizationFactory(
            project_name=project_name,
            style_manager=self.style_manager,
            logger=self.logger
        )
        
        # State tracking
        self.cache_dir = os.path.join(self.output_dir, "cache")
        self.visualizations = {}
        self.visualization_list = []
        self.errors = {}
        self.data_sources_used = {}
        self.theme = 'light'  # Default theme
        self.pdf_optimized = True  # Default to PDF-optimized output
        self.config = config or {}
        self.report_config = {}
        
        # Load data mappings
        self.data_mappings = self._load_data_mappings()
        
        self.logger.info(f"Initialized Visualizer for project: {project_name}")
        self.logger.info("Visualizer constructor completed")

    def _load_data_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Load data mappings from map_data.md file or return default mappings.
        
        Returns:
            Dictionary mapping chart types to data sources and cache paths
        """
        mappings = {
            "tvl_chart": {
                "visualizer": "line_chart",
                "data_source": "defillama",
                "research_state_key": "data.defillama.tvl_history",
                "expected_structure": "List of [timestamp, tvl] or [{'date': timestamp, 'tvl': value}]",
                "fallback_cache_path": f"docs/{self.project_name.lower()}/cache/defillama/tvl_{self.project_name.lower()}.json",
                "max_data_age": 24
            },
            "price_chart": {
                "visualizer": "candlestick_chart",
                "data_source": "coinmarketcap",
                "research_state_key": "data.coinmarketcap.ohlcv",
                "expected_structure": "List of [{'date': timestamp, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': float}]",
                "fallback_cache_path": f"docs/{self.project_name.lower()}/cache/coinmarketcap/ohlcv_{self.project_name.lower()}_30.json",
                "max_data_age": 1
            },
            "volume_chart": {
                "visualizer": "line_chart",
                "data_source": "coinmarketcap",
                "research_state_key": "data.coinmarketcap.volume_history",
                "expected_structure": "List of [{'date': timestamp, 'volume': float}]",
                "fallback_cache_path": f"docs/{self.project_name.lower()}/cache/coinmarketcap/historical_{self.project_name.lower()}_days_30.json",
                "max_data_age": 4
            },
            "tokenomics_chart": {
                "visualizer": "pie_chart",
                "data_source": "tokenomics",
                "research_state_key": "data.tokenomics.token_distribution",
                "expected_structure": "Nested object with token_allocation field containing Dict of {category: percentage}",
                "fallback_cache_path": f"docs/{self.project_name.lower()}/cache/tokenomics/distribution_{self.project_name.lower()}.json",
                "max_data_age": 168
            },
            "chain_distribution_chart": {
                "visualizer": "pie_chart",
                "data_source": "defillama",
                "research_state_key": "data.defillama.currentChainTvls",
                "expected_structure": "Dict of {chain: tvl} or [{\"chain\": str, \"tvl\": float}]",
                "fallback_cache_path": f"docs/{self.project_name.lower()}/cache/defillama/protocol_protocol_{self.project_name.lower()}.json",
                "max_data_age": 24
            },
            "comparison_chart": {
                "visualizer": "comparison_chart",
                "data_source": "multi",
                "research_state_key": "data.competitors",
                "expected_structure": "Dict of {project: {metric1: value1, metric2: value2}}",
                "fallback_cache_path": "",
                "max_data_age": 24
            },
            "metrics_table": {
                "visualizer": "table",
                "data_source": "multi",
                "research_state_key": "data.metrics_table",
                "expected_structure": "DataFrame or list of dicts",
                "fallback_cache_path": "",
                "max_data_age": 12
            }
        }
        
        # Try to read from map_data.md if it exists
        try:
            map_data_path = os.path.join(os.getcwd(), "map_data.md")
            if os.path.exists(map_data_path):
                self.logger.info(f"Reading data mappings from {map_data_path}")
                with open(map_data_path, 'r') as f:
                    content = f.read()
                    
                # Parse the markdown table (basic implementation)
                # Could be improved with a proper markdown parser
                table_lines = []
                in_table = False
                for line in content.split('\n'):
                    if line.startswith('|'):
                        if not in_table and '---' not in line:
                            in_table = True
                        if in_table and '---' not in line:
                            table_lines.append(line)
                
                # Skip header row
                if len(table_lines) > 1:
                    for line in table_lines[1:]:
                        cells = [cell.strip() for cell in line.split('|')[1:-1]]
                        if len(cells) >= 6:
                            chart_type = cells[0].lower().replace(' ', '_')
                            visualizer = cells[1].lower()
                            data_source = cells[2].lower()
                            research_state_key = cells[3]
                            expected_structure = cells[4]
                            fallback_cache_path = cells[5]
                            max_data_age = cells[6] if len(cells) > 6 else "24h"
                            
                            # Extract hours from max_data_age 
                            try:
                                if max_data_age.endswith('h'):
                                    max_data_age = int(max_data_age[:-1])
                                else:
                                    max_data_age = 24  # Default to 24h
                            except (ValueError, TypeError):
                                max_data_age = 24
                                
                            mappings[chart_type] = {
                                "visualizer": visualizer,
                                "data_source": data_source,
                                "research_state_key": research_state_key,
                                "expected_structure": expected_structure,
                                "fallback_cache_path": fallback_cache_path,
                                "max_data_age": max_data_age
                            }
                
                self.logger.info(f"Loaded {len(mappings)} data mappings from map_data.md")
        except Exception as e:
            self.logger.warning(f"Error loading data mappings from map_data.md: {str(e)}. Using default mappings.")
            
        return mappings

    def _map_data_to_visualization(self, viz_type: str, viz_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map data according to the data mappings defined in map_data.md.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            state: State dictionary
            
        Returns:
            Mapped data for the visualization
        """
        self.logger.info(f"Mapping data for visualization type: {viz_type}")
        
        # Normalize viz_type to match mappings
        viz_type_key = viz_type.lower().replace(' ', '_')
        
        # Check for mapping
        if viz_type_key not in self.data_mappings:
            self.logger.warning(f"No data mapping found for visualization type: {viz_type_key}")
            # Fall back to original data source specified in viz_config
            return None
            
        mapping = self.data_mappings[viz_type_key]
        data_source = mapping["data_source"]
        research_state_key = mapping["research_state_key"]
        fallback_cache_path = mapping["fallback_cache_path"]
        
        # If original config has data_source, use that instead
        if "data_source" in viz_config and viz_config["data_source"]:
            # Keep the original data_source for compatibility
            return None
            
        # Look for data in ResearchState using the mapping's key
        try:
            # Parse the key parts
            key_parts = research_state_key.split('.')
            if len(key_parts) >= 2:
                # Typically 'data.{source}.{field}'
                current_data = state
                for part in key_parts:
                    if part in current_data:
                        current_data = current_data[part]
                    else:
                        self.logger.info(f"Key part '{part}' not found in state path: {research_state_key}")
                        current_data = None
                        break
                
                if current_data is not None:
                    self.logger.info(f"Found data in state using path: {research_state_key}")
                    # Format the data for the visualizer
                    result = {data_source: {key_parts[-1]: current_data}}
                    return result
            else:
                self.logger.warning(f"Invalid research_state_key format: {research_state_key}")
                
        except Exception as e:
            self.logger.warning(f"Error accessing state data using path {research_state_key}: {str(e)}")
            
        # Fall back to cache if data not found in state
        if fallback_cache_path and os.path.exists(fallback_cache_path):
            try:
                self.logger.info(f"Loading data from cache: {fallback_cache_path}")
                with open(fallback_cache_path, 'r') as f:
                    cache_data = json.load(f)
                    
                # Check cache data age if available
                if "metadata" in cache_data and "cached_at" in cache_data["metadata"]:
                    cached_at = cache_data["metadata"]["cached_at"]
                    # Parse ISO format timestamp
                    try:
                        from datetime import datetime, timedelta
                        cached_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
                        max_age_hours = mapping["max_data_age"]
                        max_age = timedelta(hours=max_age_hours)
                        
                        if datetime.now() - cached_time > max_age:
                            self.logger.warning(f"Cache data is older than {max_age_hours} hours")
                    except Exception as e:
                        self.logger.warning(f"Error checking cache age: {str(e)}")
                
                # Extract the actual data
                if "data" in cache_data:
                    cache_data = cache_data["data"]
                    
                # Format the cache data for the visualizer
                result = {data_source: cache_data}
                return result
                
            except Exception as e:
                self.logger.error(f"Error loading cache from {fallback_cache_path}: {str(e)}")
                
        # If no data found, return None to fall back to original logic
        return None

    def _safe_get_dict(self, data: Any, key: str = None, default: Any = None) -> Dict[str, Any]:
        if data is None:
            return {} if default is None else default
        if isinstance(data, dict):
            if key is not None:
                return data.get(key, default if default is None else {})
            return data
        if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
            try:
                result = data.to_dict()
                if isinstance(result, dict):
                    if key is not None:
                        return result.get(key, default if default is None else {})
                    return result
            except Exception as e:
                self.logger.warning(f"Error converting object to dict via to_dict(): {str(e)}")
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    if key is not None:
                        return parsed.get(key, default if default is None else {})
                    return parsed
            except Exception as e:
                self.logger.warning(f"Error parsing JSON string: {str(e)}")
            return {"content": data, "error": "Data was string, not dict"}
        if hasattr(data, "__dict__"):
            try:
                data_dict = data.__dict__
                if key is not None:
                    return data_dict.get(key, default if default is None else {})
                return data_dict
            except Exception as e:
                self.logger.warning(f"Error accessing __dict__: {str(e)}")
        self.logger.warning(f"Unexpected data type: {type(data).__name__}, cannot convert to dict")
        return {} if default is None else default
    
    def _get_data_from_state(self, state: Dict[str, Any], data_source: str, data_field: str) -> Dict[str, Any]:
        """Use StateManager to get data from state."""
        result = {}
        if state is None:
            self.logger.warning("State is None in _get_data_from_state")
            return result
        
        try:
            # Try direct data access from the state data structure
            if isinstance(state, dict):
                # First check if we have a direct data entry with the source
                if "data" in state and isinstance(state["data"], dict):
                    if data_source in state["data"]:
                        self.logger.info(f"Found direct data for {data_source} in state.data")
                        result[data_source] = state["data"][data_source]
                        return result
                        
                    # Check if we have data in a section of state.data
                    for section_name, section_data in state["data"].items():
                        if isinstance(section_data, dict) and data_source in section_data:
                            self.logger.info(f"Found {data_source} data in state.data.{section_name}")
                            result[data_source] = section_data[data_source]
                            return result
                
                # Check for Executive Summary section which often contains data
                if "Executive Summary" in state and isinstance(state["Executive Summary"], dict):
                    if data_source in state["Executive Summary"]:
                        self.logger.info(f"Found {data_source} data in Executive Summary section")
                        result[data_source] = state["Executive Summary"][data_source]
                        return result
                
                # Check for the specific section name that might match the data source
                normalized_section = data_source.lower().replace(" ", "_")
                if normalized_section in state and isinstance(state[normalized_section], dict):
                    self.logger.info(f"Found data in section {normalized_section}")
                    result[data_source] = state[normalized_section]
                    return result
                    
            # Get section data using StateManager
            for section_title in self.state_manager.get_section_titles(state):
                section_data = self.state_manager.get_section_data(state, section_title)
                if section_data and data_source in section_data:
                    source_data = section_data[data_source]
                    if data_field and data_field in source_data:
                        self.logger.info(f"Found data in section {section_title} for {data_source}.{data_field}")
                        result[data_source] = source_data
                        return result
                    self.logger.info(f"Found data for {data_source} in section {section_title}")
                    result[data_source] = source_data
                    return result
                    
            # Try visualization data if not found in section data
            for section_title in self.state_manager.get_section_titles(state):
                try:
                    visualization_data = self.state_manager.get_visualization_data_for_section(state, section_title)
                    if visualization_data and data_source in visualization_data:
                        source_data = visualization_data[data_source]
                        if data_field and data_field in source_data:
                            self.logger.info(f"Found data in visualization_data for {section_title}/{data_source}.{data_field}")
                            result[data_source] = source_data
                            return result
                        self.logger.info(f"Found data for {data_source} in visualization_data for section {section_title}")
                        result[data_source] = source_data
                        return result
                except Exception as e:
                    self.logger.warning(f"Error accessing visualization data for section {section_title}: {str(e)}")
                
            # Try general data if not found in sections or visualization data
            data_sources = self.state_manager.get_data_sources(state)
            if data_sources and data_source in data_sources:
                source_data = data_sources[data_source]
                if data_field and data_field in source_data:
                    self.logger.info(f"Found data in state.data for {data_source}.{data_field}")
                    result[data_source] = source_data
                    return result
                self.logger.info(f"Found data for {data_source} in state.data")
                result[data_source] = source_data
                return result
                
        except Exception as e:
            self.logger.error(f"Error accessing state data for {data_source}/{data_field}: {str(e)}")
            
        self.logger.info(f"No data found in state for {data_source}/{data_field}")
        return result

    def _load_data_from_cache(self, data_source: str, data_field: str) -> Dict[str, Any]:
        """Load data from cache and format it correctly for visualizations."""
        if data_source == "multi":
            combined_data = {}
            sources = ["coinmarketcap", "defillama", "tokenomics", "coingecko"]
            for source in sources:
                source_data = self._load_data_from_cache(source, data_field)
                if source_data and source in source_data:
                    combined_data[source] = source_data[source]
            return combined_data if combined_data else {"data_unavailable": True, "message": "No data available in cache for multi-source"}
        
        cache_keys = [
            f"{data_source}_data_{self.project_name.lower()}",
            f"{data_source}_{data_field}_{self.project_name.lower()}",
            f"{data_source}_{data_field}",
            f"data_{data_field}_{self.project_name.lower()}"
        ]
        
        for cache_key in cache_keys:
            try:
                cache_data = self.cache_manager.load(data_source, cache_key, self.project_name.lower())
                if cache_data:
                    self.logger.info(f"Loaded data from cache: {data_source}/{cache_key}")
                    
                    # Special handling for OHLCV data
                    if data_field == "ohlcv" and data_source in ["coinmarketcap", "coingecko"]:
                        self.logger.info(f"Found cached OHLCV data for {data_source}, formatting for visualization")
                        
                        # Check if the data is already structured correctly
                        if "ohlcv" in cache_data:
                            self.logger.info(f"OHLCV data is already in expected format")
                            return {data_source: {"ohlcv": cache_data["ohlcv"]}}
                        
                        # Check if the data has a nested 'data' structure (common in our cache)
                        if "data" in cache_data and "ohlcv" in cache_data["data"]:
                            self.logger.info(f"OHLCV data found in nested data.ohlcv structure")
                            return {data_source: {"ohlcv": cache_data["data"]["ohlcv"]}}
                    
                    return {data_source: cache_data}
            except Exception as e:
                self.logger.debug(f"Error loading {data_source}/{cache_key} from cache: {str(e)}")
        
        self.logger.info(f"No cache found for {data_source}/{data_field}")
        return {"data_unavailable": True, "message": f"No data available in cache for {data_source}/{data_field}"}
    
    def _load_data_from_huggingface(self, data_source: str, data_field: str) -> Dict[str, Any]:
        self.logger.warning(f"HuggingFace fallback is disabled for {data_source}/{data_field}")
        return {"data_unavailable": True, "source": "huggingface", "message": "HuggingFace fallback is disabled to maintain data integrity"}

    def _add_error(self, viz_id: str, error: str):
        self.errors[viz_id] = error
        self.logger.error(f"Error creating visualization {viz_id}: {error}")

    def _get_data_for_visualization(self, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any], section_title: str = "Unknown") -> Dict[str, Any]:
        """Get data for visualization using StateManager."""
        data_source = viz_config.get("data_source", "")
        data_field = viz_config.get("data_field", "")
        
        # Try to use data mapping first
        viz_type = viz_config.get("type", "")
        mapped_data = self._map_data_to_visualization(viz_type, viz_config, state)
        if mapped_data:
            self.logger.info(f"Using mapped data for visualization {viz_id} of type {viz_type}")
            self.data_sources_used[f"{section_title}_{viz_id}"] = "mapped"
            return mapped_data
        
        # DIRECT DATA ACCESS: First check if we have data directly in the state structure
        # This is critical for accessing data populated by the researcher agent
        if "data" in state and isinstance(state["data"], dict):
            self.logger.info(f"DIRECT DATA ACCESS: Checking state.data for {data_source}/{data_field}")
            
            # Check in market_analysis section first (most common location)
            if "market_analysis" in state["data"] and isinstance(state["data"]["market_analysis"], dict):
                market_data = state["data"]["market_analysis"]
                if data_source in market_data and isinstance(market_data[data_source], dict):
                    source_data = market_data[data_source]
                    self.logger.info(f"DIRECT DATA ACCESS: Found {data_source} in market_analysis section")
                    
                    # If data_field is specified, check if it exists in the source data
                    if data_field and data_field in source_data:
                        self.logger.info(f"DIRECT DATA ACCESS: Found {data_field} in {data_source} data")
                        return {data_source: {data_field: source_data[data_field]}}
                    
                    # Return the entire source data if no specific field is requested or field not found
                    self.logger.info(f"DIRECT DATA ACCESS: Returning all {data_source} data from market_analysis")
                    return {data_source: source_data}
            
            # Check in executive_summary section (another common location)
            if "executive_summary" in state["data"] and isinstance(state["data"]["executive_summary"], dict):
                summary_data = state["data"]["executive_summary"]
                if data_source in summary_data and isinstance(summary_data[data_source], dict):
                    source_data = summary_data[data_source]
                    self.logger.info(f"DIRECT DATA ACCESS: Found {data_source} in executive_summary section")
                    
                    # If data_field is specified, check if it exists in the source data
                    if data_field and data_field in source_data:
                        self.logger.info(f"DIRECT DATA ACCESS: Found {data_field} in {data_source} data")
                        return {data_source: {data_field: source_data[data_field]}}
                    
                    # Return the entire source data if no specific field is requested or field not found
                    self.logger.info(f"DIRECT DATA ACCESS: Returning all {data_source} data from executive_summary")
                    return {data_source: source_data}
            
            # Check in the specific section that matches the visualization section
            normalized_section = section_title.lower().replace(" ", "_")
            if normalized_section in state["data"] and isinstance(state["data"][normalized_section], dict):
                section_data = state["data"][normalized_section]
                if data_source in section_data and isinstance(section_data[data_source], dict):
                    source_data = section_data[data_source]
                    self.logger.info(f"DIRECT DATA ACCESS: Found {data_source} in {normalized_section} section")
                    
                    # If data_field is specified, check if it exists in the source data
                    if data_field and data_field in source_data:
                        self.logger.info(f"DIRECT DATA ACCESS: Found {data_field} in {data_source} data")
                        return {data_source: {data_field: source_data[data_field]}}
                    
                    # Return the entire source data if no specific field is requested or field not found
                    self.logger.info(f"DIRECT DATA ACCESS: Returning all {data_source} data from {normalized_section}")
                    return {data_source: source_data}
                    
            # Check all sections if not found in the common locations
            self.logger.info(f"DIRECT DATA ACCESS: Searching all sections for {data_source}/{data_field}")
            for section_name, section_data in state["data"].items():
                if not isinstance(section_data, dict):
                    continue
                    
                if data_source in section_data and isinstance(section_data[data_source], dict):
                    source_data = section_data[data_source]
                    self.logger.info(f"DIRECT DATA ACCESS: Found {data_source} in {section_name} section")
                    
                    # If data_field is specified, check if it exists in the source data
                    if data_field and data_field in source_data:
                        self.logger.info(f"DIRECT DATA ACCESS: Found {data_field} in {data_source} data")
                        return {data_source: {data_field: source_data[data_field]}}
                    
                    # Return the entire source data if no specific field is requested or field not found
                    self.logger.info(f"DIRECT DATA ACCESS: Returning all {data_source} data from {section_name}")
                    return {data_source: source_data}
        
        # If no data found in direct state access, fall back to the original method
        # First try to get standardized data for this visualization
        normalized_section = section_title.lower().replace(" ", "_")
        
        # Try to get standardized data from visualization_data
        visualization_data = self.state_manager.get_visualization_data_for_section(state, normalized_section)
        if visualization_data and viz_id in visualization_data:
            self.logger.info(f"Found standardized data for visualization {viz_id} in section {section_title}")
            self.data_sources_used[f"{section_title}_{viz_id}"] = "standardized"
            return visualization_data[viz_id]
        
        # If no standardized data found, fall back to original data extraction logic
        if not data_source:
            self.logger.error(f"No data_source specified for visualization {viz_id}")
            return {"data_unavailable": True, "message": "No data source specified"}
            
        # Get data using StateManager
        data = self._get_data_from_state(state, data_source, data_field)
        if data and data_source in data:
            self.logger.info(f"Found data for {data_source} using StateManager")
            self.data_sources_used[f"{section_title}_{viz_id}"] = "state_manager"
            return data
        
        # If still no data found, try cache as last resort
        self.logger.info(f"No data found in state for {data_source}/{data_field}, trying cache")
        data = self._load_data_from_cache(data_source, data_field)
        if data and not data.get("data_unavailable", False):
            self.logger.info(f"Found data for {data_source} in cache")
            self.data_sources_used[f"{section_title}_{viz_id}"] = "cache"
            return data
        
        # If still no data found, log error and return empty data
        self.logger.error(f"No data found for {data_source}/{data_field} in state or cache")
        return {"data_unavailable": True, "message": f"No data available for {data_source}/{data_field}"}

    def _create_visualization(self, section_title: str, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """
        Create a visualization.
        
        Args:
            section_title: Section title
            viz_id: Visualization identifier
            viz_config: Visualization configuration
            state: State dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Creating visualization {viz_id} for section {section_title}")
            
            # Get data for visualization
            viz_data = self._get_data_for_visualization(viz_id, viz_config, state, section_title)
            
            # Get visualization type from config
            vis_type = viz_config.get("type", "")
            
            # Prepare configuration for the visualization factory
            config = {
                "title": viz_config.get("title", f"{self.project_name} {viz_id.replace('_', ' ').title()}"),
                "description": viz_config.get("description", f"Visualization for {section_title}: {viz_id}"),
                "output_filename": f"{section_title.lower().replace(' ', '_')}_{viz_id}",
                "data_source": viz_config.get("data_source", ""),
                "data_field": viz_config.get("data_field", ""),
                "source": viz_config.get("source", "Various Sources")
            }
            
            # Create the visualization using the factory
            result, file_path, error_msg = self.viz_factory.create(vis_type, config, viz_data)
            
            if result and file_path:
                self.logger.info(f"Visualization created successfully: {file_path}")
                
                # Record the visualization
                viz_item = {
                    "id": viz_id,
                    "section": section_title,
                    "path": file_path,
                    "type": viz_config.get("type", "unknown"),
                    "title": viz_config.get("title", viz_id.replace("_", " ").title())
                }
                
                # Store in visualizations dict and list
                viz_key = f"{section_title}_{viz_id}"
                self.visualizations[viz_key] = file_path
                self.visualization_list.append(viz_item)
                
                return True
            else:
                # Record the error
                viz_key = f"{section_title}_{viz_id}"
                self._add_error(viz_key, error_msg or "Unknown visualization error")
                self.logger.error(f"Visualization failed: {error_msg}")
                return False
                
        except Exception as e:
            # Record the error
            viz_key = f"{section_title}_{viz_id}"
            self._add_error(viz_key, str(e))
            self.logger.error(f"Error creating visualization {viz_id}: {str(e)}")
            return False

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the visualizer."""
        if not isinstance(state, dict) and hasattr(state, 'to_dict'):
            state_dict = state.to_dict()
            return asyncio.run(self.run_with_state_async(state, state_dict))
        else:
            return asyncio.run(self.run_with_state_async(state, state))
    
    def run_with_state(self, original_state: Any, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.run_with_state_async(original_state, state_dict))

    async def _create_visualization_async(self, section_title: str, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Create a visualization asynchronously.
        
        Args:
            section_title: Title of the section
            viz_id: ID of the visualization
            viz_config: Configuration for the visualization
            state: State dictionary
            
        Returns:
            Tuple of (viz_id, success)
        """
        try:
            # Get visualization type
            viz_type = viz_config.get("type", "unknown")
            self.logger.info(f"Creating visualization {viz_id} of type {viz_type} for section {section_title}")
            
            # Get data for visualization - this is the critical part that accesses researcher data
            data = self._get_data_for_visualization(viz_id, viz_config, state, section_title)
            
            # Log data availability
            if not data:
                self.logger.error(f"No data available for visualization {viz_id}")
                self.errors[viz_id] = "No data available"
                return viz_id, False
            
            if "data_unavailable" in data and data["data_unavailable"]:
                error_msg = data.get("message", "Data unavailable")
                self.logger.error(f"Data unavailable for visualization {viz_id}: {error_msg}")
                self.errors[viz_id] = error_msg
                return viz_id, False
                
            # Create visualization using factory
            self.logger.info(f"Creating {viz_type} visualization with data keys: {list(data.keys())}")
            
            # For debugging, check specific data content
            data_source = viz_config.get("data_source", "")
            data_field = viz_config.get("data_field", "")
            if data_source in data:
                source_data = data[data_source]
                if isinstance(source_data, dict) and data_field in source_data:
                    field_data = source_data[data_field]
                    if isinstance(field_data, list):
                        self.logger.info(f"Data for {data_source}.{data_field} is a list with {len(field_data)} items")
                    elif isinstance(field_data, dict):
                        self.logger.info(f"Data for {data_source}.{data_field} is a dict with keys: {list(field_data.keys())}")
                    else:
                        self.logger.info(f"Data for {data_source}.{data_field} is of type: {type(field_data)}")
                else:
                    self.logger.info(f"Data for {data_source} is available but {data_field} field not found or not a dict")
            
            # Create the visualization
            success, viz_path, message = self.viz_factory.create_visualization(
                viz_type=viz_type,
                viz_config=viz_config,
                data=data
            )
            
            if success and viz_path:
                # Store visualization path
                viz_key = f"{section_title}_{viz_id}"
                self.visualizations[viz_key] = viz_path
                
                # Add to visualization list
                viz_title = viz_config.get("title", viz_id.replace("_", " ").title())
                self.visualization_list.append({
                    "id": viz_id,
                    "section": section_title,
                    "path": viz_path,
                    "type": viz_type,
                    "title": viz_title
                })
                
                self.logger.info(f"Successfully created visualization {viz_id} at {viz_path}")
                return viz_id, True
            else:
                self.logger.error(f"Failed to create visualization {viz_id}: {message}")
                self.errors[viz_id] = message
                return viz_id, False
                
        except Exception as e:
            self.logger.error(f"Error creating visualization {viz_id}: {str(e)}")
            self.errors[viz_id] = str(e)
            return viz_id, Exception(f"Error creating visualization {viz_id}: {str(e)}")

    async def run_with_state_async(self, original_state: Any, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the visualizer with state data asynchronously.
        
        Args:
            original_state: Original state object
            state_dict: State dictionary
            
        Returns:
            Updated state dictionary
        """
        self.logger.info(f"Starting asynchronous visualization generation for {self.project_name}")
        
        # Ensure we have a report_config
        report_config = self._safe_get_dict(state_dict.get("report_config", {}))
        if not report_config:
            self.logger.error("No report_config found in state")
            return state_dict
            
        # Get visualization types from report config
        visualization_types = self._safe_get_dict(report_config.get("visualization_types", {}))
        if not visualization_types:
            self.logger.error("No visualization_types found in report_config")
            
        # Get sections from report config
        sections = report_config.get("sections", [])
        if not sections:
            self.logger.error("No sections found in report_config")
            return state_dict
            
        # Prepare visualization tasks
        tasks = []
        for section in sections:
            section_title = section.get("title", "Unknown")
            visualizations = section.get("visualizations", [])
            
            if not visualizations:
                continue
                
            # Log data availability for this section
            self.logger.info(f"Processing section: {section_title}")
            if "data" in state_dict and isinstance(state_dict["data"], dict):
                normalized_section = section_title.lower().replace(" ", "_")
                if normalized_section in state_dict["data"]:
                    section_data = state_dict["data"][normalized_section]
                    self.logger.info(f"Data available for section {section_title}: {list(section_data.keys())}")
                else:
                    self.logger.info(f"No specific data found for section {section_title} in state.data")
                    
                # Check market_analysis and executive_summary for data
                for key_section in ["market_analysis", "executive_summary"]:
                    if key_section in state_dict["data"]:
                        self.logger.info(f"Data available in {key_section}: {list(state_dict['data'][key_section].keys())}")
            
            # Process each visualization in the section
            for viz in visualizations:
                # Handle both string-based viz IDs and dictionary-based viz configs
                if isinstance(viz, str):
                    viz_id = viz
                    # Look up the visualization config from visualization_types
                    viz_config = visualization_types.get(viz_id, {})
                else:
                    # It's a dictionary with configuration
                    viz_id = viz.get("id") or f"{section_title.lower().replace(' ', '_')}_{viz.get('type', 'unknown')}"
                    viz_config = viz
                
                # Create task for this visualization
                self.logger.info(f"Creating visualization task for {viz_id} in section {section_title}")
                tasks.append(self._create_visualization_async(section_title, viz_id, viz_config, state_dict))
                
        # Also process any direct visualization requests
        visualization_requests = state_dict.get("visualization_request", [])
        for viz_request in visualization_requests:
            if isinstance(viz_request, str):
                viz_id = viz_request
                viz_config = visualization_types.get(viz_id, {})
            else:
                section_title = viz_request.get("section", "General")
                viz_type = viz_request.get("type", "unknown")
                viz_id = viz_request.get("id") or f"{section_title.lower().replace(' ', '_')}_{viz_type}"
                viz_config = viz_request
            
            # Create task for this visualization request
            self.logger.info(f"Creating visualization task for request {viz_id} in section {section_title}")
            tasks.append(self._create_visualization_async(section_title, viz_id, viz_config, state_dict))
            
        # Run all visualization tasks in parallel
        self.logger.info(f"Running {len(tasks)} visualization tasks in parallel")
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for viz_id, success in results:
                if isinstance(success, Exception):
                    self.logger.error(f"Error creating visualization {viz_id}: {str(success)}")
                    self.errors[viz_id] = str(success)
                elif not success:
                    self.logger.warning(f"Failed to create visualization {viz_id}")
        else:
            self.logger.warning("No visualization tasks to run")
            
        # Update state with visualization results
        state_dict["visualizations"] = self.visualizations
        state_dict["visualization_list"] = self.visualization_list
        state_dict["visualization_data_sources"] = self.data_sources_used
        
        if self.errors:
            if "errors" not in state_dict:
                state_dict["errors"] = {}
            elif not isinstance(state_dict["errors"], dict):
                # Convert errors to dict if it's not already
                state_dict["errors"] = {"previous_errors": state_dict["errors"]}
            state_dict["errors"]["visualization"] = self.errors
            
        # Set visualizer output for workflow manager
        state_dict["visualizer_output"] = {
            "visualizations": self.visualizations,
            "visualization_list": self.visualization_list,
            "visualization_data_sources": self.data_sources_used,
            "errors": self.errors
        }
        
        self.logger.info(f"Completed asynchronous visualization generation with {len(self.visualization_list)} visualizations")
        return state_dict

# Aliases for backward compatibility
visualizer = Visualizer 

async def visualizer_async(state: Dict[str, Any], llm=None, logger: Optional[logging.Logger] = None, config=None) -> Dict[str, Any]:
    """
    Asynchronous version of the Visualizer. Takes a state object and returns it with visualizations added.
    """
    # Set up logging
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting visualizer_async")
    
    # Create visualizer with proper parameters
    visualizer = Visualizer(
        project_name=_get_project_name(state),
        logger=logger,
        config=config
    )
    
    # Convert state to dict if needed
    if hasattr(state, 'to_dict'):
        state_dict = state.to_dict()
    else:
        state_dict = state
        
    logger.info("Completed visualizer_async")
    return await visualizer.run_with_state_async(state, state_dict)

def visualizer_sync(state: Dict[str, Any], llm=None, logger: Optional[logging.Logger] = None, config=None) -> Dict[str, Any]:
    """
    Synchronous version of the Visualizer. Takes a state object and returns it with visualizations added.
    """
    # Set up logging
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting visualizer_sync")
    
    # Create visualizer with proper parameters
    visualizer = Visualizer(
        project_name=_get_project_name(state),
        logger=logger,
        config=config
    )
    
    # Convert state to dict if needed
    if hasattr(state, 'to_dict'):
        state_dict = state.to_dict()
    else:
        state_dict = state
    
    try:
        # Use asyncio.run for sync context
        result = asyncio.run(visualizer.run_with_state_async(state, state_dict))
        logger.info("Sync execution completed")
        return result
    except Exception as e:
        logger.error(f"Error in visualizer_sync: {str(e)}", exc_info=True)
        return state

def _get_project_name(state: Any) -> str:
    if state is None:
        return "unknown_project"
    if hasattr(state, "project_name") and state.project_name:
        return state.project_name
    if isinstance(state, dict):
        if "project_name" in state and state["project_name"]:
            return state["project_name"]
        if "context" in state and isinstance(state["context"], dict):
            context = state["context"]
            if "project_name" in context and context["project_name"]:
                return context["project_name"]
    return "unknown_project"