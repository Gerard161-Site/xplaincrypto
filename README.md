# XplainCrypto - Advanced Cryptocurrency Research Platform

XplainCrypto is a powerful platform that produces comprehensive, factual, and real-time research reports on any cryptocurrency or blockchain project.

## 🚀 Key Features

- **Hierarchical Research System** - Breaks down research queries into strategic and tactical questions for in-depth exploration
- **Specialized Research Agents** - Domain-specific agents focus on technical aspects, tokenomics, market analysis, and ecosystem mapping
- **Real-Time Data Integration** - Up-to-date market data from CoinGecko, CoinMarketCap, and DeFiLlama
- **LangGraph Workflow** - Advanced state management and orchestration of the research process
- **Comprehensive Reports** - Detailed analysis with specific facts, figures, and technical details
- **Customizable Reports** - Configurable report structure and content via report_structure.json
- **Dynamic Visualizations** - Automated generation of charts and tables based on research data

## 🏗️ Architecture

The system implements a modular, service-based architecture:

1. **Core Layer** - Application initialization, configuration and server setup
2. **Service Layer** - Shared services for progress tracking, error handling and communication 
3. **Orchestration Layer** - Workflow management and coordination
4. **Agent Layer** - Specialized AI agents for different tasks
5. **Retrieval Layer** - API integration and data gathering components

This architecture provides clear separation of concerns, improved error handling, standardized progress tracking, and flexible configuration options.

## 📝 Report Structure

Each report includes customizable sections defined in the report configuration:

- Executive Summary
- Introduction and background
- Technical features and capabilities
- Tokenomics and economic model
- Price and Market Analysis
- Governance structure
- Risks and Opportunities
- Team Assessment
- Partnerships and Ecosystem
- SWOT Analysis
- Conclusion and References

## 🎨 Visualization System

The platform includes a modular visualization system with specialized visualizers for each chart type:

- **Base Visualizer**: Common interface and utility functions for all visualizers
- **Line Chart Visualizer**: Price trends, volume analysis, TVL trends
- **Bar Chart Visualizer**: Rankings and competitor comparisons
- **Pie Chart Visualizer**: Token distribution and allocation breakdowns
- **Table Visualizer**: Key metrics and structured data presentations
- **Timeline Visualizer**: Development roadmaps and project milestones

The system automatically selects the appropriate visualizer based on the chart type in the report configuration. Each visualization includes an AI-generated description explaining key insights from the data.

## 🛠️ Customization

Reports can be customized through the report_structure.json file:

- Define report sections and their order
- Specify which visualizations appear in each section
- Configure data sources for different sections
- Customize visualization styles and formats
- Define description templates for automated text generation

## 🔧 Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables:
   - `OPENAI_API_KEY` - Required for LLM operations
   - `TAVILY_API_KEY` - Required for web search
   - `COINMARKETCAP_API_KEY` - Optional for additional market data
4. Customize `backend/config/report_structure.json` (optional)
5. Run the server: `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload`

## 📊 Using the System


The platform can be accessed through:

1. **Web UI** - Available at http://localhost:3000 when running locally
2. **REST API** - Endpoints documented in the API reference
3. **Programmatic Access** - Import and use the research modules directly

## 🔬 Research Methodology

The system employs a hierarchical approach similar to GPT-Researcher, but with specialized domain agents and real-time data integration:

1. **Strategic Questions** - High-level research areas specific to cryptocurrency analysis
2. **Tactical Questions** - Specific sub-topics that explore details within each strategic area
3. **Multi-Source Verification** - Cross-references information across multiple sources
4. **Real-Time Data** - Integrates live market data alongside research findings
5. **Visualization Analysis** - Automated generation of insights from data visualizations

## 🌟 Future Development

- Expanded API integrations for on-chain data
- Support for automated updating of research reports
- Comparative analysis between multiple projects
- Integration with trading signals and market indicators
- Additional visualization types and interactive elements

## Project Structure

```
xplaincrypto/
├── backend/              # FastAPI server
│   ├── agents/           # AI agents for different tasks
│   │   ├── researcher.py
│   │   ├── visualizer.py
│   │   ├── writer.py
│   │   ├── editor.py
│   │   ├── reviewer.py
│   │   └── publisher.py
│   ├── api/              # FastAPI endpoints
│   │   └── mcp_api.py
│   ├── cli/              # Command-line interface tools
│   │   └── manage_mcp.py
│   ├── config/           # Configuration files
│   │   ├── app_config.json
│   │   ├── report_config.json
│   │   ├── style_config.json
│   │   ├── error_categories.json
│   │   ├── mcp_servers.json
│   │   └── visualization_mapping.json
│   ├── core/             # Core application components
│   │   ├── app_factory.py
│   │   ├── config_loader.py
│   │   └── server.py
│   ├── orchestration/    # Workflow coordination
│   │   ├── workflow_manager.py
│   │   ├── mcp/            # MCP specific orchestration (client-side)
│   │   │   ├── client_manager.py
│   │   │   ├── router.py
│   │   │   └── endpoint_selector.py
│   │   │   └── initialize_endpoints.py
│   │   └── rag/            # RAG specific orchestration
│   │       ├── retriever.py
│   │       └── vector_store.py
│   ├── services/         # Shared services
│   │   ├── communication/
│   │   │   └── socket_service.py
│   │   └── reporting/
│   │       ├── progress_tracker.py
│   │       ├── error_reporter.py
│   │       └── logging_config.py
│   ├── utils/            # Utility functions
│   │   └── style_utils.py
│   ├── visualizations/   # Modular visualization components
│   │   ├── base_visualizer.py 
│   │   ├── bar_chart.py
│   │   ├── candlestick_chart.py
│   │   ├── comparison_chart.py
│   │   ├── error_chart.py
│   │   ├── line_chart.py
│   │   ├── pie_chart.py
│   │   ├── table.py
│   │   ├── timeline.py
│   │   └── visualization_factory.py
├   |── servers/          # Standalone MCP Server Implementations
│   ├── state.py          # State definitions
│   └── main.py           # Server entry point
├── frontend/             # Next.js frontend
│   ├── app/              # Main application components (Next.js 13+ app router)
│   ├── components/       # Reusable UI components
│   ├── pages/            # Next.js pages (if using pages router)
│   ├── public/           # Static assets
│   └── styles/           # CSS and styling
├── .env                  # Environment variables (TEMPLATE - DO NOT COMMIT ACTUAL KEYS)
├── .gitignore
├── docker-compose.yml
├── install_deps.sh
├── README.md             # This file
└── requirements.txt      # Main Python dependencies for backend
```

