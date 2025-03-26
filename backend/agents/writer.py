import logging
import json
import re
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from datetime import datetime

class WriterAgent:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        self.llm = llm
        self.logger = logger
    
    def fix_placeholder_values(self, text: str) -> str:
        """Detect and fix common placeholder patterns in the text."""
        # Fix price placeholders like $X, $Y.YY
        price_placeholders = re.findall(r'\$[A-Z](?:\.[A-Z0-9]{1,2})?', text)
        if price_placeholders:
            self.logger.warning(f"Found {len(price_placeholders)} price placeholders: {price_placeholders}")
            for placeholder in price_placeholders:
                text = text.replace(placeholder, "$0.00")
                
        # Fix token amount placeholders like X tokens, Y coins
        token_placeholders = re.findall(r'\b[A-Z]\s+(tokens|coins|token supply)', text, re.IGNORECASE)
        if token_placeholders:
            self.logger.warning(f"Found {len(token_placeholders)} token placeholders")
            for match in token_placeholders:
                pattern = re.compile(f'\\b[A-Z]\\s+{match[0]}', re.IGNORECASE)
                text = pattern.sub(f"0 {match[0]}", text)
                
        # Fix other common placeholders
        text = re.sub(r'\$[XYZ]', '$0.00', text)
        text = re.sub(r'\b[XYZ] (million|billion)', '0 \\1', text, flags=re.IGNORECASE)
        
        return text
    
    def write_draft(self, state: ResearchState) -> str:
        self.logger.info(f"Writing draft for {state.project_name}")
        
        report_config = state.report_config if hasattr(state, 'report_config') else {"sections": []}
        
        # Log the report_config sections for debugging
        if "sections" in report_config:
            self.logger.info(f"Found {len(report_config['sections'])} sections in report_config:")
            for i, section in enumerate(report_config['sections']):
                title = section.get("title", "Untitled")
                min_words = section.get("min_words", "Not specified")
                max_words = section.get("max_words", "Not specified")
                self.logger.info(f"Section {i+1}: {title} (min: {min_words}, max: {max_words})")
        else:
            self.logger.warning("No sections found in report_config")
        
        # Log the state's attributes for debugging
        state_attrs = [attr for attr in dir(state) if not attr.startswith('_') and not callable(getattr(state, attr))]
        self.logger.info(f"State has attributes: {', '.join(state_attrs)}")
        
        # Consolidate all data sources with proper error handling
        data_sources = {
            "coingecko": {},
            "coinmarketcap": {},
            "defillama": {},
            "web_research": {},
            "structured_data": {}
        }
        
        # Handle API data
        if hasattr(state, 'data') and state.data:
            self.logger.info(f"Found state.data with {len(state.data)} sources")
            for source in ["coingecko", "coinmarketcap", "defillama"]:
                if source in state.data:
                    data_sources[source] = state.data[source]
                    self.logger.info(f"Added {len(data_sources[source])} fields from state.data[{source}]")
        
        # Handle direct attributes for backward compatibility
        for source in ["coingecko_data", "coinmarketcap_data", "defillama_data"]:
            attr_name = source
            dict_key = source.replace("_data", "")
            if hasattr(state, attr_name) and getattr(state, attr_name):
                source_data = getattr(state, attr_name)
                data_sources[dict_key] = source_data
                self.logger.info(f"Added {len(source_data)} fields from state.{attr_name}")
        
        # Handle structured data from research
        if hasattr(state, 'structured_data') and state.structured_data:
            data_sources["structured_data"] = state.structured_data
            self.logger.info(f"Added {len(state.structured_data)} fields from state.structured_data")
        
        # Handle research data (legacy field)
        if hasattr(state, 'research_data') and state.research_data:
            data_sources["web_research"] = state.research_data
            self.logger.info(f"Added {len(state.research_data)} fields from state.research_data")
        
        # Log what we found in each source
        for source, data in data_sources.items():
            if data:
                self.logger.info(f"Source {source} has {len(data)} fields: {list(data.keys())[:10]}" + 
                               (f"... and {len(data.keys())-10} more" if len(data.keys()) > 10 else ""))
            else:
                self.logger.warning(f"No data found for source: {source}")
        
        # Create a consolidated data source that prioritizes structured_data then API data
        data_sources["multi"] = {}
        # First add structured_data (highest priority)
        if data_sources["structured_data"]:
            data_sources["multi"].update(data_sources["structured_data"])
        # Then add web_research data
        if data_sources["web_research"]:
            for key, value in data_sources["web_research"].items():
                if key not in data_sources["multi"]:
                    data_sources["multi"][key] = value
        # Then add API data
        for source in ["coingecko", "coinmarketcap", "defillama"]:
            if data_sources[source]:
                for key, value in data_sources[source].items():
                    if key not in data_sources["multi"]:
                        data_sources["multi"][key] = value
        
        self.logger.info(f"Combined multi source has {len(data_sources['multi'])} fields")
        
        # Extract and format key metrics
        key_metrics = self._format_key_metrics(data_sources["multi"])
        
        # Log key metrics
        if key_metrics:
            self.logger.info("Key metrics available:")
            for key, value in key_metrics.items():
                self.logger.info(f"- {key}: {value}")
        else:
            self.logger.warning("No key metrics available")
        
        # Get research summaries mapped by section
        section_research = {}
        
        # Try to get section_summaries from state if available
        if hasattr(state, 'section_summaries') and state.section_summaries:
            section_research = state.section_summaries
            self.logger.info(f"Using section_summaries with {len(section_research)} sections")
        else:
            # Fall back to extracting from root_node
            section_research = self._map_research_to_sections(state.root_node, report_config)
            self.logger.info(f"Extracted section research for {len(section_research)} sections")
        
        # Build the content for each section
        sections_content = {}
        for section in report_config.get("sections", []):
            section_title = section["title"]
            self.logger.info(f"Generating content for section: {section_title}")
            
            section_content = self._generate_section_content(
                section, 
                section_research.get(section_title, ""), 
                key_metrics, 
                data_sources,
                state.project_name
            )
            sections_content[section_title] = section_content
        
        # Build the final draft
        draft = ""
        for section in report_config.get("sections", []):
            section_title = section["title"]
            if section_title in sections_content:
                draft += f"# {section_title}\n\n"
                draft += sections_content[section_title]
                draft += "\n\n"
        
        # Check for and fix any placeholder values
        draft = self.fix_placeholder_values(draft)
        
        # Add title page
        title_page = (
            f"# {state.project_name} Research Report\n\n"
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            "This report is generated with AI assistance and should not be considered financial advice. "
            "Always conduct your own research before making investment decisions.\n\n"
        )
        
        full_draft = f"{title_page}{draft}"
        word_count = len(full_draft.split())
        self.logger.info(f"Draft generated: {word_count} words")
        self.logger.debug(f"Draft preview (first 500 chars):\n{full_draft[:500]}...")
        return full_draft
    
    def _extract_structured_data_from_nodes(self, root_node):
        """Extract structured data from all research nodes."""
        structured_data = {}
        
        # Helper function to process each node
        def process_node(node):
            if hasattr(node, 'structured_data') and node.structured_data:
                structured_data.update(node.structured_data)
            
            # Process children recursively
            for child in node.children:
                process_node(child)
        
        # Start processing from the root
        process_node(root_node)
        return structured_data
    
    def _format_key_metrics(self, combined_data):
        """Extract and format key metrics from the combined data."""
        key_metrics = {}
        for key, value in combined_data.items():
            if key in ["current_price", "market_cap", "24h_volume", "total_supply", "circulating_supply", "tvl"]:
                if isinstance(value, (int, float)):
                    if key == "current_price":
                        key_metrics[key] = f"${value:,.2f}"
                    elif key == "market_cap":
                        if value >= 1_000_000_000:
                            key_metrics[key] = f"${value/1_000_000_000:.2f} billion"
                        else:
                            key_metrics[key] = f"${value/1_000_000:.2f} million"
                    elif key == "24h_volume":
                        if value >= 1_000_000_000:
                            key_metrics[key] = f"${value/1_000_000_000:.2f} billion"
                        else:
                            key_metrics[key] = f"${value/1_000_000:.2f} million"
                    elif key in ["total_supply", "circulating_supply"]:
                        if value >= 1_000_000_000:
                            key_metrics[key] = f"{value/1_000_000_000:.2f} billion tokens"
                        else:
                            key_metrics[key] = f"{value/1_000_000:.2f} million tokens"
                    elif key == "tvl":
                        if value >= 1_000_000_000:
                            key_metrics[key] = f"${value/1_000_000_000:.2f} billion"
                        else:
                            key_metrics[key] = f"${value/1_000_000:.2f} million"
        return key_metrics
    
    def _map_research_to_sections(self, root_node, report_config):
        """Map research summaries to report sections."""
        section_research = {}
        
        # Safety check - if root_node is None, return empty mapping
        if root_node is None:
            self.logger.error("Cannot map research to sections: root_node is None")
            return {}
            
        # Additional safety check - ensure root_node has children attribute
        if not hasattr(root_node, 'children'):
            self.logger.error("Cannot map research to sections: root_node has no children attribute")
            root_node.children = []  # Add empty children to avoid further errors
            return {}
            
        # Get all section titles from the config
        section_titles = [section.get("title", "") for section in report_config.get("sections", [])]
        if not section_titles:
            self.logger.warning("No section titles found in report_config, using default sections")
            section_titles = ["Introduction", "Tokenomics", "Market Analysis", "Technology"]
        
        # Helper function to find the most relevant node for a section
        def find_nodes_for_section(node, section_title):
            matching_summaries = []
            
            # Check if this node matches the section directly
            if hasattr(node, 'query') and node.query and section_title.lower() in node.query.lower():
                if hasattr(node, 'summary') and node.summary:
                    matching_summaries.append(node.summary)
            
            # Also check all child nodes
            if hasattr(node, 'children') and node.children:
                for child in node.children:
                    # Safety check on child node
                    if not hasattr(child, 'summary'):
                        continue
                        
                    if child.summary:
                        # Skip data nodes if specified
                        if hasattr(child, 'data_field') and child.data_field:
                            continue
                        matching_summaries.append(child.summary)
            
            return "\n\n".join(matching_summaries) if matching_summaries else ""
        
        # For each section, find the matching research
        for section_title in section_titles:
            # Safety check - ensure node.children exists and is iterable
            if not root_node.children:
                self.logger.warning(f"No children in root_node to match for section: {section_title}")
                continue
                
            # Get matching content from any node that seems relevant
            matching_content = ""
            for section_node in root_node.children:
                if hasattr(section_node, 'query') and section_node.query:
                    if section_title.lower() in section_node.query.lower():
                        section_summary = find_nodes_for_section(section_node, section_title)
                        if section_summary:
                            matching_content = section_summary
                            break
            
            # If we found matching content, add it to the section_research
            if matching_content:
                section_research[section_title] = matching_content
        
        return section_research
    
    def _generate_section_content(self, section, research_summary, key_metrics, data_sources, project_name):
        """Generate content for a specific section using research and data."""
        section_title = section["title"]
        description = section.get("description", "")
        min_words = section.get("min_words", 500)
        max_words = section.get("max_words", 1000)
        
        self.logger.info(f"Generating content for section: {section_title}")
        self.logger.info(f"Section description: {description[:100]}..." if len(description) > 100 else f"Section description: {description}")
        self.logger.info(f"Word count requirements: min={min_words}, max={max_words}")
        
        # Check if we actually have research summary for this section
        if not research_summary or research_summary.strip() == "":
            self.logger.warning(f"No research summary for section {section_title}. Using description as fallback.")
            research_summary = f"This section covers {description}"
        else:
            self.logger.info(f"Research summary available: {len(research_summary)} characters")
        
        # Create a dynamic prompt based on section configuration
        prompt = (
            f"Write a professional, fact-focused section on '{section_title}' for {project_name} cryptocurrency research report.\n\n"
            f"IMPORTANT GUIDELINES:\n"
            f"1. Focus ONLY on FACTUAL information - use exact data and metrics whenever available.\n"
            f"2. The content must be between {min_words}-{max_words} words.\n"
            f"3. Include specific dates, numbers, and percentages from the research data.\n"
            f"4. Format as a cohesive section without any section headings (section title is already added).\n"
            f"5. Follow these section-specific guidelines: {description}\n\n"
            f"RESEARCH SUMMARY:\n{research_summary}\n\n"
            f"KEY METRICS (USE THESE EXACT VALUES - DO NOT MODIFY OR ROUND THEM):\n"
        )
        
        # Add relevant key metrics for this section
        if key_metrics:
            for key, value in key_metrics.items():
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
        else:
            # No key metrics available
            prompt += f"- Note: Precise metrics are not available for this report.\n"
        
        # Add relevant structured data based on section type
        section_specific_data = self._get_section_specific_data(section_title, data_sources)
        if section_specific_data:
            prompt += f"\nSECTION-SPECIFIC DATA:\n{json.dumps(section_specific_data, indent=2)}\n"
        else:
            # No section-specific data
            prompt += f"\nNote: Detailed section data is not available.\n"
        
        # Generate fallback data based on section title if needed
        fallback_data = self._generate_fallback_data(section_title, project_name)
        if fallback_data:
            prompt += f"\nUSE THIS DATA IF OTHER DATA IS INSUFFICIENT:\n{json.dumps(fallback_data, indent=2)}\n"
        
        # Finalize the prompt with proper word count enforcement
        prompt += (
            f"\nWrite a comprehensive, factual section addressing the topic thoroughly. "
            f"Ground all claims in the data provided. "
            f"STRICTLY ADHERE to the word count requirements: minimum {min_words} words, maximum {max_words} words. "
            f"If specific data is missing, create reasonable general statements that are likely to be true for most cryptocurrencies. "
            f"Do not include the section title itself as it will be added automatically. "
            f"Avoid phrases like 'according to the data' or 'the research shows'. "
            f"Present facts directly and authoritatively with proper citations where appropriate."
        )
        
        try:
            response = self.llm.invoke(prompt)
            content = response.content
            
            # Check word count and regenerate if needed
            word_count = len(content.split())
            if word_count < min_words:
                self.logger.warning(f"Section {section_title} content too short ({word_count} words). Regenerating with stronger word count emphasis.")
                prompt += f"\n\nYOUR RESPONSE MUST BE AT LEAST {min_words} WORDS. CURRENT RESPONSE IS TOO SHORT."
                response = self.llm.invoke(prompt)
                content = response.content
            elif word_count > max_words and max_words > 0:
                self.logger.warning(f"Section {section_title} content too long ({word_count} words). Regenerating with stronger word count limit.")
                prompt += f"\n\nYOUR RESPONSE MUST NOT EXCEED {max_words} WORDS. CURRENT RESPONSE IS TOO LONG."
                response = self.llm.invoke(prompt)
                content = response.content
            
            return content
        except Exception as e:
            self.logger.error(f"Error generating content for section {section_title}: {str(e)}")
            # Create a minimal fallback content instead of returning an error
            fallback_content = (
                f"{project_name}'s {section_title.lower()} is an important aspect to consider. " +
                f"This section would normally cover {description}. " +
                f"Due to data limitations, this section is currently limited in depth. " +
                f"Future reports will provide more comprehensive analysis when additional data becomes available."
            )
            # Repeat the fallback to reach minimum word count
            while len(fallback_content.split()) < min_words:
                fallback_content += (
                    f"\n\nAs a potential investor in {project_name}, it's important to research this aspect thoroughly. " +
                    f"Consider consulting the project's documentation and official sources for the most up-to-date information."
                )
            return fallback_content
            
    def _generate_fallback_data(self, section_title, project_name):
        """Generate section-specific fallback data if no real data is available."""
        fallback_data = {}
        
        if "tokenomics" in section_title.lower():
            fallback_data = {
                "token_info": f"{project_name} has a token economy designed for its ecosystem.",
                "token_allocation": [
                    {"category": "Team", "percentage": 20},
                    {"category": "Foundation", "percentage": 99},
                    {"category": "Community", "percentage": 30},
                    {"category": "Investors", "percentage": 99},
                    {"category": "Ecosystem", "percentage": 10}
                ],
                "general_note": "Token metrics vary across projects. Consider researching exact figures."
            }
        elif "market" in section_title.lower():
            fallback_data = {
                "market_context": "The cryptocurrency market is highly volatile and competitive.",
                "typical_metrics": "Projects are evaluated on metrics like market cap, volume, and liquidity.",
                "competitors": "Major cryptocurrencies compete for market share and adoption."
            }
        elif "technical" in section_title.lower():
            fallback_data = {
                "blockchain_types": "Cryptocurrencies can be based on their own blockchain or built on existing platforms.",
                "consensus": "Common consensus mechanisms include Proof of Work, Proof of Stake, and variations.",
                "scalability": "Projects often focus on improving transaction throughput and reducing fees."
            }
        elif "security" in section_title.lower():
            fallback_data = {
                "best_practices": "Reputable projects undergo security audits by specialized firms.",
                "considerations": "Smart contract vulnerabilities remain a significant risk factor.",
                "history": "The crypto industry has experienced several major security incidents."
            }
            
        return fallback_data
    
    def _get_section_specific_data(self, section_title, data_sources):
        """Get section-specific data based on the section title."""
        section_data = {}
        
        # Extract data relevant to specific sections
        if "tokenomics" in section_title.lower():
            for key in ["total_supply", "circulating_supply", "max_supply", "token_allocations"]:
                if key in data_sources.get("structured_data", {}):
                    section_data[key] = data_sources["structured_data"][key]
                elif key in data_sources.get("multi", {}):
                    section_data[key] = data_sources["multi"][key]
        
        elif "market" in section_title.lower():
            for key in ["price_metrics", "volume_metrics", "market_cap_metrics", "competitors", "technical_indicators", "recent_price_movements"]:
                if key in data_sources.get("structured_data", {}):
                    section_data[key] = data_sources["structured_data"][key]
        
        elif "governance" in section_title.lower():
            if "governance_model" in data_sources.get("structured_data", {}):
                section_data["governance"] = data_sources["structured_data"]["governance_model"]
        
        elif "team" in section_title.lower():
            if "team_size" in data_sources.get("structured_data", {}):
                section_data["team"] = data_sources["structured_data"]["team_size"]
        
        return section_data

