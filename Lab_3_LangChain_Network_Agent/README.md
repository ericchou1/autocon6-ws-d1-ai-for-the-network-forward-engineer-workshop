# Lab 3: A Tool-Using Agent with LangChain and LangGraph

**Time:** ~40 minutes

Build an agent that answers natural-language questions about your network by calling a tool you define — Lab 2's parser, wrapped. The agent decides whether to call the tool, which router to ask about, whether it needs data from more than one router, and how to turn the results into an answer. Then you'll open the agent up and see that it's a small graph, trace a run end to end on an observability platform, and point it at live routers.

By the end you'll be able to type:

```
Compare BGP state between r1 and r3.
```

…and watch the agent call the tool twice, read both results, and write the comparison — with every step visible in your terminal and, from Step 5 on, in a trace waterfall in Arize AX.

## Prerequisites

- Labs 1 & 2 completed. Lab 3 imports `parse_bgp_neighbors` from Lab 2 and reads Lab 2's `golden/` captures.
- Familiarity with Python decorators (we use `@tool`) and type hints.
- For Step 5: `ARIZE_SPACE_ID` and `ARIZE_API_KEY` filled in `.env` (from the pre-workshop FAQ). If they're blank the lab still runs, just untraced.

## Concepts

- **Agent vs. plain LLM call.** A plain call is one round-trip. An agent is a *loop*: model decides → tool runs → model sees the result → decides again → eventually answers.
- **A tool is a function with a good docstring.** `@tool` turns the signature and docstring into the description the model reads. The docstring is the prompt.
- **The agent is a graph.** In LangChain 1.x, `create_agent()` returns a LangGraph graph: a model node, a tool node, one conditional edge. You'll build the same thing by hand in Step 4 so nothing about it is magic.
- **Tracing is the first eval instrument.** From Step 5, every run is exported as a trace: which tool, with what arguments, how many tokens, how long. Lab 5 builds evaluation on top of exactly these traces.
- **Canned first, live second.** Steps 1–5 read captured output so the agent code works regardless of whether the routers are up. Step 6 brings them up and the same agent reads live state.

---

## Step 1: The tool

> **Heads up — this file is already in the repo.** `bgp_tool.py` is here in this lab folder. Open it and follow along.

The tool is a thin wrapper around Lab 2's parser. The parts that matter:

```python
from langchain_core.tools import tool

# Lab 2 is a sibling folder; put it on the import path so this file stays
# self-contained (no shared package to install).
LAB2 = Path(__file__).resolve().parent.parent / "Lab_2_Structured_Network_Data"
sys.path.insert(0, str(LAB2))
from parse_bgp import GOLDEN, make_llm as make_parser_llm, parse_bgp_neighbors

# Where captures live. live_data/ is empty until Lab 3 Step 6 fills it from
# the running topology; until then the tool falls back to Lab 2's golden set.
LIVE_DATA = Path(__file__).parent / "live_data"
NODES = ("r1", "r2", "r3")

_parser_llm = make_parser_llm()


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
        ...
    return "\n".join(lines)
```

Three things to notice:

- **Nothing about BGP parsing lives here.** The schema, the validation, the retry loop — all imported from Lab 2. The tool is ten lines of "which file, run the parser, format the result." That's the right split: Lab 2 owns correctness, Lab 3 owns the interface to the agent.
- **The docstring is the prompt.** "Use this tool when the user asks about BGP neighbors…", "Call it once per router you need data for", "Do not use it for general questions" — every sentence steers a decision the agent will make in Step 3. The `Args:` block is how it learns that `node` must be `r1`, `r2` or `r3`. Vague docstring, confused agent.
- **It returns a string, not a `BgpNeighborList`.** The validated object exists inside the tool. What crosses back to the agent is plain text, because that's what the model reads best. Internal rigor, external simplicity.

Run it standalone:

