# backend/agents/reviewer.py
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from backend.utils.state_manager import StateManager
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Define openai_retry_decorator directly in reviewer.py
def openai_retry_decorator(func):
    """
    Decorator to retry OpenAI API calls with exponential backoff.
    Retries up to 3 times with a wait time of 1-5 seconds between attempts.
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying {func.__name__} (attempt {retry_state.attempt_number}/3) due to {retry_state.outcome.exception()}"
        )
    )
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

class Reviewer:
    def __init__(self, llm: Optional[ChatOpenAI] = None, logger: Optional[logging.Logger] = None):
        self.llm = llm
        self.logger = logger or logging.getLogger(__name__)
        self.project_name = None
        
        # Initialize StateManager for consistent state access
        self.state_manager = StateManager(logger=self.logger)
    
    def _extract_sections(self, draft: str) -> Dict[str, str]:
        """
        Extract main sections (level 1 headers) from the draft to process them separately.
        Keeps subsections (level 2+ headers) within their parent section.
        """
        sections = {}
        
        # First check if we have level 1 headers (# Title)
        main_headers_l1 = re.findall(r'^#\s+([^#\n]+?)$', draft, re.MULTILINE)
        
        if main_headers_l1:
            self.logger.info(f"Found {len(main_headers_l1)} main sections (level 1 headers) to review")
            
            # Extract content for each main section by finding content between # headers
            for i, title in enumerate(main_headers_l1):
                if i < len(main_headers_l1) - 1:
                    # Find content between this header and the next main header
                    pattern = fr'^#\s+{re.escape(title)}$.*?(?=^#\s+{re.escape(main_headers_l1[i+1])}$)'
                    content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
                else:
                    # Last section goes to the end of the document
                    pattern = fr'^#\s+{re.escape(title)}$.*'
                    content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
        else:
            # No level 1 headers, try level 2 headers as fallback
            main_headers_l2 = re.findall(r'^##\s+([^#\n]+?)$', draft, re.MULTILINE)
            
            if not main_headers_l2:
                self.logger.warning("No section headers found in draft. Processing as a single document.")
                sections["Full Document"] = draft
                return sections
            
            self.logger.info(f"No level 1 headers found, using {len(main_headers_l2)} level 2 headers instead")
            
            # Extract content for level 2 headers
            for i, title in enumerate(main_headers_l2):
                if i < len(main_headers_l2) - 1:
                    # Find content between this header and the next level 2 header
                    pattern = fr'^##\s+{re.escape(title)}$.*?(?=^##\s+{re.escape(main_headers_l2[i+1])}$)'
                    content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
                else:
                    # Last section goes to the end of the document
                    pattern = fr'^##\s+{re.escape(title)}$.*'
                    content = re.search(pattern, draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
                    
        # Quick validation to ensure we extracted substantial content and combine very small sections
        processed_sections = {}
        current_combined = ""
        current_title = ""
        
        for title, content in sorted(sections.items()):
            word_count = len(content.split())
            self.logger.info(f"Extracted section '{title}' with {word_count} words")
            
            # Handle very small sections
            if word_count < 200:
                if not current_combined:
                    current_combined = content
                    current_title = title
                else:
                    current_combined += "\n\n" + content
                    current_title += " + " + title
            else:
                # Add any pending combined section first
                if current_combined:
                    processed_sections[current_title] = current_combined
                    current_combined = ""
                    current_title = ""
                
                # Add this section
                processed_sections[title] = content
        
        # Add any remaining combined section
        if current_combined:
            processed_sections[current_title] = current_combined
            
        # If we still have too few sections, fall back to treating as one document
        if len(processed_sections) < 3:
            self.logger.warning(f"Only extracted {len(processed_sections)} valid sections after combining. Processing as a single document.")
            processed_sections = {"Full Document": draft}
            
        return processed_sections
    
    def _combine_sections(self, sections: Dict[str, str]) -> str:
        """Combine the reviewed sections back into a full document."""
        # Sort sections to maintain original order (if we have order info)
        return "\n\n".join(sections.values())
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the reviewer to polish the draft report."""
        try:
            # Get project name from state using StateManager
            self.project_name = self.state_manager.get_project_name(state)
            self.logger.info(f"Running reviewer for {self.project_name}")
            
            # Initialize or update progress using StateManager
            state = self.state_manager.update_progress(state, f"Reviewing draft report for {self.project_name}...")
            
            # Get draft from state using StateManager
            draft = self.state_manager.get_draft(state)
            if not draft:
                self.logger.error("No draft available for review")
                return self.state_manager.add_error(state, "reviewer", "No draft available for review")
            
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
                    state = self.state_manager.update_final_report(state, draft)
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
                references = self.state_manager.get_references(state)
                if "## References" not in reviewed_draft and references:
                    references_section = "\n\n## References\n" + "\n".join(
                        [f"- {ref['title']}: [{ref['url']}]({ref['url']})" for ref in references]
                    )
                    reviewed_draft += references_section
                
                # Update state with final report using StateManager
                state = self.state_manager.update_final_report(state, reviewed_draft)
                state = self.state_manager.update_progress(state, f"Final report polished for {self.project_name}")
                
                return state
                
            except Exception as e:
                self.logger.error(f"Error reviewing draft: {str(e)}", exc_info=True)
                # Add error to state using StateManager
                state = self.state_manager.update_final_report(state, draft)  # Use original draft on error
                return state
                
        except Exception as e:
            self.logger.error(f"Error in reviewer run: {str(e)}", exc_info=True)
            # Add error to state using StateManager
            return self.state_manager.add_error(state, "reviewer", str(e))

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
    # Use our own logger if not provided
    if not logger:
        logger = logging.getLogger(__name__)
    
    # Create a state manager
    state_manager = StateManager(logger=logger)
    
    # Get project name from state
    project_name = state_manager.get_project_name(state)
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
                return state_manager.add_error(state, "reviewer", f"Invalid result type: {type(result)}")
            
        except Exception as e:
            # Handle errors in asyncio execution
            logger.error(f"Error in reviewer_sync asyncio execution: {str(e)}", exc_info=True)
            return state_manager.add_error(state, "reviewer_asyncio", str(e))
            
    except Exception as e:
        # Handle errors in reviewer creation or other setup
        logger.error(f"Error in reviewer_sync setup: {str(e)}", exc_info=True)
        return state_manager.add_error(state, "reviewer_setup", str(e))

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
        # Add error to state using StateManager
        state_manager = StateManager(logger=logger)
        return state_manager.add_error(state, "reviewer", str(e))