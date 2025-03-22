import os
import logging
import json
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.visualization_agent import visualization_agent
from backend.agents.writer import writer
from backend.agents.publisher import publisher
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IntegrationTest")

# Initialize LLM
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment")

llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

def create_test_state(project_name):
    """Create a test state with fake data for testing."""
    state = ResearchState(project_name=project_name)
    
    # Load the report configuration
    try:
        with open("backend/config/report_config.json", "r") as f:
            report_config = json.load(f)
        state.report_config = report_config
        logger.info("Loaded report configuration")
    except Exception as e:
        logger.error(f"Failed to load report config: {e}")
        return None
    
    # Fill in synthetic research data for testing
    state.research_summary = f"This is a synthetic research summary for {project_name}."
    state.key_features = f"Key features of {project_name} include blockchain technology."
    state.tokenomics = f"Tokenomics for {project_name}:\nTotal Supply: 1,000,000,000\nCirculating Supply: 500,000,000"
    state.price_analysis = f"Price analysis for {project_name}.\n60-Day Change: +15%"
    state.governance = f"Governance structure of {project_name} is based on token voting."
    
    # Create synthetic data for visualizations
    state.coingecko_data = {
        "current_price": 100.0,
        "market_cap": 1000000000,
        "price_history": [[i, 100 + i % 10] for i in range(60)],
        "volume_history": [[i, 1000000 + (i % 5) * 100000] for i in range(30)],
        "total_supply": 100000000,
        "circulating_supply": 50000000
    }
    
    state.research_data = {
        "token_distribution": [
            {"label": "Team", "value": 20},
            {"label": "Community", "value": 30},
            {"label": "Investors", "value": 25},
            {"label": "Ecosystem", "value": 25}
        ]
    }
    
    state.defillama_data = {
        "tvl": 500000000,
        "tvl_history": [[i * 86400000, 500000000 + (i % 10) * 10000000] for i in range(60)],
        "category": "DEX"
    }
    
    return state

def run_test_pipeline(project_name):
    """Run a test pipeline that mimics the full workflow."""
    logger.info(f"==== Starting test for {project_name} ====")
    
    # Create starting state
    state = create_test_state(project_name)
    if not state:
        logger.error("Failed to create test state")
        return
    
    # Step 1: Generate visualizations
    logger.info("=== STEP 1: Generating visualizations ===")
    vis_config = {
        "use_report_config": True,
        "skip_expensive_descriptions": True
    }
    
    vis_state = visualization_agent(state, llm, logger, vis_config)
    
    if not hasattr(vis_state, 'visualizations') or not vis_state.visualizations:
        logger.error("Visualization step failed - no visualizations in state")
        # Create empty visualizations dict if missing
        vis_state.visualizations = {}
    
    logger.info(f"Visualization state contains {len(vis_state.visualizations)} visualizations")
    
    # Step 2: Write report
    logger.info("=== STEP 2: Writing report ===")
    writer_config = {
        "fast_mode": True,
        "max_tokens_per_section": 250,
        "include_visualizations": True
    }
    
    writer_state = writer(vis_state, llm, logger, writer_config)
    
    if not hasattr(writer_state, 'draft') or not writer_state.draft:
        logger.error("Writer step failed - no draft in state")
        # Create minimal draft in case it's missing
        writer_state.draft = f"# {project_name} Report\n\nThis is a test report."
    
    logger.info(f"Report draft generated with {len(writer_state.draft)} characters")
    
    # Step 3: Publish report
    logger.info("=== STEP 3: Publishing report ===")
    publisher_config = {
        "fast_mode": True,
        "use_report_config": True
    }
    
    # Log visualizations before publishing
    if hasattr(writer_state, 'visualizations'):
        logger.info(f"Visualizations before publishing: {list(writer_state.visualizations.keys())}")
        # Log visualization file paths and existence
        for vis_name, vis_data in writer_state.visualizations.items():
            file_path = vis_data.get('file_path', 'Not found')
            exists = os.path.exists(file_path) if file_path else False
            logger.info(f"Vis {vis_name}: {file_path} (exists: {exists})")
    else:
        logger.error("No visualizations in state before publishing")
    
    # Publish report
    final_state = publisher(writer_state, logger, publisher_config, llm)
    
    # Check result
    pdf_path = f"docs/{project_name}_report.pdf"
    if os.path.exists(pdf_path):
        logger.info(f"Success! PDF report generated at {pdf_path}")
        logger.info(f"PDF size: {os.path.getsize(pdf_path)/1024:.1f} KB")
    else:
        logger.error(f"Failed to generate PDF at {pdf_path}")
    
    logger.info(f"==== Test completed for {project_name} ====")
    return final_state

if __name__ == "__main__":
    # Run tests for a few cryptocurrencies
    projects = ["SUI", "Bitcoin", "Ethereum"]
    
    for project in projects:
        final_state = run_test_pipeline(project)
        if final_state and hasattr(final_state, 'final_report'):
            logger.info(f"Final report: {final_state.final_report}")
        else:
            logger.error(f"No final report for {project}")
        
        logger.info("\n" + "="*50 + "\n") 