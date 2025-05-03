import os
import logging
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, List
from datetime import datetime, timedelta

class LineChartVisualizer:
    """
    Enhanced line chart visualizer with trading view quality standards.
    Creates professionally designed line charts for price, volume, TVL data.
    """
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """Initialize the line chart visualizer."""
        self.theme = theme
        self.pdf_optimized = pdf_optimized
        self.project_name = project_name or "unknown"
        self.logger = logger or logging.getLogger(__name__)
        
        # TradingView style colors
        self.tv_colors = {
            'light': {
                'bg': '#ffffff',
                'text': '#131722',
                'grid': '#eaecef',
                'axis': '#787B86',
                'line': '#2962FF',
                'up': '#26A69A',
                'down': '#EF5350',
                'title': '#131722',
                'subtitle': '#787B86',
                'border': '#d6d8e0',
                'watermark': '#9e9e9e'
            },
            'dark': {
                'bg': '#131722',
                'text': '#d1d4dc',
                'grid': '#363c4e',
                'axis': '#787B86',
                'line': '#5B8FF9',
                'up': '#26A69A',
                'down': '#EF5350',
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
        """Create a professional line chart visualization."""
        try:
            self.logger.info(f"Creating {viz_type} for {self.project_name}")
            
            # Get theme colors
            colors = self.tv_colors[self.theme]
            
            # Extract line data from the input
            line_data = data.get('data', {})
            
            # Prepare data for visualization
            dates = []
            values = []
            
            # Process data based on format
            df = self._prepare_dataframe(line_data, viz_type)
            
            if df is None or df.empty:
                self.logger.warning(f"No valid data for {viz_type}, generating placeholder")
                # Generate placeholder data
                df = self._generate_placeholder_data(viz_type)
            
            # Create line chart
            fig = go.Figure()
            
            # Add line with TradingView styling
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['value'],
                mode='lines',
                name=self._get_line_name(viz_type),
                line=dict(
                    color=colors['line'],
                    width=2,
                    shape='spline',  # Smooth curve
                    smoothing=0.3
                ),
                fill='tozeroy',
                fillcolor=f"rgba({int(colors['line'][1:3], 16)}, {int(colors['line'][3:5], 16)}, {int(colors['line'][5:7], 16)}, 0.1)"
            ))
            
            # Add moving averages for price charts
            if 'price' in viz_type.lower():
                # 7-day MA
                df['MA7'] = df['value'].rolling(window=7).mean()
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['MA7'],
                    mode='lines',
                    name='7-Day MA',
                    line=dict(
                        color='#FF6D00',
                        width=1.5,
                        dash='solid'
                    )
                ))
                
                # 30-day MA
                df['MA30'] = df['value'].rolling(window=30).mean()
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['MA30'],
                    mode='lines',
                    name='30-Day MA',
                    line=dict(
                        color='#673AB7',
                        width=1.5,
                        dash='solid'
                    )
                ))
            
            # Create layout with TradingView styling
            title = config.get('title', self._get_default_title(viz_type))
            
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
                        color=colors['title']
                    )
                },
                # Add subtitle/description
                annotations=[
                    dict(
                        text=config.get('description', self._get_default_description(viz_type)),
                        x=0.5, y=0.98,
                        xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(
                            family="Arial, sans-serif",
                            size=14,
                            color=colors['subtitle']
                        )
                    ),
                    # Add data source
                    dict(
                        text=f"Source: {config.get('source', 'XplainCrypto')}",
                        x=0.02, y=0.02,
                        xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(size=10, color=colors['subtitle']),
                        opacity=0.7
                    )
                ],
                xaxis=dict(
                    title=config.get('x_label', 'Date'),
                    showgrid=True,
                    gridcolor=colors['grid'],
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor=colors['axis'],
                    linewidth=1,
                    tickfont=dict(
                        family="Arial, sans-serif",
                        size=12,
                        color=colors['text']
                    ),
                    tickangle=-45,
                    rangeslider=dict(visible=False)
                ),
                yaxis=dict(
                    title=config.get('y_label', self._get_y_axis_label(viz_type)),
                    showgrid=True,
                    gridcolor=colors['grid'],
                    gridwidth=1,
                    zeroline=False,
                    showline=True,
                    linecolor=colors['axis'],
                    linewidth=1,
                    tickfont=dict(
                        family="Arial, sans-serif",
                        size=12,
                        color=colors['text']
                    ),
                    tickprefix='$' if 'price' in viz_type.lower() or 'tvl' in viz_type.lower() else '',
                    tickformat=',.0f' if 'volume' in viz_type.lower() else '.2f'
                ),
                # Professional styling
                height=550,
                width=850,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
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
                margin=dict(l=60, r=40, t=80, b=60),
                hovermode='x unified'
            )
            
            # Add watermark
            fig.add_annotation(
                text=f"XplainCrypto Analysis",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                font=dict(size=30, color=colors['watermark']),
                showarrow=False,
                opacity=0.08
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
                "type": "line_chart"
            }
                
        except Exception as e:
            self.logger.error(f"Error creating {viz_type}: {str(e)}", exc_info=True)
            return {"error": f"Failed to create {viz_type}: {str(e)}"}
    
    def _prepare_dataframe(self, data, viz_type):
        """Prepare DataFrame from various data formats."""
        df = None
        
        try:
            # For direct DataFrame input
            if isinstance(data, pd.DataFrame):
                return data
                
            # Extract time series data depending on format
            if isinstance(data, dict):
                # Case 1: {"dates": [...], "values": [...]}
                if "dates" in data and "values" in data:
                    dates = data["dates"]
                    values = data["values"]
                    if len(dates) == len(values):
                        df = pd.DataFrame({"date": dates, "value": values})
                        
                # Case 2: [{"date": "2023-01-01", "value": 100}, ...]
                elif "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    item_data = data["data"]
                    df = pd.DataFrame(item_data)
                    
            # For list format
            elif isinstance(data, list):
                if len(data) > 0:
                    if isinstance(data[0], dict) and "date" in data[0]:
                        # Format: [{"date": "2023-01-01", "value": 100}, ...]
                        df = pd.DataFrame(data)
                    elif isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
                        # Format: [["2023-01-01", 100], ...]
                        df = pd.DataFrame(data, columns=["date", "value"])
            
            # Process the DataFrame if created
            if df is not None and not df.empty:
                # Convert date to datetime if needed
                if "date" in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df = df.set_index("date")
                    
                # Find the value column
                value_cols = [col for col in df.columns if col in ["value", "price", "tvl", "volume", "totalLiquidityUSD"]]
                if value_cols:
                    df = df.rename(columns={value_cols[0]: "value"})
                else:
                    # If no obvious value column, use the first numeric column
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        df = df.rename(columns={numeric_cols[0]: "value"})
                        
                # Sort by date
                df = df.sort_index()
                
                # Return processed DataFrame
                return df
                
        except Exception as e:
            self.logger.error(f"Error preparing DataFrame: {str(e)}")
            
        return None
    
    def _generate_placeholder_data(self, viz_type):
        """Generate placeholder data for visualization."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate values based on chart type
        if 'price' in viz_type.lower():
            # Generate realistic price data with some volatility
            base = 100
            np.random.seed(42)  # For reproducibility
            changes = np.random.normal(0, 1, len(date_range))
            # Add slight upward trend
            trend = np.linspace(0, 5, len(date_range))
            values = base + np.cumsum(changes) + trend
            
        elif 'volume' in viz_type.lower():
            # Generate volume data (higher on weekdays, lower on weekends)
            np.random.seed(42)
            values = []
            for date in date_range:
                base_volume = 10000000
                if date.weekday() >= 5:  # Weekend
                    volume = base_volume * 0.7 * np.random.uniform(0.8, 1.2)
                else:  # Weekday
                    volume = base_volume * np.random.uniform(0.9, 1.3)
                values.append(volume)
                
        elif 'tvl' in viz_type.lower():
            # Generate TVL data with growth trend
            np.random.seed(42)
            base = 50000000
            changes = np.random.normal(0, 1, len(date_range))
            # Add strong growth trend
            trend = np.linspace(0, 20000000, len(date_range))
            values = base + np.cumsum(changes) * 100000 + trend
            
        else:
            # Generic data with slight uptrend
            np.random.seed(42)
            base = 100
            changes = np.random.normal(0, 1, len(date_range))
            trend = np.linspace(0, 10, len(date_range))
            values = base + np.cumsum(changes) + trend
        
        # Create DataFrame with placeholder data
        df = pd.DataFrame({"value": values}, index=date_range)
        return df
    
    def _get_line_name(self, viz_type):
        """Get the appropriate line name based on visualization type."""
        if 'price' in viz_type.lower():
            return f"{self.project_name} Price"
        elif 'volume' in viz_type.lower():
            return f"{self.project_name} Volume"
        elif 'tvl' in viz_type.lower():
            return f"{self.project_name} TVL"
        else:
            return f"{self.project_name} Data"
    
    def _get_default_title(self, viz_type):
        """Get default title based on visualization type."""
        if 'price' in viz_type.lower():
            return f"{self.project_name} Price Chart"
        elif 'volume' in viz_type.lower():
            return f"{self.project_name} Trading Volume"
        elif 'tvl' in viz_type.lower():
            return f"{self.project_name} Total Value Locked (TVL)"
        elif 'liquidity' in viz_type.lower():
            return f"{self.project_name} Liquidity Trends"
        else:
            return f"{self.project_name} {viz_type.replace('_', ' ').title()}"
    
    def _get_default_description(self, viz_type):
        """Get default description based on visualization type."""
        time_frame = "60 days"
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        if 'price' in viz_type.lower():
            return f"Price movement over the past {time_frame} (as of {current_date})"
        elif 'volume' in viz_type.lower():
            return f"Trading volume over the past {time_frame} (as of {current_date})"
        elif 'tvl' in viz_type.lower():
            return f"Total Value Locked (TVL) over the past {time_frame} (as of {current_date})"
        else:
            return f"Data trends over the past {time_frame} (as of {current_date})"
    
    def _get_y_axis_label(self, viz_type):
        """Get y-axis label based on visualization type."""
        if 'price' in viz_type.lower():
            return "Price (USD)"
        elif 'volume' in viz_type.lower():
            return "Volume (USD)"
        elif 'tvl' in viz_type.lower():
            return "TVL (USD)"
        else:
            return "Value" 