# Lab 4: Interactive Co-Pilot UI with Streamlit

**Time:** ~30 minutes

Take the agent from Lab 3 and give it a face: a chat web app at `localhost:8501` where anyone on your team can ask a question — and **watch the agent work**. Not just the answer: which tool it called, with what arguments, what came back, in the order it happened. Then make it conversational, and make every chat show up as a session in Arize.

The agent code from Lab 3 does not change. You import it. Lab 4 is about what a user sees.

## Prerequisites

- Lab 3 completed. Lab 4 imports `build_agent` and `enable_tracing` from Lab 3's `agent.py`, which imports Lab 2's parser. If Lab 3 Step 6 populated `live_data/`, the UI reads your live captures; otherwise it reads Lab 2's golden set. Either works.
- `ARIZE_SPACE_ID` and `ARIZE_API_KEY` in `.env` for Step 7 (same as Lab 3 Step 5).

## Concepts

- **Streamlit's rerun model.** Every interaction reruns your script from the top. Your UI is always a pure function of current state — no callbacks, no event handlers.
- **Session state.** Because the script reruns, plain variables reset. `st.session_state` persists across reruns — chat history and the conversation's thread ID live there.
- **Build expensive things once.** `@st.cache_resource` keeps the agent (and the tracing setup) alive across reruns and across browser sessions.
- **Show the work.** A chat that only shows the final answer hides the one thing that makes an agent trustworthy or not: what it did to get there. `st.status` gives you a live, collapsible box to narrate it into.
- **Two views of one execution.** The status box is what the user sees. The trace in Arize is what the engineer sees. Same run, tagged with the same session ID.

---

## Step 1: Streamlit "hello world"

Before adding complexity, get something rendering. Create `hello.py` in this lab folder:

```python
"""hello.py — minimal Streamlit app to verify the setup."""
import streamlit as st

st.title("Network Co-Pilot")
st.write("If you can see this, Streamlit is working.")

name = st.text_input("What's your name?")
if name:
    st.write(f"Hello, {name}!")
```

Run it:

```bash
cd /workspaces/autocon6-ws-d1-ai-for-the-network-forward-engineer-workshop
streamlit run Lab_4_Streamlit_Frontend/hello.py
```

**Expected:** Streamlit prints three URLs (**Local**, **Network** and **External**), and VS Code opens a preview pane for port **8501**, labeled "Streamlit."

> **Important — open the app in a real browser tab, not the preview pane.** The pane that opens by itself is VS Code's built-in "Simple Browser", and Streamlit doesn't work in it. When we ran this in a Codespace on 8 November 2026, the pane showed **"github.com refused to connect"** and nothing else. Sometimes it renders the page instead, and then typing and clicks silently do nothing. Either way, close it and use one of the two ways in that do work:
>
> - In the **Ports** panel, click the **globe icon** next to port 8501.
> - Or, in the terminal, **Ctrl-click** (**Cmd-click** on a Mac) the **Local URL**. VS Code rewrites it to your Codespace's forwarded address.
>
> Ignore the **Network** and **External** URLs. They are addresses inside the Codespace (in our run they began `10.` and `172.`), and your laptop can't reach them. **All of this applies to every `streamlit run` in this lab.**

Type your name. "Hello, …" appears below as you type.

> **The rerun model, in action:** every keystroke reruns `hello.py` from the top. First pass, `name` is empty and the `if` is false. After a character, `name` has a value and the conditional renders. It looks like reactivity; it's re-execution.

`Ctrl+C` in the terminal stops the app.

---

## Step 2: A static chat layout

> **Heads up — `chat_app.py` is already in the repo, in its finished form** (the end of Step 7). Steps 2–7 build it up; the snippets here are what each stage looks like. Read along, or delete the file and build it yourself. If you get stuck partway, or an edit leaves the app broken, this puts the finished file back: `git checkout -- Lab_4_Streamlit_Frontend/chat_app.py`

The chat UI shape, no agent yet:

```python
"""chat_app.py — static chat UI, no agent yet."""
import streamlit as st

st.title("Network Co-Pilot")
st.caption("Ask questions about the lab topology.")

messages = [
    {"role": "user",      "content": "What's BGP looking like on r1?"},
    {"role": "assistant", "content": "r1 has two BGP neighbors, both established."},
    {"role": "user",      "content": "Is r3 peering with r1?"},
    {"role": "assistant", "content": "Yes — r1 has an eBGP session with r3 in AS 65002."},
]

for msg in messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

prompt = st.chat_input("Ask me about your network...")
if prompt:
    st.write(f"You asked: {prompt}")
```

