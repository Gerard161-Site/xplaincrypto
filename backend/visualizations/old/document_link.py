import os
import plotly.graph_objects as go
from typing import Dict, Any
from .base import BaseVisualizer
import logging

class DocumentLinkVisualizer(BaseVisualizer):
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, logger=None):
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.output_dir = os.path.join("docs", project_name.lower()) if project_name else "docs"
        os.makedirs(self.output_dir, exist_ok=True)

    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any], is_mobile: bool = False) -> Dict[str, Any]:
        try:
            self.logger.info(f"Creating document link visualization for {self.project_name}")
            url = data.get("url", "")
            if not url:
                self.logger.warning("No URL provided for document link")
                fig = go.Figure()
                fig.add_annotation(
                    text="Data Unavailable",
                    x=0.5, y=0.5, xref="paper", yref="paper",
                    showarrow=False, font=dict(size=16, color="#E15759")
                )
                fig.update_layout(width=400, height=300)
                output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
                output_path = os.path.join(self.output_dir, f"{output_filename}.png")
                fig.write_image(output_path, scale=2)
                return {"success": True, "file_path": output_path, "title": config.get("title", "Data Unavailable")}

            fig = go.Figure()
            fig.add_annotation(
                text=f'<a href="{url}" target="_blank">{self.project_name} Whitepaper</a>',
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(size=16, color="#1E88E5"),
                align="center"
            )
            layout_config = self.get_layout_config(is_mobile)
            fig.update_layout(
                width=layout_config["width"],
                height=layout_config["height"],
                margin=layout_config["margin"],
                paper_bgcolor=self.colors['background'],
                plot_bgcolor=self.colors['background'],
                annotations=[
                    dict(
                        text=f"Source: {config.get('source', 'Unknown')}",
                        xref="paper", yref="paper",
                        x=0.01, y=-0.05,
                        showarrow=False,
                        font=dict(size=10),
                        opacity=0.7
                    ),
                    dict(
                        text=f"Chart description: Link to {self.project_name} whitepaper",
                        xref="paper", yref="paper",
                        x=0, y=-0.1,
                        showarrow=False,
                        font=dict(size=10),
                        role="accessibility"
                    )
                ]
            )

            output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            fig.write_image(output_path, scale=2)

            if not self.pdf_optimized:
                html_path = output_path.replace(".png", ".html")
                fig.write_html(html_path, include_plotlyjs='cdn')

            return {
                "success": True,
                "file_path": output_path,
                "title": config.get("title", f"{self.project_name} Whitepaper Link")
            }
        except Exception as e:
            self.logger.error(f"Error creating document link visualization: {str(e)}", exc_info=True)
            return {"error": f"Failed to create document link visualization: {str(e)}"}

    def get_layout_config(self, is_mobile: bool = False) -> Dict[str, Any]:
        """
        Get the layout configuration for the document link.
        
        Args:
            is_mobile: Whether to use mobile layout
            
        Returns:
            Layout configuration dictionary
        """
        if is_mobile:
            return {
                "width": 300,
                "height": 80,
                "font_size": 12,
                "padding": 10,
                "margin": 5
            }
        else:
            return {
                "width": 450,
                "height": 100,
                "font_size": 14,
                "padding": 15,
                "margin": 10
            }