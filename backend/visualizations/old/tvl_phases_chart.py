import os
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any
from .base import BaseVisualizer
import logging
from datetime import datetime

class TVLPhasesChartVisualizer(BaseVisualizer):
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, logger=None):
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name
        self.logger = logger or logging.getLogger(__name__)
        self.output_dir = os.path.join("docs", project_name.lower()) if project_name else "docs"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Add colors attribute based on theme
        self.colors = {
            'background': self.theme_colors["background"],
            'text': self.theme_colors["text"],
            'grid': self.theme_colors["grid"],
            'chains': self.theme_colors["primary"]
        }

    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any], is_mobile: bool = False) -> Dict[str, Any]:
        try:
            self.logger.info(f"Creating TVL phases chart for {self.project_name}")
            tvl_history = data.get("tvl_history", [])
            if not tvl_history:
                self.logger.warning("No TVL history data provided")
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

            # Convert TVL data to DataFrame
            df = pd.DataFrame(tvl_history, columns=['date', 'totalLiquidityUSD'])
            df['date'] = pd.to_datetime(df['date'], unit='ms')
            df['totalLiquidityUSD'] = df['totalLiquidityUSD'] / 1_000_000  # Convert to millions
            df = df.sort_values('date')

            # Identify TVL phases (e.g., significant growth periods)
            df['growth_rate'] = df['totalLiquidityUSD'].pct_change()
            df['phase'] = 'Stable'
            df.loc[df['growth_rate'] > 0.1, 'phase'] = 'Growth'
            df.loc[df['growth_rate'] < -0.1, 'phase'] = 'Decline'

            # Create figure
            fig = go.Figure()
            for phase in df['phase'].unique():
                phase_df = df[df['phase'] == phase]
                fig.add_trace(go.Scatter(
                    x=phase_df['date'],
                    y=phase_df['totalLiquidityUSD'],
                    mode='lines',
                    name=phase,
                    line=dict(color=self.colors['chains'][['Stable', 'Growth', 'Decline'].index(phase) % len(self.colors['chains'])]),
                    connectgaps=True
                ))

            layout_config = self.get_layout_config(is_mobile)
            fig.update_layout(
                title=config.get("title", f"{self.project_name} TVL Phases"),
                xaxis_title="Date",
                yaxis_title="TVL (USD Millions)",
                height=layout_config["height"],
                width=layout_config["width"],
                template='plotly_white',
                margin=layout_config["margin"],
                paper_bgcolor=self.colors['background'],
                plot_bgcolor=self.colors['background'],
                dragmode='zoom' if not self.pdf_optimized else False,
                hovermode='x unified' if not self.pdf_optimized else False,
                showlegend=True,
                uirevision='dataset',
                annotations=[
                    dict(
                        text=f"Source: {config.get('source', 'DeFiLlama')}",
                        xref="paper", yref="paper",
                        x=0.01, y=-0.05,
                        showarrow=False,
                        font=dict(size=10),
                        opacity=0.7
                    ),
                    dict(
                        text=f"Chart description: Line chart showing TVL phases for {self.project_name}",
                        xref="paper", yref="paper",
                        x=0, y=-0.1,
                        showarrow=False,
                        font=dict(size=10)
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
                "title": config.get("title", f"{self.project_name} TVL Phases")
            }
        except Exception as e:
            self.logger.error(f"Error creating TVL phases chart: {str(e)}", exc_info=True)
            return {"error": f"Failed to create TVL phases chart: {str(e)}"}

    def get_layout_config(self, is_mobile: bool = False) -> Dict[str, Any]:
        """
        Get layout configuration based on device type.
        
        Args:
            is_mobile: Whether the layout is for a mobile device
            
        Returns:
            Layout configuration dictionary
        """
        if is_mobile:
            return {
                "width": 320,
                "height": 240,
                "margin": dict(l=10, r=10, t=50, b=50)
            }
        else:
            return {
                "width": 600,
                "height": 400,
                "margin": dict(l=50, r=50, t=80, b=80)
            }