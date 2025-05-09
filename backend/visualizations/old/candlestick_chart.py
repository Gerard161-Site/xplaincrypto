import os
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
import requests
import mplfinance as mpf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional, Tuple

class CandlestickChartVisualizer:
    """Visualizer for creating TradingView-style candlestick charts."""
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """
        Initialize the candlestick chart visualizer.
        
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
        
        # Set TradingView style colors
        self.tv_colors = {
            'light': {
                'bg': '#ffffff',
                'grid': '#eaecef',
                'text': '#131722',
                'border': '#d6d8e0',
                'up': '#089981',
                'down': '#f23645',
                'volume_up': '#08998144',
                'volume_down': '#f2364544',
                'wick': '#131722',
                'ema1': '#aa6b12',
                'ema2': '#1848cc',
                'watermark': '#9e9e9e'
            },
            'dark': {
                'bg': '#131722',
                'grid': '#363c4e',
                'text': '#d1d4dc',
                'border': '#2a2e39',
                'up': '#26a69a',
                'down': '#ef5350',
                'volume_up': '#26a69a44',
                'volume_down': '#ef535044',
                'wick': '#d1d4dc',
                'ema1': '#e1c564',
                'ema2': '#ff9100',
                'watermark': '#555555'
            }
        }
        
        # Set output directory
        self.output_dir = f"docs/{self.project_name}"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a candlestick chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Visualization configuration
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating candlestick chart for {self.project_name}")
            
            # Extract configuration
            days = config.get('days', 30)
            theme = config.get('theme', self.theme)
            
            # Get OHLCV data
            df = self._get_ohlcv_data(data, days)
            
            if df is None or df.empty:
                return {"error": "No OHLCV data available"}
                
            # Create the visualization
            output_paths = self._create_tradingview_style_charts(df, days)
            
            if output_paths:
                self.logger.info(f"Candlestick charts saved to {output_paths}")
                return {
                    "success": True,
                    "file_paths": output_paths,
                    "file_path": output_paths[theme if theme in output_paths else list(output_paths.keys())[0]],
                    "title": config.get("title", f"{self.project_name} Price Chart")
                }
            else:
                return {"error": "Failed to create candlestick chart"}
                
        except Exception as e:
            self.logger.error(f"Error creating candlestick chart: {str(e)}", exc_info=True)
            return {"error": f"Failed to create candlestick chart: {str(e)}"}
            
    def _get_ohlcv_data(self, data: Dict[str, Any], days: int) -> Optional[pd.DataFrame]:
        """
        Get OHLCV data for candlestick chart.
        
        Args:
            data: Data containing OHLCV data or settings to fetch it
            days: Number of days of data to get
            
        Returns:
            DataFrame with OHLCV data or None if unavailable
        """
        # Check if OHLCV data is provided directly
        if 'ohlcv' in data:
            df = self._prepare_dataframe(data['ohlcv'])
            if df is not None:
                return df
        
        # Try to load data from cache
        cache_dir = os.path.join(self.output_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        cache_file = os.path.join(cache_dir, f"{self.project_name.lower()}_ohlcv_data.json")
        
        # Check for cached data
        if os.path.exists(cache_file):
            file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))
            if file_age < datetime.timedelta(hours=24):
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        self.logger.info(f"Using cached OHLCV data for {self.project_name}")
                        # Convert to DataFrame
                        df = pd.DataFrame(data)
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)
                        return df
                except Exception as e:
                    self.logger.warning(f"Error loading cached data: {str(e)}")
        
        # If no cached data, fetch from CoinGecko
        try:
            self.logger.info(f"Fetching OHLCV data for {self.project_name} from CoinGecko")
            base_url = "https://api.coingecko.com/api/v3"
            
            # Get the coin ID
            coin_id = self._get_coin_id()
            
            # Fetch OHLCV data
            response = requests.get(
                f"{base_url}/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": days}
            )
            
            if response.status_code == 200:
                # CoinGecko returns data as [timestamp, open, high, low, close]
                raw_data = response.json()
                
                # Convert to DataFrame
                df = pd.DataFrame(raw_data, columns=['date', 'open', 'high', 'low', 'close'])
                df['date'] = pd.to_datetime(df['date'], unit='ms')
                
                # Get volume data separately (CoinGecko OHLC endpoint doesn't include volume)
                vol_response = requests.get(
                    f"{base_url}/coins/{coin_id}/market_chart",
                    params={"vs_currency": "usd", "days": days, "interval": "daily"}
                )
                
                if vol_response.status_code == 200:
                    vol_data = vol_response.json()
                    volumes = vol_data.get('total_volumes', [])
                    
                    # Create volume DataFrame
                    vol_df = pd.DataFrame(volumes, columns=['date', 'volume'])
                    vol_df['date'] = pd.to_datetime(vol_df['date'], unit='ms')
                    
                    # Resample volume to match OHLCV data points
                    vol_df.set_index('date', inplace=True)
                    
                    # Calculate resample frequency
                    if len(df) > 0 and days > 0:
                        resample_hours = max(1, int(24/max(1, len(df)/days)))
                        vol_df = vol_df.resample(f'{resample_hours}h').mean()
                    else:
                        vol_df = vol_df.resample('1d').mean()
                    
                    # Merge with price data
                    df.set_index('date', inplace=True)
                    if len(vol_df) >= len(df):
                        vol_df = vol_df.iloc[:len(df)]
                    else:
                        # Pad with mean volume if not enough data points
                        padding = len(df) - len(vol_df)
                        pad_data = pd.DataFrame(
                            {'volume': [vol_df['volume'].mean()] * padding}, 
                            index=df.index[-padding:]
                        )
                        vol_df = pd.concat([vol_df, pad_data])
                        
                    df['volume'] = vol_df['volume'].values
                else:
                    # If volume data fetch fails, use placeholder values
                    self.logger.warning(f"Failed to fetch volume data for {self.project_name}. Using placeholders.")
                    df['volume'] = 0
                
                # Cache the data
                try:
                    with open(cache_file, 'w') as f:
                        json.dump(df.reset_index().to_dict('records'), f)
                    self.logger.info(f"Cached OHLCV data for {self.project_name}")
                except Exception as e:
                    self.logger.warning(f"Error caching data: {str(e)}")
                
                return df
            else:
                self.logger.error(f"Error fetching OHLCV data: {response.status_code} - {response.text}")
        except Exception as e:
            self.logger.error(f"Error in OHLCV data fetch: {str(e)}")
        
        # If all else fails, generate demo data
        self.logger.warning(f"Using generated demo data for {self.project_name}")
        return self._generate_demo_price_data(days)
    
    def _get_coin_id(self) -> str:
        """Get the CoinGecko coin ID for the project."""
        base_url = "https://api.coingecko.com/api/v3"
        
        # Try to get the coin ID from CoinGecko
        try:
            response = requests.get(f"{base_url}/coins/list")
            if response.status_code == 200:
                coins = response.json()
                for coin in coins:
                    if coin['name'].lower() == self.project_name.lower() or coin['symbol'].lower() == self.project_name.lower():
                        coin_id = coin['id']
                        self.logger.info(f"Found coin ID for {self.project_name}: {coin_id}")
                        return coin_id
        except Exception as e:
            self.logger.error(f"Error fetching coin list: {str(e)}")
        
        # If coin ID not found, try common ones
        common_ids = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum", 
            "solana": "solana",
            "cardano": "cardano",
            "bnb": "binancecoin",
            "binance": "binancecoin",
            "ondo": "ondo-finance",
            "xrp": "ripple"
        }
        coin_id = common_ids.get(self.project_name.lower(), self.project_name.lower())
        self.logger.info(f"Using assumed coin ID for {self.project_name}: {coin_id}")
        
        return coin_id
    
    def _prepare_dataframe(self, ohlcv_data: Any) -> Optional[pd.DataFrame]:
        """Prepare a DataFrame from various OHLCV data formats."""
        try:
            if isinstance(ohlcv_data, pd.DataFrame):
                df = ohlcv_data.copy()
                if 'date' in df.columns and not df.index.name == 'date':
                    df.set_index('date', inplace=True)
                return df
            elif isinstance(ohlcv_data, list):
                if not ohlcv_data:
                    return None
                    
                # Determine the format of the OHLCV data
                if isinstance(ohlcv_data[0], dict) and all(k in ohlcv_data[0] for k in ['date', 'open', 'high', 'low', 'close']):
                    # Format: [{date, open, high, low, close, volume}, ...]
                    df = pd.DataFrame(ohlcv_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    return df
                elif isinstance(ohlcv_data[0], list) and len(ohlcv_data[0]) >= 5:
                    # Format: [[timestamp, open, high, low, close, volume], ...]
                    columns = ['date', 'open', 'high', 'low', 'close']
                    if len(ohlcv_data[0]) >= 6:
                        columns.append('volume')
                        
                    df = pd.DataFrame(ohlcv_data, columns=columns)
                    df['date'] = pd.to_datetime(df['date'], unit='ms')
                    df.set_index('date', inplace=True)
                    
                    # Add volume if missing
                    if 'volume' not in df.columns:
                        df['volume'] = 0
                        
                    return df
            
            return None
        except Exception as e:
            self.logger.error(f"Error preparing DataFrame: {str(e)}")
            return None
    
    def _generate_demo_price_data(self, days: int) -> pd.DataFrame:
        """Generate demo price data for when real data is unavailable."""
        self.logger.info(f"Generating demo price data for {days} days")
        
        # Generate dates
        end_date = datetime.datetime.now()
        date_range = [end_date - datetime.timedelta(days=i) for i in range(days, -1, -1)]
        
        # Generate price data with realistic trends and volatility
        np.random.seed(42)  # For reproducibility
        
        # Start with a base price
        base_price = 100.0
        
        # Generate returns with a slight upward trend and realistic volatility
        daily_returns = np.random.normal(0.002, 0.02, len(date_range))
        
        # Calculate cumulative returns
        cumulative_returns = np.cumprod(1 + daily_returns)
        
        # Calculate prices
        prices = base_price * cumulative_returns
        
        # Generate OHLC data
        ohlc_data = []
        for i, date in enumerate(date_range):
            price = prices[i]
            daily_volatility = price * 0.01  # 1% daily volatility
            
            # Calculate open, high, low, close
            if i == 0:
                open_price = price * 0.99
            else:
                open_price = ohlc_data[i-1]['close']
                
            close_price = price
            high_price = price + daily_volatility * np.random.uniform(0.5, 1.5)
            low_price = price - daily_volatility * np.random.uniform(0.5, 1.5)
            
            # Ensure high >= open, close and low <= open, close
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            # Generate volume (higher on volatile days)
            volume_base = base_price * 10000
            volume = volume_base * (1 + np.abs(daily_returns[i]) * 10)
            
            ohlc_data.append({
                'date': date,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlc_data)
        df.set_index('date', inplace=True)
        
        return df
    
    def _create_tradingview_style_charts(self, df: pd.DataFrame, days: int) -> Dict[str, str]:
        """
        Create TradingView style candlestick charts for light and dark themes.
        
        Args:
            df: DataFrame with OHLCV data
            days: Number of days of data
            
        Returns:
            Dictionary mapping themes to file paths
        """
        # Create output directory
        viz_dir = os.path.join(self.output_dir, "visualizations")
        os.makedirs(viz_dir, exist_ok=True)
        
        # Define file paths
        light_filepath = os.path.join(self.output_dir, f"{self.project_name.lower()}_candlestick_chart_light.png")
        dark_filepath = os.path.join(self.output_dir, f"{self.project_name.lower()}_candlestick_chart.png")  # Dark as default
        
        output_paths = {}
        
        # Create light theme chart
        try:
            colors = self.tv_colors['light']
            
            fig = self._create_plotly_candlestick(df, days, 'light')
            fig.write_image(light_filepath, scale=2)
            
            if os.path.exists(light_filepath):
                output_paths['light'] = light_filepath
                self.logger.info(f"Created light theme chart: {light_filepath}")
        except Exception as e:
            self.logger.error(f"Error creating light theme chart: {str(e)}")
        
        # Create dark theme chart
        try:
            colors = self.tv_colors['dark']
            
            fig = self._create_plotly_candlestick(df, days, 'dark')
            fig.write_image(dark_filepath, scale=2)
            
            if os.path.exists(dark_filepath):
                output_paths['dark'] = dark_filepath
                self.logger.info(f"Created dark theme chart: {dark_filepath}")
        except Exception as e:
            self.logger.error(f"Error creating dark theme chart: {str(e)}")
        
        return output_paths
    
    def _create_plotly_candlestick(self, df: pd.DataFrame, days: int, theme: str = 'light') -> go.Figure:
        """
        Create a Plotly candlestick chart with TradingView styling.
        
        Args:
            df: DataFrame with OHLCV data
            days: Number of days of data
            theme: 'light' or 'dark'
            
        Returns:
            Plotly Figure object
        """
        colors = self.tv_colors[theme]
        
        # Create subplot with 2 rows (price and volume)
        fig = make_subplots(
            rows=2, cols=1, 
            row_heights=[0.8, 0.2],
            vertical_spacing=0.05,
            shared_xaxes=True
        )
        
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                increasing_line_color=colors['up'],
                decreasing_line_color=colors['down'],
                name="Price"
            ),
            row=1, col=1
        )
        
        # Add volume bars
        colors_volume = []
        for i in range(len(df)):
            if i > 0 and df['close'].iloc[i] >= df['close'].iloc[i-1]:
                colors_volume.append(colors['up'])
            else:
                colors_volume.append(colors['down'])
                
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                marker_color=colors_volume,
                name="Volume",
                opacity=0.5
            ),
            row=2, col=1
        )
        
        # Calculate and add EMAs
        df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['EMA20'],
                line=dict(color=colors['ema1'], width=1.5),
                name="EMA 20"
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['EMA50'],
                line=dict(color=colors['ema2'], width=1.5),
                name="EMA 50"
            ),
            row=1, col=1
        )
        
        # Update layout for TradingView style
        fig.update_layout(
            title=f"{self.project_name} Price ({days} Days)",
            title_font=dict(size=24, color=colors['text']),
            font=dict(family="Arial, sans-serif", size=12, color=colors['text']),
            xaxis_title=None,
            yaxis_title="Price (USD)",
            plot_bgcolor=colors['bg'],
            paper_bgcolor=colors['bg'],
            height=800,
            width=1200,
            legend=dict(
                x=0.01,
                y=0.99,
                bgcolor=colors['bg'],
                bordercolor=colors['border']
            ),
            margin=dict(l=50, r=50, t=80, b=50),
            xaxis_rangeslider_visible=False
        )
        
        # Update axis styles
        fig.update_xaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            linecolor=colors['border'],
            row=1, col=1
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            linecolor=colors['border'],
            row=1, col=1,
            tickprefix='$',
            side='right'
        )
        
        fig.update_xaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            linecolor=colors['border'],
            row=2, col=1
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            linecolor=colors['border'],
            row=2, col=1,
            side='right'
        )
        
        # Add watermark
        fig.add_annotation(
            text=f"XplainCrypto Analysis",
            x=0.5, y=0.5,
            font=dict(size=36, color=colors['watermark']),
            showarrow=False,
            opacity=0.1,
            xref="paper", yref="paper"
        )
        
        # Add data source
        fig.add_annotation(
            text="Data: CoinGecko",
            x=0.99, y=0.01,
            font=dict(size=10, color=colors['text']),
            showarrow=False,
            xref="paper", yref="paper",
            xanchor="right", yanchor="bottom"
        )
        
        return fig 