import logging
import os
import datetime
import re
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from backend.state import ResearchState
from langchain_openai import ChatOpenAI

def publisher(state: ResearchState, logger: logging.Logger, config=None, llm=None) -> ResearchState:
    logger.info(f"Publishing report for {state.project_name}")
    state.update_progress(f"Publishing report for {state.project_name}...")

    # Get report configuration if available
    report_config = {}
    if hasattr(state, 'report_config') and state.report_config:
        report_config = state.report_config
        logger.info("Using report configuration from state")
    
    # Set up enhanced styles
    styles = getSampleStyleSheet()
    
    # Create custom styles with safe checks
    custom_styles = {
        'ReportTitle': ParagraphStyle(
            name='ReportTitle',
            parent=styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        'ReportSubtitle': ParagraphStyle(
            name='ReportSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        'SectionTitle': ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceBefore=8,
            spaceAfter=4,
        ),
        'SubsectionTitle': ParagraphStyle(
            name='SubsectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=6,
            spaceAfter=4,
        ),
        'TableHeader': ParagraphStyle(
            name='TableHeader',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.white,
            backColor=colors.darkblue,
        ),
        'TableCell': ParagraphStyle(
            name='TableCell',
            parent=styles['BodyText'],
            fontSize=9,
        ),
        'Reference': ParagraphStyle(
            name='Reference',
            parent=styles['BodyText'],
            fontSize=9,
            leftIndent=20,
            firstLineIndent=-20,
        ),
        'TOCEntry': ParagraphStyle(
            name='TOCEntry',
            parent=styles['BodyText'],
            fontSize=12,
            leftIndent=20,
            firstLineIndent=-20,
            spaceBefore=5,
            leading=16,
        ),
        'Normal': ParagraphStyle(
            name='Normal',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            leading=6,
            spaceBefore=4,
            spaceAfter=6,
        ),
        'BulletPoint': ParagraphStyle(
            name='BulletPoint',
            parent=styles['BodyText'],
            fontSize=10,
            leftIndent=20,
            firstLineIndent=-10,
            leading=14,
        ),
        'Caption': ParagraphStyle(
            name='Caption',
            parent=styles['BodyText'],
            fontSize=9,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique',
        ),
        'KeyMetric': ParagraphStyle(
            name='KeyMetric',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        ),
        'MetricValue': ParagraphStyle(
            name='MetricValue',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_RIGHT,
        ),
    }
    
    # Safely add styles
    for name, style in custom_styles.items():
        if name not in styles:
            styles.add(style)
    
    # Modify existing styles
    styles['Heading1'].fontSize = 18
    styles['Heading1'].spaceAfter = 12
    styles['Heading2'].fontSize = 14
    styles['Heading2'].spaceAfter = 10
    styles['BodyText'].fontSize = 11
    styles['BodyText'].leading = 14

    # Create PDF with margins
    doc = SimpleDocTemplate(
        f"docs/{state.project_name}_report.pdf", 
        pagesize=letter,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    story = []

    # Cover Page
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    
    # Get report title from config or use default
    report_title = f"{state.project_name} Research Report"
    report_subtitle = "Cryptocurrency Analysis"
    
    if report_config:
        report_title = report_config.get("report_name", report_title)
        report_subtitle = report_config.get("description", report_subtitle)
    
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph(report_title, styles['ReportTitle']))
    story.append(Paragraph(report_subtitle, styles['ReportSubtitle']))
    story.append(Spacer(1, 0.5*inch))
    
    # Extract ticker from data if available, otherwise use project name
    ticker = state.project_name.upper()
    
    # Extract 60-day change from price_analysis
    price_change = state.price_analysis.split('60-Day Change: ')[1] if '60-Day Change' in state.price_analysis else 'N/A'
    
    # Create a summary table for the cover page
    cover_data = [
        ["Project", state.project_name],
        ["Ticker Symbol", ticker],
        ["Report Date", current_date],
        ["60-Day Price Change", price_change]
    ]
    
    cover_table = Table(cover_data, colWidths=[2*inch, 3*inch])
    cover_table.setStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('PADDING', (0, 0), (-1, -1), 6)
    ])
    
    story.append(cover_table)
    story.append(Spacer(1, 1*inch))
    
    # Add visualizations from state if available
    if hasattr(state, 'visualizations') and state.visualizations:
        # Add price chart visualization if available
        price_vis = state.visualizations.get('price_history_chart', {})
        if 'file_path' in price_vis and os.path.exists(price_vis['file_path']):
            story.append(Paragraph(price_vis.get('title', "60-Day Price Trend"), styles['Caption']))
            img = Image(price_vis['file_path'], width=4*inch, height=2.5*inch)
            img.hAlign = 'CENTER'
            story.append(img)
            if 'description' in price_vis:
                story.append(Paragraph(price_vis['description'], styles['Caption']))
        # Fallback to the old chart if visualization not available
        else:
            # Add key image if available
            chart_path = os.path.join("docs", f"{state.project_name.lower()}_price_chart.png")
            if os.path.exists(chart_path):
                story.append(Paragraph("60-Day Price Trend", styles['Caption']))
                img = Image(chart_path, width=4*inch, height=2.5*inch)
                img.hAlign = 'CENTER'
                story.append(img)
    else:
        # Fallback to the old chart
        chart_path = os.path.join("docs", f"{state.project_name.lower()}_price_chart.png")
        if os.path.exists(chart_path):
            story.append(Paragraph("60-Day Price Trend", styles['Caption']))
            img = Image(chart_path, width=4*inch, height=2.5*inch)
            img.hAlign = 'CENTER'
            story.append(img)
    
    story.append(PageBreak())

    # Create a manual table of contents
    story.append(Paragraph("Table of Contents", styles['SectionTitle']))
    story.append(Spacer(1, 12))
    
    # Define standard sections based on config or default to the comprehensive template
    toc_entries = [
        "Executive Summary",
        "Introduction",
        "Key Features",
        "Tokenomics",
        "Price and Market Analysis",
        "Governance",
        "Risks and Opportunities",
        "Team Assessment",
        "Regulatory and Legal",
        "Partnerships and Ecosystem",
        "Roadmap",
        "SWOT Analysis",
        "Conclusion",
        "References"
    ]
    
    # Replace with sections from config if available
    if report_config and "sections" in report_config:
        config_sections = [section["title"] for section in report_config["sections"] 
                          if section.get("required", True)]
        if config_sections:
            toc_entries = config_sections
    
    # Add TOC entries
    for i, entry in enumerate(toc_entries, 1):
        story.append(Paragraph(f"{i}. {entry}", styles['TOCEntry']))
        story.append(Spacer(1, 6))
    
    story.append(PageBreak())

    # Executive Summary
    story.append(Paragraph("Executive Summary", styles['SectionTitle']))
    
    # Generate comprehensive executive summary
    executive_summary = []
    
    # Extract from research summary
    if state.research_summary:
        # Get first paragraph or two
        summary_parts = state.research_summary.split("\n\n")
        if summary_parts:
            executive_summary.append(summary_parts[0])
            # Add second paragraph if available for more depth
            if len(summary_parts) > 1:
                executive_summary.append(summary_parts[1])
    
    # Add market position context
    if state.price_analysis:
        price_change_value = price_change
        if price_change_value and price_change_value != 'N/A':
            try:
                change_float = float(price_change_value.strip('%'))
                if change_float > 0:
                    market_context = f"{state.project_name} has shown positive growth with a {price_change_value} increase over the past 60 days, indicating strong market confidence and growing investor interest."
                elif change_float < 0:
                    market_context = f"{state.project_name} has experienced a {price_change_value} change over the past 60 days, reflecting current market challenges and potential consolidation."
                else:
                    market_context = f"{state.project_name}'s price has remained stable over the past 60 days, suggesting a mature market position with balanced supply and demand."
            except ValueError:
                market_context = f"{state.project_name} has shown a {price_change_value} change over the past 60 days, reflecting current market conditions."
            executive_summary.append(market_context)
    
    # Add tokenomics highlight if available
    if state.tokenomics:
        tokenomics_lines = state.tokenomics.split("\n")
        if len(tokenomics_lines) >= 2:
            # Extract key tokenomics data points
            tokenomics_highlights = "Key metrics include "
            data_points = []
            for line in tokenomics_lines[:3]:  # Use first 3 metrics
                if ": " in line:
                    key, value = line.split(": ", 1)
                    data_points.append(f"{key} of {value}")
            
            if data_points:
                tokenomics_highlights += ", ".join(data_points) + "."
                executive_summary.append(tokenomics_highlights)
    
    # Add value proposition
    executive_summary.append(f"This report provides an in-depth analysis of {state.project_name}, including key features, tokenomics, governance structure, market position, and risk assessment to help investors and stakeholders make informed decisions. The analysis covers technical fundamentals, real-time market data, and comprehensive evaluation of the project's strengths and challenges in the current crypto landscape.")
    
    # Display the executive summary
    for paragraph in executive_summary:
        if paragraph.strip():
            story.append(Paragraph(paragraph, styles['Normal']))
            story.append(Spacer(1, 12))
    
    # Now iterate through remaining sections based on TOC
    # We skip the first entry (Executive Summary) since we've already covered it
    for i, section_title in enumerate(toc_entries[1:], 2):
        story.append(PageBreak())
        story.append(Paragraph(f"{i}. {section_title}", styles['SectionTitle']))
        
        # Add section content based on section type
        # This is where we would use the report config to determine what content to include
        if "Introduction" in section_title:
            # Add introduction content
            if state.research_summary:
                intro_text = state.research_summary.split("\n\n")[0] if state.research_summary.split("\n\n") else ""
                story.append(Paragraph(intro_text, styles['Normal']))
                story.append(Spacer(1, 0.2*inch))
                
            # Add key metrics table
            if hasattr(state, 'visualizations') and 'basic_metrics_table' in state.visualizations:
                basic_metrics = state.visualizations['basic_metrics_table']
                if 'file_path' in basic_metrics and os.path.exists(basic_metrics['file_path']):
                    story.append(Paragraph(basic_metrics.get('title', "Basic Metrics"), styles['SubsectionTitle']))
                    img = Image(basic_metrics['file_path'], width=5*inch, height=3*inch)
                    img.hAlign = 'CENTER'
                    story.append(img)
            else:
                # Fallback to old tokenomics data
                story.append(Paragraph("Key Project Details", styles['SubsectionTitle']))
                tokenomics_data = []
                if state.tokenomics:
                    tokenomics_lines = state.tokenomics.split("\n")
                    for line in tokenomics_lines:
                        if ": " in line:
                            key, value = line.split(": ", 1)
                            tokenomics_data.append([key, value])
                
                if tokenomics_data:
                    metrics_table = Table(tokenomics_data, colWidths=[2.5*inch, 3*inch])
                    metrics_table.setStyle([
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                        ('PADDING', (0, 0), (-1, -1), 6)
                    ])
                    story.append(metrics_table)
        
        elif "Market Analysis" in section_title or "Price" in section_title:
            # Add price analysis content
            if state.price_analysis:
                price_lines = state.price_analysis.split("\n")
                for line in price_lines:
                    if line.strip():
                        story.append(Paragraph(line, styles['Normal']))
                        story.append(Spacer(1, 4))
            else:
                story.append(Paragraph(f"Analysis of {state.project_name}'s price performance shows the token's market behavior in relation to broader crypto market trends.", styles['Normal']))
            
            story.append(Spacer(1, 0.2*inch))
            
            # Add visualizations
            if hasattr(state, 'visualizations'):
                for vis_type in ['price_history_chart', 'volume_chart', 'tvl_chart']:
                    if vis_type in state.visualizations:
                        vis_data = state.visualizations[vis_type]
                        if 'file_path' in vis_data and os.path.exists(vis_data['file_path']):
                            story.append(Paragraph(vis_data.get('title', vis_type.replace('_', ' ').title()), styles['SubsectionTitle']))
                            story.append(Spacer(1, 6))
                            img = Image(vis_data['file_path'], width=5*inch, height=3*inch)
                            img.hAlign = 'CENTER'
                            story.append(img)
                            if 'description' in vis_data:
                                story.append(Paragraph(vis_data['description'], styles['Caption']))
                            story.append(Spacer(1, 0.2*inch))
            else:
                # Fallback to old chart
                chart_path = os.path.join("docs", f"{state.project_name.lower()}_price_chart.png")
                if os.path.exists(chart_path):
                    story.append(Paragraph("60-Day Price Trend Analysis:", styles['SubsectionTitle']))
                    story.append(Spacer(1, 6))
                    img = Image(chart_path, width=5*inch, height=3*inch)
                    img.hAlign = 'CENTER'
                    story.append(img)
                    story.append(Paragraph("Figure 1: 60-day price movement showing key trends and market reactions", styles['Caption']))
        
        elif "Tokenomics" in section_title:
            # Add tokenomics narrative if available
            if state.research_summary and "tokenomics" in state.research_summary.lower():
                tokenomics_narrative = state.research_summary.split("Describe")[1].split("Analyze")[0].strip() if "Describe" in state.research_summary else ""
                story.append(Paragraph(tokenomics_narrative, styles['Normal']))
            else:
                story.append(Paragraph(f"The {state.project_name} token serves as the native utility and governance token for the ecosystem, providing holders with various benefits and use cases.", styles['Normal']))
            
            story.append(Spacer(1, 0.2*inch))
            
            # Add token distribution visualization if available
            if hasattr(state, 'visualizations') and 'token_distribution_chart' in state.visualizations:
                token_dist = state.visualizations['token_distribution_chart']
                if 'file_path' in token_dist and os.path.exists(token_dist['file_path']):
                    story.append(Paragraph(token_dist.get('title', "Token Distribution"), styles['SubsectionTitle']))
                    img = Image(token_dist['file_path'], width=5*inch, height=4*inch)
                    img.hAlign = 'CENTER'
                    story.append(img)
                    if 'description' in token_dist:
                        story.append(Paragraph(token_dist['description'], styles['Caption']))
                    story.append(Spacer(1, 0.2*inch))
            
            # Add supply table if available
            if hasattr(state, 'visualizations') and 'supply_table' in state.visualizations:
                supply_table = state.visualizations['supply_table']
                if 'file_path' in supply_table and os.path.exists(supply_table['file_path']):
                    story.append(Paragraph(supply_table.get('title', "Supply Details"), styles['SubsectionTitle']))
                    img = Image(supply_table['file_path'], width=5*inch, height=3*inch)
                    img.hAlign = 'CENTER'
                    story.append(img)
                    story.append(Spacer(1, 0.2*inch))
            else:
                # Fallback to basic tokenomics table
                tokenomics_data = []
                if state.tokenomics:
                    tokenomics_lines = state.tokenomics.split("\n")
                    for line in tokenomics_lines:
                        if ": " in line:
                            key, value = line.split(": ", 1)
                            tokenomics_data.append([key, value])
                
                if tokenomics_data:
                    story.append(Paragraph("Tokenomics Metrics", styles['SubsectionTitle']))
                    metrics_table = Table(tokenomics_data, colWidths=[2.5*inch, 3*inch])
                    metrics_table.setStyle([
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                        ('PADDING', (0, 0), (-1, -1), 6)
                    ])
                    story.append(metrics_table)
        
        # For all other sections, try to extract content from research summary
        else:
            section_content = ""
            section_title_lower = section_title.lower()
            
            # Try to find content related to this section in research summary
            if state.research_summary:
                for paragraph in state.research_summary.split("\n\n"):
                    # Check if paragraph relates to this section
                    if any(keyword in paragraph.lower() for keyword in section_title_lower.split()):
                        section_content += paragraph + "\n\n"
            
            # If we found content, add it
            if section_content:
                story.append(Paragraph(section_content, styles['Normal']))
            else:
                # Otherwise, add a generic paragraph
                story.append(Paragraph(f"Information about {state.project_name}'s {section_title.lower()} is presented in this section.", styles['Normal']))
                
            # Add section-specific visualizations if available
            if hasattr(state, 'visualizations'):
                for vis_type, vis_data in state.visualizations.items():
                    # Check if visualization matches this section
                    vis_name = vis_type.replace('_', ' ').lower()
                    if any(keyword in vis_name for keyword in section_title_lower.split()):
                        if 'file_path' in vis_data and os.path.exists(vis_data['file_path']):
                            story.append(Paragraph(vis_data.get('title', vis_type.replace('_', ' ').title()), styles['SubsectionTitle']))
                            img = Image(vis_data['file_path'], width=5*inch, height=3*inch)
                            img.hAlign = 'CENTER'
                            story.append(img)
                            if 'description' in vis_data:
                                story.append(Paragraph(vis_data['description'], styles['Caption']))
                            story.append(Spacer(1, 0.2*inch))
    
    # Add References section with better formatting
    story.append(PageBreak())
    story.append(Paragraph("References", styles['SectionTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    if state.references:
        # Sort references to avoid duplicates and improve presentation
        unique_refs = {}
        for ref in state.references:
            if ref['url'] not in unique_refs:
                unique_refs[ref['url']] = ref['title']
        
        for i, (url, title) in enumerate(unique_refs.items(), 1):
            # Truncate title if needed to avoid rendering issues
            truncated_title = title[:100] + "..." if len(title) > 100 else title
            ref_text = f"{i}. {truncated_title}"
            story.append(Paragraph(ref_text, styles['Reference']))
            story.append(Spacer(1, 4))
            logger.debug(f"Added reference {i}: {url}")
    else:
        story.append(Paragraph("No web references available; data sourced from APIs.", styles['Normal']))

    # Sources section
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Data Sources:", styles['SubsectionTitle']))
    sources = [
        "CoinGecko: Price data, supply metrics, market trends",
        "CoinMarketCap: Market capitalization, pricing data",
        "DeFiLlama: Total Value Locked (TVL) metrics",
        "On-chain Data: Liquidity pools, trading volume",
        "Research: Web references, project documentation"
    ]
    
    for source in sources:
        story.append(Paragraph(f"• {source}", styles['Normal']))
        story.append(Spacer(1, 4))

    # Build PDF
    try:
        doc.build(story)
        state.final_report = f"PDF generated at docs/{state.project_name}_report.pdf"
        logger.info(f"Publishing completed for {state.project_name}. PDF saved at docs/{state.project_name}_report.pdf")
    except Exception as e:
        logger.error(f"Error building PDF: {e}")
        state.final_report = f"PDF generation failed: {str(e)}"

    state.update_progress("Report published.")
    return state

# Helper functions to generate context-appropriate text
def get_project_maturity(state):
    """Determine project maturity based on available data"""
    # This is a placeholder logic - would be better with real data
    if state.research_summary and ("established" in state.research_summary.lower() or "mature" in state.research_summary.lower()):
        return "well-established"
    elif state.research_summary and ("new" in state.research_summary.lower() or "emerging" in state.research_summary.lower()):
        return "emerging"
    else:
        return "developing"

def get_primary_focus(state):
    """Extract the primary focus of the project"""
    # Try to extract from research summary
    focus_indicators = {
        "defi": "decentralized finance (DeFi)",
        "exchange": "trading and exchange services",
        "nft": "non-fungible tokens (NFTs)",
        "layer": "blockchain infrastructure",
        "gaming": "blockchain gaming",
        "metaverse": "metaverse applications",
        "dao": "decentralized governance",
        "privacy": "privacy-focused solutions",
        "oracle": "oracle services",
        "lending": "lending and borrowing protocols",
        "staking": "staking and yield generation"
    }
    
    if state.research_summary:
        lower_summary = state.research_summary.lower()
        for indicator, description in focus_indicators.items():
            if indicator in lower_summary:
                return description
    
    # Default if no match found
    return "blockchain technology applications"

def get_investment_recommendation(state):
    """Generate an investment recommendation phrase"""
    # This would ideally use more sophisticated analysis
    if state.price_analysis and "60-Day Change:" in state.price_analysis:
        price_change = state.price_analysis.split("60-Day Change:")[1].strip().split()[0]
        try:
            change_float = float(price_change.strip('%'))
            if change_float > 20:
                return "strong growth potential"
            elif change_float > 5:
                return "promising fundamentals"
            elif change_float > -5:
                return "stable characteristics"
            else:
                return "potential value at current levels, with higher risk factors"
        except ValueError:
            pass
    
    # Default recommendation
    return "various strengths and considerations to evaluate"

# Add this function to clean markdown formatting
def clean_markdown(text):
    """Remove markdown formatting that might cause issues in the PDF"""
    import re
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold markers
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic markers
    text = re.sub(r'#{1,6}\s+', '', text)         # Remove heading markers
    return text