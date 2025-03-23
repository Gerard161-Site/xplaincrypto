import logging
import os
import datetime
import json
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from backend.state import ResearchState

def escape_xml(text):
    """Escape XML characters that might cause problems with ReportLab"""
    if not text:
        return ""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')  # Corrected to use single quotes consistently
    return text

def convert_markdown_to_reportlab(text):
    """Convert basic Markdown formatting to ReportLab's XML-like syntax"""
    if not text:
        return ""
    
    # Make a copy of the text for safe processing
    processed_text = text
    
    # Step 1: Extract portions that should be bold (before any escaping)
    bold_parts = []
    bold_pattern = r'\*\*([^*]+)\*\*'
    for match in re.finditer(bold_pattern, processed_text):
        bold_parts.append(match.group(1))
    
    # Step 2: Extract portions that should be italic
    italic_parts = []
    italic_pattern = r'\*([^*]+)\*'
    for match in re.finditer(italic_pattern, processed_text):
        italic_parts.append(match.group(1))
    
    # Step 3: Escape XML characters in the entire text
    processed_text = processed_text.replace('&', '&amp;')
    processed_text = processed_text.replace('<', '&lt;')
    processed_text = processed_text.replace('>', '&gt;')
    processed_text = processed_text.replace('"', '&quot;')
    processed_text = processed_text.replace("'", '&#39;')
    
    # Step 4: Replace Markdown patterns with ReportLab XML tags
    # Replace bold (**text**) with <b>text</b>
    processed_text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', processed_text)
    
    # Replace italic (*text*) with <i>text</i>
    processed_text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', processed_text)
    
    # Step 5: Fix the XML tags that might have been escaped
    for bold_text in bold_parts:
        escaped_bold = bold_text
        escaped_bold = escaped_bold.replace('&', '&amp;')
        escaped_bold = escaped_bold.replace('<', '&lt;')
        escaped_bold = escaped_bold.replace('>', '&gt;')
        escaped_bold = escaped_bold.replace('"', '&quot;')
        escaped_bold = escaped_bold.replace("'", '&#39;')
        
        # Replace the escaped tags with proper XML tags
        processed_text = processed_text.replace(f"&lt;b&gt;{escaped_bold}&lt;/b&gt;", f"<b>{escaped_bold}</b>")
    
    for italic_text in italic_parts:
        escaped_italic = italic_text
        escaped_italic = escaped_italic.replace('&', '&amp;')
        escaped_italic = escaped_italic.replace('<', '&lt;')
        escaped_italic = escaped_italic.replace('>', '&gt;')
        escaped_italic = escaped_italic.replace('"', '&quot;')
        escaped_italic = escaped_italic.replace("'", '&#39;')
        
        # Replace the escaped tags with proper XML tags
        processed_text = processed_text.replace(f"&lt;i&gt;{escaped_italic}&lt;/i&gt;", f"<i>{escaped_italic}</i>")
    
    return processed_text