```bash
python Lab_3_LangChain_Network_Agent/bgp_tool.py r1
python Lab_3_LangChain_Network_Agent/bgp_tool.py r9
```

**Expected:**
```
BGP neighbors on r1 (golden capture, 2 session(s)):
  - peer 10.0.0.2  AS65001  group=ibgp-65001  state=established  uptime=69s  rx/active/tx=6/1/10
  - peer 10.1.13.2  AS65002  group=ebgp-r3  state=established  uptime=51s  rx/active/tx=3/3/8
Unknown node 'r9'. Available nodes: r1, r2, r3.
```

Note `(golden capture, …)` — the tool tells you where its data came from. In Step 6 that will say `live capture`. And note the second run: a tool that returns a clear error string is far better than one that raises, because the agent can read the error and recover (ask the user, try another node) instead of crashing.

---

## Step 2: The agent in one call

> **Heads up — this file is already in the repo, and it's the finished version** with all four Step 3 questions. Read along with the snippets here; the challenge version is to delete it and rebuild it from them.

Here's the whole agent:

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from bgp_tool import get_bgp_state

CLOUD_MODEL = "gpt-6-luna"

SYSTEM_PROMPT = (
    "You are a network engineering assistant. The user asks questions about a small "
    "containerlab topology with three nodes (r1, r2, r3). Use the available tools "
    "when the user asks about specific routers. For general questions ('what is BGP?') "
    "answer from your own knowledge — do not call tools when they aren't needed. "
    "Keep answers short and factual."
)


def make_llm(local: bool = False, effort: str = "low"):
    return ChatOpenAI(model=CLOUD_MODEL, use_responses_api=True, reasoning={"effort": effort})


def build_agent(local: bool = False, effort: str = "low", **kwargs):
    return create_agent(make_llm(local, effort), tools=[get_bgp_state],
                        system_prompt=SYSTEM_PROMPT, **kwargs)
```

That's it. `create_agent(model, tools, system_prompt)` returns a runnable agent. Two details in `make_llm()` are deliberate:

- **`use_responses_api=True`.** GPT-6 models do tool calling through OpenAI's Responses API. Over the older Chat Completions API they only call tools with reasoning fully off. Switching the flag is how you keep Lab 1's reasoning dial *and* tools.
- **`reasoning={"effort": "low"}`.** The dial, set low. Deciding "which tool, which node" is not a hard problem; paying for `high` on every agent turn adds latency and cost for nothing. Going Further #5 lets you measure that.

Now the part that makes the loop visible. The `ask()` helper streams the graph's updates and prints each one:

```python
def ask(agent, question: str, config: dict | None = None) -> str:
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
```

`stream_mode="updates"` yields one item per graph node that ran, keyed by the node's name. An `AIMessage` with `tool_calls` means the model decided to act. A `ToolMessage` is the tool's result coming back. A plain `AIMessage` is the final answer. You're watching the loop turn.

Run it:

```bash
python Lab_3_LangChain_Network_Agent/agent.py
```

**Expected** (the first of four questions; the rest are Step 3):

```
[tracing] ARIZE_SPACE_ID / ARIZE_API_KEY not set in .env — running untraced

======================================================================
Question: What is BGP?
======================================================================

Final answer:
BGP (Border Gateway Protocol) is the routing protocol that exchanges reachability
information between autonomous systems ...
```

(If your Arize keys *are* in `.env` you'll see `[tracing] exporting to Arize AX project 'autocon6-lab3'` instead — that's Step 5 already working. Carry on.)

---

## Step 3: Watch it decide

The interesting part of an agent isn't one call — it's watching it *choose*. `agent.py` runs four questions picked to exercise four different decisions:

```python
    questions = [
        "What is BGP?",                              # General — should not call any tool
        "What's BGP looking like on r1?",            # Specific — single tool call
        "Is r3 peering with r1?",                    # Specific — needs reasoning over result
        "Compare BGP state between r1 and r3.",      # Needs data from two routers
    ]
