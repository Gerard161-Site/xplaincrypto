# XplainCrypto MCP Setup Guide

This document provides a detailed overview of the Microservices Communication Protocol (MCP) setup in the XplainCrypto project. It covers the installation of MCP servers, starting them, and how all related files interact. This guide is designed to help developers understand the system and debug issues effectively.

## Overview

The MCP setup in XplainCrypto allows the application to interact with external data sources (e.g., CoinMarketCap, DeFiLlama, Tavily, HuggingFace) via dedicated server scripts. These servers are managed as background processes by the FastAPI application, providing tools and data retrieval capabilities for cryptocurrency research.

### Key Components

-   **MCP Server Scripts**: Individual Python scripts (e.g., `coinmarketcap_mcp.py`, `defillama_mcp.py`) located in `backend/servers/`. Each script runs a server that provides specific tools or data (e.g., price data, protocol metrics).
-   **MCP Configuration (`mcp_servers.json`)**: A JSON file in `backend/config/` that lists all MCP servers, their startup commands, and metadata files.
-   **MCP Management Script (`manage_mcp.py`)**: A CLI script in `backend/cli/` for installing and uninstalling MCP servers, including dependency installation.
-   **MCP Client Manager (`client_manager.py`)**: A Python module in `backend/orchestration/mcp/` that starts, manages, and interacts with MCP servers during application runtime.
-   **FastAPI Application (`main.py`, `routes.py`)**: The main application that integrates MCP servers via `client_manager.py` and exposes endpoints (e.g., `/api/tools`, `/api/execute-tool`).

## Directory Structure

```
xplaincrypto/
├── backend/
│   ├── servers/                # Directory for installed MCP server scripts and metadata
│   │   ├── coinmarketcap_mcp.py
│   │   ├── coinmarketcap.json
│   │   ├── defillama_mcp.py
│   │   ├── defillama.json
│   │   ├── tavily_mcp.py
│   │   ├── tavily.json
│   │   ├── huggingface_mcp.py
│   │   └── huggingface.json
│   ├── config/
│   │   └── mcp_servers.json    # Configuration listing all MCP servers
│   ├── cli/
│   │   └── manage_mcp.py       # Script for installing/uninstalling MCP servers
│   ├── orchestration/
│   │   └── mcp/
│   │       ├── client_manager.py # Manages MCP server processes
│   │       ├── endpoint_selector.py
│   │       └── initialize_endpoints.py
│   ├── api/
│   │   ├── main.py             # FastAPI application entry point
│   │   ├── routes.py           # API routes (including MCP interaction)
│   │   └── models.py
```

## MCP Server Installation

### 1. Prepare MCP Server Directories

Each MCP server (e.g., `coinmarketcap`, `defillama`) should have its own source directory, typically located as a sibling to the `backend` directory (e.g., `xplaincrypto/coinmarketcap-mcp/`). These directories must contain:
-   The server script (e.g., `coinmarketcap_mcp.py`).
-   A metadata JSON file (e.g., `coinmarketcap.json`) describing the server's tools and endpoints.
-   A `requirements.txt` file listing its Python dependencies (e.g., `requests`, `aiohttp`).

**Example: `coinmarketcap-mcp/requirements.txt`**
```text
requests==2.31.0
aiohttp==3.9.5
```

### 2. Install MCP Servers Using `manage_mcp.py`

The `manage_mcp.py` script installs MCP servers by:
1.  Validating the necessary files in the source directory.
2.  Installing dependencies from the server's `requirements.txt`.
3.  Copying the server script and metadata file to `backend/servers/`.
4.  Updating `backend/config/mcp_servers.json` with the server's information.

**Command to Install a Server**:
```bash
cd /Users/gkavanagh/Development/xplaincrypto/backend/cli
python manage_mcp.py install --server-name coinmarketcap --path ../../coinmarketcap-mcp
```
*(Note: Adjust `--path` relative to the `backend/cli` directory. `../../coinmarketcap-mcp` assumes `coinmarketcap-mcp` is at the project root, sibling to `backend`)*

