# backend/agents/reviewer.py
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from backend.state import ResearchState

class ReviewerAgent:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        self.llm = llm
        self.logger = logger
    
    def _extract_sections(self, draft: str) -> Dict[str, str]:
        """Extract sections from the draft to process them separately."""
        sections = {}
        
        # Get section headers
        headers = re.findall(r'^(#+)\s+(.*?)$', draft, re.MULTILINE)
        if not headers:
            # No sections found, treat the entire document as one section
            sections["Full Document"] = draft
            return sections
        
        # Extract content for each section
        for i, (level, title) in enumerate(headers):
            if i < len(headers) - 1:
                # Find the content between this header and the next
                pattern = fr'^{re.escape(level)}\s+{re.escape(title)}$.*?(?=^{re.escape(headers[i+1][0])}\s+{re.escape(headers[i+1][1])}$)'
                content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                if content:
                    sections[title] = content.group(0).strip()
            else:
                # Last section goes to the end of the document
                pattern = fr'^{re.escape(level)}\s+{re.escape(title)}$.*'
                content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                if content:
                    sections[title] = content.group(0).strip()
                    
        return sections
    
    def _combine_sections(self, sections: Dict[str, str]) -> str:
        """Combine the reviewed sections back into a full document."""
        # Sort sections to maintain original order (if we have order info)
        return "\n\n".join(sections.values())
    
    def review_draft(self, state: ResearchState) -> str:
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
        
        review_instructions = (
            f"Focus on:\n"
            "1. Ensuring an objective, balanced perspective—highlight both strengths and risks without bias.\n"
            "2. Verifying all investment-relevant information (e.g., market position, growth potential, risks) is clearly presented and actionable.\n"
            "3. Highlighting risk factors appropriately, ensuring they are not downplayed and include clear implications for investors.\n"
            "4. Ensuring conclusions in each section follow logically from the evidence, avoiding unsupported claims.\n"
            "5. Confirming the Executive Summary reflects the full report content, focusing on high-level insights without repeating detailed metrics from other sections.\n"
            "6. Polishing language for clarity, conciseness, and professional impact—use precise, direct sentences and avoid redundancy.\n"
            "7. Ensuring numerical data (e.g., price, market cap, supply, TVL) is consistent across all sections—cross-check values and correct discrepancies.\n\n"
            "Preserve the structure and core content, making only necessary changes to meet investment-grade quality. Return the revised section in markdown format."
        )
        
        try:
            # Split the draft into sections to avoid context limit issues
            sections = self._extract_sections(draft)
            self.logger.info(f"Split draft into {len(sections)} sections for review")
            
            # Check if we actually have a substantive draft to review
            total_words = sum(len(content.split()) for content in sections.values())
            if total_words < 100:
                self.logger.warning(f"Draft is too short to review properly: {total_words} words")
                return draft  # Return original if too short
            
            # Review each section separately
            reviewed_sections = {}
            section_count = 0
            
            for title, content in sections.items():
                # Only review substantial sections
                if len(content.split()) > 50:
                    section_count += 1
                    self.logger.info(f"Reviewing section {section_count}/{len(sections)}: '{title}' ({len(content.split())} words)")
                    
                    section_prompt = (
                        f"Review and polish this section on '{title}' from a report about {state.project_name} cryptocurrency:\n\n"
                        f"{content}\n\n"
                        f"{metrics_note}\n"
                        f"{review_instructions}"
                    )
                    
                    try:
                        # Force synchronous execution to ensure each review completes
                        reviewed_content = self.llm.invoke(section_prompt).content
                        
                        # Basic validation of content quality
                        if len(reviewed_content.split()) < len(content.split()) * 0.5:
                            self.logger.warning(f"Review produced suspiciously short content for '{title}', using original")
                            reviewed_sections[title] = content
                        else:
                            reviewed_sections[title] = reviewed_content
                            self.logger.info(f"Successfully reviewed section '{title}': {len(reviewed_content.split())} words")
                    except Exception as e:
                        self.logger.error(f"Error reviewing section '{title}': {str(e)}")
                        reviewed_sections[title] = content  # Use original content if review fails
                else:
                    # Section too small to review
                    reviewed_sections[title] = content
            
            # Combine the reviewed sections
            reviewed_draft = self._combine_sections(reviewed_sections)
            
            # Final validation to ensure we have a reasonable result
            if len(reviewed_draft.split()) < len(draft.split()) * 0.5:
                self.logger.error(f"Review produced a much shorter document than the original. Using original draft.")
                reviewed_draft = draft
            
            self.logger.info(f"Completed review: {len(reviewed_draft.split())} words from original {len(draft.split())} words")
            
            # Add references if they're missing
            if "## References" not in reviewed_draft and hasattr(state, 'references') and state.references:
                references = "\n\n## References\n" + "\n".join(
                    [f"- {ref['title']}: [{ref['url']}]({ref['url']})" for ref in state.references]
                )
                reviewed_draft += references
            
            return reviewed_draft
        except Exception as e:
            self.logger.error(f"Error reviewing draft: {str(e)}", exc_info=True)
            return draft

async def reviewer(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    # Get project name
    project_name = state.get("project_name", "Unknown Project")
    logger.info(f"Reviewer agent processing for {project_name}")
    
    # Update progress
    if hasattr(state, 'update_progress'):
        state.update_progress(f"Reviewing draft report for {project_name}...")
    else:
        state["progress"] = f"Reviewing draft report for {project_name}..."
    
    # Create temp state for backward compatibility
    temp_state = ResearchState(project_name=project_name)
    for key, value in state.items():
        if hasattr(temp_state, key):
            setattr(temp_state, key, value)
            
    # Run review
    agent = ReviewerAgent(llm, logger)
    final_report = agent.review_draft(temp_state)
    
    # Update state
    state["final_report"] = final_report
    
    # Update progress
    if hasattr(state, 'update_progress'):
        state.update_progress(f"Final report polished for {project_name}")
    else:
        state["progress"] = f"Final report polished for {project_name}"
    
    return state

review = reviewer