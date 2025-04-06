import os
import json
import logging
import re
import datetime
import asyncio
from typing import Dict, List, Any, Optional, Callable, Annotated, Sequence, TypedDict, cast

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_react_agent
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Custom imports
from backend.state import ResearchState
from backend.research.core import ResearchNode, ResearchType
from backend.research.orchestrator import ResearchOrchestrator
from backend.retriever.huggingface_search import HuggingFaceSearch
from backend.retriever.data_gatherer import DataGatherer
from backend.utils.logging_utils import log_safe
from backend.utils.json_encoder import dump_with_custom_encoder
from dotenv import load_dotenv

# Conditionally import MCP components
try:
    from backend.orchestration.mcp.router import MCPRouter
    from backend.orchestration.rag.vector_store import get_vector_store
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

load_dotenv()

# Load API tokens
hf_api_token = os.environ.get("HUGGINGFACE_API_KEY")

# Cache configuration
CACHE_DIR = os.path.join("docs", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_filename(project_name: str) -> str:
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', project_name.lower())
    return os.path.join(CACHE_DIR, f"{safe_name}_research.json")

# Define AgentState for MCP workflow
class AgentState(TypedDict):
    """State for the agent workflow."""
    query: str
    tools: List[BaseTool]
    messages: Annotated[Sequence, "Messages between human and AI"]
    context: Dict[str, Any]
    agent_outcome: Any
    project_name: str

class Researcher:
    """
    Unified Researcher agent that can use either classic or MCP-enhanced workflows.
    
    This class combines the functionality of enhanced_researcher.py and enhanced_researcher_mcp.py
    to provide a single interface for research.
    """
    
    def __init__(self, llm_model: str = "gpt-4o", use_mcp: bool = None, logger: logging.Logger = None):
        """
        Initialize the researcher.
        
        Args:
            llm_model: The LLM model to use
            use_mcp: Whether to use MCP. If None, uses USE_MCP environment variable
            logger: Logger to use. If None, creates a new logger
        """
        # Set up logger
        self.logger = logger or logging.getLogger(__name__)
        
        # Determine whether to use MCP
        if use_mcp is None:
            self.use_mcp = os.environ.get("USE_MCP", "false").lower() == "true"
        else:
            self.use_mcp = use_mcp and MCP_AVAILABLE
            
        # Initialize LLM
        self.llm = ChatOpenAI(model=llm_model, api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Initialize MCP components if using MCP
        if self.use_mcp and MCP_AVAILABLE:
            self.logger.info("Initializing with MCP components")
            self.vector_store = get_vector_store()
            self.router = MCPRouter(self.vector_store)
            
            # Create compiled MCP workflow (initialize on first use)
            self._compiled_mcp_workflow = None
        else:
            if self.use_mcp and not MCP_AVAILABLE:
                self.logger.warning("MCP requested but components not available. Falling back to classic mode.")
            self.use_mcp = False
            self.logger.info("Initializing in classic mode")
    
    async def initialize(self):
        """Initialize components, particularly MCP endpoints if using MCP."""
        if self.use_mcp and MCP_AVAILABLE:
            try:
                await self.router.initialize_endpoints()
                self.logger.info("MCP endpoints initialized successfully")
            except Exception as e:
                self.logger.error(f"Error initializing MCP endpoints: {str(e)}")
                # Fall back to classic mode if MCP initialization fails
                self.use_mcp = False
    
    async def execute_workflow(self, query_or_state: Dict[str, Any] | str, context: Dict[str, Any] = None, 
                               llm: ChatOpenAI = None, logger: logging.Logger = None, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the research workflow.
        
        This is a unified entry point that handles both classic mode and MCP mode.
        In classic mode, it expects state, llm, logger, and config arguments.
        In MCP mode, it expects query and context arguments.
        
        Args:
            query_or_state: Either a query string (MCP mode) or state dict (classic mode)
            context: Additional context for MCP mode
            llm: LLM to use in classic mode
            logger: Logger to use in classic mode
            config: Config to use in classic mode
            
        Returns:
            The result of the workflow execution
        """
        # Use provided logger or instance logger
        effective_logger = logger or self.logger
        
        # Determine the execution mode
        use_mcp = self.use_mcp and MCP_AVAILABLE
        
        # If query is a string, use MCP mode (preferred)
        if isinstance(query_or_state, str):
            if use_mcp:
                effective_logger.info(f"Executing MCP workflow for query: {query_or_state}")
                result = await self._execute_mcp_workflow(query_or_state, context or {})
                return result
            else:
                # Convert string query to state dict for classic mode
                error_msg = "MCP mode requested but not available. Using string query with classic mode."
                effective_logger.warning(error_msg)
                project_name = "Unknown Project"
                if context and "project_name" in context:
                    project_name = context["project_name"]
                query = query_or_state
                return {
                    "project_name": project_name,
                    "draft": f"# {project_name}\n\n{query}\n\nMCP mode not available. Please provide direct API access.",
                    "errors": [error_msg],
                    "progress": error_msg
                }
        
        # If state is a dict, use classic or MCP mode based on configuration
        elif isinstance(query_or_state, dict):
            state = query_or_state
            project_name = state.get("project_name", "")
            
            # Try to use MCP mode if enabled even with state dict
            if use_mcp and project_name:
                try:
                    # Create a query from project name
                    query = f"Provide comprehensive research about {project_name} cryptocurrency"
                    effective_logger.info(f"Converting state to MCP query: {query}")
                    
                    # Execute MCP workflow with the query
                    mcp_result = await self._execute_mcp_workflow(query, {"project_name": project_name})
                    
                    # Merge relevant parts of MCP result with original state for backward compatibility
                    for key in ["draft", "web_research", "progress"]:
                        if key in mcp_result:
                            state[key] = mcp_result[key]
                            
                    return state
                except Exception as e:
                    effective_logger.error(f"MCP workflow failed with state conversion: {str(e)}")
                    effective_logger.info("Falling back to classic workflow")
            
            # Execute classic workflow as fallback
            effective_logger.info("Executing classic workflow")
            effective_llm = llm or self.llm
            result = await self._execute_classic_workflow(state, effective_llm, effective_logger, config)
            return result
        
        # Handle invalid input
        else:
            error_msg = "Invalid input: expected a query string or state dict"
            effective_logger.error(error_msg)
            return {
                "project_name": "Unknown Project",
                "errors": [error_msg],
                "progress": f"Error: {error_msg}"
            }
    
    # ======= MCP-BASED WORKFLOW METHODS =======
    
    async def get_tools_for_query(self, state: AgentState) -> AgentState:
        """Get the appropriate tools for a query using the MCP router."""
        query = state["query"]
        tools = await self.router.route_query(query)
        
        # Log the tools found
        self.logger.info(f"Found {len(tools)} tools for query: {query}")
        for tool in tools:
            self.logger.info(f"Tool: {tool.name}")
        
        return {**state, "tools": tools}
    
    def create_agent(self, tools: List[BaseTool]) -> Callable:
        """Create a LangChain agent with the given tools."""
        # Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Enhanced Researcher for cryptocurrency and blockchain topics.
            Your goal is to provide comprehensive, accurate, and up-to-date information.
            Use the tools available to gather information from various sources.
            Always cite your sources and provide balanced perspectives."""),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the agent
        agent = create_react_agent(self.llm, tools, prompt)
        
        # Create the agent executor
        async def agent_executor(state: AgentState) -> AgentState:
            messages = [HumanMessage(content=state["query"])]
            agent_outcome = await agent.ainvoke({
                "input": state["query"],
                "agent_scratchpad": messages
            })
            
            return {**state, "agent_outcome": agent_outcome}
        
        return agent_executor
    
    def create_mcp_workflow(self) -> StateGraph:
        """Create a LangGraph workflow that integrates with MCP."""
        # Create the workflow graph
        workflow = StateGraph(AgentState)
        
        # Add nodes to the graph
        workflow.add_node("get_tools", self.get_tools_for_query)
        workflow.add_node("run_agent", lambda state: self.create_agent(state["tools"])(state))
        
        # Add edges to the graph
        workflow.add_edge("get_tools", "run_agent")
        workflow.add_edge("run_agent", END)
        
        # Set the entry point
        workflow.set_entry_point("get_tools")
        
        return workflow
    
    async def _execute_mcp_workflow(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the MCP-based workflow."""
        # Extract project name from query or context
        project_name = context.get("project_name", "")
        if not project_name and "about" in query.lower():
            parts = query.lower().split("about")
            if len(parts) > 1:
                project_name = parts[1].split()[0].strip()
        
        if not project_name:
            project_name = "Unknown Project"
            
        self.logger.info(f"MCP workflow for project: {project_name}")
            
        # Initialize the state
        state = {
            "query": query,
            "tools": [],
            "messages": [],
            "context": context or {},
            "agent_outcome": None,
            "project_name": project_name
        }
        
        # Compile the workflow if not already compiled
        if not self._compiled_mcp_workflow:
            workflow = self.create_mcp_workflow()
            self._compiled_mcp_workflow = workflow.compile()
        
        # Execute the workflow
        try:
            result = await self._compiled_mcp_workflow.ainvoke(state)
            
            # Process the result to match the format expected by downstream components
            processed_result = self._process_mcp_result(result, project_name)
            return processed_result
        except Exception as e:
            self.logger.error(f"Error in MCP workflow: {str(e)}")
            return {
                "project_name": project_name,
                "errors": [str(e)],
                "progress": f"Error in research: {str(e)}"
            }
    
    def _process_mcp_result(self, result: Dict[str, Any], project_name: str) -> Dict[str, Any]:
        """Process MCP result to match format expected by downstream components."""
        # Extract the agent outcome
        agent_outcome = result.get("agent_outcome", "No results found.")
        
        # Create a formatted result
        formatted_result = {
            "project_name": project_name,
            "progress": "Research completed",
            "draft": f"# {project_name} Research Report\n\n*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n{agent_outcome}\n\n",
            "web_research": {"MCP Research": agent_outcome}
        }
        
        # Preserve context data
        if "context" in result:
            formatted_result["context"] = result["context"]
            
        return formatted_result
    
    # ======= CLASSIC WORKFLOW METHODS =======
    
    async def _execute_classic_workflow(self, state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
        """Execute the classic workflow (from original enhanced_researcher)."""
        # Debug log the entire state
        logger.info(f"Classic researcher received state keys: {list(state.keys())}")
        
        # Get project name
        project_name = state.get("project_name", "")
        if not project_name:
            logger.warning("No project name found in state - using default")
            project_name = "Unknown Project"
        else:
            logger.info(f"Using project name from state: '{project_name}'")
            
        # Ensure project name is preserved in all data we gather
        state["project_name"] = project_name
        
        # Load report config
        if "report_config" not in state:
            logger.error("No report configuration found in state")
            state["errors"] = state.get("errors", []) + ["No report configuration found"]
            return state
        
        logger.info(f"Loaded report_config with {len(state['report_config'].get('sections', []))} sections")
        
        # Set cache file location
        cache_file = get_cache_filename(project_name)

        # Extract functions from enhanced_researcher
        extract_from_web_research = lambda web_research, section_title: self._extract_from_web_research(web_research, section_title, logger)
        cache_results = lambda state_dict, cache_file: self._cache_results(state_dict, cache_file, project_name, logger)
        
        # Ensure the project name is set correctly everywhere
        data_gatherer = DataGatherer(project_name, logger)
        
        try:
            state["data"] = data_gatherer.gather_all_data(use_cache=True, cache_ttl=3600)
            state["coingecko_data"] = {k: v for k, v in state["data"].items() if k in ["current_price", "market_cap", "total_supply", "circulating_supply", "max_supply", "price_change_percentage_24h", "24h_volume", "price_history", "volume_history"]}
            state["coinmarketcap_data"] = {k: v for k, v in state["data"].items() if k in ["current_price", "market_cap", "24h_volume", "price_change_percentage_24h", "circulating_supply", "total_supply", "max_supply", "cmc_rank", "price_history", "volume_history", "competitors"]}
            state["defillama_data"] = {k: v for k, v in state["data"].items() if k in ["tvl", "tvl_history", "category", "chains"]}
            
            # Use log_safe to truncate API data in logs
            logger.info(f"Fetched CoinGecko data: {log_safe(state['coingecko_data'])}")
            logger.info(f"Fetched CoinMarketCap data: {log_safe(state['coinmarketcap_data'])}")
            logger.info(f"Fetched DeFiLlama data: {log_safe(state['defillama_data'])}")
            logger.info(f"Fetched and integrated real-time API data for '{project_name}'")
        except Exception as e:
            logger.error(f"Error gathering data: {str(e)}")
            # Initialize empty objects for safety
            state["data"] = state.get("data", {})
            state["coingecko_data"] = state.get("coingecko_data", {})
            state["coinmarketcap_data"] = state.get("coinmarketcap_data", {})
            state["defillama_data"] = state.get("defillama_data", {})

        state["research_data"] = state.get("research_data", {})

        try:
            config_path = config.get("config_path", "backend/config/report_config.json") if config else "backend/config/report_config.json"
            orchestrator = ResearchOrchestrator(llm=llm, logger=logger, config_path=config_path)
            if not orchestrator.report_config:
                orchestrator.report_config = state["report_config"]

            # Web Search
            state["queries"] = await self._generate_queries(project_name, state["report_config"], logger)
            state["progress"] = f"Generated {len(state['queries'])} research queries..."

            if not state.get("root_node"):
                state["root_node"] = ResearchNode(query=f"Comprehensive analysis of {project_name} cryptocurrency", research_type=ResearchType.TECHNICAL)
            
            for i, query in enumerate(state["queries"]):
                if i < len(state["report_config"].get("sections", [])):
                    title = state["report_config"]["sections"][i].get("title", f"Section {i+1}")
                    research_type = orchestrator._determine_research_type(title)
                    state["root_node"].add_child(query=query, research_type=research_type)

            # Create a ResearchState for compatibility with the orchestrator
            research_state_obj = ResearchState(project_name=project_name)
            for key, value in state.items():
                if hasattr(research_state_obj, key):
                    setattr(research_state_obj, key, value)
            
            research_result = await orchestrator.research(project_name, research_state_obj)
            
            if research_result:
                # Copy results back to state dict
                for attr in dir(research_result):
                    if not attr.startswith('_') and not callable(getattr(research_result, attr)) and attr not in ['queries', 'report_config']:
                        state[attr] = getattr(research_result, attr)

            state["structured_data"] = state.get("structured_data", {})
            state["web_research"] = state.get("research_data", {})

            # Populate draft
            draft_lines = [f"# {project_name} Research Report\n\n*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"]
            draft_lines.append("This report is generated with AI assistance and should not be considered financial advice.\n\n")
            
            # Log first few lines of draft for debugging
            logger.info(f"Generating draft with {len(state['report_config'].get('sections', []))} sections")
            
            for section in state["report_config"].get("sections", []):
                section_title = section["title"]
                description = section.get("prompt", "")
                content = extract_from_web_research(state["web_research"], section_title)
                if not content and hf_api_token:
                    content = await self._infer_missing_section_content(state, section_title, description, project_name, logger)
                if not content:
                    content = section.get("fallback_template", "Data unavailable for {section_title}.").format(section_title=section_title)
                draft_lines.append(f"## {section_title}\n\n{content}\n\n")
            
            state["draft"] = "\n".join(draft_lines)
            logger.info(f"Initial draft generated: {len(state['draft'].split())} words")

            # Cache the results using the custom JSON encoder
            cache_results(state, cache_file)
            state["progress"] = f"Research completed for {project_name}"
            return state
        except Exception as e:
            logger.error(f"Error in classic research: {str(e)}", exc_info=True)
            state["errors"] = state.get("errors", []) + [str(e)]
            state["progress"] = f"Error in research: {str(e)}"
            
            # Ensure project_name is preserved even after error
            state["project_name"] = project_name
            return state
    
    # Helper methods from original enhanced_researcher
    
    def _extract_from_web_research(self, web_research: Dict, section_title: str, logger: logging.Logger) -> str:
        """Extract content for a section from web research."""
        content = []
        for query, summary in web_research.items():
            if not isinstance(summary, str) or not summary.strip():
                continue
            if section_title.lower() in query.lower():
                content.append(summary)
                logger.info(f"Extracted content for '{section_title}' from query '{query}'")
        return "\n\n".join(content) if content else ""
    
    def _cache_results(self, state_dict: Dict, cache_file: str, project_name: str, logger: logging.Logger) -> None:
        """Cache research results to file."""
        # Ensure project_name is set correctly before caching
        if "project_name" in state_dict and state_dict["project_name"] != project_name:
            logger.warning(f"Project name mismatch before caching: {state_dict['project_name']} != {project_name}")
            state_dict["project_name"] = project_name
            
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as f:
            # Use custom JSON encoder to handle ResearchNode objects
            dump_with_custom_encoder(state_dict, f)
        logger.info(f"Cached research data to {cache_file}")
    
    async def _generate_queries(self, project_name: str, report_config: Dict, logger: logging.Logger) -> List[str]:
        """Generate research queries based on report configuration."""
        from backend.retriever.tavily_search import TavilySearch
        tavily = TavilySearch(logger=logger)
        queries = []
        for section in report_config.get("sections", []):
            template = section.get("query_template", "")
            if "{project_name}" in template:
                query = template.format(project_name=project_name)
                queries.append(query[:400])
                logger.info(f"Generated query for {section.get('title', 'Unknown')}: {query}")

        async def search_with_fallback(q):
            try:
                section_title = ""
                parts = q.split()
                if len(parts) > 1:
                    section_title = ' '.join(parts[1:3])  # Use a couple words after project name
                
                # Try Tavily search first
                results = await tavily.search_batch([q], max_results=30)
                if (results and isinstance(results[0], dict) and 
                    "results" in results[0] and results[0]["results"]):
                    result_items = results[0]["results"]
                    summaries = [res.get("body", "") for res in result_items if res.get("body")]
                    content = "\n\n".join(summaries)[:2000]
                    if content.strip():
                        logger.info(f"Got valid Tavily content for '{q}'")
                        return content
                
                # If no Tavily results, try HuggingFace if available
                logger.warning(f"No valid content from Tavily for '{q}', trying HuggingFace fallback")
                if hf_api_token:
                    try:
                        hf_search = HuggingFaceSearch(hf_api_token, logger)
                        prompt = f"Provide accurate, factual information about {q}. Focus on verifiable facts."
                        result = hf_search.query("google/pegasus-xsum", prompt, {"max_length": 500})
                        if isinstance(result, list) and result and "generated_text" in result[0]:
                            content = result[0]["generated_text"]
                            logger.info(f"Used HuggingFace fallback for '{q}'")
                            return content
                    except Exception as e:
                        logger.error(f"HuggingFace fallback failed for '{q}': {str(e)}")
                
                # If we reach here, all search methods failed
                logger.error(f"All search methods failed for '{q}'")
                return f"[No data available for {q}. Please refer to the project's official resources for accurate information.]"
                
            except Exception as e:
                logger.error(f"Search failed for '{q}': {str(e)}")
                return f"[Error retrieving information for {q}: {str(e)}]"

        tasks = [search_with_fallback(q) for q in queries]
        results = await asyncio.gather(*tasks)
        return results
    
    async def _infer_missing_section_content(self, state_dict: Dict, section_title: str, description: str, project_name: str, logger: logging.Logger) -> str:
        """Infer content for a missing section using HuggingFace."""
        if not hf_api_token:
            logger.warning(f"No HF token for inferring '{section_title}' content")
            return f"Data unavailable for {section_title}."
        try:
            hf_search = HuggingFaceSearch(hf_api_token, logger)
            prompt = f"Provide a detailed 400-500 word summary of '{section_title}' for {project_name}: {description}"
            result = hf_search.query("google/pegasus-xsum", prompt, {"max_length": 500})
            if isinstance(result, list) and result and "generated_text" in result[0]:
                content = result[0]["generated_text"]
                logger.info(f"Inferred content for '{section_title}' via HF: {content[:50]}...")
                return content
            logger.warning(f"Invalid HF response for '{section_title}'")
            return f"Data unavailable for {section_title}."
        except Exception as e:
            logger.error(f"HF inference failed for '{section_title}': {str(e)}")
            return f"Data unavailable for {section_title}."

# Backward compatibility function for direct calling
async def researcher(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    """Backward-compatible function for direct calling of the researcher."""
    agent = Researcher(llm_model=llm.model_name, logger=logger)
    return await agent._execute_classic_workflow(state, llm, logger, config)

# Synchronous wrapper for backward compatibility
def researcher_sync(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    """Synchronous wrapper for backward compatibility."""
    return asyncio.run(researcher(state, llm, logger, config)) 