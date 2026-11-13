# Lab 1: Foundations — Local and Cloud LLMs

**Time:** ~35-40 minutes

Make your first calls to a local LLM (Ollama running `qwen3:4b-q4_K_M`) and a cloud LLM (OpenAI's `gpt-6-luna`), learn to work the **reasoning dial** on both, and run your first prompt-engineering experiment on real SR Linux output. By the end of this lab you'll have:

- A working sense of how local vs. cloud LLMs differ in speed, quality, and cost
- Small Python scripts that call each provider, including one that switches providers with a single line of code
- A feel for what "reasoning" costs you in tokens and seconds, and when it buys you anything
- Proof, on your own screen, that a naive prompt gives you unpredictable output and a one-example prompt fixes it

This lab doesn't touch the network topology — it's purely about getting comfortable calling LLMs.

## Prerequisites

- You launched the Codespace and saw the welcome banner from `postCreate.sh`.
- `ollama --version` returns `0.23.1`.
- Your `.env` file has a real `OPENAI_API_KEY` (we'll verify this in Step 4).

## Concepts

- **Local vs cloud LLMs.** Local (Ollama) means the model runs on your Codespace's CPU — private, free, slower, smaller. Cloud (OpenAI) means a request leaves your machine — faster, sharper answers, pay-per-token.
- **The same API shape.** Both Ollama and OpenAI expose chat-completion APIs with the same `messages` array structure. This is not a coincidence; Ollama deliberately mirrors OpenAI.
- **Reasoning is a dial.** Current models can "think before they answer." It is not on or off — it is a setting you pay for in output tokens and wall-clock time. Both of today's models expose it, which lets us compare the dial locally and in the cloud.
- **LangChain as a thin abstraction.** Write your application code once against LangChain's interface, and swap providers with one constructor change. We'll exploit this heavily in Labs 2-5.

---

## Step 1: Start the Ollama daemon and warm the model

Ollama doesn't auto-start in this Codespace — we start it deliberately so you see the "infrastructure must run before you can use it" pattern. (This same pattern shows up for containerlab in Lab 3.)

In a Codespace terminal:

```bash
ollama serve > /tmp/ollama.log 2>&1 &
sleep 3
```

Verify it's responding:

```bash
curl -s http://localhost:11434/ && echo "  ← Ollama is responding"
```

**Expected output:**
```
Ollama is running  ← Ollama is responding
```

Confirm the baked-in model is available:

```bash
ollama list
```

**Expected:** `qwen3:4b-q4_K_M` with size `2.6 GB`.

Now warm it up. The first request after `ollama serve` loads 2.6 GB of weights into RAM, which takes 10-20 seconds on the Codespace. Pay that once now, not in the middle of Step 3:

```bash
ollama run qwen3:4b-q4_K_M --think=false "Say hi."
```

**Expected:** a 10-20 second pause, then a one-line greeting. Every call from here on skips the load.

> **Why this exact model tag?** `qwen3:4b-q4_K_M` is the original Qwen3 4B — a *hybrid* model whose thinking mode you can switch on and off. The shorter alias `qwen3:4b` now points at a different build that always thinks and can't be told not to. Model registries move tags underneath you; pin the explicit one.

> **Troubleshooting:** If `curl` fails with `Failed to connect`, the daemon didn't start. Check `cat /tmp/ollama.log` for errors. The most common cause is port 11434 already in use — `pkill ollama` and retry.

---

## Step 2: First call via the CLI

The fastest way to talk to a local LLM is the `ollama` CLI. Try this:

```bash
ollama run qwen3:4b-q4_K_M --think=false "Explain BGP in one sentence."
```

**Expected:** A one-sentence response about BGP, streamed token-by-token at roughly 6 tokens per second — you can watch it type.

Now run the same prompt **without** `--think=false`:

```bash
ollama run qwen3:4b-q4_K_M "Explain BGP in one sentence."
```

**Expected:** A greyed-out block labeled `Thinking...` appears first — the model talking to itself about what BGP is and how to compress it into a sentence — and *then* the answer. Same model, same prompt, more tokens, more seconds. That block is the reasoning dial, and you just turned it. We'll measure it properly in Step 6.

Try a couple more prompts (keep `--think=false` for speed) to get a feel for what a 4B-parameter model can and can't do:

```bash
ollama run qwen3:4b-q4_K_M --think=false "What is the default OSPF hello interval?"
ollama run qwen3:4b-q4_K_M --think=false "Write an SR Linux command to show BGP neighbors."
```

Notice that responses on well-known topics are reasonable, but the model may fabricate specifics on niche topics (this is hallucination — Lab 2 puts a contract around it, and Lab 5 measures it).

---

## Step 3: First call via Python (raw Ollama SDK)

CLI is fine for spot checks. For automation, we use Python.

Create `hello_ollama.py` in this lab folder with the following content:

```python
"""hello_ollama.py — first call to the local LLM via Python."""
from ollama import Client

client = Client(host="http://localhost:11434")

response = client.chat(
    model="qwen3:4b-q4_K_M",
    messages=[
        {"role": "user", "content": "Explain OSPF in one sentence."}
    ],
    think=False,   # the same dial as --think=false on the CLI
)

print(response["message"]["content"])
```

Run it:

```bash
python Lab_1_Foundations/hello_ollama.py
```

**Expected output:** A one-sentence explanation of OSPF, after a few seconds.

Notice the API structure: `client.chat()` takes a list of `messages` (each a dict with `role` and `content`), and returns a dict where the answer lives at `response["message"]["content"]`. That's the same shape OpenAI uses — a deliberate design choice on Ollama's part.

---

## Step 4: First call to OpenAI

Time to make a cloud LLM call. First, verify your key is loading.

Open `.env` in the file explorer (root of the workspace) and confirm `OPENAI_API_KEY=sk-...` has a real value, not blank. If it's still blank, grab a key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and make sure your account has at least $5 in prepaid credit.

Create `hello_openai.py` in this lab folder:

```python
"""hello_openai.py — first call to OpenAI's gpt-6-luna via Python."""
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # reads .env, sets OPENAI_API_KEY in environment
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-6-luna",
    messages=[
        {"role": "user", "content": "Explain OSPF in one sentence."}
    ],
)

print(response.choices[0].message.content)

usage = response.usage
print(f"\nTokens: prompt={usage.prompt_tokens}, "
      f"completion={usage.completion_tokens} "
      f"(of which reasoning={usage.completion_tokens_details.reasoning_tokens})")
```

Run it:

```bash
python Lab_1_Foundations/hello_openai.py
```

**Expected:** A one-sentence OSPF explanation, followed by a `Tokens: ...` line showing roughly 14 prompt tokens and 80-100 completion tokens — **of which about half are reasoning tokens**. You asked a one-sentence question and the model spent ~45 tokens thinking about it before it answered, because its default reasoning setting is `medium`. You're billed for those. Hold that thought for Step 6.

Compare against Step 3:
- **Speed:** OpenAI typically comes back in 1-3s — faster than the local model (5-10s for a sentence).
- **Quality:** `gpt-6-luna` is a stronger model than a 4B local model. You'll usually notice the answers are tighter and more precise.
- **Cost:** You pay per token, reasoning tokens included. Track it from the start. At today's prices this call is a few hundredths of a cent.

> **Troubleshooting:** If you see `AuthenticationError`, your key isn't loading. Diagnose with:
> ```bash
> python -c "import os; from dotenv import load_dotenv; load_dotenv(); k = os.getenv('OPENAI_API_KEY'); print(k[:10] + '...' if k else 'KEY NOT SET')"
> ```
> Should print the first 10 chars of your key. If it says `KEY NOT SET`, `.env` isn't being read — make sure you're running Python from the workspace root (or the lab folder, since `load_dotenv()` walks up looking for `.env`).
>
> If you see `RateLimitError` saying "insufficient quota," your key is valid but the OpenAI account has no credit. Add $5 at [platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing).
>
> If you see `BadRequestError ... 'temperature' does not support 0`, you (or an older tutorial) passed `temperature=0`. Reasoning-capable models don't take the classic sampling knobs — the dial you *do* get is `reasoning_effort`, next step.

---

## Step 5: Same code, both providers — via LangChain

Here's the punchline of the first half of this lab: with LangChain, the exact same Python code can drive either provider. You swap them by changing the constructor.

> **Heads up — this file is already in the repo.** `compare.py` is here in this lab folder as a reference starting point. Open it and follow along with the walkthrough below, or, if you want the challenge, delete it and write it yourself from the steps. Either way works.

Here's `compare.py`:

```python
"""
compare.py — Send the same prompt to both Ollama and OpenAI,
print responses side-by-side. Demonstrates LangChain's provider abstraction.
"""
import time
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv()

# Model strings live on one line each so they're easy to find and swap.
LOCAL_MODEL = "qwen3:4b-q4_K_M"
CLOUD_MODEL = "gpt-6-luna"

PROMPT = "In one sentence, explain why BGP uses TCP instead of UDP."


def ask(llm):
    """Send the prompt, time the call, return (response_text, elapsed_seconds)."""
    start = time.time()
    response = llm.invoke([HumanMessage(content=PROMPT)])
    elapsed = time.time() - start
    return response.content, elapsed


# Same interface, different providers. Both have their "reasoning" dial turned
# off here so we compare the models, not how long they spend thinking.
# (Lab 1 Step 6 turns the dial back on.)
ollama = ChatOllama(model=LOCAL_MODEL, base_url="http://localhost:11434", reasoning=False)
openai = ChatOpenAI(model=CLOUD_MODEL, reasoning_effort="none")

print(f"Prompt: {PROMPT}\n")

for llm, label in [(ollama, f"Ollama / {LOCAL_MODEL}"),
                   (openai, f"OpenAI / {CLOUD_MODEL}")]:
    text, elapsed = ask(llm)
    print(f"=== {label} ({elapsed:.2f}s) ===")
    print(text)
    print()
```

Run it:

```bash
python Lab_1_Foundations/compare.py
```

**Expected output:** Two responses to the same prompt, with elapsed time stamped on each section. Typical timing:
- Ollama: 5-10s
- OpenAI: 1-3s

Notice what's identical and what's different:

- **Identical:** the call site is `llm.invoke([HumanMessage(...)])`. The same function call works for both providers.
- **Different:** the constructor — `ChatOllama(...)` vs `ChatOpenAI(...)`. Even the reasoning dial has a provider-specific name (`reasoning=False` vs `reasoning_effort="none"`), but it lives in the constructor, not in your application logic.

This is the abstraction we'll lean on in Labs 2-5. Application code doesn't need to know whether it's talking to a local or cloud model, which makes the "swap providers based on data sensitivity" pattern a one-line change in practice.

---

## Step 6: The reasoning dial

You've now seen reasoning three ways: a grey `Thinking...` block in the CLI (Step 2), a reasoning-token count on your bill (Step 4), and a constructor flag that turns it off (Step 5). Time to measure it.

> **Heads up — this file is already in the repo.** `reasoning.py` is here in this lab folder. Open it and read it before running — it's short.

The script asks one short question two ways:

- **Part A (cloud):** `gpt-6-luna` at `reasoning_effort` = `none`, `low`, `high`. For each run it prints latency, reasoning tokens, answer tokens, and the answer.
- **Part B (local):** `qwen3:4b-q4_K_M` with `reasoning=False`, then `reasoning=True`. The second run prints the model's **actual thinking text** — something the cloud provider never shows you.

Run it:

```bash
python Lab_1_Foundations/reasoning.py
```

**Expected (Part A):** three answers that are all correct and all nearly identical. `effort=none` shows `reasoning_tokens=0`; `effort=low` spends a few dozen reasoning tokens; `effort=high` spends around a hundred, and its answer is a little longer and more careful (it tends to mention missed withdrawals or session-failure detection). Latency climbs from about 1.5s to about 3s. That's the whole dial on a one-liner: 100 tokens and a second and a half for a marginally better sentence.

**Expected (Part B):** `thinking=off` answers in 10-15 seconds. `thinking=on` takes **about 1.5-2 minutes** on the default 4-core Codespace, then prints a thinking block of several hundred words — the model restating the question, listing TCP properties, considering what UDP would lose, drafting, and trimming to two sentences — followed by an answer that is, again, about the same as the one it gave without thinking.

**What this tells you:**

1. **Reasoning is a dial you pay for.** Tokens on the cloud side, seconds on the local side. `effort=high` on a one-liner bought you nothing but a bigger bill.
2. **The dial matters when the question has steps.** A lookup doesn't benefit. A multi-hop question — "given this topology, will r2 re-advertise this prefix, and why?" — does. Going Further #2 lets you prove that on the cloud side.
3. **Default is not "off."** `gpt-6-luna` defaults to `medium`. If you build a tool that fires thousands of simple calls (Lab 3's agent, Lab 4's UI), set the effort deliberately. Lab 5 will show you the trace that makes the hidden cost visible.
4. **Local lets you read the scratchpad.** That's not just a curiosity. When Lab 5 asks "why did the agent say that?", the thinking text is the closest thing you'll get to an answer.

> **Short on time?** Open `reasoning.py` and set `RUN_LOCAL_THINKING = False` to skip the slow run. Your proctor will show the local thinking block on the projector.

---

## Step 7: Prompt engineering for network tasks — naive vs few-shot

Everything so far has been "ask a question, read the answer." Starting now, the LLM is a **component in a pipeline**: raw SR Linux output goes in, something your code can use comes out. That changes what "good output" means.

### 7a. The naive baseline — and why it fails

Create `naive_parser.py` in this lab folder:

```python
"""naive_parser.py — what happens when you just ask the LLM to do it."""
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-6-luna", reasoning_effort="none")

SAMPLE = """
+---------------+----------------------+---------------+------+--------+------------+
|   Net-Inst    |         Peer         |     Group     | Flags| Peer-  |   State    |
|               |                      |               |      |   AS   |            |
+===============+======================+===============+======+========+============+
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
+---------------+----------------------+---------------+------+--------+------------+
"""

prompt = f"Extract the BGP neighbors from this output:\n{SAMPLE}"
response = llm.invoke(prompt)
print(response.content)
```

Run it **three times** in a row:

```bash
python Lab_1_Foundations/naive_parser.py
python Lab_1_Foundations/naive_parser.py
python Lab_1_Foundations/naive_parser.py
```

**Expected:** Each run can give a different format. One might return a bulleted list, another a Markdown table, another a paragraph of prose, another a code-fenced JSON-ish blob that isn't quite valid JSON. The model has too much freedom in *how* to present the answer. (Depending on the model, the three runs may sometimes look similar — newer models are more consistent. The point isn't that the format *always* changes; it's that nothing *guarantees* it stays the same, so you can't safely build a parser on it.)

**This is the problem.** You can't build software on output you can't predict.

> **Can't I just set `temperature=0`?** Two things. First, this model family doesn't accept it (Step 4's troubleshooting note). Second, even on models that do, temperature makes token sampling deterministic for an identical prompt — it does nothing to constrain the *format*. Nothing in the prompt told the model which shape to use, so it's free to pick.

### 7b. Few-shot prompting — give it an example

> **Heads up — this file is already in the repo.** `few_shot_parser.py` is here in this lab folder. Open it and follow along, or delete it and write it yourself from the steps.

Here's `few_shot_parser.py`:

```python
"""few_shot_parser.py — same task as naive_parser.py, but with an example to imitate."""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# Model string lives on one line so it's easy to find and swap.
MODEL = "gpt-6-luna"

llm = ChatOpenAI(model=MODEL, reasoning_effort="none")

SYSTEM_PROMPT = """You are a network configuration parser. Given SR Linux BGP neighbor
output, extract each peer and return one JSON object per line, no commentary.

Example input:
| default       | 192.168.1.1          | example-grp   | S    | 65500  | established|

Example output:
{"peer_ip": "192.168.1.1", "group": "example-grp", "peer_as": 65500, "state": "established"}
"""

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

response = llm.invoke([
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=SAMPLE),
])
print(response.content)
```

Run it three times:

```bash
python Lab_1_Foundations/few_shot_parser.py
python Lab_1_Foundations/few_shot_parser.py
python Lab_1_Foundations/few_shot_parser.py
```

**Expected:** Two JSON objects, one per line, in the format the example specified. Consistent across runs. No commentary, no bullets, no prose.

**The fix:** The example acts as an implicit contract. The model treats "give me output like this example" much more reliably than "give me output that I'll be happy with." Few-shot is the cheapest, most-bang-for-buck prompting technique.

> **Why does a single example help so much?** LLMs are pattern-completion engines. Showing one input/output pair turns the task from "interpret a vague instruction" into "complete the pattern" — which models are exceptionally good at. Two or three examples help a bit more; the marginal gain drops off fast.

**But notice what you *don't* have.** You have text that *looks like* JSON. Nothing guarantees it parses, that `peer_as` is an integer, or that a field isn't missing on the next run. The example is a hint, not a contract. **Lab 2 turns the hint into a contract** with Pydantic schemas — and that contract becomes your first eval.

---

## Step 8 (optional): A chat interface for your local model

For exploration (as opposed to scripting), an interactive chat is often nicer than one-shot CLI calls. How you get one depends on which Codespace you launched.

> 🔶 **GitHub Pro image only:** the Open WebUI graphical chat runs only on the **GitHub Pro** Codespace. If you launched the **default** Codespace, use the CLI REPL below.

**GitHub Pro image — Open WebUI (graphical).** Open WebUI is already running. In VS Code's **Ports** panel, find port **8080** labeled **"Open WebUI"** (it probably auto-opened in a preview pane; if not, click the globe icon). No sign-up — pick `qwen3:4b-q4_K_M` from the model dropdown and chat. If the dropdown is empty, Ollama isn't running — go back to Step 1. The UI shows the model's thinking in a collapsible block above each answer, the same text Step 6 printed.

**Default image — CLI REPL.** `ollama run` with no prompt gives you an interactive session against the same daemon:

```bash
ollama run qwen3:4b-q4_K_M
```

Type a prompt, hit enter, chat back and forth. Inside the REPL, `/set nothink` turns the dial off and `/set think` turns it back on. Type `/bye` (or Ctrl-D) to exit.

---

## Going Further

If you finish the core lab early — or want to dig deeper later — try one or more of these:

### 1. A bigger local model

> 🔶 **GitHub Pro image only:** this pulls an extra ~5 GB model. The default Codespace (32 GB) is kept lean and doesn't have headroom for it — do this on the **GitHub Pro** Codespace (or any box with more disk).

`qwen3:4b-q4_K_M` is small and fast. Its 8B sibling is roughly twice the size and noticeably stronger on network reasoning — and it's the same hybrid family, so the thinking toggle still works.

```bash
ollama pull qwen3:8b-q4_K_M   # ~5.2 GB download, 1-2 min on Codespace network
```

Change `LOCAL_MODEL` in `compare.py` and `reasoning.py` to `qwen3:8b-q4_K_M`. Re-run. Notice both the quality improvement and the latency hit (roughly 2x slower per token).

### 2. Push the dial to the top — on a question that deserves it

Step 6 used a short question on purpose. Here's one with steps. In `reasoning.py`, replace `QUESTION` with:

```python
QUESTION = ("Router r1 is in AS 65001. It has an eBGP session to r3 (AS 65002) "
            "and an iBGP session to r2 (also AS 65001). r2 learns a prefix from r1 "
            "that originated at r3. Will r2 advertise that prefix back to r1? "
            "Answer yes or no, then explain in two sentences.")
```

and change the Part A sweep to `["none", "low", "high", "xhigh", "max"]`. **Set `RUN_LOCAL_THINKING = False` first** — the local model takes 10+ minutes to think through this one on 4 cores, and Ctrl-C is your friend if you forget.

Re-run. Watch reasoning tokens climb across the sweep, and compare the *explanations*, not just the yes/no. (The answer is no — iBGP split horizon: a route learned from an iBGP peer is not re-advertised to other iBGP peers. At `none`, the model sometimes gets the right answer for a muddled reason; at `high` and above it tends to name the rule.) This is the shape of question where the dial earns its cost.

### 3. Streaming responses

Both providers support streaming. Instead of getting the whole response at once with `llm.invoke(...)`, you get chunks as the model generates them — useful for chatty UIs where the user sees text appear word-by-word instead of waiting in silence.

In `compare.py`, the `ask()` function near the top of the file currently looks like this:

```python
def ask(llm):
    """Send the prompt, time the call, return (response_text, elapsed_seconds)."""
    start = time.time()
    response = llm.invoke([HumanMessage(content=PROMPT)])
    elapsed = time.time() - start
    return response.content, elapsed
```

Replace it with this streaming version:

```python
def ask(llm):
    """Stream the response chunk-by-chunk, return (full_text, elapsed_seconds)."""
    start = time.time()
    chunks = []
    for chunk in llm.stream([HumanMessage(content=PROMPT)]):
        print(chunk.content, end="", flush=True)   # print each chunk as it arrives
        chunks.append(chunk.content)
    print()                                         # newline once the stream ends
    elapsed = time.time() - start
    return "".join(chunks), elapsed
```

**Now re-run it:**

```bash
python Lab_1_Foundations/compare.py
```

You'll see Ollama's response appear word-by-word in real time, then OpenAI's. The `text` value returned by `ask()` is still the full response, so the existing `print(text)` line below the loop will redundantly re-print each answer after streaming — that's fine for the demo (and confirms the chunks were captured), or you can delete that line for a cleaner output.

**Why this matters:** streaming doesn't make the model faster — total elapsed time is the same. What it changes is *perceived* latency: the user sees motion immediately instead of staring at a frozen prompt for 8 seconds. Every chat UI you've ever used (ChatGPT, Claude, Open WebUI in Step 8) does this. Lab 4's Streamlit app will too.

### 4. Median latency, not single-shot

Right now `compare.py` calls `ask()` once per provider. A single slow call — model cold-start, garbage-collection pause, a network blip — skews the elapsed-time number. Median across multiple runs is more honest.

Modify the comparison loop at the bottom of `compare.py` (the `for llm, label in [...]` block). Replace it with this version that runs each prompt N times and reports the median:

```python
import statistics

N = 5

print(f"Prompt: {PROMPT}\n")

for llm, label in [(ollama, f"Ollama / {LOCAL_MODEL}"),
                   (openai, f"OpenAI / {CLOUD_MODEL}")]:
    times = []
    for i in range(N):
        text, elapsed = ask(llm)
        times.append(elapsed)
        print(f"  run {i+1}: {elapsed:.2f}s")
    median = statistics.median(times)
    print(f"=== {label} — median of {N} runs: {median:.2f}s ===")
    print(text)   # last response — eyeball quality
    print()
```

Add `import statistics` at the top with the other imports (it's in Python's standard library — nothing to install).

Re-run `python Lab_1_Foundations/compare.py`. Typical pattern:

- **Ollama:** if you skipped the warm-up in Step 1, the first call is meaningfully slower than calls 2-5 — that's the model loading into CPU memory. The median ignores that outlier.
- **OpenAI:** no local warm-up, so all 5 calls cluster more tightly, but you'll still see network-jitter variance of a few hundred ms.

**Cost note:** this sends the prompt 10 times total (5 runs × 2 providers). For `gpt-6-luna` at `reasoning_effort="none"` that's a fraction of a cent — but worth understanding that "measure latency properly" comes with a real (small) bill on cloud providers.

### 5. Add Anthropic as a third provider

Anthropic Claude isn't pre-installed in the workshop image (only Ollama + OpenAI are baked into the core dependencies). Adding it as a third provider takes four steps.

**Step 1: Install the LangChain Anthropic integration.**

```bash
pip install langchain-anthropic
```

The workshop image is on the LangChain 1.x line, and so is the current `langchain-anthropic`, so no version pin is needed. Takes a few seconds. Only needed once per Codespace.

**Step 2: Get an Anthropic API key.** Go to [console.anthropic.com](https://console.anthropic.com), sign up (or sign in), grab the starter credits, and create an API key. It'll look like `sk-ant-...`.

**Step 3: Add the key to `.env`.** Open `.env` in this Codespace (the file `postCreate.sh` copied from `.env.example` on Codespace startup) and add a line:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The `load_dotenv()` call at the top of `compare.py` auto-reads this into environment variables, and `ChatAnthropic` picks it up from there — no need to pass the key explicitly in code.

**Step 4: Add three lines to `compare.py`.**

a) Add the import alongside the other LangChain imports (next to `ChatOllama` / `ChatOpenAI`):

```python
from langchain_anthropic import ChatAnthropic
```

b) Add the constructor next to where `ollama` and `openai` are created:

```python
anthropic = ChatAnthropic(model="claude-haiku-5-5")
```

c) Add a third entry to the comparison loop (the `for llm, label in [...]` list):

```python
for llm, label in [(ollama, f"Ollama / {LOCAL_MODEL}"),
                   (openai, f"OpenAI / {CLOUD_MODEL}"),
                   (anthropic, "Anthropic / claude-haiku-5-5")]:
```

Re-run `python Lab_1_Foundations/compare.py`. You'll get a three-way side-by-side: local Qwen, cloud OpenAI, cloud Anthropic. `claude-haiku-5-5` sits in the same price bracket as `gpt-6-luna` ($0.10 in / $0.50 out per million tokens), and it too thinks by default — the dial on Anthropic's side is called `effort`. Notice that the answers vary in *style* even with the same prompt and same `messages` shape — different model lineages produce noticeably different prose. The `bonus/anthropic/` folder goes deeper on what's specifically different about Anthropic's API and where Claude tends to shine for network workflows.

---

## What's next

In **Lab 2 (Structuring Network Data with Pydantic)** we turn Step 7's hint into a contract: a Pydantic schema the model *must* satisfy, validated in code, with retries when it doesn't. The same raw BGP output becomes a real Python object — and a small golden set of known outputs becomes your first eval, which Lab 5 will scale up. We'll use the LangChain interface from Step 5 throughout, so the provider switch stays free.
