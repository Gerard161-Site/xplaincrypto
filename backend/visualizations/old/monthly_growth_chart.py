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

class MonthlyGrowthChartVisualizer:
    """Visualizer for creating monthly growth rate charts."""
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the monthly growth chart visualizer.
        
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
            'positive': '#59A14F',
            'negative': '#E15759'
        }
        
        # Set output directory
        self.output_dir = f"docs/{self.project_name.lower()}"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a monthly growth chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Visualization configuration
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating monthly growth chart for {self.project_name}")
            
            # Extract TVL or other metric data
            metric_data = None
            if 'tvl_history' in data:
                metric_data = data['tvl_history']
            elif 'tvl' in data and isinstance(data['tvl'], list):
                metric_data = data['tvl']
            elif 'data' in data and isinstance(data['data'], list):
                metric_data = data['data']
                
            if not metric_data:
                return {"error": "No metric history data found"}
                
            # Convert to DataFrame if needed
            df = None
            if isinstance(metric_data, pd.DataFrame):
                df = metric_data
            elif isinstance(metric_data, list):
                # Check format of the data
                if metric_data and isinstance(metric_data[0], dict) and 'date' in metric_data[0] and 'totalLiquidityUSD' in metric_data[0]:
                    # Format from DeFiLlama API
                    df = pd.DataFrame(metric_data)
                    df['date'] = pd.to_datetime(df['date'], unit='s')
                    df['value'] = df['totalLiquidityUSD']
                elif metric_data and isinstance(metric_data[0], dict) and 'date' in metric_data[0] and 'value' in metric_data[0]:
                    # Format: list of dict with date and value
                    df = pd.DataFrame(metric_data)
                    df['date'] = pd.to_datetime(df['date'])
                elif metric_data and isinstance(metric_data[0], list) and len(metric_data[0]) == 2:
                    # Format: [[timestamp, value], ...]
                    df = pd.DataFrame(metric_data, columns=['date', 'value'])
                    df['date'] = pd.to_datetime(df['date'], unit='ms')
                elif isinstance(metric_data[0], dict) and 'month' in metric_data[0] and 'growth_rate' in metric_data[0]:
                    # Pre-processed monthly growth data
                    df = pd.DataFrame(metric_data)
                    return self.render_from_processed_data(df, config)
            
            if df is None or df.empty:
                return {"error": "Could not process metric data format"}
                
            # Calculate monthly data
            # Convert date to the first day of each month for grouping
            df['month'] = df['date'].dt.to_period('M').dt.to_timestamp()
            
            # Group by month and calculate monthly metric value
            monthly_df = df.groupby('month').agg({'value': 'last'}).reset_index()
            
            # Calculate month-over-month growth rate
            monthly_df['growth_rate'] = monthly_df['value'].pct_change() * 100
            
            # Remove the first row which has NaN growth rate
            monthly_df = monthly_df.dropna()
            
            # Create the visualization
            output_path = self.render(monthly_df, config)
            
            if output_path and os.path.exists(output_path):
                self.logger.info(f"Monthly growth chart saved to {output_path}")
                return {
                    "success": True,
                    "file_path": output_path,
                    "title": config.get("title", f"{self.project_name} Monthly Growth Rate")
                }
            else:
                return {"error": "Failed to create monthly growth chart"}
                
        except Exception as e:
            self.logger.error(f"Error creating monthly growth chart: {str(e)}", exc_info=True)
            return {"error": f"Failed to create monthly growth chart: {str(e)}"}
    
    def render_from_processed_data(self, df: pd.DataFrame, config: Dict[str, Any]) -> str:
        """
        Render the monthly growth chart visualization from pre-processed data.
        
        Args:
            df: DataFrame with pre-processed growth data
            config: Visualization configuration
            
        Returns:
            Path to the generated visualization file
        """
        try:
            # Ensure month is in datetime format
            if 'month' in df.columns and not pd.api.types.is_datetime64_dtype(df['month']):
                df['month'] = pd.to_datetime(df['month'])
            
            return self.render(df, config)
        except Exception as e:
            self.logger.error(f"Error rendering from processed data: {str(e)}", exc_info=True)
            return None
            
    def render(self, df: pd.DataFrame, config: Dict[str, Any]) -> str:
        """
        Render the monthly growth chart visualization.
        
        Args:
            df: DataFrame with monthly growth data
            config: Visualization configuration
            
        Returns:
            Path to the generated visualization file
        """
        # Set the chart title
        chart_title = config.get("title", f"{self.project_name} Monthly Growth Rate")
        
        # Create figure
        fig = go.Figure()
        
        # Add growth rate line with positive/negative coloring
        for i in range(len(df)-1):
            # Get current and next data point
            current = df.iloc[i]
            next_point = df.iloc[i+1]
            
            # Set color based on growth rate value
            color = self.colors['positive'] if next_point['growth_rate'] >= 0 else self.colors['negative']
            
            # Add line segment
            fig.add_trace(go.Scatter(
                x=[current['month'], next_point['month']],
                y=[current['growth_rate'], next_point['growth_rate']],
                mode='lines',
                line=dict(color=color, width=3),
                showlegend=False
            ))
        
        # Add markers for each data point
        fig.add_trace(go.Scatter(
            x=df['month'],
            y=df['growth_rate'],
            mode='markers',
            name='Monthly Growth Rate',
            marker=dict(
                size=10,
                color=self.colors['primary'],
                line=dict(width=2, color='white')
            )
        ))
        
        # Add horizontal line at 0% growth
        fig.add_shape(
            type="line",
            x0=df['month'].min(),
            y0=0,
            x1=df['month'].max(),
            y1=0,
            line=dict(color="gray", width=1, dash="dash")
        )
        
        # Update layout with professional styling
        fig.update_layout(
            title={
                'text': chart_title,
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': dict(size=24, color=self.colors['text'], family="Arial, sans-serif")
            },
            xaxis_title={
                'text': config.get("x_label", "Month"),
                'font': dict(size=16, color=self.colors['text'])
            },
            yaxis_title={
                'text': config.get("y_label", "Growth Rate (%)"),
                'font': dict(size=16, color=self.colors['text'])
            },
            height=600,
            width=1000,
            template='plotly_white',
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
            tickfont=dict(size=12),
            tickformat='%b %Y'
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(220,220,220,0.5)',
            zeroline=False,
            tickfont=dict(size=12),
            ticksuffix='%'
        )
        
        # Set output path based on config or default
        output_path = config.get("output_path", "")
        if not output_path:
            output_path = os.path.join(self.output_dir, f"{self.project_name.lower()}_monthly_growth_chart.png")
        else:
            # Replace {project_name} in the output path if present
            output_path = output_path.replace("{project_name}", self.project_name.lower())
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as PNG (static)
        fig.write_image(output_path)
        
        # Also save as interactive HTML if requested
        if config.get("save_html", False):
            html_path = output_path.replace(".png", ".html")
            fig.write_html(html_path)
        
        return output_path 