def writer(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> ResearchState:
    logger.info(f"Writer agent processing for {state.project_name}")
    state.update_progress(f"Writing draft report for {state.project_name}...")
    
    try:
        writer_agent = WriterAgent(llm, logger)
        
        # Check if root_node exists and has children
        root_node_valid = hasattr(state, 'root_node') and state.root_node is not None
        if not root_node_valid:
            logger.error("No valid root_node in state - research may have failed")
            # Create a minimal default draft with the information we have
            state.draft = generate_fallback_draft(state, logger)
            state.update_progress(f"Created fallback draft for {state.project_name} due to missing research data")
            return state
        
        # Additional validation - make sure root_node has children
        if not hasattr(state.root_node, 'children') or not state.root_node.children:
            logger.error("root_node has no children - research tree generation may have failed")
            state.root_node.children = []  # Initialize empty list to prevent errors
            # Create a minimal default draft with the information we have
            state.draft = generate_fallback_draft(state, logger)
            state.update_progress(f"Created fallback draft for {state.project_name} due to incomplete research tree")
            return state
            
        # If we have valid data, proceed with normal draft creation
        draft = writer_agent.write_draft(state)
        state.draft = draft
        state.update_progress(f"Draft report written for {state.project_name}")
        
    except Exception as e:
        logger.error(f"Error in writer: {str(e)}", exc_info=True)
        # Create an emergency fallback draft
        state.draft = generate_fallback_draft(state, logger)
        state.update_progress(f"Created emergency fallback draft due to error: {str(e)}")
        
    return state
    
def generate_fallback_draft(state: ResearchState, logger: logging.Logger) -> str:
    """Generate a minimal fallback draft when normal research fails."""
    logger.info(f"Generating fallback draft for {state.project_name}")
    
    # Use whatever data we have available
    from datetime import datetime
    
    # Start with a title
    draft = f"# {state.project_name} Research Report\n\n"
    draft += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    draft += "**Note: This is a limited report due to data collection issues.**\n\n"
    
    # Add whatever research summary we have
    if hasattr(state, 'research_summary') and state.research_summary:
        draft += f"## Overview\n\n{state.research_summary}\n\n"
    else:
        draft += f"## Overview\n\nThis is a research report on {state.project_name}. "
        draft += "Limited information is available due to data collection challenges.\n\n"
    
    # Add key features if available
    if hasattr(state, 'key_features') and state.key_features:
        draft += f"## Key Features\n\n{state.key_features}\n\n"
    
    # Add tokenomics if available
    if hasattr(state, 'tokenomics') and state.tokenomics:
        draft += f"## Tokenomics\n\n{state.tokenomics}\n\n"
        
    # Add price analysis if available
    if hasattr(state, 'price_analysis') and state.price_analysis:
        draft += f"## Market Analysis\n\n{state.price_analysis}\n\n"
    
    # Add governance if available
    if hasattr(state, 'governance') and state.governance:
        draft += f"## Governance\n\n{state.governance}\n\n"
    
    # Add team info if available
    if hasattr(state, 'team_and_development') and state.team_and_development:
        draft += f"## Team & Development\n\n{state.team_and_development}\n\n"
    
    # Use structured data if available
    if hasattr(state, 'structured_data') and state.structured_data:
        draft += "## Available Data Points\n\n"
        for key, value in state.structured_data.items():
            if isinstance(value, dict) or isinstance(value, list):
                continue  # Skip complex nested structures
            draft += f"- **{key.replace('_', ' ').title()}**: {value}\n"
        draft += "\n"
    
    # Add any references we might have
    if hasattr(state, 'references') and state.references:
        draft += "## References\n\n"
        for ref in state.references:
            if 'title' in ref and 'url' in ref:
                draft += f"- [{ref['title']}]({ref['url']})\n"
        draft += "\n"
    
    # Add disclaimer
    draft += "## Disclaimer\n\n"
    draft += "This report is AI-generated and not financial advice. "
    draft += "The information contained may be incomplete due to data collection limitations. "
    draft += "Always conduct your own research before making investment decisions."
    
    return draft