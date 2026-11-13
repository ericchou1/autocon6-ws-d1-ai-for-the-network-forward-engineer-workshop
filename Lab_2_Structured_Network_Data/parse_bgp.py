"""parse_bgp.py — the real thing: full-width SR Linux output -> validated objects.

This file is the parser the rest of the workshop reuses (Lab 3 wraps it as a
tool). It separates two jobs that are easy to blur together:

  1. EXTRACTION  — the model turns text into JSON that matches the schema's
                   *shape*. The provider enforces the shape.
  2. VALIDATION  — Pydantic enforces the *meaning*: types, ranges, enums, and
                   cross-field rules the provider knows nothing about.

Keeping them separate is what makes retries possible: when validation fails
we still hold the raw JSON, so we can show the model exactly what it got
wrong and ask again.
"""
import json
import sys
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

load_dotenv()

CLOUD_MODEL = "gpt-6-luna"
LOCAL_MODEL = "qwen3:4b-q4_K_M"

GOLDEN = Path(__file__).parent / "golden"

BgpState = Literal["idle", "connect", "active", "opensent", "openconfirm", "established"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class BgpNeighbor(BaseModel):
    peer_ip: IPv4Address = Field(description="IP address of the BGP peer")
    group: str = Field(min_length=1, description="Peer group name")
    peer_as: int = Field(ge=1, le=4294967295, description="Peer AS number")
    state: BgpState = Field(description="BGP session state, lowercase")
    uptime_seconds: int | None = Field(
        description="The Uptime column converted to total seconds "
                    "(e.g. '0d:0h:1m:9s' -> 69). null when the column is '-'."
    )
    # The [Rx/Active/Tx] column, split into three fields. (Not a tuple:
    # OpenAI's strict-schema subset doesn't allow fixed-length arrays.)
    prefixes_received: int | None = Field(description="Rx count from [Rx/Active/Tx]; null if blank")
    prefixes_active: int | None = Field(description="Active count from [Rx/Active/Tx]; null if blank")
    prefixes_sent: int | None = Field(description="Tx count from [Rx/Active/Tx]; null if blank")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value):
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def uptime_matches_state(self):
        """A cross-field rule the provider can't enforce: only established
        sessions have an uptime."""
        if self.state == "established" and self.uptime_seconds is None:
            raise ValueError("an established session must have an uptime")
        if self.state != "established" and self.uptime_seconds is not None:
            raise ValueError(f"a session in state '{self.state}' cannot have an uptime")
        return self


class BgpNeighborList(BaseModel):
    neighbors: list[BgpNeighbor]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You extract BGP neighbor sessions from SR Linux 'show network-instance "
    "default protocols bgp neighbor' output. One object per table row. "
    "If the output is empty or has no rows, return an empty list."
)


RETRY_PROMPT = """Your previous output failed validation:

{errors}

Fix ONLY the fields named above and return the full corrected JSON.
Remember: where the table shows '-' or a blank cell, the value must be
JSON null — never 0 and never an empty string."""


def make_llm(local: bool = False):
    """Build the chat model. One place to swap providers."""
    if local:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=LOCAL_MODEL, reasoning=False)
    return ChatOpenAI(model=CLOUD_MODEL, reasoning_effort="none")


def parse_bgp_neighbors(raw_output: str, llm=None, max_attempts: int = 1) -> BgpNeighborList:
    """Parse SR Linux BGP neighbor output into a validated BgpNeighborList.

    Extraction and validation are separate steps. If validation fails and
    attempts remain, the model is shown its own JSON plus the validation
    errors and asked to correct it.
    """
    llm = llm or make_llm()
    # Pass the JSON *schema*, not the class: the provider enforces the shape
    # and hands back a plain dict. Validation is our job, below.
    extractor = llm.with_structured_output(BgpNeighborList.model_json_schema())

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=raw_output if raw_output.strip() else "(the command printed nothing)"),
    ]

    for attempt in range(1, max_attempts + 1):
        data = extractor.invoke(messages)
        try:
            return BgpNeighborList.model_validate(data)
        except ValidationError as e:
            if attempt == max_attempts:
                raise
            print(f"    attempt {attempt} failed validation "
                  f"({e.error_count()} error(s)) — retrying", file=sys.stderr)
            messages += [
                AIMessage(content=json.dumps(data)),
                HumanMessage(content=RETRY_PROMPT.format(errors=e)),
            ]


# ---------------------------------------------------------------------------
# Quick standalone run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "r1_bgp.txt"
    raw = (GOLDEN / target).read_text()
    print(f"--- {target}: {len(raw.splitlines())} lines of raw output\n")
    result = parse_bgp_neighbors(raw)
    print(f"{len(result.neighbors)} neighbor(s):")
    for n in result.neighbors:
        rx = f"[{n.prefixes_received}/{n.prefixes_active}/{n.prefixes_sent}]" if n.prefixes_received is not None else "-"
        up = f"{n.uptime_seconds}s" if n.uptime_seconds is not None else "-"
        print(f"  {n.peer_ip!s:<12} {n.group:<12} AS{n.peer_as:<6} {n.state:<12} up={up:<6} rx/act/tx={rx}")
