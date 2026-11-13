# Lab 4 Concepts: Interactive Co-Pilot UI with Streamlit

> 10-15 min introduction before hands-on starts.

## The big picture

Three labs in, you have an agent that answers questions about a network, backed by a validated parser, with every run traced. It works.

It also lives in a Python script that only you can run.

Lab 4 gives it a face: a chat web app anyone on your team can open. But a face is the easy part — Streamlit makes a chat UI in forty lines. The part that matters is what the face *shows*. An agent that hands back only an answer asks to be trusted. An agent that shows which tool it called, with what, and what came back, can be *checked*. That panel is the difference between a demo and a tool someone will rely on, and it's the centerpiece of this lab.

## Why a UI is the unlock

Every network team has someone like Maria who reads configs fluently but doesn't write Python, and someone like Raj who lives in vim. If the co-pilot only runs from `python agent.py`, Raj has a toy and Maria has nothing.

A chat UI levels that. Raj keeps the script. Maria gets the same agent in a browser tab. And because the agent *shows its work*, Maria can tell the difference between "the agent checked r3" and "the agent assumed" — which is exactly the judgement she's good at.

## What Streamlit is

A Python library that turns a script into a web app. No HTML, no JavaScript. The one idea to internalize: **every interaction reruns the whole script from the top.** Click, type, submit — rerun. It sounds wasteful and it makes the model dead simple: the UI is a pure function of current state.

Three consequences, and they're the whole of Steps 3–4:

- State that must survive a rerun goes in `st.session_state` — chat history, the conversation's thread ID.
- Things that are expensive to build go behind `@st.cache_resource` — the agent, the tracing setup — built once, shared across reruns and across users.
- Everything else just renders fresh.

## Showing the work

Lab 3's agent is a LangGraph graph, and a graph streams its progress one node at a time: *the model asked for a tool*, *the tool returned*, *the model answered*. Lab 3 printed those to a terminal. Lab 4 renders the identical stream into a live status box that's open while the agent works and collapses when it's done.

```
   ┌────────────────────────────────────────────────┐
   │  🌐 Network Co-Pilot                           │
   │                                                │
   │  [user]  Compare r1 and r3.                    │
   │  [assistant]                                   │
   │    ▾ Working…                                  │
   │      → get_bgp_state({'node': 'r1'})           │
   │      → get_bgp_state({'node': 'r3'})           │
   │      ← get_bgp_state returned: …               │
   │      ← get_bgp_state returned: …               │
   │    Both routers have established sessions …    │
   └────────────────────────────────────────────────┘
```

Nothing about the agent changed to make this possible. The stream was always there; the UI just stopped throwing it away.

## Memory is a thread

"…and r2?" means nothing without the previous turn. In LangGraph, conversation memory is a *checkpointer* on the graph plus a *thread ID* on each call: same thread, the graph remembers; new thread, it doesn't. One cached agent holds every user's thread. The clear button just mints a new ID.

## Two views of one execution

The status box is what the user sees. The trace in Arize is what the engineer sees. In Step 7 they become the same object: every turn runs inside a *session* tagged with the thread ID, so Arize groups a conversation's traces the way the browser groups its bubbles.

```
   user's view                        engineer's view
   ──────────────                     ──────────────────────────────
   ▾ Done — 2 tool call(s)            session 3f9a…  ·  trace #3
     → get_bgp_state(r1)                ├─ model      1.2s   412 tok
     → get_bgp_state(r3)                ├─ tools
     ← returned …                       │   ├─ get_bgp_state(r1)  ← parser LLM call
     ← returned …                       │   └─ get_bgp_state(r3)  ← parser LLM call
   Both routers have …                  └─ model      1.6s   388 tok
```

That's the seam into Lab 5. Everything Lab 5 evaluates is already flowing.

## The config generator: a gate that checks before it asks

Querying a router is safe. *Changing* one is where a co-pilot can hurt you, and "human in the loop" has to mean more than an Approve button a tired engineer clicks at 4:45pm. Going Further #1 builds the pattern properly:

- the model extracts a **validated intent** from free text — with a schema that lets it say *"not enough information"* rather than invent a peer;
- the model generates config from the intent;
- **code, not a model,** parses the config back and proves it encodes the same intent;
- only then is the Approve button enabled — and by default it still touches nothing.

Every arrow that involves a model is followed by a check that doesn't. The human's attention is saved for the one question only a human can answer: is this the *right* change?

## What you'll have built

```
   ┌──────────────────────────────────────────────┐
   │  Streamlit chat UI           (Lab 4)         │   shows steps · remembers · tags sessions
   └─────────────────┬────────────────────────────┘
                     │ "Compare r1 and r3"
                     ▼
   ┌──────────────────────────────────────────────┐
   │  LangGraph agent             (Lab 3)         │   decides · calls tools · traced
   └─────────────────┬────────────────────────────┘
                     │ get_bgp_state(node='r1'), (node='r3')
                     ▼
   ┌──────────────────────────────────────────────┐
   │  BGP tool → Pydantic parser  (Lab 3 + Lab 2) │   validated · eval'd
   └─────────────────┬────────────────────────────┘
                     │ raw text
                     ▼
   ┌──────────────────────────────────────────────┐
   │  Golden captures / live containerlab         │
   └──────────────────────────────────────────────┘
```

The UI knows nothing about BGP. The agent knows nothing about Streamlit. The parser knows nothing about either. Each layer swaps independently; the trace ties them back together.

## Where this fits in the workshop arc

Lab 4 is the payoff moment — you'll remember typing a question into a chat box and watching your own tooling go and check. It is also the last lab that *builds*. Lab 5 builds nothing new; it asks of everything you've built the only question that matters in production: *is it right, and how do you know?*
