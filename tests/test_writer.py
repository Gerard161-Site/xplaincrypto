# test_writer.py
import logging
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.writer import WriterAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestWriter")

# Mock report config
report_config = {
    "sections": [
        {"title": "Introduction", "prompt": "Intro to project", "min_words": 50, "max_words": 100},
        {"title": "Tokenomics", "prompt": "Token economics", "min_words": 50, "max_words": 100, "visualizations": ["supply_metrics_table"]}
    ],
    "visualization_types": {
        "supply_metrics_table": {"data_fields": ["total_supply", "circulating_supply"]}
    }
}

def test_writer():
    # Initialize state
    state = ResearchState(project_name="TestCoin")
    state.report_config = report_config
    state.research_data = {"total_supply": 1000000}
    state.structured_data = {"circulating_supply": 500000}
    
    # Mock LLM
    class MockLLM:
        def invoke(self, prompt):
            return type('Response', (), {'content': f"Generated content for {prompt[:20]}..."})()
    
    # Test writer
    writer_agent = WriterAgent(llm=MockLLM(), logger=logger, hf_api_token="mock_hf_token")
    draft = writer_agent.write_draft(state)
    
    # Assertions
    assert "TestCoin Research Report" in draft
    assert "Introduction" in draft
    assert "Tokenomics" in draft
    assert len(draft.split()) > 50  # Rough check for content
    logger.info("Writer test passed!")

if __name__ == "__main__":
    test_writer()