def publisher(state: ResearchState, logger: logging.Logger, config=None, llm=None) -> ResearchState:
    logger.info(f"Publishing report for {state.project_name}")
    state.update_progress(f"Publishing report for {state.project_name}...")

    # Create output directory
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)
    
    project_name = state.project_name if hasattr(state, 'project_name') else "Untitled"
    project_dir = os.path.join(docs_dir, project_name.lower().replace(" ", "_"))
    os.makedirs(project_dir, exist_ok=True)
    logger.info(f"Created project directory: {project_dir}")
    
    # Save draft content for debugging
    if hasattr(state, 'draft') and state.draft:
        draft_file = os.path.join(project_dir, "draft_content.txt")
        with open(draft_file, 'w', encoding='utf-8') as f:
            f.write(state.draft)
        logger.info(f"Draft content saved to {draft_file} ({len(state.draft)} characters)")
    else:
        logger.warning("No draft content found in state")

    # Config options
    fast_mode = config.get("fast_mode", False) if config else False
    use_report_config = config.get("use_report_config", True) if config else True
    
    # Load report configuration
    report_config = {}
    if use_report_config and hasattr(state, 'report_config') and state.report_config:
        report_config = state.report_config
        logger.info("Using report configuration from state")
    else:
        try:
            with open("backend/config/report_config.json", "r") as f:
                report_config = json.load(f)
            logger.info("Loaded report configuration from file")
        except Exception as e:
            logger.warning(f"No report configuration found, using defaults: {str(e)}")
    
    # Set defaults if fields are missing
    if not hasattr(state, 'research_summary') or not state.research_summary:
        state.research_summary = f"Analysis of {state.project_name} cryptocurrency."
        logger.warning("Missing research_summary, using default")
    
    if not hasattr(state, 'visualizations') or not state.visualizations:
        state.visualizations = {}
        logger.warning("No visualizations in state, checking project directory")
        for file in os.listdir(project_dir):
            if file.endswith('.png'):
                state.visualizations[file] = {"file_path": os.path.join(project_dir, file), "description": file.replace('_', ' ').title()}
                logger.info(f"Added visualization from project dir: {file}")
    
    if not hasattr(state, 'references') or not state.references:
        state.references = [
            {"title": f"{project_name} Official Website", "url": f"https://{project_name.lower()}.io"},
            {"title": "CoinGecko", "url": "https://www.coingecko.com"},
            {"title": "CoinMarketCap", "url": "https://coinmarketcap.com"}
        ]
        logger.warning("Created default references")
    
    # Get report content
    content = ""
    if hasattr(state, 'draft') and state.draft:
        content = state.draft
        logger.info(f"Using draft for report content: {len(state.draft)} characters")
    elif hasattr(state, 'research_summary') and state.research_summary:
        content = f"{state.project_name} Research Report\n\n{state.research_summary}"
        logger.warning("No draft, using research summary")
    else:
        content = f"{state.project_name} Research Report\n\nNo content available."
        logger.error("No content available for report")
    
    try:
        # Prepare PDF
        pdf_path = os.path.join(docs_dir, f"{project_name}_report.pdf")
        doc = SimpleDocTemplate(
            pdf_path, 
            pagesize=letter,
            leftMargin=1*inch,
            rightMargin=1*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        
        # Define styles
        stylesheet = getSampleStyleSheet()
        styles = {
            # Title style for main report title
            'Title': ParagraphStyle(
                name='Title', 
                fontName='Times-Bold', 
                fontSize=16, 
                alignment=TA_CENTER, 
                spaceAfter=24
            ),
            
            # Section heading style for main sections
            'SectionHeading': ParagraphStyle(
                name='SectionHeading', 
                fontName='Times-Bold', 
                fontSize=12, 
                alignment=TA_LEFT, 
                spaceBefore=24, 
                spaceAfter=12
            ),
            
            # Subsection heading style
            'SubsectionHeading': ParagraphStyle(
                name='SubsectionHeading', 
                fontName='Times-Bold', 
                fontSize=10, 
                alignment=TA_LEFT, 
                spaceBefore=12, 
                spaceAfter=6
            ),
            
            # Body text style
            'BodyText': ParagraphStyle(
                name='BodyText', 
                fontName='Times-Roman', 
                fontSize=10, 
                alignment=TA_JUSTIFY, 
                spaceBefore=6, 
                spaceAfter=8,    # Increased spacing after paragraphs
                leading=16,      # Increased line spacing
                firstLineIndent=0 # Remove first line indent
            ),
            
            # Centered text style
            'CenteredText': ParagraphStyle(
                name='CenteredText', 
                fontName='Times-Roman', 
                fontSize=10, 
                alignment=TA_CENTER, 
                spaceBefore=6, 
                spaceAfter=6, 
                leading=12
            ),
            
            # Caption style for images
            'Caption': ParagraphStyle(
                name='Caption', 
                fontName='Times-Italic', 
                fontSize=9, 
                alignment=TA_CENTER, 
                spaceAfter=12
            ),
            
            # Disclaimer style for title page
            'Disclaimer': ParagraphStyle(
                name='Disclaimer', 
                fontName='Times-Italic', 
                fontSize=8, 
                alignment=TA_CENTER
            ),
            
            # Reference style for references section
            'Reference': ParagraphStyle(
                name='Reference', 
                fontName='Times-Roman', 
                fontSize=9, 
                alignment=TA_LEFT, 
                spaceBefore=2, 
                spaceAfter=2, 
                leading=11
            ),
            
            # TOC entry style
            'TOCEntry': ParagraphStyle(
                name='TOCEntry',
                fontName='Times-Roman',
                fontSize=10,
                alignment=TA_LEFT,
                leftIndent=20,
                firstLineIndent=-12,  # Negative indent for bullet
                spaceBefore=2,
                spaceAfter=2,
                leading=12
            ),
            
            'Normal': stylesheet['Normal'],
        }
        
        # Build document
        story = []
        
        # Title page
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(f"Comprehensive Analysis of", styles['CenteredText']))
        story.append(Spacer(1, 0.25*inch))
        story.append(Paragraph(f"{project_name} ({project_name.upper()}) Token", styles['Title']))
        story.append(Spacer(1, 0.5*inch))
        current_date = datetime.datetime.now().strftime('%B %d, %Y')
        story.append(Paragraph(f"Generated on {current_date}", styles['CenteredText']))
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("This report provides a detailed analysis of the token's performance, technology, and market position.", styles['CenteredText']))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("This report is AI-generated and should not be considered financial advice.", styles['Disclaimer']))
        story.append(Paragraph("Always conduct your own research before making investment decisions.", styles['Disclaimer']))
        story.append(PageBreak())
        
        # Table of Contents
        story.append(Paragraph("Table of Contents", styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        # Create TOC from report config sections
        if report_config and 'sections' in report_config:
            for i, section_config in enumerate(report_config.get('sections', [])):
                section_title = section_config.get('title', '')
                if not section_title:
                    continue
                section_bullet = f"• {section_title}"
                story.append(Paragraph(section_bullet, styles['TOCEntry']))
        
        story.append(PageBreak())
        
        # Parse sections from content (try both # and ###)
        sections = {}
        header_pattern = r'^(#+)\s+(.+)$'
        current_section = None
        current_text = []
        for line in content.split('\n'):
            match = re.match(header_pattern, line.strip())
            if match:
                level, title = match.groups()
                if current_section and current_text:
                    sections[current_section] = '\n'.join(current_text).strip()
                current_section = title.strip()
                current_text = []
                logger.debug(f"Found header: {current_section} (level: {len(level)})")
            elif current_section is not None:
                current_text.append(line)
        if current_section and current_text:
            sections[current_section] = '\n'.join(current_text).strip()
        
        if not sections:
            sections[project_name + " Report"] = content
            logger.warning("No sections detected, using full content as fallback")
        logger.info(f"Extracted {len(sections)} sections from content: {list(sections.keys())}")
        
        # Log visualizations
        visualizations = state.visualizations if hasattr(state, 'visualizations') else {}
        logger.info(f"Found {len(visualizations)} visualizations: {list(visualizations.keys())}")
        
        # Build report with config
        if report_config and 'sections' in report_config:
            logger.info(f"Building report with {len(report_config['sections'])} configured sections")
            for section_config in report_config.get('sections', []):
                section_title = section_config.get('title', '')
                if not section_title:
                    continue
                
                logger.debug(f"Processing section: {section_title}")
                story.append(Paragraph(section_title, styles['SectionHeading']))
                
                # Find matching content
                section_content = None
                for title, text in sections.items():
                    if title.lower() == section_title.lower() or section_title.lower() in title.lower():
                        section_content = text
                        logger.debug(f"Matched content for {section_title}: {section_content[:100]}...")
                        break
                
                if not section_content and sections:
                    section_content = next(iter(sections.values()), "No specific content available for this section.")
                    logger.warning(f"No exact match for {section_title}, using first available content: {section_content[:100]}...")
                
                # Add text
                if section_content:
                    paragraphs = section_content.split('\n\n') if '\n\n' in section_content else section_content.split('\n')
                    for para in paragraphs:
                        para = para.strip()
                        if not para:
                            continue
                        
                        # Add extra spacing between sentences for readability
                        para = para.replace('. ', '.  ')  # Double space after periods
                        para = para.replace('- ', '• ')
                        para = convert_markdown_to_reportlab(para)
                        
                        logger.debug(f"Adding paragraph: {para[:50]}...")
                        story.append(Paragraph(para, styles['BodyText']))
                        story.append(Spacer(1, 12))  # Increased spacing between paragraphs
                else:
                    story.append(Paragraph("No content available.", styles['BodyText']))
                    logger.warning(f"No content for {section_title}")
                
                # Add visualizations
                if 'visualizations' in section_config:
                    vis_list = section_config.get('visualizations', [])
                    logger.debug(f"Adding {len(vis_list)} visualizations to {section_title}: {vis_list}")
                    for vis_name in vis_list:
                        if vis_name in visualizations:
                            vis = visualizations[vis_name]
                            img_path = vis.get("file_path", "")
                            if os.path.exists(img_path) and os.access(img_path, os.R_OK):
                                logger.debug(f"Adding image: {img_path}")
                                story.append(Spacer(1, 0.3*inch))
                                img = Image(img_path, width=6*inch, height=3*inch, kind='proportional')
                                story.append(img)
                                vis_title = vis.get("description", vis_name.replace('_', ' ').title())
                                story.append(Paragraph(convert_markdown_to_reportlab(vis_title), styles['Caption']))
                                story.append(Spacer(1, 0.2*inch))
                            else:
                                logger.error(f"Image file not found or inaccessible: {img_path}")
                                story.append(Paragraph(f"[Image missing: {vis_name}]", styles['Caption']))
                        else:
                            logger.warning(f"Visualization {vis_name} not in state.visualizations")
                
                story.append(PageBreak())
        else:
            logger.info("No report config, adding all sections")
            for section_title, section_content in sections.items():
                logger.debug(f"Processing section: {section_title}")
                story.append(Paragraph(section_title, styles['SectionHeading']))
                paragraphs = section_content.split('\n\n') if '\n\n' in section_content else section_content.split('\n')
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    
                    # Add extra spacing between sentences for readability
                    para = para.replace('. ', '.  ')  # Double space after periods
                    para = para.replace('- ', '• ')
                    para = convert_markdown_to_reportlab(para)
                    
                    logger.debug(f"Adding paragraph: {para[:50]}...")
                    story.append(Paragraph(para, styles['BodyText']))
                    story.append(Spacer(1, 12))  # Increased spacing between paragraphs
                
                for vis_name, vis in visualizations.items():
                    img_path = vis.get("file_path", "")
                    if os.path.exists(img_path) and os.access(img_path, os.R_OK):
                        logger.debug(f"Adding image: {img_path}")
                        story.append(Spacer(1, 0.3*inch))
                        img = Image(img_path, width=6*inch, height=3*inch, kind='proportional')
                        story.append(img)
                        vis_title = vis.get("description", vis_name.replace('_', ' ').title())
                        story.append(Paragraph(convert_markdown_to_reportlab(vis_title), styles['Caption']))
                        story.append(Spacer(1, 0.2*inch))
                
                story.append(PageBreak())
        
        # References
        logger.debug("Adding references")
        story.append(Paragraph("References", styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        # Process references with proper formatting
        for ref in state.references:
            title = ref.get('title', 'Untitled')
            url = ref.get('url', 'No URL')
            
            # Format each reference as a bullet point with title and URL on separate lines
            ref_text = f"• {title}<br/>{url}"
            logger.debug(f"Adding reference: {ref_text}")
            story.append(Paragraph(ref_text, styles['Reference']))
            story.append(Spacer(1, 0.05*inch))
        
        # Define page numbering function
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Times-Roman', 9)
            # Simple page number format
            page_num = f"Page {doc.page}"
            # Position at bottom of page, centered
            canvas.drawCentredString(letter[0]/2, 36, page_num)
            canvas.restoreState()
        
        # Build PDF with page numbering
        logger.info("Building PDF document")
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        state.final_report = f"PDF report generated: {pdf_path}"
        logger.info(f"Successfully created PDF report at {pdf_path}")
        
    except Exception as e:
        logger.error(f"Error building PDF: {str(e)}", exc_info=True)
        state.final_report = f"Error creating PDF: {str(e)}"
        txt_path = pdf_path.replace('.pdf', '.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"{project_name} Research Report\n\n{content}")
        logger.info(f"Created text fallback at {txt_path}")
    
    return state