**What Happens**:
-   **Validate Files**: Checks for `coinmarketcap_mcp.py` and `coinmarketcap.json` in the source path.
-   **Install Dependencies**: If `requirements.txt` exists, runs `pip install -r requirements.txt`.
-   **Copy Files**: Copies `coinmarketcap_mcp.py` and `coinmarketcap.json` to `backend/servers/`.
-   **Update `mcp_servers.json`**: Adds an entry to `backend/config/mcp_servers.json`:
    ```json
    {
      "server_name": "coinmarketcap",
      "command": "python backend/servers/coinmarketcap_mcp.py",
      "metadata_file": "backend/servers/coinmarketcap.json"
    }
    ```

**Repeat for Other Servers**:
```bash
python manage_mcp.py install --server-name defillama --path ../../defillama-mcp
python manage_mcp.py install --server-name tavily --path ../../tavily-mcp
python manage_mcp.py install --server-name huggingface --path ../../huggingface-mcp
```

### 3. Uninstalling MCP Servers
To remove a server:
```bash
cd /Users/gkavanagh/Development/xplaincrypto/backend/cli
python manage_mcp.py uninstall --server-name coinmarketcap
```
**What Happens**:
-   Removes the server's entry from `mcp_servers.json`.
-   Deletes `coinmarketcap_mcp.py` and `coinmarketcap.json` from `backend/servers/`.

## Starting MCP Servers

### 1. Overview

MCP servers are started automatically as background processes when the FastAPI application launches. This is managed by `client_manager.py`.

### 2. Files Involved

-   `backend/config/mcp_servers.json`: Contains the list of servers, their startup commands, and metadata files.
-   `backend/orchestration/mcp/client_manager.py`: Starts, manages, and monitors MCP server processes.
-   `backend/api/main.py` and `backend/api/routes.py`: The FastAPI application entry point and API routes, which initialize `client_manager.py` via `WorkflowManager`.

### 3. Startup Process

**FastAPI Startup (`main.py` via `routes.py`)**:
```python
# In backend/api/routes.py (simplified)
@router.on_event("startup")
async def startup_event():
    logger.info("Starting application initialization")
    logger.info("Initializing workflow manager")
    await workflow_manager.initialize()
    logger.info("Application initialization complete")
```
The `WorkflowManager` (in `backend/orchestration/workflow_manager.py`) in turn calls `client_manager.initialize()`.

**`client_manager.py` Initialization**:
-   Loads `mcp_servers.json` to get the list of servers.
-   For each server, calls `start_server` to launch it as a background process and monitor its initial output.

**Updated `start_server` method in `client_manager.py` (conceptual representation)**:
```python
async def start_server(self, server_name: str):
    # ... (command and path resolution logic) ...
    cmd = f"python {resolved_script_path}"
    self.logger.info(f"Starting MCP server for {server_name} with command={cmd}, PYTHONPATH={python_path}")

    # Start the server process in the background
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": python_path}
    )

    # Store the process immediately
    self.processes[server_name] = process

    # Wait briefly to check if the process starts successfully and capture initial output
    try:
        # Wait for up to 5 seconds to see if the process exits
        await asyncio.sleep(5) # Check status after a short delay
        if process.returncode is not None:
            # Process exited, capture output and handle the failure
            stdout, stderr = await process.communicate()
            self.logger.error(f"Server {server_name} failed to start: exit code {process.returncode}")
            self.logger.error(f"STDOUT: {stdout.decode() if stdout else 'No output'}")
            self.logger.error(f"STDERR: {stderr.decode() if stderr else 'No output'}")
            del self.processes[server_name] # Remove failed process
            raise RuntimeError(f"Failed to start MCP server for {server_name}")
        else:
            # Process is still running, capture any initial output for debugging
            try:
                stdout_data, stderr_data = await asyncio.gather(
                    process.stdout.read(1024),  # Read up to 1KB of initial stdout
                    process.stderr.read(1024)   # Read up to 1KB of initial stderr
                )
                if stdout_data:
                    self.logger.info(f"Initial STDOUT from {server_name}: {stdout_data.decode().strip()}")
                if stderr_data:
                    self.logger.warning(f"Initial STDERR from {server_name}: {stderr_data.decode().strip()}")
            except Exception as e:
                self.logger.warning(f"Error capturing initial output from {server_name}: {str(e)}")
            self.logger.info(f"Server {server_name} started successfully and is running in the background")
    except asyncio.TimeoutError: # This catch might not be directly in start_server based on your snippet, but represents the idea of assuming success if running after a delay.
        # If the process is still running after the check period, assume it's started successfully
        self.logger.info(f"Server {server_name} appears to be running after initial check (timeout occurred)")
    # Simplified: Original logic might not have TimeoutError here if sleep is awaited directly
    # The core idea is: start, store, wait a bit, check status, log output.
```
-   The `client_manager.py` starts each server and monitors its initial status to catch early failures.

