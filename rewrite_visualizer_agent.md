Objective: Rewrite the XplainCrypto Visualizer agent to generate consistent, reliable, and professional visualizations for cryptocurrency research reports, replacing the existing flaky implementation. The visualizations must be created using Dash by Plotly for a dashboard interface and Plotly for individual charts, with the ability to export each visualization as a high-quality PNG image for PDF reports. The primary data source is the LangGraph state graph accessed via StateManager, with CacheManager as a backup. The system should build a reusable library of visualizations driven by the report_config.json file, support data from CoinMarketCap, DeFiLlama, and tokenomics sources, and be extensible for future chatbot-driven visualization requests via a dashboard.

Background:

Current Issues: The existing Visualizer agent (visualizer.py, candlestick_chart_visualizer.py, etc.) is inconsistent, producing missing charts, formatting errors (e.g., unwanted quotes in tables), and unreliable outputs. Data handling is flaky, and styling varies across charts.
Data Sources:
Primary: LangGraph state graph, accessed via StateManager. Contains data for CoinMarketCap (30-day OHLCV, market cap, volume), DeFiLlama (TVL history, chain distribution, protocol metrics), and tokenomics (distribution/allocation from whitepapers).
Backup: CacheManager, storing data in docs/<project_name>/cache (e.g., JSON files like tvl_history_<project>.json).
Requirements:
Visualizations are driven by report_config.json, specifying sections (e.g., Market Analysis, Tokenomics) and required visuals (e.g., candlestick_chart, tokenomics_pie_chart).
The Visualizer loops through report_config.json, fetches data from the state graph (via StateManager), falls back to cache (via CacheManager) if data is missing, and saves outputs as PNG images to docs/<project_name> for PDF reports.
Visualizations must be designed for a Dash dashboard (for future interactivity) but exported as PDF-optimized PNGs (high DPI, consistent styling) for immediate use in reports.
Future extensibility: A chatbot will allow users to request custom visuals via the dashboard, requiring a modular visualization library.
Existing Code: The provided files (visualizer.py, candlestick_chart.py, pie_chart_visualizer.py, etc.) show the current Plotly-based implementation, which is inconsistent. These should be replaced with a Dash-based system that supports image export.
Tasks:

Rewrite the Visualizer Agent:
Replace the current Visualizer class (visualizer.py) with a new implementation that uses Dash for dashboard-style visualization management and Plotly for individual charts.
Process report_config.json to generate all required visuals for each section, saving them as PNG images in docs/<project_name> for PDF reports.
Fetch data primarily from the LangGraph state graph using StateManager methods (get_data_sources, get_section_data, get_visualization_data_for_section).
If data is missing in the state graph, fall back to CacheManager.load() to retrieve cached data.
Implement robust error handling to prevent missing charts, logging errors (e.g., “No OHLCV data for candlestick chart”) and generating error images with messages like “Data Unavailable”.
Support both synchronous (visualizer_sync) and asynchronous (visualizer_async) execution for compatibility with the existing system.
Prepare visualizations for a Dash dashboard by creating a modular structure, but prioritize PNG export for PDF reports. The dashboard will be fully implemented later for chatbot integration.
Data Sourcing Strategy:
Primary Source: Use StateManager to extract data from the LangGraph state graph. Example methods:
StateManager.get_data_sources(state): Retrieves top-level data (e.g., coinmarketcap, defillama, tokenomics).
StateManager.get_section_data(state, section_title): Retrieves section-specific data.
StateManager.get_visualization_data_for_section(state, section_title): Retrieves pre-processed visualization data.
Backup Source: If data is missing (e.g., data.get("data_unavailable", False) or empty), use CacheManager.load(data_source, cache_key, project_name) to fetch from cache. Example cache keys:
coinmarketcap_data_<project_name>
defillama_tvl_history_<project_name>
tokenomics_distribution_<project_name>
Validation: Check data usability before visualization (adapt _check_data_usability() from existing code). Generate error images for invalid/missing data.
Logging: Log data source usage (e.g., “Fetched OHLCV from state graph” or “Fetched TVL from cache”) and update data_sources_used in the state graph via StateManager.update_field().
Build a Reusable Visualization Library:
Create a modular library of Plotly-based visualization components, each accepting a configuration dictionary (viz_config) and data from the state graph or cache.
Ensure consistency using a centralized StyleManager for themes, colors, and layouts.
Recommended Visualizations (aligned with data sources and crypto report needs):
Candlestick Chart: 30-day price history (CoinMarketCap OHLCV). Includes open, high, low, close, volume, and EMAs (20, 50).
Line Chart: TVL, volume, or price trends (DeFiLlama, CoinMarketCap). Includes moving averages (7-day, 30-day) for price charts.
Pie/Donut Chart: Tokenomics distribution (e.g., team, community, reserve) or chain distribution (tokenomics, DeFiLlama).
Table: Key metrics (price, market cap, volume, TVL) and adoption metrics (active addresses, transactions) (CoinMarketCap, DeFiLlama).
Bar Chart: TVL or volume across chains/protocols (DeFiLlama).
Area Chart: Cumulative TVL or volume growth (DeFiLlama).
Competitor Comparison Chart: Multi-line chart comparing price/volume/TVL across tokens (CoinMarketCap, DeFiLlama).
Each visualization must:
Be renderable in a Dash dashboard as a dcc.Graph component.
Be exportable as a PNG image using fig.write_image() for PDF reports.
Handle missing data gracefully (e.g., display “N/A” or an error image) and adhere to the strict no-synthetic-data policy.
Use Dash and Plotly for Dual-Purpose Visualizations:
Dash:
Use Dash to structure visualizations as components within a dashboard, ensuring they are ready for future interactive use.
Example Dash app structure (for future dashboard, with immediate image export):
python