```

Look at the step lines for each:

**Question 1 — "What is BGP?"** No `→ call` line at all. The agent answered from its own knowledge. It did not get tricked into calling the tool because the word "BGP" appeared — the docstring's "Do not use it for general questions" is doing its job.

**Question 2 — "What's BGP looking like on r1?"**
```
  [model] → call get_bgp_state({'node': 'r1'})
  [tools] ← get_bgp_state returned: BGP neighbors on r1 (golden capture, 2 session(s)):
```
One call, correct argument extracted from the sentence, answer composed from the result. Took about 5 seconds, most of it the two model calls (the agent's, and the parser's inside the tool).

**Question 3 — "Is r3 peering with r1?"** The agent has to reason: either router's neighbor table answers this. Notice which one it picked (usually `r3`, the subject of the sentence) and that the answer is a direct *yes* with the evidence, not a dump of the table.

**Question 4 — "Compare BGP state between r1 and r3."**
```
  [model] → call get_bgp_state({'node': 'r1'})
  [model] → call get_bgp_state({'node': 'r3'})
  [tools] ← get_bgp_state returned: BGP neighbors on r1 (golden capture, 2 session(s)):
  [tools] ← get_bgp_state returned: BGP neighbors on r3 (golden capture, 1 session(s)):
```
Two calls — **issued in the same model turn**, then executed together by the tool node (so the two `←` lines can come back in either order), then one synthesis. Nobody told the agent "for comparisons, call the tool twice" and nobody told it the two calls were independent. It worked both out from the question. Older models did this sequentially: call, wait, call, wait. Current ones batch independent calls, which halves the wall-clock on multi-router questions.

> **Try it:** change a question to "Check the second router" and see whether the agent maps that to `r2`. Then try "How's BGP on the core?" — a name the topology doesn't have — and watch it either ask you which router you mean or try one and read the tool's error string. Both are reasonable; neither is a crash.

---

## Step 4: What `create_agent` built — the graph, explicitly

`create_agent()` is a convenience. Underneath it is a **LangGraph graph**, and you should see it once so that nothing about agents feels like magic — and so you know where you'd plug in a second tool, a memory store, or a human-approval gate.

> **Heads up — this file is already in the repo.** `graph_agent.py` is here in this lab folder.

The entire thing:

```python
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

tools = [get_bgp_state]
model = make_llm().bind_tools(tools)   # the model now knows the tool schema


