"""bgp_server.py — minimal MCP server exposing the workshop's BGP captures."""
from pathlib import Path
from mcp.server.mcpserver import MCPServer

# mcp 2.x: the server class is MCPServer (it was FastMCP in 1.x).
mcp = MCPServer("network-tools")

# Same data the Lab 3 tool reads: live captures if Lab 3 Step 6 made them,
# otherwise Lab 2's golden set.
ROOT = Path(__file__).resolve().parent.parent.parent
LIVE_DATA = ROOT / "Lab_3_LangChain_Network_Agent" / "live_data"
GOLDEN = ROOT / "Lab_2_Structured_Network_Data" / "golden"


@mcp.tool()
def get_bgp_state(node: str) -> str:
    """Get the BGP peering state for a node in the topology.

    Args:
        node: Node name. One of: 'r1', 'r2', 'r3'.

    Returns:
        Raw show-command output for the node's BGP neighbors.
    """
    node = node.strip().lower()
    for folder in (LIVE_DATA, GOLDEN):
        f = folder / f"{node}_bgp.txt"
        if f.exists():
            return f.read_text()
    return f"No BGP data for '{node}'. Available nodes: r1, r2, r3."


if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport
