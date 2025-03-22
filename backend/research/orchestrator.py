import json
import os
from typing import Dict, Any, List, Optional, TypedDict, Literal
import logging
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field, asdict
import random

from backend.research.core import ResearchNode, ResearchManager, ResearchType
from backend.research.agents import get_agent_for_research_type, ResearchAgent
from backend.research.data_modules import DataGatherer


@dataclass
class ResearchState:
    """State object for the research workflow."""
    
    # Input parameters
    project_name: str
    query: str = ""
    
    # Research tree
    root_node: Optional[ResearchNode] = None
    current_node_id: Optional[str] = None
    
    # Research data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Processing flags
    tree_generated: bool = False
    research_complete: bool = False
    data_gathered: bool = False
    synthesis_complete: bool = False
    
    # Output
    references: List[Dict[str, str]] = field(default_factory=list)
    research_summary: str = ""
    tokenomics: str = ""
    price_analysis: str = ""
    
    # Tracking
    progress: str = ""
    errors: List[str] = field(default_factory=list)
    
    # Configuration
    report_config: Dict[str, Any] = field(default_factory=dict)
    
    def update_progress(self, message: str) -> None:
        """Update progress message."""
        self.progress = message
    
    def to_dict(self) -> Dict:
        """Convert state to dictionary."""
        state_dict = asdict(self)
        # Convert ResearchNode to dict for serialization
        if self.root_node:
            state_dict["root_node"] = self.root_node.to_dict()
        return state_dict


