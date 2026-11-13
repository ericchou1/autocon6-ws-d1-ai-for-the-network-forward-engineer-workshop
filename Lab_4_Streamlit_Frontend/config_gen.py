"""config_gen.py — intent → SR Linux config, validated before a human sees the button.

The pipeline, left to right:

  free text ──LLM──► BgpPeerIntent ──LLM──► 'set' lines ──regex──► BgpPeerIntent
                      (validated)            (generated)            (must match)
                                                                         │
                                                              ✅ gate opens ──► human approves
                                                                                     │
                                                              (optional, lab only) ──► router

Every arrow that involves a model is followed by a check that doesn't.
"""
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

# Reuse Lab 2's intent schema, generator and deterministic parse-back.
LAB2 = Path(__file__).resolve().parent.parent / "Lab_2_Structured_Network_Data"
sys.path.insert(0, str(LAB2))
from config_roundtrip import BgpPeerIntent, generate, parse_back  # noqa: E402

MODEL = "gpt-6-luna"
ROUTERS = ("r1", "r2", "r3")

st.set_page_config(page_title="SR Linux Config Generator", page_icon="🛠️")
st.title("🛠️ SR Linux Config Generator")
st.caption("Describe the BGP peer you want. The app extracts the intent, generates config, "
           "proves the config says what you meant, and only then lets you approve it.")


class ExtractedIntent(BaseModel):
    """What the model found in the text. `intent` is null when the text doesn't
    actually specify a peer — the schema gives the model a way to say "I can't",
    which is the difference between extraction and invention."""
    intent: BgpPeerIntent | None = Field(
        description="The BGP peer to configure, or null if the text does not state "
                    "all three of: peer IP address, peer AS number, peer group name.")
    missing: list[str] = Field(
        default_factory=list,
        description="Which of peer_ip / peer_as / group the text did not state.")


@st.cache_resource
def intent_extractor():
    """Free text -> ExtractedIntent, validated by Pydantic (Lab 2, Step 1 again)."""
    return ChatOpenAI(model=MODEL, reasoning_effort="none").with_structured_output(ExtractedIntent)


for key in ("intent", "config", "roundtrip_ok", "applied"):
    st.session_state.setdefault(key, None)

text = st.text_area("What do you want to configure?",
                    placeholder="e.g. Add an eBGP neighbor 10.0.99.1 in AS 65010, group name ebgp-lab")
router = st.selectbox("Target router", ROUTERS)

if st.button("Generate config", type="primary"):
    st.session_state.update(intent=None, config=None, roundtrip_ok=None, applied=None)
    if not text.strip():
        st.error("Describe what you want to configure first.")
    else:
        with st.status("Working…", expanded=True) as status:
            try:
                status.write("1. Extracting intent from your text…")
                extracted = intent_extractor().invoke(text)
                if extracted.intent is None:
                    status.update(label="Not enough to go on", state="error")
                    st.error("That text doesn't specify a BGP peer. Missing: "
                             f"{', '.join(extracted.missing) or 'peer IP, AS and group'}. "
                             "Nothing was generated — the gate stays closed.")
                    st.stop()
                intent = extracted.intent
                status.write(f"   → `{intent}`")

                status.write("2. Generating SR Linux config…")
                config = generate(intent)

                status.write("3. Parsing the generated config back (no LLM) and comparing…")
                try:
                    recovered = parse_back(config)
                    ok = recovered == intent
                    status.write("   → ✅ round-trip matches" if ok else f"   → ❌ mismatch: {recovered}")
                except ValueError as e:
                    ok = False
                    status.write(f"   → ❌ parse-back failed: {e}")

                st.session_state.update(intent=intent, config=config, roundtrip_ok=ok)
                status.update(label="Done", state="complete", expanded=False)
            except ValidationError as e:
                status.update(label="Could not extract a valid intent", state="error")
                st.error(f"The text didn't yield a valid BGP peer intent:\n\n{e}")

if st.session_state.config:
    st.markdown("### Review")
    st.code(st.session_state.config, language="bash")

    if st.session_state.roundtrip_ok:
        st.success("Round-trip check passed: the generated config encodes exactly the intent "
                   "that was extracted. A human still decides whether that intent is *right*.")
    else:
        st.error("Round-trip check FAILED. The generated config does not say what the intent said. "
                 "Do not approve this; regenerate or fix the prompt.")

    apply_for_real = st.checkbox(
        f"Actually apply to **clab-autocon6-{router}** (lab router only — this commits config)",
        value=False, disabled=not st.session_state.roundtrip_ok)

    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("✅ Approve", disabled=not st.session_state.roundtrip_ok):
            if not apply_for_real:
                st.success("Approved. This is the point where production code would push the config. "
                           "Tick the box above to push it to the lab router.")
            else:
                results = []
                for line in st.session_state.config.splitlines():
                    if not line.strip():
                        continue
                    proc = subprocess.run(
                        ["docker", "exec", f"clab-autocon6-{router}", "sr_cli", "-ec", line.strip()],
                        capture_output=True, text=True, timeout=30)
                    results.append((line.strip(), proc.returncode, (proc.stdout + proc.stderr).strip()))
                st.session_state.applied = results
    with col_right:
        if st.button("❌ Reject"):
            st.session_state.update(intent=None, config=None, roundtrip_ok=None, applied=None)
            st.rerun()

if st.session_state.applied:
    st.markdown("### Applied")
    for line, rc, out in st.session_state.applied:
        (st.success if rc == 0 else st.error)(f"`{line}`\n\n{out or '(committed)'}")
    st.info(f"Now re-capture `{router}` (Lab 3 Step 6) and ask the chat app about it. "
            "The new neighbor will sit in `active` — nothing is listening on the other end.")