Copy
import dash
from dash import dcc, html
import plotly.graph_objects as go
import pandas as pd
import os

class Visualizer:
    def __init__(self, project_name, state_manager, cache_manager, style_manager):
        self.app = dash.Dash(__name__)
        self.project_name = project_name
        self.state_manager = state_manager
        self.cache_manager = cache_manager
        self.style_manager = style_manager
        self.output_dir = f"docs/{project_name.lower()}"

    def create_dashboard_and_images(self, state, report_config):
        visuals = []
        for section in report_config['sections']:
            section_title = section['title']
            for viz_id in section['visualizations']:
                viz_config = report_config['visualization_types'][viz_id]
                data = self.get_data(viz_config, state)
                fig = self.create_visualization(viz_id, viz_config, data)
                # Save as PNG for PDF report
                output_path = os.path.join(self.output_dir, f"{section_title.lower()}_{viz_id}.png")
                fig.write_image(output_path, scale=2, engine='kaleido')
                # Add to dashboard layout
                visuals.append(html.Div([
                    html.H2(section_title, style=self.style_manager.get_text_style()),
                    dcc.Graph(figure=fig)
                ]))
        self.app.layout = html.Div(visuals, style=self.style_manager.get_dashboard_style())
        # Save dashboard as HTML for future use
        self.app.write_html(os.path.join(self.output_dir, 'dashboard.html'))
        return self.app

    def get_data(self, viz_config, state):
        data_source = viz_config.get('data_source')
        data_field = viz_config.get('data_field')
        data = self.state_manager.get_data_sources(state).get(data_source, {})
        if data.get('data_unavailable', False) or not data:
            data = self.cache_manager.load(data_source, data_field, self.project_name)
        return data
Export PNGs using plotly.io.write_image() with kaleido for high-quality, PDF-optimized images (300 DPI, consistent dimensions).
Plotly:
Use Plotly for individual chart rendering within Dash components.
Example visualization components:
Candlestick Chart:
python

Copy
def create_candlestick_chart(data, project_name, style_manager, theme='dark'):
    df = pd.DataFrame(data.get('coinmarketcap', {}).get('ohlcv', []))
    if df.empty or not all(col in df for col in ['date', 'open', 'high', 'low', 'close']):
        return create_error_chart("No valid OHLCV data available")
    fig = go.Figure(data=[go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color=style_manager.style_config['colors']['positive'],
        decreasing_line_color=style_manager.style_config['colors']['negative']
    )])
    fig.update_layout(
        title=f"{project_name} Price History",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        template='plotly_dark' if theme == 'dark' else 'plotly_white',
        **style_manager.get_chart_layout()
    )
    return fig
Pie Chart:
python

