"""bgp_tool.py — the agent's first tool: fetch and parse BGP state for a node.

The parsing is Lab 2's parse_bgp_neighbors(), imported, not re-declared.
The tool's job is the thin layer around it: pick the right capture, run the
parser, and flatten the validated objects into text the agent can read.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# Lab 2 is a sibling folder; put it on the import path so this file stays
# self-contained (no shared package to install).
LAB2 = Path(__file__).resolve().parent.parent / "Lab_2_Structured_Network_Data"
sys.path.insert(0, str(LAB2))
from parse_bgp import GOLDEN, make_llm as make_parser_llm, parse_bgp_neighbors  # noqa: E402

# Where captures live. live_data/ is empty until Lab 3 Step 6 fills it from
# the running topology; until then the tool falls back to Lab 2's golden set.
LIVE_DATA = Path(__file__).parent / "live_data"
NODES = ("r1", "r2", "r3")

# One parser model for the lifetime of the process (cloud, reasoning off —
# it's extraction, not reasoning).
_parser_llm = make_parser_llm()


def _load_capture(node: str) -> tuple[str, str]:
    """Return (raw_output, source_label), preferring a live capture."""
    live = LIVE_DATA / f"{node}_bgp.txt"
    if live.exists():
        return live.read_text(), "live capture"
    return (GOLDEN / f"{node}_bgp.txt").read_text(), "golden capture"


@tool
def get_bgp_state(node: str) -> str:
    """Get the BGP peering state for one router in the lab topology.

    Use this tool when the user asks about BGP neighbors, peering status,
    session state, uptime or prefix counts on a specific router. Call it
    once per router you need data for. Do not use it for general questions
    about what BGP is.

    Args:
        node: Router name. One of 'r1', 'r2', 'r3'.

    Returns:
        A text summary with one line per BGP neighbor: peer IP, peer AS,
        peer group, session state, uptime in seconds, and the
        received/active/sent prefix counts.
    """
    node = node.strip().lower()
    if node not in NODES:
        return f"Unknown node '{node}'. Available nodes: {', '.join(NODES)}."

    raw, source = _load_capture(node)
    result = parse_bgp_neighbors(raw, llm=_parser_llm, max_attempts=2)

    lines = [f"BGP neighbors on {node} ({source}, {len(result.neighbors)} session(s)):"]
    for n in result.neighbors:
        uptime = f"{n.uptime_seconds}s" if n.uptime_seconds is not None else "-"
        prefixes = (f"{n.prefixes_received}/{n.prefixes_active}/{n.prefixes_sent}"
                    if n.prefixes_received is not None else "-")
        lines.append(f"  - peer {n.peer_ip}  AS{n.peer_as}  group={n.group}  "
                     f"state={n.state}  uptime={uptime}  rx/active/tx={prefixes}")
    if not result.neighbors:
        lines.append("  (no BGP neighbors configured)")
    return "\n".join(lines)


# Quick standalone test
if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "r1"
    print(get_bgp_state.invoke({"node": target}))
