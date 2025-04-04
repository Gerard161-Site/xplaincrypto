import asyncio
import logging
import json
import os
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.enhanced_researcher import enhanced_researcher
from backend.agents.writer import writer
from backend.agents.visualization_agent import visualization_agent  # New import

async def test_pipeline():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("TestPipeline")
    llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
    state = ResearchState(project_name="ONDO")
    state.report_config = json.load(open("backend/config/report_config.json"))
    
    # Run researcher
    start_time = asyncio.get_event_loop().time()
    state = await enhanced_researcher(state, llm, logger)
    research_elapsed = asyncio.get_event_loop().time() - start_time
    assert state.queries, "No queries generated"
    assert len(state.queries) == 13, f"Expected 13 queries, got {len(state.queries)}"
    assert state.root_node.children, "Research tree has no sections"
    assert len(state.root_node.children) >= 13, f"Expected at least 13 sections, got {len(state.root_node.children)}"
    assert state.research_complete, "Research incomplete"
    logger.info(f"Research completed in {research_elapsed:.2f} seconds with {len(state.references)} references")
    
    # Run writer
    writer_start_time = asyncio.get_event_loop().time()
    state = await writer(state, llm, logger, {"hf_api_token": os.getenv("HUGGINGFACE_API_KEY")})
    writer_elapsed = asyncio.get_event_loop().time() - writer_start_time
    assert state.draft, "No draft generated"
    assert "ONDO Research Report" in state.draft, "Draft missing title"
    logger.info(f"Writing completed in {writer_elapsed:.2f} seconds")
    
    # Run visualization agent
    vis_start_time = asyncio.get_event_loop().time()
    state = await visualization_agent(state, llm, logger)
    vis_elapsed = asyncio.get_event_loop().time() - vis_start_time
    assert state.visualizations, "No visualizations generated"
    logger.info(f"Visualizations completed in {vis_elapsed:.2f} seconds with {len(state.visualizations)} visuals")
    
    total_time = asyncio.get_event_loop().time() - start_time
    logger.info(f"Test completed: {len(state.draft.split())} words in total time {total_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(test_pipeline())