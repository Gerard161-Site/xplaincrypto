import os
import sys
import aiohttp
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()

async def test_coinmarketcap():
    print("\n=== Testing CoinMarketCap API ===")
    api_key = os.getenv("COINMARKETCAP_API_KEY")
    if not api_key:
        print("❌ COINMARKETCAP_API_KEY not found in environment variables")
        return False
    
    print(f"✅ COINMARKETCAP_API_KEY found (length: {len(api_key)})")
    
    enabled = os.getenv("COINMARKETCAP_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
    print(f"{'✅' if enabled else '❌'} COINMARKETCAP_ENABLED: {enabled}")
    
    if not enabled:
        print("⚠️ CoinMarketCap API is disabled. Enable it by setting COINMARKETCAP_ENABLED=true")
        return False
    
    # Test endpoint: /v1/cryptocurrency/map to find a specific symbol
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
    headers = {
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json"
    }
    params = {
        "symbol": "ONDO"  # Test with ONDO token
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                print(f"📡 API Request to: {url}?symbol=ONDO")
                print(f"📊 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and isinstance(data['data'], list):
                        print(f"✅ Found {len(data['data'])} results for ONDO")
                        for coin in data['data'][:3]:  # Show up to 3 results
                            print(f"   - {coin.get('name')} (ID: {coin.get('id')}, Symbol: {coin.get('symbol')})")
                        return True
                    else:
                        print(f"❌ Unexpected response format: {data.get('status', {}).get('error_message', 'Unknown error')}")
                else:
                    error = await response.text()
                    print(f"❌ API Error: {error}")
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

async def test_coingecko():
    print("\n=== Testing CoinGecko API ===")
    api_key = os.getenv("COINGECKO_API_KEY")
    if not api_key:
        print("❌ COINGECKO_API_KEY not found in environment variables")
        return False
    
    print(f"✅ COINGECKO_API_KEY found (length: {len(api_key)})")
    
    enabled = os.getenv("COINGECKO_ENABLED", "true").lower() in ["true", "1", "yes", "y"]
    print(f"{'✅' if enabled else '❌'} COINGECKO_ENABLED: {enabled}")
    
    if not enabled:
        print("⚠️ CoinGecko API is disabled. Enable it by setting COINGECKO_ENABLED=true")
        return False
    
    # Test endpoint: /search to find a specific token
    url = "https://api.coingecko.com/api/v3/search"
    headers = {
        "x-cg-demo-api-key": api_key
    }
    params = {
        "query": "ondo finance"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                print(f"📡 API Request to: {url}?query=ondo+finance")
                print(f"📊 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    if 'coins' in data:
                        coins = data['coins']
                        print(f"✅ Found {len(coins)} results for 'ondo finance'")
                        for coin in coins[:3]:  # Show up to 3 results
                            print(f"   - {coin.get('name')} (ID: {coin.get('id')}, Symbol: {coin.get('symbol')})")
                        return True
                    else:
                        print(f"❌ Unexpected response format: {data}")
                else:
                    error = await response.text()
                    print(f"❌ API Error: {error}")
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

async def test_coinmarketcap_ohlcv():
    print("\n=== Testing CoinMarketCap OHLCV Data ===")
    api_key = os.getenv("COINMARKETCAP_API_KEY")
    if not api_key:
        print("❌ COINMARKETCAP_API_KEY not found in environment variables")
        return False
    
    # First, find the coin ID
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
    headers = {
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json"
    }
    params = {
        "symbol": "ONDO"
    }
    
    coin_id = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                        coin_id = data['data'][0]['id']
                        print(f"✅ Found coin ID for ONDO: {coin_id}")
                    else:
                        print("❌ Failed to find ONDO coin ID")
                        return False
                else:
                    error = await response.text()
                    print(f"❌ API Error finding coin ID: {error}")
                    return False
    except Exception as e:
        print(f"❌ Exception finding coin ID: {str(e)}")
        return False
    
    # Now get the OHLCV data
    url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/ohlcv/historical"
    params = {
        "id": coin_id,
        "convert": "USD",
        "count": 30  # Last 30 days
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=10) as response:
                print(f"📡 API Request to: {url}?id={coin_id}&convert=USD&count=30")
                print(f"📊 Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and str(coin_id) in data['data']:
                        quotes = data['data'][str(coin_id)]['quotes']
                        print(f"✅ Found {len(quotes)} OHLCV data points for ONDO")
                        
                        # Format as OHLCV format for our candlestick charts
                        ohlcv = []
                        for quote in quotes:
                            time_open = quote.get('time_open')
                            ohlcv.append({
                                'date': time_open,
                                'open': quote.get('quote', {}).get('USD', {}).get('open'),
                                'high': quote.get('quote', {}).get('USD', {}).get('high'),
                                'low': quote.get('quote', {}).get('USD', {}).get('low'),
                                'close': quote.get('quote', {}).get('USD', {}).get('close'),
                                'volume': quote.get('quote', {}).get('USD', {}).get('volume')
                            })
                        
                        # Print the first few data points
                        print("Sample OHLCV data:")
                        for point in ohlcv[:3]:
                            print(f"   - {point['date']}: Open ${point['open']:.4f}, Close ${point['close']:.4f}, Volume ${point['volume']:.2f}")
                        
                        return True
                    else:
                        print(f"❌ Unexpected response format: {data.get('status', {}).get('error_message', 'Unknown error')}")
                else:
                    error = await response.text()
                    print(f"❌ API Error: {error}")
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

async def main():
    # Create a horizontal line for better readability
    print("\n" + "="*50)
    print(" API CONNECTIVITY TEST ".center(50, "="))
    print("="*50)
    
    # Test each API
    cmc_success = await test_coinmarketcap()
    cg_success = await test_coingecko()
    ohlcv_success = await test_coinmarketcap_ohlcv()
    
    # Print summary
    print("\n" + "="*50)
    print(" SUMMARY ".center(50, "="))
    print("="*50)
    print(f"CoinMarketCap API:    {'✅ WORKING' if cmc_success else '❌ FAILED'}")
    print(f"CoinGecko API:        {'✅ WORKING' if cg_success else '❌ FAILED'}")
    print(f"OHLCV Data:           {'✅ WORKING' if ohlcv_success else '❌ FAILED'}")
    print("="*50)
    
    # Suggest fixes
    if not cg_success and os.getenv("COINGECKO_ENABLED") == "false":
        print("\n⚠️ To fix CoinGecko: Set COINGECKO_ENABLED=true in your .env file")
    
    if not cmc_success and os.getenv("COINMARKETCAP_ENABLED") != "true":
        print("\n⚠️ To fix CoinMarketCap: Ensure COINMARKETCAP_ENABLED=true in your .env file")
    
    if not ohlcv_success:
        print("\n⚠️ To fix OHLCV data: Check CoinMarketCap API rate limits or try again later")
    
    if not any([cmc_success, cg_success]):
        print("\n❌ ERROR: All cryptocurrency data APIs are failing")
        print("Without API data, visualizations cannot be generated properly.")
        print("Please fix the API connectivity issues above.")
    
if __name__ == "__main__":
    asyncio.run(main()) 