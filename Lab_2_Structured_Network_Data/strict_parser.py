"""strict_parser.py — tighten the contract: types, enums, ranges, validators.

Part 1 never calls an LLM. It feeds bad data straight into the schema so you
can read what a ValidationError looks like. Part 2 runs the strict schema
through the model.
"""
from ipaddress import IPv4Address
from typing import Literal
from pydantic import BaseModel, Field, ValidationError, field_validator
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-6-luna"

# The six BGP FSM states from RFC 4271. Anything else is rejected.
BgpState = Literal["idle", "connect", "active", "opensent", "openconfirm", "established"]


class BgpNeighbor(BaseModel):
    peer_ip: IPv4Address = Field(description="IP address of the BGP peer")
    group: str = Field(min_length=1, description="Peer group name")
    peer_as: int = Field(ge=1, le=4294967295, description="Peer AS number (1 to 2^32-1)")
    state: BgpState = Field(description="BGP session state, lowercase")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value):
        """Accept 'Established' / 'ESTABLISHED' from the model, store lowercase."""
        return value.lower() if isinstance(value, str) else value


class BgpNeighborList(BaseModel):
    neighbors: list[BgpNeighbor]


# ---------------------------------------------------------------------------
# Part 1: no LLM. What does the contract reject?
# ---------------------------------------------------------------------------
print("=== Part 1: validating hand-made data (no LLM) ===")

good = {"peer_ip": "10.0.0.2", "group": "ibgp-65001", "peer_as": 65001, "state": "Established"}
print("good row  ->", BgpNeighbor.model_validate(good))

bad = {"peer_ip": "10.0.0.256", "group": "", "peer_as": 0, "state": "up"}
try:
    BgpNeighbor.model_validate(bad)
except ValidationError as e:
    print(f"\nbad row   -> {e.error_count()} errors:")
    for err in e.errors():
        print(f"  {'.'.join(str(x) for x in err['loc']):<10} {err['msg']}")

# ---------------------------------------------------------------------------
# Part 2: the same strict schema, through the model
# ---------------------------------------------------------------------------
print("\n=== Part 2: strict schema through the LLM ===")

llm = ChatOpenAI(model=MODEL, reasoning_effort="none").with_structured_output(BgpNeighborList)

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

result = llm.invoke(f"Extract the BGP neighbors:\n{SAMPLE}")
for n in result.neighbors:
    print(f"  {n.peer_ip!s:<12} AS{n.peer_as:<6} {n.state:<12} ({type(n.peer_ip).__name__})")
