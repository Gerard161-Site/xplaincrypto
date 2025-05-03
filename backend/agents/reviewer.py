# backend/agents/reviewer.py
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from backend.state import ResearchState

class Reviewer:
    def __init__(self, llm: Optional[ChatOpenAI] = None, logger: Optional[logging.Logger] = None):
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)
        self.project_name = None
    
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
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the reviewer to polish the draft report."""
        try:
            # Get project name from state
            self.project_name = state.get("project_name", "Unknown Project")
            self.logger.info(f"Running reviewer for {self.project_name}")
            
            # Create temp state for backward compatibility
            temp_state = ResearchState(project_name=self.project_name)
            for key, value in state.items():
                if hasattr(temp_state, key):
                    setattr(temp_state, key, value)
            
            # Initialize or update progress
            if "progress" not in state:
                state["progress"] = {}
            
            # Ensure progress is a dictionary
            if not isinstance(state["progress"], dict):
                state["progress"] = {}
                
            # Update progress for reviewer
            state["progress"]["reviewer"] = f"Reviewing draft report for {self.project_name}..."
            
            if not hasattr(temp_state, 'draft') or not temp_state.draft:
                self.logger.error("No draft available for review")
                state["errors"] = state.get("errors", {})
                state["errors"]["reviewer"] = "No draft available for review"
                return state
            
            draft = temp_state.draft
            
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
                    state["final_report"] = draft
                    return state
                
                # Review each section separately
                reviewed_sections = {}
                section_count = 0
                
                for title, content in sections.items():
                    # Only review substantial sections
                    if len(content.split()) > 50:
                        section_count += 1
                        self.logger.info(f"Reviewing section {section_count}/{len(sections)}: '{title}' ({len(content.split())} words)")
                        
                        section_prompt = (
                            f"Review and polish this section on '{title}' from a report about {self.project_name} cryptocurrency:\n\n"
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
                if "## References" not in reviewed_draft and hasattr(temp_state, 'references') and temp_state.references:
                    references = "\n\n## References\n" + "\n".join(
                        [f"- {ref['title']}: [{ref['url']}]({ref['url']})" for ref in temp_state.references]
                    )
                    reviewed_draft += references
                
                # Update state with final report
                state["final_report"] = reviewed_draft
                state["progress"]["reviewer"] = f"Final report polished for {self.project_name}"
                
                return state
                
            except Exception as e:
                self.logger.error(f"Error reviewing draft: {str(e)}", exc_info=True)
                state["errors"] = state.get("errors", {})
                state["errors"]["reviewer"] = str(e)
                state["final_report"] = draft  # Return original draft on error
                return state
                
        except Exception as e:
            self.logger.error(f"Error in reviewer run: {str(e)}", exc_info=True)
            state["errors"] = state.get("errors", {})
            state["errors"]["reviewer"] = str(e)
            return state

def reviewer_sync(state: Dict, llm: Optional[ChatOpenAI] = None, logger: Optional[logging.Logger] = None, config: Optional[Dict[str, Any]] = None) -> Dict:
    """
    Synchronous wrapper for the Reviewer class to be used in the workflow.
    This function matches the expected signature in workflow_manager.py.
    
    Args:
        state: The current workflow state
        llm: The language model instance (optional)
        logger: Logger instance (optional)
        config: Additional configuration (optional)
        
    Returns:
        Updated state with reviewed report
    """
    # Return a copy of the state to avoid modifying the original
    updated_state = state.copy() if isinstance(state, dict) else state
    
    # Use our own logger if not provided
    if not logger:
        logger = logging.getLogger(__name__)
    
    # Get project name from state
    project_name = state.get("project_name", "Unknown Project") if isinstance(state, dict) else getattr(state, "project_name", "Unknown Project")
    logger.info(f"Starting reviewer_sync for project: {project_name}")
    
    try:
        # Create a new reviewer instance
        reviewer_instance = Reviewer(llm=llm, logger=logger)
        
        # Run the async agent in a synchronous context
        import asyncio
        
        try:
            # Simple approach: Create a new event loop and run the coroutine directly
            # This is safer than trying to use an existing loop with complex nesting patterns
            result = asyncio.run(reviewer_instance.run(state))
            
            # If we got a valid result from the reviewer, return it
            if isinstance(result, dict):
                logger.info(f"Reviewer completed successfully")
                return result
            else:
                logger.warning(f"Reviewer returned non-dict result: {type(result)}")
                if isinstance(updated_state, dict):
                    if "errors" not in updated_state:
                        updated_state["errors"] = {}
                    updated_state["errors"]["reviewer"] = f"Invalid result type: {type(result)}"
                return updated_state
            
        except Exception as e:
            # Handle errors in asyncio execution
            logger.error(f"Error in reviewer_sync asyncio execution: {str(e)}", exc_info=True)
            if isinstance(updated_state, dict):
                if "errors" not in updated_state:
                    updated_state["errors"] = {}
                updated_state["errors"]["reviewer_asyncio"] = str(e)
            return updated_state
            
    except Exception as e:
        # Handle errors in reviewer creation or other setup
        logger.error(f"Error in reviewer_sync setup: {str(e)}", exc_info=True)
        if isinstance(updated_state, dict):
            if "errors" not in updated_state:
                updated_state["errors"] = {}
            updated_state["errors"]["reviewer_setup"] = str(e)
        return updated_state

# Legacy standalone function for backward compatibility
async def reviewer(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    """Legacy function interface for reviewer."""
    logger = logger or logging.getLogger(__name__)
    logger.info("Using legacy reviewer function with Reviewer class")
    
    # Create and initialize a reviewer instance
    reviewer_instance = Reviewer(llm=llm, logger=logger)
    
    # Run the reviewer
    try:
        updated_state = await reviewer_instance.run(state)
        return updated_state
    except Exception as e:
        logger.error(f"Error in legacy reviewer function: {str(e)}", exc_info=True)
        # Ensure state has error field
        if not hasattr(state, 'errors'):
            state["errors"] = {}
        state["errors"]["reviewer"] = str(e)
        return state