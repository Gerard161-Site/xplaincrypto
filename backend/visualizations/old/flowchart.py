"""
Flowchart visualization module.

This module provides the FlowchartVisualizer class for creating flowchart visualizations
for system architecture, process flows, and relationship diagrams.
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

# For HTML-based flowcharts
import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network

from backend.visualizations.base import BaseVisualizer

class FlowchartVisualizer(BaseVisualizer):
    """
    Specialized visualizer for flowcharts.
    
    Handles creation of flowchart visualizations for system architectures,
    process flows, and relationship diagrams.
    """
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the flowchart visualizer.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Name of the project
            logger: Logger instance
        """
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_")) if project_name else "docs"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a flowchart visualization based on the provided configuration and data.
        
        Args:
            viz_type: Type of visualization (e.g., system_architecture, process_flow)
            config: Configuration for the visualization
            data: Data to visualize (nodes and edges)
            
        Returns:
            Dictionary containing visualization result information
        """
        self.logger.info(f"Creating flowchart: {viz_type}")
        
        # Validate output directory
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        try:
            # Extract nodes and edges from data
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])
            
            if not nodes:
                return {"error": "No nodes provided for flowchart"}
                
            if not edges:
                return {"error": "No edges provided for flowchart"}
            
            # Get title and description from config
            title = config.get('title', 'Flowchart')
            description = config.get('description', '')
            
            # Generate filename
            filename = f"{viz_type.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            file_path = os.path.join(self.output_dir, filename)
            
            # Create the flowchart using pyvis NetworkX
            net = Network(notebook=False, height="500px", width="100%", directed=True)
            
            # Set the theme
            if self.theme == 'dark':
                net.bgcolor = "#212121"
                net.font_color = "#FFFFFF"
            else:
                net.bgcolor = "#FFFFFF"
                net.font_color = "#333333"
            
            # Add nodes with properties
            for node in nodes:
                node_id = node.get('id')
                label = node.get('label', node_id)
                title = node.get('title', label)
                color = node.get('color', '#1E88E5')
                shape = node.get('shape', 'box')
                
                net.add_node(node_id, label=label, title=title, color=color, shape=shape)
            
            # Add edges with properties
            for edge in edges:
                source = edge.get('source')
                target = edge.get('target')
                label = edge.get('label', '')
                color = edge.get('color', '#666666')
                width = edge.get('width', 1)
                
                net.add_edge(source, target, label=label, color=color, width=width)
            
            # Set physics simulation options
            physics_options = {
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 100,
                    "springConstant": 0.08,
                    "damping": 0.4,
                    "avoidOverlap": 0.5
                },
                "minVelocity": 0.75,
                "maxVelocity": 50,
                "stabilization": {
                    "enabled": True,
                    "iterations": 100,
                    "updateInterval": 100,
                    "fit": True
                }
            }
            net.set_options(json.dumps({"physics": physics_options}))
            
            # Add title as HTML heading
            html_title = f"<h2 style='text-align:center; color:{net.font_color}'>{config.get('title', 'Flowchart')}</h2>"
            if description:
                html_title += f"<p style='text-align:center; color:{net.font_color}'>{description}</p>"
            
            # Save the flowchart
            net.save_graph(file_path)
            
            # Insert the title into the HTML file
            with open(file_path, 'r') as f:
                html_content = f.read()
            
            # Insert title after the body tag
            modified_html = html_content.replace('<body>', f'<body>\n{html_title}')
            
            with open(file_path, 'w') as f:
                f.write(modified_html)
            
            # Verify file was saved correctly
            if os.path.exists(file_path):
                self.logger.info(f"Flowchart saved to: {file_path}")
                
                # Return success
                return {
                    "file_path": file_path,
                    "title": config.get('title', 'Flowchart'),
                    "data_summary": {
                        "nodes": len(nodes),
                        "edges": len(edges),
                        "type": viz_type
                    }
                }
            else:
                return {"error": f"Failed to save flowchart {viz_type}"}
            
        except Exception as e:
            self.logger.error(f"Error creating flowchart: {str(e)}", exc_info=True)
            return {"error": f"Failed to create flowchart: {str(e)}"} 