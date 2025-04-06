from mcp.server.fastmcp import FastMCP
from retriever.coingecko_api import CoinGeckoAPI

mcp = FastMCP("CoinGecko")

@mcp.resource("data://coingecko/{coin}")
async def get_coingecko_data(coin: str) -> dict:
    """Fetch real-time data from CoinGecko for a given coin."""
    api = CoinGeckoAPI()
    return await api.fetch_data(coin)

@mcp.resource("data://coingecko/market/{coin}")
async def get_market_data(coin: str) -> dict:
    """Fetch market data from CoinGecko for a given coin."""
    api = CoinGeckoAPI()
    return await api.fetch_market_data(coin)

@mcp.resource("data://coingecko/price/{coin}")
async def get_price_data(coin: str) -> dict:
    """Fetch price data from CoinGecko for a given coin."""
    api = CoinGeckoAPI()
    return await api.fetch_price_data(coin)

@mcp.tool()
async def search_coins(query: str) -> list:
    """Search for coins on CoinGecko by name or symbol."""
    api = CoinGeckoAPI()
    return await api.search_coins(query)

if __name__ == "__main__":
    mcp.run(transport="stdio")
