# XplainCrypto Architecture Guide

## Directory Structure

```
XplainCrypto/
├── backend/                       # Backend API and server
│   ├── agents/                    # Agent modules
│   │   ├── enhanced_researcher.py # Main research agent with data fallback
│   │   ├── visualization_agent.py # Data visualization agent
│   │   ├── writer.py              # Report writing agent
│   │   ├── editor.py              # Report editing agent
│   │   ├── reviewer.py            # Report review agent
│   │   └── publisher.py           # Report publishing agent
│   ├── config/                    # Configuration files
│   │   ├── app_config.json        # Main application configuration
│   │   ├── report_config.json     # Customizable report configuration
│   │   ├── style_config.json      # Visual styling configuration
│   │   └── error_categories.json  # Error categorization configuration
│   ├── core/                      # Core application components
│   │   ├── app_factory.py         # Application initialization
│   │   ├── config_loader.py       # Configuration management
│   │   └── server.py              # Server setup and routes
│   ├── orchestration/             # Workflow coordination
│   │   └── workflow_manager.py    # Workflow execution and state management
│   ├── research/                  # Enhanced research system
│   │   ├── core.py                # Core research components
│   │   ├── agents.py              # Specialized research agents
│   │   └── orchestrator.py        # Research workflow orchestrator
│   ├── retriever/                 # Web retrieval and API components
│   │   ├── tavily_search.py       # Tavily API integration
│   │   ├── huggingface_search.py  # HuggingFace API integration
│   │   ├── coingecko_api.py       # CoinGecko API retriever
│   │   ├── coinmarketcap_api.py   # CoinMarketCap API retriever
│   │   ├── defillama_api.py       # DeFi Llama API retriever
│   │   └── data_gatherer.py       # Coordinates data gathering from multiple APIs
│   ├── services/                  # Shared services
│   │   ├── communication/         # Communication services
│   │   │   └── socket_service.py  # Socket.IO handling
│   │   └── reporting/             # Reporting services
│   │       ├── progress_tracker.py # Progress tracking
│   │       ├── error_reporter.py   # Error reporting
│   │       └── logging_config.py   # Centralized logging config
│   ├── utils/                     # Utility functions
│   │   └── style_utils.py         # Styling utilities for visualizations
│   ├── visualizations/            # Modular visualization components
│   │   ├── __init__.py            # Module exports
│   │   ├── base.py                # Base visualizer class
│   │   ├── line_chart.py          # Line chart visualizer
│   │   ├── bar_chart.py           # Bar chart visualizer
│   │   ├── pie_chart.py           # Pie chart visualizer
│   │   ├── table.py               # Table visualizer
│   │   └── timeline.py            # Timeline visualizer
│   ├── state.py                   # State definitions
│   └── main.py                    # Simplified entry point
├── frontend/                      # Frontend web application
├── docs/                          # Generated reports and visualizations
│   ├── cache/                     # Cached research results
│   └── project_name/              # Project-specific reports and visualizations
└── requirements.txt               # Python dependencies
```

## Component Architecture

The system is built with a modular, service-based architecture:

### Core Layer
- **Application Factory** (`app_factory.py`): Creates and configures the FastAPI application
- **Configuration Loader** (`config_loader.py`): Loads and manages configuration with environment variable overrides
- **Server Configuration** (`server.py`): Sets up server middleware, routes and request handling

### Service Layer
- **Progress Tracking Service**: Manages and reports progress of operations
- **Error Reporting Service**: Standardizes error handling and reporting
- **Socket Communication Service**: Manages real-time communication with clients
- **Logging Service**: Centralizes logging configuration and management

### Orchestration Layer
- **Workflow Manager**: Coordinates the execution of the LangGraph workflow
  - Handles LLM initialization
  - Manages agent wrappers with error handling
  - Tracks active workflows and completion status

### Agent Layer
- **Enhanced Researcher**: Entry point for the research process
- **Writer**: Converts research into narrative format
- **Visualization Agent**: Generates charts, graphs, and tables from data
- **Reviewer**: Checks report for accuracy and completeness
- **Editor**: Polishes and structures the report
- **Publisher**: Creates the final report in various formats

