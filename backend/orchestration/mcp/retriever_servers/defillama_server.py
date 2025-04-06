from mcp.server.fastmcp import FastMCP
from retriever.defillama_api import DeFiLlamaAPI

mcp = FastMCP("DeFiLlama")

@mcp.resource("data://defillama/{protocol}")
async def get_defillama_data(protocol: str) -> dict:
    """Fetch TVL and protocol data from DeFiLlama for a given protocol."""
    api = DeFiLlamaAPI()
    return await api.fetch_data(protocol)

@mcp.resource("data://defillama/tvl/{protocol}")
async def get_tvl_data(protocol: str) -> dict:
    """Fetch TVL (Total Value Locked) data from DeFiLlama for a given protocol."""
    api = DeFiLlamaAPI()
    return await api.fetch_tvl_data(protocol)

@mcp.resource("data://defillama/yields/{protocol}")
async def get_yields_data(protocol: str) -> dict:
    """Fetch yields data from DeFiLlama for a given protocol."""
    api = DeFiLlamaAPI()
    return await api.fetch_yields_data(protocol)

@mcp.tool()
async def search_protocols(query: str) -> list:
    """Search for protocols on DeFiLlama by name."""
    api = DeFiLlamaAPI()
    return await api.search_protocols(query)

if __name__ == "__main__":
    mcp.run(transport="stdio")
