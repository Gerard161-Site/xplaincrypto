from langchain_openai import ChatOpenAI
import logging
import re
from backend.state import ResearchState
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

def writer(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    """
    Writer agent function for creating a structured report based on research data.
    
    Args:
        state: Current state of the research
        llm: Language model for generating text
        logger: Logger instance
        config: Optional configuration parameters
    
    Returns:
        Updated state with draft report
    """
    project_name = state.project_name
    logger.info(f"Writing report for {project_name}")
    state.update_progress(f"Writing report for {project_name}...")
    
    # Extract configuration options
    fast_mode = config.get("fast_mode", False) if config else False
    max_tokens_per_section = config.get("max_tokens_per_section", 500) if config else 500
    include_visualizations = config.get("include_visualizations", True) if config else True
    
    try:
        # Load the report configuration
        report_config = None
        if hasattr(state, 'report_config') and state.report_config:
            logger.info("Using report configuration from state")
            report_config = state.report_config
        else:
            # Fallback to loading from file
            report_config = load_report_config(logger)
            if report_config:
                logger.info("Loaded report configuration from file")
                state.report_config = report_config
        
        if not report_config:
            logger.error("Failed to load report configuration")
            state.update_progress("Error: Failed to load report configuration")
            return state
        
        # Get research summary
        research_summary = getattr(state, "research_summary", "")
        
        # Get data from state
        data = {}
        if hasattr(state, "data"):
            data = state.data
        
        # Get tokenomics data
        tokenomics = getattr(state, "tokenomics", "")
        
        # Get price analysis
        price_analysis = getattr(state, "price_analysis", "")
        
        # Get visualizations
        visualizations = getattr(state, "visualizations", {})
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Start building the report
        report = []
        
        # Add title and date
        report.append(f"# {project_name} Research Report")
        report.append(f"*Generated on {timestamp}*")
        report.append("")
        
        # Generate each section according to the report configuration
        for section in report_config.get("sections", []):
            section_title = section.get("title", "")
            if not section_title:
                continue
                
            section_required = section.get("required", False)
            section_max_words = section.get("max_words", 500)
            section_description = section.get("description", "")
            section_data_sources = section.get("data_sources", [])
            section_visualizations = section.get("visualizations", [])
            
            logger.info(f"Generating section: {section_title}")
            
            # Adjust tokens per section in fast mode
            if fast_mode:
                section_max_words = min(section_max_words, max_tokens_per_section)
            
            # Start section with heading
            section_content = [f"## {section_title}", ""]
            
            # Generate section prompt that includes visualization awareness
            visualization_info = ""
            if include_visualizations and section_visualizations and hasattr(state, "visualizations"):
                visualization_info = "This section includes the following visualizations that you should reference in your text:\n"
                
                for vis_name in section_visualizations:
                    if vis_name in state.visualizations:
                        vis_data = state.visualizations[vis_name]
                        vis_title = vis_data.get("title", vis_name.replace("_", " ").title())
                        vis_desc = vis_data.get("description", "")
                        visualization_info += f"- {vis_title}: {vis_desc}\n"
            
            # Add section content based on type
            if section_title == "Executive Summary":
                content = generate_executive_summary(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Introduction":
                content = generate_introduction(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Market Analysis":
                content = generate_market_analysis(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Technical Analysis":
                content = generate_technical_analysis(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Tokenomics":
                content = generate_tokenomics_section(project_name, state, llm, tokenomics, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Governance and Community":
                content = generate_governance_section(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Ecosystem and Partnerships":
                content = generate_ecosystem_section(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Risks and Opportunities":
                content = generate_risks_section(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Team and Development":
                content = generate_team_section(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            elif section_title == "Conclusion":
                content = generate_conclusion(project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            else:
                # Generic section handler for any other sections in the config
                content = generate_generic_section(section_title, project_name, state, llm, section_max_words, visualization_info, logger)
                section_content.append(content)
            
            # Add section to report
            report.extend(section_content)
            report.append("")  # Add blank line after section
        
        # Add references section
        references_content = generate_references_section(project_name, state, llm, logger)
        report.append(references_content)
        
        # Combine report into final draft
        state.draft = "\n".join(report)
        logger.info(f"Successfully wrote draft report for {project_name}")
        state.update_progress(f"Completed writing report for {project_name}")
        
        return state
    except Exception as e:
        logger.error(f"Error in writer agent: {str(e)}", exc_info=True)
        state.update_progress(f"Error generating report: {str(e)}")
        
        # Create minimal report as fallback
        minimal_report = [
            f"# {project_name} Research Report",
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Executive Summary",
            "",
            research_summary or f"Analysis of {project_name} cryptocurrency.",
            "",
            "## Tokenomics",
            "",
            tokenomics or f"Tokenomics information for {project_name}.",
            "",
            "## Price Analysis",
            "",
            price_analysis or f"Price analysis for {project_name}."
        ]
        
        state.draft = "\n".join(minimal_report)
        return state

def generate_executive_summary(project_name, state, llm, max_words, visualization_info, logger):
    """Generate executive summary section."""
    research_summary = getattr(state, "research_summary", "")
    price_analysis = getattr(state, "price_analysis", "")
    
    prompt = f"""
    Write an executive summary for {project_name} cryptocurrency research report.
    
    The summary should be concise (no more than {max_words} words) and cover:
    - Key value proposition
    - Market position
    - Main strengths
    - Investment considerations
    
    Research data:
    {research_summary[:1000]}
    
    Price analysis:
    {price_analysis[:500]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating executive summary: {str(e)}")
        return f"Executive summary for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_introduction(project_name, state, llm, max_words, visualization_info, logger):
    """Generate introduction section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write an introduction for {project_name} cryptocurrency research report.
    
    The introduction should be informative and engaging, establishing the foundation for understanding the project.
    
    Research data:
    {research_summary[:1500]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating introduction: {str(e)}")
        return f"Introduction for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_market_analysis(project_name, state, llm, max_words, visualization_info, logger):
    """Generate comprehensive market analysis with specific price data and metrics."""
    research_summary = getattr(state, "research_summary", "")
    price_analysis = getattr(state, "price_analysis", "")
    
    # Try to get enhanced data if available
    enhanced_data = {}
    if hasattr(state, "enhanced_data") and state.enhanced_data and "market" in state.enhanced_data:
        enhanced_data = state.enhanced_data["market"]
        logger.info(f"Using enhanced market data for {project_name} market analysis")
    
    # Format specific data points if available
    specific_data = ""
    if enhanced_data:
        specific_data += "## Key Market Metrics\n"
        if "current_price" in enhanced_data:
            specific_data += f"- Current Price: ${enhanced_data['current_price']:.4f}\n"
        if "market_cap" in enhanced_data:
            specific_data += f"- Market Cap: ${enhanced_data['market_cap']:,}\n"
        if "total_volume" in enhanced_data:
            specific_data += f"- 24h Trading Volume: ${enhanced_data['total_volume']:,}\n"
        if "price_change_24h" in enhanced_data:
            specific_data += f"- 24h Change: {enhanced_data['price_change_24h']:.2f}%\n"
        if "price_change_7d" in enhanced_data:
            specific_data += f"- 7-day Change: {enhanced_data['price_change_7d']:.2f}%\n"
        if "price_change_30d" in enhanced_data:
            specific_data += f"- 30-day Change: {enhanced_data['price_change_30d']:.2f}%\n"
        if "price_change_60d" in enhanced_data:
            specific_data += f"- 60-day Change: {enhanced_data['price_change_60d']:.2f}%\n"
    
    prompt = f"""
    Write a detailed Market Analysis section for the {project_name} cryptocurrency research report.
    
    Include these specific components:
    1. Current price, market cap, trading volume, and historical performance
    2. Price movements over the last 60 days with percentage changes
    3. Market trends affecting {project_name}
    4. Trading volume analysis and liquidity assessment
    5. Market sentiment and investor interest
    6. Comparison with overall cryptocurrency market performance
    
    Specific market data to incorporate:
    {specific_data if specific_data else "Use the research data to find current market metrics."}
    
    Also include a detailed competitive analysis comparing {project_name} with Ethereum, Solana, and other major competitors in its sector, focusing on:
    - Transaction speeds and fees
    - Market capitalization comparison
    - Developer activity and ecosystem size
    - Unique technological advantages
    
    Research data:
    {research_summary[:800]}
    
    Price analysis:
    {price_analysis[:400]}
    
    {visualization_info}
    
    Format the response as plain text with clear section headers. Use specific numbers and metrics.
    The section should be data-rich, informative, and approximately {max_words} words.
    """
    
    try:
        response = llm.invoke(prompt).content
        logger.info(f"Generated enhanced market analysis with {len(response.split())} words")
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating market analysis: {str(e)}")
        return f"Market analysis for {project_name}. Price movements and trading activity suggest varying levels of investor interest."

def generate_technical_analysis(project_name, state, llm, max_words, visualization_info, logger):
    """Generate technical analysis section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a technical analysis for {project_name} cryptocurrency research report.
    
    The analysis should provide investors with a clear understanding of {project_name}'s technological foundations and potential, using technical terms appropriately but remaining accessible to non-technical readers.
    
    Research data:
    {research_summary[:1500]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating technical analysis: {str(e)}")
        return f"Technical analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_tokenomics_section(project_name, state, llm, tokenomics, max_words, visualization_info, logger):
    """Generate tokenomics section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a tokenomics analysis for {project_name} cryptocurrency research report.
    
    The analysis should provide investors with a clear understanding of the token's economic model and value accrual mechanisms, with specific numbers and percentages where available.
    
    Research data:
    {research_summary[:1000]}
    
    Tokenomics data:
    {tokenomics}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating tokenomics section: {str(e)}")
        return f"Tokenomics analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_governance_section(project_name, state, llm, max_words, visualization_info, logger):
    """Generate comprehensive governance and community section with specific data points and metrics."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a detailed Governance and Community section for the {project_name} cryptocurrency research report.
    
    Include these SPECIFIC components:
    1. Governance model details (DAO structure, voting mechanisms, proposal systems)
    2. Community engagement metrics (social media followers, growth rates, active community members)
    3. Recent governance decisions and their impacts
    4. Voting participation percentages
    5. Community development contributions
    6. Governance token utility and distribution
    
    The section should be informative, data-rich and concise (no more than {max_words} words).
    
    Research data:
    {research_summary[:800]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs with clear subheadings. Focus on facts, current data, and objective analysis.
    Include specific numbers and metrics wherever possible. Do not use vague statements.
    """
    
    try:
        response = llm.invoke(prompt).content
        logger.info(f"Generated enhanced governance section with {len(response.split())} words")
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating governance section: {str(e)}")
        return f"Governance and community analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_ecosystem_section(project_name, state, llm, max_words, visualization_info, logger):
    """Generate ecosystem and partnerships section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write an ecosystem and partnerships analysis for {project_name} cryptocurrency research report.
    
    The analysis should provide investors with a clear picture of {project_name}'s network effects and strategic position within the broader blockchain landscape.
    
    Research data:
    {research_summary[:1000]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating ecosystem section: {str(e)}")
        return f"Ecosystem and partnerships analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_risks_section(project_name, state, llm, max_words, visualization_info, logger):
    """Generate risks and opportunities section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a risks and opportunities analysis for {project_name} cryptocurrency research report.
    
    The analysis should provide investors with a clear framework for evaluating {project_name}'s risk-reward profile, being honest about challenges while also recognizing potential upside.
    
    Research data:
    {research_summary[:1000]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating risks and opportunities section: {str(e)}")
        return f"Risks and opportunities analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_team_section(project_name, state, llm, max_words, visualization_info, logger):
    """Generate comprehensive team and development section with specific data points and roadmap details."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a detailed Team and Development section for the {project_name} cryptocurrency research report.
    
    Include these SPECIFIC components:
    1. Key team members with their backgrounds and relevant experience
    2. Development team size and expertise
    3. Detailed project roadmap with specific upcoming milestones and their target dates
    4. Recent development achievements
    5. Development activity metrics (GitHub commits, contributors)
    6. Notable advisors or partnerships that strengthen the development team
    
    The section should be informative, data-rich and concise (no more than {max_words} words).
    
    Research data:
    {research_summary[:800]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs with clear subheadings. Focus on facts, current data, and objective analysis.
    Include specific numbers and metrics wherever possible. Do not use vague statements.
    """
    
    try:
        response = llm.invoke(prompt).content
        logger.info(f"Generated enhanced team section with {len(response.split())} words")
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating team section: {str(e)}")
        return f"Team and development analysis for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_conclusion(project_name, state, llm, max_words, visualization_info, logger):
    """Generate conclusion section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write a conclusion for {project_name} cryptocurrency research report.
    
    The conclusion should provide a clear perspective on {project_name}'s potential as an investment while acknowledging uncertainties and maintaining objectivity.
    
    Research data:
    {research_summary[:1000]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating conclusion: {str(e)}")
        return f"Conclusion for {project_name}. This cryptocurrency offers unique features and applications in the blockchain space."

def generate_generic_section(section_title, project_name, state, llm, max_words, visualization_info, logger):
    """Generate content for a generic section."""
    research_summary = getattr(state, "research_summary", "")
    
    prompt = f"""
    Write the {section_title} section for a {project_name} cryptocurrency research report.
    
    The section should be informative and concise (no more than {max_words} words).
    
    Research data:
    {research_summary[:800]}
    
    {visualization_info}
    
    Format the response as plain text paragraphs. Focus on facts, current data, and objective analysis.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating {section_title} section: {str(e)}")
        return f"Information about {project_name}'s {section_title.lower()}."

def generate_references_section(project_name, state, llm, logger):
    """Generate a properly formatted references section based on sources used."""
    references = getattr(state, "references", [])
    
    if not references:
        # Default references if none available
        references = [
            {"title": f"{project_name} Official Website", "url": f"https://{project_name.lower()}.io"},
            {"title": "CoinGecko", "url": f"https://www.coingecko.com/en/coins/{project_name.lower()}"},
            {"title": "CoinMarketCap", "url": f"https://coinmarketcap.com/currencies/{project_name.lower()}/"}
        ]
    
    # Format the references section
    references_text = "# References\n\n"
    
    for ref in references:
        title = ref.get("title", "Unknown Source")
        url = ref.get("url", "")
        if url:
            references_text += f"- {title}: {url}\n"
        else:
            references_text += f"- {title}\n"
    
    logger.info(f"Generated references section with {len(references)} sources")
    return references_text.strip()

def load_report_config(logger):
    """Load report configuration from file."""
    try:
        with open("backend/config/report_config.json", "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load report configuration: {str(e)}")
        return None