# RAG > MCP Integration for XplainCrypto

This document provides an overview of the RAG > MCP tier integration for the XplainCrypto project.

## Architecture Overview

The enhanced architecture introduces a new RAG > MCP tier that acts as an intermediary between the agent layer and retriever services. This tier uses Retrieval-Augmented Generation (RAG) with Pinecone to store metadata about available Model Context Protocol (MCP) endpoints and route queries to the appropriate services.

### Key Components

1. **RAG Layer**
   - `VectorStore`: Manages the Pinecone vector store for storing and retrieving MCP endpoint metadata
   - `RAGRetriever`: Uses the vector store and LLM to determine which MCP endpoints to call for a given query

2. **MCP Layer**
   - `MCPClientManager`: Manages the lifecycle of MCP server processes and client connections
   - `MCPRouter`: Orchestrates the interaction between the RAG retriever and MCP clients
   - MCP Servers: Lightweight servers for each retriever service (CoinGecko, CoinMarketCap, DeFiLlama, Tavily, HuggingFace)

3. **Integration Layer**
   - `MCPLangGraphIntegration`: Connects the RAG > MCP tier with LangGraph
   - `EnhancedResearcherWithMCP`: Extends the Enhanced Researcher agent with MCP capabilities
   - `WorkflowManagerWithMCP`: Integrates the MCP-enabled agents into the existing workflow

4. **API Layer**
   - `mcp_api.py`: Provides FastAPI endpoints for interacting with the MCP-enabled workflow

## Directory Structure

```
backend/
├── orchestration/
│   ├── rag/
│   │   ├── vector_store.py
│   │   └── retriever.py
│   └── mcp/
│       ├── client_manager.py
│       ├── router.py
│       └── retriever_servers/
│           ├── coingecko_server.py
│           ├── coinmarketcap_server.py
│           ├── defillama_server.py
│           ├── tavily_server.py
│           └── huggingface_server.py
├── agent/
│   ├── mcp_integration.py
│   ├── enhanced_researcher_mcp.py
│   └── workflow_manager_mcp.py
└── api/
    └── mcp_api.py
tests/
├── test_mcp_integration.py
└── test_mcp_api.py
```

## Implementation Details

### RAG Layer

The RAG layer uses Pinecone as a vector store to store metadata about available MCP endpoints. When a query is received, the RAG retriever uses the vector store to find the most relevant endpoints and then uses an LLM to decide which endpoints to call.

#### VectorStore

The `VectorStore` class provides methods for:
- Initializing a Pinecone index
- Upserting endpoint metadata
- Querying for relevant endpoints

```python
# Example usage
vector_store = get_vector_store()
vector_store.upsert_endpoint("coingecko", "CoinGecko API for cryptocurrency data")
endpoints = vector_store.query("What is the price of Bitcoin?")
```

#### RAGRetriever

The `RAGRetriever` class uses the vector store and an LLM to determine which endpoints to call for a given query.

```python
# Example usage
retriever = RAGRetriever(vector_store)
endpoints = await retriever.process_query("What is the price of Bitcoin?")
```

### MCP Layer

The MCP layer consists of MCP servers for each retriever service, a client manager, and a router.

#### MCP Servers

Each retriever service has its own MCP server that exposes resources and tools. For example, the CoinGecko server exposes resources for fetching coin data and tools for searching coins.

```python
# Example server
mcp = FastMCP("CoinGecko")

@mcp.resource("data://coingecko/{coin}")
async def get_coingecko_data(coin: str) -> dict:
    """Fetch real-time data from CoinGecko for a given coin."""
    api = CoinGeckoAPI()
    return await api.fetch_data(coin)
```

#### MCPClientManager

The `MCPClientManager` class manages the lifecycle of MCP server processes and client connections. It provides methods for:
- Starting and stopping server processes
- Creating clients connected to multiple servers
- Getting tools from servers

```python
# Example usage
client_manager = MCPClientManager()
async with client_manager.create_client(["coingecko", "tavily"]) as client:
    tools = client.get_tools()
```

#### MCPRouter

The `MCPRouter` class orchestrates the interaction between the RAG retriever and MCP clients. It provides methods for:
- Initializing the vector store with endpoint metadata
- Routing queries to the appropriate MCP endpoints
- Executing specific tools

```python
# Example usage
router = MCPRouter(vector_store)
await router.initialize_endpoints()
tools = await router.route_query("What is the price of Bitcoin?")
```

### Integration Layer

The integration layer connects the RAG > MCP tier with the existing LangGraph workflow.

#### MCPLangGraphIntegration

The `MCPLangGraphIntegration` class provides a basic integration between MCP and LangGraph. It creates a simple workflow that gets tools for a query and returns them.

#### EnhancedResearcherWithMCP

The `EnhancedResearcherWithMCP` class extends the Enhanced Researcher agent with MCP capabilities. It creates a LangGraph workflow that:
1. Gets tools for a query using the MCP router
2. Creates an agent with those tools
3. Runs the agent to answer the query

```python
# Example usage
researcher = EnhancedResearcherWithMCP()
await researcher.initialize()
result = await researcher.execute_workflow("What is the price of Bitcoin?")
```

#### WorkflowManagerWithMCP

The `WorkflowManagerWithMCP` class integrates the MCP-enabled agents into the existing workflow. It provides methods for:
- Initializing all components of the workflow
- Executing the research workflow
- Getting available tools
- Executing specific tools

```python
# Example usage
manager = WorkflowManagerWithMCP()
await manager.initialize()
result = await manager.execute_research_workflow("What is the price of Bitcoin?")
```

### API Layer

The API layer provides FastAPI endpoints for interacting with the MCP-enabled workflow.

#### mcp_api.py

The `mcp_api.py` file defines FastAPI endpoints for:
- Executing the research workflow
- Getting available tools
- Executing specific tools

```python
# Example endpoint
@app.post("/api/research", response_model=ApiResponse)
async def execute_research(request: ResearchRequest):
    """Execute the research workflow for a given query."""
    try:
        result = await workflow_manager.execute_research_workflow(request.query, request.context)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, data=None, error=str(e))
```

## Testing

The implementation includes comprehensive tests for all components of the RAG > MCP tier.

### Unit Tests

The `test_mcp_integration.py` file contains unit tests for:
- The RAG retriever
- The MCP router
- The Enhanced Researcher with MCP
- The Workflow Manager with MCP

### API Tests

The `test_mcp_api.py` file contains tests for the FastAPI endpoints:
- The research endpoint
- The tools endpoint
- The execute tool endpoint
- Error handling

## Usage

To use the RAG > MCP tier in your application:

1. Initialize the workflow manager:
```python
manager = WorkflowManagerWithMCP()
await manager.initialize()
```

2. Execute the research workflow:
```python
result = await manager.execute_research_workflow("What is the price of Bitcoin?")
```

3. Get available tools:
```python
tools = manager.get_available_tools()
```

4. Execute a specific tool:
```python
result = await manager.execute_tool("coingecko_search_coins", query="bitcoin")
```

## Environment Variables

The following environment variables are required:
- `PINECONE_API_KEY`: API key for Pinecone
- `OPENAI_API_KEY`: API key for OpenAI (used for LLM)

## Future Enhancements

Potential future enhancements to the RAG > MCP tier include:
- Adding more retriever services
- Implementing more sophisticated routing logic
- Integrating with other LangGraph agents (Writer, Visualization Agent, etc.)
- Adding support for more transport types (SSE, WebSockets, etc.)
- Implementing caching for improved performance
