#!/usr/bin/env python3
"""
Enhance Existing Report Script

This script takes an existing report and enhances it with improved formatting,
layout, and data enrichment.

Usage:
  python enhance_existing_report.py [project_name]
  (default project name is "SUI" if not specified)
"""

import os
import logging
import sys
from langchain_openai import ChatOpenAI
from backend.state import ResearchState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/enhance_report.log", mode='w')
    ]
)
logger = logging.getLogger("Report_Enhancer")

def load_existing_report(project_name):
    """Load an existing report content"""
    # Try to find the existing report
    md_path = f"docs/{project_name}_report.md"
    if os.path.exists(md_path):
        with open(md_path, 'r') as f:
            return f.read()
    
    # If no markdown, look for notes or research summary
    if os.path.exists(f"docs/{project_name}_notes.md"):
        with open(f"docs/{project_name}_notes.md", 'r') as f:
            return f.read()
    
    # If no files found, return None
    return None

def enhance_report(project_name, content=None):
    """Enhance an existing report with improved formatting and data enrichment"""
    try:
        # Import necessary components
        from backend.research.data_modules import DataGatherer
        from backend.agents.publisher import publisher
        from langchain_openai import ChatOpenAI
        import os

        # Create language model if API key exists
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            llm = ChatOpenAI(model_name='gpt-3.5-turbo')
            logger.info("Created language model for content generation")
        else:
            llm = None
            logger.warning("No OpenAI API key found, will use basic content only")

        # Create empty state
        state = ResearchState(project_name=project_name)
        
        # Load report configuration
        try:
            with open("backend/config/report_config.json", "r") as f:
                import json
                state.report_config = json.load(f)
                logger.info("Loaded report configuration")
        except Exception as e:
            logger.error(f"Error loading report config: {str(e)}")
            return False
        
        # Load existing report content if provided
        if content:
            state.draft = content
            logger.info(f"Loaded existing content: {len(content)} characters")
        else:
            # Try to load from file
            existing_content = load_existing_report(project_name)
            if existing_content:
                state.draft = existing_content
                logger.info(f"Loaded existing report from file: {len(existing_content)} characters")
            else:
                logger.warning(f"No existing report found for {project_name}")
                state.draft = None  # We'll generate content based on enhanced data
        
        # Gather enhanced data
        logger.info(f"Gathering enhanced data for {project_name}")
        data_gatherer = DataGatherer(project_name, logger)
        
        # Gather all data
        state.data = data_gatherer.gather_all_data()
        
        # Get enhanced market data specifically
        enhanced_market = data_gatherer.get_enhanced_market_data()
        if "error" not in enhanced_market:
            if not hasattr(state, "enhanced_data"):
                state.enhanced_data = {}
            state.enhanced_data["market"] = enhanced_market
            logger.info(f"Added enhanced market data with {len(enhanced_market)} fields")
        
        # Format enhanced tokenomics
        state.tokenomics = data_gatherer.get_formatted_tokenomics(state.data)
        logger.info("Added enhanced tokenomics data")
        
        # Add references
        state.references = [
            {"title": f"{project_name} Official Website", "url": f"https://{project_name.lower()}.io"},
            {"title": "CoinGecko", "url": f"https://www.coingecko.com/en/coins/{project_name.lower()}"},
            {"title": "CoinMarketCap", "url": f"https://coinmarketcap.com/currencies/{project_name.lower()}/"}
        ]
        logger.info("Added default references")
        
        # Generate content if none exists and we have a language model
        if not state.draft and llm:
            logger.info("Generating content from enhanced data")
            
            # Create a basic report structure based on the data we have
            report = []
            
            # Title and introduction
            report.append(f"# {project_name} Research Report")
            report.append("")
            report.append("## Introduction")
            report.append("")
            report.append(f"{project_name} is a cryptocurrency that offers various features and capabilities in the blockchain ecosystem.")
            report.append("")
            
            # Market analysis from enhanced data
            report.append("## Market Analysis")
            report.append("")
            
            if hasattr(state, "enhanced_data") and "market" in state.enhanced_data:
                market_data = state.enhanced_data["market"]
                report.append("### Current Market Metrics")
                report.append("")
                if "current_price" in market_data:
                    report.append(f"- Current Price: ${market_data['current_price']:.4f}")
                if "market_cap" in market_data:
                    report.append(f"- Market Cap: ${market_data['market_cap']:,}")
                if "total_volume" in market_data:
                    report.append(f"- 24h Trading Volume: ${market_data['total_volume']:,}")
                
                report.append("")
                report.append("### Price Performance")
                report.append("")
                
                if "price_change_24h" in market_data:
                    report.append(f"- 24-Hour Change: {market_data['price_change_24h']:.2f}%")
                if "price_change_7d" in market_data:
                    report.append(f"- 7-Day Change: {market_data['price_change_7d']:.2f}%")
                if "price_change_30d" in market_data:
                    report.append(f"- 30-Day Change: {market_data['price_change_30d']:.2f}%")
                if "price_change_60d" in market_data:
                    report.append(f"- 60-Day Change: {market_data['price_change_60d']:.2f}%")
            
            report.append("")
            
            # Tokenomics from tokenomics data
            if state.tokenomics:
                report.append(state.tokenomics)
            else:
                report.append("## Tokenomics")
                report.append("")
                report.append(f"Tokenomics information for {project_name} includes details about supply, distribution, and utility.")
            
            report.append("")
            
            # Technical Analysis section
            report.append("## Technical Analysis")
            report.append("")
            report.append(f"{project_name}'s technical architecture is designed to address key challenges in the blockchain space.")
            report.append("")
            
            # Governance section
            report.append("## Governance and Community")
            report.append("")
            report.append(f"{project_name} has a governance system that allows token holders to participate in decision-making processes.")
            report.append("")
            
            # Risks and Opportunities section
            report.append("## Risks and Opportunities")
            report.append("")
            report.append("### Risks")
            report.append("")
            report.append("- Market volatility and competition from other blockchain projects")
            report.append("- Regulatory uncertainties in various jurisdictions")
            report.append("- Technical challenges and potential security vulnerabilities")
            report.append("")
            report.append("### Opportunities")
            report.append("")
            report.append("- Growing adoption and ecosystem expansion")
            report.append("- Technological innovations and improvements")
            report.append("- Strategic partnerships and integrations")
            report.append("")
            
            # Team section
            report.append("## Team and Development")
            report.append("")
            report.append(f"The {project_name} development team is working on several key initiatives to advance the platform.")
            report.append("")
            
            # Conclusion
            report.append("## Conclusion")
            report.append("")
            report.append(f"{project_name} presents a unique value proposition in the blockchain space with its combination of features and capabilities.")
            report.append("")
            
            # References
            report.append("## References")
            report.append("")
            for ref in state.references:
                title = ref.get("title", "Unknown Source")
                url = ref.get("url", "")
                if url:
                    report.append(f"- {title}: {url}")
                else:
                    report.append(f"- {title}")
            
            # Set the draft content
            state.draft = "\n".join(report)
            logger.info(f"Generated basic report content: {len(state.draft)} characters")
        elif not state.draft:
            # Create minimal content if no LLM and no existing content
            state.draft = f"""# {project_name} Research Report

## Introduction
{project_name} is a cryptocurrency that offers various features and capabilities in the blockchain ecosystem.

{state.tokenomics}

## References
"""
            for ref in state.references:
                title = ref.get("title", "Unknown Source")
                url = ref.get("url", "")
                if url:
                    state.draft += f"- {title}: {url}\n"
                else:
                    state.draft += f"- {title}\n"
                    
            logger.info(f"Generated minimal report content: {len(state.draft)} characters")
        
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
        logger.error(f"Error enhancing report: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to enhance an existing report"""
    # Determine which project to enhance
    project_name = "SUI"  # Default
    if len(sys.argv) > 1:
        project_name = sys.argv[1]
    
    logger.info(f"Enhancing report for {project_name}")
    
    # Run enhancement
    success = enhance_report(project_name)
    
    if success:
        logger.info(f"Report enhancement completed successfully for {project_name}")
        return 0
    else:
        logger.error(f"Report enhancement failed for {project_name}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 