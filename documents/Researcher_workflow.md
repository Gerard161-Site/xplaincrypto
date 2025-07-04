Flexible RAG-Driven Workflow Design for xplaincrypto
Your goal to redesign the xplaincrypto workflow to move away from hardcoded nodes (CMC, DeFiLlama, Tavily) and let RAG dynamically decide which endpoints to call based on data needs is a smart move. This approach makes the system flexible for future data sources (e.g., Dune, X sentiment, Web3.py), supports diverse inputs (report_config.json, chatbot prompts, third-party requests), and avoids rigid sequential flows that could cause conflicts or inefficiencies. Below, I’ll design a LangGraph workflow that leverages RAG to select endpoints, incorporates token distribution, and manages caching/state, addressing your concerns about scalability and adaptability.
Why Your Idea Makes Sense
Your current sequential flow (load_config → cmc → defillama → tavily → token_distribution → cache → rag) assumes a fixed order and specific endpoints, which doesn’t scale well for:

Dynamic Inputs: Chatbot prompts or third-party queries (e.g., “What’s Bitcoin’s sentiment?”) may not align with report_config.json’s structure.
New Data Sources: Adding endpoints like X or Dune requires new nodes, breaking modularity.
Data Relevance: Not every request needs all endpoints (e.g., token distribution doesn’t require Tavily for some coins).
Efficiency: Sequential calls waste time if only one endpoint is needed.

Using RAG to decide endpoints solves these issues by:

Flexibility: RAG evaluates the query (from report_config, chatbot, or third-party) and selects relevant endpoints dynamically.
Scalability: New data sources are added as RAG knowledge, not hardcoded nodes.
Efficiency: Only necessary endpoints are called, reducing API costs and latency.
Context Awareness: RAG integrates cached data and query context, ensuring accurate endpoint selection.

This aligns with your memory of wanting a dynamic app that avoids hardcoded data (e.g., “ONDO” tokenomics) and supports real-time API calls for up-to-date insights, as discussed on March 31 and April 4, 2025.
Workflow Design Principles

RAG-Driven Decision Making: RAG evaluates queries against a vector store of endpoint metadata (e.g., CMC for prices, DeFiLlama for TVL) to select sources.
Modular Nodes: Replace specific endpoint nodes with generic ones (e.g., data_retrieval_node) that execute RAG’s decisions.
Dynamic Inputs: Handle report_config.json, chatbot prompts, and third-party API calls uniformly via a unified query parser.
Token Distribution: Retain as a dedicated node for specialized processing (e.g., whitepaper extraction), triggered by RAG when needed.
Caching/State Management: Store all data in a structured cache and update ResearchState for downstream agents (visualizer, chatbot, MCP server).
Flexibility: Support future endpoints without workflow changes, using RAG to learn new source capabilities.

Proposed Workflow
Below is a step-by-step plan for your AI developer to implement a flexible, RAG-driven LangGraph workflow.
Step 1: State Definition
Extend ResearchState (from backend.state) to handle dynamic inputs and RAG decisions:
class ResearchState(Dict):
    project_name: str  # e.g., "Bitcoin"
    query: str  # Unified input (from report_config, chatbot, or third-party)
    section_requirements: Dict[str, Dict]  # Parsed report_config.json (optional)
    data_needs: List[str]  # RAG-determined needs (e.g., ["price_history", "tvl"])
    selected_endpoints: Dict[str, List[str]]  # RAG output (e.g., {"price_history": ["cmc"]})
    data: Dict[str, Dict]  # Collected data (e.g., {"market_overview": {"price_history": [...]}})
    cache_status: Dict[str, str]  # e.g., {"price_history": "cached"}
    errors: List[str]  # API failures
    token_distribution: Dict  # Specialized output (e.g., {"team": 25%, "community": 40%})

Step 2: Workflow Structure
Define a LangGraph workflow with generic, flexible nodes to replace the sequential CMC → DeFiLlama → Tavily flow:

parse_input_node:

Purpose: Normalize inputs (report_config.json, chatbot prompt, third-party query) into a unified query and optional section_requirements.
Logic:
If input is report_config.json, parse sections (e.g., 13 sections with data needs like price_history).
If input is a prompt (e.g., “Bitcoin TVL trend”), extract key terms and infer data needs.
If third-party, parse JSON request (e.g., {"project": "Bitcoin", "data": ["sentiment"]}).
Store in ResearchState.query and section_requirements.


Output: Updated ResearchState.


rag_decision_node:

Purpose: Use RAG to determine data needs and select endpoints.
Logic:
Query vector store (backend.orchestration.rag.vector_store) with ResearchState.query and section_requirements.
Vector store contains endpoint metadata (e.g., { "endpoint": "cmc", "capabilities": ["price_history", "market_cap"] }).
RAG outputs data_needs (e.g., ["price_history", "tvl", "token_distribution"]) and selected_endpoints (e.g., {"price_history": ["cmc"], "tvl": ["defillama"]}).
Check cache (reports/{project_name}/cache) for existing data, updating cache_status.