**Server Scripts (e.g., `coinmarketcap_mcp.py`)**:
-   Each script runs as a standalone server (e.g., using a simple HTTP server, or just stdio-based communication if designed that way).
-   It should listen for requests or commands, typically managed via the `mcp-sdk` or a similar mechanism if interacting beyond simple process start/stop.

### 4. Interacting with MCP Servers

**`client_manager.py` Methods**:
-   `get_tools`: Retrieves available tools from MCP servers (currently simulated in the provided `client_manager.py`).
-   `execute_tool`: Executes a specific tool on an MCP server (currently simulated).

**`routes.py` Endpoints**:
-   `/api/tools`: Calls `client_manager.get_tools()` to list available tools.
-   `/api/execute-tool`: Calls `client_manager.execute_tool()` to run a tool.

## Debugging MCP Server Issues

### 1. Test MCP Servers Individually

To isolate issues, run each server script manually from the project root:
```bash
cd /Users/gkavanagh/Development/xplaincrypto
PYTHONPATH=$(pwd) python backend/servers/coinmarketcap_mcp.py
```
Repeat for `defillama_mcp.py`, `tavily_mcp.py`, and `huggingface_mcp.py`.

**Common Issues and Fixes**:

-   **Missing Dependency**:
    ```text
    ModuleNotFoundError: No module named 'requests'
    ```
    Solution: Update the server's `requirements.txt` (e.g., `coinmarketcap-mcp/requirements.txt`) to include `requests`, then reinstall the server using `manage_mcp.py`:
    ```bash
    echo "requests==2.31.0" >> ../../coinmarketcap-mcp/requirements.txt # Adjust path if not in backend/cli
    # then from backend/cli:
    python manage_mcp.py uninstall --server-name coinmarketcap
    python manage_mcp.py install --server-name coinmarketcap --path ../../coinmarketcap-mcp
    ```

-   **Syntax Error**:
    ```text
    SyntaxError: f-string: unmatched '('
    ```
    Solution: Open the script (e.g., `backend/servers/coinmarketcap_mcp.py`) and fix the syntax error.

-   **Missing Environment Variable**:
    ```text
    KeyError: 'COINMARKETCAP_API_KEY'
    ```
    Solution: Set the required environment variable in your shell or `.env` file:
    ```bash
    export COINMARKETCAP_API_KEY="your-api-key-here"
    ```

### 2. Check Logs During Startup

When starting the FastAPI application, `client_manager.py` logs initial output from each server. Check these logs for errors:
```text
INFO: Initial STDOUT from coinmarketcap: Starting CoinMarketCap MCP server...
WARNING: Initial STDERR from coinmarketcap: (any errors during startup)
ERROR: Server coinmarketcap failed to start: exit code 1
```

### 3. Verify File Paths

Ensure paths in `backend/config/mcp_servers.json` are correct:
-   `command`: Should be like `python backend/servers/coinmarketcap_mcp.py`.
-   `metadata_file`: Should be like `backend/servers/coinmarketcap.json`.

### 4. Debugging Tips

-   **Add Logging to Server Scripts**: Add detailed `print` or `logging` statements at the very beginning of each MCP server script (e.g., `backend/servers/coinmarketcap_mcp.py`) to confirm it's being executed and to trace its initialization.
-   **Check Permissions**: Ensure server scripts are executable (though `python script.py` usually doesn't require `+x`).
-   **Monitor Processes**: Use `ps aux | grep python` (or `pgrep -af python` on some systems) to confirm MCP server processes are running after application startup. Look for your specific script names.

## File Interactions Summary

1.  **`manage_mcp.py` (CLI Tool)**
    -   **Inputs**: MCP server source directories (e.g., `../../coinmarketcap-mcp/`).
    -   **Outputs**: Copies files to `backend/servers/`. Updates `backend/config/mcp_servers.json`.
    -   **Interactions**: Reads/writes `mcp_servers.json`. Uses `pip` to install dependencies from `requirements.txt`.

2.  **`backend/config/mcp_servers.json` (Configuration File)**
    -   **Role**: Lists all configured MCP servers, their commands, and metadata paths.
    -   **Read By**: `client_manager.py` (to know which servers to start).
    -   **Written By**: `manage_mcp.py` (during server installation/uninstallation).

3.  **`backend/orchestration/mcp/client_manager.py` (Process Manager)**
    -   **Inputs**: `mcp_servers.json`.
    -   **Outputs**: Starts MCP server scripts as background processes. Logs their startup status and initial output.
    -   **Interactions**: Executes server scripts (e.g., `backend/servers/coinmarketcap_mcp.py`) using `asyncio.create_subprocess_shell`. Provides `get_tools` and `execute_tool` methods for `routes.py`.

4.  **`backend/api/main.py` and `backend/api/routes.py` (FastAPI Application)**
    -   **Role**: FastAPI application entry point and API routes.
    -   **Interactions**: `main.py` (via `routes.py`'s startup event) initializes `WorkflowManager`, which in turn initializes `client_manager.py`. `routes.py` exposes endpoints (`/api/tools`, `/api/execute-tool`) that interact with `client_manager.py`.

5.  **MCP Server Scripts (e.g., `backend/servers/coinmarketcap_mcp.py`)**
    -   **Role**: Run as standalone servers providing specific data/tools.
    -   **Interactions**: Started by `client_manager.py`. Designed to respond to requests (e.g., via an SDK or other IPC mechanism if applicable, though current `client_manager.py` simulates direct tool calls).

## Example Workflow

1.  **Install MCP Servers**:
    ```bash
    cd /Users/gkavanagh/Development/xplaincrypto/backend/cli
    python manage_mcp.py install --server-name coinmarketcap --path ../../coinmarketcap-mcp
    # Installs dependencies, copies files, updates mcp_servers.json.
    ```

2.  **Test Individual MCP Server (Optional but Recommended)**:
    ```bash
    cd /Users/gkavanagh/Development/xplaincrypto
    PYTHONPATH=$(pwd) python backend/servers/coinmarketcap_mcp.py
    ```

3.  **Start FastAPI Application**:
    ```bash
    cd /Users/gkavanagh/Development/xplaincrypto
    python -m uvicorn backend.api.main:app --reload
    ```
    *(Monitor console output for MCP server startup logs from `client_manager.py`)*

4.  **Test Endpoints**:
    ```bash
    curl http://localhost:8000/api/tools
    # Example, if a real tool named 'get_coin_price_data' was implemented and discoverable:
    # curl -X POST http://localhost:8000/api/execute-tool -H "Content-Type: application/json" -d '{"tool_name": "coinmarketcap_tool.get_coin_price_data", "arguments": {"coin": "bitcoin"}}'
    ```

## Troubleshooting Common Issues

-   **Server Fails to Start**:
    -   Check the FastAPI application console logs for `STDOUT` and `STDERR` output from `client_manager.py` related to the failing server.
    -   Test the server individually (see step 2 above) to isolate the issue.
-   **Missing Dependencies**:
    -   Ensure the server's source directory (e.g., `../../coinmarketcap-mcp/`) has an accurate `requirements.txt`.
    -   Reinstall the server using `manage_mcp.py` to trigger dependency installation.
-   **Environment Variables Not Set**:
    -   If a server script relies on environment variables (e.g., `COINMARKETCAP_API_KEY`), ensure they are set in your shell environment or a `.env` file loaded by your application/scripts.
-   **Application Hanging or Unresponsive**:
    -   This could indicate an issue in `client_manager.py`'s process management or a problem with an MCP server not starting/responding correctly.
    -   Check logs for any indication of which server might be causing trouble.
    -   Ensure all servers start successfully by checking the startup logs.

This guide provides a comprehensive overview of the MCP setup in XplainCrypto, designed to aid in development, debugging, and maintenance.