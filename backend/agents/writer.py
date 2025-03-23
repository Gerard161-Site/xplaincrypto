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
        data_sources = {
            "coingecko": state.coingecko_data if hasattr(state, 'coingecko_data') else {},
            "coinmarketcap": state.coinmarketcap_data if hasattr(state, 'coinmarketcap_data') else {},
            "defillama": state.defillama_data if hasattr(state, 'defillama_data') else {},
            "web_research": state.research_data if hasattr(state, 'research_data') else {},
            "multi": {**state.coingecko_data, **state.coinmarketcap_data, **state.defillama_data, **state.research_data} if all(hasattr(state, attr) for attr in ['coingecko_data', 'coinmarketcap_data', 'defillama_data', 'research_data']) else {}
        }
        
        content_parts = []
        
        # Extract and format key metrics to ensure they are included in the report text
        key_metrics = {}
        
        # Extract current price
        if 'current_price' in data_sources['multi']:
            key_metrics['current_price'] = f"${data_sources['multi']['current_price']}"
        
        # Extract market cap
        if 'market_cap' in data_sources['multi']:
            market_cap = data_sources['multi']['market_cap']
            if market_cap >= 1_000_000_000:  # Billions
                key_metrics['market_cap'] = f"${market_cap/1_000_000_000:.2f} billion"
            else:  # Millions
                key_metrics['market_cap'] = f"${market_cap/1_000_000:.2f} million"
        
        # Extract trading volume
        if '24h_volume' in data_sources['multi']:
            volume = data_sources['multi']['24h_volume']
            if volume >= 1_000_000_000:  # Billions
                key_metrics['trading_volume'] = f"${volume/1_000_000_000:.2f} billion"
            else:  # Millions
                key_metrics['trading_volume'] = f"${volume/1_000_000:.2f} million"
        elif 'volume_24h' in data_sources['multi']:
            volume = data_sources['multi']['volume_24h']
            if volume >= 1_000_000_000:  # Billions
                key_metrics['trading_volume'] = f"${volume/1_000_000_000:.2f} billion"
            else:  # Millions
                key_metrics['trading_volume'] = f"${volume/1_000_000:.2f} million"
        
        # Extract total supply
        if 'total_supply' in data_sources['multi']:
            supply = data_sources['multi']['total_supply']
            if supply >= 1_000_000_000:  # Billions
                key_metrics['total_supply'] = f"{supply/1_000_000_000:.2f} billion tokens"
            else:  # Millions
                key_metrics['total_supply'] = f"{supply/1_000_000:.2f} million tokens"
                
        # Extract circulating supply
        if 'circulating_supply' in data_sources['multi']:
            supply = data_sources['multi']['circulating_supply']
            if supply >= 1_000_000_000:  # Billions
                key_metrics['circulating_supply'] = f"{supply/1_000_000_000:.2f} billion tokens"
            else:  # Millions
                key_metrics['circulating_supply'] = f"{supply/1_000_000:.2f} million tokens"
                
        # Extract TVL if available
        if 'tvl' in data_sources['multi']:
            tvl = data_sources['multi']['tvl']
            if tvl >= 1_000_000_000:  # Billions
                key_metrics['tvl'] = f"${tvl/1_000_000_000:.2f} billion"
            else:  # Millions
                key_metrics['tvl'] = f"${tvl/1_000_000:.2f} million"
        
        # Add specific metrics section to ensure they're used
        if key_metrics:
            metrics_content = "## Key Metrics (USE THESE EXACT VALUES IN YOUR REPORT TEXT)\n"
            for key, value in key_metrics.items():
                metrics_content += f"- {key.replace('_', ' ').title()}: {value}\n"
            content_parts.append(metrics_content)
        
        # Add the raw data as well
        for source, data in data_sources.items():
            if data:
                content_parts.append(f"{source.capitalize()} Data:\n{json.dumps(data, indent=2)}")
        
        all_content = "\n\n".join(content_parts) if content_parts else "Limited data available."
        
        title_page = (
            f"# {state.project_name} Research Report\n\n"
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            "This report is generated with AI assistance and should not be considered financial advice. "
            "Always conduct your own research before making investment decisions."
        )
        
        sections_prompt = []
        total_words = 0
        for section in report_config.get("sections", []):
            section_title = section["title"]
            max_words = section["max_words"]
            total_words += max_words
            description = section["description"]
            sources = ", ".join(section["data_sources"]) or "available data"
            vis_types = ", ".join(section["visualizations"]) or "none"
            sections_prompt.append(
                f"### {section_title}\n"
                f"- **Max Words**: {max_words}\n"
                f"- **Description**: {description}\n"
                f"- **Data Sources**: {sources}\n"
                f"- **Visualizations**: {vis_types}"
            )
        
        prompt = (
            f"Using the following research data about {state.project_name} cryptocurrency:\n\n"
            f"{all_content}\n\n"
            f"Create a polished, professional draft report with the sections outlined below. "
            f"Ensure each section adheres to its maximum word count, is factual, clear, and uses markdown formatting "
            f"with # for main sections and ## for subsections where applicable. Include specific data points "
            f"from the provided sources, and expand with reasoned analysis. "
            f"IMPORTANT: Use the EXACT numerical values provided in the 'Key Metrics' section when mentioning price, market cap, "
            f"trading volume, total supply, or other metrics. DO NOT use placeholders like '$X' or 'Y tokens'. "
            f"Avoid speculative claims unless labeled as such. If some data is limited, provide general insights relevant "
            f"to the section's focus and extrapolate logically.\n\n"
            f"NOTE ABOUT VISUALIZATIONS: Do not attempt to include tables or images directly in your text. "
            f"Just write the text content, and visualizations will be added automatically during publishing. "
            f"Do not add placeholders for tables or charts.\n\n"
            f"Sections:\n" + "\n\n".join(sections_prompt)
        )
        
        try:
            response = self.llm.invoke(prompt, max_completion_tokens=5000)  # ~4400 words max
            draft = response.content
            
            # Check for and fix any placeholder values that still made it through
            draft = self.fix_placeholder_values(draft)
            
            full_draft = f"{title_page}\n\n{draft}"
            word_count = len(full_draft.split())
            self.logger.info(f"Draft generated: {word_count} words")
            self.logger.debug(f"Full draft content:\n{full_draft[:1000]}...")  # Log first 1000 chars
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