Copy
def create_pie_chart(data, project_name, style_manager, theme='dark'):
    distribution = data.get('tokenomics', {}).get('distribution', [])
    if not distribution:
        return create_error_chart("No distribution data available")
    labels = [item['name'] for item in distribution]
    values = [item['value'] for item in distribution]
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        textinfo='label+percent',
        hole=0.4,  # Donut chart
        marker_colors=style_manager.style_config['colors']['accent']
    )])
    fig.update_layout(
        title=f"{project_name} Token Distribution",
        template='plotly_dark' if theme == 'dark' else 'plotly_white',
        **style_manager.get_chart_layout()
    )
    return fig
Table:
python

Copy
def create_table(data, project_name, style_manager, theme='dark'):
    metrics = data.get('coinmarketcap', {})
    if not metrics:
        return create_error_chart("No metrics data available")
    table_data = [{'Metric': k, 'Value': style_manager.format_value(v, k)} for k, v in metrics.items()]
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['Metric', 'Value'],
            fill_color=style_manager.style_config['colors']['header'],
            font_color='white',
            align='left'
        ),
        cells=dict(
            values=[[row['Metric'] for row in table_data], [row['Value'] for row in table_data]],
            fill_color=style_manager.style_config['colors']['cell'],
            font_color='white',
            align='left'
        )
    )])
    fig.update_layout(
        title=f"{project_name} Key Metrics",
        template='plotly_dark' if theme == 'dark' else 'plotly_white',
        **style_manager.get_chart_layout()
    )
    return fig
Error Chart:
python

Copy
def create_error_chart(message):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#FF5252")
    )
    fig.update_layout(
        width=900, height=600,
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        template='plotly_dark'
    )
    return fig
Consistency:
Extend StyleManager to centralize styling for both dashboard and images:
python

Copy
class StyleManager:
    def __init__(self, logger=None):
        self.style_config = {
            'theme': 'dark',
            'colors': {
                'background': '#1a1a1a',
                'text': '#ffffff',
                'header': '#2c3e50',
                'cell': '#1e293b',
                'accent': ['#1e88e5', '#26a69a', '#d81b60', '#ffb300'],
                'positive': '#66bb6a',
                'negative': '#d81b60'
            },
            'font': {'family': 'Arial', 'size': 14},
            'figure': {'width': 900, 'height': 600, 'dpi': 300}
        }

    def get_dashboard_style(self):
        return {
            'backgroundColor': self.style_config['colors']['background'],
            'color': self.style_config['colors']['text'],
            'fontFamily': self.style_config['font']['family'],
            'padding': '20px'
        }

    def get_chart_layout(self):
        return {
            'width': self.style_config['figure']['width'],
            'height': self.style_config['figure']['height'],
            'font': self.style_config['font'],
            'paper_bgcolor': self.style_config['colors']['background'],
            'plot_bgcolor': self.style_config['colors']['background'],
            'margin': {'l': 50, 'r': 50, 't': 80, 'b': 50}
        }

    def format_value(self, value, key):
        if value is None or pd.isna(value):
            return "N/A"
        if 'price' in key.lower() or 'volume' in key.lower() or 'tvl' in key.lower():
            return f"${value:,.2f}" if isinstance(value, (int, float)) else str(value)
        if 'percent' in key.lower() or 'change' in key.lower():
            return f"{value:.2f}%" if isinstance(value, (int, float)) else str(value)
        return str(value)
Use Plotly templates (plotly_dark, plotly_white) and custom CSS in Dash for consistent aesthetics.
Store style settings in a style_config.json file for reusability.
Ensure PNG exports use consistent dimensions (e.g., 900x600 pixels) and high DPI (300) for PDF clarity.
Image Export:
Use plotly.io.write_image() with kaleido to export each visualization as a PNG:
python

Copy
import plotly.io as pio
fig.write_image(output_path, scale=2, engine='kaleido')
Optimize images for PDF by setting high DPI and consistent margins in StyleManager.get_chart_layout().
Error Handling:
Validate data before rendering (e.g., check for non-empty DataFrames, required columns like date, open, high, low, close for candlestick charts).
Log errors with context (e.g., “Failed to fetch OHLCV for candlestick_chart: No data in state or cache”).
Generate error images for invalid/missing data, ensuring no visualizations are skipped silently.
Integrate with Existing System:
Maintain compatibility with report_config.json structure:
json

