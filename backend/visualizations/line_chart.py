# visualizations/line_chart.py
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import plotly.graph_objects as go
from backend.services.reporting.error_reporter import ErrorReporter
from backend.utils.cache_utils import CacheManager
from .base_visualizer import BaseVisualizer

class LineChartVisualizer(BaseVisualizer):
    """
    Visualizer for line charts displaying time series data, e.g., TVL history.
    Adheres to XplainCrypto workspace rules: no synthetic data, transparent error handling.
    """
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the line chart visualizer."""
        super().__init__(project_name, style_manager, logger)
        self.error_reporter = ErrorReporter(logger)
        self.cache_manager = CacheManager(project_name, logger=logger)
        self.logger.info("LINE_CHART_PY_VERSION_2025_05_12")  # Unique marker

    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a line chart visualization for TVL or other time series data.
        """
        try:
            self.logger.info(f"Creating line chart visualization: {viz_type}")
            data_source = viz_config.get("data_source", "defillama")
            data_field = viz_config.get("data_field", "tvl_history")
            source_label = viz_config.get("source", "DeFiLlama")

            # Try standardized data from visualization_data
            time_series_data = None
            if data.get("series"):
                self.logger.info("Using standardized visualization_data")
                time_series_data = data["series"][0]["data"] if data["series"] else None
            else:
                # Fallback to raw state.data
                time_series_data = self._extract_data_source(data, data_source, data_field)
            
            if not time_series_data and data.get("data_unavailable"):
                self.logger.warning(f"No data available for {data_source}.{data_field}: {data.get('message', 'Unknown error')}")
                return self._create_unavailable_chart(viz_config, viz_config.get("fallback_options", {}).get("message", "Data Unavailable"))

            # Fall back to cache if no data in state
            if not time_series_data and data_source in ["defillama", "coinmarketcap"]:
                self.logger.info(f"No {data_field} data in state, checking cache")
                cache_data = self.cache_manager.load(
                    source=data_source,
                    endpoint=data_field,
                    query=f"{data_field}_{self.project_name.lower()}",
                    check_freshness=True
                )
                if cache_data and data_field in cache_data:
                    time_series_data = cache_data[data_field]
                    source_label = f"{source_label} (Cache)"
                    self.logger.info(f"Loaded {data_field} data from cache")

            # Log data for debugging
            if time_series_data:
                self.logger.debug(f"{data_field} data type: {type(time_series_data)}, length: {len(time_series_data) if isinstance(time_series_data, list) else 'N/A'}")
                self.logger.debug(f"First 5 items: {time_series_data[:5] if isinstance(time_series_data, list) else time_series_data}")

            # Prepare data
            df = self._prepare_timeseries_data(time_series_data)
            if df is None or df.empty:
                self.logger.warning(f"No valid time series data for {data_source}.{data_field}")
                return self._create_unavailable_chart(viz_config, viz_config.get("fallback_options", {}).get("message", "Data Unavailable"))

            # Create figure
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df["value"],
                    mode="lines",
                    name=viz_config.get("line_name", "TVL"),
                    line=dict(
                        color=self.colors.get("primary", "#3366cc"),
                        width=self.visualization_config.get("line_chart", {}).get("line_width", 2)
                    ),
                    connectgaps=False
                )
            )

            # Update layout
            title = viz_config.get("title", f"{self.project_name} {viz_type.replace('_', ' ').title()}")
            fig.update_layout(
                title=dict(
                    text=title,
                    x=0.5,
                    xanchor="center",
                    font=dict(
                        family=self.style_manager.get_font_family(),
                        size=self.style_manager.get_font_size("title"),
                        color=self.colors.get("text", "#333333")
                    )
                ),
                xaxis_title=viz_config.get("x_axis_title", "Date"),
                yaxis_title=viz_config.get("y_axis_title", "Value"),
                xaxis=dict(
                    tickfont=dict(
                        family=self.style_manager.get_font_family(),
                        size=self.style_manager.get_font_size("tick")
                    ),
                    gridcolor=self.colors.get("grid", "#e6e6e6")
                ),
                yaxis=dict(
                    tickfont=dict(
                        family=self.style_manager.get_font_family(),
                        size=self.style_manager.get_font_size("tick")
                    ),
                    gridcolor=self.colors.get("grid", "#e6e6e6")
                ),
                width=self.visualization_config.get("chart_sizes", {}).get("desktop", {}).get("width", 1000),
                height=self.visualization_config.get("chart_sizes", {}).get("desktop", {}).get("height", 600),
                margin=dict(
                    l=self.visualization_config.get("pdf", {}).get("margins", {}).get("left", 50) * 72,
                    r=self.visualization_config.get("pdf", {}).get("margins", {}).get("right", 50) * 72,
                    t=self.visualization_config.get("pdf", {}).get("margins", {}).get("top", 80) * 72,
                    b=self.visualization_config.get("pdf", {}).get("margins", {}).get("bottom", 50) * 72
                ),
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                showlegend=True,
                template="plotly_white"
            )

            # Add data source annotation
            fig.add_annotation(
                text=f"Source: {source_label}",
                xref="paper",
                yref="paper",
                x=0.01,
                y=-0.12,
                showarrow=False,
                font=dict(size=10, color="#808080"),
                align="left"
            )

            # Generate output path
            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Export as PNG
            fig.write_image(output_path, scale=2)
            self.logger.info(f"Line chart saved to {output_path}")
            return True, output_path, "Line chart created successfully"

        except Exception as e:
            error_msg = f"Error creating line chart: {str(e)}"
            self.logger.error(error_msg)
            error_id = self.error_reporter.report_error(
                error=e,
                category="processing_error",
                component="LineChartVisualizer.create_visualization",
                context={"viz_type": viz_type, "data_source": data_source}
            )
            return False, "", f"Error creating line chart (ID: {error_id}): {str(e)}"

    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a line chart, handling standardized and raw data.
        """
        self.logger.debug(f"Checking data usability for {viz_type}")
        if not super().check_data_usability(data, viz_type):
            self.logger.debug(f"Failed base usability check for {viz_type}")
            return False

        data_source = "defillama" if "tvl" in viz_type.lower() or "growth" in viz_type.lower() else "coinmarketcap"
        data_field = "tvl_history" if "tvl" in viz_type.lower() or "growth" in viz_type.lower() else "volume_history"
        self.logger.debug(f"Target: {data_source}.{data_field}")

        time_series_data = None
        if data.get("series"):
            # Standardized data from DataStandardizer
            self.logger.debug("Checking standardized visualization_data")
            time_series_data = data["series"][0]["data"] if data["series"] else None
        else:
            # Fallback to raw data
            time_series_data = self._extract_data_source(data, data_source, data_field)

        if not time_series_data:
            self.logger.debug(f"No data found for {data_source}.{data_field}")
            return False

        self.logger.debug(f"Data type: {type(time_series_data)}, length: {len(time_series_data) if isinstance(time_series_data, list) else 'N/A'}")
        if isinstance(time_series_data, list) and len(time_series_data) > 0:
            self.logger.debug(f"First 5 items: {time_series_data[:5]}")

        if isinstance(time_series_data, list) and len(time_series_data) > 0:
            first_item = time_series_data[0]
            if isinstance(first_item, dict):
                # Standardized format: {"x": timestamp, "y": value}
                x_key = next((key for key in ["x", "date", "timestamp"] if key in first_item), None)
                y_key = next((key for key in ["y", "tvl", "value", "price"] if key in first_item), None)
                if x_key and y_key:
                    value = first_item[y_key]
                    if value is None or pd.isna(value):
                        self.logger.debug(f"Invalid value: {value} in {first_item}")
                        return False
                    try:
                        float(value)
                        self.logger.debug(f"Valid dict format: [{x_key}: timestamp, {y_key}: value]")
                    except (ValueError, TypeError) as e:
                        self.logger.debug(f"Invalid dict value: {value}, error: {str(e)}")
                        return False
                else:
                    self.logger.debug(f"Missing keys in dict: {first_item}")
                    return False
            elif isinstance(first_item, (list, tuple)) and len(first_item) >= 2:
                # Raw format: [timestamp, value]
                try:
                    _, value = first_item[:2]
                    if value is None or pd.isna(value):
                        self.logger.debug(f"Invalid value: {value} in {first_item}")
                        return False
                    float(value)
                    self.logger.debug(f"Valid list format: [timestamp, value], length: {len(time_series_data)}")
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Invalid list value: {first_item}, error: {str(e)}")
                    return False
            else:
                self.logger.debug(f"Unsupported format: {type(first_item)}")
                return False
        else:
            self.logger.debug(f"Data is not a non-empty list: {type(time_series_data)}")
            return False

        df = self._prepare_timeseries_data(time_series_data)
        if df is None or df.empty:
            self.logger.debug(f"Failed to prepare time series data for {data_source}.{data_field}")
            return False

        self.logger.debug(f"Data usable: {len(df)} rows for {viz_type}")
        return True

    def _create_unavailable_chart(self, viz_config: Dict[str, Any], message: str) -> Tuple[bool, str, str]:
        """
        Create a chart indicating data is unavailable.
        """
        try:
            fig = go.Figure()
            fig.add_annotation(
                text=message,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(
                    family=self.style_manager.get_font_family(),
                    size=self.style_manager.get_font_size("body_text"),
                    color=self.colors.get("text", "#333333")
                )
            )
            fig.update_layout(
                title=dict(
                    text=viz_config.get("title", "Data Unavailable"),
                    x=0.5,
                    xanchor="center",
                    font=dict(
                        family=self.style_manager.get_font_family(),
                        size=self.style_manager.get_font_size("title")
                    )
                ),
                width=self.visualization_config.get("chart_sizes", {}).get("desktop", {}).get("width", 1000),
                height=self.visualization_config.get("chart_sizes", {}).get("desktop", {}).get("height", 600),
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                showlegend=False
            )
            fig.update_xaxes(visible=False)
            fig.update_yaxes(visible=False)

            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_tvl_chart")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            fig.write_image(output_path, scale=2)
            self.logger.info(f"Data unavailable chart saved to {output_path}")
            return False, output_path, message
        except Exception as e:
            error_msg = f"Error creating unavailable chart: {str(e)}"
            self.logger.error(error_msg)
            error_id = self.error_reporter.report_error(
                error=e,
                category="processing_error",
                component="LineChartVisualizer._create_unavailable_chart",
                context={"message": message}
            )
            return False, "", f"Error creating unavailable chart (ID: {error_id}): {str(e)}"