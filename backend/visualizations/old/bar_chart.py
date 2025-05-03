import os
import logging
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from .base import BaseVisualizer

logger = logging.getLogger(__name__)

class BarChartVisualizer(BaseVisualizer):
    """Bar chart visualizer for creating bar chart visualizations."""
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_")) if project_name else "docs"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: dict, data: dict) -> dict:
        """
        Create a bar chart visualization based on the configuration and data.
        
        Args:
            viz_type: Type of visualization to create
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dictionary with metadata about the created visualization
        """
        try:
            title = config.get("title", viz_type.replace("_", " ").replace("chart", "").strip().title())
            subtitle = config.get("subtitle")
            source = config.get("source", "XplainCrypto Analysis")
            
            project_dir = "docs"
            if hasattr(self, 'project_name') and self.project_name:
                project_dir = os.path.join(project_dir, self.project_name.lower().replace(" ", "_"))
            
            os.makedirs(project_dir, exist_ok=True)
            
            filename = f"{viz_type}.png"
            file_path = os.path.join(project_dir, filename)
            
            # Prepare data
            categories = data.get("categories", ["Category 1", "Category 2", "Category 3"])
            values = data.get("values", [0, 0, 0])
            
            if len(categories) != len(values):
                self.logger.error(f"Mismatch between categories ({len(categories)}) and values ({len(values)})")
                return {"error": "Mismatch between categories and values"}
            
            self.logger.info(f"Creating bar chart with {len(categories)} categories and {len(values)} values")
            self.logger.info(f"Categories: {categories}")
            self.logger.info(f"Values: {values}")
            
            # Create the bar chart
            pdf_config = self.style_manager.get_pdf_config()
            width = pdf_config.get("images", {}).get("max_width", 5.5)
            fig, ax = plt.subplots(figsize=(10, 6))
            
            colors = self._get_theme_colors()
            
            fig.patch.set_facecolor(colors["background"])
            ax.set_facecolor(colors["background"])
            
            bars = ax.bar(categories, values, color=colors["primary"], edgecolor=colors["background"])
            
            # Customize appearance with more space for labels
            ax.set_title(title, fontsize=self.style_manager.get_font_size('title'), pad=20)
            ax.set_xlabel("Category", fontsize=self.style_manager.get_font_size('label'), labelpad=15)
            ax.set_ylabel("Value", fontsize=self.style_manager.get_font_size('label'), labelpad=15)
            
            # Rotate x-axis labels for better readability
            plt.xticks(rotation=45, ha='right', fontsize=self.style_manager.get_font_size('label'))
            plt.yticks(fontsize=self.style_manager.get_font_size('label'))
            
            # Add value labels on top of bars with adjusted position
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:,.2f}',
                        ha='center', va='bottom', fontsize=self.style_manager.get_font_size('label'), y=height + 0.05*height)
            
            # Adjust layout to prevent label cutoff
            plt.subplots_adjust(bottom=0.2, top=0.9, left=0.1, right=0.9)
            
            plt.tight_layout()
            
            plt.savefig(file_path, dpi=300, bbox_inches='tight', facecolor=colors["background"])
            plt.close(fig)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                self.logger.info(f"Saved bar chart to {file_path}")
                return {
                    "title": title,
                    "subtitle": subtitle,
                    "source": source,
                    "file_path": file_path,
                    "chart_type": "bar",
                    "data_summary": {
                        "type": "bar",
                        "categories": categories,
                        "values": values
                    }
                }
            else:
                self.logger.error(f"Failed to save bar chart to {file_path}")
                return {"error": "Failed to save bar chart"}
            
        except Exception as e:
            self.logger.error(f"Error creating bar chart: {str(e)}")
            return {
                "error": str(e),
                "viz_type": viz_type
            }