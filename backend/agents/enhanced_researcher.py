import os
import json
import logging
import re
import datetime
from typing import Dict, List, Any, Optional
from backend.state import ResearchState
from backend.research.core import ResearchNode, ResearchType
from langchain_openai import ChatOpenAI
from backend.research.orchestrator import ResearchOrchestrator
from backend.retriever.huggingface_search import HuggingFaceSearch
from dotenv import load_dotenv
import asyncio
from backend.retriever.data_gatherer import DataGatherer
from backend.utils.logging_utils import log_safe  # Import from utils
from backend.utils.json_encoder import dump_with_custom_encoder  # Import custom JSON encoder

load_dotenv()

# Load API tokens
hf_api_token = os.environ.get("HUGGINGFACE_API_KEY")

CACHE_DIR = os.path.join("docs", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_filename(project_name: str) -> str:
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', project_name.lower())
    return os.path.join(CACHE_DIR, f"{safe_name}_research.json")

async def enhanced_researcher(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    # Debug log the entire state
    logger.info(f"Enhanced researcher received state keys: {list(state.keys())}")
    
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

    def extract_from_web_research(web_research: Dict, section_title: str) -> str:
        content = []
        for query, summary in web_research.items():
            if not isinstance(summary, str) or not summary.strip():
                continue
            if section_title.lower() in query.lower():
                content.append(summary)
                logger.info(f"Extracted content for '{section_title}' from query '{query}'")
        return "\n\n".join(content) if content else ""

    def cache_results(state_dict: Dict, cache_file: str) -> None:
        # Ensure project_name is set correctly before caching
        if "project_name" in state_dict and state_dict["project_name"] != project_name:
            logger.warning(f"Project name mismatch before caching: {state_dict['project_name']} != {project_name}")
            state_dict["project_name"] = project_name
            
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as f:
            # Use custom JSON encoder to handle ResearchNode objects
            dump_with_custom_encoder(state_dict, f)
        logger.info(f"Cached research data to {cache_file}")

    async def generate_queries(project_name: str, report_config: Dict) -> List[str]:
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
                # Extract section title from query for better synthetic content
                parts = q.split()
                if len(parts) > 1:
                    section_title = ' '.join(parts[1:3])  # Use a couple words after project name
                else:
                    section_title = "general info"
                    
                # Try Tavily search
                results = await tavily.search_batch([q], max_results=30)
                if results and isinstance(results[0], dict) and "results" in results[0]:
                    result_items = results[0]["results"]
                    if result_items:
                        # Process and concatenate valid content
                        summaries = [res.get("body", "") for res in result_items if res.get("body")]
                        content = "\n\n".join(summaries)[:2000]
                        if content.strip():
                            logger.info(f"Got valid Tavily content for '{q}'")
                            return content
                
                # If we reach here, Tavily didn't return valid results
                logger.warning(f"No valid content from Tavily for '{q}', generating synthetic content")
                
                # Generate more specific synthetic content
                synthetic_content = (
                    f"Information about {project_name}'s {section_title}. {project_name} is a cryptocurrency "
                    f"with various features and capabilities in the blockchain space. This section would typically "
                    f"cover detailed information about {project_name}'s {section_title}, including key metrics, "
                    f"comparisons with competitors, and relevant analysis based on current market data. "
                    f"For accurate information, please refer to {project_name}'s official documentation and "
                    f"reliable cryptocurrency analytics platforms."
                )
                return synthetic_content
                
            except Exception as e:
                logger.error(f"Tavily search failed for '{q}': {str(e)}")
                # Return a more informative placeholder that mentions the error
                return f"Research data for {project_name} could not be retrieved due to search service unavailability. Please try again later or check alternative sources for information about {project_name}."

        tasks = [search_with_fallback(q) for q in queries]
        results = await asyncio.gather(*tasks)
        return results

    async def infer_missing_section_content(state_dict: Dict, section_title: str, description: str) -> str:
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

    try:
        config_path = config.get("config_path", "backend/config/report_config.json") if config else "backend/config/report_config.json"
        orchestrator = ResearchOrchestrator(llm=llm, logger=logger, config_path=config_path)
        if not orchestrator.report_config:
            orchestrator.report_config = state["report_config"]

        # Web Search
        state["queries"] = await generate_queries(project_name, state["report_config"])
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
                content = await infer_missing_section_content(state, section_title, description)
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
        logger.error(f"Error in enhanced research: {str(e)}", exc_info=True)
        state["errors"] = state.get("errors", []) + [str(e)]
        state["progress"] = f"Error in research: {str(e)}"
        
        # Ensure project_name is preserved even after error
        state["project_name"] = project_name
        return state

def enhanced_researcher_sync(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    return asyncio.run(enhanced_researcher(state, llm, logger, config))