```bash
streamlit run Lab_4_Streamlit_Frontend/chat_app.py
```

**Expected:** four chat bubbles with avatars, an input pinned to the bottom. Typing echoes "You asked: …".

`st.chat_message("user"|"assistant")` gives you the styled bubbles and avatars for free. `st.chat_input(...)` is always pinned to the bottom and returns the typed value on Enter.

---

## Step 3: Persistent history with session state

The script reruns on every input, so `messages` resets. Move it into `st.session_state`:

```python
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Ask me about your network..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    response = f"You said: {prompt}"          # placeholder until Step 4
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.write(response)
```

**Expected:** type three questions; all six messages stay. Refresh the page and they're gone — session state is per browser session.

Two patterns to memorize: the walrus `if prompt := st.chat_input(...)` runs the block only when there's new input; and after appending to history you also render the new messages immediately, because the render loop above already ran before you appended.

---

## Step 4: Wire in the Lab 3 agent

Replace the placeholder with the real agent. The imports and setup:

```python
import sys
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()

# Import the agent from Lab 3. Adding Lab 3's folder to the import path keeps
# this a self-contained file (no shared package to install).
LAB3 = Path(__file__).resolve().parent.parent / "Lab_3_LangChain_Network_Agent"
sys.path.insert(0, str(LAB3))
from agent import build_agent, enable_tracing  # noqa: E402


@st.cache_resource
def get_agent(local: bool):
    return build_agent(local=local)


agent = get_agent(False)
```

and the turn:

```python
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        answer = result["messages"][-1].text
        st.write(answer)
```