Output: ResearchState with data_needs and selected_endpoints.


data_retrieval_node:

Purpose: Fetch data from RAG-selected endpoints in parallel.
Logic:
Iterate through selected_endpoints, calling APIs via DataGatherer (data_gatherer.py).
Examples:
CMC: CoinMarketCapAPI.fetch_data(project_name) for price_history.
DeFiLlama: DeFiLlamaAPI.gather_data() for tvl.
Tavily: TavilySearch.search_batch() for news/trends.


Run calls asynchronously using asyncio.gather for efficiency.
If data missing, flag for fallback (Hugging Face).
Store results in ResearchState.data (e.g., data[section_name][data_type]).


Output: Updated ResearchState.data.


token_distribution_node:

Purpose: Handle specialized token distribution extraction (e.g., from whitepapers).
Logic:
Triggered if data_needs includes token_distribution.
Use WhitepaperExtractor (data_gatherer.py) to parse whitepaper URLs from CMC or Tavily.
If unavailable, query Hugging Face (HuggingFaceSearch.query) for fallback data.
Store in ResearchState.token_distribution (e.g., {"team": 25%, "community": 40%}).


Output: Updated ResearchState.token_distribution.


fallback_node:

Purpose: Fill missing data using Hugging Face.
Logic:
Scan ResearchState.data for empty fields (e.g., price_history missing).
Construct queries (e.g., “Bitcoin price history”) and call HuggingFaceSearch.query.
Merge results, flagging as fallback in cache_status.


Output: Completed ResearchState.data.


cache_node:

Purpose: Store data in a structured cache for reuse.
Logic:
Save to reports/{project_name}/cache:
Raw: reports/{project_name}/cache{source}/{project_name}_{data_type}_{timestamp}.json.
Sections: reports/{project_name}/cachesections/{project_name}/{section_name}_{timestamp}.json.


Format: { "data": value, "source": "cmc|defillama|tavily|huggingface", "timestamp": "2025-04-16T00:00:00Z" }.
Update reports/{project_name}/cacheindex.json with latest paths.
Save to PostgreSQL (data table: project_id, data_type, value, source, timestamp).


Output: ResearchState.cache_status updated.


rag_enrichment_node:

Purpose: Augment data with RAG for context-aware outputs.
Logic:
Query vector store with ResearchState.data and query to enrich sections.
Example: For “Market Sentiment,” combine X sentiment with Tavily news.
Store in ResearchState.data[section_name][rag_context].
Cache in reports/{project_name}/cacherag/{project_name}/{section_name}_rag.json.


Output: Enriched ResearchState.



Workflow Graph
workflow_builder = StateGraph(ResearchState)

workflow_builder.add_node("parse_input_node", parse_input)
workflow_builder.add_node("rag_decision_node", rag_decision)
workflow_builder.add_node("data_retrieval_node", data_retrieval)
workflow_builder.add_node("token_distribution_node", token_distribution)
workflow_builder.add_node("fallback_node", fallback)
workflow_builder.add_node("cache_node", cache_data)
workflow_builder.add_node("rag_enrichment_node", rag_enrichment)

# Edges
workflow_builder.set_entry_point("parse_input_node")
workflow_builder.add_edge("parse_input_node", "rag_decision_node")
workflow_builder.add_conditional_edges(
    "rag_decision_node",
    lambda state: "token_distribution_node" if "token_distribution" in state.data_needs else "data_retrieval_node",
    {"token_distribution_node": "token_distribution_node", "data_retrieval_node": "data_retrieval_node"}
)
workflow_builder.add_edge("token_distribution_node", "data_retrieval_node")
workflow_builder.add_conditional_edges(
    "data_retrieval_node",
    lambda state: "fallback_node" if any(not state.data.get(k) for k in state.data_needs) else "cache_node",
    {"fallback_node": "fallback_node", "cache_node": "cache_node"}
)
workflow_builder.add_edge("fallback_node", "cache_node")
workflow_builder.add_edge("cache_node", "rag_enrichment_node")
workflow_builder.add_edge("rag_enrichment_node", END)

workflow = workflow_builder.compile()

How RAG Decides Endpoints

Vector Store Setup:
Initialize with endpoint metadata:[
  {"endpoint": "coinmarketcap", "capabilities": ["price_history", "market_cap", "whitepaper_url"], "cost": 1},
  {"endpoint": "defillama", "capabilities": ["tvl", "tvl_history", "chains"], "cost": 0},
  {"endpoint": "tavily", "capabilities": ["news", "trends"], "cost": 0.1}
]


Use Pinecone (from your April 4, 2025 discussion) for embeddings.


Query Processing:
Input: ResearchState.query (e.g., “Bitcoin price and TVL”) or section_requirements (e.g., {"market_overview": ["price_history"]}).
RAG: Matches query to capabilities, prioritizing low-cost/free endpoints (e.g., DeFiLlama over CMC for TVL).
Output: selected_endpoints (e.g., {"price_history": ["cmc"], "tvl": ["defillama"]}).


