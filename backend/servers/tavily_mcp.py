from mcp.server.fastmcp import FastMCP
import aiohttp
import logging
import os
import json
import asyncio
import uvicorn
from typing import Dict, Any, Optional, List, Union, Sequence, Literal

logger = logging.getLogger("TavilyMCP")
mcp = FastMCP("Tavily")

# Default project name if none is specifically passed to a tool/resource that might use it for internal logic
# However, for a standalone MCP, this is less relevant as caching is removed from this layer.
DEFAULT_PROJECT_NAME = "general_tavily_mcp_usage"

class TavilyApiClient:
    """
    Asynchronous client for the Tavily Search API.
    This class is adapted from the original TavilySearch, focusing on API interaction
    without its own caching layer (caching should be handled by the caller or not at all
    for a standalone server if direct passthrough is desired).
    """
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.headers = {"Content-Type": "application/json"}
        if not self.api_key:
            logger.error("TAVILY_API_KEY not found. Tavily API calls will fail.")
            # No fallback key here; calls will fail without a key.

    async def _search_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Internal method to make the search POST request to Tavily API."""
        if not self.api_key:
            return {"error": "Tavily API key is not configured.", "results": []}

        payload["api_key"] = self.api_key # Add API key to each request
        logger.debug(f"Executing Tavily search with payload: {json.dumps(payload)[:200]}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.BASE_URL, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=100)) as response:
                    logger.info(f"Tavily API response status: {response.status} for query: {payload.get('query')}")
                    if response.status == 200:
                        return await response.json()
                    else:
                        response_text = await response.text()
                        logger.warning(f"Tavily API error: {response.status} - {response_text} for query: {payload.get('query')}")
                        return {"results": [], "error": f"Tavily API error: {response.status} - {response_text}"}
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Tavily connection error: {str(e)} for query: {payload.get('query')}")
            return {"results": [], "error": f"Tavily connection error: {str(e)}"}
        except asyncio.TimeoutError:
            logger.warning(f"Tavily request timed out for query: {payload.get('query')}")
            return {"results": [], "error": "Tavily request timed out"}
        except Exception as e:
            logger.error(f"Async Tavily search failed: {str(e)} ({type(e).__name__}) for query: {payload.get('query')}")
            return {"results": [], "error": f"Tavily search failed: {str(e)}"}

    async def search(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        topic: str = "general",
        days: Optional[int] = None, # Tavily API uses `max_days_back`
        max_results: int = 5,
        include_domains: Optional[Sequence[str]] = None,
        exclude_domains: Optional[Sequence[str]] = None,
        include_answer: bool = False,
        include_raw_content: bool = False,
        include_images: bool = False
    ) -> Dict[str, Any]:
        """Performs a search using the Tavily API."""
        payload = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        if days is not None: # Map 'days' to 'max_days_back' if Tavily uses that
            payload["max_days_back"] = days 
            # Or if Tavily uses 'days' directly, then payload["days"] = days

        return await self._search_request(payload)

    async def research(self, query: str) -> Dict[str, Any]:
        """
        Performs an advanced research search using Tavily.
        This typically involves setting search_depth to "advanced" and including answers/raw_content.
        """
        logger.info(f"Performing Tavily research for query: {query}")
        return await self.search(
            query=query,
            search_depth="advanced",
            max_results=7, # Typically want more results for research
            include_answer=True,
            include_raw_content=True,
            include_images=False # Usually not needed for text-based research synthesis
        )

# --- MCP Resources ---
@mcp.resource("data://tavily/search/{query}")
async def search_web_mcp(query: str) -> Dict[str, Any]:
    """Perform a basic web search using Tavily."""
    client = TavilyApiClient()
    # Default to a basic search, can be made configurable via query params if MCP supports it
    return await client.search(query=query, search_depth="basic", max_results=5)

@mcp.resource("data://tavily/research/{query}")
async def research_web_mcp(query: str) -> Dict[str, Any]:
    """Perform an advanced/research-oriented web search using Tavily."""
    client = TavilyApiClient()
    return await client.research(query=query)


# --- MCP Tools ---
@mcp.tool("search") # Explicitly name tool to match common usage
async def tavily_search_tool(
    query: str,
    search_depth: Literal["basic", "advanced"] = "basic",
    max_results: int = 5,
    include_answer: bool = False,
    topic: str = "general",
    days_back: Optional[int] = None,
    include_raw_content: bool = False
) -> Dict[str, Any]:
    """
    Tool to perform a web search using Tavily API.
    Args:
        query: The search query string.
        search_depth: "basic" or "advanced". Advanced is more comprehensive.
        max_results: Number of search results to return.
        include_answer: Whether to include a direct answer to the query, if available.
        topic: Topic focus for the search (e.g., "finance", "news"). Defaults to "general".
        days_back: Restrict search to results from the last N days.
        include_raw_content: Whether to include raw content of search results.
    Returns:
        A dictionary containing search results or an error.
    """
    logger.info(f"Tool 'tavily_search_tool' called with query: {query}")
    client = TavilyApiClient()
    return await client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        include_answer=include_answer,
        topic=topic,
        days=days_back, # maps to max_days_back in client
        include_raw_content=include_raw_content
    )

@mcp.tool("research") # Explicitly name to match common usage for research tasks
async def tavily_research_tool(query: str) -> Dict[str, Any]:
    """
    Tool to perform an in-depth research search on a topic using Tavily's advanced capabilities.
    Args:
        query: The research query string.
    Returns:
        A dictionary containing comprehensive research results or an error.
    """
    logger.info(f"Tool 'tavily_research_tool' called with query: {query}")
    client = TavilyApiClient()
    return await client.research(query=query)

async def run_mcp_server(port: int):
    """
    Run the MCP server with Uvicorn on the specified port.
    """
    config = uvicorn.Config(app=mcp.get_asgi_app(), host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    import selectors
    selectors.DefaultSelector = selectors.PollSelector
    print("Entered main block", flush=True)
    logger.info("Entered main block")
    logger.info("Starting Tavily MCP server with stdio")
    print("Starting Tavily MCP server with stdio", flush=True)
    try:
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        logger.debug("New event loop set")
        print("New event loop set", flush=True)
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        logger.debug("Calling mcp.run with stdio")
        print("Calling mcp.run with stdio", flush=True)
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"Error in mcp.run: {str(e)}")
            print(f"Error in mcp.run: {str(e)}", flush=True)
            raise
        logger.debug("MCP server running")
        print("MCP server running", flush=True)
    except Exception as e:
        logger.error(f"Error in mcp.run: {str(e)}")
        print(f"Error in mcp.run: {str(e)}", flush=True)
        raise