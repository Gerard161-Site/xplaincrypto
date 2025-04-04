# test_visualizations.py
import asyncio
from backend.state import ResearchState
from backend.agents.visualization_agent import VisualizationAgent
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestVisualizations")

async def test_visualizations():
    state = ResearchState("ONDO")
    with open("backend/config/report_config.json", "r") as f:
        state.report_config = json.load(f)
    
    # Mock data
    state.research_data = {
        "current_price": 0.86,
        "market_cap": 3_000_000_000,
        "24h_volume": 50_000_000,
        "tvl": 100_000_000,
        "total_supply": 10_000_000_000,
        "circulating_supply": 3_500_000_000,
        "price_history": [[int(time.time() * 1000 - i * 86400000), 0.8 + i * 0.01] for i in range(60)],
        "volume_history": [[int(time.time() * 1000 - i * 86400000), 45_000_000 + i * 100_000] for i in range(30)],
        "tvl_history": [[int(time.time() * 1000 - i * 86400000), 90_000_000 + i * 500_000] for i in range(60)],
        "competitors": {
            "ETH": {"market_cap": 300_000_000_000, "price_change_percentage_24h": 2.5},
            "SOL": {"market_cap": 50_000_000_000, "price_change_percentage_24h": -1.0}
        }
    }
    
    agent = VisualizationAgent("ONDO", logger)
    vis_types = [
        "price_history_chart", "volume_chart", "tvl_chart", "liquidity_trends_chart",
        "competitor_comparison_chart", "token_distribution_pie", "key_metrics_table",
        "basic_metrics_table", "supply_metrics_table", "adoption_metrics_table"
    ]
    
    for vis_type in vis_types:
        result = await agent.generate_visualization(vis_type, state)
        if "error" in result:
            logger.error(f"Failed {vis_type}: {result['error']}")
        else:
            logger.info(f"Generated {vis_type}: {result['file_path']}")

if __name__ == "__main__":
    asyncio.run(test_visualizations())