# --- Node 1: call the model -------------------------------------------------
def call_model(state: MessagesState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    return {"messages": [model.invoke(messages)]}


# --- Node 2: run whatever tools the model asked for --------------------------
tool_node = ToolNode(tools)


# --- Wire it up --------------------------------------------------------------
graph = StateGraph(MessagesState)
graph.add_node("model", call_model)
graph.add_node("tools", tool_node)

graph.add_edge(START, "model")
graph.add_conditional_edges("model", tools_condition)
graph.add_edge("tools", "model")

agent = graph.compile()
```

Read it top to bottom:

- **State** is `MessagesState`: a list of messages. Every node receives the list and returns messages to append. That's the whole memory of a run.
- **`call_model`** prepends the system prompt, sends the conversation, appends the reply. The model was given the tool schema by `bind_tools()`, so its reply may contain tool calls.
- **`ToolNode`** reads tool calls off the last message, runs them, appends a `ToolMessage` per call. It's the thing that executed both calls together in Step 3.
- **`tools_condition`** is the agent loop in one line. It looks at the model's last message: tool calls present → route to `"tools"`; none → `END`. The edge from `tools` back to `model` closes the cycle.

Run it:

```bash
python Lab_3_LangChain_Network_Agent/graph_agent.py
```

**Expected:** first a Mermaid diagram of the graph (paste it into [mermaid.live](https://mermaid.live) if you want to see it drawn):

```
graph TD;
	__start__([<p>__start__</p>]):::first
	model(model)
	tools(tools<hr/><small><em>__tools = get_bgp_state</em></small>)
	__end__([<p>__end__</p>]):::last
	__start__ --> model;
	model -.-> __end__;
	model -.-> tools;
	tools --> model;
```

…then the compare question with **the same step lines Step 3 produced** — `[model] → call` twice, `[tools] ←` twice, same shape of answer. Hand-built graph, convenience function: identical behavior, because they're the same graph.

**Why this is worth ten minutes of a forty-minute lab:** every extension you'll want is a node or an edge in this picture. A second tool is another entry in `tools`. Conversation memory is a *checkpointer* on `compile()`. A human-approval gate before anything runs on a router is `interrupt_before=["tools"]`. Going Further #3 and #4 do exactly those two, and Lab 4's config generator is the approval gate with a UI on it. You can only reason about those additions if you've seen the graph they're added to.

---

## Step 5: Tracing debuts

You've been reading the agent's steps off a terminal. That works for one agent, one question, one person watching. It doesn't work for an agent your team uses all day, or for answering "why did it say *that* last Tuesday?" For that you need every run recorded, structured, and searchable. That's tracing, and it's three lines.

Open `agent.py` and look at `enable_tracing()`:

```python
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
```

The three real lines are `register(...)`, `LangChainInstrumentor().instrument(...)`, and that's two — the third is the `force_flush()` at the end of `__main__` that makes sure the last spans leave before the process exits. Everything else is the guard.

- **`register()`** creates an OpenTelemetry tracer that ships spans to Arize's collector, authenticated with your Space ID and API key, grouped under a project name.
- **`LangChainInstrumentor`** hooks LangChain and LangGraph so that every model call, tool call and graph step emits a span automatically. You don't annotate anything. Lab 2's parser is LangChain code too, so its model call inside the tool gets traced as well — nested under the tool's span, where it belongs.

Open `.env` and confirm `ARIZE_SPACE_ID` and `ARIZE_API_KEY` have values (both come from **Space Settings** in [app.arize.com](https://app.arize.com); the FAQ walks through it). Then re-run:

```bash
python Lab_3_LangChain_Network_Agent/agent.py
```

**Expected:** the first line is now `[tracing] exporting to Arize AX project 'autocon6-lab3'`, and the four questions run exactly as before. Tracing is invisible from the terminal — that's the point.

Now go look. In Arize: **Projects → autocon6-lab3 → Traces**. You should see four traces, one per question. Open the *Compare BGP state* one. You're looking at a **waterfall**: a root span for the whole agent run; under it, the model call that decided to use the tool; under that, two tool spans running side by side; under each tool span, the parser's own model call; then the final model call that wrote the comparison. Click any model span to see the exact prompt it was sent, the exact response, token counts in and out, and latency.

**What to notice**

1. **Every question costs more than one model call.** The compare question is three agent-level model calls plus two parser calls. That's five LLM round-trips you'd never have counted from the terminal. The token totals on the root span are what you'd be billed.
2. **The tool's inputs and outputs are recorded.** When the agent gives a wrong answer next week, you'll be able to see whether the tool returned bad data or the model misread good data. That distinction is the whole debugging game, and it's exactly what Lab 2's structural-versus-correctness split was about.
3. **Nothing in the agent changed.** Three lines at startup, zero in the logic.

Lab 4 adds the same three lines to the Streamlit app. Lab 5 opens by reading what lands here.

> **If the project doesn't appear** after a minute: check for a typo in the two `.env` values (the API key is long; make sure the whole thing pasted), and check the terminal for a connection error from `register()`. Spans are batched and sent in the background, so a script that exits very quickly can lose them — `force_flush()` is there to prevent that; if you write your own script, call it.

---

## Step 6: Now with real routers

Everything so far read captured output. Same agent, same tool — now against routers running in your Codespace.

### Deploy the topology

```bash
cd /workspaces/autocon6-ws-d1-ai-for-the-network-forward-engineer-workshop
containerlab deploy -t clab/topology.clab.yml
```

**Expected:** after 30–60 seconds, a table with `clab-autocon6-r1`, `r2`, `r3` all `running`.

### Let BGP converge, and check r3

The routers boot in parallel but not in lockstep. The internal iBGP session (r1↔r2) comes up first; the eBGP session to r3 typically takes another **10–20 seconds** after that. Check from r1:

```bash
docker exec clab-autocon6-r1 sr_cli "show network-instance default protocols bgp neighbor"
```

**Expected:** two neighbors. `10.0.0.2` (r2, iBGP) `established`; `10.1.13.2` (r3, eBGP) `established` — or `active`/`connect` if you're quick, in which case wait ten seconds and run it again. `active` during the first half-minute is normal convergence, not a fault.

If `10.1.13.2` is still not `established` after a minute, look at r3's side:

```bash
docker exec clab-autocon6-r3 sr_cli "show network-instance default protocols bgp neighbor"
```

It should show `10.1.13.1` (r1). If the table is **empty**, r3's startup config lost its neighbor statement — a thing SR Linux 25.10 has been seen to do on some deploys. Put it back live, and take the one-liner tour of SR Linux's commit-based CLI while you're at it:

```bash
docker exec clab-autocon6-r3 sr_cli -ec "set / network-instance default protocols bgp neighbor 10.1.13.1 peer-group ebgp-r1"
```

(`-e` enters candidate mode, `-c` commits — the same thing as typing `enter candidate` / `set …` / `commit now` interactively.) Re-check r1 after twenty seconds. Re-applying the line when it's already present is a harmless no-op, so if in doubt, run it.

> **Want to poke around interactively?** `ssh admin@clab-autocon6-r1` (password `NokiaSrl1!`) drops you into the SR Linux CLI. `docker exec … sr_cli "…"` is the same CLI, one command at a time, without the password prompt — which is why the capture step below uses it.

### Capture real BGP output

The tool prefers `live_data/` when files exist there. Fill it:

```bash
for NODE in r1 r2 r3; do
    docker exec clab-autocon6-$NODE sr_cli "show network-instance default protocols bgp neighbor" \
        > Lab_3_LangChain_Network_Agent/live_data/${NODE}_bgp.txt
done

head -12 Lab_3_LangChain_Network_Agent/live_data/r1_bgp.txt
```

**Expected:** the full nine-column table, with uptimes of a minute or two and small prefix counters — your routers, right now.

### Re-run the agent

```bash
python Lab_3_LangChain_Network_Agent/agent.py
```

**Expected:** the same four questions, and the tool's first line now reads `BGP neighbors on r1 (live capture, 2 session(s))`. The comparison answer quotes *your* uptimes. Nothing in `agent.py` or `bgp_tool.py` changed.

### Why this matters

The parser doesn't care whether its input came from a file we shipped or a `show` command you ran thirty seconds ago. The agent doesn't care that the tool is reading live state. The only thing that changed was which file the tool opened — and in Going Further #6, even that goes away and the tool runs the `show` command itself. Swapping "read a file" for "ask the router" is the entire productionisation step. Every other line stays.

Leave the topology running — Lab 4 uses it.

---

## Step 7: Provider swap — the local model drives the agent

Same move as Labs 1 and 2: change the model, keep everything else. `agent.py` already has the switch:

```bash
python Lab_3_LangChain_Network_Agent/agent.py --local
```

That uses `ChatOllama(model="qwen3:4b-q4_K_M", reasoning=False)` for the *agent's* decisions. (The parser inside the tool stays on the cloud model, so you're measuring one thing.)

**Expected:** it works. The 4B model picks the right tool, extracts `r1` correctly, reads the result and answers — at roughly **a minute and a half per question** on four CPU cores, versus five seconds. The compare question is the one to watch: see whether it issues both calls in one turn like the cloud model did (it did when we ran it), or one at a time, or asks about only one router and calls it done. All three happen with small models, and which one you get can change from run to run.

**The lesson, updated.** A year ago this step was where the local model fell over — wrong tool, wrong arguments, loops. Small models have gotten markedly better at tool use, and "local can't do agents" is no longer a safe assumption. What hasn't changed is the **latency** gap: twenty times slower is the difference between a co-pilot and a batch job. And what you can't tell from one run is *reliability* — does it get the compare question right nine times out of ten, or six? That's not a feeling you should have; it's a number you should measure. Lab 2 showed you how; Lab 5 does it at scale.

Lab 1's framework stands: the smallest model that's good enough, as close to the data as its sensitivity demands. "Good enough" for an agent now includes "fast enough to wait for," and only an eval tells you where that line is.

---

## Going Further

If you finish the core lab early:

### 1. A second tool — `get_ospf_state`

Lab 2's `golden/` already has `r1_ospf.txt` and `r2_ospf.txt`. Give the agent a tool for them. Add to `bgp_tool.py` (or a new `ospf_tool.py`):

```python
from typing import Literal
from pydantic import BaseModel, Field
from agent import make_llm


class OspfNeighbor(BaseModel):
    interface: str = Field(description="Interface-Name column")
    router_id: str = Field(description="Rtr Id column")
    state: Literal["down", "attempt", "init", "2-way", "exstart",
                   "exchange", "loading", "full"] = Field(description="State column, lowercase")
    priority: int = Field(description="Pri column")
    dead_timer_seconds: int = Field(description="Time Before Dead column")


class OspfNeighborList(BaseModel):
    neighbors: list[OspfNeighbor]


_ospf_llm = make_llm().with_structured_output(OspfNeighborList)


@tool
def get_ospf_state(node: str) -> str:
    """Get OSPF neighbor state for one router. Use for OSPF adjacency, neighbor
    or convergence questions on r1 or r2 (r3 does not run OSPF).

    Args:
        node: 'r1' or 'r2'.
    """
    f = GOLDEN / f"{node.strip().lower()}_ospf.txt"
    if not f.exists():
        return f"No OSPF data for '{node}'. OSPF runs on r1 and r2 only."
    res = _ospf_llm.invoke(f"Extract the OSPF neighbors:\n{f.read_text()}")
    return f"OSPF neighbors on {node}:\n" + "\n".join(
        f"  - {n.router_id} via {n.interface} state={n.state} pri={n.priority} "
        f"dead_in={n.dead_timer_seconds}s" for n in res.neighbors)
```

Then in `agent.py`, change `tools=[get_bgp_state]` to `tools=[get_bgp_state, get_ospf_state]` and try:

- *"How's OSPF doing on r1?"* — only the OSPF tool fires.
- *"Is r1 fully converged with r2 on both BGP and OSPF?"* — **both** tools fire, in one turn, and the answer combines them.

> **Tip:** naming both protocols explicitly is what reliably gets both tools called. "Is r1 fully converged with r2?" alone usually gets you BGP only — "converged" doesn't tell the agent OSPF is in scope. Wording steers tool choice; that's worth remembering when you write the system prompt for a real deployment.

Look at the trace in Arize afterwards: two tool spans under one model span.

### 2. A second-step tool — `diagnose_session`

The BGP tool reports *facts*. Add a tool that explains them, using Lab 2's `BGP_REFERENCE` text from `analyzer.py`:

```python
@tool
def diagnose_session(state: str) -> str:
    """Explain what a BGP session state means operationally and what to check.
    Call this AFTER get_bgp_state, for any session that is not 'established'.

    Args:
        state: the session state, e.g. 'active', 'connect', 'idle'.
    """
    ...  # look the state up in BGP_REFERENCE and return the matching line + advice
```

Now ask *"Why isn't r3 receiving routes from r1?"* against the **degraded** capture (copy `Lab_2_Structured_Network_Data/golden/r1_bgp_degraded.txt` over `live_data/r1_bgp.txt` for a moment). The agent should call `get_bgp_state('r1')`, see `active`, then call `diagnose_session('active')`, then answer. That's a genuine multi-step plan the agent made on its own, and the trace shows it as two sequential tool spans.

### 3. Memory — follow-up questions

Each `ask()` so far starts from an empty message list. LangGraph adds memory with a *checkpointer* on the graph plus a thread ID on each call:

```python
from langgraph.checkpoint.memory import InMemorySaver

agent = build_agent(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "demo"}}

