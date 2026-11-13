"""config_roundtrip.py — the other direction: validate GENERATED config.

Parsing: text -> schema. Generation: schema -> text. The second one is scarier,
because a plausible-looking config line that is subtly wrong gets *committed*.
So we check it the same way we checked parsing: with code, not with eyeballs.

  intent (Pydantic)  --LLM-->  SR Linux 'set' lines  --regex-->  intent again
                                                                      |
                                                 must equal the original
"""
import re
from ipaddress import IPv4Address

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "gpt-6-luna"


class BgpPeerIntent(BaseModel):
    """What we *mean*. The config is just one rendering of this."""
    peer_ip: IPv4Address
    peer_as: int = Field(ge=1, le=4294967295)
    group: str = Field(pattern=r"^[a-z0-9-]+$")


SYSTEM_PROMPT = """You write Nokia SR Linux configuration in 'set' flat syntax.
Output only 'set / ...' lines, one per line, no prose, no code fences.
Configure a BGP peer in network-instance 'default': create the group with its
peer-as, enable ipv4-unicast on the group, and attach the neighbor to the group.
Use exactly this shape:
set / network-instance default protocols bgp group <group> peer-as <asn>
set / network-instance default protocols bgp group <group> afi-safi ipv4-unicast admin-state enable
set / network-instance default protocols bgp neighbor <ip> peer-group <group>
"""

GROUP_RE = re.compile(r"^set / network-instance default protocols bgp group (\S+) peer-as (\d+)$")
NEIGHBOR_RE = re.compile(r"^set / network-instance default protocols bgp neighbor (\S+) peer-group (\S+)$")


def generate(intent: BgpPeerIntent) -> str:
    llm = ChatOpenAI(model=MODEL, reasoning_effort="none")
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Peer {intent.peer_ip} in AS {intent.peer_as}, group name '{intent.group}'."),
    ])
    return response.content.strip()


def parse_back(config: str) -> BgpPeerIntent:
    """Deterministic. No LLM. If the config doesn't say what we meant, this raises."""
    groups, neighbors = {}, {}
    for line in config.splitlines():
        if m := GROUP_RE.match(line.strip()):
            groups[m.group(1)] = int(m.group(2))
        elif m := NEIGHBOR_RE.match(line.strip()):
            neighbors[m.group(1)] = m.group(2)
    if len(neighbors) != 1:
        raise ValueError(f"expected exactly one neighbor line, found {len(neighbors)}")
    (ip, group), = neighbors.items()
    if group not in groups:
        raise ValueError(f"neighbor references group '{group}' but no peer-as line defines it")
    return BgpPeerIntent(peer_ip=ip, peer_as=groups[group], group=group)


if __name__ == "__main__":
    intent = BgpPeerIntent(peer_ip="10.1.13.2", peer_as=65002, group="ebgp-r3")
    print(f"intent:    {intent}\n")

    config = generate(intent)
    print("generated:")
    print("\n".join("  " + l for l in config.splitlines()))

    recovered = parse_back(config)
    print(f"\nrecovered: {recovered}")
    print("\nROUND-TRIP", "OK — the config says what we meant." if recovered == intent
          else f"MISMATCH — {recovered} != {intent}")