That's the whole integration: Lab 3's `build_agent()` behind `@st.cache_resource`, and `agent.invoke()` with a message list (it's a LangGraph graph, so the input is state, not a string). The last message in the returned state is the answer.

Re-run and ask the four Lab 3 questions. **Expected:** the same answers as Lab 3, in chat bubbles. And notice what you *can't* see: whether the agent called a tool. The terminal where `streamlit run` is going is silent, because the agent's step printing lived in Lab 3's `ask()` helper, which we didn't use. The user gets an answer and no evidence. Step 5 fixes that.

> **About `@st.cache_resource`:** without it you'd rebuild the agent on every keystroke. The decorator says "this object is expensive and reusable — keep it." It's keyed on the arguments, which is how the sidebar's model toggle in Step 7 gets one cached agent per model.

---

## Step 5: Show the agent's work

This is the step the lab is named for. Replace the `invoke` with a stream, and narrate it into a status box:

```python
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def run_turn(agent, question: str, status) -> str:
    """Stream the agent's graph updates. Tool calls and results go to the
    status box as they happen; the final answer is returned."""
    final = ""
    for update in agent.stream({"messages": [HumanMessage(content=question)]},
                               stream_mode="updates"):
        for node, payload in update.items():
            for msg in payload.get("messages", []):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for call in msg.tool_calls:
                        status.markdown(f"→ `{call['name']}({call['args']})`")
                elif isinstance(msg, ToolMessage):
                    status.markdown(f"← `{msg.name}` returned:")
                    status.code(msg.content, language="text")
                elif isinstance(msg, AIMessage):
                    final = msg.text
    return final
```

```python
    with st.chat_message("assistant"):
        with st.status("Working…", expanded=True) as status:
            answer = run_turn(agent, prompt, status)
            status.update(label="Done", state="complete", expanded=False)
        st.write(answer)
```

This is Lab 3's `ask()` with `print` swapped for `status.markdown`. Same stream, same three message kinds — a tool call, a tool result, a final answer — rendered into a box that's open while the agent works and collapses when it's done.

Re-run and ask *"Compare r1 and r3."*

**Expected:** a "Working…" box appears and fills in live:

```
→ get_bgp_state({'node': 'r1'})
→ get_bgp_state({'node': 'r3'})
← get_bgp_state returned:
    BGP neighbors on r3 (live capture, 1 session(s)):
      - peer 10.1.13.1  AS65001  group=ebgp-r1  state=established  uptime=28s  ...
← get_bgp_state returned:
    BGP neighbors on r1 (live capture, 2 session(s)):
      ...
```

…then the box collapses to **Done** and the comparison appears below it. Click the collapsed box to reopen it. Ask *"What is BGP?"* and the box completes with nothing in it — no tool call, and the user can see that too.

**Why this is the centerpiece.** An agent that shows only its answer asks the user to trust it. An agent that shows *"I ran `get_bgp_state` on r1 and r3, here's what came back"* lets the user check it — and lets them notice when it checked the wrong router, or didn't check at all. Every serious agent product has this panel. Now yours does.

---

## Step 6: Make it conversational

Each turn so far is an island: *"…and r2?"* after a question about r1 has nothing to resolve against. In Lab 3's Going Further #3 you saw the fix — a checkpointer on the graph and a thread ID on each call. In the UI it's three changes:

```python
from langgraph.checkpoint.memory import InMemorySaver
import uuid


@st.cache_resource
def get_agent(local: bool):
    # The InMemorySaver inside holds every browser session's thread, keyed by thread_id.
    return build_agent(local=local, checkpointer=InMemorySaver())
```

```python
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())     # one per browser session
```

```python
    config = {"configurable": {"thread_id": thread_id}}
    for update in agent.stream({"messages": [HumanMessage(content=question)]},
                               config=config, stream_mode="updates"):
```

(`run_turn` gains a `thread_id` parameter and passes it as `config`.) And the clear button becomes a real reset:

```python
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())   # new thread = fresh memory
        st.rerun()
```

Re-run. Ask *"What's BGP looking like on r1?"*, then *"…and r2?"*.

**Expected:** the second turn's status box shows `→ get_bgp_state({'node': 'r2'})` — the agent understood "and" from the thread — and the answer may compare against r1 unprompted. Click **Clear conversation** and ask *"…and r2?"* cold: the agent now asks what you mean, or guesses. Memory is a thread, and you just started a new one.

Two browser tabs get two thread IDs and two independent conversations against one cached agent. That's the whole multi-user story, for free.

---

## Step 7: Polish — and two views of one execution

Finishing touches first. The sidebar gains a model toggle, the suggestions, and the trace pointer:

```python
with st.sidebar:
    st.markdown("### Model")
    model_choice = st.radio("Model", ["Cloud · gpt-6-luna", "Local · qwen3:4b"],
                            label_visibility="collapsed")
    use_local = model_choice.startswith("Local")
    ...
    st.markdown("### Trace")
    st.caption(f"Arize project `autocon6-lab4`, session `{st.session_state.thread_id[:8]}…`")

agent = get_agent(use_local)
```

History replay keeps each earlier turn's steps in a collapsed **Agent steps** expander, so the evidence doesn't vanish on rerun. Open the finished `chat_app.py` to see where those pieces sit.

Now the seam into Lab 5. Tracing is two lines, exactly as in Lab 3 — plus the thing a UI can add that a script can't: **who** was asking and **which conversation** it belonged to.

```python
from openinference.instrumentation import using_metadata, using_session


@st.cache_resource
def start_tracing():
    """Register the Arize exporter exactly once per server process."""
    return enable_tracing(project_name="autocon6-lab4")


start_tracing()
```

```python
    # Tag every span from this turn with the session and where it came from.
    with using_session(session_id=thread_id), using_metadata({"source": "streamlit", "app": "chat_app"}):
        for update in agent.stream(...):
            ...
```

`using_session` stamps the thread ID onto every span the turn produces. `using_metadata` adds whatever key-values you like. Neither touches the agent.

Re-run, ask two or three questions, then open Arize → **autocon6-lab4**. **Expected:** the same traces you saw in Lab 3 — root span, model calls, tool spans with the parser's calls nested inside — but now with a **session** column. Click the session and you get the whole conversation in order, each turn a trace. Compare it with the status boxes in the browser tab: same tool calls, same arguments, same order. The user's view and the engineer's view of one execution.

Flip the sidebar to **Local** and ask one question. **Expected:** about a minute and a half, the same status box, the same shape of answer — and in Arize, a trace whose model spans say `qwen3:4b-q4_K_M` and whose latency is twenty times the cloud run's. That's the comparison Lab 5 will make with numbers instead of eyeballs.

**That's the app.** About 120 lines of Streamlit, importing 60 lines of agent, importing 100 lines of parser. The UI knows nothing about BGP. The agent knows nothing about Streamlit. The parser knows nothing about either. Each layer swaps independently, and the trace ties them back together.

---

## Going Further

If you finish the core lab early — or want to extend it later:

### 1. The config generator — a gate that checks before it asks

Querying is safe. *Changing* a router is where a co-pilot can hurt you, and where "human in the loop" has to mean more than a button. This app generates SR Linux config from a sentence — and proves the config says what you meant *before* it lets a human approve it.

> **Heads up — this file is already in the repo.** `config_gen.py` is here in this lab folder.

The pipeline:

```
  free text ──LLM──► BgpPeerIntent ──LLM──► 'set' lines ──regex──► BgpPeerIntent
                      (validated)            (generated)            (must match)
                                                                         │
                                                              ✅ gate opens ──► human approves
                                                                                     │
                                                              (optional, lab only) ──► router
```

Every arrow that involves a model is followed by a check that doesn't. The generation and the parse-back are Lab 2's `config_roundtrip.py`, imported. The extraction step uses a schema that **lets the model say no**:

```python
class ExtractedIntent(BaseModel):
    intent: BgpPeerIntent | None = Field(
        description="The BGP peer to configure, or null if the text does not state "
                    "all three of: peer IP address, peer AS number, peer group name.")
    missing: list[str] = Field(default_factory=list,
        description="Which of peer_ip / peer_as / group the text did not state.")
```

Without the `| None`, a strict schema *forces* the model to produce a peer — and given "make the network faster please" it will invent an IP and an AS to satisfy the schema. We saw it do exactly that. Giving the schema an honest exit is the difference between extraction and invention.

```bash
streamlit run Lab_4_Streamlit_Frontend/config_gen.py
```

Try, in order:

- *"Add an eBGP neighbor 10.0.99.1 in AS 65010, group name ebgp-lab"* → the status box walks through extract → generate → parse back → **✅ round-trip matches**, the three `set` lines appear, and the **Approve** button is enabled.
- *"make the network faster please"* → **Not enough to go on**, missing `peer_ip, peer_as, group`, nothing generated, no button.
- *"Peer with 192.0.2.9 please"* → missing `peer_as, group`. Partial intent is still no intent.

**Approve** on its own does nothing to any device — the message tells you that's where production code would push. Tick **Actually apply to clab-autocon6-rX** first and Approve runs each `set` line through `docker exec … sr_cli -ec`, one commit per line, and shows the router's reply. Then re-run the Lab 3 Step 6 capture for that router and ask the chat app about it: the new neighbor is there, in `active`, because nothing answers at 10.0.99.1. Remove it afterwards with `docker exec clab-autocon6-r3 sr_cli -ec "delete / network-instance default protocols bgp neighbor 10.0.99.1"` (and the group).

> **Why a round-trip check and not "the LLM looked correct"?** Because the human reviewing three `set` lines at 4:45pm on a Friday is the weakest link in the chain, and the check costs nothing. The gate should do the mechanical verification so the human can spend their attention on the one question only they can answer: *is this the right change?*

### 2. Stream the answer token by token

Step 5 streams *steps*. The final answer still arrives in one piece. LangGraph can stream the model's tokens too — `stream_mode="messages"` yields `(message_chunk, metadata)` pairs as they're generated:

```python
def answer_tokens(agent, question, config):
    for chunk, meta in agent.stream({"messages": [HumanMessage(content=question)]},
                                    config=config, stream_mode="messages"):
        if meta.get("langgraph_node") == "model" and not getattr(chunk, "tool_calls", None):
            yield chunk.text

with st.chat_message("assistant"):
    answer = st.write_stream(answer_tokens(agent, prompt, config))
```

`st.write_stream` consumes the generator and returns the full text for history. Combine with Step 5 by running the `updates` stream for the status box and the `messages` stream for the answer — or use `stream_mode=["updates", "messages"]` to get both from one call.

### 3. Multi-page app

Streamlit builds navigation from a `pages/` folder. Move `config_gen.py` to `pages/config_gen.py` next to `chat_app.py`, run `chat_app.py`, and both apps appear in the sidebar. A co-pilot *suite* instead of two scripts.

### 4. Deploy it

Streamlit Community Cloud ([share.streamlit.io](https://share.streamlit.io)) publishes a public app from a GitHub repo for free. You'd move the OpenAI and Arize keys into Streamlit's secrets manager (never commit `.env`), and the tool would need a data source other than your Codespace's routers — the golden captures work. The result is a URL you can hand to anyone.

---

## What's next

You've built every layer: LLM access and the reasoning dial (Lab 1), a validated parser with its own eval (Lab 2), an agent that uses it and traces itself (Lab 3), and a UI that shows the agent's work and tags every conversation (Lab 4). Traces from the terminal and from the UI are sitting in Arize right now.

**Lab 5** is the question that makes all of it defensible: *is it right, and how do you know?* You'll read those traces, then run an experiment in Arize: four questions about this network, one prompt, and an LLM judge that scores every answer. You'll change the prompt, run it again, and compare the two runs row by row. Then the agent you just built takes the same kind of test, with two trap questions that invite it to make something up. No new code to build: the agent Lab 5 tests is the one you already have.