print(ask(agent, "Show me BGP on r1.", config=config))
print(ask(agent, "Now the same for r2, and tell me if they share a peer group.", config=config))
```

**Expected:** the second question resolves "the same" and "they" from the first — the agent calls the tool for `r2` and compares against r1's group names it already has in the thread. Change `thread_id` and the context is gone. This is what Lab 4's chat UI needs for a multi-turn conversation; Going Further #4 there wires it in.

### 4. Human-in-the-loop — approve before the tool runs

The graph from Step 4 has an edge from `model` to `tools`. LangGraph can pause on it:

```python
agent = build_agent(checkpointer=InMemorySaver(), interrupt_before=["tools"])
config = {"configurable": {"thread_id": "approve-1"}}

agent.invoke({"messages": [HumanMessage(content="What's BGP looking like on r3?")]}, config=config)

state = agent.get_state(config)
print("paused before:", state.next)
print("pending:", [(c["name"], c["args"]) for c in state.values["messages"][-1].tool_calls])

# A human looks at that and says yes:
result = agent.invoke(None, config=config)     # resume from the checkpoint
print(result["messages"][-1].text)
```

**Expected:** `paused before: ('tools',)` and the pending call `get_bgp_state({'node': 'r3'})`, then the answer after the resume. For a read-only `show` command this is theatre. For a tool that *changes* a router it's the difference between a co-pilot and an incident. Lab 4's config generator puts a button on exactly this pause.

### 5. The reasoning dial, for agents

`build_agent(effort="none")`, `"low"`, `"high"`. Run the compare question at each and look at the three traces side by side in Arize: tokens on the root span, total latency, and whether the decisions changed at all. For routing-style decisions they rarely do — which tells you where to leave the dial for an agent that runs a thousand times a day.

### 6. Make the tool itself live

Step 6 captured files by hand. Let the tool run the `show` command instead — no file, no SSH password, since `docker exec` works from inside the Codespace:

```python
import subprocess

def fetch_bgp_live(node: str) -> str | None:
    """Run the show command on the node via docker exec; None if the node isn't up."""
    try:
        out = subprocess.run(
            ["docker", "exec", f"clab-autocon6-{node}", "sr_cli",
             "show network-instance default protocols bgp neighbor"],
            capture_output=True, text=True, timeout=20, check=True)
        return out.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
```

Then in `_load_capture()`, try `fetch_bgp_live(node)` first and fall back to the files when it returns `None`. The tool is now genuinely hybrid: live when the routers are up, canned when they aren't, and the agent never knows the difference. (Prefer SSH? `paramiko` to `admin@clab-autocon6-{node}` with password `NokiaSrl1!` does the same job; it's not in the image, `pip install paramiko` first.)

---

## What's next

In **Lab 4 (Streamlit Frontend)**, this agent gets a chat UI. `build_agent()` and the streaming pattern from `ask()` are exactly what the web app calls — and because the steps stream, the UI can show the user *which tools the agent called* while it works, not just the final answer. The three tracing lines come along too, so Lab 5 has traces from both the terminal and the UI to evaluate.
