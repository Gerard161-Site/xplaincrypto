import logging
import os
import datetime
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from backend.state import ResearchState

def publisher(state: ResearchState, logger: logging.Logger, config=None, llm=None) -> ResearchState:
    logger.info(f"Publishing report for {state.project_name}")
    state.update_progress(f"Publishing report for {state.project_name}...")

    # Create output directory if it doesn't exist
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)
    
    # Create project-specific directory for visualizations if needed
    project_dir = os.path.join(docs_dir, state.project_name.lower().replace(" ", "_"))
    os.makedirs(project_dir, exist_ok=True)
    logger.info(f"Created project directory: {project_dir}")
    
    # Safely get report configuration if available
    report_config = state.report_config if hasattr(state, 'report_config') else {}
    
    # Define section mappings
    section_mappings = {
        "Executive Summary": "executive_summary",
        "Introduction": "introduction",
        "Market Analysis": "market_analysis",
        "Technical Analysis": "technical_analysis",
        "Tokenomics": "tokenomics",
        "Governance and Community": "governance_and_community",
        "Ecosystem and Partnerships": "ecosystem_and_partnerships",
        "Risks and Opportunities": "risks_and_opportunities",
        "Team and Development": "team_and_development",
        "Conclusion": "conclusion",
        "References": "references"
    }
    
    # Ensure all mapped sections have at least default content
    for section_name, attr_name in section_mappings.items():
        if not hasattr(state, attr_name) or not getattr(state, attr_name):
            default_content = f"Content for {section_name} not available."
            setattr(state, attr_name, default_content)
            logger.warning(f"Missing {attr_name}, using default: {default_content}")
    
    # Prepare PDF document
    pdf_path = os.path.join(docs_dir, f"{state.project_name}_report.pdf")
    
    # Define page footer with page numbers and generation date
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(1*inch, 0.5*inch, f"Page {doc.page}")
        canvas.drawRightString(7.5*inch, 0.5*inch, f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d')}")
        canvas.restoreState()
    
    doc = SimpleDocTemplate(
        pdf_path, 
        pagesize=letter,
        leftMargin=1*inch,
        rightMargin=1*inch,
        topMargin=1*inch,
        bottomMargin=1*inch,
        onPage=on_page
    )
    
    # Define styles
    styles = {
        'Title': ParagraphStyle(
            name='Title',
            fontName='Helvetica-Bold',
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=24
        ),
        'SectionHeading': ParagraphStyle(
            name='SectionHeading',
            fontName='Helvetica-Bold',
            fontSize=14,
            alignment=TA_LEFT,
            spaceBefore=24,
            spaceAfter=12
        ),
        'Subheading': ParagraphStyle(
            name='Subheading',
            fontName='Helvetica-Bold',
            fontSize=12,
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=6
        ),
        'BodyText': ParagraphStyle(
            name='BodyText',
            fontName='Helvetica',
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceBefore=6,
            spaceAfter=6,
            leading=14
        ),
        'Caption': ParagraphStyle(
            name='Caption',
            fontName='Helvetica-Oblique',
            fontSize=9,
            alignment=TA_CENTER,
            spaceAfter=12
        ),
        'References': ParagraphStyle(
            name='References',
            fontName='Helvetica',
            fontSize=9,
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=4
        ),
        'TOCItem': ParagraphStyle(
            name='TOCItem',
            fontName='Helvetica',
            fontSize=10,
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=4
        )
    }
    
    # Start building the document
    story = []
    
    # Title page
    story.append(Paragraph(f"Comprehensive Analysis of {state.project_name}", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on {datetime.datetime.now().strftime('%B %d, %Y')}", styles['BodyText']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("This research report is generated with AI assistance and should not be considered as financial advice. Always conduct your own research before making investment decisions.", styles['BodyText']))
    story.append(PageBreak())
    
    # Table of contents
    story.append(Paragraph("Table of Contents", styles['SectionHeading']))
    story.append(Spacer(1, 12))
    for i, section in enumerate(report_config.get('sections', []), 1):
        story.append(Paragraph(f"{i}. {section['title']}", styles['TOCItem']))
    story.append(PageBreak())
    
    # Add sections
    for section in report_config.get('sections', []):
        title = section['title']
        attr_name = section_mappings.get(title, title.lower().replace(' ', '_'))
        content = getattr(state, attr_name, "Content not available")
        
        # Add section heading
        story.append(Paragraph(title, styles['SectionHeading']))
        
        # Add content
        for paragraph in content.split('\n\n'):
            story.append(Paragraph(paragraph, styles['BodyText']))
            story.append(Spacer(1, 6))
        
        # Add visualizations
        for vis_type in section.get('visualization_types', []):
            vis_path = state.visualizations.get(vis_type, {}).get('file_path')
            if vis_path and os.path.exists(vis_path):
                story.append(Image(vis_path, width=6*inch, height=3*inch))
                story.append(Paragraph(state.visualizations[vis_type].get('title', vis_type.replace('_', ' ').title()), styles['Caption']))
                story.append(Spacer(1, 12))
            else:
                logger.warning(f"Visualization {vis_type} not found for section {title}")
        
        story.append(Spacer(1, 24))  # Space between sections
    
    # References section
    story.append(Paragraph("References", styles['SectionHeading']))
    if isinstance(state.references, list):
        for ref in state.references:
            story.append(Paragraph(ref, styles['References']))
    else:
        story.append(Paragraph("No references available.", styles['BodyText']))
    
    # Build the document
    doc.build(story)
    state.final_report = pdf_path
    return state