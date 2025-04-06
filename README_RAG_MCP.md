# RAG > MCP Tier Integration for XplainCrypto

This README provides an overview of the implementation of the RAG > MCP tier for the XplainCrypto project.

## Overview

The RAG > MCP tier integration enhances the XplainCrypto project by adding a Retrieval-Augmented Generation (RAG) layer with Model Context Protocol (MCP) to standardize the interface between agents and retriever services. This implementation follows the architecture outlined in the MCP plan document.

## Key Features

- **RAG with Pinecone**: Uses Pinecone vector store to store metadata about MCP endpoints and intelligently route queries
- **MCP Servers**: Implements MCP servers for each retriever service (CoinGecko, CoinMarketCap, DeFiLlama, Tavily, HuggingFace)
- **LangGraph Integration**: Integrates the RAG > MCP tier with the existing LangGraph workflow
- **Enhanced Researcher**: Extends the Enhanced Researcher agent with MCP capabilities
- **API Endpoints**: Provides FastAPI endpoints for interacting with the MCP-enabled workflow

## Directory Structure

```
backend/
├── orchestration/
│   ├── rag/
│   │   ├── vector_store.py  # Pinecone vector store integration
│   │   └── retriever.py     # RAG retriever with LLM decision-making
│   └── mcp/
│       ├── client_manager.py                # MCP client lifecycle management
│       ├── router.py                        # MCP endpoint routing
│       └── retriever_servers/               # MCP servers for retriever services
│           ├── coingecko_server.py
│           ├── coinmarketcap_server.py
│           ├── defillama_server.py
│           ├── tavily_server.py
│           └── huggingface_server.py
├── agent/
│   ├── mcp_integration.py         # Basic MCP-LangGraph integration
│   ├── enhanced_researcher_mcp.py # Enhanced Researcher with MCP
│   └── workflow_manager_mcp.py    # Workflow manager with MCP integration
└── api/
    └── mcp_api.py                 # FastAPI endpoints for MCP integration
tests/
├── test_mcp_integration.py        # Unit tests for MCP integration
└── test_mcp_api.py                # API tests for MCP endpoints
docs/
└── rag_mcp_integration.md         # Detailed documentation
```

## Getting Started

### Prerequisites

- Python 3.10+
- Pinecone account (for vector store)
- OpenAI API key (for LLM)

### Environment Variables

Set the following environment variables:

```bash
export PINECONE_API_KEY=your_pinecone_api_key
export OPENAI_API_KEY=your_openai_api_key
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Gerard161-Site/xplaincrypto.git
cd xplaincrypto
git checkout rag-mcp-integration
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the API:
```bash
uvicorn backend.api.mcp_api:app --host 0.0.0.0 --port 8000
```

### Usage

#### API Endpoints

- `POST /api/research`: Execute the research workflow for a given query
- `GET /api/tools`: Get all available tools from the MCP servers
- `POST /api/execute-tool`: Execute a specific MCP tool

#### Example API Request

```python
import requests

# Execute research workflow
response = requests.post(
    "http://localhost:8000/api/research",
    json={"query": "What is the price of Bitcoin?", "context": {}}
)
print(response.json())
```

## Documentation

For detailed documentation, see [rag_mcp_integration.md](docs/rag_mcp_integration.md).

## Testing

Run the tests with pytest:

```bash
pytest tests/
```

## Future Enhancements

- Add more retriever services
- Implement more sophisticated routing logic
- Integrate with other LangGraph agents
- Add support for more transport types
- Implement caching for improved performance

## License

This project is licensed under the MIT License - see the LICENSE file for details.
