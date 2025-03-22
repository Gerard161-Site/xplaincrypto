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
    Writer agent for generating a comprehensive cryptocurrency research report.
    Uses the research data, data gathering results, and visualizations to create
    a detailed report according to the report configuration.
    
    Args:
        state: Current state of the research process
        llm: Language model for generating text
        logger: Logger instance
        config: Optional configuration
        
    Returns:
        Updated state with the draft report
    """
    project_name = state.project_name
    logger.info(f"Writer agent starting for {project_name}")
    state.update_progress(f"Writing report for {project_name}...")
    
    try:
        # Load the report configuration
        report_config = load_report_config(logger)
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
            
            # Start section with heading
            section_content = [f"## {section_title}", ""]
            
            # Add section content based on type
            if section_title == "Executive Summary":
                content = generate_executive_summary(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Introduction":
                content = generate_introduction(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Market Analysis":
                content = generate_market_analysis(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Technical Analysis":
                content = generate_technical_analysis(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Tokenomics":
                content = generate_tokenomics_section(project_name, state, llm, tokenomics, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Governance and Community":
                content = generate_governance_section(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Ecosystem and Partnerships":
                content = generate_ecosystem_section(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Risks and Opportunities":
                content = generate_risks_opportunities_section(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Team and Development":
                content = generate_team_section(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            elif section_title == "Conclusion":
                content = generate_conclusion(project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            else:
                # Generic section generation
                content = generate_generic_section(section_title, section_description, project_name, state, llm, section_max_words, logger)
                section_content.append(content)
            
            # Add visualizations for this section
            for vis_type in section_visualizations:
                if vis_type in visualizations:
                    vis_data = visualizations[vis_type]
                    if "error" not in vis_data:
                        # Add visualization to section
                        file_path = vis_data.get("file_path", "")
                        title = vis_data.get("title", vis_type.replace("_", " ").title())
                        description = vis_data.get("description", "")
                        
                        if file_path and os.path.exists(file_path):
                            # For markdown, add the image
                            rel_path = os.path.relpath(file_path, start="docs")
                            section_content.append("")
                            section_content.append(f"![{title}]({rel_path})")
                            section_content.append(f"*{description}*")
                            section_content.append("")
                        
                        # If it's a table, add markdown table if available
                        if "markdown_table" in vis_data:
                            section_content.append("")
                            section_content.append(vis_data["markdown_table"])
                            section_content.append("")
            
            # Add the section to the report
            report.extend(section_content)
            report.append("")  # Add blank line after section
        
        # Build the final draft
        draft = "\n".join(report)
        
        # Update state
        state.draft = draft
        state.update_progress("Report draft completed")
        
        return state
    except Exception as e:
        logger.error(f"Error in writer agent: {str(e)}", exc_info=True)
        state.update_progress(f"Error generating report: {str(e)}")
        return state

def load_report_config(logger) -> Dict[str, Any]:
    """Load report configuration from JSON file."""
    try:
        with open("backend/config/report_config.json", "r") as f:
            config = json.load(f)
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading report config: {str(e)}")
        return {}

def generate_executive_summary(project_name, state, llm, max_words, logger) -> str:
    """Generate the executive summary section."""
    logger.info(f"Generating executive summary for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    tokenomics = getattr(state, "tokenomics", "")
    price_analysis = getattr(state, "price_analysis", "")
    
    # Combine available data
    context = []
    if research_summary:
        context.append(research_summary[:1000])  # Limit to first 1000 chars to avoid token limits
    if tokenomics:
        context.append(tokenomics)
    if price_analysis:
        context.append(price_analysis)
    
    combined_context = "\n\n".join(context)
    
    # Generate executive summary
    prompt = f"""
    You are generating an executive summary for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {combined_context}
    
    Create a concise executive summary (no more than {max_words} words) that provides a high-level overview of:
    1. What {project_name} is and its main purpose
    2. Key market metrics and performance
    3. Major strengths and potential risks
    4. A balanced investment outlook
    
    The executive summary should be succinct but information-rich, helping investors quickly understand the project's value proposition and current status.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating executive summary: {str(e)}")
        return f"*Error generating executive summary: {str(e)}*"

