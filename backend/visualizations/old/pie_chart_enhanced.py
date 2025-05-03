import os
import logging
import json
import plotly.graph_objects as go
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Tuple

class PieChartVisualizer:
    """
    Enhanced pie chart visualizer with trading view quality standards.
    Creates professionally designed pie charts for tokenomics and other distribution data.
    """
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the pie chart visualizer.
        
        Args:
            theme: Visual theme (light or dark)
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for titles and file names
            logger: Logger instance
        """
        self.theme = theme
        self.pdf_optimized = pdf_optimized
        self.project_name = project_name or "unknown"
        self.logger = logger or logging.getLogger(__name__)
        
        # Trading View inspired color palettes
        self.tv_colors = {
            'light': {
                'bg': '#ffffff',
                'text': '#131722',
                'grid': '#eaecef',
                'palette': ['#2962FF', '#26A69A', '#FFC107', '#FF6D00', '#F44336', 
                           '#673AB7', '#8BC34A', '#03A9F4', '#E91E63', '#607D8B'],
                'title': '#131722',
                'subtitle': '#787B86',
                'border': '#d6d8e0',
                'watermark': '#9e9e9e'
            },
            'dark': {
                'bg': '#131722',
                'text': '#d1d4dc',
                'grid': '#363c4e',
                'palette': ['#5B8FF9', '#5AD8A6', '#FFAB0F', '#FF6B3B', '#F5616F', 
                           '#945FB9', '#ADCA53', '#59C4E6', '#F8667B', '#A5AAB5'],
                'title': '#d1d4dc',
                'subtitle': '#787B86',
                'border': '#2a2e39',
                'watermark': '#555555'
            }
        }
        
        # Default output directory
        self.output_dir = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a professional pie chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating {viz_type} for {self.project_name}")
            
            # Get theme colors
            colors = self.tv_colors[self.theme]
            
            # Extract pie data from the input
            pie_data = data.get('data', {})
            
            # Support multiple data formats
            labels = []
            values = []
            
            # Extract data based on format
            if isinstance(pie_data, list):
                # Format: [{"name": "Name1", "value": 50}, {"name": "Name2", "value": 30}, ...]
                # Or: [{"label": "Name1", "value": 50}, {"label": "Name2", "value": 30}, ...]
                for item in pie_data:
                    if isinstance(item, dict):
                        name = item.get('name') or item.get('label') or item.get('category')
                        value = item.get('value') or item.get('percentage') or 0
                        if name:
                            labels.append(name)
                            values.append(value)
            elif isinstance(pie_data, dict):
                # Format: {"Name1": 50, "Name2": 30, ...}
                for key, value in pie_data.items():
                    labels.append(key)
                    values.append(value)
            
            # For tokenomics_pie_chart, try to directly extract from tokenomics data
            if viz_type == 'tokenomics_pie_chart' and not (labels and values):
                token_dist = self._extract_tokenomics_distribution(data)
                if token_dist:
                    labels = [item['name'] for item in token_dist]
                    values = [item['value'] for item in token_dist]
            
            # If still no data, use placeholder
            if not labels or not values:
                self.logger.warning(f"No valid data for {viz_type}, using placeholder data")
                labels = ["Team", "Foundation", "Ecosystem", "Community", "Investors"]
                values = [20, 20, 30, 20, 10]
            
            # Create the visualization with Plotly for interactive and high-quality output
            total = sum(values)
            if total != 100:
                # Normalize to percentages
                values = [v / total * 100 for v in values]
                
            # Sort by value descending for better visualization
            combined = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
            labels, values = zip(*combined)
                
            # Create pie chart
            fig = go.Figure()
            
            # Add pie chart with professional styling
            fig.add_trace(go.Pie(
                labels=labels,
                values=values,
                hole=0.4,  # Donut chart
                textinfo='label+percent',
                insidetextorientation='radial',
                textfont=dict(size=14, family="Arial, sans-serif"),
                marker=dict(
                    colors=colors['palette'],
                    line=dict(color=colors['bg'], width=2)
                ),
                rotation=45,  # Start angle
                sort=False,  # Don't re-sort (already sorted above)
                direction='clockwise',
                pull=[0.05 if i == 0 else 0 for i in range(len(labels))]  # Pull out largest slice
            ))
            
            # Add title with TradingView style
            title = config.get('title', viz_type.replace('_', ' ').title())
            if self.project_name and self.project_name.lower() not in title.lower():
                title = f"{self.project_name} {title}"
                
            fig.update_layout(
                title={
                    'text': title,
                    'y': 0.95,
                    'x': 0.5,
                    'xanchor': 'center',
                    'yanchor': 'top',
                    'font': dict(
                        family="Arial, sans-serif",
                        size=24,
                        color=colors['title'],
                        weight='bold'
                    )
                },
                # Add subtitle/description
                annotations=[
                    dict(
                        text=config.get('description', f"Distribution of {self.project_name} tokens"),
                        x=0.5, y=0.98,
                        xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(
                            family="Arial, sans-serif",
                            size=14,
                            color=colors['subtitle']
                        )
                    ),
                    # Add data source attribution
                    dict(
                        text=f"Source: {config.get('source', 'Project Data')}",
                        x=0.02, y=0.02,
                        xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(size=10, color=colors['subtitle']),
                        opacity=0.7
                    ),
                    # Add accessibility description
                    dict(
                        text=f"Chart description: Pie chart showing {viz_type.replace('_', ' ')} distribution",
                        x=0, y=0,
                        xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(size=1),
                        role="accessibility"
                    )
                ],
                # Professional styling
                height=600,
                width=800,
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.0,
                    font=dict(
                        family="Arial, sans-serif",
                        size=12,
                        color=colors['text']
                    ),
                    bgcolor=colors['bg'],
                    bordercolor=colors['border'],
                    borderwidth=1
                ),
                paper_bgcolor=colors['bg'],
                plot_bgcolor=colors['bg'],
                margin=dict(l=20, r=160, t=100, b=60)
            )
            
            # Add watermark
            fig.add_annotation(
                text=f"XplainCrypto Analysis",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                font=dict(size=30, color=colors['watermark']),
                showarrow=False,
                opacity=0.1
            )
            
            # Add percentage in center (total allocation)
            fig.add_annotation(
                text="100%",
                x=0.5, y=0.5,
                font=dict(size=20, color=colors['text'], family="Arial, sans-serif"),
                showarrow=False
            )
            
            # Generate output paths
            output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Save static image with high resolution
            fig.write_image(output_path, scale=2)
            
            # Save interactive HTML version if not optimized for PDF
            if not self.pdf_optimized:
                html_path = output_path.replace(".png", ".html")
                fig.write_html(html_path)
            
            # Return result
            return {
                "success": True,
                "file_path": output_path,
                "title": title,
                "type": "pie_chart"
            }
                
        except Exception as e:
            self.logger.error(f"Error creating {viz_type}: {str(e)}", exc_info=True)
            return {"error": f"Failed to create {viz_type}: {str(e)}"}
            
    def _extract_tokenomics_distribution(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tokenomics distribution data from various formats.
        
        Args:
            data: Data dictionary that might contain tokenomics data
            
        Returns:
            List of dicts with name and value keys
        """
        distribution = []
        
        # Try different paths to find distribution data
        paths = [
            # Path: data -> tokenomics -> token_distribution
            lambda d: d.get('data', {}).get('tokenomics', {}).get('token_distribution'),
            # Path: data -> token_distribution
            lambda d: d.get('data', {}).get('token_distribution'),
            # Path: data -> distribution
            lambda d: d.get('data', {}).get('distribution'),
            # Path: data -> tokenomics -> distribution
            lambda d: d.get('data', {}).get('tokenomics', {}).get('distribution'),
            # Path: tokenomics -> token_distribution
            lambda d: d.get('tokenomics', {}).get('token_distribution'),
            # Path: tokenomics -> distribution
            lambda d: d.get('tokenomics', {}).get('distribution'),
            # Path: token_distribution
            lambda d: d.get('token_distribution'),
            # Path: distribution
            lambda d: d.get('distribution')
        ]
        
        # Try each path
        for path_func in paths:
            result = path_func(data)
            if result:
                # Check format and convert
                if isinstance(result, dict):
                    # Format: {"Team": 20, "Foundation": 20, ...}
                    distribution = [{'name': k, 'value': v} for k, v in result.items()]
                    break
                elif isinstance(result, list):
                    # Format: [{"name": "Team", "value": 20}, ...]
                    # Or: [{"category": "Team", "percentage": 20}, ...]
                    formatted = []
                    for item in result:
                        if isinstance(item, dict):
                            name = item.get('name') or item.get('label') or item.get('category')
                            value = item.get('value') or item.get('percentage') or 0
                            if name:
                                formatted.append({'name': name, 'value': value})
                    if formatted:
                        distribution = formatted
                        break
        
        return distribution 