### Retrieval Layer
- **Web Search**: Tavily and HuggingFace for web content
- **Crypto API Retrievers**: 
  - CoinGecko API
  - CoinMarketCap API
  - DeFi Llama API
- **Data Gatherer**: Coordinates multiple data sources

### Configuration System
The application uses a layered configuration approach:
1. **Base Configuration**: Default settings in JSON files
2. **Environment Overrides**: Environment variables that override JSON settings
3. **Runtime Configuration**: Settings that can be changed during operation

Configuration files:
- `app_config.json`: Main application settings
- `report_config.json`: Report structure and content settings
- `style_config.json`: Visual styling configuration
- `error_categories.json`: Error categories and handling strategies

## System Flow Diagram

```
┌─────────────────┐                                          
│                 │                                          
│      User       │                                          
│    Interface    │                                          
│                 │                                          
└────────┬────────┘                                          
         │                                                   
         ▼                                                   
┌─────────────────┐                                          
│                 │                                          
│  App Factory    │                                          
│                 │                                          
└────────┬────────┘                                          
         │                                                   
         ▼                                                   
┌─────────────────┐     ┌────────────────┐    ┌────────────────┐
│                 │     │                │    │                │
│   FastAPI       │◄────┤ Config Loader  │◄───┤ app_config.json│
│   Server        │     │                │    │                │
│                 │     └────────────────┘    └────────────────┘
└────────┬────────┘                                          
         │                                                   
         ▼                                                   
┌─────────────────┐     ┌────────────────┐                  
│                 │     │                │                  
│  Socket Service │◄────┤ Error Reporter │                  
│                 │     │                │                  
└────────┬────────┘     └───────▲────────┘                  
         │                      │                           
         ▼                      │                           
┌─────────────────┐     ┌───────┴────────┐                  
│                 │     │                │                  
│   Workflow      │◄────┤Progress Tracker│                  
│   Manager       │     │                │                  
│                 │     └────────────────┘                  
└────────┬────────┘                                         
         │                                                   
         ▼                                                   
┌─────────────────┐                                          
│                 │                                          
│    LangGraph    │                                          
│    Workflow     │                                          
│                 │                                          
└────────┬────────┘                                          
         │                                                   
         ▼                                                   
┌─────────────────┐                                          
│                 │                                          
│    Enhanced     │                                          
│   Researcher    │                                          
│                 │                                          
└────────┬────────┘                                          
         │                                                   
         │                                                
         ▼              ┌────────────────┐     ┌────────────────┐
┌─────────────────┐     │                │     │                │
│                 │◄────┤ Data Gatherer  │◄────┤  External APIs │
│                 │     │                │     │                │
│    Research     │     └────────────────┘     └────────────────┘
│    Manager      │                                                                                           
│                 │     ┌────────────────┐     ┌────────────────┐
│                 │     │                │     │                │
│                 │◄────┤    Tavily      │◄────┤   Web Search   │
└────────┬────────┘     │                │     │                │
         │              └────────────────┘     └────────────────┘
         │                                 
         │                                                   
         ▼                                                   
┌─────────────────┐                                          
│                 │                                          
│     Writer      │                                          
│                 │                                          
└────────┬────────┘                                          
         │                                                   
         ▼                                                   
┌─────────────────┐       ┌───────────────────┐             
│                 │       │                   │             
│  Visualization  │◄──────┤   StyleManager    │             
│     Agent       │       │                   │             
│                 │       └───────────────────┘             
└────────┬────────┘                                          
         │                                                   
         ├─────────────┬────────────────┬────────────────┐ 
         │             │                │                │ 
         ▼             ▼                ▼                ▼ 
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│             │ │             │ │             │ │             │
│ LineChart   │ │ BarChart    │ │ PieChart    │ │ Table       │
│ Visualizer  │ │ Visualizer  │ │ Visualizer  │ │ Visualizer  │
│             │ │             │ │             │ │             │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │              │              │              │        
        └──────┬───────┴──────┬───────┴──────┬───────┘        
               │              │              │                
               ▼              ▼              ▼                
       ┌───────────────────────────────────────┐              
       │                                       │              
       │          Output Directory             │              
       │     (docs/project_name/*.png)         │              
       │                                       │              
       └───────────────┬───────────────────────┘              
                       │                                      
                       ▼                                      
┌─────────────────┐     ┌────────────────┐     ┌────────────────┐
│                 │     │                │     │                │
│    Reviewer     │────►│     Editor     │────►│   Publisher    │
│                 │     │                │     │                │
└─────────────────┘     └────────────────┘     └───────┬────────┘
                                                       │         
                                                       ▼         
                                               ┌────────────────┐
                                               │                │
                                               │  Final Report  │
                                               │                │
                                               └────────────────┘
```