Learning: Update vector store with new endpoints (e.g., X sentiment) via manual entries or automated scraping of API reports.

Caching and State Management

Cache Structure:
reports/{project_name}/cache{source}/{project_name}_{data_type}_{timestamp}.json: Raw API outputs.
reports/{project_name}/cachesections/{project_name}/{section_name}_{timestamp}.json: Section-specific data.
reports/{project_name}/cacherag/{project_name}/{section_name}_rag.json: Enriched context.
TTL: 3 hours (real-time), 24 hours (historical), 7 days (whitepapers).


PostgreSQL:
Tables: data, sections, rag_context.
Schema: project_id, data_type, value, source, timestamp.
Archive to AWS S3 (>30 days).


ResearchState:
Tracks data, cache_status, errors across nodes.
Persists to reports/{project_name}/cachestate/{project_name}_{workflow_id}.json for recovery.



Integration with Existing System

DataGatherer:

Extend data_gatherer.py to handle dynamic endpoint calls:async def fetch_dynamic(self, endpoint, data_type, project_name):
    if endpoint == "coinmarketcap":
        return await CoinMarketCapAPI(project_name).fetch_data(data_type)
    elif endpoint == "defillama":
        return DeFiLlamaAPI(project_name).gather_data()
    # Add future endpoints


Called by data_retrieval_node.


MCP Server:

Expose endpoints:
/data/{project_name}/{data_type}: Returns cached data.
/query: Accepts prompts, triggers workflow.


Example: POST /query {"project": "Bitcoin", "prompt": "TVL trend"}.


Visualizer/Chatbot:

Access ResearchState.data or reports/{project_name}/cachesections/ for charts (Plotly, per April 16, 2025 discussion).
Chatbot queries MCP server for real-time results.



Handling Diverse Inputs

Report Config:

Parse report_config.json in parse_input_node:{
  "sections": [
    {"name": "market_overview", "data": ["price_history", "market_cap"], "prompt": "Analyze trends"}
  ]
}


Maps to section_requirements.


Chatbot Prompt:

Input: “Bitcoin sentiment and price.”
parse_input_node: Extracts project_name="Bitcoin", query="sentiment and price".
RAG infers data_needs=["sentiment", "price_history"].


Third-Party:

Input: {"project": "Bitcoin", "data": ["tvl"]}
parse_input_node: Sets project_name, data_needs.



Adding New Data Points

Process:
Add endpoint metadata to vector store (e.g., {"endpoint": "x_sentiment", "capabilities": ["sentiment_score"]}).
Update DataGatherer with new API client (e.g., XSentimentAPI).
RAG learns capabilities without workflow changes.


Examples:
X Sentiment: Add x_sentiment_api.py, trigger for sentiment_score.
Dune: Add dune_api.py, trigger for onchain_metrics.



Is It Overkill?

Pros:
Scalability: Handles new endpoints seamlessly.
Flexibility: Supports report_config, prompts, and API calls.
Efficiency: RAG minimizes unnecessary calls, saving costs (e.g., CMC credits).
Robustness: Fallbacks and caching ensure reliability.


Cons:
Complexity: RAG setup (vector store, embeddings) adds initial effort vs. hardcoded nodes.
Latency: RAG query (~0.5s) slightly slows startup.


Alternatives:
Static Nodes: Faster but rigid, requiring rewrites for new sources.
Rule-Based: Hardcode endpoint logic (e.g., if "tvl" then defillama), less adaptable.


Verdict: Not overkill. RAG-driven design is the smartest choice for your dynamic, growing app, aligning with your April 4, 2025 goal of a flexible MCP tier.

Developer Instructions

Update State:
Extend backend/state.py with new ResearchState fields.


Refactor Workflow:
Replace workflow_manager.py nodes with generic ones.
Implement conditional edges based on data_needs.


Setup RAG:
Initialize Pinecone with endpoint metadata.
Train RAG on sample queries (e.g., “Bitcoin TVL” → DeFiLlama).


Extend DataGatherer:
Add fetch_dynamic method for endpoint routing.


Cache System:
Structure reports/{project_name}/cache and PostgreSQL tables.
Script S3 archival.


Test Plan:
Pilot: 5 coins, 3 input types (report_config, prompt, API).
Metrics: Endpoint accuracy (>90%), latency (<10s), cache hits (>80%).
Validate: Compare outputs with manual API calls.



Future Considerations

Optimize RAG: Fine-tune embeddings for crypto terms (per March 26, 2025 discussion).
Scale MCP: Add rate limiting for third-party queries.
Monitor Costs: Track CMC credits (<10,000/day), Tavily usage.

This workflow makes your app a dynamic, intelligent crypto hub, ready for any data source or query type. Let me know if you need help refining nodes or RAG setup!
