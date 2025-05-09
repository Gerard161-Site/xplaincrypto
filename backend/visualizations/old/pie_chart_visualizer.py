import os
import json
import logging
from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import pandas as pd

from backend.visualizations.plotly_visualizer import PlotlyVisualizer
from backend.utils.style_utils import StyleManager

class PieChartVisualizer(PlotlyVisualizer):
    """
    Visualizer for creating pie and donut charts using Plotly.
    Designed for tokenomics, allocation, and distribution data.
    """
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, 
                 style_manager: Optional[StyleManager] = None, logger=None):
        """
        Initialize the pie chart visualizer
        
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
        Create a pie chart visualization
        
        Args:
            viz_type: Type of visualization (e.g., 'tokenomics_pie_chart')
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating pie chart: {viz_type} for {self.project_name}")
            
            # Get chart data - specific handling for tokenomics data
            if 'tokenomics' in viz_type.lower() or 'allocation' in viz_type.lower():
                distribution_data = self._extract_tokenomics_distribution(data)
            else:
                distribution_data = self._extract_pie_data(data)
            
            if not distribution_data:
                self.logger.warning(f"No valid data found for {viz_type}")
                return self.create_error_chart(
                    "No valid data available for pie chart", 
                    os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
                )
            
            # Get labels and values
            labels = [item.get('name', item.get('label', f"Segment {i+1}")) 
                    for i, item in enumerate(distribution_data)]
            values = [item.get('value', 0) for item in distribution_data]
            
            # Create the chart
            return self._create_pie_chart(viz_type, config, labels, values)
            
        except Exception as e:
            self.logger.error(f"Error creating pie chart: {str(e)}")
            return self.create_error_chart(
                f"Error creating pie chart: {str(e)}",
                os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            )
    
    def _create_pie_chart(self, viz_type: str, config: Dict[str, Any], labels: List[str], 
                         values: List[Any]) -> Dict[str, Any]:
        """
        Create a pie chart with the provided data
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            labels: Labels for pie segments
            values: Values for pie segments
            
        Returns:
            Dict with visualization result information
        """
        # Validate inputs
        if not labels or not values or len(labels) != len(values):
            self.logger.error(f"Invalid data for pie chart: labels={len(labels)}, values={len(values)}")
            return self.create_error_chart(
                "Invalid data for pie chart",
                os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            )
        
        # Normalize values if they don't sum to 100
        total = sum(values)
        if total != 0 and total != 100:
            values = [v / total * 100 for v in values]
        
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
            hole=0.4,  # Create a donut chart
            sort=False  # Keep the original order
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
        source = config.get("source", "Project Documentation")
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
            "type": "pie_chart"
        }
    
    def _extract_tokenomics_distribution(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tokenomics distribution data from various sources
        
        Args:
            data: Data dictionary that might contain tokenomics data
            
        Returns:
            List of dicts with name and value keys
        """
        # Try loading from tokenomics cache if not in data
        if not data or not isinstance(data, dict):
            tokenomics_data = self._extract_data_from_cache("distribution", ["tokenomics"])
            if tokenomics_data:
                data = tokenomics_data
        
        distribution = []
        
        # Debug logs for tokenomics data structure
        data_structure = {}
        if isinstance(data, dict):
            for key in data.keys():
                if key == 'tokenomics':
                    self.logger.info(f"Found tokenomics key in data with type: {type(data['tokenomics'])}")
                    tokenomics_obj = data['tokenomics']
                    if isinstance(tokenomics_obj, dict):
                        if 'data' in tokenomics_obj:
                            self.logger.info(f"Tokenomics data keys: {tokenomics_obj['data'].keys() if isinstance(tokenomics_obj['data'], dict) else 'not a dict'}")
                        data_structure['tokenomics'] = list(tokenomics_obj.keys())
        
        if data_structure:
            self.logger.info(f"Data structure: {data_structure}")
        
        # Now extract from data object
        try:
            # Check for various data paths
            if isinstance(data, dict):
                # Look for the specific tokenomics format we know about
                if "tokenomics" in data and isinstance(data["tokenomics"], dict):
                    # This is the format from the TokenomicsServer
                    token_data = data["tokenomics"]
                    if "data" in token_data and isinstance(token_data["data"], dict):
                        data_obj = token_data["data"]
                        
                        # Try different field names for token distribution
                        distribution_field_names = [
                            "token_distribution", "distribution", "tokenomics", 
                            "allocation", "token_allocation", "supply_allocation"
                        ]
                        
                        for field_name in distribution_field_names:
                            if field_name in data_obj and data_obj[field_name]:
                                dist_data = data_obj[field_name]
                                # Dictionary format {category: percentage}
                                if isinstance(dist_data, dict):
                                    for category, value in dist_data.items():
                                        try:
                                            # Skip empty or non-numeric values
                                            if value is None:
                                                continue
                                                
                                            # Handle value as percentage or decimal
                                            if isinstance(value, (int, float)):
                                                # Convert to float and add to distribution
                                                distribution.append({"name": category, "value": float(value)})
                                            elif isinstance(value, str) and value.replace('.', '', 1).isdigit():
                                                # Convert string to float
                                                distribution.append({"name": category, "value": float(value)})
                                        except (ValueError, TypeError):
                                            # Skip invalid values
                                            continue
                                            
                                    if distribution:
                                        self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from TokenomicsServer via {field_name}")
                                        break
                                        
                                # List format [{name: category, value: percentage}, ...]
                                elif isinstance(dist_data, list) and dist_data:
                                    valid_items = []
                                    for item in dist_data:
                                        if isinstance(item, dict) and 'name' in item and 'value' in item:
                                            if item['value'] is not None:
                                                valid_items.append({"name": item['name'], "value": float(item['value'])})
                                    
                                    if valid_items:
                                        distribution = valid_items
                                        self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from TokenomicsServer via {field_name} list")
                                        break
                
                # Try nested paths in data if not found yet
                if not distribution and "data" in data:
                    data_obj = data["data"]
                    
                    # Try tokenomics.token_allocation path
                    if isinstance(data_obj, dict) and "tokenomics" in data_obj:
                        tokenomics = data_obj["tokenomics"]
                        if isinstance(tokenomics, dict):
                            # Check multiple possible field names
                            for field in ["token_allocation", "distribution", "allocation"]:
                                if field in tokenomics and tokenomics[field]:
                                    field_data = tokenomics[field]
                                    if isinstance(field_data, dict):
                                        distribution = [{"name": k, "value": float(v) if isinstance(v, (int, float, str)) else 0} 
                                                     for k, v in field_data.items() if v is not None]
                                        if distribution:
                                            self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from {field}")
                                            break
                    
                    # Try direct distribution/allocation fields
                    if not distribution:
                        for field in ["token_allocation", "distribution", "allocation", "token_distribution"]:
                            if field in data_obj and data_obj[field]:
                                field_data = data_obj[field]
                                if isinstance(field_data, dict):
                                    distribution = [{"name": k, "value": float(v) if isinstance(v, (int, float, str)) else 0} 
                                                 for k, v in field_data.items() if v is not None]
                                    if distribution:
                                        self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from direct {field}")
                                        break
                                elif isinstance(field_data, list) and field_data:
                                    # Check if it's a list of name/value pairs
                                    if all(isinstance(item, dict) and 'name' in item and 'value' in item for item in field_data):
                                        distribution = [{"name": item["name"], "value": float(item["value"]) if isinstance(item["value"], (int, float, str)) else 0} 
                                                     for item in field_data if item["value"] is not None]
                                        if distribution:
                                            self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from direct {field} list")
                                            break
                
                # Last resort: check for direct token_allocation or distribution at top level
                if not distribution:
                    for field in ["token_allocation", "distribution", "allocation", "token_distribution"]:
                        if field in data and data[field]:
                            field_data = data[field]
                            if isinstance(field_data, dict):
                                distribution = [{"name": k, "value": float(v) if isinstance(v, (int, float, str)) else 0} 
                                             for k, v in field_data.items() if v is not None]
                                if distribution:
                                    self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from top-level {field}")
                                    break
                            elif isinstance(field_data, list) and field_data:
                                # Check if it's a list of name/value pairs
                                if all(isinstance(item, dict) and 'name' in item and 'value' in item for item in field_data):
                                    distribution = [{"name": item["name"], "value": float(item["value"]) if isinstance(item["value"], (int, float, str)) else 0} 
                                                 for item in field_data if item["value"] is not None]
                                    if distribution:
                                        self.logger.info(f"Found tokenomics distribution with {len(distribution)} segments from top-level {field} list")
                                        break
            
            # Log results
            if distribution:
                self.logger.info(f"Successfully extracted {len(distribution)} distribution segments")
                # Mark as using real data
                self.using_real_data = True
            else:
                self.logger.warning("No valid tokenomics distribution found in any expected location")
                
            return distribution
            
        except Exception as e:
            self.logger.error(f"Error extracting tokenomics distribution: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return empty list instead of placeholder data - STRICT NO SYNTHETIC DATA POLICY
            return []
    
    def _extract_pie_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract generic pie chart data from various formats
        
        Args:
            data: Input data in various formats
            
        Returns:
            List of dicts with name and value keys
        """
        pie_data = []
        
        try:
            # Extract the data field if present
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            
            # Handle dictionary format - convert to list of dicts
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        pie_data.append({"name": key, "value": value})
            
            # Handle list format - check if it's a list of dicts or list of lists
            elif isinstance(data, list):
                if all(isinstance(item, dict) for item in data):
                    # Check if items have name/value or label/value pairs
                    for item in data:
                        name = item.get("name") or item.get("label") or item.get("category")
                        value = item.get("value") or item.get("amount") or item.get("size")
                        if name and value is not None:
                            pie_data.append({"name": name, "value": value})
                
                elif all(isinstance(item, (list, tuple)) for item in data):
                    # Convert list of lists/tuples to dict format
                    for item in data:
                        if len(item) >= 2:
                            name = item[0]
                            value = item[1]
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                pie_data.append({"name": name, "value": value})
            
            return pie_data
            
        except Exception as e:
            self.logger.error(f"Error extracting pie data: {str(e)}")
            return [] 