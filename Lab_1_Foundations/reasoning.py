"""
reasoning.py — Reasoning is a dial, not a feature.

Part A: one question to the cloud model at three reasoning_effort settings.
        Watch reasoning tokens, latency, and the answer change (or not).
Part B: the same question to the local model with thinking off, then on.
        This time you get to READ the reasoning, not just count it.
"""
import time
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv()

LOCAL_MODEL = "qwen3:4b-q4_K_M"
CLOUD_MODEL = "gpt-6-luna"

# Deliberately a *short* question. Reasoning cost scales with how much there
# is to reason about, and on a 4-core Codespace the local model thinks at
# roughly 6 tokens/second. (Going Further #2 has a harder one.)
QUESTION = ("In two sentences: why does BGP use TCP instead of UDP, "
            "and what would break if it used UDP?")

# Flip to False if you're short on time — Part B's thinking=on run takes
# about 1.5–2 minutes on the default Codespace.
RUN_LOCAL_THINKING = True


def timed(llm, question):
    start = time.time()
    response = llm.invoke([HumanMessage(content=question)])
    return response, time.time() - start


# ---------------------------------------------------------------------------
# Part A — cloud: the reasoning_effort dial
# ---------------------------------------------------------------------------
print(f"Question: {QUESTION}\n")
print(f"=== Part A: {CLOUD_MODEL}, reasoning_effort sweep ===")

for effort in ["none", "low", "high"]:
    llm = ChatOpenAI(model=CLOUD_MODEL, reasoning_effort=effort)
    response, elapsed = timed(llm, QUESTION)
    usage = response.usage_metadata or {}
    reasoning_tokens = (usage.get("output_token_details") or {}).get("reasoning", 0)
    answer_tokens = usage.get("output_tokens", 0) - reasoning_tokens
    print(f"\n--- effort={effort:<4}  {elapsed:4.1f}s  "
          f"reasoning_tokens={reasoning_tokens:<4} answer_tokens={answer_tokens}")
    print(response.content)

# ---------------------------------------------------------------------------
# Part B — local: the thinking toggle, and the thinking itself
# ---------------------------------------------------------------------------
print(f"\n\n=== Part B: {LOCAL_MODEL}, thinking off vs on ===")

llm = ChatOllama(model=LOCAL_MODEL, reasoning=False)
response, elapsed = timed(llm, QUESTION)
print(f"\n--- thinking=off  {elapsed:4.1f}s")
print(response.content)

if RUN_LOCAL_THINKING:
    print("\n--- thinking=on   (be patient: ~1.5–2 min on 4 CPU cores) ...", flush=True)
    llm = ChatOllama(model=LOCAL_MODEL, reasoning=True)
    response, elapsed = timed(llm, QUESTION)
    thinking = response.additional_kwargs.get("reasoning_content", "")
    print(f"--- thinking=on   {elapsed:4.1f}s  thinking_chars={len(thinking)}")
    print("\n[THINKING — the model's scratchpad, normally hidden]")
    print(thinking.strip())
    print("\n[ANSWER]")
    print(response.content)
