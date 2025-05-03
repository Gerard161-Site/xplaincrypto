import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from backend.visualizations.plotly_visualizer import PlotlyVisualizer
from backend.utils.style_utils import StyleManager

class ChainDistributionVisualizer(PlotlyVisualizer):
    """
    Visualizer for creating chain distribution charts using Plotly.
    Shows distribution of TVL across different blockchain networks.
    """
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, 
                 style_manager: Optional[StyleManager] = None, logger=None):
        """
        Initialize the chain distribution visualizer
        
        Args:
            theme: Visual theme ('light' or 'dark')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for file paths
            style_manager: Optional StyleManager for consistent styling
            logger: Optional logger instance
        """
        super().__init__(theme, pdf_optimized, project_name, style_manager, logger)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a chain distribution chart visualization
        
        Args:
            viz_type: Type of visualization (e.g., 'chain_distribution_chart')
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating chain distribution chart: {viz_type} for {self.project_name}")
            
            # Extract chain distribution data
            chains_data = self._extract_chain_distribution(data)
            
            if not chains_data:
                self.logger.warning(f"No chain distribution data found for {viz_type}")
                return self.create_error_chart(
                    "No valid chain distribution data available", 
                    os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
                )
            
            # Extract labels and values for pie chart
            labels = [item["name"] for item in chains_data]
            values = [item["value"] for item in chains_data]
            
            # Create the chart
            return self._create_distribution_chart(viz_type, config, labels, values)
            
        except Exception as e:
            self.logger.error(f"Error creating chain distribution chart: {str(e)}")
            return self.create_error_chart(
                f"Error creating chain distribution chart: {str(e)}",
                os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            )
    
    def _create_distribution_chart(self, viz_type: str, config: Dict[str, Any], 
                               labels: List[str], values: List[float]) -> Dict[str, Any]:
        """
        Create a chain distribution chart
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            labels: Labels for the chains
            values: Values for each chain (percentages)
            
        Returns:
            Dict with visualization result information
        """
        # Ensure we have valid data
        if not labels or not values or len(labels) != len(values):
            self.logger.error(f"Invalid data for chain distribution chart: labels={len(labels)}, values={len(values)}")
            return self.create_error_chart(
                "Invalid data for chain distribution chart",
                os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            )
        
        # Create figure
        fig = go.Figure()
        
        # Add pie chart
        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            textinfo='label+percent',
            insidetextorientation='radial',
            textfont=dict(size=14),
            marker=dict(
                colors=self.theme_colors.get("accent_palette", None),
                line=dict(color=self.theme_colors.get("background"), width=2)
            ),
            hole=0.4  # Create a donut chart
        ))
        
        # Get layout configuration
        layout_config = self.get_layout_config()
        
        # Get title from config
        title = config.get("title", viz_type.replace("_", " ").title())
        if self.project_name.lower() not in title.lower():
            title = f"{self.project_name} {title}"
        
        # Style the figure with the styler
        fig = self.styler.style_pie_chart(fig)
        fig = self.styler.apply_layout(
            fig=fig,
            title=title,
            width=layout_config.get("width", 800),
            height=layout_config.get("height", 600)
        )
        
        # Add source if provided
        source = config.get("source", "DeFiLlama")
        fig = self.styler.add_source_annotation(fig, source)
        
        # Add watermark
        fig = self.styler.add_watermark(fig)
        
        # Set output filename and path
        output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
        output_path = os.path.join(self.output_dir, f"{output_filename}.png")
        
        # Save the figure
        fig.write_image(output_path, scale=2)
        
        # If not optimized for PDF, also save as HTML
        if not self.pdf_optimized:
            html_path = output_path.replace(".png", ".html")
            fig.write_html(html_path)
        
        return {
            "success": True,
            "file_path": output_path,
            "title": title,
            "type": "chain_distribution_chart"
        }
    
    def _extract_chain_distribution(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract chain distribution data from DeFiLlama or tokenomics data.
        
        Args:
            data: Data dictionary
            
        Returns:
            List of dictionaries with chain and percentage
        """
        distribution = []
        
        try:
            # Debug log the structure of the data
            self.logger.info(f"Extracting chain distribution from data of type: {type(data)}")
            if isinstance(data, dict):
                self.logger.info(f"Data keys: {list(data.keys())}")
                
                # Check for DeFiLlama data (most likely source)
                if 'defillama' in data:
                    defillama_data = data['defillama']
                    
                    # Handle different DeFiLlama data formats
                    if isinstance(defillama_data, dict):
                        self.logger.info(f"DeFiLlama data keys: {list(defillama_data.keys())}")
                        
                        # Check for direct tvlByChain field
                        if 'tvlByChain' in defillama_data and isinstance(defillama_data['tvlByChain'], dict):
                            tvl_by_chain = defillama_data['tvlByChain']
                            if tvl_by_chain:
                                total_tvl = sum(tvl_by_chain.values())
                                if total_tvl > 0:
                                    for chain, value in tvl_by_chain.items():
                                        distribution.append({
                                            'name': chain,
                                            'value': (value / total_tvl) * 100
                                        })
                                    self.logger.info(f"Extracted {len(distribution)} chains from tvlByChain")
                                    return distribution
                        
                        # Check for chains list
                        if 'chains' in defillama_data:
                            chains = defillama_data['chains']
                            if isinstance(chains, list) and chains:
                                # Simple case: just a list of chains without proportions
                                # We'll assign equal weight to each chain
                                weight = 100.0 / len(chains)
                                distribution = [{'name': chain, 'value': weight} for chain in chains]
                                self.logger.info(f"Extracted {len(distribution)} chains with equal distribution")
                                return distribution
                        
                        # Check if we have chain breakdown in a nested structure
                        if 'data' in defillama_data and isinstance(defillama_data['data'], dict):
                            dl_data = defillama_data['data']
                            
                            # Check for tvlByChain
                            if 'tvlByChain' in dl_data and isinstance(dl_data['tvlByChain'], dict):
                                tvl_by_chain = dl_data['tvlByChain']
                                if tvl_by_chain:
                                    total_tvl = sum(tvl_by_chain.values())
                                    if total_tvl > 0:
                                        for chain, value in tvl_by_chain.items():
                                            distribution.append({
                                                'name': chain,
                                                'value': (value / total_tvl) * 100
                                            })
                                        self.logger.info(f"Extracted {len(distribution)} chains from nested tvlByChain")
                                        return distribution
                            
                            # Check for chains list in nested data
                            if 'chains' in dl_data:
                                chains = dl_data['chains']
                                if isinstance(chains, list) and chains:
                                    weight = 100.0 / len(chains)
                                    distribution = [{'name': chain, 'value': weight} for chain in chains]
                                    self.logger.info(f"Extracted {len(distribution)} chains with equal distribution from nested data")
                                    return distribution
                    
                    # Try parsing string data (sometimes DeFiLlama returns a serialized JSON string)
                    elif isinstance(defillama_data, str):
                        try:
                            # Find the beginning of JSON
                            start_idx = defillama_data.find('{')
                            if start_idx >= 0:
                                json_str = defillama_data[start_idx:]
                                defillama_json = json.loads(json_str)
                                
                                # Extract from parsed JSON
                                if isinstance(defillama_json, dict):
                                    # Check for tvlByChain
                                    if 'tvlByChain' in defillama_json and isinstance(defillama_json['tvlByChain'], dict):
                                        tvl_by_chain = defillama_json['tvlByChain']
                                        if tvl_by_chain:
                                            total_tvl = sum(tvl_by_chain.values())
                                            if total_tvl > 0:
                                                for chain, value in tvl_by_chain.items():
                                                    distribution.append({
                                                        'name': chain,
                                                        'value': (value / total_tvl) * 100
                                                    })
                                                self.logger.info(f"Extracted {len(distribution)} chains from JSON string tvlByChain")
                                                return distribution
                                    
                                    # Check for chains list
                                    if 'chains' in defillama_json:
                                        chains = defillama_json['chains']
                                        if isinstance(chains, list) and chains:
                                            weight = 100.0 / len(chains)
                                            distribution = [{'name': chain, 'value': weight} for chain in chains]
                                            self.logger.info(f"Extracted {len(distribution)} chains with equal distribution from JSON string")
                                            return distribution
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse DeFiLlama string as JSON: {str(e)}")
                
                # Try tokenomics data as an alternative source
                if 'tokenomics' in data:
                    tokenomics_data = data['tokenomics']
                    
                    if isinstance(tokenomics_data, dict):
                        # Check for different field structures
                        chains_field_names = ['chains', 'blockchain_distribution', 'chain_distribution', 'distribution_by_chain']
                        
                        for field in chains_field_names:
                            if field in tokenomics_data:
                                chains_data = tokenomics_data[field]
                                
                                # Handle dictionary format {chain: percentage}
                                if isinstance(chains_data, dict):
                                    for chain, value in chains_data.items():
                                        # Skip if value is None or not numeric
                                        if value is None:
                                            continue
                                            
                                        try:
                                            if isinstance(value, (int, float)):
                                                distribution.append({'name': chain, 'value': float(value)})
                                            elif isinstance(value, str) and value.replace('.', '', 1).isdigit():
                                                distribution.append({'name': chain, 'value': float(value)})
                                        except (ValueError, TypeError):
                                            # Skip invalid values
                                            continue
                                    
                                    if distribution:
                                        self.logger.info(f"Extracted {len(distribution)} chains from tokenomics {field}")
                                        return distribution
                                
                                # Handle list format if it's a list of dicts
                                elif isinstance(chains_data, list) and chains_data:
                                    if all(isinstance(item, dict) for item in chains_data):
                                        valid_items = []
                                        for item in chains_data:
                                            if 'name' in item and 'value' in item and item['value'] is not None:
                                                valid_items.append({'name': item['name'], 'value': float(item['value'])})
                                        
                                        if valid_items:
                                            distribution = valid_items
                                            self.logger.info(f"Extracted {len(distribution)} chains from tokenomics {field} list")
                                            return distribution
                                    elif all(isinstance(item, str) for item in chains_data):
                                        # Just a list of chain names without values
                                        weight = 100.0 / len(chains_data)
                                        distribution = [{'name': chain, 'value': weight} for chain in chains_data]
                                        self.logger.info(f"Extracted {len(distribution)} chains from tokenomics {field} with equal weights")
                                        return distribution
            
            # If we couldn't extract anything meaningful, return an empty list (strict no synthetic data policy)
            if not distribution:
                self.logger.warning("No valid chain distribution data found, returning empty list")
                return []
            
            return distribution
            
        except Exception as e:
            self.logger.error(f"Error extracting chain distribution: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return empty list (strict no synthetic data policy)
            return [] 