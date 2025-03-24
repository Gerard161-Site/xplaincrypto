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
        
        # Consolidate all data sources
        data_sources = {
            "coingecko": state.coingecko_data if hasattr(state, 'coingecko_data') else {},
            "coinmarketcap": state.coinmarketcap_data if hasattr(state, 'coinmarketcap_data') else {},
            "defillama": state.defillama_data if hasattr(state, 'defillama_data') else {},
            "web_research": state.research_data if hasattr(state, 'research_data') else {}
        }
        
        # Log data source availability
        for source, data in data_sources.items():
            if data:
                self.logger.info(f"Found {source} data with {len(data)} fields")
            else:
                self.logger.warning(f"No {source} data available")
        
        # Create a consolidated data source
        data_sources["multi"] = {}
        for source, data in data_sources.items():
            if isinstance(data, dict):
                data_sources["multi"].update(data)
        
        # Extract and format key metrics
        key_metrics = {}
        for key, value in data_sources["multi"].items():
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
        
        # Log key metrics
        if key_metrics:
            self.logger.info("Key metrics available:")
            for key, value in key_metrics.items():
                self.logger.info(f"- {key}: {value}")
        else:
            self.logger.warning("No key metrics available")
        
        # Build the prompt with exact section titles
        sections_text = ""
        for section in report_config.get("sections", []):
            section_title = section["title"]
            # Look for min_words first, fall back to max_words for backwards compatibility
            word_count = section.get("min_words", section.get("max_words", 500))
            description = section.get("description", "")
            sources = ", ".join(section.get("data_sources", []))
            vis_types = ", ".join(section.get("visualizations", []))
            
            sections_text += f"# {section_title}\n"
            sections_text += f"- Minimum Words: {word_count}\n"
            sections_text += f"- Description: {description}\n"
            sections_text += f"- Data Sources: {sources}\n"
            sections_text += f"- Visualizations: {vis_types}\n\n"
        
        # Create the prompt with key metrics and data
        prompt = (
            f"Using the following research data about {state.project_name} cryptocurrency:\n\n"
            f"KEY METRICS (USE THESE EXACT VALUES):\n"
        )
        
        # Add key metrics
        for key, value in key_metrics.items():
            prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        prompt += "\nRESEARCH DATA:\n"
        for source, data in data_sources.items():
            if data:
                # Only include essential data in the prompt
                essential_data = {k: v for k, v in data.items() if k in key_metrics or k in ["name", "symbol", "description"]}
                prompt += f"\n{source.upper()}:\n{json.dumps(essential_data, indent=2)}\n"
        
        prompt += f"\n\nCreate a polished, professional draft report with the following sections. "
        prompt += f"Use markdown formatting with # for main sections. "
        prompt += f"IMPORTANT: Meet or exceed the Minimum Words count requirement for each section. "
        prompt += f"IMPORTANT: Use the EXACT numerical values provided in the Key Metrics section. "
        prompt += f"DO NOT use placeholders like '$X' or 'Y tokens'. "
        prompt += f"Avoid speculative claims unless labeled as such.\n\n"
        prompt += f"SECTIONS:\n{sections_text}"
        
        try:
            response = self.llm.invoke(prompt, max_completion_tokens=5000)
            draft = response.content
            
            # Check for and fix any placeholder values
            draft = self.fix_placeholder_values(draft)
            
            # Ensure section titles match exactly
            for section in report_config.get("sections", []):
                section_title = section["title"]
                # Replace any variations of the section title with the exact one
                draft = re.sub(rf'^#+\s+{re.escape(section_title)}.*$', f'# {section_title}', draft, flags=re.MULTILINE)
            
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
            
        except Exception as e:
            self.logger.error(f"Error generating draft: {str(e)}")
            return f"# {state.project_name} Research Report\n\nError generating report: {str(e)}"

def writer(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> ResearchState:
    logger.info(f"Writer agent processing for {state.project_name}")
    state.update_progress(f"Writing draft report for {state.project_name}...")
    
    writer_agent = WriterAgent(llm, logger)
    draft = writer_agent.write_draft(state)
    state.draft = draft
    state.update_progress(f"Draft report written for {state.project_name}")
    
    return state