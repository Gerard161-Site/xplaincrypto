import logging
import os
from typing import Dict, Any, Optional, List, Tuple

from ..utils.cache_utils import CacheManager
from ..utils.style_utils import StyleManager
from .candlestick_chart_visualizer import CandlestickChartVisualizer
from .chain_distribution_visualizer import ChainDistributionVisualizer
from .pie_chart_visualizer import PieChartVisualizer
from .table_visualizer import TableVisualizer
from .line_chart_visualizer import LineChartVisualizer

class VisualizationAPI:
    """API for creating visualizations for cryptocurrency research reports."""
    
    def __init__(self, project_name: str, cache_manager: Optional[CacheManager] = None, 
                 style_manager: Optional[StyleManager] = None, theme: str = 'light'):
        """
        Initialize the visualization API.
        """
        self.project_name = project_name
        self.cache_manager = cache_manager or CacheManager(project_name=project_name)
        self.style_manager = style_manager or StyleManager()
        self.theme = theme
        self.logger = logging.getLogger(__name__)
        
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.visualizers = self._initialize_visualizers()
        
        self.used_real_data_sources = set()
        
        self.logger.info(f"Initialized VisualizationAPI for project: {project_name}")
    
    def _initialize_visualizers(self) -> Dict[str, Any]:
        """
        Initialize the visualization classes.
        """
        visualizers = {}
        
        try:
            visualizers["candlestick_chart"] = CandlestickChartVisualizer(
                theme=self.theme,
                project_name=self.project_name,
                style_manager=self.style_manager,
                logger=self.logger
            )
            
            visualizers["chain_distribution_chart"] = ChainDistributionVisualizer(
                theme=self.theme,
                project_name=self.project_name,
                style_manager=self.style_manager,
                logger=self.logger
            )
            
            visualizers["tokenomics_pie_chart"] = PieChartVisualizer(
                theme=self.theme,
                project_name=self.project_name,
                style_manager=self.style_manager,
                logger=self.logger
            )
            visualizers["pie_chart"] = visualizers["tokenomics_pie_chart"]
            
            table_visualizer = TableVisualizer(
                theme=self.theme,
                project_name=self.project_name,
                style_manager=self.style_manager,
                logger=self.logger
            )
            visualizers["key_metrics_table"] = table_visualizer
            visualizers["adoption_metrics_table"] = table_visualizer
            visualizers["table"] = table_visualizer
            
            line_chart_visualizer = LineChartVisualizer(
                theme=self.theme,
                project_name=self.project_name,
                style_manager=self.style_manager,
                logger=self.logger
            )
            visualizers["volume_chart"] = line_chart_visualizer
            visualizers["liquidity_trends_chart"] = line_chart_visualizer
            visualizers["tvl_milestone_chart"] = line_chart_visualizer
            visualizers["tvl_phases_chart"] = line_chart_visualizer
            visualizers["monthly_growth_chart"] = line_chart_visualizer
            visualizers["competitor_comparison_chart"] = line_chart_visualizer
            visualizers["line_chart"] = line_chart_visualizer
            
        except Exception as e:
            self.logger.error(f"Error initializing visualizers: {e}")
        
        return visualizers
    
    def _load_data_for_visualization(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load data for a visualization from cache.
        """
        if not self.cache_manager:
            self.logger.error("No cache manager available for loading data")
            return {"data_unavailable": True, "message": "No cache manager available"}
        
        data = {}
        
        vis_type = config.get('type', '')
        data_source = config.get('data_source', '')
        data_field = config.get('data_field', '')
        
        if not data_source or not data_field:
            self.logger.error(f"Missing data_source or data_field for {vis_type}")
            return {"data_unavailable": True, "message": "Missing data_source or data_field"}
        
        try:
            cache_keys = [
                f"{data_source}_data_{self.project_name.lower()}",
                f"{data_source}_{data_field}_{self.project_name.lower()}",
                f"{data_source}_{data_field}"
            ]
            
            for cache_key in cache_keys:
                try:
                    source_data = self.cache_manager.load(data_source, cache_key, self.project_name.lower())
                    if source_data:
                        data[data_source] = source_data
                        self.logger.info(f"Loaded data from cache: {self.cache_manager.cache_dir}/{data_source}/{cache_key}.json")
                        return data
                except Exception as e:
                    self.logger.debug(f"Error loading {data_source}/{cache_key} from cache: {str(e)}")
            
            self.logger.warning(f"No data found in cache for {data_source}/{data_field}")
            data[data_source] = {"data_unavailable": True, "message": f"No data available in cache for {data_source}/{data_field}"}
        
        except Exception as e:
            self.logger.error(f"Error loading data for {vis_type}: {str(e)}")
            data[data_source] = {"data_unavailable": True, "message": str(e)}
        
        return data
    
    def create_visualization(self, vis_type: str, config: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a visualization.
        """
        try:
            self.logger.info(f"Creating visualization: {vis_type}")
            
            if vis_type not in self.visualizers:
                error_msg = f"Visualization type not supported: {vis_type}"
                self.logger.error(error_msg)
                return False, "", error_msg
            
            visualizer = self.visualizers[vis_type]
            
            data = self._load_data_for_visualization(config)
            
            data_source = config.get('data_source', '')
            
            if data.get(data_source, {}).get("data_unavailable", False) and vis_type not in ['key_metrics_table', 'adoption_metrics_table']:
                error_msg = f"No data available for {vis_type}: {data.get(data_source, {}).get('message', 'Unknown error')}"
                self.logger.warning(error_msg)
                return False, "", error_msg
            
            has_real_data = False
            if vis_type in ['key_metrics_table', 'adoption_metrics_table'] and data:
                if len(data) > 0 and not set(data.keys()).issubset(['error', 'available_tools', 'data_unavailable']):
                    has_real_data = True
            elif vis_type == 'tokenomics_pie_chart' and 'tokenomics' in data:
                has_real_data = not data['tokenomics'].get("data_unavailable", False)
            elif vis_type == 'chain_distribution_chart' and 'defillama' in data:
                if isinstance(data['defillama'], dict) and 'error' in data['defillama'] and len(data['defillama'].keys()) == 1:
                    error_msg = f"No valid chain distribution data found: {data['defillama']['error']}"
                    self.logger.warning(error_msg)
                    return False, "", error_msg
                if isinstance(data['defillama'], dict) and 'chains' in data['defillama'] and data['defillama']['chains']:
                    has_real_data = True
            elif vis_type == 'candlestick_chart':
                has_real_data = 'ohlcv' in data and not data['ohlcv'].get("data_unavailable", False)
            elif vis_type in ['tvl_milestone_chart', 'tvl_phases_chart', 'liquidity_trends_chart', 'monthly_growth_chart', 'volume_chart']:
                if data.get('tvl') or data.get('volume'):
                    has_real_data = not (data.get('tvl', {}).get("data_unavailable", False) or data.get('volume', {}).get("data_unavailable", False))
                elif 'defillama' in data and isinstance(data['defillama'], dict) and 'tvl_history' in data['defillama']:
                    tvl_history = data['defillama']['tvl_history']
                    if isinstance(tvl_history, list) and len(tvl_history) > 0:
                        has_real_data = True
            
            result = visualizer.create(vis_type, config, data)
            
            if hasattr(visualizer, 'using_real_data') and visualizer.using_real_data:
                self.used_real_data_sources.add(vis_type)
            elif has_real_data:
                self.used_real_data_sources.add(vis_type)
            
            if not result:
                return False, "", "Visualization creation failed (empty result)"
                
            if isinstance(result, str):
                return True, result, ""
                
            if isinstance(result, dict):
                if "error" in result:
                    return False, "", result["error"]
                    
                file_path = result.get("file_path", "")
                if file_path and os.path.exists(file_path):
                    return True, file_path, ""
                else:
                    return False, "", "Visualization file not created"
            
            return False, "", f"Unexpected result type: {type(result)}"
            
        except Exception as e:
            error_msg = f"Error creating visualization {vis_type}: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg

    def get_available_visualizations(self) -> List[str]:
        """
        Get a list of available visualization types.
        """
        return list(self.visualizers.keys())

    def get_data_sources(self, token_name: str = None) -> Dict[str, List[str]]:
        """
        Get available data sources from cache.
        """
        sources = {}
        
        source_dirs = {
            'coingecko': os.path.join('docs', self.project_name, 'cache', 'coingecko'),
            'coinmarketcap': os.path.join('docs', self.project_name, 'cache', 'coinmarketcap'),
            'defillama': os.path.join('docs', self.project_name, 'cache', 'defillama'),
            'tokenomics': os.path.join('docs', self.project_name, 'cache', 'tokenomics'),
            'tavily': os.path.join('docs', self.project_name, 'cache', 'tavily')
        }
        
        for source_type, directory in source_dirs.items():
            if os.path.exists(directory):
                files = [f for f in os.listdir(directory) if f.endswith('.json')]
                if token_name:
                    files = [f for f in files if token_name.lower() in f.lower()]
                sources[source_type] = files
            else:
                sources[source_type] = []
        
        return sources