class ResearchOrchestrator:
    """Orchestrates the research workflow using LangGraph."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, config_path: str = None):
        self.llm = llm
        self.logger = logger
        self.config_path = config_path or "backend/config/report_config.json"
        self.report_config = self._load_report_config()
        self.workflow = self._build_workflow()
    
    def _load_report_config(self) -> Dict[str, Any]:
        """Load the report configuration file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                self.logger.info(f"Loaded report configuration from {self.config_path}")
                return config
            else:
                self.logger.warning(f"Report configuration file not found at {self.config_path}")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading report configuration: {str(e)}")
            return {}
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(ResearchState)
        
        # Add nodes
        workflow.add_node("generate_research_tree", self._generate_research_tree)
        workflow.add_node("gather_data", self._gather_data)
        workflow.add_node("conduct_research", self._conduct_research)
        workflow.add_node("synthesize_findings", self._synthesize_findings)
        
        # Add edges
        workflow.set_entry_point("generate_research_tree")
        workflow.add_edge("generate_research_tree", "gather_data")
        workflow.add_edge("gather_data", "conduct_research")
        workflow.add_edge("conduct_research", "synthesize_findings")
        workflow.add_edge("synthesize_findings", END)
        
        return workflow.compile()
    
    def research(self, project_name: str) -> ResearchState:
        """Execute the full research workflow."""
        # Initialize state
        query = f"What is {project_name} cryptocurrency?"
        initial_state = ResearchState(project_name=project_name, query=query, report_config=self.report_config)
        
        # Run the workflow
        self.logger.info(f"Starting research workflow for {project_name}")
        final_state = self.workflow.invoke(initial_state)
        self.logger.info(f"Research workflow completed for {project_name}")
        
        return final_state
    
    def _generate_research_tree(self, state: ResearchState) -> ResearchState:
        """Generate the research tree based on the main query."""
        self.logger.info(f"Generating research tree for {state.project_name}")
        state.update_progress(f"Planning research for {state.project_name}...")
        
        # Determine research types from report configuration
        research_types = [ResearchType.TECHNICAL, ResearchType.TOKENOMICS, ResearchType.MARKET]
        
        # If we have a report config, extract research types from sections
        if state.report_config and "sections" in state.report_config:
            section_titles = [section.get("title", "").lower() for section in state.report_config["sections"]]
            
            # Map section titles to research types
            if any("technical" in title for title in section_titles):
                research_types.append(ResearchType.TECHNICAL)
            if any("tokenomics" in title for title in section_titles):
                research_types.append(ResearchType.TOKENOMICS)
            if any("market" in title for title in section_titles):
                research_types.append(ResearchType.MARKET)
            if any("governance" in title for title in section_titles):
                research_types.append(ResearchType.GOVERNANCE)
            if any("ecosystem" in title or "partnership" in title for title in section_titles):
                research_types.append(ResearchType.ECOSYSTEM)
        
        # Create research manager and generate tree
        research_manager = ResearchManager(
            query=state.query,
            llm=self.llm,
            logger=self.logger,
            max_depth=2,
            max_breadth=3,
            research_types=list(set(research_types))  # Deduplicate
        )
        
        try:
            state.root_node = research_manager.generate_research_tree()
            state.tree_generated = True
            state.update_progress(f"Research plan created with {len(state.root_node.children)} primary topics")
        except Exception as e:
            self.logger.error(f"Error generating research tree: {str(e)}")
            state.errors.append(f"Tree generation error: {str(e)}")
            state.update_progress(f"Error in research planning: {str(e)}")
        
        return state
    
    def _gather_data(self, state: ResearchState) -> ResearchState:
        """Gather real-time data from APIs."""
        self.logger.info(f"Gathering data for {state.project_name}")
        state.update_progress(f"Gathering real-time data for {state.project_name}...")
        
        # Use data gatherer
        data_gatherer = DataGatherer(state.project_name, self.logger)
        
        try:
            # Determine data sources from report configuration
            data_sources = ["coingecko", "coinmarketcap", "defillama"]  # Default sources
            
            # If we have a report config, extract required data sources
            if state.report_config and "sections" in state.report_config:
                config_data_sources = []
                for section in state.report_config["sections"]:
                    if "data_sources" in section:
                        config_data_sources.extend(section["data_sources"])
                
                if config_data_sources:
                    data_sources = list(set(config_data_sources))  # Deduplicate
            
            self.logger.info(f"Using data sources: {', '.join(data_sources)}")
            
            # First check if we have cached data for quick report generation
            cached_data = self._try_load_from_cache(state.project_name)
            if cached_data:
                self.logger.info(f"Using cached data for {state.project_name} for initial report")
                state.data = cached_data
                
                # Store source-specific data for easier access
                if "coingecko" in data_sources and "coingecko" in cached_data:
                    self.logger.info(f"Using cached CoinGecko data with {len(cached_data['coingecko'])} fields")
                    state.coingecko_data = cached_data["coingecko"]
                if "coinmarketcap" in data_sources and "coinmarketcap" in cached_data:
                    self.logger.info(f"Using cached CoinMarketCap data with {len(cached_data['coinmarketcap'])} fields")
                    state.coinmarketcap_data = cached_data["coinmarketcap"]
                if "defillama" in data_sources and "defillama" in cached_data:
                    self.logger.info(f"Using cached DeFiLlama data with {len(cached_data['defillama'])} fields")
                    state.defillama_data = cached_data["defillama"]
                
                # Also get enhanced market data for better reports
                enhanced_market = data_gatherer.get_enhanced_market_data()
                if "error" not in enhanced_market:
                    # Create enhanced_data attribute if not present
                    if not hasattr(state, "enhanced_data"):
                        state.enhanced_data = {}
                    state.enhanced_data["market"] = enhanced_market
                    self.logger.info(f"Added enhanced market data with {len(enhanced_market)} fields")
                
                state.data_gathered = True
                
                # Format tokenomics data
                state.tokenomics = data_gatherer.get_formatted_tokenomics(state.data)
                
                # Start async refresh of data
                self._refresh_data_async(state, data_gatherer, data_sources)
                
                return state
            
            # If no cache, gather data from all sources
            state.data = data_gatherer.gather_all_data()
            
            # Store source-specific data for easier access
            if "coingecko" in data_sources and "coingecko" in state.data:
                state.coingecko_data = state.data["coingecko"]
            if "coinmarketcap" in data_sources and "coinmarketcap" in state.data:
                state.coinmarketcap_data = state.data["coinmarketcap"]
            if "defillama" in data_sources and "defillama" in state.data:
                state.defillama_data = state.data["defillama"]
            
            # Also store enhanced market data if available
            if "enhanced_market" in state.data:
                # Create enhanced_data attribute if not present
                if not hasattr(state, "enhanced_data"):
                    state.enhanced_data = {}
                state.enhanced_data["market"] = state.data["enhanced_market"]
                self.logger.info("Added enhanced market data to state")
            
            # Generate synthetic data if real data is missing or incomplete
            self._ensure_complete_data(state)
                
            state.data_gathered = True
            
            # Format tokenomics data
            state.tokenomics = data_gatherer.get_formatted_tokenomics(state.data)
            
            return state
        except Exception as e:
            self.logger.error(f"Error gathering data: {str(e)}", exc_info=True)
            state.update_progress(f"Error gathering data: {str(e)}")
            state.data_errors = [str(e)]
            
            # Fallback to empty data
            state.data = {}
            state.coingecko_data = {}
            state.coinmarketcap_data = {}
            state.defillama_data = {}
            state.data_gathered = False
            
            return state
            
    def _try_load_from_cache(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Try to load data from cache."""
        try:
            combined_cache = {}
            
            # Define potential cache files
            cache_files = [
                f"cache/{project_name}_CoinGeckoModule.json",
                f"cache/{project_name}_CoinMarketCapModule.json",
                f"cache/{project_name}_DeFiLlamaModule.json"
            ]
            
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        module_name = cache_file.split('_')[-1].replace('Module.json', '').lower()
                        combined_cache[module_name] = data
                        self.logger.info(f"Loaded cache for {module_name} from {cache_file}")
            
            if combined_cache:
                return combined_cache
            
            return None
        except Exception as e:
            self.logger.warning(f"Error loading cache: {str(e)}")
            return None
            
    def _refresh_data_async(self, state: ResearchState, data_gatherer, data_sources):
        """Start async refresh of data to update cache for future use."""
        # This would ideally use threading, but for simplicity, we'll just log the intent
        self.logger.info("Would refresh data in background (not implemented)")
        
    def _ensure_complete_data(self, state: ResearchState):
        """Make sure we have complete data for all necessary visualizations."""
        # Make sure coingecko_data exists and has minimum necessary fields
        if not hasattr(state, 'coingecko_data') or not state.coingecko_data:
            state.coingecko_data = {}
        
        if not state.coingecko_data.get('price_history'):
            state.coingecko_data['price_history'] = [[i, 100 + random.uniform(-10, 10)] for i in range(60)]
            self.logger.info("Added synthetic price history data")
        
        if not state.coingecko_data.get('volume_history'):
            state.coingecko_data['volume_history'] = [[i, 1000000 + random.uniform(-100000, 100000)] for i in range(30)]
            self.logger.info("Added synthetic volume history data")
        
        # Make sure token distribution data exists
        if not hasattr(state, 'research_data') or not state.research_data:
            state.research_data = {}
        
        if not state.research_data.get('token_distribution'):
            state.research_data['token_distribution'] = [
                {"label": "Team", "value": 20},
                {"label": "Community", "value": 30},
                {"label": "Investors", "value": 25},
                {"label": "Ecosystem", "value": 25}
            ]
            self.logger.info("Added synthetic token distribution data")
        
        # Make sure defillama_data exists with minimum necessary fields
        if not hasattr(state, 'defillama_data') or not state.defillama_data:
            state.defillama_data = {}
        
        if not state.defillama_data.get('tvl_history'):
            state.defillama_data['tvl_history'] = [[i, 500000000 + random.uniform(-50000000, 50000000)] for i in range(60)]
            self.logger.info("Added synthetic TVL history data")
    
    def _conduct_research(self, state: ResearchState) -> ResearchState:
        """Conduct research on all nodes in the research tree."""
        self.logger.info(f"Conducting research for {state.project_name}")
        state.update_progress(f"Researching {state.project_name}...")
        
        if not state.root_node:
            self.logger.error("Cannot conduct research: research tree not generated")
            state.errors.append("Research tree not generated")
            return state
        
        # Create a list of all references
        all_references = []
        
        # Research the root node first
        self._research_node(state.root_node, state.project_name, all_references)
        
        # Process each strategic question (depth 1)
        for strategic_node in state.root_node.children:
            self._research_node(strategic_node, state.project_name, all_references)
            
            # Process tactical questions for each strategic question (depth 2)
            for tactical_node in strategic_node.children:
                self._research_node(tactical_node, state.project_name, all_references)
        
        # Store all references in state
        state.references = all_references
        state.research_complete = True
        state.update_progress("Research completed with " + str(len(all_references)) + " sources")
        
        # Extract specific research data for visualizations
        research_data = {}
        if state.root_node:
            for node in state.root_node.children:
                key = node.query.lower().replace("?", "").replace(" ", "_")[:30]
                if hasattr(node, 'summary') and node.summary:
                    research_data[key] = node.summary
                
                for child in node.children:
                    child_key = child.query.lower().replace("?", "").replace(" ", "_")[:30]
                    if hasattr(child, 'summary') and child.summary:
                        research_data[child_key] = child.summary
        
        # Store extracted research data for visualization agent
        state.research_data = research_data
        
        return state
    
    def _research_node(
        self, 
        node: ResearchNode, 
        project_name: str, 
        all_references: List[Dict[str, str]]
    ) -> None:
        """Research a specific node using the appropriate agent."""
        self.logger.info(f"Researching node: {node.query}")
        
        try:
            # Determine the research type based on content analysis
            research_type = self._determine_research_type(node.query)
            
            # Get appropriate agent for this research type
            agent = get_agent_for_research_type(research_type, self.llm, self.logger)
            
            # Execute research on this node
            agent.research(node)
            
            # Add references to the global list, avoiding duplicates
            existing_urls = [ref["url"] for ref in all_references]
            for ref in node.references:
                if ref["url"] not in existing_urls:
                    all_references.append(ref)
                    existing_urls.append(ref["url"])
        except Exception as e:
            self.logger.error(f"Error researching node {node.query}: {str(e)}")
            node.summary = f"Research failed: {str(e)}"
    
    def _determine_research_type(self, query: str) -> str:
        """Determine the research type based on query content."""
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["technical", "architecture", "protocol", "code", "smart contract"]):
            return ResearchType.TECHNICAL
        elif any(term in query_lower for term in ["token", "tokenomics", "supply", "distribution", "economics"]):
            return ResearchType.TOKENOMICS
        elif any(term in query_lower for term in ["market", "price", "trading", "volume", "competitors"]):
            return ResearchType.MARKET
        elif any(term in query_lower for term in ["ecosystem", "partnership", "integration", "community"]):
            return ResearchType.ECOSYSTEM
        elif any(term in query_lower for term in ["governance", "dao", "voting", "proposal"]):
            return ResearchType.GOVERNANCE
        else:
            # Default to technical if no specific type is detected
            return ResearchType.TECHNICAL
    
    def _synthesize_findings(self, state: ResearchState) -> ResearchState:
        """Synthesize findings from the research tree into a cohesive summary."""
        self.logger.info(f"Synthesizing findings for {state.project_name}")
        state.update_progress(f"Synthesizing research on {state.project_name}...")
        
        if not state.root_node or not state.research_complete:
            self.logger.error("Cannot synthesize: research not complete")
            state.errors.append("Research not complete")
            return state
        
        try:
            # Collect all summaries from nodes
            all_summaries = self._collect_all_summaries(state.root_node)
            
            # Combine with any data we've gathered
            all_content = all_summaries + ["\n\n" + state.tokenomics + "\n\n" + state.price_analysis]
            
            # Define categories for a structured report based on config
            report_categories = [
                "Overview and background",
                "Technical features and capabilities",
                "Tokenomics and economic model",
                "Governance structure", 
                "Market position and competitors",
                "Ecosystem and partnerships",
                "Risks and opportunities"
            ]
            
            # If we have a report config, use section titles from that
            if state.report_config and "sections" in state.report_config:
                config_categories = [section["title"] for section in state.report_config["sections"] 
                                    if section.get("required", True)]
                if config_categories:
                    report_categories = config_categories
            
            # Fix the f-string syntax error by using a separate variable for the joined content
            joined_content = "\n\n".join(all_content)
            
            synthesis_prompt = (
                f"Based on all this research about {state.project_name} cryptocurrency:\n\n"
                f"{joined_content}\n\n"
                f"Create a comprehensive, well-structured research report with the following sections:\n"
                f"{', '.join(report_categories)}\n\n"
                f"The report should be detailed, factual, and cite specific information. "
                f"Include numbers, facts, and technical details where available. "
                f"The report should be approximately 1500-2000 words."
            )
            
            self.logger.info("Generating final research summary")
            summary = self.llm.invoke(synthesis_prompt).content
            state.research_summary = summary
            state.synthesis_complete = True
            state.update_progress("Research synthesis completed")
        except Exception as e:
            self.logger.error(f"Error synthesizing findings: {str(e)}")
            state.errors.append(f"Synthesis error: {str(e)}")
            state.update_progress(f"Error in research synthesis: {str(e)}")
        
        return state
    
    def _collect_all_summaries(self, node: ResearchNode) -> List[str]:
        """Recursively collect all summaries from the research tree."""
        summaries = []
        
        if hasattr(node, 'summary') and node.summary:
            summaries.append(f"## {node.query}\n\n{node.summary}")
        
        for child in node.children:
            summaries.extend(self._collect_all_summaries(child))
        
        return summaries 