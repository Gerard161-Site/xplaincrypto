from mcp.server.fastmcp import FastMCP
from retriever.tavily_search import TavilySearch

mcp = FastMCP("Tavily")

@mcp.resource("research://tavily/{query}")
async def get_tavily_search_results(query: str) -> dict:
    """Perform web research using Tavily for a given query."""
    api = TavilySearch()
    return await api.search(query)

@mcp.resource("research://tavily/news/{query}")
async def get_tavily_news(query: str) -> dict:
    """Fetch recent news using Tavily for a given query."""
    api = TavilySearch()
    return await api.search_news(query)

@mcp.tool()
async def search_with_filters(query: str, search_depth: str = "basic", include_domains: list = None, exclude_domains: list = None) -> dict:
    """
    Perform advanced search with Tavily using filters.
    
    Args:
        query: The search query
        search_depth: Either "basic" or "comprehensive"
        include_domains: List of domains to include in search results
        exclude_domains: List of domains to exclude from search results
    """
    api = TavilySearch()
    return await api.advanced_search(
        query=query,
        search_depth=search_depth,
        include_domains=include_domains or [],
        exclude_domains=exclude_domains or []
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")
