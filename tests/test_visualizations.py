import os
import logging
import json
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.visualization_agent import visualization_agent, VisualizationAgent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VisualizationTest")

# Initialize LLM
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment")

llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

def test_visualization(project_name: str):
    """Test visualization generation for a specific project."""
    logger.info(f"Testing visualization generation for {project_name}")
    
    # Set up test state
    state = ResearchState(project_name=project_name)
    
    # Load the report configuration
    try:
        with open("backend/config/report_config.json", "r") as f:
            report_config = json.load(f)
        state.report_config = report_config
        logger.info("Loaded report configuration")
    except Exception as e:
        logger.error(f"Failed to load report config: {e}")
        return
    
    # Create test data
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
    
    # Config for visualization agent
    config = {
        "use_report_config": True,
        "skip_expensive_descriptions": True
    }
    
    # Run visualization agent
    result_state = visualization_agent(state, llm, logger, config)
    
    if not hasattr(result_state, 'visualizations') or not result_state.visualizations:
        logger.error("No visualizations generated in state object")
        return None
    
    # Verify all visualization files exist
    vis_count = len(result_state.visualizations)
    exists_count = 0
    
    for vis_type, vis_data in result_state.visualizations.items():
        file_path = vis_data.get("file_path")
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            exists_count += 1
            logger.info(f"✅ {vis_type}: {file_path} ({file_size/1024:.1f} KB)")
        else:
            logger.error(f"❌ {vis_type}: File not found - {file_path}")
    
    logger.info(f"Found {exists_count}/{vis_count} valid visualization files")
    
    # Get absolute paths for all visualizations for PDF generation
    for vis_type, vis_data in result_state.visualizations.items():
        if "file_path" in vis_data and os.path.exists(vis_data["file_path"]):
            vis_data["absolute_path"] = os.path.abspath(vis_data["file_path"])
            logger.info(f"Absolute path for {vis_type}: {vis_data['absolute_path']}")
    
    logger.info(f"Visualization test for {project_name} completed with {len(result_state.visualizations)} visualizations")
    
    # Return the state with visualizations to be used by the publisher
    return result_state

if __name__ == "__main__":
    # Test for a few different project names
    projects = ["SUI", "Bitcoin", "Ethereum"]
    for project in projects:
        result = test_visualization(project)
        if result and hasattr(result, 'visualizations'):
            logger.info(f"Successfully generated {len(result.visualizations)} visualizations for {project}")
        else:
            logger.error(f"Failed to generate or return visualizations for {project}") 