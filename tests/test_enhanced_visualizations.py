import os
import logging
import json
import argparse
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.visualization_agent import visualization_agent, VisualizationAgent
from tests.test_enhanced_data_modules import EnhancedDataGatherer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("EnhancedVisualizationTest")

def test_enhanced_visualizations(project_name: str, use_real_data: bool = True):
    """Test visualization generation with enhanced data sources."""
    logger.info(f"Testing enhanced visualization generation for {project_name}")
    
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
    
    # Get real data from APIs using enhanced data gatherer
    if use_real_data:
        logger.info(f"Gathering real data for {project_name} using enhanced data gatherer")
        try:
            # Clean up cache first
            cache_dir = "cache"
            os.makedirs(cache_dir, exist_ok=True)
            for file in os.listdir(cache_dir):
                if file.startswith(project_name) and file.endswith(".json"):
                    os.remove(os.path.join(cache_dir, file))
                    logger.info(f"Cleared cache file: {file}")
            
            # Gather real data
            data_gatherer = EnhancedDataGatherer(project_name, logger)
            all_data = data_gatherer.gather_all_data(use_cache=False)
            
            # Split data into appropriate state fields
            coingecko_data = {}
            coinmarketcap_data = {}
            defillama_data = {}
            research_data = {}
            
            # Sort the data into the appropriate buckets based on field names
            for key, value in all_data.items():
                if key in ["price_history", "volume_history", "current_price", "market_cap", 
                          "total_supply", "circulating_supply", "max_supply"]:
                    coingecko_data[key] = value
                elif key in ["price_change_percentage_24h"]:
                    coinmarketcap_data[key] = value
                elif key in ["tvl", "tvl_history"]:
                    defillama_data[key] = value
                elif key in ["token_distribution", "competitors"]:
                    research_data[key] = value
                else:
                    # Put other fields in multiple data sources
                    coingecko_data[key] = value
                    coinmarketcap_data[key] = value
                    defillama_data[key] = value
            
            # Add competitors data to coingecko_data as well
            if "competitors" in research_data:
                coingecko_data["competitors"] = research_data["competitors"]
            
            # Update state
            state.coingecko_data = coingecko_data
            state.coinmarketcap_data = coinmarketcap_data
            state.defillama_data = defillama_data
            state.research_data = research_data
            state.data = all_data  # Combined data
            
            logger.info(f"Data assigned to state: CoinGecko ({len(coingecko_data)} fields), "
                       f"CoinMarketCap ({len(coinmarketcap_data)} fields), "
                       f"DeFiLlama ({len(defillama_data)} fields), "
                       f"Research ({len(research_data)} fields)")
        except Exception as e:
            logger.error(f"Error gathering data: {str(e)}", exc_info=True)
            logger.warning("Falling back to synthetic test data")
            use_real_data = False
    
    # If not using real data or real data gathering failed, use synthetic test data
    if not use_real_data:
        logger.info("Using synthetic test data")
        
        # Create test data similar to what's in test_visualizations.py but more complete
        state.coingecko_data = {
            "current_price": 100.0,
            "market_cap": 1000000000,
            "price_history": [[int(1000 * 1000000000) - (i * 86400000), 100 + i % 10] for i in range(60)],
            "volume_history": [[int(1000 * 1000000000) - (i * 86400000), 1000000 + (i % 5) * 100000] for i in range(30)],
            "total_supply": 100000000,
            "circulating_supply": 50000000,
            "max_supply": 100000000,
            "price_change_percentage_24h": 2.5
        }
        
        state.coinmarketcap_data = {
            "current_price": 100.0,
            "market_cap": 1000000000,
            "price_change_percentage_24h": 2.5,
            "24h_volume": 150000000
        }
        
        state.defillama_data = {
            "tvl": 500000000,
            "tvl_history": [[int(1000 * 1000000000) - (i * 86400000), 500000000 + (i % 10) * 10000000] for i in range(60)],
            "category": "DEX"
        }
        
        state.research_data = {
            "token_distribution": {
                "Team": 20,
                "Community": 30,
                "Investors": 25,
                "Ecosystem": 25
            },
            "competitors": {
                "Ethereum": {
                    "market_cap": 200000000000,
                    "price_change_percentage_24h": 1.5
                },
                "Solana": {
                    "market_cap": 20000000000, 
                    "price_change_percentage_24h": 3.0
                }
            }
        }
        
        # Combine all data into one data field as well
        state.data = {}
        state.data.update(state.coingecko_data)
        state.data.update(state.coinmarketcap_data)
        state.data.update(state.defillama_data)
        state.data.update(state.research_data)
    
    # Initialize LLM if API key is available
    api_key = os.getenv("OPENAI_API_KEY")
    llm = None
    if api_key:
        try:
            llm = ChatOpenAI(model="gpt-4-mini", api_key=api_key) 
            logger.info("Successfully initialized LLM")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
    else:
        logger.warning("OPENAI_API_KEY not found in environment, descriptions will be generic")
    
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
    
    # Display all available fields for reference
    logger.info("Available data fields that could be used for visualizations:")
    if hasattr(state, 'data') and state.data:
        logger.info(f"Fields: {', '.join(list(state.data.keys()))}")
    
    # Return the state with visualizations
    return result_state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test enhanced visualizations for cryptocurrency projects")
    parser.add_argument("--project", type=str, default="Bitcoin", help="Project name to test")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic data instead of real API data")
    args = parser.parse_args()
    
    # Run the test
    result = test_enhanced_visualizations(args.project, use_real_data=not args.synthetic)
    
    if result and hasattr(result, 'visualizations'):
        logger.info(f"Successfully generated {len(result.visualizations)} visualizations for {args.project}")
    else:
        logger.error(f"Failed to generate or return visualizations for {args.project}") 