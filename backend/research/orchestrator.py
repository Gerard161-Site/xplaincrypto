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
from backend.research.data_modules import DataGatherer, DataModule


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
    # NEW: Added fields for governance and team to store specific content (Task 1)
    governance: str = ""
    team_and_development: str = ""
    
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


class ResearchManager:
    """Manages the research process by handling research tree generation, data gathering, and research execution."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, config_path: str = None):
        self.llm = llm
        self.logger = logger
        self.config_path = config_path or "backend/config/report_config.json"
        self.report_config = self._load_report_config()
    
    def research(self, project_name: str) -> ResearchState:
        """Execute the research process for a given project."""
        state = ResearchState(project_name=project_name)
        state = self._generate_research_tree(state)
        state = self._gather_data(state)
        state = self._conduct_research(state)
        state = self._synthesize_findings(state)
        return state
    
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
    
    def _generate_research_tree(self, state: ResearchState) -> ResearchState:
        """Generate the research tree based on the main query."""
        self.logger.info(f"Generating research tree for {state.project_name}")
        state.update_progress(f"Planning research for {state.project_name}...")
        
        # Create root node for the project
        root_query = f"Comprehensive analysis of {state.project_name} cryptocurrency"
        state.root_node = ResearchNode(query=root_query, research_type=ResearchType.TECHNICAL)
        
        # If we have a report config, use it to structure the research tree
        if state.report_config and "sections" in state.report_config:
            self._generate_config_based_tree(state)
        else:
            # Fallback to the original approach if no config is available
            self._generate_generic_tree(state)
        
        state.tree_generated = True
        self.logger.info(f"Research tree generated with {len(state.root_node.children)} sections")
        state.update_progress(f"Research plan created with {len(state.root_node.children)} primary topics")
        
        return state

    def _generate_config_based_tree(self, state: ResearchState) -> None:
        """Generate a structured research tree based on report configuration."""
        self.logger.info("Generating research tree based on report configuration")
        
        # For each section in the report config
        for section in state.report_config.get("sections", []):
            section_title = section.get("title", "")
            description = section.get("description", "")
            data_sources = section.get("data_sources", [])
            visualizations = section.get("visualizations", [])
            
            # Skip sections without a title or description
            if not section_title:
                continue
                
            # Determine research type for this section
            research_type = self._determine_research_type(section_title)
            
            # Create a section node
            section_query = f"{section_title} of {state.project_name}"
            section_node = state.root_node.add_child(
                query=section_query,
                research_type=research_type
            )
            
            # If the section has visualizations, extract the data fields needed
            data_fields = self._get_data_fields_for_section(section, state.report_config)
            
            # If we have data fields, create data nodes for each one
            if data_fields:
                for data_field, source_info in data_fields.items():
                    source = source_info.get('source', 'web_research')
                    field_query = f"{data_field} of {state.project_name}"
                    
                    # Add a specific data node for this field
                    section_node.add_child(
                        query=field_query,
                        research_type=research_type,
                        data_field=data_field,
                        source=source
                    )
            
            # Add an analysis node with the section description
            if description:
                analysis_query = f"Analysis: {description} for {state.project_name}"
                section_node.add_child(
                    query=analysis_query,
                    research_type=research_type
                )
                
    def _get_data_fields_for_section(self, section: Dict[str, Any], report_config: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Extract data fields needed for visualizations in a section."""
        data_fields = {}
        vis_types = report_config.get("visualization_types", {})
        
        # For each visualization in the section
        for vis_name in section.get("visualizations", []):
            if vis_name in vis_types:
                vis_config = vis_types[vis_name]
                source = vis_config.get("data_source", "web_research")
                
                # Get data fields from the visualization
                if "data_field" in vis_config:
                    field = vis_config["data_field"]
                    data_fields[field] = {"source": source}
                
                if "data_fields" in vis_config:
                    for field in vis_config["data_fields"]:
                        data_fields[field] = {"source": source}
        
        return data_fields
        
    def _generate_generic_tree(self, state: ResearchState) -> None:
        """Generate a generic research tree based on predefined research types."""
        self.logger.info("Generating generic research tree with predefined types")
        
        research_types = [
            ResearchType.TECHNICAL,
            ResearchType.TOKENOMICS,
            ResearchType.MARKET,
            ResearchType.ECOSYSTEM,
            ResearchType.GOVERNANCE,
            ResearchType.TEAM,
            ResearchType.RISKS,
            ResearchType.OPPORTUNITIES
        ]
        
        # Directly create the nodes without using ResearchManager from core.py
        for rt in research_types:
            state.root_node.add_child(f"{rt} analysis of {state.project_name}", rt)
        
        self.logger.info(f"Created {len(research_types)} research type nodes")
    
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
            
            # Try to fetch competitor data but handle errors gracefully
            try:
                # MODIFIED: Fetch competitor data for Task 3 (Competitive Analysis)
                competitors = ["ethereum", "solana", "avalanche-2"]  # CoinGecko IDs for ETH, SOL, AVAX
                competitor_data = {}
                for comp in competitors:
                    # Use a concrete implementation instead of abstract class
                    from backend.research.data_modules import CoinGeckoModule
                    comp_module = CoinGeckoModule(comp, self.logger)
                    comp_data = comp_module.gather_data(use_cache=True)
                    if "error" not in comp_data:
                        competitor_data[comp] = comp_data
                state.data["competitors"] = competitor_data
                self.logger.info(f"Gathered competitor data for {len(competitor_data)} coins")
            except Exception as e:
                # Provide an empty placeholder if the above fails
                self.logger.warning(f"Could not gather competitor data: {str(e)}")
                state.data["competitors"] = {}
            
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
                
                state.data_gathered = True
                
                # MODIFIED: Format price analysis with real data (Task 2)
                state.price_analysis = self._format_price_analysis(state)
                state.tokenomics = self._format_tokenomics(state)  # Use internal method instead
                
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
            
            state.data_gathered = True
            
            # MODIFIED: Format price analysis with real data (Task 2)
            state.price_analysis = self._format_price_analysis(state)
            state.tokenomics = self._format_tokenomics(state)  # Use internal method instead
            
            return state
        except Exception as e:
            self.logger.error(f"Error gathering data: {str(e)}", exc_info=True)
            state.update_progress(f"Error gathering data: {str(e)}")
            state.errors.append(str(e))
            
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
        # Placeholder for async implementation
        self.logger.info("Would refresh data in background (not implemented)")
    
    # NEW: Added method to format price analysis with real data (Task 2)
    def _format_price_analysis(self, state: ResearchState) -> str:
        """Format price analysis with real-time data."""
        price_data = state.coingecko_data if hasattr(state, 'coingecko_data') else {}
        if not price_data or "current_price" not in price_data:
            return f"Price analysis for {state.project_name}.\n60-Day Change: Data unavailable."
        
        current_price = price_data.get("current_price", 0)
        market_cap = price_data.get("market_cap", 0)
        # Simulate 60-day change if historical data isn't available
        price_history = price_data.get("price_history", [])
        sixty_day_change = "Data unavailable"
        if price_history and len(price_history) >= 60:
            old_price = price_history[-60][1] if isinstance(price_history[-60], list) else price_history[-60]
            sixty_day_change = f"{((current_price - old_price) / old_price * 100):.2f}%"
        
        return (
            f"Price analysis for {state.project_name}\n\n"
            f"Current Price: ${current_price:.4f}\n"
            f"Market Cap: ${market_cap:,}\n"
            f"60-Day Change: {sixty_day_change}"
        )
    
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
        self._research_node(state.root_node, state.project_name, all_references, state.data)
        
        # Process each section node (depth 1)
        for section_node in state.root_node.children:
            self._research_node(section_node, state.project_name, all_references, state.data)
            
            # Process data and analysis nodes for each section (depth 2)
            for detail_node in section_node.children:
                self._research_node(detail_node, state.project_name, all_references, state.data)
        
        # Store all references in state
        state.references = all_references
        state.research_complete = True
        state.update_progress(f"Research completed with {len(all_references)} sources")
        
        return state
    
    def _research_node(
        self, 
        node: ResearchNode, 
        project_name: str, 
        all_references: List[Dict[str, str]],
        api_data: Dict[str, Any]
    ) -> None:
        """Research a specific node using appropriate method based on node type."""
        self.logger.info(f"Researching node: {node.query}")
        node_id = node.id if hasattr(node, 'id') else "unknown"
        self.logger.debug(f"Node ID: {node_id}, Type: {node.research_type}, Data field: {node.data_field}")
        
        try:
            # Check if node is a data node (has data_field)
            if node.data_field:
                self.logger.debug(f"Node has data_field: {node.data_field}, checking API sources")
                # Try to get data from API sources first
                api_value = self._get_api_data_for_field(node.data_field, node.source, api_data)
                
                if api_value is not None:
                    # We have API data, use it directly
                    self.logger.info(f"Using API data for {node.data_field}: {api_value}")
                    
                    # Set structured data
                    node.structured_data = {node.data_field: api_value}
                    
                    # Set summary with the data field and value
                    node.summary = f"{node.data_field}: {api_value}"
                    
                    # Add API as reference
                    source_name = node.source.capitalize() if node.source else "API"
                    node.references = [{"title": f"{source_name} data", "url": f"https://{node.source}.com"}]
                    
                    # Return without doing web research
                    self.logger.debug(f"Successfully used API data for node {node_id}")
                    return
                else:
                    self.logger.info(f"No API data for {node.data_field}, falling back to web research")
            
            # No API data found or not a data node, proceed with web research
            research_type = node.research_type or self._determine_research_type(node.query)
            self.logger.debug(f"Research type determined for node {node_id}: {research_type}")
            
            # Get appropriate agent for this research type
            self.logger.debug(f"Getting agent for research type: {research_type}")
            agent = get_agent_for_research_type(research_type, self.llm, self.logger)
            self.logger.debug(f"Using agent: {agent.__class__.__name__} for node {node_id}")
            
            # Execute research on this node
            before_state = {
                'has_content': bool(getattr(node, 'content', '')), 
                'has_summary': bool(getattr(node, 'summary', '')),
                'has_references': bool(getattr(node, 'references', []))
            }
            self.logger.debug(f"Node state before research: {before_state}")
            
            # Execute research and verify the node was returned
            result_node = agent.research(node)
            if result_node is not node:
                self.logger.warning(f"Agent returned a different node than passed in. Using the returned node.")
                # Copy relevant properties from the returned node
                node.content = getattr(result_node, 'content', node.content)
                node.summary = getattr(result_node, 'summary', node.summary)
                node.references = getattr(result_node, 'references', node.references)
                node.structured_data = getattr(result_node, 'structured_data', node.structured_data)
            
            after_state = {
                'has_content': bool(getattr(node, 'content', '')), 
                'has_summary': bool(getattr(node, 'summary', '')),
                'has_references': len(getattr(node, 'references', [])),
                'summary_length': len(getattr(node, 'summary', '')),
                'content_preview': getattr(node, 'content', '')[:50] + '...' if getattr(node, 'content', '') else ''
            }
            self.logger.debug(f"Node state after research: {after_state}")
            
            # Verify that the research was successful
            if not node.summary:
                self.logger.warning(f"Research completed but no summary was generated for node {node_id}")
                node.summary = f"Research produced no results for: {node.query}"
            
            # Add references to the global list, avoiding duplicates
            existing_urls = [ref["url"] for ref in all_references]
            refs_added = 0
            for ref in node.references:
                if "url" in ref and ref["url"] not in existing_urls:
                    all_references.append(ref)
                    existing_urls.append(ref["url"])
                    refs_added += 1
            self.logger.debug(f"Added {refs_added} new references from node {node_id}")
            
            self.logger.info(f"Successfully researched node {node_id}")
                    
        except Exception as e:
            self.logger.error(f"Error researching node {node_id}: {str(e)}", exc_info=True)
            node.summary = f"Research failed: {str(e)}"
            # Ensure structured_data exists even on error
            if not hasattr(node, 'structured_data') or node.structured_data is None:
                node.structured_data = {}
            # Ensure references exists even on error
            if not hasattr(node, 'references') or node.references is None:
                node.references = []
    
    def _get_api_data_for_field(self, data_field: str, source: str, api_data: Dict[str, Any]) -> Any:
        """Get data for a specific field from API data if available."""
        # Check if we have the source
        if not source or source == "web_research" or source not in api_data:
            return None
            
        source_data = api_data.get(source, {})
        
        # Direct match for the data field
        if data_field in source_data:
            return source_data[data_field]
            
        # Handle multi-source by checking if multi exists and contains field
        if "multi" in api_data and data_field in api_data["multi"]:
            return api_data["multi"][data_field]
            
        # No match found
        return None
    
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
        elif any(term in query_lower for term in ["team", "development", "roadmap", "founders"]):
            return ResearchType.TEAM
        elif any(term in query_lower for term in ["risks", "challenges", "vulnerabilities"]):
            return ResearchType.RISKS
        elif any(term in query_lower for term in ["opportunities", "growth", "potential"]):
            return ResearchType.OPPORTUNITIES
        else:
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
            
            # MODIFIED: Include competitor data and specific sections (Tasks 1, 2, 3)
            all_content = all_summaries + [
                "\n\n" + state.tokenomics,
                "\n\n" + state.price_analysis,
                "\n\n" + state.governance,
                "\n\n" + state.team_and_development,
                "\n\nCompetitor Data:\n" + json.dumps(state.data.get("competitors", {}), indent=2)
            ]
            
            # Define categories for a structured report based on config
            report_categories = [
                "Overview and background",
                "Technical features and capabilities",
                "Tokenomics and economic model",
                "Governance structure",
                "Market position and competitors",
                "Ecosystem and partnerships",
                "Risks and opportunities",
                "Team and development"  # Added for Task 1
            ]
            
            # If we have a report config, use section titles from that
            if state.report_config and "sections" in state.report_config:
                config_categories = [section["title"] for section in state.report_config["sections"] 
                                    if section.get("required", True)]
                if config_categories:
                    report_categories = config_categories
            
            joined_content = "\n\n".join(all_content)
            
            synthesis_prompt = (
                f"Based on all this research about {state.project_name} cryptocurrency:\n\n"
                f"{joined_content}\n\n"
                f"Create a comprehensive, well-structured research report with the following sections:\n"
                f"{', '.join(report_categories)}\n\n"
                f"The report should be detailed, factual, and cite specific information. "
                f"Include numbers, facts, and technical details where available (e.g., current price, market cap, "
                f"60-day percentage change, token distribution percentages, governance metrics, team experience, "
                f"and comparisons with Ethereum, Solana, and Avalanche). "
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

    # NEW: Added method to format tokenomics with data from API
    def _format_tokenomics(self, state: ResearchState) -> str:
        """Format tokenomics data from the state."""
        # Get data from coingecko if available
        coin_data = state.coingecko_data if hasattr(state, 'coingecko_data') else {}
        
        # Extract tokenomics data
        total_supply = coin_data.get("total_supply", "Data unavailable")
        circulating_supply = coin_data.get("circulating_supply", "Data unavailable")
        
        # Format into readable text
        tokenomics = (
            f"Tokenomics for {state.project_name}\n\n"
            f"Total Supply: {total_supply:,} tokens\n"
            f"Circulating Supply: {circulating_supply:,} tokens\n"
        )
        
        # Add token distribution if available
        if coin_data.get("token_distribution"):
            tokenomics += "\nToken Distribution:\n"
            for allocation in coin_data.get("token_distribution", []):
                category = allocation.get("category", "Unknown")
                percentage = allocation.get("percentage", 0)
                tokenomics += f"- {category}: {percentage}%\n"
                
        return tokenomics

class ResearchOrchestrator:
    """Orchestrates the research process using ResearchManager."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, config_path: str = None):
        self.llm = llm
        self.logger = logger
        self.config_path = config_path
        self.report_config = {}
        self._load_report_config()
        
    def _load_report_config(self) -> Dict[str, Any]:
        """Load the report configuration file."""
        try:
            if self.config_path and os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    self.report_config = json.load(f)
                self.logger.info(f"Loaded report configuration from {self.config_path}")
            else:
                self.logger.warning(f"Report configuration file not found at {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error loading report configuration: {str(e)}")
        return self.report_config
        
    def research(self, project_name: str) -> ResearchState:
        """Execute the research process using ResearchManager."""
        self.logger.info(f"ResearchOrchestrator starting research for {project_name}")
        
        # Create a ResearchManager instance
        manager = ResearchManager(
            llm=self.llm,
            logger=self.logger,
            config_path=self.config_path
        )
        
        # Pass our report_config to the manager if we have one
        if self.report_config:
            manager.report_config = self.report_config
            self.logger.debug("Transferred report_config to ResearchManager")
            
        # Execute the research
        state = manager.research(project_name)
        
        # Make sure the report_config is set on the state
        if not hasattr(state, 'report_config') or not state.report_config:
            state.report_config = manager.report_config
            self.logger.info("Set report_config on state object from manager")
        
        # Initialize additional fields for compatibility with main ResearchState
        if not hasattr(state, 'missing_data_fields'):
            state.missing_data_fields = []
            
        if not hasattr(state, 'visualizations'):
            state.visualizations = {}
            
        if not hasattr(state, 'outputDir'):
            state.outputDir = os.path.join("docs", state.project_name.lower().replace(" ", "_"))
            # Create output directory if it doesn't exist
            os.makedirs(state.outputDir, exist_ok=True)
            
        if not hasattr(state, 'draft'):
            state.draft = ""
            
        if not hasattr(state, 'final_report'):
            state.final_report = ""
            
        if not hasattr(state, 'key_features'):
            state.key_features = ""
            
        # Make sure the structured_data field exists and is properly initialized
        if not hasattr(state, 'structured_data') or not state.structured_data:
            state.structured_data = {}
            
        # Make sure research_data exists for backward compatibility
        if not hasattr(state, 'research_data'):
            state.research_data = state.structured_data.copy() if hasattr(state, 'structured_data') else {}
            
        # Ensure errors list is initialized
        if not hasattr(state, 'errors'):
            state.errors = []
            
        self.logger.info(f"ResearchOrchestrator completed research for {project_name}")
        return state