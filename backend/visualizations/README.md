# XplainCrypto Visualization System

This directory contains the visualization components for the XplainCrypto platform. The system is built around Plotly for consistent, high-quality charts and visualizations in cryptocurrency research reports.

## Architecture

The visualization system follows a layered architecture:

1. **Base Layer**: `PlotlyVisualizer` - Foundational class with shared utilities for all visualizers
2. **Specialized Visualizers**: Type-specific implementations for different chart types
3. **API Layer**: `VisualizationAPI` - Entry point for creating visualizations

## Visualizer Classes

Each visualizer inherits from `PlotlyVisualizer` and specializes in a specific chart type:

- `CandlestickChartVisualizer`: Price candlestick charts
- `ChainDistributionVisualizer`: Distribution of TVL across blockchain networks
- `PieChartVisualizer`: Token distribution and allocation charts
- `TableVisualizer`: Metrics and data tables
- `LineChartVisualizer`: Time series data (price, volume, TVL)

## Data Sources

Visualizers load data from the cache directory, which contains real-time data retrieved from:

- CoinGecko: Price and market data
- CoinMarketCap: Price and exchange data
- DeFiLlama: TVL and chain distribution
- Tokenomics: Token distribution and allocation

## Usage

To create a visualization:

```python
from backend.visualizations.api import VisualizationAPI

# Initialize API
viz_api = VisualizationAPI(project_name="ONDO", theme="light")

# Define configuration
config = {
    "type": "price_chart",
    "title": "ONDO Price History",
    "data_sources": {
        "price": {
            "type": "cache",
            "path": "coingecko/price_ondo"
        }
    }
}

# Create visualization
success, path, message = viz_api.create_visualization("price_chart", config)
if success:
    print(f"Visualization created at: {path}")
else:
    print(f"Error: {message}")
```

## Configuration Options

Each visualization type accepts different configuration options:

### Common Options
- `title`: Chart title
- `output_filename`: Output filename (without extension)
- `source`: Data source attribution
- `theme`: Visual theme ('light' or 'dark')

### Chart-Specific Options
- Line charts: `x_title`, `y_title`, `series_name`
- Pie charts: (None specific)
- Tables: `note`
- Candlestick: `timeframe`, `show_volume`

## Styling

Styling is handled by the `StyleManager` and `PlotlyStyler` classes which ensure consistent appearance across all visualizations. Styles are defined in `style_config.json`.

## Data Loading

The `CacheManager` class handles data loading from the cache directory, with intelligent fallbacks if data is missing. The system will look for data in multiple places to ensure visualizations can be created even if the primary data source is unavailable.

## Extending

To add a new visualization type:

1. Create a new class inheriting from `PlotlyVisualizer`
2. Implement the `create()` method
3. Add data extraction methods
4. Register the new visualizer in `VisualizationAPI._register_visualizations()` 