"""
Update the Researcher class to use the LLMFactory for model selection.
This ensures that the Researcher can use different models for different tasks,
optimizing for both performance and cost.
"""

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
from backend.utils.llm_factory import LLMFactory
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
    
    def __init__(self, llm_model: str = None, use_mcp: bool = None, logger: logging.Logger = None):
        """
        Initialize the researcher.
        
        Args:
            llm_model: The LLM model to use (optional, will use LLMFactory if not provided)
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
            
        # Initialize LLM using the factory
        if llm_model:
            self.llm = ChatOpenAI(model=llm_model, api_key=os.environ.get("OPENAI_API_KEY"))
        else:
            self.llm = LLMFactory.get_llm_for_task("RESEARCHER")
        
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
        
        # Use RAG-specific LLM for the agent if available
        try:
            rag_llm = LLMFactory.get_llm_for_task("RAG")
            self.logger.info(f"Using RAG-specific LLM for agent: {rag_llm.model_name}")
        except Exception as e:
            self.logger.warning(f"Could not get RAG-specific LLM, using default: {str(e)}")
            rag_llm = self.llm
        
        # Create the agent
        agent = create_react_agent(rag_llm, tools, prompt)
        
        # Create the agent executor
        def agent_executor(state: AgentState) -> AgentState:
            messages = state["messages"]
            agent_scratchpad = format_to_openai_function_messages(messages[1:])
            
            # Get the agent's response
            result = agent.invoke({
                "input": state["query"],
                "agent_scratchpad": agent_scratchpad
            })
            
            # Update the state with the agent's response
            return {**state, "agent_outcome": result, "messages": messages + [result]}
        
        return agent_executor
    
    async def _execute_mcp_workflow(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the MCP-based research workflow."""
        # Initialize the workflow if not already done
        if self._compiled_mcp_workflow is None:
            self._compiled_mcp_workflow = self._create_mcp_workflow()
            
        # Create the initial state
        project_name = context.get("project_name", "Unknown Project")
        initial_state = {
            "query": query,
            "tools": [],
            "messages": [HumanMessage(content=query)],
            "context": context,
            "agent_outcome": None,
            "project_name": project_name
        }
        
        # Execute the workflow
        self.logger.info(f"Executing MCP workflow for project: {project_name}")
        try:
            result = await self._compiled_mcp_workflow.ainvoke(initial_state)
            
            # Process the result into a format compatible with the classic workflow
            agent_outcome = result.get("agent_outcome", {})
            agent_content = agent_outcome.get("output", "") if agent_outcome else ""
            
            # Create a draft from the agent's output
            draft = f"# {project_name}\n\n{agent_content}"
            
            # Return the result in a format compatible with the classic workflow
            return {
                "project_name": project_name,
                "draft": draft,
                "web_research": agent_content,
                "progress": "Research completed successfully using MCP workflow"
            }
        except Exception as e:
            self.logger.error(f"Error executing MCP workflow: {str(e)}")
            return {
                "project_name": project_name,
                "draft": f"# {project_name}\n\nError: {str(e)}",
                "errors": [str(e)],
                "progress": f"Error: {str(e)}"
            }
    
    def _create_mcp_workflow(self) -> StateGraph:
        """Create the MCP-based research workflow."""
        # Create the workflow
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("get_tools", self.get_tools_for_query)
        workflow.add_node("execute_agent", self.create_agent([]))  # Tools will be provided by get_tools
        
        # Set the entry point
        workflow.set_entry_point("get_tools")
        
        # Add edges
        workflow.add_edge("get_tools", "execute_agent")
        workflow.add_edge("execute_agent", END)
        
        # Compile the workflow
        return workflow.compile()
    
    # ======= CLASSIC WORKFLOW METHODS =======
    
    async def _execute_classic_workflow(self, state: Dict[str, Any], llm: ChatOpenAI, 
                                       logger: logging.Logger, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the classic research workflow."""
        # Implementation of the classic workflow (unchanged)
        # This is a placeholder - the actual implementation would be copied from the existing code
        logger.info("Executing classic workflow (placeholder)")
        return state

# Legacy function for backward compatibility
async def researcher(state: Dict[str, Any], llm: ChatOpenAI = None, 
                    logger: logging.Logger = None, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Legacy function for the classic researcher workflow."""
    # Create a researcher instance
    researcher_instance = Researcher(
        llm_model=llm.model_name if llm else None,
        use_mcp=False,
        logger=logger
    )
    
    # Execute the workflow
    return await researcher_instance._execute_classic_workflow(state, llm, logger, config)