## Key Features

- **Centralized Error Handling** - Standardized error reporting, categorization, and user messaging
- **Progress Tracking** - Real-time progress updates with configurable verbosity
- **Modular API Retrievers** - Separate components for different cryptocurrency data sources
- **Workflow Management** - LangGraph workflow with error handling and metrics
- **Configurable System** - JSON configuration with environment variable overrides
- **Consistent Styling** - Centralized style configuration for reports and visualizations
- **Improved Testability** - Clear component boundaries for easier testing

## Future Roadmap

- **State Management** - Adding a dedicated state manager component
- **Caching Service** - Centralizing cache management for API responses
- **Microservices Architecture** - Gradual transition to separate services
- **Client Notification System** - Enhanced notification capabilities

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

# XplainCrypto Visualization System

This repository contains a professional cryptocurrency research report visualization system built with Plotly. The system is designed to create high-quality, consistent visualizations for cryptocurrency research reports.

## Overview

The visualization system includes:

1. **Plotly-based Visualizers**: All visualizations are built using Plotly for consistent styling and interactivity
2. **Flexible Data Loading**: Loads data from cache or state, with fallbacks for missing data
3. **Consistent Styling**: Uses a StyleManager and PlotlyStyler for unified appearance
4. **Modular Design**: Each visualization type has its own specialized class
5. **Comprehensive Coverage**: Supports all required visualization types:
   - `key_metrics_table`: Key metrics about the token in table format
   - `tokenomics_pie_chart`: Token distribution visualization
   - `chain_distribution_chart`: Distribution of TVL across chains
   - `candlestick_chart`: Price chart with OHLCV data
   - `volume_chart`: Trading volume visualization
   - `competitor_comparison_chart`: Comparison with competitor tokens
   - `liquidity_trends_chart`: Liquidity over time
   - `adoption_metrics_table`: Adoption metrics in table format
   - `tvl_milestone_chart`: TVL milestones chart
   - `tvl_phases_chart`: TVL growth phases
   - `monthly_growth_chart`: Monthly growth metrics

## Files and Structure

- `backend/visualizations/`: Visualization classes
  - `plotly_visualizer.py`: Base class for all Plotly visualizers
  - `api.py`: API for creating visualizations
  - `candlestick_chart_visualizer.py`: Candlestick chart (preserved from original)
  - `chain_distribution_visualizer.py`: Chain distribution visualizer
  - `line_chart_visualizer.py`: Line chart visualizer for time series data
  - `pie_chart_visualizer.py`: Pie chart visualizer for tokenomics
  - `table_visualizer.py`: Table visualizer for metrics
- `backend/utils/`: Utility classes
  - `cache_utils.py`: Cache management utilities
  - `style_utils.py`: Style management utilities
  - `plotly_styler.py`: Plotly-specific styling utilities
- `examples/`: Example scripts
  - `generate_visualizations.py`: Example script showing how to generate all visualizations

## How to Use

```python
from backend.agents.visualizer import Visualizer

# Initialize visualizer
visualizer = Visualizer(project_name="ONDO")

# Create report config with visualization specifications
report_config = {
    "sections": [
        {
            "title": "Market",
            "visualizations": ["candlestick_chart", "volume_chart"]
        }
    ],
    "visualization_types": {
        "candlestick_chart": {
            "type": "candlestick_chart",
            "data_source": "coingecko",
            "data_field": "price"
        },
        "volume_chart": {
            "type": "volume_chart",
            "data_source": "coingecko",
            "data_field": "volume"
        }
    }
}

# Create state with the report config
state = {
    "project_name": "ONDO",
    "report_config": report_config
}

# Run the visualizer
result_state = visualizer.run(state)

# Access the visualizations
for vis in result_state.get('visualization_list', []):
    print(f"{vis['type']}: {vis['path']}")
```

## Testing

Run the example script to generate all visualizations:

```bash
python examples/generate_visualizations.py
```

This will create all 11 visualization types in the `reports/ONDO/` directory.