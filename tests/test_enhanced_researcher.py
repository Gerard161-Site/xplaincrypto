import asyncio
import logging
import json
import os
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.agents.enhanced_researcher import enhanced_researcher
from backend.agents.writer import writer

async def test_enhanced_researcher_with_writer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("TestEnhancedResearcherWriter")

    llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
    state = ResearchState(project_name="ONDO")
    state.report_config = json.load(open("backend/config/report_config.json"))

    # Run researcher
    start_time = asyncio.get_event_loop().time()
    state = await enhanced_researcher(state, llm, logger)
    research_elapsed = asyncio.get_event_loop().time() - start_time

    # Validate researcher output
    assert state.queries, "No queries generated"
    assert len(state.queries) == 13, f"Expected 13 queries, got {len(state.queries)}"
    assert state.research_complete, "Research not completed"
    assert "tokenomics" in state.research_data, "Tokenomics data missing"
    logger.info(f"Completed research for ONDO in {research_elapsed:.2f} seconds with {len(state.references)} references")

    # Run writer
    config = {"hf_api_token": os.getenv("HUGGINGFACE_API_KEY")}
    state = writer(state, llm, logger, config)
    writer_elapsed = asyncio.get_event_loop().time() - start_time - research_elapsed

    # Validate writer output
    assert state.draft, "No draft generated"
    assert "ONDO Research Report" in state.draft, "Draft missing title"
    assert all(section["title"] in state.draft for section in state.report_config["sections"]), "Missing sections in draft"
    logger.info(f"Completed writer for ONDO in {writer_elapsed:.2f} seconds, draft length: {len(state.draft.split())} words")

if __name__ == "__main__":
    asyncio.run(test_enhanced_researcher_with_writer())