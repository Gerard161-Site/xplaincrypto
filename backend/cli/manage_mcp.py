import argparse
import json
import shutil
from pathlib import Path

def install_server(server_name: str, path: str):
    """
    Install an MCP server by copying its script and metadata file to servers/.

    Args:
        server_name: The name of the server (e.g., "coinmarketcap")
        path: Path to the MCP server directory (e.g., "coinmarketcap-mcp")
    """
    # Validate the path
    server_dir = Path(path)
    if not server_dir.exists() or not server_dir.is_dir():
        print(f"Error: Path {path} does not exist or is not a directory")
        return

    # Check for server script and metadata file
    server_script = server_dir / f"{server_name}_mcp.py"
    metadata_file = server_dir / f"{server_name}.json"
    if not server_script.exists():
        print(f"Error: Server script {server_script} not found")
        return
    if not metadata_file.exists():
        print(f"Error: Metadata file {metadata_file} not found")
        return

    # Copy files to servers/
    servers_dir = Path("servers")
    servers_dir.mkdir(exist_ok=True)
    dest_script = servers_dir / f"{server_name}_mcp.py"
    dest_metadata = servers_dir / f"{server_name}.json"
    shutil.copy(server_script, dest_script)
    shutil.copy(metadata_file, dest_metadata)
    print(f"Copied {server_script} to {dest_script}")
    print(f"Copied {metadata_file} to {dest_metadata}")

    # Update mcp_servers.json
    mcp_servers_file = Path("config/mcp_servers.json")
    servers = []
    if mcp_servers_file.exists():
        with open(mcp_servers_file, "r") as f:
            servers = json.load(f)
    servers.append({
        "server_name": server_name,
        "command": f"python servers/{server_name}_mcp.py",
        "metadata_file": f"servers/{server_name}.json"
    })
    with open(mcp_servers_file, "w") as f:
        json.dump(servers, f, indent=2)
    print(f"Installed {server_name}")

def uninstall_server(server_name: str):
    """
    Uninstall an MCP server by removing its files from servers/ and updating mcp_servers.json.

    Args:
        server_name: The name of the server to uninstall (e.g., "coinmarketcap")
    """
    mcp_servers_file = Path("config/mcp_servers.json")
    if not mcp_servers_file.exists():
        print(f"No servers installed")
        return
    with open(mcp_servers_file, "r") as f:
        servers = json.load(f)
    servers = [s for s in servers if s["server_name"] != server_name]
    with open(mcp_servers_file, "w") as f:
        json.dump(servers, f, indent=2)

    # Remove files from servers/
    server_script = Path(f"servers/{server_name}_mcp.py")
    metadata_file = Path(f"servers/{server_name}.json")
    if server_script.exists():
        server_script.unlink()
        print(f"Removed {server_script}")
    if metadata_file.exists():
        metadata_file.unlink()
        print(f"Removed {metadata_file}")
    print(f"Uninstalled {server_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage MCP servers for XplainCrypto")
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--server-name", required=True, help="Name of the MCP server")
    parser.add_argument("--path", help="Path to the MCP server directory (required for install)")
    args = parser.parse_args()

    if args.action == "install":
        if not args.path:
            parser.error("The --path argument is required for install action")
        install_server(args.server_name, args.path)
    elif args.action == "uninstall":
        uninstall_server(args.server_name)