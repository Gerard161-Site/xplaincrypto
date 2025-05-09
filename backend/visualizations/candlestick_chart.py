import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from .base_visualizer import BaseVisualizer

class CandlestickChartVisualizer(BaseVisualizer):
    """
    Visualizer for candlestick charts displaying OHLCV price data.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the candlestick chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a candlestick chart with OHLC data.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        try:
            # ENHANCED DEBUGGING - Complete data structure analysis
            self.logger.info(f"========== CANDLESTICK DEBUG START ==========")
            self.logger.info(f"Data keys at top level: {list(data.keys())}")
            
            # Extract OHLCV data
            ohlcv_data = None
            
            # STEP 1: Check for data in state.data.market_analysis structure
            if 'data' in data and isinstance(data['data'], dict):
                if 'market_analysis' in data['data'] and isinstance(data['data']['market_analysis'], dict):
                    market_data = data['data']['market_analysis']
                    self.logger.info(f"Found market_analysis data, checking for OHLCV in keys: {list(market_data.keys())}")
                    
                    # Check for CoinMarketCap data
                    if 'coinmarketcap' in market_data and isinstance(market_data['coinmarketcap'], dict):
                        cmc_data = market_data['coinmarketcap']
                        if 'ohlcv' in cmc_data:
                            ohlcv_data = cmc_data['ohlcv']
                            self.logger.info("Found OHLCV data in data.market_analysis.coinmarketcap.ohlcv")
                    
                    # Check for CoinGecko data
                    if not ohlcv_data and 'coingecko' in market_data and isinstance(market_data['coingecko'], dict):
                        cg_data = market_data['coingecko']
                        if 'ohlcv' in cg_data:
                            ohlcv_data = cg_data['ohlcv']
                            self.logger.info("Found OHLCV data in data.market_analysis.coingecko.ohlcv")
                        # Check for alternative field names
                        elif 'price_history' in cg_data:
                            ohlcv_data = cg_data['price_history']
                            self.logger.info("Found price_history data in data.market_analysis.coingecko.price_history")
                        elif 'historical_data' in cg_data:
                            ohlcv_data = cg_data['historical_data']
                            self.logger.info("Found historical_data in data.market_analysis.coingecko.historical_data")
            
            # STEP 2: Check for data in state.data.executive_summary structure
            if not ohlcv_data and 'data' in data and isinstance(data['data'], dict):
                if 'executive_summary' in data['data'] and isinstance(data['data']['executive_summary'], dict):
                    summary_data = data['data']['executive_summary']
                    self.logger.info(f"Found executive_summary data, checking for OHLCV in keys: {list(summary_data.keys())}")
                    
                    # Check for CoinMarketCap data
                    if 'coinmarketcap' in summary_data and isinstance(summary_data['coinmarketcap'], dict):
                        cmc_data = summary_data['coinmarketcap']
                        if 'ohlcv' in cmc_data:
                            ohlcv_data = cmc_data['ohlcv']
                            self.logger.info("Found OHLCV data in data.executive_summary.coinmarketcap.ohlcv")
                    
                    # Check for CoinGecko data
                    if not ohlcv_data and 'coingecko' in summary_data and isinstance(summary_data['coingecko'], dict):
                        cg_data = summary_data['coingecko']
                        if 'ohlcv' in cg_data:
                            ohlcv_data = cg_data['ohlcv']
                            self.logger.info("Found OHLCV data in data.executive_summary.coingecko.ohlcv")
                        elif 'price_history' in cg_data:
                            ohlcv_data = cg_data['price_history']
                            self.logger.info("Found price_history data in data.executive_summary.coingecko.price_history")
                        elif 'historical_data' in cg_data:
                            ohlcv_data = cg_data['historical_data']
                            self.logger.info("Found historical_data in data.executive_summary.coingecko.historical_data")

            # STEP 3: Check for data in other sections of state.data
            if not ohlcv_data and 'data' in data and isinstance(data['data'], dict):
                self.logger.info(f"Searching all sections in data structure: {list(data['data'].keys())}")
                # Loop through all sections to find OHLCV data
                for section_name, section_data in data['data'].items():
                    if not isinstance(section_data, dict):
                        continue
                        
                    # Check for CoinMarketCap data in this section
                    if 'coinmarketcap' in section_data and isinstance(section_data['coinmarketcap'], dict):
                        cmc_data = section_data['coinmarketcap']
                        if 'ohlcv' in cmc_data:
                            ohlcv_data = cmc_data['ohlcv']
                            self.logger.info(f"Found OHLCV data in data.{section_name}.coinmarketcap.ohlcv")
                            break
                    
                    # Check for CoinGecko data in this section
                    if 'coingecko' in section_data and isinstance(section_data['coingecko'], dict):
                        cg_data = section_data['coingecko']
                        if 'ohlcv' in cg_data:
                            ohlcv_data = cg_data['ohlcv']
                            self.logger.info(f"Found OHLCV data in data.{section_name}.coingecko.ohlcv")
                            break
                        elif 'price_history' in cg_data:
                            ohlcv_data = cg_data['price_history']
                            self.logger.info(f"Found price_history data in data.{section_name}.coingecko.price_history")
                            break
                        elif 'historical_data' in cg_data:
                            ohlcv_data = cg_data['historical_data']
                            self.logger.info(f"Found historical_data in data.{section_name}.coingecko.historical_data")
                            break
            
            # STEP 4: Check original paths if none of the above worked
            if ohlcv_data is None:
                # Look for data in coinmarketcap source (checking different possible structures)
                if 'coinmarketcap' in data and 'ohlcv' in data['coinmarketcap']:
                    ohlcv_data = data['coinmarketcap']['ohlcv']
                    self.logger.info("Found OHLCV data in data['coinmarketcap']['ohlcv']")
                
                # Also check top-level ohlcv key (common pattern in our cache files)
                elif 'ohlcv' in data:
                    if isinstance(data['ohlcv'], dict) and 'data' in data['ohlcv']:
                        ohlcv_data = data['ohlcv']['data']
                        self.logger.info("Found OHLCV data in data['ohlcv']['data']")
                    else:
                        ohlcv_data = data['ohlcv']
                        self.logger.info("Found OHLCV data in data['ohlcv']")
                
                # Check if it's in coingecko data
                elif 'coingecko' in data and isinstance(data['coingecko'], dict):
                    cg_data = data['coingecko']
                    if 'ohlcv' in cg_data:
                        ohlcv_data = cg_data['ohlcv']
                        self.logger.info("Found OHLCV data in data['coingecko']['ohlcv']")
                    elif 'price_history' in cg_data:
                        ohlcv_data = cg_data['price_history']
                        self.logger.info("Found price history in data['coingecko']['price_history']")
            
            # If no OHLCV data, return error
            if not ohlcv_data:
                self.logger.error(f"No OHLCV data available for candlestick chart. Available keys: {list(data.keys())}")
                if 'data' in data and isinstance(data['data'], dict):
                    self.logger.error(f"Available sections in data: {list(data['data'].keys())}")
                return False, "", "No OHLCV data available for candlestick chart"
                
            # Convert to DataFrame
            self.logger.info(f"OHLCV data type: {type(ohlcv_data)}")
            if isinstance(ohlcv_data, list):
                df = pd.DataFrame(ohlcv_data)
            else:
                # Try to convert dict to DataFrame if possible
                df = pd.DataFrame(ohlcv_data)
            
            self.logger.info(f"DataFrame columns: {df.columns.tolist()}")
            
            # Ensure DataFrame has required columns
            required_cols = ['date', 'open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                self.logger.error(f"OHLCV data missing required columns. Available columns: {df.columns.tolist()}")
                return False, "", f"OHLCV data missing required columns: {', '.join(required_cols)}"
                
            # Create figure
            fig = go.Figure()
            
            # Add candlestick trace
            fig.add_trace(go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name=self.project_name,
                increasing_line_color=self.colors.get("positive", "#26a69a"),
                decreasing_line_color=self.colors.get("negative", "#ef5350")
            ))
            
            # Add volume as bar chart if available
            if 'volume' in df.columns and df['volume'].notna().any():
                # Create subplot for volume
                fig = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=True,
                    vertical_spacing=0.1,
                    row_heights=[0.7, 0.3],
                    subplot_titles=[
                        viz_config.get("title", f"{self.project_name} Price"), 
                        "Volume"
                    ]
                )
                
                # Add candlestick to upper subplot
                fig.add_trace(
                    go.Candlestick(
                        x=df['date'],
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close'],
                        name=self.project_name,
                        increasing_line_color=self.colors.get("positive", "#26a69a"),
                        decreasing_line_color=self.colors.get("negative", "#ef5350")
                    ),
                    row=1, col=1
                )
                
                # Add volume to lower subplot
                fig.add_trace(
                    go.Bar(
                        x=df['date'],
                        y=df['volume'],
                        name="Volume",
                        marker_color=self.colors.get("accent", "#2196f3")
                    ),
                    row=2, col=1
                )
            
            # Add moving averages - 20-day and 50-day EMAs
            if len(df) >= 20:
                df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df['date'],
                        y=df['EMA20'],
                        name="20-day EMA",
                        line=dict(
                            color=self.colors.get("accent_secondary", "#f9a825"),
                            width=1.5
                        )
                    ),
                    row=1, col=1
                )
                
            if len(df) >= 50:
                df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df['date'],
                        y=df['EMA50'],
                        name="50-day EMA",
                        line=dict(
                            color=self.colors.get("accent_tertiary", "#7b1fa2"),
                            width=1.5
                        )
                    ),
                    row=1, col=1
                )
            
            # Update layout
            title = viz_config.get("title", f"{self.project_name} Price Chart")
            source = viz_config.get("source", "CoinMarketCap/CoinGecko")
            
            # Apply layout
            fig.update_layout(
                title=title,
                width=self.width,
                height=self.height,
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                margin=dict(l=50, r=50, t=80, b=50),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis_rangeslider_visible=False,  # Hide default rangeslider
                # Add custom rangeslider with reduced height
                xaxis=dict(
                    rangeselector=dict(
                        buttons=list([
                            dict(count=7, label="1w", step="day", stepmode="backward"),
                            dict(count=1, label="1m", step="month", stepmode="backward"),
                            dict(count=3, label="3m", step="month", stepmode="backward"),
                            dict(step="all")
                        ])
                    )
                )
            )
            
            # Add data source annotation
            fig.add_annotation(
                text=f"Source: {source}",
                xref="paper", yref="paper",
                x=0.01, y=-0.05 if 'volume' not in df.columns else -0.15,
                showarrow=False,
                font=dict(size=10, color="#808080"),
                align="left"
            )
            
            # Generate output path
            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_candlestick")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export as PNG using kaleido
            fig.write_image(output_path, scale=2)
            
            return True, output_path, "Candlestick chart created successfully"
            
        except Exception as e:
            error_msg = f"Error creating candlestick chart: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
            
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a candlestick chart.
        
        Args:
            data: Data to check
            viz_type: Type of visualization
            
        Returns:
            True if usable, False otherwise
        """
        if not super().check_data_usability(data, viz_type):
            return False
        
        # For candlestick charts, we need OHLCV data in some form
        self.logger.info(f"Checking data usability for candlestick chart, keys: {list(data.keys())}")
        
        # STEP 1: Check for data in state.data.market_analysis structure (most common location)
        if 'data' in data and isinstance(data['data'], dict):
            self.logger.info(f"Found data structure, looking for OHLCV in state.data with keys: {list(data['data'].keys())}")
            
            # Check market_analysis section
            if 'market_analysis' in data['data'] and isinstance(data['data']['market_analysis'], dict):
                market_data = data['data']['market_analysis']
                self.logger.info(f"Found market_analysis section with keys: {list(market_data.keys())}")
                
                # Check for CoinMarketCap data
                if 'coinmarketcap' in market_data and isinstance(market_data['coinmarketcap'], dict):
                    cmc_data = market_data['coinmarketcap']
                    if 'ohlcv' in cmc_data:
                        self.logger.info("Found OHLCV data in state.data.market_analysis.coinmarketcap.ohlcv")
                        return True
                
                # Check for CoinGecko data
                if 'coingecko' in market_data and isinstance(market_data['coingecko'], dict):
                    cg_data = market_data['coingecko']
                    if 'ohlcv' in cg_data:
                        self.logger.info("Found OHLCV data in state.data.market_analysis.coingecko.ohlcv")
                        return True
                    if 'price_history' in cg_data:
                        self.logger.info("Found price_history data in state.data.market_analysis.coingecko.price_history")
                        return True
                    if 'historical_data' in cg_data:
                        self.logger.info("Found historical_data in state.data.market_analysis.coingecko.historical_data")
                        return True
            
            # STEP 2: Check executive_summary section
            if 'executive_summary' in data['data'] and isinstance(data['data']['executive_summary'], dict):
                summary_data = data['data']['executive_summary']
                self.logger.info(f"Found executive_summary section with keys: {list(summary_data.keys())}")
                
                # Check for CoinMarketCap data
                if 'coinmarketcap' in summary_data and isinstance(summary_data['coinmarketcap'], dict):
                    cmc_data = summary_data['coinmarketcap']
                    if 'ohlcv' in cmc_data:
                        self.logger.info("Found OHLCV data in state.data.executive_summary.coinmarketcap.ohlcv")
                        return True
                
                # Check for CoinGecko data
                if 'coingecko' in summary_data and isinstance(summary_data['coingecko'], dict):
                    cg_data = summary_data['coingecko']
                    if 'ohlcv' in cg_data:
                        self.logger.info("Found OHLCV data in state.data.executive_summary.coingecko.ohlcv")
                        return True
                    if 'price_history' in cg_data:
                        self.logger.info("Found price_history data in state.data.executive_summary.coingecko.price_history")
                        return True
                    if 'historical_data' in cg_data:
                        self.logger.info("Found historical_data in state.data.executive_summary.coingecko.historical_data")
                        return True
            
            # STEP 3: Check all other sections
            for section_name, section_data in data['data'].items():
                if not isinstance(section_data, dict):
                    continue
                
                # Check for CoinMarketCap data in this section
                if 'coinmarketcap' in section_data and isinstance(section_data['coinmarketcap'], dict):
                    cmc_data = section_data['coinmarketcap']
                    if 'ohlcv' in cmc_data:
                        self.logger.info(f"Found OHLCV data in state.data.{section_name}.coinmarketcap.ohlcv")
                        return True
                
                # Check for CoinGecko data in this section
                if 'coingecko' in section_data and isinstance(section_data['coingecko'], dict):
                    cg_data = section_data['coingecko']
                    if 'ohlcv' in cg_data:
                        self.logger.info(f"Found OHLCV data in state.data.{section_name}.coingecko.ohlcv")
                        return True
                    if 'price_history' in cg_data:
                        self.logger.info(f"Found price_history data in state.data.{section_name}.coingecko.price_history")
                        return True
                    if 'historical_data' in cg_data:
                        self.logger.info(f"Found historical_data in state.data.{section_name}.coingecko.historical_data")
                        return True
        
        # STEP 4: Check original paths
        # Check direct path in top-level data
        if 'coinmarketcap' in data:
            self.logger.info(f"Found coinmarketcap data, keys: {list(data['coinmarketcap'].keys()) if isinstance(data['coinmarketcap'], dict) else 'not a dict'}")
            
            # First check if OHLCV data is directly in the structure
            if isinstance(data['coinmarketcap'], dict) and 'ohlcv' in data['coinmarketcap']:
                self.logger.info("Found direct OHLCV data in coinmarketcap")
                return True
            
            # Check if OHLCV is nested in data.ohlcv
            if isinstance(data['coinmarketcap'], dict) and 'data' in data['coinmarketcap'] and 'ohlcv' in data['coinmarketcap']['data']:
                self.logger.info("Found OHLCV data in coinmarketcap.data.ohlcv")
                return True
        
        # Check in coingecko data    
        if 'coingecko' in data:
            self.logger.info(f"Found coingecko data, keys: {list(data['coingecko'].keys()) if isinstance(data['coingecko'], dict) else 'not a dict'}")
            
            # First check if OHLCV data is directly in the structure
            if isinstance(data['coingecko'], dict) and 'ohlcv' in data['coingecko']:
                self.logger.info("Found direct OHLCV data in coingecko")
                return True
            
            # Check for price history
            if isinstance(data['coingecko'], dict) and 'price_history' in data['coingecko']:
                self.logger.info("Found price_history data in coingecko")
                return True
        
        # Check for top-level OHLCV data
        if 'ohlcv' in data:
            self.logger.info("Found top-level OHLCV data")
            return True
        
        self.logger.warning("No OHLCV data found for candlestick chart")
        return False 