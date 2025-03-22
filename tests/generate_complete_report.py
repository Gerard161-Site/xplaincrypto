#!/usr/bin/env python3
"""
Generate Complete Report Script

This script generates a complete cryptocurrency report from scratch
using the enhanced writer, data gathering, and publisher modules.

Usage:
  python generate_complete_report.py [project_name]
  (default project name is "SUI" if not specified)
"""

import os
import logging
import sys
import json
from datetime import datetime
from backend.state import ResearchState  # Import the state class

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/generate_report.log", mode='w')
    ]
)
logger = logging.getLogger("Report_Generator")

def generate_report(project_name):
    """Generate a complete report for the specified project"""
    try:
        # Import necessary components
        from backend.research.data_modules import DataGatherer
        from backend.agents.publisher import publisher
        from langchain_openai import ChatOpenAI
        
        # Check if API key is available
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            return False
        
        # Create language model for content generation
        llm = ChatOpenAI(model_name='gpt-3.5-turbo')
        logger.info("Created language model for content generation")
        
        # Create report state
        state = ResearchState(project_name=project_name)
        logger.info(f"Initialized state for {project_name}")
        
        # Load report configuration
        try:
            with open("backend/config/report_config.json", "r") as f:
                state.report_config = json.load(f)
                logger.info("Loaded report configuration")
        except Exception as e:
            logger.error(f"Error loading report config: {str(e)}")
            return False
        
        # Gather data
        logger.info(f"Gathering data for {project_name}")
        data_gatherer = DataGatherer(project_name, logger)
        state.data = data_gatherer.gather_all_data()
        logger.info(f"Gathered data from {len(state.data)} sources")
        
        # Get enhanced market data
        enhanced_market = data_gatherer.get_enhanced_market_data()
        if "error" not in enhanced_market:
            if not hasattr(state, "enhanced_data"):
                state.enhanced_data = {}
            state.enhanced_data["market"] = enhanced_market
            logger.info(f"Added enhanced market data with {len(enhanced_market)} fields")
        
        # Format tokenomics
        state.tokenomics = data_gatherer.get_formatted_tokenomics(state.data)
        logger.info("Added enhanced tokenomics data")
        
        # Generate content sections
        sections = []
        
        # Title section
        sections.append(f"# {project_name} Research Report")
        sections.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        sections.append("")
        
        # Introduction
        sections.append("# Introduction")
        sections.append("")
        intro_prompt = f"""
        Write a concise introduction for a {project_name} cryptocurrency research report.
        The introduction should explain what {project_name} is, its core purpose, and key value propositions.
        Keep it factual, objective, and around 200 words.
        """
        try:
            intro_response = llm.invoke(intro_prompt).content
            sections.append(intro_response.strip())
        except Exception as e:
            logger.error(f"Error generating introduction: {e}")
            sections.append(f"{project_name} is a cryptocurrency project with unique features and capabilities.")
        sections.append("")
        
        # Market Analysis with enhanced data
        sections.append("# Market Analysis")
        sections.append("")
        
        # Use enhanced data for market metrics
        if hasattr(state, "enhanced_data") and "market" in state.enhanced_data:
            market_data = state.enhanced_data["market"]
            sections.append("## Current Market Metrics")
            sections.append("")
            metrics_list = []
            if "current_price" in market_data:
                metrics_list.append(f"- Current Price: ${market_data['current_price']:.4f}")
            if "market_cap" in market_data:
                metrics_list.append(f"- Market Cap: ${market_data['market_cap']:,}")
            if "total_volume" in market_data:
                metrics_list.append(f"- 24h Trading Volume: ${market_data['total_volume']:,}")
            if metrics_list:
                sections.extend(metrics_list)
                sections.append("")
            
            # Price performance metrics
            sections.append("## Price Performance")
            sections.append("")
            performance_list = []
            if "price_change_24h" in market_data:
                performance_list.append(f"- 24-Hour Change: {market_data['price_change_24h']:.2f}%")
            if "price_change_7d" in market_data:
                performance_list.append(f"- 7-Day Change: {market_data['price_change_7d']:.2f}%")
            if "price_change_30d" in market_data:
                performance_list.append(f"- 30-Day Change: {market_data['price_change_30d']:.2f}%")
            if "price_change_60d" in market_data:
                performance_list.append(f"- 60-Day Change: {market_data['price_change_60d']:.2f}%")
            if performance_list:
                sections.extend(performance_list)
                sections.append("")
        
        # Generate market analysis text
        market_prompt = f"""
        Write a detailed market analysis for {project_name} cryptocurrency.
        
        Include:
        1. Current market position and competition
        2. Trading volume analysis and liquidity assessment
        3. Market trends affecting {project_name}
        4. Comparative analysis with Ethereum, Solana, and other major competitors
        
        Emphasize specific metrics and data-driven insights. Length should be about 300 words.
        """
        try:
            market_response = llm.invoke(market_prompt).content
            sections.append("## Market Trends and Competition")
            sections.append("")
            sections.append(market_response.strip())
        except Exception as e:
            logger.error(f"Error generating market analysis: {e}")
        sections.append("")
        
        # Tokenomics section
        if state.tokenomics:
            sections.append(state.tokenomics)
        else:
            sections.append("# Tokenomics")
            sections.append("")
            sections.append(f"Tokenomics information for {project_name} includes details about supply, distribution, and utility.")
        sections.append("")
        
        # Technical Analysis
        sections.append("# Technical Analysis")
        sections.append("")
        tech_prompt = f"""
        Write a detailed technical analysis for {project_name} cryptocurrency.
        
        Include:
        1. Blockchain architecture and consensus mechanism
        2. Transaction speed, scalability, and fees
        3. Smart contract capabilities
        4. Security features and audit history
        5. Recent technical developments and upgrades
        
        Emphasize specific technical details and metrics. Length should be about 300 words.
        """
        try:
            tech_response = llm.invoke(tech_prompt).content
            sections.append(tech_response.strip())
        except Exception as e:
            logger.error(f"Error generating technical analysis: {e}")
            sections.append(f"{project_name}'s technical architecture is designed to address key challenges in the blockchain space.")
        sections.append("")
        
        # Governance and Community
        sections.append("# Governance and Community")
        sections.append("")
        gov_prompt = f"""
        Write a detailed governance and community analysis for {project_name} cryptocurrency.
        
        Include these SPECIFIC components:
        1. Governance model details (DAO structure, voting mechanisms, proposal systems)
        2. Community engagement metrics (social media followers, growth rates, active community members)
        3. Recent governance decisions and their impacts
        4. Voting participation percentages
        5. Community development contributions
        
        Format with clear subheadings and include specific numbers and metrics. Length should be about 300 words.
        """
        try:
            gov_response = llm.invoke(gov_prompt).content
            sections.append(gov_response.strip())
        except Exception as e:
            logger.error(f"Error generating governance section: {e}")
            sections.append(f"{project_name} has a governance system that allows token holders to participate in decision-making processes.")
        sections.append("")
        
        # Risks and Opportunities
        sections.append("# Risks and Opportunities")
        sections.append("")
        risks_prompt = f"""
        Write a detailed risks and opportunities analysis for {project_name} cryptocurrency.
        
        Structure as follows:
        
        ## Risks
        - Market risks (with specific examples)
        - Technical risks (with specific examples)
        - Regulatory risks (with specific examples)
        - Competition risks (with specific examples)
        
        ## Opportunities
        - Market opportunities (with specific examples)
        - Technical opportunities (with specific examples)
        - Adoption opportunities (with specific examples)
        - Strategic opportunities (with specific examples)
        
        Use bullet points and be specific with examples. Length should be about 300 words total.
        """
        try:
            risks_response = llm.invoke(risks_prompt).content
            sections.append(risks_response.strip())
        except Exception as e:
            logger.error(f"Error generating risks section: {e}")
            sections.append("## Risks\n\n- Market volatility\n- Regulatory uncertainty\n- Technical challenges\n\n## Opportunities\n\n- Growing adoption\n- Technical innovation\n- Strategic partnerships")
        sections.append("")
        
        # Team and Development
        sections.append("# Team and Development")
        sections.append("")
        team_prompt = f"""
        Write a detailed team and development section for {project_name} cryptocurrency.
        
        Include these SPECIFIC components:
        1. Key team members with their backgrounds and relevant experience
        2. Development team size and expertise
        3. Detailed project roadmap with specific upcoming milestones and their target dates
        4. Recent development achievements
        5. Development activity metrics (GitHub commits, contributors)
        
        Format with clear subheadings and include specific data points. Length should be about 300 words.
        """
        try:
            team_response = llm.invoke(team_prompt).content
            sections.append(team_response.strip())
        except Exception as e:
            logger.error(f"Error generating team section: {e}")
            sections.append(f"The {project_name} development team is working on several key initiatives to advance the platform.")
        sections.append("")
        
        # Conclusion
        sections.append("# Conclusion")
        sections.append("")
        conclusion_prompt = f"""
        Write a concise conclusion for a {project_name} cryptocurrency research report.
        
        Summarize the key findings about {project_name}'s market position, technical strengths, 
        governance, risks/opportunities, and future outlook.
        
        End with a balanced perspective on {project_name}'s potential. Length should be about 150 words.
        """
        try:
            conclusion_response = llm.invoke(conclusion_prompt).content
            sections.append(conclusion_response.strip())
        except Exception as e:
            logger.error(f"Error generating conclusion: {e}")
            sections.append(f"{project_name} presents a unique value proposition in the blockchain space with its combination of features and capabilities.")
        sections.append("")
        
        # References
        sections.append("# References")
        sections.append("")
        # Add default references
        state.references = [
            {"title": f"{project_name} Official Website", "url": f"https://{project_name.lower()}.io"},
            {"title": "CoinGecko", "url": f"https://www.coingecko.com/en/coins/{project_name.lower()}"},
            {"title": "CoinMarketCap", "url": f"https://coinmarketcap.com/currencies/{project_name.lower()}"}
        ]
        for ref in state.references:
            title = ref.get("title", "Unknown Source")
            url = ref.get("url", "")
            if url:
                sections.append(f"- {title}: {url}")
            else:
                sections.append(f"- {title}")
                
        # Combine all sections into the report draft
        state.draft = "\n".join(sections)
        logger.info(f"Generated complete report content: {len(state.draft)} characters")
        
        # Save the markdown content for reference
        md_path = f"docs/{project_name}_report.md"
        os.makedirs("docs", exist_ok=True)
        with open(md_path, 'w') as f:
            f.write(state.draft)
        logger.info(f"Saved markdown report to {md_path}")
        
        # Generate enhanced PDF report
        logger.info("Generating enhanced PDF report...")
        publisher_config = {"use_report_config": True}
        final_state = publisher(state, logger, publisher_config)
        
        # Check result
        pdf_path = f"docs/{project_name}_report.pdf"
        if os.path.exists(pdf_path):
            logger.info(f"Successfully generated enhanced report at {pdf_path}")
            logger.info(f"PDF size: {os.path.getsize(pdf_path)/1024:.1f} KB")
            return True
        else:
            logger.error(f"Failed to generate PDF at {pdf_path}")
            return False
    
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to generate a complete report"""
    # Determine which project to report on
    project_name = "SUI"  # Default
    if len(sys.argv) > 1:
        project_name = sys.argv[1]
    
    logger.info(f"Generating complete report for {project_name}")
    
    # Generate the report
    success = generate_report(project_name)
    
    if success:
        logger.info(f"Report generation completed successfully for {project_name}")
        return 0
    else:
        logger.error(f"Report generation failed for {project_name}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 