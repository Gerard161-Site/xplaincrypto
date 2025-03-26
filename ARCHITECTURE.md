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
│   │   └── report_config.json     # Customizable report configuration
│   ├── research/                  # Enhanced research system
│   │   ├── core.py                # Core research components
│   │   ├── agents.py              # Specialized research agents
│   │   ├── data_modules.py        # Real-time data gathering modules
│   │   ├── orchestrator.py        # Research workflow orchestrator
│   │   └── README.md              # Research module documentation
│   ├── retriever/                 # Web retrieval components
│   │   └── tavily_search.py       # Tavily API integration
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
│   ├── state.py                   # State management
│   └── main.py                    # FastAPI server and entry point
├── frontend/                      # Frontend web application
├── docs/                          # Generated reports and visualizations
│   ├── cache/                     # Cached research results
│   └── project_name/              # Project-specific reports and visualizations
└── requirements.txt               # Python dependencies
```

## Component Architecture

The system is built with a multi-tier architecture:

### Tier 1: Web Interface (Frontend)
Provides a user-friendly interface for initiating research and displaying results.

### Tier 2: Orchestration (Backend/Main)
- **FastAPI Server**: Handles HTTP requests and WebSocket connections
- **LangGraph Workflow**: Manages the full report generation lifecycle

### Tier 3: Agent System (Backend/Agents)
- **Enhanced Researcher**: Entry point for the research process
  - **Web Research Fallback**: Populates missing web research data when web search is unavailable
  - **Cache Management**: Stores and retrieves research results to optimize performance
  - **Data Normalization**: Ensures consistent data format across sources
- **Visualization Agent**: Generates charts, graphs, and tables from data
  - **Professional Styling**: Applies consistent styling to all visualizations
  - **Markdown Processing**: Properly handles text formatting in report generation
- **Writer**: Converts research into narrative format
- **Reviewer**: Checks report for accuracy and completeness
- **Editor**: Polishes and structures the report
- **Publisher**: Creates the final report in various formats
  - **PDF Formatting**: Professional PDF layout with consistent typography and spacing

### Tier 4: Research System (Backend/Research)
- **Research Manager**: Manages research tree generation and data gathering
- **Specialized Agents**: Domain-specific agents for different research aspects
- **DataGatherer**: Collects real-time cryptocurrency data

### Tier 5: Data Sources
- **Web Search**: Using TavilySearch for web content
- **API Integration**: CoinGecko, CoinMarketCap, DeFiLlama
- **Data Processing**: Data normalization and visualization

## Report Configuration System

The `report_config.json` file serves as a central configuration system that defines:

1. **Report Structure**: The sections included in the report and their order
2. **Section Requirements**: Which sections are required vs. optional
3. **Data Sources**: The data sources to use for each section
4. **Visualizations**: Which visualizations to include in each section
5. **Visualization Types**: Configuration for each type of visualization (charts, tables, etc.)

This configuration system enables:
- Customizable reports for different use cases
- Consistent report structure across projects
- Efficient sharing of data between components
- Template-based visualization generation

## Visualization Agent

The VisualizationAgent is responsible for generating visual representations of the research data:

1. **Modular Architecture**: Coordinates specialized visualizer classes for each chart type:
   - **BaseVisualizer**: Defines the common interface and utility functions
   - **LineChartVisualizer**: Creates time-series visualizations
   - **BarChartVisualizer**: Handles categorical data comparisons
   - **PieChartVisualizer**: Shows proportional distributions
   - **TableVisualizer**: Presents structured tabular data
   - **TimelineVisualizer**: Displays chronological events and milestones

2. **Data Flow**: The visualization agent:
   - Maps visualization type to the appropriate visualizer class
   - Extracts and prepares data from multiple sources (API, web research)
   - Passes data to the specialized visualizer
   - Generates AI descriptions for each visualization
   - Stores the visualization files and metadata

3. **Professional Styling**: Applies consistent styling via a centralized StyleManager
   - Typography: Consistent font usage with Times Roman for readability
   - Color schemes: Coordinated color palettes for visual consistency
   - Spacing: Optimized spacing between chart elements for readability
   - Formatting: Proper handling of numeric data with appropriate units
   - Bold text: Special emphasis on key metrics via proper Markdown processing
   - PDF formatting: Professional PDF layout with page numbering

Supported visualization types:
- **Line Charts**: Price history, volume, TVL trends with shaded areas and marker points
- **Bar Charts**: Competitive comparisons, performance metrics with data labels
- **Pie Charts**: Token distribution, allocation breakdowns with highlighted segments
- **Tables**: Key metrics, tokenomics details, performance data with alternating row colors
- **Timelines**: Development roadmaps, milestone tracking with connecting lines

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
┌─────────────────┐     ┌────────────────┐                  
│                 │     │                │                  
│     FastAPI     │◄────┤ report_config  │                  
│     Server      │     │     .json      │                  
│                 │     │                │                  
└────────┬────────┘     └────────────────┘                  
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

## Data Flow

The end-to-end flow of data through the system follows these steps:

1. **Input Processing**
   - User submits a project name through the frontend User Interface
   - FastAPI server receives the request and initializes the workflow
   - Server loads the report_config.json for configuration parameters
   - The LangGraph Workflow is created and the initial state is initialized
   - The initial state is created with the project name and passed to the Enhanced Researcher

2. **Research Planning**
   - Enhanced Researcher agent loads the report_config.json
   - Invokes the Research Manager with the configuration
   - Research Manager generates a hierarchical research tree based on configured sections
   - Research types are determined from section titles in the configuration

3. **Data Gathering**
   - Data sources are extracted from the report configuration
   - DataGatherer fetches real-time data from configured APIs
   - Cache is checked for recent data to reduce API calls
   - Data is organized and stored in the state object
   - Price, token, and market data are structured for later use

4. **Research Execution**
   - Research Manager coordinates the research process
   - Specialized agents conduct research for each node in the tree
   - Research Manager makes Tavily Search API calls for web research with the following process:
     - Query generation based on research context
     - Parallel search execution for efficiency
     - Result filtering and relevance scoring
     - Content extraction and summarization
     - Source tracking and citation management
   - References are collected and deduplicated
   - Research data is structured for visualization

5. **Data Fallback Mechanisms**
   - Research Manager checks if web research data is available
   - If missing, populate_web_research_data function provides fallback data for:
     - Governance metrics (governance_model, proposal_count, voting_participation)
     - Partnerships (partner_name, partnership_type, partnership_date)
     - Risks (risk_type, risk_description, risk_level)
     - Opportunities (opportunity_type, opportunity_description, potential_impact)
     - Team metrics (team_size, notable_members, development_activity)
     - Key takeaways (aspect, assessment, recommendation)
   - This ensures all visualization tables can be generated even without web search

6. **Report Writing**
   - Writer agent receives complete research data from Research Manager
   - Synthesizes research into narrative form
   - Creates structured content based on the report configuration
   - Adds metadata for effective visualization integration

7. **Visualization Generation**
   - Visualization Agent receives the fully prepared research state with complete data
   - Reads visualization types from the report configuration
   - For each visualization type:
     - Determines the appropriate visualizer class (LineChart, BarChart, PieChart, etc.)
     - Extracts and prepares data from relevant sources (API data, web research)
     - Delegates visualization creation to the specialized visualizer
     - Applies consistent styling via the StyleManager
   - Each specialized visualizer:
     - Processes data specific to its chart type
     - Creates the visualization using matplotlib:
       - Sets up figure with appropriate dimensions
       - Plots the data with proper formatting
       - Adds labels, titles, and styling elements
       - Saves the figure as a PNG file to the project's output directory (docs/project_name/visualization_type.png)
       - Verifies the file was successfully saved and has appropriate content
     - Returns metadata about the visualization to the agent, including the file path
   - Visualization Agent uses the LLM to generate descriptive text for each visualization
   - Stores visualization file paths and metadata in the state for use by the Publisher agent
   - If image creation fails, detailed error information is logged and reported back to the agent

8. **Report Finalization**
   - Reviewer checks content for accuracy and completeness
   - Editor structures the content according to the report configuration
   - Publisher creates the final PDF report with:
     - Enhanced typography using Times Roman font family
     - Proper paragraph spacing for improved readability
     - Professional title page with project details
     - Table of contents section for easy navigation
     - Consistent page numbering format
     - Bold formatting for emphasis on key metrics
     - Alternating row colors in tables for readability
   - Incorporates visualizations from the Visualization Agent

9. **Output Delivery**
   - Final report is stored in the docs directory
   - Result is sent back to the frontend for display
   - Visualizations are embedded in the report

## State Management

The system uses two state models:

1. **Global ResearchState** (backend/state.py):
   - Tracks the overall progress
   - Holds visualizations and references
   - Stores the final report
   - Contains data from various sources
   - Holds the report configuration

2. **Research-specific ResearchState** (research/orchestrator.py):
   - Manages the internal research workflow
   - Contains the research tree structure
   - Tracks completion status of research steps
   - Holds intermediate research results

State properties include:
- **project_name**: Target of the research
- **research_summary**: Consolidated research findings
- **tokenomics**: Structured token economic data
- **price_analysis**: Market performance data
- **visualizations**: Generated charts and tables
- **research_data**: Structured research information
- **report_config**: Configuration for the report
- **progress**: Status updates for tracking

## Component Integration

### Configuration Flow
The report_config.json file is loaded and used by multiple components:

1. **ResearchManager**: Uses the config to determine research types and data sources
2. **VisualizationAgent**: Uses the config to determine which visualizations to generate
3. **Publisher**: Uses the config to structure the final report

### Data Sharing
Data is efficiently shared between components:

1. **DataGatherer → ResearchManager → Enhanced Researcher**: API data flows through
2. **ResearchManager → VisualizationAgent**: Research data is passed for visualization
3. **VisualizationAgent → Publisher**: Visualizations are incorporated into the final report

### Configuration-Based Customization
The system allows for customization at multiple levels:

1. **Report Sections**: Define which sections to include
2. **Data Sources**: Specify which data sources to use
3. **Visualization Types**: Choose which visualizations to generate
4. **Description Templates**: Customize automatic text generation

## API Integration

The system integrates with external APIs for real-time data:

1. **CoinGecko**: Price, market cap, and supply information
2. **CoinMarketCap**: Alternative market metrics
3. **DeFiLlama**: Total Value Locked (TVL) and protocol data
4. **Tavily**: Web search for comprehensive research

## Extensibility

The architecture is designed for easy extension:

1. **New Agents**: Add specialized agents for specific research tasks
2. **New Visualizations**: Define new visualization types in the configuration
3. **New Data Sources**: Integrate additional APIs by adding new data modules
4. **Custom Report Formats**: Support additional output formats beyond PDF 

## Resilience and Fault Tolerance

The system includes multiple mechanisms to ensure robustness and handle failures gracefully:

1. **Data Source Redundancy**:
   - Multiple API sources (CoinGecko, CoinMarketCap, DeFiLlama) provide redundancy
   - If one data source fails, others can fill in missing information

2. **Web Research Fallback**:
   - When web search is unavailable or returns no results, synthetic data is provided
   - The populate_web_research_data function ensures all visualizations can be generated
   - This prevents critical report sections from being empty or incomplete

3. **Caching System**:
   - Research results are cached to disk with timestamps
   - Reports can be generated even when external APIs are temporarily unavailable
   - Cache TTL (Time To Live) ensures data freshness while balancing API usage

4. **Error Handling**:
   - Graceful degradation when components fail
   - Detailed logging of errors for debugging
   - Fallback to default values when data is incomplete

5. **Visualization Robustness**:
   - Charts and tables adapt to available data
   - Consistent styling even with different data sources
   - Automatic handling of missing or invalid data points

These features ensure that the system can produce complete, high-quality reports even under suboptimal conditions or when certain data sources are unavailable. 