## Modular Architecture Benefits

The current modular architecture provides several benefits:

1. **Separation of Concerns**
   - Each component has a well-defined responsibility
   - Services are decoupled, enhancing maintainability
   - Clear boundaries between layers

2. **Enhanced Error Handling**
   - Centralized error reporting with standardized categories
   - Consistent user messaging for different error types
   - Better error tracking and debugging

3. **Improved Progress Tracking**
   - Standardized progress reporting across all components
   - Real-time updates via socket service
   - Configurable verbosity levels

4. **Flexible Configuration**
   - Environment variable overrides for deployment flexibility
   - Consolidated configuration files
   - Runtime configuration adaptability

5. **Simplified Main Module**
   - Main.py reduced to a few lines of initialization code
   - Business logic moved to appropriate services
   - Better testability and component isolation

## Future Enhancements

While our current implementation provides a solid foundation, future enhancements could include:

1. **State Management**: Adding a dedicated state manager to handle state transitions more explicitly
2. **Caching Service**: Implementing a centralized caching service for API responses and research results
3. **Client Notification System**: Extracting notification logic from socket service for better separation
4. **Workflow Definition**: Separating workflow definition from workflow management

## Scalability to Microservices

This architecture is designed to facilitate a future transition to microservices:

1. **API Retrievers**: Each cryptocurrency data API retriever can be run as a separate service
2. **Socket Service**: Can be separated into a dedicated communication service
3. **Workflow Manager**: Can be evolved into a distributed workflow orchestrator
4. **Agents**: Each agent can be deployed as an independent service

The `DataGatherer` already serves as a coordinator for multiple data sources, which can be easily adapted to communicate with external services rather than in-process modules.

## Error Handling Flow

The error handling system follows this process:

1. Exception occurs in any component
2. Component reports error to ErrorReporter service
3. ErrorReporter categorizes the error and logs appropriately
4. ErrorReporter notifies subscribers (Socket Service)
5. Socket Service sends appropriate user message to client
6. Workflow continues with graceful degradation when possible

Error categories are defined in `error_categories.json` with properties:
- `severity`: critical, error, warning, info
- `retry_allowed`: whether the operation can be retried
- `user_message`: the human-readable message to display

## Progress Tracking Flow

The progress tracking system follows this process:

1. Workflow steps update progress via ProgressTracker service
2. ProgressTracker logs progress based on verbosity settings
3. ProgressTracker notifies subscribers (Socket Service)
4. Socket Service sends real-time updates to client
5. Client renders progress indicators

Each progress update includes:
- `step`: The current workflow step
- `percentage`: Completion percentage (0-100)
- `message`: Human-readable progress message

## Configuration System

The configuration system uses a layered approach:

1. Default settings from JSON configuration files
2. Environment variable overrides using the XC_ prefix
   - For example, XC_LOGGING_LEVEL=DEBUG overrides logging.level
3. Runtime configuration changes (future enhancement)

## Deployment Options

This architecture supports multiple deployment options:

1. **Monolithic Deployment**: Run as a single application (current approach)
2. **Containerized Deployment**: Each major component in its own container
3. **Serverless Deployment**: Agents as serverless functions
4. **Microservices**: Full microservice architecture with service discovery

The transition between these approaches can be gradual, starting with the extraction of API retrievers into separate services. 