import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

class PlotlyStyler:
    """
    Utility class for applying consistent styling to Plotly charts
    based on the application's style_config.json.
    """
    def __init__(self, theme: str = 'light', project_name: Optional[str] = None, 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the PlotlyStyler with configuration from style_config.json
        
        Args:
            theme: 'light' or 'dark' theme
            project_name: Optional name of the project for watermarks
            logger: Optional logger instance
        """
        self.theme = theme
        self.project_name = project_name or 'XplainCrypto'
        self.logger = logger or logging.getLogger(__name__)
        self.style_config = self._load_style_config()
        self.colors = self._get_theme_colors()
        self._set_default_template()
        
        # Set project watermark
        self.watermark = f"© {self.project_name} Research"
        
    def _load_style_config(self) -> Dict[str, Any]:
        """Load the style configuration from JSON file"""
        try:
            # Try multiple possible locations for the style_config.json file
            possible_paths = [
                os.path.join("config", "style_config.json"),
                os.path.join("..", "config", "style_config.json"),
                os.path.join("backend", "config", "style_config.json"),
                os.path.join("..", "backend", "config", "style_config.json"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "style_config.json")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        return json.load(f)
            
            # If none of the paths work, return empty dict
            self.logger.error(f"Could not find style_config.json in any expected location")
            return {}
        except Exception as e:
            self.logger.error(f"Error loading style config: {e}")
            return {}
            
    def _get_theme_colors(self) -> Dict[str, Any]:
        """Get the color palette for the current theme"""
        visualization = self.style_config.get("visualization", {})
        themes = visualization.get("themes", {})
        theme_colors = themes.get(self.theme, {})
        
        # Default colors if theme not found
        default_colors = {
            "light": {
                "background": "#ffffff",
                "text": "#333333",
                "accent": "#3366cc",
                "secondary": "#66aa66",
                "grid": "#dddddd",
                "error": "#e15759",
                "success": "#4caf50",
                "accent_palette": ["#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", "#dd4477", "#66aa00"]
            },
            "dark": {
                "background": "#202124",
                "text": "#e8eaed",
                "accent": "#8ab4f8",
                "secondary": "#81c995",
                "grid": "#3c4043",
                "error": "#f28b82",
                "success": "#81c995",
                "accent_palette": ["#8ab4f8", "#f28b82", "#fdd663", "#81c995", "#d7aefb", "#78d9ec", "#ff8bcb", "#b9e769"]
            }
        }
        
        if not theme_colors:
            self.logger.warning(f"Theme '{self.theme}' not found in config, using defaults")
            return default_colors.get(self.theme, default_colors["light"])
        
        return theme_colors
    
    def _set_default_template(self):
        """
        Configure a custom Plotly template based on style configuration
        """
        vis_config = self.style_config.get("visualization", {})
        fonts = self.style_config.get("fonts", {})
        sizes = self.style_config.get("font_sizes", {})
        
        # Create template with our styling
        template = go.layout.Template()
        
        # Configure global font
        template.layout.font = dict(
            family=fonts.get("family", "Arial, Helvetica, sans-serif"),
            size=sizes.get("body_text", 12),
            color=self.colors.get("text", "#333333")
        )
        
        # Configure color axis
        template.layout.coloraxis.colorscale = self.colors.get("accent_palette", ["#3366cc", "#dc3912"])
        
        # Configure title
        template.layout.title = dict(
            font=dict(
                family=fonts.get("family", "Arial, Helvetica, sans-serif"),
                size=sizes.get("title", 18),
                color=self.colors.get("text", "#333333")
            ),
            x=0.5,
            xanchor="center"
        )
        
        # Configure axes
        axis_config = dict(
            title=dict(
                font=dict(
                    family=fonts.get("family", "Arial, Helvetica, sans-serif"),
                    size=sizes.get("section_heading", 14),
                    color=self.colors.get("text", "#333333")
                ),
                standoff=10
            ),
            tickfont=dict(
                family=fonts.get("family", "Arial, Helvetica, sans-serif"),
                size=sizes.get("caption", 10),
                color=self.colors.get("text", "#333333")
            ),
            gridcolor=self.colors.get("grid", "#dddddd"),
            gridwidth=1,
            linecolor=self.colors.get("text", "#333333"),
            linewidth=1,
            showgrid=True,
            zeroline=True,
            zerolinecolor=self.colors.get("text", "#333333"),
            zerolinewidth=1
        )
        
        template.layout.xaxis = axis_config
        template.layout.yaxis = axis_config
        
        # Configure legend
        template.layout.legend = dict(
            font=dict(
                family=fonts.get("family", "Arial, Helvetica, sans-serif"),
                size=sizes.get("caption", 10),
                color=self.colors.get("text", "#333333")
            ),
            bgcolor=self.colors.get("background", "#ffffff"),
            bordercolor=self.colors.get("grid", "#dddddd"),
            borderwidth=1
        )
        
        # Configure margin
        template.layout.margin = dict(l=50, r=50, t=80, b=50, pad=10)
        
        # Configure paper and plot background
        template.layout.paper_bgcolor = self.colors.get("background", "#ffffff")
        template.layout.plot_bgcolor = self.colors.get("background", "#ffffff")
        
        # Configure hover
        template.layout.hovermode = "closest"
        
        # Set template name based on theme
        template_name = f"xplaincrypto_{self.theme}"
        pio.templates[template_name] = template
        pio.templates.default = template_name
        
    def apply_layout(self, fig: go.Figure, title: str, width: int = 900, height: int = 500, 
                     showlegend: bool = True) -> go.Figure:
        """
        Apply consistent layout to a Plotly figure
        
        Args:
            fig: The plotly figure to style
            title: Chart title
            width: Chart width in pixels
            height: Chart height in pixels
            showlegend: Whether to show the legend
            
        Returns:
            The styled figure
        """
        paper_bgcolor = self.colors.get("background", "#ffffff")
        plot_bgcolor = self.colors.get("background", "#ffffff")
        
        fig.update_layout(
            title=title,
            width=width,
            height=height,
            paper_bgcolor=paper_bgcolor,
            plot_bgcolor=plot_bgcolor,
            showlegend=showlegend
        )
        return fig
    
    def style_bar_chart(self, fig: go.Figure, x_title: str = None, y_title: str = None,
                        text_auto: Union[bool, str] = False) -> go.Figure:
        """
        Apply styling specific to bar charts
        
        Args:
            fig: The plotly figure to style
            x_title: Optional title for x-axis
            y_title: Optional title for y-axis
            text_auto: Whether to show values on bars
            
        Returns:
            The styled figure
        """
        # Update layout
        fig.update_layout(
            bargap=0.2,
            bargroupgap=0.1
        )
        
        # Update axis titles
        if x_title:
            fig.update_xaxes(title_text=x_title)
        if y_title:
            fig.update_yaxes(title_text=y_title)
        
        # Apply consistent styling to all bars
        fig.update_traces(
            marker_line_width=1,
            marker_line_color=self.colors.get("grid", "#dddddd"),
            marker_color=self.colors.get("accent", "#3366cc"),
            opacity=0.8,
            textfont=dict(
                family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif"),
                size=self.style_config.get("font_sizes", {}).get("caption", 10),
                color=self.colors.get("text", "#333333")
            )
        )
        
        # Add values on bars if requested
        if text_auto:
            fig.update_traces(
                texttemplate='%{y:.2s}' if text_auto is True else text_auto,
                textposition='outside'
            )
        
        # Update axes
        fig.update_xaxes(
            showgrid=False,
            showline=True,
            linewidth=1,
            linecolor=self.colors.get("grid", "#dddddd"),
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor=self.colors.get("grid", "#dddddd"),
            showline=True,
            linewidth=1,
            linecolor=self.colors.get("grid", "#dddddd"),
        )
        
        return fig
    
    def style_line_chart(self, fig: go.Figure, x_title: str = None, y_title: str = None,
                         show_points: bool = True) -> go.Figure:
        """
        Apply styling specific to line charts
        
        Args:
            fig: The plotly figure to style
            x_title: Optional title for x-axis
            y_title: Optional title for y-axis
            show_points: Whether to show points on the line
            
        Returns:
            The styled figure
        """
        # Create color sequence based on accent_palette
        color_sequence = self.colors.get("accent_palette", [
            "#3366cc", "#dc3912", "#ff9900", "#109618", 
            "#990099", "#0099c6", "#dd4477", "#66aa00"
        ])
        
        # Update layout
        fig.update_layout(
            hovermode="x unified"
        )
        
        # Update axis titles
        if x_title:
            fig.update_xaxes(title_text=x_title)
        if y_title:
            fig.update_yaxes(title_text=y_title)
        
        # Apply consistent styling to all lines
        for i, trace in enumerate(fig.data):
            if trace.type == 'scatter' and trace.mode in ['lines', 'lines+markers', 'markers']:
                color_idx = i % len(color_sequence)
                fig.data[i].update(
                    line=dict(
                        width=2.5,
                        color=color_sequence[color_idx]
                    ),
                    marker=dict(
                        size=6,
                        symbol='circle',
                        color=color_sequence[color_idx],
                        line=dict(
                            width=1,
                            color=self.colors.get("background", "#ffffff")
                        )
                    ),
                    mode='lines+markers' if show_points else 'lines'
                )
        
        # Update axes
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor=self.colors.get("grid", "#dddddd"),
            showline=True,
            linewidth=1,
            linecolor=self.colors.get("grid", "#dddddd"),
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor=self.colors.get("grid", "#dddddd"),
            showline=True,
            linewidth=1,
            linecolor=self.colors.get("grid", "#dddddd"),
            zeroline=True,
            zerolinewidth=1,
            zerolinecolor=self.colors.get("grid", "#dddddd"),
        )
        
        return fig
    
    def style_pie_chart(self, fig: go.Figure, title_position: str = "top center") -> go.Figure:
        """
        Apply styling specific to pie charts
        
        Args:
            fig: The plotly figure to style
            title_position: Position of the title
            
        Returns:
            The styled figure
        """
        # Get pie chart specific config
        vis_config = self.style_config.get("visualization", {})
        pie_config = vis_config.get("pie_chart", {})
        
        # Create color sequence based on accent_palette
        color_sequence = self.colors.get("accent_palette", [
            "#3366cc", "#dc3912", "#ff9900", "#109618", 
            "#990099", "#0099c6", "#dd4477", "#66aa00"
        ])
        
        # Get donut hole size
        donut_hole = pie_config.get("donut_hole", 0.4)
        
        # Update layout
        fig.update_layout(
            title_x=0.5 if "center" in title_position else 0.0,
            title_y=0.95 if "top" in title_position else 0.0,
            showlegend=True,
            legend=dict(
                orientation="h",
                xanchor="center",
                x=0.5,
                y=-0.1
            )
        )
        
        # Apply consistent styling to the pie chart
        fig.update_traces(
            marker=dict(
                colors=color_sequence,
                line=dict(
                    color=self.colors.get("background", "#ffffff"),
                    width=1
                )
            ),
            hole=donut_hole,
            textfont=dict(
                family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif"),
                size=self.style_config.get("font_sizes", {}).get("caption", 10),
                color=self.colors.get("text", "#333333")
            ),
            textposition="outside",
            textinfo="percent+label",
            insidetextorientation="radial"
        )
        
        return fig
    
    def style_table(self, fig: go.Figure, alternating_fill: bool = True) -> go.Figure:
        """
        Apply styling specific to tables
        
        Args:
            fig: The plotly figure to style
            alternating_fill: Whether to apply alternating colors to rows
            
        Returns:
            The styled figure
        """
        # Get table specific config
        vis_config = self.style_config.get("visualization", {})
        table_config = vis_config.get("table", {})
        
        # Get color setup
        header_color = table_config.get("header_color", {}).get(self.theme, "#f2f2f2")
        row_colors = table_config.get("row_colors", {}).get(self.theme, ["#ffffff", "#f9f9f9"])
        border_color = table_config.get("border_color", {}).get(self.theme, "#dddddd")
        
        # Skip styling if table not found
        if not fig.data or not fig.data[0].type == 'table':
            return fig
        
        # Get the table data
        table = fig.data[0]
        
        # Style the header
        header_values = table.header.values if hasattr(table, 'header') and hasattr(table.header, 'values') else []
        fig.update_traces(
            header=dict(
                fill_color=header_color,
                align='center',
                font=dict(
                    size=table_config.get("font_size", 10) + 1,
                    color=self.colors.get("text", "#333333"),
                    family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif")
                ),
                height=table_config.get("row_height", 0.3) * table_config.get("header_scale", 1.2) * 100,
                line=dict(
                    width=1,
                    color=border_color
                )
            )
        )
        
        # Style the cells
        row_fill_color = row_colors[0]
        if alternating_fill:
            # Create alternating colors for rows
            num_rows = len(table.cells.values[0]) if (hasattr(table, 'cells') and 
                                                       hasattr(table.cells, 'values') and 
                                                       len(table.cells.values) > 0) else 0
            row_fill_color = [row_colors[i % len(row_colors)] for i in range(num_rows)]
            
        fig.update_traces(
            cells=dict(
                fill_color=row_fill_color,
                align='center',
                font=dict(
                    size=table_config.get("font_size", 10),
                    color=self.colors.get("text", "#333333"),
                    family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif")
                ),
                height=table_config.get("row_height", 0.3) * 100,
                line=dict(
                    width=1,
                    color=border_color
                )
            )
        )
        
        return fig
    
    def add_watermark(self, fig: go.Figure) -> go.Figure:
        """
        Add a watermark to the plot
        
        Args:
            fig: The plotly figure to modify
            
        Returns:
            The modified figure
        """
        # Convert hex color to rgba for proper opacity handling
        text_color = self.colors.get("text", "#333333")
        # If it's a hex color, convert to rgba
        if text_color.startswith('#'):
            r = int(text_color[1:3], 16)
            g = int(text_color[3:5], 16)
            b = int(text_color[5:7], 16)
            rgba_color = f"rgba({r}, {g}, {b}, 0.1)"  # 10% opacity
        else:
            rgba_color = text_color
            
        fig.add_annotation(
            text=self.watermark,
            x=1,
            y=0,
            xref="paper",
            yref="paper",
            xanchor="right",
            yanchor="bottom",
            showarrow=False,
            font=dict(
                family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif"),
                size=8,
                color=rgba_color
            )
        )
        
        return fig
    
    def add_source_annotation(self, fig: go.Figure, source: str, y_position: float = -0.15) -> go.Figure:
        """
        Add a source annotation to the bottom of the chart
        
        Args:
            fig: The plotly figure to modify
            source: Source text
            y_position: Y position for the annotation
            
        Returns:
            The modified figure
        """
        if not source:
            return fig
            
        # Add the source annotation
        fig.add_annotation(
            text=f"Source: {source}",
            x=0,
            y=y_position,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(
                family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif"),
                size=self.style_config.get("font_sizes", {}).get("disclaimer", 8),
                color=self.colors.get("text", "#333333")
            ),
            align="left",
            xanchor="left"
        )
        
        return fig
    
    def add_note_annotation(self, fig: go.Figure, note: str, y_position: float = -0.2) -> go.Figure:
        """
        Add a note annotation to the bottom of the chart
        
        Args:
            fig: The plotly figure to modify
            note: Note text
            y_position: Y position for the annotation
            
        Returns:
            The modified figure
        """
        if not note:
            return fig
            
        # Convert hex color to rgba for proper opacity handling
        text_color = self.colors.get("text", "#333333")
        # If it's a hex color, convert to rgba
        if text_color.startswith('#'):
            r = int(text_color[1:3], 16)
            g = int(text_color[3:5], 16)
            b = int(text_color[5:7], 16)
            rgba_color = f"rgba({r}, {g}, {b}, 0.8)"  # 80% opacity
        else:
            rgba_color = text_color
            
        # Add the note annotation
        fig.add_annotation(
            text=f"Note: {note}",
            x=0,
            y=y_position,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(
                family=self.style_config.get("fonts", {}).get("family", "Arial, Helvetica, sans-serif"),
                size=self.style_config.get("font_sizes", {}).get("disclaimer", 8),
                color=rgba_color
            ),
            align="left",
            xanchor="left"
        )
        
        return fig 