def generate_introduction(project_name, state, llm, max_words, logger) -> str:
    """Generate the introduction section."""
    logger.info(f"Generating introduction for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate introduction
    prompt = f"""
    You are generating an introduction for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1500]}
    
    Create an introduction (no more than {max_words} words) that:
    1. Clearly explains what {project_name} is, including its purpose, core functionality, and value proposition
    2. Provides necessary context about the blockchain or platform it operates on
    3. Briefly outlines the history and development of the project
    4. Sets the stage for the detailed analysis to follow in the report
    
    The introduction should be informative and engaging, establishing the foundation for understanding the project.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating introduction: {str(e)}")
        return f"*Error generating introduction: {str(e)}*"

def generate_market_analysis(project_name, state, llm, max_words, logger) -> str:
    """Generate the market analysis section."""
    logger.info(f"Generating market analysis for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    price_analysis = getattr(state, "price_analysis", "")
    
    # Gather market data from different sources
    market_data = []
    if hasattr(state, "data"):
        data = state.data
        if "coingecko" in data:
            market_data.append(f"CoinGecko Data: {str(data['coingecko'])[:500]}...")
        if "coinmarketcap" in data:
            market_data.append(f"CoinMarketCap Data: {str(data['coinmarketcap'])[:500]}...")
        if "defillama" in data:
            market_data.append(f"DeFiLlama Data: {str(data['defillama'])[:500]}...")
    
    combined_market_data = "\n\n".join(market_data)
    
    # Generate market analysis
    prompt = f"""
    You are generating a market analysis section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Price Analysis:
    {price_analysis}
    
    Market Data:
    {combined_market_data}
    
    Create a detailed market analysis (no more than {max_words} words) that:
    1. Analyzes {project_name}'s current market position, including price, market cap, and trading volume
    2. Examines historical price trends and significant price movements
    3. Compares {project_name} with its key competitors in the same sector
    4. Discusses market sentiment and adoption metrics
    5. For DeFi projects, includes analysis of Total Value Locked (TVL) and protocol revenue
    
    The market analysis should be data-driven, objective, and provide meaningful insights for investors evaluating {project_name}.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating market analysis: {str(e)}")
        return f"*Error generating market analysis: {str(e)}*"

def generate_technical_analysis(project_name, state, llm, max_words, logger) -> str:
    """Generate the technical analysis section."""
    logger.info(f"Generating technical analysis for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate technical analysis
    prompt = f"""
    You are generating a technical analysis section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1500]}
    
    Create a detailed technical analysis (no more than {max_words} words) that:
    1. Explains {project_name}'s underlying technology and architecture
    2. Assesses its scalability, security features, and consensus mechanism
    3. Evaluates the quality of the codebase and development activity (if information is available)
    4. Analyzes unique technical features that differentiate it from competitors
    5. Discusses any technical challenges, limitations, or ongoing development efforts
    
    The technical analysis should provide investors with a clear understanding of {project_name}'s technological foundations and potential, using technical terms appropriately but remaining accessible to non-technical readers.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating technical analysis: {str(e)}")
        return f"*Error generating technical analysis: {str(e)}*"

def generate_tokenomics_section(project_name, state, llm, tokenomics_data, max_words, logger) -> str:
    """Generate the tokenomics section."""
    logger.info(f"Generating tokenomics section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate tokenomics section
    prompt = f"""
    You are generating a tokenomics section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Tokenomics Data:
    {tokenomics_data}
    
    Create a detailed tokenomics analysis (no more than {max_words} words) that:
    1. Explains the token supply mechanics, including total, circulating, and maximum supply
    2. Breaks down token distribution across different stakeholders (team, investors, community, etc.)
    3. Analyzes token utility and use cases within the ecosystem
    4. Examines inflation/deflation mechanisms, burning, staking rewards, and vesting schedules
    5. Assesses the token's economic design and sustainability
    
    The tokenomics section should provide investors with a clear understanding of the token's economic model and value accrual mechanisms, with specific numbers and percentages where available.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating tokenomics section: {str(e)}")
        return f"*Error generating tokenomics section: {str(e)}*"

def generate_governance_section(project_name, state, llm, max_words, logger) -> str:
    """Generate the governance and community section."""
    logger.info(f"Generating governance and community section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate governance section
    prompt = f"""
    You are generating a governance and community section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a detailed governance and community analysis (no more than {max_words} words) that:
    1. Explains {project_name}'s governance model and decision-making processes
    2. Analyzes community engagement and activity across social media and community platforms
    3. Examines recent governance proposals and their outcomes (if applicable)
    4. Assesses the level of decentralization in governance
    5. Discusses community sentiment and growth trends
    
    The governance and community section should provide investors with insights into the project's governance structure and community health, which are important indicators of long-term sustainability.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating governance section: {str(e)}")
        return f"*Error generating governance section: {str(e)}*"

def generate_ecosystem_section(project_name, state, llm, max_words, logger) -> str:
    """Generate the ecosystem and partnerships section."""
    logger.info(f"Generating ecosystem and partnerships section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate ecosystem section
    prompt = f"""
    You are generating an ecosystem and partnerships section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a detailed ecosystem and partnerships analysis (no more than {max_words} words) that:
    1. Maps out {project_name}'s ecosystem, including key applications and integrations
    2. Highlights significant partnerships and collaborations
    3. Analyzes how these partnerships enhance {project_name}'s value proposition
    4. Compares the ecosystem's size and activity with competitors
    5. Identifies potential areas for ecosystem expansion
    
    The ecosystem and partnerships section should provide investors with a clear picture of {project_name}'s network effects and strategic position within the broader blockchain landscape.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating ecosystem section: {str(e)}")
        return f"*Error generating ecosystem section: {str(e)}*"

def generate_risks_opportunities_section(project_name, state, llm, max_words, logger) -> str:
    """Generate the risks and opportunities section."""
    logger.info(f"Generating risks and opportunities section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate risks and opportunities section
    prompt = f"""
    You are generating a risks and opportunities section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a balanced risks and opportunities analysis (no more than {max_words} words) that:
    1. Identifies key risks facing {project_name}, including market, technical, regulatory, and competitive risks
    2. Assigns a risk level (low, medium, high) to each risk factor with justification
    3. Highlights significant opportunities for growth and value creation
    4. Analyzes market trends and developments that could impact {project_name}'s future
    5. Discusses potential catalysts and risk mitigation strategies
    
    The risks and opportunities section should provide investors with a clear framework for evaluating {project_name}'s risk-reward profile, being honest about challenges while also recognizing potential upside.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating risks and opportunities section: {str(e)}")
        return f"*Error generating risks and opportunities section: {str(e)}*"

def generate_team_section(project_name, state, llm, max_words, logger) -> str:
    """Generate the team and development section."""
    logger.info(f"Generating team and development section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate team section
    prompt = f"""
    You are generating a team and development section for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a detailed team and development analysis (no more than {max_words} words) that:
    1. Profiles key team members, their backgrounds, and relevant experience
    2. Analyzes the team's track record and previous achievements
    3. Examines development activity and progress against the roadmap
    4. Highlights upcoming milestones and development goals
    5. Assesses the team's transparency and communication with the community
    
    The team and development section should help investors evaluate the execution capability of the team behind {project_name}, which is a critical factor for project success.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating team section: {str(e)}")
        return f"*Error generating team section: {str(e)}*"

def generate_conclusion(project_name, state, llm, max_words, logger) -> str:
    """Generate the conclusion section."""
    logger.info(f"Generating conclusion for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate conclusion
    prompt = f"""
    You are generating a conclusion for a cryptocurrency research report on {project_name}.
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a thoughtful conclusion (no more than {max_words} words) that:
    1. Summarizes key findings from the report
    2. Highlights the most significant strengths and potential concerns
    3. Provides a balanced investment outlook for {project_name}
    4. Indicates specific factors that investors should monitor going forward
    
    The conclusion should provide a clear perspective on {project_name}'s potential as an investment while acknowledging uncertainties and maintaining objectivity.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating conclusion: {str(e)}")
        return f"*Error generating conclusion: {str(e)}*"

def generate_generic_section(section_title, section_description, project_name, state, llm, max_words, logger) -> str:
    """Generate content for a generic section based on its title and description."""
    logger.info(f"Generating {section_title} section for {project_name}")
    
    # Collect relevant information
    research_summary = getattr(state, "research_summary", "")
    
    # Generate generic section
    prompt = f"""
    You are generating a {section_title} section for a cryptocurrency research report on {project_name}.
    
    Section description: {section_description}
    
    Based on the following information:
    {research_summary[:1000]}
    
    Create a detailed {section_title} analysis (no more than {max_words} words) that addresses the key aspects described in the section description.
    
    The section should be well-structured, informative, and relevant to investors evaluating {project_name}.
    """
    
    try:
        response = llm.invoke(prompt).content
        return response.strip()
    except Exception as e:
        logger.error(f"Error generating {section_title} section: {str(e)}")
        return f"*Error generating {section_title} section: {str(e)}*"

def extract_research_data(research_summary):
    """Extract structured data from research summary"""
    data = {}
    
    # Initialize with the overview (beginning of the summary)
    intro_end = research_summary.find("What is")
    if intro_end > 0:
        data["overview"] = research_summary[:intro_end].strip()
    
    # Extract sections based on "What is X" patterns
    sections = [
        ("governance", "What is .+?'s governance", "What is .+?'s tokenomics"),
        ("tokenomics", "What is .+?'s tokenomics", "What is .+?'s features"),
        ("features", "What is .+?'s features", "What is .+?'s market"),
        ("market", "What is .+?'s market", "What is .+?'s team"),
        ("team", "What is .+?'s team", "What is .+?'s risks"),
        ("risks", "What is .+?'s risks", "What is .+?'s opportunities"),
        ("opportunities", "What is .+?'s opportunities", "What is .+?'s partnerships"),
        ("partnerships", "What is .+?'s partnerships", "What is .+?'s roadmap"),
        ("roadmap", "What is .+?'s roadmap", "SWOT Analysis")
    ]
    
    for section, start_pattern, end_pattern in sections:
        start_match = re.search(start_pattern, research_summary)
        if start_match:
            start_idx = start_match.end()
            
            # Find the end of this section
            end_match = re.search(end_pattern, research_summary)
            if end_match:
                end_idx = end_match.start()
                content = research_summary[start_idx:end_idx].strip()
                data[section] = content
            else:
                # If it's the last section
                remaining = research_summary[start_idx:].strip()
                
                # Check if SWOT follows
                swot_idx = remaining.find("SWOT Analysis")
                if swot_idx > 0:
                    content = remaining[:swot_idx].strip()
                    data[section] = content
                else:
                    data[section] = remaining
    
    # Extract SWOT analysis
    swot_match = re.search(r"SWOT Analysis for .+?:(.*?)(?=\n\n\n|$)", research_summary, re.DOTALL)
    if swot_match:
        data["swot"] = swot_match.group(1).strip()
    
    return data