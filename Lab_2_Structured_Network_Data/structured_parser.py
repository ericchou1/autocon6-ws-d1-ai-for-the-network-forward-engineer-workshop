"""structured_parser.py — Pydantic schemas as a contract with the LLM."""
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-6-luna"


class BgpNeighbor(BaseModel):
    """A single BGP peering session."""
    peer_ip: str = Field(description="IP address of the BGP peer")
    group: str = Field(description="Peer group name this neighbor belongs to")
    peer_as: int = Field(description="Peer's autonomous system number")
    state: str = Field(description="BGP session state (established, active, idle, etc.)")


class BgpNeighborList(BaseModel):
    """Top-level container for a list of neighbors."""
    neighbors: list[BgpNeighbor]


llm = ChatOpenAI(model=MODEL, reasoning_effort="none").with_structured_output(BgpNeighborList)

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

result = llm.invoke(f"Extract the BGP neighbors:\n{SAMPLE}")

# result is a BgpNeighborList — a real Python object, not a string
print(type(result).__name__)
for n in result.neighbors:
    print(f"  {n.peer_ip:<12} AS{n.peer_as:<6} {n.state}")
