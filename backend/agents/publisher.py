import logging
import os
import datetime
import json
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from backend.state import ResearchState
from backend.utils.style_utils import StyleManager

# Suppress matplotlib font manager debug logs
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

# Suppress socketio logs
logging.getLogger('socketio').setLevel(logging.WARNING)

def escape_xml(text):
    """Escape XML characters that might cause problems with ReportLab"""
    if not text:
        return ""
    text = text.replace('&', '&amp;')  # Fixed: proper XML entities
    text = text.replace('<', '&lt;')   # Fixed: proper XML entities
    text = text.replace('>', '&gt;')   # Fixed: proper XML entities
    text = text.replace('"', '&quot;') # Fixed: proper XML entities
    text = text.replace("'", '&#39;')  # Fixed: proper XML entities
    return text

def publisher(state: ResearchState, logger: logging.Logger, config=None, llm=None) -> ResearchState:
    logger.info(f"Publishing report for {state.project_name}")
    
    # Get project details
    project_name = state.project_name
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)

    # Initialize pdf_path
    pdf_path = os.path.join(docs_dir, f"{project_name}_report.pdf")

    # Create project directory for debugging
    project_dir = os.path.join(docs_dir, project_name.lower().replace(" ", "_"))
    os.makedirs(project_dir, exist_ok=True)
    logger.info(f"Created project directory: {project_dir}")
    
    # Save draft content for debugging
    if hasattr(state, 'draft') and state.draft:
        draft_file = os.path.join(project_dir, "draft_content.txt")
        with open(draft_file, 'w', encoding='utf-8') as f:
            f.write(state.draft)
        logger.info(f"Draft content saved to {draft_file} ({len(state.draft)} characters)")
        logger.debug(f"Draft content preview:\n{state.draft[:500]}...")
    else:
        logger.warning("No draft content found in state")
    
    # Load report configuration
    report_config = None
    if config:
        report_config = config
    else:
        try:
            with open(os.path.join("backend", "config", "report_config.json"), "r") as f:
                report_config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading report config: {str(e)}")
    
    # Debug logging for state content
    logger.info("=== State Content Debug ===")
    logger.info(f"Has draft: {hasattr(state, 'draft')}")
    if hasattr(state, 'draft'):
        logger.info(f"Draft length: {len(state.draft)} characters")
        logger.debug(f"Draft preview (first 200 chars):\n{state.draft[:200]}...")
    
    logger.info(f"Has research_summary: {hasattr(state, 'research_summary')}")
    if hasattr(state, 'research_summary'):
        logger.info(f"Research summary length: {len(state.research_summary)} characters")
        logger.debug(f"Research summary preview (first 200 chars):\n{state.research_summary[:200]}...")
    
    # Get content from state
    content = ""
    if hasattr(state, 'draft') and state.draft:
        content = state.draft
        logger.info(f"Using draft for report content: {len(state.draft)} characters")
        logger.debug(f"Content preview:\n{content[:500]}...")
    elif hasattr(state, 'research_summary') and state.research_summary:
        content = f"{state.project_name} Research Report\n\n{state.research_summary}"
        logger.warning("No draft, using research summary")
    else:
        content = f"{state.project_name} Research Report\n\nNo content available."
        logger.error("No content available for report")
    
    # Parse sections from content (try both # and ###)
    sections = {}
    header_pattern = r'^(#+)\s+(.+)$'  # Matches any number of # symbols
    current_section = None
    current_text = []
    
    for line in content.split('\n'):
        header_match = re.match(header_pattern, line.strip())
        if header_match:
            level, title = header_match.groups()
            if current_section and current_text:
                sections[current_section] = '\n'.join(current_text).strip()
            current_section = title.strip()
            current_text = []
            logger.debug(f"Found header: {current_section} (level: {len(level)})")
        elif current_section is not None:
            current_text.append(line)
    
    if current_section and current_text:
        sections[current_section] = '\n'.join(current_text).strip()
    
    # Debug logging for sections
    logger.info("=== Sections Debug ===")
    logger.info(f"Number of sections found: {len(sections)}")
    logger.info(f"Section titles: {list(sections.keys())}")
    for title, text in sections.items():
        logger.debug(f"Section '{title}' content preview:\n{text[:200]}...")
    
    # Fallback if no sections found
    if not sections:
        sections[project_name + " Report"] = content
        logger.warning("No sections detected, using full content as fallback")
    
    # Build PDF document - REDUCED MARGINS
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=55,  # Further reduced from 60
        leftMargin=55,   # Further reduced from 60
        topMargin=45,    # Further reduced from 48
        bottomMargin=45  # Further reduced from 48
    )
    
    # Use StyleManager for styles
    style_manager = StyleManager(logger)
    styles = style_manager.get_reportlab_styles()
    logger.info(f"Loaded styles: {list(styles.keys())}")
    
    # Initialize story list for PDF content
    story = []
    
    # Title page with updated format to match user request
    story.append(Spacer(1, 1.5*inch))  # Space at top
    story.append(Paragraph("Comprehensive Analysis of", styles['SubTitle']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"{project_name} ({project_name.upper()}) Token", styles['Title']))
    story.append(Spacer(1, 1.0*inch))
    
    # Adding date
    current_date = datetime.datetime.now().strftime('%B %d, %Y')
    story.append(Paragraph(f"Generated on {current_date}", styles['CenteredText']))
    story.append(Spacer(1, 2.5*inch))
    
    # Add disclaimer with better spacing
    disclaimer_text = "This report is for informational purposes only and does not constitute financial advice."
    story.append(Paragraph(disclaimer_text, styles['Disclaimer']))
    story.append(Spacer(1, 0.1*inch))
    data_sources_text = "Data sources for this report include CoinGecko, CoinMarketCap, and DeFiLlama."
    story.append(Paragraph(data_sources_text, styles['Disclaimer']))
    story.append(PageBreak())
    
    # Build report with config
    if report_config and 'sections' in report_config:
        logger.info(f"Building report with {len(report_config['sections'])} configured sections")
        for section_config in report_config.get('sections', []):
            section_title = section_config.get('title', '')
            if not section_title:
                continue
            
            logger.debug(f"Processing section: {section_title}")
            story.append(Paragraph(section_title, styles['SectionHeading']))
            
            # Find matching content with improved matching
            section_content = None
            for title, text in sections.items():
                # Try exact match first
                if title == section_title:
                    section_content = text
                    logger.debug(f"Found exact match for {section_title}")
                    break
                # Try case-insensitive match
                elif title.lower() == section_title.lower():
                    section_content = text
                    logger.debug(f"Found case-insensitive match for {section_title}")
                    break
                # Try partial match
                elif section_title.lower() in title.lower():
                    section_content = text
                    logger.debug(f"Found partial match for {section_title}")
                    break
                # Try removing common prefixes/suffixes
                elif section_title.lower().replace("section", "").strip() in title.lower().replace("section", "").strip():
                    section_content = text
                    logger.debug(f"Found match after removing common words for {section_title}")
                    break
            
            if not section_content and sections:
                # If no match found, use the first available content
                section_content = next(iter(sections.values()), "No specific content available for this section.")
                logger.warning(f"No match found for {section_title}, using first available content")
            
            # Add text with improved formatting
            if section_content:
                # Filter out lines that mention charts or tables
                filtered_paragraphs = []
                
                # First, split the content by paragraphs
                paragraphs = section_content.split('\n\n') if '\n\n' in section_content else section_content.split('\n')
                
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    
                    # Skip lines with chart/table references or markdown image syntax
                    if any(keyword in para.lower() for keyword in ['chart:', 'table:', '![', '**price history chart**', '**volume chart**', '**tvl chart**', '**competitor comparison chart**', '**key metrics table**']):
                        logger.debug(f"Skipping visualization reference line: {para[:50]}...")
                        continue
                    
                    # Skip data sources markers
                    if "Data Sources:" in para or "---" in para:
                        continue
                    
                    filtered_paragraphs.append(para)
                
                # Process filtered paragraphs
                for para in filtered_paragraphs:
                    # Add extra spacing between sentences for readability
                    para = para.replace('. ', '.  ')  # Double space after periods
                    para = para.replace('- ', '• ')
                    
                    # Fix heading formatting to use proper bold
                    para = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', para)
                    
                    para = escape_xml(para)
                    
                    logger.debug(f"Adding paragraph (first 50 chars): {para[:50]}...")
                    story.append(Paragraph(para, styles['BodyText']))
                    story.append(Spacer(1, 2))  # Further reduced from 3
            else:
                story.append(Paragraph("No content available.", styles['BodyText']))
                logger.warning(f"No content for {section_title}")
            
            # Add visualizations WITHOUT titles (titles are in the images)
            if 'visualizations' in section_config:
                vis_list = section_config.get('visualizations', [])
                available_vis = [vis for vis in vis_list if vis in state.visualizations]
                
                if not available_vis:
                    logger.warning(f"No visualizations available for section {section_title}")
                else:
                    logger.debug(f"Adding {len(available_vis)} of {len(vis_list)} visualizations to {section_title}")
                
                for vis_name in vis_list:
                    if vis_name in state.visualizations:
                        vis = state.visualizations[vis_name]
                        img_path = vis.get("file_path", "")
                        
                        if os.path.exists(img_path) and os.access(img_path, os.R_OK):
                            logger.debug(f"Adding image: {img_path}")
                            story.append(Spacer(1, 0.04*inch))  # Further reduced from 0.05 inch
                            
                            # Set different heights based on image type
                            if 'table' in vis_name.lower():
                                # Tables - use original size
                                img = Image(img_path, width=6.5*inch, height=3.5*inch, kind='proportional')
                            else:
                                # Standard charts
                                img = Image(img_path, width=6.5*inch, height=3.0*inch, kind='proportional')
                                
                            story.append(img)
                            # No need to add title caption - they're in the image
                            story.append(Spacer(1, 0.04*inch))  # Further reduced from 0.05 inch
                        else:
                            logger.error(f"Image file not found or inaccessible: {img_path}")
                            # Don't add missing image placeholder to avoid clutter
                    else:
                        logger.warning(f"Visualization {vis_name} not in state.visualizations")
            
            story.append(PageBreak())
    
    # References section
    logger.debug("Adding references")
    story.append(Paragraph("References", styles['SectionHeading']))
    
    # Process references with proper formatting
    if hasattr(state, 'references') and state.references:
        for ref in state.references:
            title = ref.get('title', 'Untitled')
            url = ref.get('url', 'No URL')
            
            # Format each reference as a bullet point with title and URL on separate lines
            ref_text = f"• {title}<br/>{url}"
            logger.debug(f"Adding reference: {ref_text}")
            story.append(Paragraph(escape_xml(ref_text), styles['Reference']))
            story.append(Spacer(1, 0.02*inch))  # Further reduced from 0.03 inch
    else:
        # Add default references if none found
        default_refs = [
            {"title": f"{project_name} Official Website", "url": f"https://{project_name.lower()}.com"},
            {"title": "CoinGecko", "url": "https://www.coingecko.com"},
            {"title": "CoinMarketCap", "url": "https://coinmarketcap.com"},
            {"title": "DeFiLlama", "url": "https://defillama.com"}
        ]
        
        for ref in default_refs:
            ref_text = f"• {ref['title']}<br/>{ref['url']}"
            story.append(Paragraph(escape_xml(ref_text), styles['Reference']))
            story.append(Spacer(1, 0.02*inch))
    
    # Define page numbering function
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Times-Roman', 9)
        page_num = f"Page {doc.page}"
        canvas.drawCentredString(letter[0]/2, 25, page_num)  # Further reduced from 30
        canvas.restoreState()
    
    # Build PDF
    logger.info("Building PDF document")
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    state.final_report = f"PDF report generated: {pdf_path}"
    logger.info(f"Successfully created PDF report at {pdf_path}")
    
    return state