Copy
{
  "sections": [
    {
      "title": "Market Analysis",
      "visualizations": ["candlestick_chart", "volume_chart"],
      "data_source": "coinmarketcap"
    },
    {
      "title": "Tokenomics",
      "visualizations": ["tokenomics_pie_chart"],
      "data_source": "tokenomics"
    }
  ],
  "visualization_types": {
    "candlestick_chart": {
      "type": "candlestick_chart",
      "data_source": "coinmarketcap",
      "data_field": "ohlcv",
      "title": "Price History"
    },
    "tokenomics_pie_chart": {
      "type": "pie_chart",
      "data_source": "tokenomics",
      "data_field": "distribution",
      "title": "Token Distribution"
    }
  }
}
Update the state graph with visualization paths and errors using StateManager.update_visualizations() and StateManager.add_errors().
Store PNG outputs in docs/<project_name> (e.g., docs/ondo/market_analysis_candlestick_chart.png) and HTML dashboard in docs/<project_name>/dashboard.html.
Ensure PNGs are accessible for PDF report generation and Dash dashboard is ready for future Next.js integration (e.g., via iframe or static HTML).
Future-Proof for Chatbot and Dashboard:
Design the visualization library to be queryable via a chatbot. Each component should accept a viz_config dictionary with type, data_source, data_field, title, etc.
Implement a VisualizationFactory to map visualization types to components:
python

Copy
class VisualizationFactory:
    def __init__(self, style_manager):
        self.visualizations = {
            'candlestick_chart': create_candlestick_chart,
            'pie_chart': create_pie_chart,
            'table': create_table,
            'line_chart': create_line_chart,
            'bar_chart': create_bar_chart,
            'area_chart': create_area_chart,
            'competitor_comparison_chart': create_competitor_comparison_chart
        }
        self.style_manager = style_manager

    def create(self, viz_type, data, project_name, theme='dark'):
        if viz_type not in self.visualizations:
            raise ValueError(f"Unknown visualization type: {viz_type}")
        return self.visualizations[viz_type](data, project_name, self.style_manager, theme)
Support dynamic data sources (e.g., real-time CoinGecko API calls) for chatbot requests.
Ensure the Dash dashboard can be extended to handle chatbot queries by adding a callback to render new visualizations:
python

Copy
from dash.dependencies import Input, Output

@app.callback(
    Output('visualization-container', 'children'),
    Input('chatbot-input', 'value')
)
def update_visualization(chat_input):
    viz_config = parse_chat_input(chat_input)  # Parse chatbot query to viz_config
    data = fetch_data(viz_config)  # Fetch from state or cache
    fig = VisualizationFactory(style_manager).create(viz_config['type'], data, project_name)
    return dcc.Graph(figure=fig)
Implementation Notes:

Performance: Process visualizations in batches (e.g., 3 at a time, as in existing visualizer.py) to avoid memory issues. Use Dash’s caching (dash_extensions.cache) for large datasets.
Image Quality: Ensure PNG exports are high-resolution (300 DPI) and optimized for PDF (e.g., minimal margins, clear fonts). Test with PDF viewers to confirm clarity.
Testing: Test with sample data for tokens like ONDO, Ethereum, and Solana, ensuring all visualizations render correctly from both state graph and cache, and PNGs are PDF-ready.
Debugging: Add detailed logging for data fetching, rendering, and image export. Use Dash’s debug mode (app.run_server(debug=True)) for development.
Dependencies: Install dash, plotly, pandas, and kaleido. Update requirements.txt accordingly.
Documentation: Document each visualization component, including input data format, configuration options, PNG export process, and dashboard integration.
Deliverables:

Rewritten Visualizer class integrating Dash and Plotly, with PNG export for PDF reports.
Visualization library with recommended visualizations (candlestick, line, pie, table, bar, area, competitor comparison).
Updated StyleManager with consistent styling for dashboard and images.
Integration with StateManager (primary) and CacheManager (backup).
Example Dash app generating a report dashboard and PNG images.
Unit tests for each visualization component and image export.
Documentation for the visualization library, PNG export process, and chatbot integration.
Timeline: Complete the rewrite within 2-3 weeks, with weekly progress updates. Prioritize candlestick, pie, and table visualizations for the first iteration, ensuring PNG exports are PDF-ready.

Resources:

Dash Documentation: https://dash.plotly.com/
Plotly Financial Charts: https://plotly.com/python/financial-charts/
Dash Sample Apps: https://github.com/plotly/dash-sample-apps
Kaleido for Image Export: https://plotly.com/python/static-image-export/
Existing Code: Use provided files (visualizer.py, candlestick_chart.py, etc.) as reference but replace with new Dash-based implementation.