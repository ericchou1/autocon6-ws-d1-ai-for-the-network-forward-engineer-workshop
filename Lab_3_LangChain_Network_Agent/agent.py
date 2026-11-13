"""agent.py — a tool-using network agent on LangChain 1.x / LangGraph.

Three things live here:
  build_agent()    — the agent, in one call to create_agent()
  ask()            — run one question and print each step as it happens
  enable_tracing() — Step 5: export every run to Arize AX (3 lines, guarded)

Lab 4 imports build_agent() and ask()'s streaming pattern for its chat UI.
"""
import os
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from bgp_tool import get_bgp_state

load_dotenv()

CLOUD_MODEL = "gpt-6-luna"
LOCAL_MODEL = "qwen3:4b-q4_K_M"

SYSTEM_PROMPT = (
    "You are a network engineering assistant. The user asks questions about a small "
    "containerlab topology with three nodes (r1, r2, r3). Use the available tools "
    "when the user asks about specific routers. For general questions ('what is BGP?') "
    "answer from your own knowledge — do not call tools when they aren't needed. "
    "Keep answers short and factual."
)


# ---------------------------------------------------------------------------
# Step 5: tracing. Three real lines (register, instrument, done), wrapped in a
# guard so the lab runs untraced if the Arize keys aren't in .env yet.
# ---------------------------------------------------------------------------
def enable_tracing(project_name: str = "autocon6-lab3"):
    space_id, api_key = os.getenv("ARIZE_SPACE_ID"), os.getenv("ARIZE_API_KEY")
    if not (space_id and api_key):
        print("[tracing] ARIZE_SPACE_ID / ARIZE_API_KEY not set in .env — running untraced\n")
        return None
    from arize.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor

    tracer_provider = register(space_id=space_id, api_key=api_key,
                               project_name=project_name, verbose=False)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    print(f"[tracing] exporting to Arize AX project '{project_name}'\n")
    return tracer_provider


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------
def make_llm(local: bool = False, effort: str = "low"):
    """One place to choose the model. GPT-6 tool calling goes through the
    Responses API; `effort` is the reasoning dial from Lab 1."""
    if local:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=LOCAL_MODEL, reasoning=False)
    return ChatOpenAI(model=CLOUD_MODEL, use_responses_api=True, reasoning={"effort": effort})


def build_agent(local: bool = False, effort: str = "low", **kwargs):
    """The whole agent. create_agent() returns a compiled LangGraph graph:
    a model node and a tool node, looping until the model stops calling tools."""
    return create_agent(make_llm(local, effort), tools=[get_bgp_state],
                        system_prompt=SYSTEM_PROMPT, **kwargs)


def ask(agent, question: str, config: dict | None = None) -> str:
    """Run one question, print each graph step as it streams, return the answer."""
    final = ""
    for update in agent.stream({"messages": [HumanMessage(content=question)]},
                               config=config, stream_mode="updates"):
        for node, payload in update.items():
            for msg in payload.get("messages", []):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for call in msg.tool_calls:
                        print(f"  [{node}] → call {call['name']}({call['args']})")
                elif isinstance(msg, ToolMessage):
                    first_line = str(msg.content).splitlines()[0]
                    print(f"  [{node}] ← {msg.name} returned: {first_line}")
                elif isinstance(msg, AIMessage):
                    final = msg.text
    return final


if __name__ == "__main__":
    tracing = enable_tracing()
    agent = build_agent(local="--local" in sys.argv)

    questions = [
        "What is BGP?",                              # General — should not call any tool
        "What's BGP looking like on r1?",            # Specific — single tool call
        "Is r3 peering with r1?",                    # Specific — needs reasoning over result
        "Compare BGP state between r1 and r3.",      # Needs data from two routers
    ]

    for q in questions:
        print(f"{'=' * 70}\nQuestion: {q}\n{'=' * 70}")
        answer = ask(agent, q)
        print(f"\nFinal answer:\n{answer}\n")

    if tracing:
        tracing.force_flush()
