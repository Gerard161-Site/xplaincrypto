from mcp.server.fastmcp import FastMCP
from retriever.coinmarketcap_api import CoinMarketCapAPI

mcp = FastMCP("CoinMarketCap")

@mcp.resource("data://coinmarketcap/{coin}")
async def get_coinmarketcap_data(coin: str) -> dict:
    """Fetch comprehensive data from CoinMarketCap for a given coin."""
    api = CoinMarketCapAPI()
    return await api.fetch_data(coin)

@mcp.resource("data://coinmarketcap/market/{coin}")
async def get_market_data(coin: str) -> dict:
    """Fetch market cap and supply data from CoinMarketCap for a given coin."""
    api = CoinMarketCapAPI()
    return await api.fetch_market_data(coin)

@mcp.resource("data://coinmarketcap/price/{coin}")
async def get_price_data(coin: str) -> dict:
    """Fetch price and volume data from CoinMarketCap for a given coin."""
    api = CoinMarketCapAPI()
    return await api.fetch_price_data(coin)

@mcp.tool()
async def search_coins(query: str) -> list:
    """Search for coins on CoinMarketCap by name or symbol."""
    api = CoinMarketCapAPI()
    return await api.search_coins(query)

if __name__ == "__main__":
    mcp.run(transport="stdio")
