# Lab 3 Concepts: A Tool-Using Agent with LangChain and LangGraph

> 10-15 min introduction before hands-on starts.

## The big picture

So far every LLM call has been one round-trip that *you* orchestrated: prompt in, text out, your code decides what happens next. Lab 2 made the output trustworthy. Lab 3 hands the orchestration to the model.

An **agent** is an LLM that decides its own next step: fetch data, or answer? Which data? Is one fetch enough? It makes those decisions by reading descriptions of the *tools* you've given it. That sounds like magic. It isn't — it's a loop, and you'll build it twice in forty minutes: once with a one-line helper, once by hand.

## What an agent actually is

```
                  ┌─────────────────────────────┐
                  │       User's question       │
                  └──────────────┬──────────────┘
                                 ▼
                  ┌─────────────────────────────┐
            ┌────►│  MODEL                      │
            │     │  "Which tool, if any?"      │
            │     └──────────────┬──────────────┘
            │          tool calls?│
            │        ┌── yes ─────┴──── no ──┐
            │        ▼                       ▼
            │  ┌───────────────┐    ┌─────────────────┐
            │  │  TOOLS        │    │  Final answer   │
            │  │  run them,    │    └─────────────────┘
            │  │  append results│
            │  └───────┬───────┘
            └──────────┘
```

Three things to notice:

1. **The model decides, not you.** You hand it a question and tool descriptions. It decides to call a tool (or not). The tool runs. The model sees the result and decides again.
2. **The loop can turn more than once, and a turn can hold more than one call.** "Compare r1 and r3" → the model asks for both routers in a single turn, the tool node runs both, the model writes the comparison. Current models batch independent calls; older ones went one at a time.
3. **This picture is literally the code.** In LangChain 1.x an agent *is* a LangGraph graph: a model node, a tool node, one conditional edge. Step 4 of the lab builds it from those parts in twenty lines, and it behaves identically to the one-line version. Every extension you'll ever want — a second tool, memory, a human-approval gate — is a node or an edge on this diagram.

## What "tools" really are

A tool is a Python function with a precise docstring. `@tool` reads the signature and docstring and describes the function to the model as part of its instructions. The model sees roughly:

> *"You have `get_bgp_state(node: str) -> str`. Use this tool when the user asks about BGP neighbors, peering status, session state, uptime or prefix counts on a specific router. Call it once per router you need data for. Do not use it for general questions about what BGP is. `node` is one of 'r1', 'r2', 'r3'."*

Every clause in that docstring steers a decision you'll watch the agent make. *"Do not use it for general questions"* is why "What is BGP?" doesn't trigger a call. *"Once per router"* is why the compare question triggers two. *"One of 'r1', 'r2', 'r3'"* is how "check the second router" becomes `node='r2'`.

**Writing docstrings is the highest-leverage agent engineering you'll do.** The second-highest is what the tool returns: plain, well-labelled text the model can read, with a clear error string when something's wrong rather than an exception. Internal rigor (Lab 2's validated objects live inside the tool), external simplicity.

## Tracing: the agent's flight recorder

Reading steps off a terminal works for one person, one question. It doesn't work for an agent your team uses all day, and it can't answer "why did it say *that* last Tuesday?"

Tracing records every run as a tree of spans: the agent run, each model call under it, each tool call, each tool's own model call nested where it belongs — with the exact prompts, responses, token counts and timings attached. Three lines turn it on; nothing in the agent changes. From Step 5 onward every run of this workshop's agent lands in Arize AX, and that's the raw material Lab 5 evaluates.

Two habits start here. First, **look at the trace, not the terminal, when an answer is wrong** — it tells you whether the tool returned bad data or the model misread good data, which is Lab 2's structural-versus-correctness split showing up again. Second, **count the model calls.** "One question" was five LLM round-trips in Step 5. You'd never have known from the terminal.

## Canned first, live second

Steps 1–5 run against captured output. Step 6 brings the routers up and the same agent reads live state. The only thing that changes is which file the tool opens — and Going Further #6 removes even that, having the tool run the `show` command itself. That's the productionisation step, and it's one function. Everything above it stays.

## On small models and tool calling

A year ago this lab's "swap to the local model" step was where things fell apart: wrong tool, wrong arguments, loops. Small models have gotten markedly better at tool use, and the 4B model you'll run in Step 7 gets the right answer. What it doesn't get is *fast* — about a minute and a half per question versus five seconds — and what you can't tell from one run is how *reliably* it gets the compare question right.

That's the workshop's framework again with two words added: the smallest model that's good enough, *fast enough*, as close to your data as its sensitivity demands. "Good enough" for an agent is a reliability number, and Lab 2 showed you how to get one.

## Where this fits in the workshop arc

Lab 3 is the brain. Lab 4 puts a face on it — same `build_agent()`, same streaming steps, now in a chat window where users watch the tool calls happen. Lab 5 takes the traces that start flowing in Step 5 and asks the question that makes all of it defensible: *is it right, and how often?*

And when you hear **MCP** (Model Context Protocol) mentioned in the bonus discussion: it's this tool pattern, standardized, so an agent in one application can use tools defined for another. Once you've written `get_bgp_state`, you already understand what MCP is for.
