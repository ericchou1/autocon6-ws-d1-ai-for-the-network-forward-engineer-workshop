"""chat_app.py — Streamlit chat UI on the Lab 3 agent. Final form (Step 7).

The agent is imported, not rebuilt. What this file adds:
  - a chat UI with persistent history           (Steps 2–3)
  - the agent wired in, built once              (Step 4)
  - the agent's tool steps shown as they happen (Step 5)
  - conversation memory per browser session     (Step 6)
  - tracing with session metadata, so each chat
    shows up as one session in Arize            (Step 7)
"""
import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from openinference.instrumentation import using_metadata, using_session

load_dotenv()

# Import the agent from Lab 3. Adding Lab 3's folder to the import path keeps
# this a self-contained file (no shared package to install).
LAB3 = Path(__file__).resolve().parent.parent / "Lab_3_LangChain_Network_Agent"
sys.path.insert(0, str(LAB3))
from agent import build_agent, enable_tracing  # noqa: E402

st.set_page_config(page_title="Network Co-Pilot", page_icon="🌐", layout="centered")


# ---------------------------------------------------------------------------
# Expensive things, built once and shared across reruns and browser sessions
# ---------------------------------------------------------------------------
@st.cache_resource
def start_tracing():
    """Register the Arize exporter exactly once per server process."""
    return enable_tracing(project_name="autocon6-lab4")


@st.cache_resource
def get_agent(local: bool):
    """One agent per model choice. The InMemorySaver inside it holds every
    browser session's conversation thread, keyed by thread_id."""
    return build_agent(local=local, checkpointer=InMemorySaver())


start_tracing()


# ---------------------------------------------------------------------------
# One turn of the conversation, narrated into a status box
# ---------------------------------------------------------------------------
def run_turn(agent, question: str, thread_id: str, status) -> tuple[str, list[str]]:
    """Stream the agent's graph updates. Tool calls and results go to the
    status box as they happen; the final answer is returned."""
    config = {"configurable": {"thread_id": thread_id}}
    steps, final = [], ""

    # Tag every span from this turn with the session and where it came from.
    with using_session(session_id=thread_id), using_metadata({"source": "streamlit", "app": "chat_app"}):
        for update in agent.stream({"messages": [HumanMessage(content=question)]},
                                   config=config, stream_mode="updates"):
            for node, payload in update.items():
                for msg in payload.get("messages", []):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for call in msg.tool_calls:
                            line = f"→ `{call['name']}({call['args']})`"
                            steps.append(line)
                            status.markdown(line)
                    elif isinstance(msg, ToolMessage):
                        steps.append(f"← {msg.name} returned:\n```\n{msg.content}\n```")
                        status.markdown(f"← `{msg.name}` returned:")
                        status.code(msg.content, language="text")
                    elif isinstance(msg, AIMessage):
                        final = msg.text
    return final, steps


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

with st.sidebar:
    st.markdown("### Model")
    model_choice = st.radio("Model", ["Cloud · gpt-6-luna", "Local · qwen3:4b"],
                            label_visibility="collapsed")
    use_local = model_choice.startswith("Local")
    if use_local:
        st.caption("Local answers take about a minute and a half per question.")

    st.markdown("### Controls")
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())   # new thread = fresh memory
        st.rerun()

    st.markdown("### Try asking")
    st.markdown(
        "- *What is BGP?*\n"
        "- *What's BGP looking like on r1?*\n"
        "- *Compare r1 and r3.*\n"
        "- *…and r2?*  (a follow-up — Step 6)\n"
    )

    st.markdown("### Trace")
    st.caption(f"Arize project `autocon6-lab4`, session `{st.session_state.thread_id[:8]}…`")

agent = get_agent(use_local)

st.title("🌐 Network Co-Pilot")
st.caption("Ask about the lab topology — r1, r2, r3. The assistant calls tools to inspect BGP state, and shows you when it does.")

# Replay history. Earlier turns keep their tool steps in a collapsed expander.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("steps"):
            with st.expander("Agent steps", expanded=False):
                for s in msg["steps"]:
                    st.markdown(s)
        st.write(msg["content"])

# New turn
if prompt := st.chat_input("Ask me about your network..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.status("Working…", expanded=True) as status:
            answer, steps = run_turn(agent, prompt, st.session_state.thread_id, status)
            status.update(label=f"Done — {len([s for s in steps if s.startswith('→')])} tool call(s)",
                          state="complete", expanded=False)
        st.write(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer, "steps": steps})
