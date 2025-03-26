import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from backend.state import ResearchState

class ReviewerAgent:
    """Agent responsible for reviewing and polishing the draft report."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        self.llm = llm
        self.logger = logger
    
    def review_draft(self, state: ResearchState) -> str:
        """Review and refine the draft report for consistency and quality."""
        self.logger.info(f"Reviewing draft for {state.project_name}")
        
        if not hasattr(state, 'draft') or not state.draft:
            self.logger.error("No draft available for review")
            return "Error: No draft available for review"
        
        draft = state.draft
        
        metrics_note = """
IMPORTANT INSTRUCTIONS:
1. Maintain all exact numerical values (prices, market cap, trading volume, etc.) throughout the document.
2. DO NOT replace specific figures with placeholders like '$X' or 'Y tokens'.
3. DO NOT attempt to add or reference tables or images directly in the text.
4. Focus only on improving the quality of the existing text content.
5. Ensure each section focuses on its unique scope as defined in the report configuration, avoiding overlap with other sections.
6. Maintain a professional, investment-grade tone suitable for crypto investors and analysts.
"""
        
        prompt = (
            f"Review and polish this draft report for {state.project_name} cryptocurrency to ensure it meets investment-grade quality for professional crypto investors and analysts:\n\n"
            f"{draft}\n\n"
            f"{metrics_note}\n"
            f"Focus on:\n"
            "1. Ensuring an objective, balanced perspective throughout—highlight both strengths and risks without bias.\n"
            "2. Verifying all investment-relevant information (e.g., market position, growth potential, risks) is clearly presented and actionable for decision-making.\n"
            "3. Highlighting risk factors appropriately, ensuring they are not downplayed and include clear implications for investors.\n"
            "4. Ensuring conclusions in each section follow logically from the evidence, avoiding unsupported claims.\n"
            "5. Confirming the Executive Summary reflects the full report content, focusing on high-level insights (e.g., strategic positioning, investment potential) without repeating detailed metrics from other sections.\n"
            "6. Polishing language for clarity, conciseness, and professional impact—use precise, direct sentences and avoid redundancy.\n"
            "7. Ensuring numerical data (e.g., price, market cap, supply, trading volume, TVL) is consistent across all sections—cross-check values and correct any discrepancies.\n\n"
            "Preserve the structure and core content, making only necessary changes to meet investment-grade quality. "
            "Return the revised report in markdown format."
        )
        
        try:
            reviewed_draft = self.llm.invoke(prompt).content
            self.logger.info(f"Draft reviewed: {len(reviewed_draft.split())} words")
            
            if "## References" not in reviewed_draft and hasattr(state, 'references'):
                references = "\n\n## References\n" + "\n".join(
                    [f"- {ref['title']}: [{ref['url']}]({ref['url']})" for ref in state.references]
                )
                reviewed_draft += references
            
            return reviewed_draft
        except Exception as e:
            self.logger.error(f"Error reviewing draft: {str(e)}")
            return draft

def reviewer(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> ResearchState:
    """Integrate reviewer agent into the research workflow."""
    logger.info(f"Reviewer agent processing for {state.project_name}")
    state.update_progress(f"Reviewing draft report for {state.project_name}...")
    
    agent = ReviewerAgent(llm, logger)
    final_report = agent.review_draft(state)
    state.final_report = final_report
    state.update_progress(f"Final report polished for {state.project_name}")
    
    return state

# Alias for compatibility with potential original naming
review = reviewer