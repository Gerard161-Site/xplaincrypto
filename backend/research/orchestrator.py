import json
import os
from typing import Dict, Any, List, Optional
import logging
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import random
import asyncio

from backend.state import ResearchState
from backend.research.core import ResearchNode, ResearchType
from backend.research.agents import get_agent_for_research_type
from backend.retriever.huggingface_search import HuggingFaceSearch
from backend.retriever.tavily_search import TavilySearch
from backend.utils.inference import infer_missing_data


CACHE_DIR = os.path.join("docs", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class ResearchManager:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, config_path: str = None):
        self.llm = llm
        self.logger = logger
        self.config_path = config_path or "backend/config/report_config.json"
        self.report_config = self._load_report_config()

    async def research(self, project_name: str, state: ResearchState = None) -> ResearchState:
        state = state or ResearchState(project_name=project_name)
        if not state.report_config:
            state.report_config = self.report_config
            self.logger.debug(f"Assigned report_config from ResearchManager to state: {len(state.report_config.get('sections', []))} sections")
        
        # Log initial state
        self.logger.debug(f"Initial state.root_node: {state.root_node.query if state.root_node else 'None'}, children: {len(state.root_node.children) if state.root_node else 0}")
        
        # Use existing tree if populated, otherwise generate
        if not state.root_node or not state.root_node.children:
            state = self._generate_research_tree(state)
        else:
            self.logger.info(f"Using pre-populated research tree with {len(state.root_node.children)} sections")
        
        state = self._gather_data(state)
        state = await self._conduct_research(state)
        state = self._synthesize_findings(state)
        return state

    def _load_report_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                self.logger.info(f"Loaded report configuration from {self.config_path} with {len(config.get('sections', []))} sections")
                return config
            else:
                self.logger.error(f"Report configuration file not found at {self.config_path}")
                raise FileNotFoundError(f"Report config not found at {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error loading report configuration: {str(e)}")
            raise

    def _generate_research_tree(self, state: ResearchState) -> ResearchState:
        self.logger.info(f"Generating research tree for {state.project_name}")
        state.update_progress(f"Planning research for {state.project_name}...")
        if not state.root_node:
            root_query = f"Comprehensive analysis of {state.project_name} cryptocurrency"
            state.root_node = ResearchNode(query=root_query, research_type=ResearchType.TECHNICAL)
            self.logger.debug(f"Initialized root node: {root_query}")
        
        self._generate_config_based_tree(state)
        state.tree_generated = True
        self.logger.info(f"Research tree generated with {len(state.root_node.children)} sections")
        if not state.root_node.children:
            self.logger.error("No sections added to research tree; check report_config and ResearchNode.add_child")
            self.logger.debug(f"state.report_config sections: {len(state.report_config.get('sections', []))}")
        state.update_progress(f"Research plan created with {len(state.root_node.children)} primary topics")
        return state

    def _generate_config_based_tree(self, state: ResearchState) -> None:
        self.logger.info("Generating research tree based on report configuration")
        sections = state.report_config.get("sections", [])
        if not sections:
            self.logger.error("No sections found in state.report_config")
            self.logger.debug(f"Full state.report_config: {json.dumps(state.report_config, indent=2)}")
            return
        for section in sections:
            section_title = section.get("title", "")
            if not section_title:
                self.logger.warning("Skipping section with no title")
                continue
            description = section.get("description", section.get("prompt", ""))
            data_sources = section.get("data_sources", [])
            visualizations = section.get("visualizations", [])
            
            research_type = self._determine_research_type(section_title)
            section_query = f"{section_title} of {state.project_name}"
            section_node = state.root_node.add_child(query=section_query, research_type=research_type)
            self.logger.debug(f"Added section node: {section_query}, children count: {len(state.root_node.children)}")
            
            data_fields = self._get_data_fields_for_section(section, state.report_config)
            for data_field, source_info in data_fields.items():
                source = source_info.get('source', 'web_research')
                field_query = f"{data_field} of {state.project_name}"
                section_node.add_child(query=field_query, research_type=research_type, data_field=data_field, source=source)
                self.logger.debug(f"Added data field node: {field_query}, section children: {len(section_node.children)}")
            
            if description:
                analysis_query = f"Analysis: {description} for {state.project_name}"
                section_node.add_child(query=analysis_query, research_type=research_type)
                self.logger.debug(f"Added analysis node: {analysis_query}, section children: {len(section_node.children)}")
    def _get_data_fields_for_section(self, section: Dict[str, Any], report_config: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        data_fields = {}
        vis_types = report_config.get("visualization_types", {})
        for vis_name in section.get("visualizations", []):
            if vis_name in vis_types:
                vis_config = vis_types[vis_name]
                source = vis_config.get("data_source", "web_research")
                if "data_field" in vis_config:
                    field = vis_config["data_field"]
                    data_fields[field] = {"source": source}
                if "data_fields" in vis_config:
                    for field in vis_config["data_fields"]:
                        data_fields[field] = {"source": source}
        return data_fields

    def _gather_data(self, state: ResearchState) -> ResearchState:
        self.logger.info(f"Gathering data for {state.project_name}")
        state.update_progress(f"Gathering real-time data for {state.project_name}...")
        # Commenting out DataGatherer instantiation as the class is undefined
        # data_gatherer = DataGatherer(state.project_name, self.logger)
        try:
            data_sources = set()
            for section in state.report_config.get("sections", []):
                data_sources.update(section.get("data_sources", []))
            data_sources = list(data_sources) or ["coingecko", "coinmarketcap", "defillama"]
            self.logger.info(f"Using data sources: {', '.join(data_sources)}")
            
            competitors = ["ethereum", "solana", "avalanche-2"]
            competitor_data = {}
            for comp in competitors:
                # Commenting out import from deleted file
                # from backend.research.data_modules import CoinGeckoModule
                # comp_module = CoinGeckoModule(comp, self.logger)
                # comp_data = comp_module.gather_data(use_cache=True)
                # if "error" not in comp_data:
                #     competitor_data[comp] = comp_data
                pass # Skip competitor data gathering for now
            state.data["competitors"] = competitor_data
            self.logger.info(f"Skipped competitor data gathering. Found {len(competitor_data)} cached competitors.")
            
            cached_data = self._try_load_from_cache(state.project_name)
            if cached_data:
                self.logger.info(f"Using cached data for {state.project_name} for initial report")
                state.data = cached_data
                if "coingecko" in cached_data:
                    state.coingecko_data = cached_data["coingecko"]
                if "coinmarketcap" in cached_data:
                    state.coinmarketcap_data = cached_data["coinmarketcap"]
                if "defillama" in cached_data:
                    state.defillama_data = cached_data["defillama"]
                state.data_gathered = True
                state.price_analysis = self._format_price_analysis(state)
                state.tokenomics = self._format_tokenomics(state)
                # Commenting out as data_gatherer is undefined
                # self._refresh_data_async(state, data_gatherer, data_sources)
                return state

            # Commenting out usage as data_gatherer is undefined
            # state.data = data_gatherer.gather_all_data()
            # Initialize state.data if not already done (e.g., from cache)
            if not hasattr(state, 'data') or not state.data:
                state.data = {}
                self.logger.warning("Initialized state.data as empty dict because DataGatherer is commented out.")
                
            if "coingecko" in state.data:
                state.coingecko_data = state.data["coingecko"]
            if "coinmarketcap" in state.data:
                state.coinmarketcap_data = state.data["coinmarketcap"]
            if "defillama" in state.data:
                state.defillama_data = state.data["defillama"]
            state.data_gathered = True
            state.price_analysis = self._format_price_analysis(state)
            state.tokenomics = self._format_tokenomics(state)
            return state
        except Exception as e:
            self.logger.error(f"Error gathering data: {str(e)}", exc_info=True)
            state.update_progress(f"Error gathering data: {str(e)}")
            state.errors.append(str(e))
            state.data = {}
            state.data_gathered = False
            return state

    def _try_load_from_cache(self, project_name: str) -> Optional[Dict[str, Any]]:
        try:
            combined_cache = {}
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
            return combined_cache if combined_cache else None
        except Exception as e:
            self.logger.warning(f"Error loading cache: {str(e)}")
            return None

    def _refresh_data_async(self, state: ResearchState, data_gatherer, data_sources):
        self.logger.info("Would refresh data in background (not implemented)")

    def _format_price_analysis(self, state: ResearchState) -> str:
        # First try to get data from attributes for backward compatibility
        if hasattr(state, 'coingecko_data') and state.coingecko_data:
            price_data = state.coingecko_data
        elif hasattr(state, 'data') and state.data and "coingecko" in state.data:
            price_data = state.data.get("coingecko", {})
        # Then try dictionary access
        elif "coingecko_data" in state:
            price_data = state["coingecko_data"]
        elif "data" in state and "coingecko" in state["data"]:
            price_data = state["data"].get("coingecko", {})
        else:
            price_data = {}
            
        # Get project name
        project_name = state["project_name"] if "project_name" in state else getattr(state, "project_name", "Unknown Cryptocurrency")
            
        if not price_data or "current_price" not in price_data:
            return f"Price analysis for {project_name}.\n60-Day Change: Data unavailable."
            
        current_price = price_data.get("current_price", 0)
        market_cap = price_data.get("market_cap", 0)
        price_history = price_data.get("price_history", [])
        sixty_day_change = "Data unavailable"
        if price_history and len(price_history) >= 60:
            old_price = price_history[-60][1] if isinstance(price_history[-60], list) else price_history[-60]
            sixty_day_change = f"{((current_price - old_price) / old_price * 100):.2f}%"
        return (
            f"Price analysis for {project_name}\n\n"
            f"Current Price: ${current_price:.4f}\n"
            f"Market Cap: ${market_cap:,}\n"
            f"60-Day Change: {sixty_day_change}"
        )

    def _format_tokenomics(self, state: ResearchState) -> str:
        # First try to get data from attributes for backward compatibility
        if hasattr(state, 'coingecko_data') and state.coingecko_data:
            coin_data = state.coingecko_data
        elif hasattr(state, 'data') and state.data and "coingecko" in state.data:
            coin_data = state.data.get("coingecko", {})
        # Then try dictionary access
        elif "coingecko_data" in state:
            coin_data = state["coingecko_data"] 
        elif "data" in state and "coingecko" in state["data"]:
            coin_data = state["data"].get("coingecko", {})
        else:
            coin_data = {}
            
        # Get project name
        project_name = state["project_name"] if "project_name" in state else getattr(state, "project_name", "Unknown Cryptocurrency")
        
        # Convert numeric values to string if not available
        total_supply = coin_data.get("total_supply", "Data unavailable")
        if total_supply != "Data unavailable":
            total_supply_str = f"{total_supply:,}"
        else:
            total_supply_str = "Data unavailable"
            
        circulating_supply = coin_data.get("circulating_supply", "Data unavailable")
        if circulating_supply != "Data unavailable":
            circulating_supply_str = f"{circulating_supply:,}"
        else:
            circulating_supply_str = "Data unavailable"
            
        return (
            f"Tokenomics for {project_name}\n\n"
            f"Total Supply: {total_supply_str} tokens\n"
            f"Circulating Supply: {circulating_supply_str} tokens\n"
        )

    async def _conduct_research(self, state: ResearchState) -> ResearchState:
        # Get project name 
        project_name = state["project_name"] if "project_name" in state else getattr(state, "project_name", "Unknown Project")
        
        self.logger.info(f"Conducting research for {project_name}")
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Researching {project_name}...")
        else:
            state["progress"] = f"Researching {project_name}..."
            
        if not state.get("root_node") and not hasattr(state, "root_node"):
            self.logger.error("Cannot conduct research: research tree not generated")
            if hasattr(state, 'errors') and isinstance(state.errors, list):
                state.errors.append("Research tree not generated") 
            else:
                state["errors"] = state.get("errors", []) + ["Research tree not generated"]
            return state

        all_references = []
        tavily = TavilySearch(logger=self.logger)
        hf_search = HuggingFaceSearch(api_token=os.getenv("HUGGINGFACE_API_KEY"), logger=self.logger)

        nodes_to_research = []
        
        root_node = state.get("root_node") if hasattr(state, "get") else state.root_node
        
        def collect_nodes(node):
            if node.data_field and self._get_api_data_for_field(node.data_field, node.source, state.get("data") if hasattr(state, "get") else state.data) is None:
                nodes_to_research.append(node)
            elif not node.data_field:
                nodes_to_research.append(node)
            for child in node.children:
                collect_nodes(child)

        collect_nodes(root_node)
        self.logger.info(f"Found {len(nodes_to_research)} nodes requiring web research")

        queries = [node.query for node in nodes_to_research]
        batches = tavily.batch_queries(queries, batch_size=4)
        self.logger.info(f"Batched into {len(batches)} groups")

        # Access data using dictionary get method with fallback to attribute
        state_data = state.get("data", {}) if hasattr(state, "get") else state.data
        state_research_data = state.get("research_data", {}) if hasattr(state, "get") else state.research_data
        combined_data = {**state_data, **state_research_data}
        
        for batch in batches:
            results = await tavily.search_batch(batch)
            for node, result in zip([n for n in nodes_to_research if n.query in batch], results):
                research_type = node.research_type or self._determine_research_type(node.query)
                agent = get_agent_for_research_type(research_type, self.llm, self.logger)
                if "needs_inference" in result:
                    self.logger.info(f"Tavily failed for {node.query}, inferring data with Hugging Face")
                    required_fields = [node.data_field] if node.data_field else ["summary"]
                    inferred = infer_missing_data(hf_search, combined_data, required_fields, project_name, self.logger)
                    if node.data_field:
                        node.structured_data[node.data_field] = inferred.get(node.data_field, "")
                        node.summary = f"{node.data_field}: {node.structured_data[node.data_field]}"
                    else:
                        node.summary = inferred.get("summary", f"No data inferred for {node.query}")
                    node.references = [{"title": "Hugging Face Inference", "url": "https://huggingface.co"}]
                else:
                    node.content = "\n\n".join([r["body"] for r in result["results"]]) if result["results"] else ""
                    node.references = [{"title": r["body"][:50] + "..." if r["body"] else "Untitled", "url": r["href"]} 
                                      for r in result["results"]] if result["results"] else []
                    node.summary = agent._summarize_content(node.content, node.query) if node.content else f"No data available for {node.query}"
                all_references.extend([r for r in node.references if r["url"] not in [ref["url"] for ref in all_references]])

        # Update state with references
        if hasattr(state, 'references'):
            state.references = all_references
        else:
            state["references"] = all_references
            
        # Mark research as complete
        if hasattr(state, 'research_complete'):
            state.research_complete = True
        else:
            state["research_complete"] = True
            
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Research completed with {len(all_references)} sources")
        else:
            state["progress"] = f"Research completed with {len(all_references)} sources"
            
        return state

    def _get_api_data_for_field(self, data_field: str, source: str, api_data: Dict[str, Any]) -> Any:
        if not source or source == "web_research" or source not in api_data:
            return None
        source_data = api_data.get(source, {})
        if data_field in source_data:
            return source_data[data_field]
        if "multi" in api_data and data_field in api_data["multi"]:
            return api_data["multi"][data_field]
        return None

    def _determine_research_type(self, query: str) -> str:
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
        # Get project name
        project_name = state["project_name"] if "project_name" in state else getattr(state, "project_name", "Unknown Project")
        
        self.logger.info(f"Synthesizing findings for {project_name}")
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Synthesizing research on {project_name}...")
        else:
            state["progress"] = f"Synthesizing research on {project_name}..."
            
        # Check if research is complete
        root_node = state.get("root_node") if hasattr(state, "get") else getattr(state, "root_node", None)
        research_complete = state.get("research_complete", False) if hasattr(state, "get") else getattr(state, "research_complete", False)
        
        if not root_node or not research_complete:
            self.logger.error("Cannot synthesize: research not complete")
            
            # Add error message
            if hasattr(state, 'errors'):
                state.errors.append("Research not complete")
            else:
                state["errors"] = state.get("errors", []) + ["Research not complete"]
                
            return state

        try:
            all_summaries = self._collect_all_summaries(root_node)
            
            # Get report config
            report_config = state.get("report_config", {}) if hasattr(state, "get") else getattr(state, "report_config", {})
            report_categories = [section["title"] for section in report_config.get("sections", []) if section.get("required", True)]
            
            # Collect content from various attributes/keys
            content_items = []
            
            # Add all summaries
            content_items.extend(all_summaries)
            
            # Add attributes if they exist
            for attr in ["tokenomics", "price_analysis", "governance", "team_and_development"]:
                # Try dictionary access first
                if attr in state:
                    content = state[attr]
                    if content:
                        content_items.append("\n\n" + content)
                # Then try attribute access
                elif hasattr(state, attr):
                    content = getattr(state, attr, "")
                    if content:
                        content_items.append("\n\n" + content)
            
            # Add competitor data
            state_data = state.get("data", {}) if hasattr(state, "get") else getattr(state, "data", {}) 
            competitor_data = json.dumps(state_data.get("competitors", {}), indent=2)
            content_items.append("\n\nCompetitor Data:\n" + competitor_data)
            
            # Join all content
            joined_content = "\n\n".join(content_items)
            
            # Create synthesis prompt
            synthesis_prompt = (
                f"Based on all this research about {project_name} cryptocurrency:\n\n"
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
            
            # Set research summary
            if hasattr(state, 'research_summary'):
                state.research_summary = summary
            else:
                state["research_summary"] = summary
                
            # Mark synthesis as complete
            if hasattr(state, 'synthesis_complete'):
                state.synthesis_complete = True
            else:
                state["synthesis_complete"] = True
                
            # Update progress
            if hasattr(state, 'update_progress'):
                state.update_progress("Research synthesis completed")
            else:
                state["progress"] = "Research synthesis completed"
                
        except Exception as e:
            self.logger.error(f"Error synthesizing findings: {str(e)}")
            
            # Add error message
            if hasattr(state, 'errors'):
                state.errors.append(f"Synthesis error: {str(e)}")
            else:
                state["errors"] = state.get("errors", []) + [f"Synthesis error: {str(e)}"]
                
            # Update progress
            if hasattr(state, 'update_progress'):
                state.update_progress(f"Error in research synthesis: {str(e)}")
            else:
                state["progress"] = f"Error in research synthesis: {str(e)}"
                
        return state

    def _collect_all_summaries(self, node: ResearchNode) -> List[str]:
        summaries = []
        if hasattr(node, 'summary') and node.summary:
            summaries.append(f"## {node.query}\n\n{node.summary}")
        for child in node.children:
            summaries.extend(self._collect_all_summaries(child))
        return summaries

class ResearchOrchestrator:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, config_path: str = None):
        self.llm = llm
        self.logger = logger
        self.config_path = config_path
        self.report_config = {}
        self._load_report_config()

    def _load_report_config(self) -> Dict[str, Any]:
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

    def _determine_research_type(self, query: str) -> str:
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

    async def research(self, project_name: str, state: ResearchState = None) -> ResearchState:
        self.logger.info(f"ResearchOrchestrator starting research for {project_name}")
        manager = ResearchManager(llm=self.llm, logger=self.logger, config_path=self.config_path)
        if self.report_config:
            manager.report_config = self.report_config
            self.logger.debug("Transferred report_config to ResearchManager")
        
        if state is None:
            state = ResearchState(project_name=project_name)
            self.logger.debug("Created new ResearchState in orchestrator")
            if self.report_config:
                # Set report_config in state (using dict access if it's a dict, else attribute)
                if hasattr(state, "get") and callable(getattr(state, "get")):
                    state["report_config"] = self.report_config
                else:
                    state.report_config = self.report_config
                self.logger.debug("Transferred report_config to new state in orchestrator")
        
        state = await manager.research(project_name, state)
        self.logger.info(f"ResearchOrchestrator completed research for {project_name}")
        return state