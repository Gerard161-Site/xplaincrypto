# XplainCrypto - Advanced Cryptocurrency Research Platform

XplainCrypto is a powerful platform that produces comprehensive, factual, and real-time research reports on any cryptocurrency or blockchain project.

## 🚀 Key Features

- **Hierarchical Research System** - Breaks down research queries into strategic and tactical questions for in-depth exploration
- **Specialized Research Agents** - Domain-specific agents focus on technical aspects, tokenomics, market analysis, and ecosystem mapping
- **Real-Time Data Integration** - Up-to-date market data from CoinGecko, CoinMarketCap, and DeFiLlama
- **LangGraph Workflow** - Advanced state management and orchestration of the research process
- **Comprehensive Reports** - Detailed analysis with specific facts, figures, and technical details
- **Customizable Reports** - Configurable report structure and content via report_config.json
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

Reports can be customized through the report_config.json file:

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
4. Customize report_config.json (optional)
5. Run the server: `python -m uvicorn main:app --reload`

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
│   │   ├── enhanced_researcher.py # Main research agent
│   │   ├── visualization_agent.py # Data visualization agent
│   │   ├── writer.py     # Report writing agent
│   │   ├── editor.py     # Report editing agent
│   │   ├── reviewer.py   # Report review agent
│   │   └── publisher.py  # Report publishing agent
│   ├── config/           # Configuration files
│   │   ├── app_config.json # Main application configuration
│   │   ├── report_config.json # Report customization settings
│   │   ├── style_config.json # Visual styling configuration
│   │   └── error_categories.json # Error handling configuration
│   ├── core/             # Core application components
│   │   ├── app_factory.py # Application initialization
│   │   ├── config_loader.py # Configuration management
│   │   └── server.py     # Server setup and routes
│   ├── orchestration/    # Workflow coordination
│   │   └── workflow_manager.py # Manages workflow execution
│   ├── research/         # Research system components
│   │   ├── core.py       # Core research components
│   │   ├── agents.py     # Specialized research agents
│   │   └── orchestrator.py # Orchestrates research process
│   ├── retriever/        # Web & API retrieval components
│   │   ├── tavily_search.py # Web search integration
│   │   ├── huggingface_search.py # HuggingFace integration
│   │   ├── coingecko_api.py # CoinGecko API retriever
│   │   ├── coinmarketcap_api.py # CoinMarketCap API retriever
│   │   ├── defillama_api.py # DeFi Llama API retriever 
│   │   └── data_gatherer.py # Manages multiple data sources
│   ├── services/         # Shared services
│   │   ├── communication/ # Communication services
│   │   │   └── socket_service.py # Socket.IO handling
│   │   └── reporting/    # Reporting services
│   │       ├── progress_tracker.py # Progress tracking
│   │       ├── error_reporter.py # Error reporting
│   │       └── logging_config.py # Centralized logging config
│   ├── utils/            # Utility functions
│   │   └── style_utils.py # Styling utilities for visualizations
│   ├── visualizations/   # Modular visualization components
│   │   ├── base.py       # Base visualizer class
│   │   ├── line_chart.py # Line chart visualizer
│   │   ├── bar_chart.py  # Bar chart visualizer
│   │   ├── pie_chart.py  # Pie chart visualizer
│   │   ├── table.py      # Table visualizer
│   │   └── timeline.py   # Timeline visualizer
│   ├── state.py          # State definitions
│   └── main.py           # Server entry point
├── frontend/             # Next.js frontend
│   ├── pages/            # React components and pages
│   └── styles/           # CSS and styling
└── docs/                 # Generated reports and visualizations
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