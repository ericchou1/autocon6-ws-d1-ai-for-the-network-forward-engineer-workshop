"""consistency_check.py — put three devices in one prompt, ask a cross-device question.

Single-device parsing is table stakes. The interesting questions span devices:
"do these three configs agree with each other?" That needs all of them in the
context window at once — which is the point of this exercise.

Usage:
  python consistency_check.py            # healthy trio
  python consistency_check.py --broken   # r3 is missing its eBGP neighbor
  python consistency_check.py --full     # the FULL running configs (~680 lines each)
"""
import argparse
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "gpt-6-luna"
GOLDEN = Path(__file__).parent / "golden"


class Finding(BaseModel):
    severity: Literal["ok", "warning", "error"]
    devices: list[str] = Field(description="Which devices are involved, e.g. ['r1', 'r3']")
    summary: str = Field(description="One sentence. Quote the exact config lines or IPs involved.")


class ConsistencyReport(BaseModel):
    bgp_sessions_expected: int = Field(description="How many BGP sessions the configs, taken together, intend to form")
    findings: list[Finding]


# The *intent* of the network. Without this, the model has to guess which links
# are internal and which are external — and it will guess wrong (try deleting
# the "Design intent" paragraph and re-running the healthy trio).
SYSTEM_PROMPT = """You are reviewing the running configurations of three routers.

Design intent:
- r1 and r2 are in AS 65001. They share an internal link (10.1.12.0/30) that
  runs OSPF area 0 (their loopbacks are passive OSPF interfaces), and an iBGP
  session between loopbacks (10.0.0.1, 10.0.0.2).
- r3 is an external router in AS 65002, connected to r1 over 10.1.13.0/30 with
  an eBGP session. r3 does NOT run OSPF; the r1-r3 link is not internal.

Check that the three configs are mutually consistent with that intent: every
BGP neighbor statement on one device must have a matching statement on the
peer (correct IP on the shared subnet, each side's peer-as equal to the other
side's autonomous-system), OSPF enabled on both ends of the r1-r2 link and nowhere else except passive loopbacks,
and link addresses pairwise on the same /30. Report what is consistent as 'ok'
findings and anything missing or mismatched as 'error'. Be specific: name
devices and quote lines."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broken", action="store_true", help="use r3's degraded config (neighbor line missing)")
    ap.add_argument("--full", action="store_true", help="use the full ~680-line running configs")
    ap.add_argument("--effort", default="none", help="reasoning_effort: none/low/medium/high")
    args = ap.parse_args()

    suffix = "running" if args.full else "routing"
    files = {
        "r1": GOLDEN / f"r1_{suffix}.cfg",
        "r2": GOLDEN / f"r2_{suffix}.cfg",
        "r3": GOLDEN / (f"r3_routing_degraded.cfg" if args.broken and not args.full else f"r3_{suffix}.cfg"),
    }
    blocks = []
    total_lines = 0
    for name, path in files.items():
        text = path.read_text()
        total_lines += len(text.splitlines())
        blocks.append(f"===== {name} =====\n{text}")
    prompt = "\n\n".join(blocks) + "\n\nAre these three configurations mutually consistent?"

    llm = ChatOpenAI(model=MODEL, reasoning_effort=args.effort)
    print(f"Sending {total_lines} config lines from 3 devices (effort={args.effort}) ...")
    # Ask for the structured report, but also grab token usage from a raw call
    # so you can see what three configs cost in context.
    raw = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt + " Answer briefly.")])
    usage = raw.usage_metadata or {}
    print(f"Context used: {usage.get('input_tokens')} input tokens "
          f"(the local model's window is 40,960)\n")

    report = llm.with_structured_output(ConsistencyReport).invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )
    print(f"BGP sessions the configs intend to form: {report.bgp_sessions_expected}\n")
    for f in report.findings:
        flag = {"ok": "  ok   ", "warning": " WARN  ", "error": " ERROR "}[f.severity]
        print(f"[{flag}] {'+'.join(f.devices):<8} {f.summary}")


if __name__ == "__main__":
    main()
