#!/usr/bin/env python3
"""
Test script for CoinMarketCap OHLCV data implementation.
"""
import os
import json
import logging
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import seaborn as sns
from datetime import datetime

# Import the CoinMarketCapAPI directly
from backend.retriever.coinmarketcap_api import CoinMarketCapAPI
from backend.orchestration.mcp.retriever_servers.coinmarketcap_server import get_coin_ohlcv_data

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_coinmarketcap_ohlcv")

async def test_ohlcv_implementation(coin="ONDO", days=30):
    """Test the OHLCV data implementation directly."""
    logger.info(f"Testing OHLCV implementation for {coin}, days={days}")
    
    try:
        # Call the MCP tool directly
        result = await get_coin_ohlcv_data(coin, days)
        
        if not result or "ohlcv" not in result:
            logger.error(f"OHLCV data not found in result. Result keys: {result.keys() if result else 'None'}")
            return None
        
        ohlcv_data = result["ohlcv"]
        if not ohlcv_data:
            logger.error("Empty OHLCV data")
            return None
        
        logger.info(f"OHLCV data contains {len(ohlcv_data)} entries")
        
        # Display sample of the data
        logger.info(f"First entry: {ohlcv_data[0]}")
        logger.info(f"Last entry: {ohlcv_data[-1]}")
        
        # Convert to DataFrame and analyze
        df = pd.DataFrame(ohlcv_data)
        logger.info(f"DataFrame columns: {df.columns}")
        logger.info(f"DataFrame shape: {df.shape}")
        
        # Check for required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            return None
        
        # Convert date to datetime for plotting
        if 'date' in df.columns:
            try:
                # Handle ISO format dates
                df['date'] = pd.to_datetime(df['date'])
            except:
                logger.warning("Failed to convert date column to datetime")
        
        # Create a simple plot to verify data visually
        create_candlestick_plot(df, coin)
        
        return df
    except Exception as e:
        logger.error(f"Error testing OHLCV implementation: {str(e)}")
        return None

async def test_historical_data(coin="ONDO", days=30):
    """Test the underlying historical data fetch."""
    logger.info(f"Testing historical data fetch for {coin}, days={days}")
    
    try:
        # Create API instance
        api = CoinMarketCapAPI(project_name=coin)
        
        # Fetch historical data
        historical_data = await api.fetch_historical_data(coin, days)
        
        if not historical_data:
            logger.error("No historical data returned")
            return None
        
        logger.info(f"Historical data keys: {historical_data.keys()}")
        
        if "prices" in historical_data and "timestamps" in historical_data:
            logger.info(f"Found {len(historical_data['prices'])} price points")
            logger.info(f"Found {len(historical_data['timestamps'])} timestamps")
            
            # Display sample data
            if historical_data['timestamps'] and historical_data['prices']:
                logger.info(f"First timestamp: {historical_data['timestamps'][0]}")
                logger.info(f"First price: {historical_data['prices'][0]}")
                logger.info(f"Last timestamp: {historical_data['timestamps'][-1]}")
                logger.info(f"Last price: {historical_data['prices'][-1]}")
                
            return historical_data
        else:
            logger.error("Missing required fields in historical data")
            return None
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        return None

def create_candlestick_plot(df, coin_name):
    """Create a basic candlestick plot from OHLCV data."""
    try:
        # Sort data by date to ensure chronological order
        df = df.sort_values('date')
        
        # Create a figure and axis
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        # Format dates for x-axis
        date_format = DateFormatter('%Y-%m-%d')
        ax1.xaxis.set_major_formatter(date_format)
        
        # Calculate width of candlestick elements
        width = 0.6
        width2 = 0.3
        
        # Plot up and down candles separately
        up = df[df['close'] >= df['open']]
        down = df[df['close'] < df['open']]
        
        # Plot up candles
        ax1.bar(up.index, up['high'] - up['low'], width=width2, bottom=up['low'], color='green', alpha=0.5)
        ax1.bar(up.index, up['close'] - up['open'], width=width, bottom=up['open'], color='green')
        
        # Plot down candles
        ax1.bar(down.index, down['high'] - down['low'], width=width2, bottom=down['low'], color='red', alpha=0.5)
        ax1.bar(down.index, down['open'] - down['close'], width=width, bottom=down['close'], color='red')
        
        # Plot volume
        ax2.bar(df.index, df['volume'], color='blue', alpha=0.5)
        
        # Add labels and title
        ax1.set_title(f'{coin_name} Price - OHLCV Data')
        ax1.set_ylabel('Price (USD)')
        ax1.grid(True)
        ax2.set_ylabel('Volume')
        ax2.grid(True)
        
        # Set x-axis labels
        plt.xticks(rotation=45)
        
        # Adjust layout and save the plot
        plt.tight_layout()
        output_dir = "docs"
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, f"{coin_name.lower()}_ohlcv_test.png"))
        logger.info(f"Candlestick plot saved to {os.path.join(output_dir, f'{coin_name.lower()}_ohlcv_test.png')}")
        
        # Close the plot
        plt.close()
    except Exception as e:
        logger.error(f"Error creating candlestick plot: {str(e)}")

async def main():
    """Main function to run all tests."""
    # First test the historical data fetch
    historical_data = await test_historical_data()
    
    # Then test the OHLCV implementation
    ohlcv_data = await test_ohlcv_implementation()
    
    # Optionally test with Bitcoin as well
    # historical_data_btc = await test_historical_data("BTC")
    # ohlcv_data_btc = await test_ohlcv_implementation("BTC")

if __name__ == "__main__":
    asyncio.run(main()) 