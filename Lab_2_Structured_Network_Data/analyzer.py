"""analyzer.py — structured output + context injection: the schema gives you
shape, the reference data gives you correctness."""
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-6-luna"

# The "retrieved" knowledge. In real RAG this would come from a vector
# store keyed off the user's question; here we inline it because the
# scope is fixed (BGP state interpretation).
BGP_REFERENCE = """
BGP session states, per RFC 4271:
- idle:        starting state, no resources allocated
- connect:     trying to complete TCP/179 connection to peer
- active:      TCP connection failed, retrying. Usually indicates the
               peer is not configured to accept this session — check
               peer-side config, not local reachability.
- opensent:    TCP up, OPEN message sent, waiting for peer's OPEN
- openconfirm: peer's OPEN accepted, waiting for KEEPALIVE
- established: session up, prefixes are being exchanged
"""


class BgpNeighbor(BaseModel):
    peer_ip: str = Field(description="IP address of the BGP peer")
    group: str = Field(description="Peer group name")
    peer_as: int = Field(description="Peer AS number")
    state: str = Field(description="BGP session state")
    diagnosis: str = Field(
        description="One-sentence explanation of what this state means "
                    "operationally, citing the reference data."
    )


class BgpNeighborList(BaseModel):
    neighbors: list[BgpNeighbor]


SYSTEM_PROMPT = f"""You are a network engineer parsing SR Linux BGP output.

Use this reference to diagnose each session:
{BGP_REFERENCE}

If you don't have enough information to diagnose, say "insufficient data" — do not guess.
"""

llm = ChatOpenAI(model=MODEL, reasoning_effort="none").with_structured_output(BgpNeighborList)

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

result = llm.invoke([
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=f"Parse and diagnose:\n{SAMPLE}"),
])

for n in result.neighbors:
    print(f"{n.peer_ip} ({n.state}, AS{n.peer_as})")
    print(f"  → {n.diagnosis}\n")
