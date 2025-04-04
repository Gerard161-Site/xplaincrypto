# test_inference.py
import asyncio
from backend.state import ResearchState
from backend.agents.enhanced_researcher import enhanced_researcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestInference")

async def test_inference():
    state = ResearchState("ONDO")
    state.research_data = {"current_price": 0.86, "market_cap": 3_000_000_000}
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(temperature=0)
    state = await enhanced_researcher.enhanced_researcher(state, llm, logger)
    print(f"Inferred fields: {state.research_data}")
    print(f"Errors: {state.errors}")

if __name__ == "__main__":
    asyncio.run(test_inference())