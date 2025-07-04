import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

import plotly.graph_objects as go
import matplotlib.pyplot as plt

from .base_visualizer import BaseVisualizer

class PieChartVisualizer(BaseVisualizer):
    """
    Visualizer for pie charts displaying distribution data.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the pie chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a pie chart visualization.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        try:
            # Determine the type of pie chart from viz_config
            chart_type = viz_type.lower()
            
            # Handle different distribution data formats
            distribution_data = None
            labels = []
            values = []
            
            # For tokenomics pie chart
            if "tokenomics" in chart_type or viz_config.get("data_source") == "tokenomics":
                if "tokenomics" in data and "token_distribution" in data["tokenomics"]:
                    distribution_data = data["tokenomics"]["token_distribution"]
                    
                    # Process distribution data (handle different formats)
                    if isinstance(distribution_data, list):
                        for item in distribution_data:
                            if isinstance(item, dict) and "name" in item and "value" in item:
                                labels.append(item["name"])
                                values.append(item["value"])
                
                # Alternative data format
                elif "tokenomics" in data and "distribution" in data["tokenomics"]:
                    distribution_data = data["tokenomics"]["distribution"]
                    
                    if isinstance(distribution_data, dict):
                        labels = list(distribution_data.keys())
                        values = list(distribution_data.values())
                    elif isinstance(distribution_data, list):
                        for item in distribution_data:
                            if isinstance(item, dict) and "name" in item and "value" in item:
                                labels.append(item["name"])
                                values.append(item["value"])
            
            # For chain distribution chart
            elif "chain" in chart_type:
                if "defillama" in data and "chains" in data["defillama"]:
                    chains_data = data["defillama"]
                    
                    # Get chains list
                    chains = chains_data.get("chains", [])
                    
                    # Try to find TVL values for each chain
                    if "chainTvls" in chains_data:
                        chain_tvls = chains_data["chainTvls"]
                        for chain in chains:
                            chain_tvl = chain_tvls.get(chain, 0)
                            # Handle nested TVL structure
                            if isinstance(chain_tvl, dict) and "tvl" in chain_tvl:
                                chain_tvl = chain_tvl["tvl"]
                            
                            labels.append(chain)
                            values.append(chain_tvl / 1000000)  # Convert to millions
                    
                    # Alternative format
                    elif "currentChainTvls" in chains_data:
                        chain_tvls = chains_data["currentChainTvls"]
                        for chain in chains:
                            labels.append(chain)
                            values.append(chain_tvls.get(chain, 0) / 1000000)  # Convert to millions
            
            # If we still have no data, try generic formats
            if not labels or not values:
                # Generic dictionary format
                for source, source_data in data.items():
                    if isinstance(source_data, dict) and "distribution" in source_data:
                        distribution = source_data["distribution"]
                        if isinstance(distribution, dict):
                            labels = list(distribution.keys())
                            values = list(distribution.values())
                            break
                        elif isinstance(distribution, list):
                            for item in distribution:
                                if isinstance(item, dict) and "name" in item and "value" in item:
                                    labels.append(item["name"])
                                    values.append(item["value"])
                            break
            
            # If we still have no usable data, return error
            if not labels or not values or len(labels) != len(values):
                return False, "", "No usable distribution data available for pie chart"
            
            # Create pie chart
            fig = go.Figure()
            
            # Add pie trace
            fig.add_trace(go.Pie(
                labels=labels,
                values=values,
                hole=0.4,  # Create a donut chart
                textinfo='label+percent',
                textposition='outside',
                marker=dict(
                    colors=self.colors.get("accent_palette", [
                        "#3366cc", "#dc3912", "#ff9900", "#109618", 
                        "#990099", "#0099c6", "#dd4477", "#66aa00"
                    ]),
                    line=dict(color=self.colors.get("background", "#ffffff"), width=1)
                ),
                rotation=90,  # Start from top
                sort=False,  # Don't auto-sort (preserve original order)
                direction='clockwise'
            ))
            
            # Update layout
            title = viz_config.get("title", f"{self.project_name} Distribution")
            source = viz_config.get("source", "Various Sources")
            
            fig.update_layout(
                title=title,
                width=self.width,
                height=self.height,
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                margin=dict(l=20, r=20, t=80, b=20),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.15,
                    xanchor="center",
                    x=0.5
                ),
                uniformtext_minsize=12,
                uniformtext_mode='hide'
            )
            
            # Add data source annotation
            fig.add_annotation(
                text=f"Source: {source}",
                xref="paper", yref="paper",
                x=0.01, y=-0.16,
                showarrow=False,
                font=dict(size=10, color="#808080"),
                align="left"
            )
            
            # Generate output path
            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_{chart_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export as PNG using kaleido
            fig.write_image(output_path, scale=2)
            
            return True, output_path, "Pie chart created successfully"
            
        except Exception as e:
            error_msg = f"Error creating pie chart: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a pie chart.
        
        Args:
            data: Data to check
            viz_type: Type of visualization
            
        Returns:
            True if usable, False otherwise
        """
        if not super().check_data_usability(data, viz_type):
            return False
        
        # For tokenomics charts
        if "tokenomics" in viz_type or "tokenomics" in data:
            if "tokenomics" in data and isinstance(data["tokenomics"], dict):
                return ("token_distribution" in data["tokenomics"] or 
                        "distribution" in data["tokenomics"])
        
        # For chain distribution charts
        if "chain" in viz_type:
            if "defillama" in data and isinstance(data["defillama"], dict):
                return "chains" in data["defillama"] and data["defillama"]["chains"]
        
        # Generic distribution data
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                if "distribution" in source_data:
                    return bool(source_data["distribution"])
        
        return False 

    def _extract_distribution_data(self, data: Dict[str, Any]) -> Any:
        """Extract distribution data from input data."""
        # Direct access if distribution data is at the top level
        if 'token_distribution' in data:
            self.logger.info("Found direct token_distribution data")
            token_dist = data['token_distribution']
            self.logger.info(f"Token distribution type: {type(token_dist)}")
            return token_dist
        
        # Check in tokenomics data - most likely location
        if 'tokenomics' in data:
            self.logger.info("Checking tokenomics data")
            tokenomics_data = data['tokenomics']
            
            if isinstance(tokenomics_data, dict):
                self.logger.info(f"Tokenomics keys: {tokenomics_data.keys() if hasattr(tokenomics_data, 'keys') else 'No keys'}")
                
                # Check for token_distribution
                if 'token_distribution' in tokenomics_data:
                    token_dist = tokenomics_data['token_distribution']
                    self.logger.info(f"Token distribution type: {type(token_dist)}")
                    
                    if isinstance(token_dist, list) and len(token_dist) > 0:
                        self.logger.info(f"Token distribution length: {len(token_dist)}")
                        self.logger.info(f"First token item: {token_dist[0]}")
                        return token_dist
            
        # Look in allocation data
        for source_key in ['allocations', 'distribution', 'token_allocations']:
            if source_key in data:
                alloc_data = data[source_key]
                if isinstance(alloc_data, list) and len(alloc_data) > 0:
                    # Validate the format - should be a list of dicts with name/value pairs
                    if all('name' in item and 'value' in item for item in alloc_data if isinstance(item, dict)):
                        return alloc_data
                    
        # Search in nested data structures from all sources
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                # Check for token distribution in this source
                for key in ['token_distribution', 'allocations', 'distribution', 'token_allocations']:
                    if key in source_data:
                        alloc_data = source_data[key]
                        if isinstance(alloc_data, list) and len(alloc_data) > 0:
                            # Validate the format - should be a list of dicts with name/value pairs
                            if all('name' in item and 'value' in item for item in alloc_data if isinstance(item, dict)):
                                return alloc_data
                
                # Check if we need to go one level deeper for tokenomics data
                if 'tokenomics' in source_data and isinstance(source_data['tokenomics'], dict):
                    tokenomics = source_data['tokenomics']
                    for key in ['token_distribution', 'allocations', 'distribution']:
                        if key in tokenomics:
                            alloc_data = tokenomics[key]
                            if isinstance(alloc_data, list) and len(alloc_data) > 0:
                                # Validate the format
                                if all('name' in item and 'value' in item for item in alloc_data if isinstance(item, dict)):
                                    return alloc_data
        
        return None 

    def generate(self, data: Dict[str, Any], viz_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Generate a pie chart visualization from the data."""
        if not self.check_data_usability(data, 'pie_chart'):
            return False, '', 'No usable distribution data available for pie chart'
        
        # Extract distribution data
        distribution_data = self._extract_distribution_data(data)
        if not distribution_data:
            self.logger.warning("No distribution data found")
            return False, '', 'No usable distribution data available for pie chart'
            
        # Verify distribution data format
        if not isinstance(distribution_data, list) or not all(
            isinstance(item, dict) and 'name' in item and 'value' in item 
            for item in distribution_data
        ):
            self.logger.warning(f"Invalid distribution data format: {distribution_data}")
            return False, '', 'Invalid distribution data format'
        
        # Prepare the data
        labels = [item['name'] for item in distribution_data]
        values = [item['value'] for item in distribution_data]
        
        # Set config
        title = viz_config.get('title', 'Distribution')
        
        # Get colors from style manager
        colors = self.style_manager.get_colors()
        viz_colors = [
            colors['primary'], 
            colors['secondary'], 
            colors['accent'],
            colors['accent_secondary'],
            colors['accent_tertiary']
        ]
        
        # Create a custom color cycle for more than 5 categories
        if len(labels) > 5:
            import matplotlib.colors as mcolors
            import matplotlib.cm as cm
            cmap = cm.get_cmap('tab10')
            viz_colors = [mcolors.rgb2hex(cmap(i)) for i in range(len(labels))]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))
        wedges, texts, autotexts = ax.pie(values, 
                                         autopct='%1.1f%%',
                                         labels=labels,
                                         colors=viz_colors[:len(labels)],
                                         startangle=90,
                                         wedgeprops={'edgecolor': 'w', 'linewidth': 1})
        
        # Customize appearance
        for text in texts:
            text.set_size(12)
        for autotext in autotexts:
            autotext.set_size(10)
            autotext.set_color('white')
            
        # Set title
        ax.set_title(title, fontsize=14, pad=20)
        
        # Save to file
        output_path = f"reports/{self.project_name}/test_token_distribution.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        return True, output_path, 'Pie chart created successfully' 