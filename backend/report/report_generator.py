"""
Enhanced report generator for XplainCrypto with PDF optimization.
This module provides advanced report generation capabilities with beautiful visualizations
optimized for PDF output.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import matplotlib.pyplot as plt
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import json
import pandas as pd

# Import visualization components
from backend.visualizations.line_chart import LineChartVisualizer
from backend.visualizations.bar_chart import BarChartVisualizer
from backend.visualizations.pie_chart import PieChartVisualizer
from backend.utils.llm_factory import LLMFactory

# Configure logging
logger = logging.getLogger(__name__)

class ReportGenerator:
    """Enhanced report generator with PDF optimization."""
    
    def __init__(self, theme: str = "dark", output_dir: str = "reports"):
        """
        Initialize the report generator.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            output_dir: Directory to save reports
        """
        self.theme = theme
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize visualizers
        self.line_chart = LineChartVisualizer(theme=theme, pdf_optimized=True)
        self.bar_chart = BarChartVisualizer(theme=theme, pdf_optimized=True)
        self.pie_chart = PieChartVisualizer(theme=theme, pdf_optimized=True)
        
        # Initialize Jinja2 environment for HTML templates
        self.jinja_env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
            autoescape=True
        )
        
        # Create templates directory if it doesn't exist
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(templates_dir, exist_ok=True)
        
        # Create default template if it doesn't exist
        default_template_path = os.path.join(templates_dir, 'report_template.html')
        if not os.path.exists(default_template_path):
            self._create_default_template(default_template_path)
    
    def _create_default_template(self, template_path: str):
        """Create a default HTML template for reports."""
        template_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <style>
                @page {
                    size: A4;
                    margin: 2cm;
                }
                body {
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: {{ text_color }};
                    background-color: {{ background_color }};
                    margin: 0;
                    padding: 0;
                }
                .container {
                    max-width: 100%;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1, h2, h3, h4, h5, h6 {
                    color: {{ heading_color }};
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }
                h1 {
                    font-size: 28px;
                    text-align: center;
                    margin-top: 0;
                    padding-top: 20px;
                    border-bottom: 2px solid {{ accent_color }};
                    padding-bottom: 10px;
                }
                h2 {
                    font-size: 24px;
                    border-bottom: 1px solid {{ accent_color }};
                    padding-bottom: 5px;
                }
                h3 {
                    font-size: 20px;
                }
                p {
                    margin-bottom: 1em;
                }
                img {
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 20px auto;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                th, td {
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid {{ border_color }};
                }
                th {
                    background-color: {{ accent_color }};
                    color: {{ background_color }};
                    font-weight: bold;
                }
                tr:nth-child(even) {
                    background-color: {{ table_alt_color }};
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                }
                .logo {
                    max-width: 200px;
                }
                .date {
                    font-style: italic;
                    color: {{ text_color }};
                    opacity: 0.7;
                }
                .footer {
                    text-align: center;
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid {{ border_color }};
                    font-size: 12px;
                    color: {{ text_color }};
                    opacity: 0.7;
                }
                .chart-container {
                    margin: 30px 0;
                }
                .chart-title {
                    text-align: center;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .key-metrics {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    margin: 20px 0;
                }
                .metric-card {
                    background-color: {{ card_background }};
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 15px;
                    width: calc(33% - 10px);
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .metric-title {
                    font-size: 14px;
                    color: {{ text_color }};
                    opacity: 0.8;
                    margin-bottom: 5px;
                }
                .metric-value {
                    font-size: 24px;
                    font-weight: bold;
                    color: {{ accent_color }};
                }
                .positive {
                    color: {{ positive_color }};
                }
                .negative {
                    color: {{ negative_color }};
                }
                .neutral {
                    color: {{ neutral_color }};
                }
                .executive-summary {
                    background-color: {{ card_background }};
                    border-left: 4px solid {{ accent_color }};
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 0 8px 8px 0;
                }
                .risk-assessment {
                    background-color: {{ card_background }};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                }
                .risk-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid {{ border_color }};
                }
                .risk-name {
                    font-weight: bold;
                }
                .risk-rating {
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                .risk-low {
                    background-color: {{ positive_color }};
                    color: white;
                }
                .risk-medium {
                    background-color: {{ neutral_color }};
                    color: white;
                }
                .risk-high {
                    background-color: {{ negative_color }};
                    color: white;
                }
                @media print {
                    body {
                        font-size: 12pt;
                    }
                    h1 {
                        font-size: 24pt;
                    }
                    h2 {
                        font-size: 18pt;
                    }
                    h3 {
                        font-size: 14pt;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div>
                        <h1>{{ title }}</h1>
                        <p class="date">Generated on {{ generation_date }}</p>
                    </div>
                </div>
                
                {{ content|safe }}
                
                <div class="footer">
                    <p>© {{ current_year }} XplainCrypto. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(template_path, 'w') as f:
            f.write(template_content)
    
    def generate_report(self, research_data: Dict[str, Any], config: Dict[str, Any]) -> str:
        """
        Generate a comprehensive PDF report from research data.
        
        Args:
            research_data: Dictionary containing research data
            config: Report configuration
            
        Returns:
            Path to the generated PDF report
        """
        logger.info(f"Generating report for {research_data.get('project_name', 'Unknown Project')}")
        
        # Extract project name and create safe filename
        project_name = research_data.get('project_name', 'Unknown Project')
        safe_name = ''.join(c if c.isalnum() else '_' for c in project_name.lower())
        
        # Create report directory
        report_dir = os.path.join(self.output_dir, safe_name)
        os.makedirs(report_dir, exist_ok=True)
        
        # Create images directory
        images_dir = os.path.join(report_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # Generate visualizations based on config
        visualization_paths = self._generate_visualizations(research_data, config, images_dir)
        
        # Generate HTML content
        html_content = self._generate_html_content(research_data, config, visualization_paths)
        
        # Save HTML file
        html_path = os.path.join(report_dir, f"{safe_name}_report.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Convert HTML to PDF
        pdf_path = os.path.join(report_dir, f"{safe_name}_report.pdf")
        self._convert_to_pdf(html_path, pdf_path)
        
        logger.info(f"Report generated successfully: {pdf_path}")
        return pdf_path
    
    def _generate_visualizations(self, research_data: Dict[str, Any], config: Dict[str, Any], 
                               images_dir: str) -> Dict[str, str]:
        """
        Generate visualizations for the report.
        
        Args:
            research_data: Dictionary containing research data
            config: Report configuration
            images_dir: Directory to save visualization images
            
        Returns:
            Dictionary mapping visualization keys to file paths
        """
        visualization_paths = {}
        
        # Process each section in the config
        for section in config.get('sections', []):
            section_id = section.get('id', '')
            visualizations = section.get('visualizations', [])
            
            for viz in visualizations:
                viz_type = viz.get('type', '')
                viz_id = viz.get('id', '')
                viz_data_key = viz.get('data_key', '')
                
                # Skip if no visualization type or ID
                if not viz_type or not viz_id:
                    continue
                
                # Get visualization data
                viz_data = research_data.get(viz_data_key, {})
                if not viz_data and viz_data_key in research_data:
                    # Try to parse JSON string
                    try:
                        viz_data = json.loads(research_data[viz_data_key])
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Could not parse visualization data for {viz_id}")
                        continue
                
                # Generate visualization
                try:
                    viz_path = self._generate_visualization(viz_type, viz_id, viz_data, images_dir, viz)
                    if viz_path:
                        visualization_paths[viz_id] = viz_path
                except Exception as e:
                    logger.error(f"Error generating visualization {viz_id}: {str(e)}")
        
        return visualization_paths
    
    def _generate_visualization(self, viz_type: str, viz_id: str, viz_data: Dict[str, Any], 
                              images_dir: str, viz_config: Dict[str, Any]) -> Optional[str]:
        """
        Generate a single visualization.
        
        Args:
            viz_type: Type of visualization
            viz_id: Visualization ID
            viz_data: Visualization data
            images_dir: Directory to save visualization images
            viz_config: Visualization configuration
            
        Returns:
            Path to the generated visualization image
        """
        if not viz_data:
            logger.warning(f"No data for visualization {viz_id}")
            return None
        
        # Create file path
        file_path = os.path.join(images_dir, f"{viz_id}.png")
        
        # Get title from config
        title = viz_config.get('title', viz_id.replace('_', ' ').title())
        
        # Generate visualization based on type
        if viz_type == 'price_chart':
            self.line_chart.plot_price_chart(
                data=viz_data,
                title=title,
                show_volume=viz_config.get('show_volume', True),
                add_indicators=viz_config.get('add_indicators', True),
                moving_averages=viz_config.get('moving_averages', [7, 30, 90])
            )
            self.line_chart.save_figure(file_path)
            self.line_chart.close_figure()
            
        elif viz_type == 'comparison_chart':
            self.line_chart.plot_comparison_chart(
                data_sets=viz_data,
                title=title,
                normalize=viz_config.get('normalize', True)
            )
            self.line_chart.save_figure(file_path)
            self.line_chart.close_figure()
            
        elif viz_type == 'correlation_chart':
            self.line_chart.plot_correlation_chart(
                data=viz_data,
                title=title
            )
            self.line_chart.save_figure(file_path)
            self.line_chart.close_figure()
            
        elif viz_type == 'token_metrics':
            self.line_chart.plot_token_metrics(
                timestamps=viz_data.get('timestamps', []),
                metrics=viz_data.get('metrics', {}),
                title=title
            )
            self.line_chart.save_figure(file_path)
            self.line_chart.close_figure()
            
        elif viz_type == 'market_dominance':
            self.bar_chart.plot_market_dominance(
                data=viz_data,
                title=title
            )
            self.bar_chart.save_figure(file_path)
            self.bar_chart.close_figure()
            
        elif viz_type == 'token_distribution_bar':
            self.bar_chart.plot_token_distribution(
                data=viz_data,
                title=title
            )
            self.bar_chart.save_figure(file_path)
            self.bar_chart.close_figure()
            
        elif viz_type == 'comparison_bars':
            self.bar_chart.plot_comparison_bars(
                categories=viz_data.get('categories', []),
                data_sets=viz_data.get('data_sets', []),
                title=title
            )
            self.bar_chart.save_figure(file_path)
            self.bar_chart.close_figure()
            
        elif viz_type == 'risk_matrix':
            self.bar_chart.plot_risk_matrix(
                risks=viz_data,
                title=title
            )
            self.bar_chart.save_figure(file_path)
            self.bar_chart.close_figure()
            
        elif viz_type == 'token_distribution_pie':
            self.pie_chart.plot_token_distribution_pie(
                data=viz_data,
                title=title,
                explode_largest=viz_config.get('explode_largest', True),
                donut=viz_config.get('donut', True)
            )
            self.pie_chart.save_figure(file_path)
            self.pie_chart.close_figure()
            
        elif viz_type == 'market_share_pie':
            self.pie_chart.plot_market_share_pie(
                data=viz_data,
                title=title,
                min_percentage=viz_config.get('min_percentage', 3.0)
            )
            self.pie_chart.save_figure(file_path)
            self.pie_chart.close_figure()
            
        elif viz_type == 'nested_pie':
            self.pie_chart.plot_nested_pie(
                inner_data=viz_data.get('inner_data', {}),
                outer_data=viz_data.get('outer_data', {}),
                title=title
            )
            self.pie_chart.save_figure(file_path)
            self.pie_chart.close_figure()
            
        elif viz_type == 'valuation_range':
            self.pie_chart.plot_valuation_range(
                current_price=viz_data.get('current_price', 0),
                valuation_ranges=viz_data.get('valuation_ranges', {}),
                title=title
            )
            self.pie_chart.save_figure(file_path)
            self.pie_chart.close_figure()
            
        else:
            logger.warning(f"Unknown visualization type: {viz_type}")
            return None
        
        return file_path
    
    def _generate_html_content(self, research_data: Dict[str, Any], config: Dict[str, Any],
                             visualization_paths: Dict[str, str]) -> str:
        """
        Generate HTML content for the report.
        
        Args:
            research_data: Dictionary containing research data
            config: Report configuration
            visualization_paths: Dictionary mapping visualization keys to file paths
            
        Returns:
            HTML content for the report
        """
        # Load template
        template = self.jinja_env.get_template('report_template.html')
        
        # Get project name
        project_name = research_data.get('project_name', 'Unknown Project')
        
        # Get current date
        current_date = datetime.now().strftime('%B %d, %Y')
        current_year = datetime.now().year
        
        # Get theme colors
        colors = self._get_theme_colors()
        
        # Process markdown content to HTML
        content_html = self._process_content(research_data, config, visualization_paths)
        
        # Render template
        html_content = template.render(
            title=f"{project_name} Research Report",
            content=content_html,
            generation_date=current_date,
            current_year=current_year,
            text_color=colors['text'],
            background_color=colors['background'],
            heading_color=colors['heading'],
            accent_color=colors['accent'],
            border_color=colors['border'],
            table_alt_color=colors['table_alt'],
            card_background=colors['card_background'],
            positive_color=colors['positive'],
            negative_color=colors['negative'],
            neutral_color=colors['neutral']
        )
        
        return html_content
    
    def _process_content(self, research_data: Dict[str, Any], config: Dict[str, Any],
                       visualization_paths: Dict[str, str]) -> str:
        """
        Process research data and config into HTML content.
        
        Args:
            research_data: Dictionary containing research data
            config: Report configuration
            visualization_paths: Dictionary mapping visualization keys to file paths
            
        Returns:
            HTML content for the report
        """
        content_html = ""
        
        # Get draft content
        draft = research_data.get('draft', '')
        
        # Process each section in the config
        for section in config.get('sections', []):
            section_id = section.get('id', '')
            section_title = section.get('title', '')
            section_content_key = section.get('content_key', '')
            visualizations = section.get('visualizations', [])
            
            # Start section
            content_html += f"<h2 id='{section_id}'>{section_title}</h2>\n"
            
            # Add section content
            section_content = ""
            
            # Try to extract section content from draft
            if draft:
                section_marker = f"# {section_title}"
                next_section_index = draft.find("# ", draft.find(section_marker) + 1) if draft.find(section_marker) >= 0 else -1
                
                if draft.find(section_marker) >= 0:
                    if next_section_index >= 0:
                        section_content = draft[draft.find(section_marker) + len(section_marker):next_section_index]
                    else:
                        section_content = draft[draft.find(section_marker) + len(section_marker):]
            
            # If no content found in draft, try to get from research_data
            if not section_content.strip() and section_content_key and section_content_key in research_data:
                section_content = research_data[section_content_key]
            
            # Convert markdown to HTML
            if section_content:
                # Simple markdown to HTML conversion
                section_content = self._markdown_to_html(section_content)
                content_html += section_content + "\n"
            
            # Add visualizations
            for viz in visualizations:
                viz_id = viz.get('id', '')
                viz_caption = viz.get('caption', '')
                
                if viz_id in visualization_paths:
                    viz_path = visualization_paths[viz_id]
                    rel_path = os.path.relpath(viz_path, os.path.dirname(os.path.join(self.output_dir, 'temp.html')))
                    
                    content_html += f"<div class='chart-container'>\n"
                    content_html += f"<img src='{rel_path}' alt='{viz_id}'>\n"
                    if viz_caption:
                        content_html += f"<p class='chart-caption'>{viz_caption}</p>\n"
                    content_html += f"</div>\n"
        
        return content_html
    
    def _markdown_to_html(self, markdown: str) -> str:
        """
        Convert markdown to HTML.
        
        Args:
            markdown: Markdown content
            
        Returns:
            HTML content
        """
        # Simple markdown to HTML conversion
        html = markdown
        
        # Headers
        html = html.replace("\n## ", "\n<h2>").replace(" ##\n", "</h2>\n")
        html = html.replace("\n### ", "\n<h3>").replace(" ###\n", "</h3>\n")
        html = html.replace("\n#### ", "\n<h4>").replace(" ####\n", "</h4>\n")
        
        # Bold and italic
        html = html.replace("**", "<strong>").replace("**", "</strong>")
        html = html.replace("*", "<em>").replace("*", "</em>")
        
        # Lists
        lines = html.split("\n")
        in_list = False
        new_lines = []
        
        for line in lines:
            if line.strip().startswith("- "):
                if not in_list:
                    new_lines.append("<ul>")
                    in_list = True
                new_lines.append(f"<li>{line.strip()[2:]}</li>")
            elif line.strip().startswith("1. ") or line.strip().startswith("2. ") or line.strip().startswith("3. "):
                if not in_list:
                    new_lines.append("<ol>")
                    in_list = True
                new_lines.append(f"<li>{line.strip()[3:]}</li>")
            else:
                if in_list:
                    new_lines.append("</ul>" if "- " in html else "</ol>")
                    in_list = False
                new_lines.append(line)
        
        if in_list:
            new_lines.append("</ul>" if "- " in html else "</ol>")
        
        html = "\n".join(new_lines)
        
        # Paragraphs
        paragraphs = html.split("\n\n")
        html = "\n\n".join([f"<p>{p}</p>" if not p.startswith("<") else p for p in paragraphs if p.strip()])
        
        return html
    
    def _convert_to_pdf(self, html_path: str, pdf_path: str):
        """
        Convert HTML to PDF.
        
        Args:
            html_path: Path to HTML file
            pdf_path: Path to output PDF file
        """
        # Create CSS for PDF
        css = CSS(string="""
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: 'Arial', sans-serif;
            }
        """)
        
        # Convert HTML to PDF
        HTML(filename=html_path).write_pdf(pdf_path, stylesheets=[css])
    
    def _get_theme_colors(self) -> Dict[str, str]:
        """
        Get colors for the current theme.
        
        Returns:
            Dictionary of theme colors
        """
        if self.theme == "dark":
            return {
                'text': '#ffffff',
                'background': '#121212',
                'heading': '#ffffff',
                'accent': '#4cc9f0',
                'border': '#333333',
                'table_alt': '#1e1e1e',
                'card_background': '#1e1e1e',
                'positive': '#00b894',
                'negative': '#ff7675',
                'neutral': '#74b9ff'
            }
        else:
            return {
                'text': '#333333',
                'background': '#ffffff',
                'heading': '#333333',
                'accent': '#0077b6',
                'border': '#dddddd',
                'table_alt': '#f5f5f5',
                'card_background': '#f5f5f5',
                'positive': '#00b894',
                'negative': '#ff7675',
                'neutral': '#74b9ff'
            }
