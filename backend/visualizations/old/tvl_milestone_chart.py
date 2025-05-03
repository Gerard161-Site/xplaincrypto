import os
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import plotly.graph_objects as go
from typing import Dict, Any, List, Optional, Tuple

class TvlMilestoneChartVisualizer:
    """Visualizer for creating combined TVL growth and milestone charts."""
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the TVL milestone chart visualizer.
        
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
        
        # Define professionally designed color palette
        self.colors = {
            'primary': '#4E79A7',
            'secondary': '#F28E2B',
            'accent': '#59A14F',
            'background': '#F8F9FA',
            'text': '#303030',
            'grid': '#DDDDDD',
            'chains': ['#4E79A7', '#F28E2B', '#59A14F', '#E15759', '#76B7B2', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC']
        }
        
        # Set output directory
        self.output_dir = f"docs/{self.project_name.lower()}"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a TVL milestone chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Visualization configuration
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating TVL milestone chart for {self.project_name}")
            
            # Extract TVL data
            tvl_data = None
            if 'tvl_history' in data:
                tvl_data = data['tvl_history']
            elif 'tvl' in data and isinstance(data['tvl'], list):
                tvl_data = data['tvl']
                
            if not tvl_data:
                return {"error": "No TVL history data found"}
                
            # Convert to DataFrame if needed
            df = None
            if isinstance(tvl_data, pd.DataFrame):
                df = tvl_data
            elif isinstance(tvl_data, list):
                # Check format of the TVL data
                if tvl_data and isinstance(tvl_data[0], dict) and 'date' in tvl_data[0] and 'totalLiquidityUSD' in tvl_data[0]:
                    # Format from DeFiLlama API
                    df = pd.DataFrame(tvl_data)
                    df['date'] = pd.to_datetime(df['date'], unit='s')
                    df['tvl_millions'] = df['totalLiquidityUSD'] / 1000000
                elif tvl_data and isinstance(tvl_data[0], list) and len(tvl_data[0]) == 2:
                    # Format: [[timestamp, value], ...]
                    df = pd.DataFrame(tvl_data, columns=['date', 'tvl'])
                    df['date'] = pd.to_datetime(df['date'], unit='ms')
                    df['tvl_millions'] = df['tvl'] / 1000000
            
            if df is None or df.empty:
                return {"error": "Could not process TVL data format"}
                
            # Sort data by date
            df = df.sort_values('date')
            
            # Create the visualization
            output_path = self.render(df, config)
            
            if output_path and os.path.exists(output_path):
                self.logger.info(f"TVL milestone chart saved to {output_path}")
                return {
                    "success": True,
                    "file_path": output_path,
                    "title": config.get("title", f"{self.project_name} TVL Growth and Milestones")
                }
            else:
                return {"error": "Failed to create TVL milestone chart"}
                
        except Exception as e:
            self.logger.error(f"Error creating TVL milestone chart: {str(e)}", exc_info=True)
            return {"error": f"Failed to create TVL milestone chart: {str(e)}"}
            
    def render(self, df: pd.DataFrame, config: Dict[str, Any]) -> str:
        """
        Render the TVL milestone chart visualization.
        
        Args:
            df: DataFrame with TVL data
            config: Visualization configuration
            
        Returns:
            Path to the generated visualization file
        """
        # Define milestones (in millions USD)
        milestones = config.get("milestones", [10, 50, 100, 200, 500, 1000])
        
        # Find when each milestone was first reached
        milestone_dates = []
        for milestone in milestones:
            milestone_reached = df[df['tvl_millions'] >= milestone]
            if not milestone_reached.empty:
                milestone_dates.append({
                    'milestone': milestone,
                    'date': milestone_reached.iloc[0]['date'],
                    'tvl': milestone_reached.iloc[0]['tvl_millions']
                })
        
        # Create an interactive milestone chart using Plotly
        fig = go.Figure()
        
        # Add the TVL line
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['tvl_millions'],
            mode='lines',
            name='TVL',
            line=dict(color=self.colors['primary'], width=3),
            fill='tozeroy',
            fillcolor=f'rgba({78}, {121}, {167}, 0.2)'  # Semi-transparent fill
        ))
        
        # Add milestone markers
        for i, milestone in enumerate(milestone_dates):
            marker_color = self.colors['chains'][min(i, len(self.colors['chains'])-1)]
            fig.add_trace(go.Scatter(
                x=[milestone['date']],
                y=[milestone['tvl']],
                mode='markers+text',
                marker=dict(
                    size=16, 
                    color=marker_color, 
                    line=dict(width=2, color='white'),
                    symbol='diamond'
                ),
                text=[f"${milestone['milestone']}M"],
                textposition="top center",
                name=f"${milestone['milestone']}M Milestone",
                textfont=dict(size=14, color=self.colors['text'])
            ))
        
        # Add annotation for latest TVL
        if not df.empty:
            latest_tvl = df['tvl_millions'].iloc[-1]
            latest_date = df['date'].iloc[-1]
            
            fig.add_annotation(
                x=latest_date,
                y=latest_tvl,
                text=f"Latest: ${latest_tvl:.2f}M",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor=self.colors['secondary'],
                font=dict(size=14, color=self.colors['text']),
                bordercolor=self.colors['secondary'],
                borderwidth=2,
                borderpad=4,
                bgcolor='white',
                opacity=0.8
            )
        
        # Update layout with a more professional style
        chart_title = config.get("title", f"{self.project_name} TVL Growth and Milestones")
        
        fig.update_layout(
            title={
                'text': chart_title,
                'y':0.95,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': dict(size=24, color=self.colors['text'], family="Arial, sans-serif")
            },
            xaxis_title={
                'text': 'Date',
                'font': dict(size=16, color=self.colors['text'])
            },
            yaxis_title={
                'text': 'TVL (Millions USD)',
                'font': dict(size=16, color=self.colors['text'])
            },
            height=700,
            width=1200,
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=14)
            ),
            margin=dict(l=60, r=60, t=100, b=60),
            paper_bgcolor=self.colors['background'],
            plot_bgcolor=self.colors['background'],
            hovermode='x unified'
        )
        
        # Add a grid with refined styling
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(220,220,220,0.5)',
            zeroline=False,
            tickfont=dict(size=12)
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(220,220,220,0.5)',
            zeroline=False,
            tickfont=dict(size=12)
        )
        
        # Define output paths
        output_filename = config.get("output_filename", f"{self.project_name.lower()}_tvl_milestone_chart")
        output_path_png = os.path.join(self.output_dir, f"{output_filename}.png")
        
        # Save the chart
        fig.write_image(output_path_png, scale=2)
        
        # If not pdf_optimized, also save interactive HTML version
        if not self.pdf_optimized:
            output_path_html = os.path.join(self.output_dir, f"{output_filename}.html")
            fig.write_html(output_path_html)
        
        return output_path_png 