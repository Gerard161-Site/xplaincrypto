from langchain_openai import ChatOpenAI
import logging
import re
from backend.state import ResearchState

def editor(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> ResearchState:
    logger.info(f"Performing comprehensive editing for {state.project_name}")
    state.update_progress(f"Editing draft for {state.project_name}...")

    # Check for any issues with section formatting
    fixed_draft = fix_section_formatting(state.draft)
    
    # Add instructions about preserving exact metrics
    metrics_note = """
IMPORTANT INSTRUCTIONS:
1. Maintain all exact numerical values (prices, market cap, trading volume, etc.) throughout the document
2. DO NOT replace specific figures with placeholders like '$X' or 'Y tokens'
3. DO NOT attempt to add or reference tables or images directly in the text
4. Focus only on improving the quality of the existing text content
"""
    
    # Perform editing in stages for better results
    
    # Stage 1: Fix structural issues and ensure consistent formatting
    structure_prompt = f"""Improve the structure and formatting of this crypto research report on {state.project_name}.
    
{metrics_note}
    
Focus on:
1. Ensuring all section headings are properly formatted and consistent
2. Organizing content logically within each section
3. Adding subheadings where appropriate for clarity
4. Making sure the report flows naturally from one section to the next
5. Ensuring all markdown formatting is correct

Only fix structural/formatting issues and section organization. DO NOT change the factual content.
    
{fixed_draft}
    """
    
    logger.debug("Improving report structure and formatting")
    structured_draft = llm.invoke(structure_prompt).content
    
    # Stage 2: Improve content quality, clarity and professional tone
    content_prompt = f"""Polish this {state.project_name} research report for professional quality and clarity.
    
{metrics_note}
    
Focus on:
1. Ensuring professional language and tone throughout
2. Improving clarity and readability with precise wording
3. Eliminating redundancy and wordiness
4. Ensuring consistent tense and point of view
5. Enhancing readability with better transitions between ideas
6. Maintaining appropriate formality for a financial research document
7. Ensuring any claims are properly qualified

Maintain all existing sections, facts and information - only improve the writing quality.
    
{structured_draft}
    """
    
    logger.debug("Improving report content quality and clarity")
    polished_draft = llm.invoke(content_prompt).content
    
    # Stage 3: Perform fact-checking and ensure consistency
    fact_check_prompt = f"""Review this {state.project_name} research report for factual consistency and accuracy.
    
{metrics_note}
    
Focus on:
1. Ensuring any numerical data or statistics are presented consistently throughout the document
2. Resolving any contradictions or inconsistencies in the information presented
3. Verifying that tokenomics figures are consistent where mentioned multiple times
4. Ensuring claims are proportional and not overstated
5. Removing any speculative statements that aren't clearly labeled as such

Make only the necessary changes to ensure factual consistency - preserve the overall content and structure.
    
{polished_draft}
    """
    
    logger.debug("Performing fact-checking and consistency review")
    fact_checked_draft = llm.invoke(fact_check_prompt).content
    
    # Stage 4: Final polish and executive quality check
    final_prompt = f"""Perform a final review and polish of this {state.project_name} cryptocurrency research report to ensure investment-grade quality.
    
{metrics_note}
    
Focus on:
1. Ensuring an objective, balanced perspective throughout
2. Verifying all investment-relevant information is clearly presented
3. Making sure risk factors are appropriately highlighted
4. Checking that conclusions follow logically from the presented evidence
5. Ensuring the executive summary accurately reflects the full report content
6. Polishing language for maximum clarity and impact

The report should meet the quality standards expected by professional crypto investors and analysts.
    
{fact_checked_draft}
    """
    
    logger.debug("Performing final quality review")
    edited_draft = llm.invoke(final_prompt).content
    
    # Store the final edited version
    state.final_report = edited_draft

    # Calculate improvement metrics
    original_words = len(state.draft.split())
    edited_words = len(edited_draft.split())
    word_diff = edited_words - original_words
    
    logger.info(f"Editing completed: {original_words} words → {edited_words} words ({word_diff:+d} words)")
    state.update_progress("Comprehensive editing completed.")
    return state

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