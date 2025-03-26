from langchain_openai import ChatOpenAI
import logging
import re
from backend.state import ResearchState

def editor(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> ResearchState:
    """Edit the report draft for clarity, conciseness, and style."""
    try:
        logger.info("Editor agent starting")
        
        # Debug incoming state
        logger.debug(f"EDITOR DEBUG - Incoming state type: {type(state)}")
        if isinstance(state, dict):
            logger.debug(f"EDITOR DEBUG - Incoming state keys: {list(state.keys())}")
        else:
            logger.debug(f"EDITOR DEBUG - Incoming state dir: {[attr for attr in dir(state) if not attr.startswith('_') and not callable(getattr(state, attr))]}")
        
        # Get draft and update metrics
        draft = ""
        if isinstance(state, dict):
            draft = state.get("draft", "")
            if not draft and "report_sections" in state:
                # Draft might be stored in sections
                draft = "\n\n".join([f"## {section.get('title', '')}\n\n{section.get('content', '')}" 
                                 for section in state.get("report_sections", [])])
        else:
            draft = getattr(state, "draft", "")

        logger.info(f"Performing comprehensive editing for {state.project_name}")
        state.update_progress(f"Editing draft for {state.project_name}...")

        # Check for any issues with section formatting
        fixed_draft = fix_section_formatting(draft)
        
        # Add instructions about preserving exact metrics and avoiding repetition
        metrics_note = """
IMPORTANT INSTRUCTIONS:
1. Maintain all exact numerical values (prices, market cap, trading volume, etc.) throughout the document.
2. DO NOT replace specific figures with placeholders like '$X' or 'Y tokens'.
3. DO NOT attempt to add or reference tables or images directly in the text.
4. Focus only on improving the quality of the existing text content.
5. Avoid repetition of information across sections—each section should have a unique focus as defined in the report configuration.
6. Ensure the report maintains a professional, investment-grade tone suitable for crypto investors and analysts.
"""
        
        # Perform editing in stages for better results
        
        # Stage 1: Fix structural issues and ensure consistent formatting
        structure_prompt = f"""Improve the structure and formatting of this crypto research report on {state.project_name}.
        
{metrics_note}
        
Focus on:
1. Ensuring all section headings are properly formatted and consistent (e.g., ## Section Title).
2. Organizing content logically within each section, using subheadings where appropriate for clarity.
3. Ensuring each section focuses on its unique scope as defined in the report configuration, avoiding overlap with other sections.
4. Making sure the report flows naturally from one section to the next with clear transitions.
5. Ensuring all markdown formatting is correct and consistent.

Only fix structural/formatting issues and section organization. DO NOT change the factual content.
        
{fixed_draft}
        """
        
        logger.debug("Improving report structure and formatting")
        structured_draft = llm.invoke(structure_prompt).content
        
        # Stage 2: Improve content quality, clarity, and professional tone
        content_prompt = f"""Polish this {state.project_name} research report for professional quality and clarity.
        
{metrics_note}
        
Focus on:
1. Ensuring a professional, objective tone suitable for crypto investors and analysts, avoiding speculative or promotional language.
2. Improving clarity and readability with precise, concise wording—eliminate jargon unless necessary and define terms where appropriate.
3. Eliminating redundancy and wordiness within sections, ensuring each paragraph adds unique value.
4. Ensuring consistent tense (use present tense unless discussing historical data) and point of view (third-person objective).
5. Enhancing readability with smooth transitions between ideas and paragraphs.
6. Maintaining appropriate formality for a financial research document, avoiding casual language.
7. Ensuring claims are properly qualified (e.g., "as of [date]" for time-sensitive data).

Maintain all existing sections, facts, and information—only improve the writing quality.
        
{structured_draft}
        """
        
        logger.debug("Improving report content quality and clarity")
        polished_draft = llm.invoke(content_prompt).content
        
        # Stage 3: Perform fact-checking and ensure consistency
        fact_check_prompt = f"""Review this {state.project_name} research report for factual consistency and accuracy.
        
{metrics_note}
        
Focus on:
1. Ensuring all numerical data (e.g., price, market cap, supply, trading volume, TVL) is presented consistently across all sections—cross-check values and correct any discrepancies.
2. Resolving contradictions or inconsistencies in information (e.g., conflicting statements about token supply or market performance).
3. Verifying that tokenomics figures (e.g., total supply, circulating supply, allocation percentages) are consistent across sections.
4. Ensuring claims are proportional and not overstated—qualify statements with data sources or timeframes where necessary.
5. Removing speculative statements unless clearly labeled as such (e.g., "Analysts predict..." should be supported by data or removed).

Make only the necessary changes to ensure factual consistency—preserve the overall content and structure.
        
{polished_draft}
        """
        
        logger.debug("Performing fact-checking and consistency review")
        fact_checked_draft = llm.invoke(fact_check_prompt).content
        
        # Stage 4: Final polish and executive quality check
        final_prompt = f"""Perform a final review and polish of this {state.project_name} cryptocurrency research report to ensure investment-grade quality for professional crypto investors and analysts.
        
{metrics_note}
        
Focus on:
1. Ensuring an objective, balanced perspective throughout—highlight both strengths and risks without bias.
2. Verifying all investment-relevant information (e.g., market position, growth potential, risks) is clearly presented and actionable.
3. Ensuring risk factors are appropriately highlighted and not downplayed, with clear implications for investors.
4. Checking that conclusions in each section follow logically from the presented evidence, avoiding unsupported claims.
5. Ensuring the Executive Summary accurately reflects the full report content, focusing on high-level insights (e.g., strategic positioning, investment potential) without repeating detailed metrics from other sections.
6. Polishing language for maximum clarity, impact, and professionalism—use concise, direct sentences and avoid redundancy.

The report should meet the quality standards expected by professional crypto investors and analysts, providing actionable insights for investment decisions.
        
{fact_checked_draft}
        """
        
        logger.debug("Performing final quality review")
        edited_draft = llm.invoke(final_prompt).content
        
        # Store the final edited version
        state.final_report = edited_draft

        # Calculate improvement metrics
        original_words = len(draft.split())
        edited_words = len(edited_draft.split())
        word_diff = edited_words - original_words
        
        logger.info(f"Editing completed: {original_words} words → {edited_words} words ({word_diff:+d} words)")
        
        # Debug log what's in the state
        if isinstance(state, dict):
            logger.debug(f"EDITOR DEBUG - Dict-style state output with keys: {state.keys()}")
            if "sections" in state:
                logger.debug(f"EDITOR DEBUG - Number of sections: {len(state['sections'])}")
                for i, section in enumerate(state["sections"]):
                    logger.debug(f"EDITOR DEBUG - Section {i} title: {section.get('title', 'No title')} ({len(section.get('content', '').split())} words)")
        else:
            logger.debug(f"EDITOR DEBUG - Object-style state output")
            if hasattr(state, "sections"):
                logger.debug(f"EDITOR DEBUG - Number of sections: {len(state.sections)}")
                for i, section in enumerate(state.sections):
                    title = section.title if hasattr(section, "title") else "No title"
                    content = section.content if hasattr(section, "content") else ""
                    logger.debug(f"EDITOR DEBUG - Section {i} title: {title} ({len(content.split())} words)")
                
        state.update_progress("Comprehensive editing completed.")
        return state
    except Exception as e:
        logger.error(f"Editor agent encountered an error: {e}")
        raise

def fix_section_formatting(draft):
    """Fix common formatting issues with section headers"""
    
    # Ensure consistent header formatting (## Section Title)
    fixed_draft = re.sub(r'^# ([^#\n]+)', r'# \1', draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'^##([^#\n]+)', r'## \1', fixed_draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'^###([^#\n]+)', r'### \1', fixed_draft, flags=re.MULTILINE)
    
    # Ensure blank lines before headers for proper markdown rendering
    fixed_draft = re.sub(r'([^\n])\n(#+ )', r'\1\n\n\2', fixed_draft)
    
    # Fix bullet points if needed
    fixed_draft = re.sub(r'^(\s*)-([^\s])', r'\1- \2', fixed_draft, flags=re.MULTILINE)
    
    # Ensure consistent spacing after headers
    fixed_draft = re.sub(r'^(#+ [^\n]+)\n([^#\n])', r'\1\n\n\2', fixed_draft, flags=re.MULTILINE)
    
    return fixed_draft