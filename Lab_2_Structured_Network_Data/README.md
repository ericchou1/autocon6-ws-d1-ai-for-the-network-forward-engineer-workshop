# Lab 2: Structuring Network Data with Pydantic

**Time:** ~35-40 minutes

Lab 1 ended with a few-shot example: a *hint* about the output format you wanted. This lab replaces the hint with a **contract** — a Pydantic schema the model must satisfy, validated in your code — and then uses that contract plus a handful of real router captures to build your **first eval**.

By the end, this raw output:

```
| default              | 10.1.13.2                      | ebgp-r3              | S      | 65002      | active           | -                |                |                                |
```

will reliably become this Python object:

```python
BgpNeighbor(peer_ip=IPv4Address('10.1.13.2'), group='ebgp-r3', peer_as=65002,
            state='active', uptime_seconds=None,
            prefixes_received=None, prefixes_active=None, prefixes_sent=None)
```

and you'll have a script that proves it, across five real captures, with a score.

The parser you build here reappears in Lab 3, wrapped in an agent that calls it autonomously. The eval reappears in Lab 5, scaled up onto a platform.

## Prerequisites

- Lab 1 completed (Ollama daemon running, OpenAI key working).
- Comfortable with Python's class syntax — we'll use Pydantic to define schemas.
- **No topology needed.** This lab runs against real captures in `golden/`, taken from the workshop's containerlab topology. Lab 3 brings the routers up.

## Concepts

- **The schema is the contract.** `with_structured_output()` hands the provider a JSON schema; the provider guarantees the *shape*. Pydantic then enforces the *meaning*: types, ranges, allowed values, cross-field rules.
- **Extraction and validation are different jobs.** The model extracts. Your code validates. Keep them separate and retries become trivial.
- **A ValidationError is a feature.** It's the model being *stopped* from handing you garbage. Production code catches it and retries; it never swallows it.
- **Structural correctness is not correctness.** A perfectly valid object can hold a wrong number. Only comparing against known-good answers catches that — and that comparison is an eval.

---

## Step 1: The schema is the contract

> **Heads up — this file is already in the repo.** `structured_parser.py` is here in this lab folder. Open it and follow along, or delete it and write it yourself from the steps.

Here's `structured_parser.py`:

```python
"""structured_parser.py — Pydantic schemas as a contract with the LLM."""
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-6-luna"


class BgpNeighbor(BaseModel):
    """A single BGP peering session."""
    peer_ip: str = Field(description="IP address of the BGP peer")
    group: str = Field(description="Peer group name this neighbor belongs to")
    peer_as: int = Field(description="Peer's autonomous system number")
    state: str = Field(description="BGP session state (established, active, idle, etc.)")


class BgpNeighborList(BaseModel):
    """Top-level container for a list of neighbors."""
    neighbors: list[BgpNeighbor]


llm = ChatOpenAI(model=MODEL, reasoning_effort="none").with_structured_output(BgpNeighborList)

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

result = llm.invoke(f"Extract the BGP neighbors:\n{SAMPLE}")

# result is a BgpNeighborList — a real Python object, not a string
print(type(result).__name__)
for n in result.neighbors:
    print(f"  {n.peer_ip:<12} AS{n.peer_as:<6} {n.state}")
```

Run it:

```bash
python Lab_2_Structured_Network_Data/structured_parser.py
```

**Expected:**
```
BgpNeighborList
  10.0.0.2     AS65001  established
  10.1.13.2    AS65002  active
```

Notice what's happening here:

- The LLM call returns a `BgpNeighborList` object, not a string. No `json.loads()`, no regex, no "strip the code fence first."
- `peer_as` is typed as `int`. If the model returned `"65001"` as a string, Pydantic would coerce it. If it returned something that can't be an integer, you'd get an error, not silent corruption.
- The `Field(description=...)` text travels to the model as part of the schema. It's documentation and prompt at the same time.

Run it three times. Same object shape every time — that's what Lab 1's few-shot example couldn't promise.

---

## Step 2: Tighten the contract

Step 1's schema is honest but loose. `peer_ip: str` accepts `"banana"`. `peer_as: int` accepts `-5`. `state: str` accepts `"up"`, which is not a BGP state. Pydantic can enforce all of that — and the model will see those constraints in the schema it's given.

> **Heads up — this file is already in the repo.** `strict_parser.py` is here in this lab folder.

Open `strict_parser.py`. The schema now reads:

```python
from ipaddress import IPv4Address
from typing import Literal
from pydantic import BaseModel, Field, ValidationError, field_validator

# The six BGP FSM states from RFC 4271. Anything else is rejected.
BgpState = Literal["idle", "connect", "active", "opensent", "openconfirm", "established"]


class BgpNeighbor(BaseModel):
    peer_ip: IPv4Address = Field(description="IP address of the BGP peer")
    group: str = Field(min_length=1, description="Peer group name")
    peer_as: int = Field(ge=1, le=4294967295, description="Peer AS number (1 to 2^32-1)")
    state: BgpState = Field(description="BGP session state, lowercase")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value):
        """Accept 'Established' / 'ESTABLISHED' from the model, store lowercase."""
        return value.lower() if isinstance(value, str) else value
```

Four upgrades, each closing a hole:

| Change | What it rejects now |
|---|---|
| `IPv4Address` instead of `str` | `"10.0.0.256"`, `"banana"`, an IPv6 address |
| `Literal[...]` for state | `"up"`, `"down"`, `"Estab"`, anything that isn't one of the six FSM states |
| `ge=1, le=4294967295` | `0`, negatives, anything beyond 32 bits |
| `@field_validator` | nothing — it *normalizes*. `"Established"` becomes `"established"` before the Literal check runs, so harmless casing differences don't fail |

The script has two parts. **Part 1 never calls an LLM.** It feeds a good row and a deliberately bad row straight into the schema so you can see what rejection looks like. Run it:

```bash
python Lab_2_Structured_Network_Data/strict_parser.py
```

**Expected (Part 1):**
```
=== Part 1: validating hand-made data (no LLM) ===
good row  -> peer_ip=IPv4Address('10.0.0.2') group='ibgp-65001' peer_as=65001 state='established'

bad row   -> 4 errors:
  peer_ip    Input is not a valid IPv4 address
  group      String should have at least 1 character
  peer_as    Input should be greater than or equal to 1
  state      Input should be 'idle', 'connect', 'active', 'opensent', 'openconfirm' or 'established'
```

Read that error block carefully. It names the field, says what was wrong, and does it for *all four* problems at once. That text is going to matter in Step 5, because it's exactly what we'll hand back to the model when it gets something wrong.

**Expected (Part 2):** the same two neighbors as Step 1, but `peer_ip` is now an `IPv4Address` object, not a string. The model saw the tighter schema and complied.

> **Why not validate everything in the prompt?** You could write "state must be one of idle, connect, …" in English. The model would mostly obey. *Mostly.* The schema makes it structural: the provider won't even let the model emit a value outside the Literal. And for things the provider can't enforce — like "an established session must have an uptime" — Pydantic is the backstop. Prompt for intent; validate for guarantees.

---

## Step 3: Real output, full width

The samples so far were two trimmed rows. Real `show network-instance default protocols bgp neighbor` output has a banner, a flags legend, nine columns, and a summary footer. Look at one:

```bash
cat Lab_2_Structured_Network_Data/golden/r1_bgp.txt
```

That's a genuine capture from r1 in the workshop topology. The extra columns are the interesting ones: `Uptime` as `0d:0h:1m:9s`, and `[Rx/Active/Tx]` as `[6/1/10]`. A useful parser needs those as numbers, not strings.

> **Heads up — this file is already in the repo.** `parse_bgp.py` is here in this lab folder. **This is the parser the rest of the workshop reuses** — Lab 3 wraps it as a tool. Open it.

The schema grows to match the real output:

```python
class BgpNeighbor(BaseModel):
    peer_ip: IPv4Address = Field(description="IP address of the BGP peer")
    group: str = Field(min_length=1, description="Peer group name")
    peer_as: int = Field(ge=1, le=4294967295, description="Peer AS number")
    state: BgpState = Field(description="BGP session state, lowercase")
    uptime_seconds: int | None = Field(
        description="The Uptime column converted to total seconds "
                    "(e.g. '0d:0h:1m:9s' -> 69). null when the column is '-'."
    )
    # The [Rx/Active/Tx] column, split into three fields. (Not a tuple:
    # OpenAI's strict-schema subset doesn't allow fixed-length arrays.)
    prefixes_received: int | None = Field(description="Rx count from [Rx/Active/Tx]; null if blank")
    prefixes_active: int | None = Field(description="Active count from [Rx/Active/Tx]; null if blank")
    prefixes_sent: int | None = Field(description="Tx count from [Rx/Active/Tx]; null if blank")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value):
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def uptime_matches_state(self):
        """A cross-field rule the provider can't enforce: only established
        sessions have an uptime."""
        if self.state == "established" and self.uptime_seconds is None:
            raise ValueError("an established session must have an uptime")
        if self.state != "established" and self.uptime_seconds is not None:
            raise ValueError(f"a session in state '{self.state}' cannot have an uptime")
        return self
```

Two things are new:

- **The model is asked to *compute*, not just copy.** `uptime_seconds` requires converting `0d:0h:1m:9s` to `69`. The description tells it how. Hold that thought for Step 4.
- **A `@model_validator`** checks a rule that spans two fields. No JSON schema can express "uptime must be null unless state is established." Pydantic can.

Now the parser function itself — the part worth reading twice:

```python
def parse_bgp_neighbors(raw_output: str, llm=None, max_attempts: int = 1) -> BgpNeighborList:
    llm = llm or make_llm()
    # Pass the JSON *schema*, not the class: the provider enforces the shape
    # and hands back a plain dict. Validation is our job, below.
    extractor = llm.with_structured_output(BgpNeighborList.model_json_schema())

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=raw_output if raw_output.strip() else "(the command printed nothing)"),
    ]

    for attempt in range(1, max_attempts + 1):
        data = extractor.invoke(messages)
        try:
            return BgpNeighborList.model_validate(data)
        except ValidationError as e:
            if attempt == max_attempts:
                raise
            ...  # Step 5
```

In Steps 1 and 2 we passed the *class* to `with_structured_output()` and got a validated object back in one shot. Here we pass the *JSON schema* and get a plain `dict`, then call `model_validate()` ourselves. Same result when things go well. The difference is what we're holding when things go badly: the raw dict. Step 5 uses it.

Run the parser against the real capture:

```bash
python Lab_2_Structured_Network_Data/parse_bgp.py r1_bgp.txt
```

**Expected:**
```
--- r1_bgp.txt: 15 lines of raw output

2 neighbor(s):
  10.0.0.2     ibgp-65001   AS65001  established  up=69s    rx/act/tx=[6/1/10]
  10.1.13.2    ebgp-r3      AS65002  established  up=51s    rx/act/tx=[3/3/8]
```

Banner, legend and footer ignored; uptime converted; counters split. Now the two edge cases:

```bash
python Lab_2_Structured_Network_Data/parse_bgp.py r1_bgp_degraded.txt
python Lab_2_Structured_Network_Data/parse_bgp.py r3_bgp_empty.txt
```

**Expected:** the degraded capture shows the eBGP session in `active` with `up=-` and no counters — the model correctly returned `null` where the table shows `-`, and the model validator let it through because the state isn't `established`. The empty capture returns `0 neighbor(s)`. Open that file: it's **zero bytes**. SR Linux prints nothing at all when a node has no BGP neighbors. The parser's system prompt covers that case explicitly, and the model returns an empty list rather than inventing a neighbor.

> **Where did these captures come from?** `golden/README.md` lists every file. They were taken from the live topology with the exact commands Lab 3 will have you run. Nothing was typed in or trimmed. The degraded one was captured with r3's neighbor statement deliberately removed.

---

## Step 4: Your first eval

You now have a parser that produces valid objects. **Valid is not the same as right.** The schema will happily accept `uptime_seconds=31` for a session whose uptime was 51 seconds. Nothing in Pydantic knows what the answer *should* be.

Something has to. Open `golden/expected.json`:

```bash
head -8 Lab_2_Structured_Network_Data/golden/expected.json
```

It's an answer key: for each of the five captures, every neighbor's eight fields, verified by hand against the raw output. Uptime converted to seconds by a human with a calculator. This is the smallest honest eval dataset there is, and building it took ten minutes.

> **Heads up — this file is already in the repo.** `eval_parser.py` is here in this lab folder.

`eval_parser.py` runs `parse_bgp_neighbors()` over all five files and compares against the key. It reports two things separately, and the separation is the lesson:

- **Structural:** did the output validate at all? (Did Pydantic raise?)
- **Correctness:** of the fields that validated, how many match the answer key?

Run it:

```bash
python Lab_2_Structured_Network_Data/eval_parser.py
```

**Expected:**
```
Model: cloud gpt-6-luna   attempts: 1   cases: 5

file                   struct   fields      time  notes
------------------------------------------------------------------------------
r1_bgp.txt             ok       16/16      2.1s  ok
r1_bgp_degraded.txt    ok       16/16      2.0s  ok
r2_bgp.txt             ok        8/8       1.6s  ok
r3_bgp.txt             ok        8/8       1.6s  ok
r3_bgp_empty.txt       ok        0/0       1.3s  ok
------------------------------------------------------------------------------
structural: 5/5 files validated    correctness: 48/48 fields (100%)    total time: 9s
```

Five files, 48 field comparisons, under ten seconds, a number at the bottom. Congratulations: you have an eval. It's small, it's local, it's deterministic, and you can run it after every change to the schema, the prompt, or the model and know in ten seconds whether you broke something.

**Why this matters more than it looks.** Every "does the LLM part of my tool actually work?" question you will ever be asked at work has this shape: a set of inputs, a set of known-good outputs, a script that compares them, a number. Lab 5 moves this exact idea onto a platform that can run it continuously against live traffic, with an LLM as the judge when there's no answer key. The idea doesn't change. Start here.

---

## Step 5: Retries — and the case the schema can't catch

Everything passed, which is pleasant and uninformative. Let's point the eval at a model that will struggle. `--local` swaps in the 4B-parameter Qwen model from Lab 1, thinking off. The whole local run takes about four minutes, so start with the one file that matters:

```bash
python Lab_2_Structured_Network_Data/eval_parser.py --local --only r1_bgp_degraded.txt
```

**Expected:** about a minute, then:

```
r1_bgp_degraded.txt    FAIL     -          64.1s  1 validation error(s): Value error, a session in state 'active' cannot have an uptime
------------------------------------------------------------------------------
structural: 0/1 files validated    correctness: 0/16 fields (0%)    total time: 64s
```

The model gave the `active` session `uptime_seconds: 0` instead of `null`. The `@model_validator` from Step 3 rejected it. Pydantic raised. The eval marked the file `FAIL` rather than scoring a wrong value. That's the contract doing its job.

It's also a failure the model can be *told about*. Look at what the loop in `parse_bgp_neighbors()` does when `max_attempts` is more than one:

```python
        except ValidationError as e:
            if attempt == max_attempts:
                raise
            print(f"    attempt {attempt} failed validation "
                  f"({e.error_count()} error(s)) — retrying", file=sys.stderr)
            messages += [
                AIMessage(content=json.dumps(data)),
                HumanMessage(content=RETRY_PROMPT.format(errors=e)),
            ]
```

It appends the model's own JSON to the conversation as an assistant turn, then the Pydantic error text wrapped in `RETRY_PROMPT` as the next human turn, and asks again. The model sees exactly what it said and exactly which rule it broke. This is why extraction and validation were kept separate in Step 3: with the one-shot `with_structured_output(BgpNeighborList)` form, the exception fires inside LangChain and you never get the raw dict to send back.

Open `parse_bgp.py` and read `RETRY_PROMPT`. It does one thing beyond quoting the error: it reminds the model that a dash in the table means `null`, never `0`. Small models need the rule restated, not just the violation named. Now allow retries:

```bash
python Lab_2_Structured_Network_Data/eval_parser.py --local --only r1_bgp_degraded.txt --attempts 3
```

**Expected:** two to three minutes, and something like:

```
    attempt 1 failed validation (1 error(s)) — retrying
r1_bgp_degraded.txt    ok       15/16     159.0s  MISMATCH
                                                    - 10.0.0.2.uptime_seconds: expected 71, got 67
------------------------------------------------------------------------------
structural: 1/1 files validated    correctness: 15/16 fields (94%)    total time: 159s
```

Read that carefully, because it's two lessons in one line.

**Lesson 1 — the retry worked.** Attempt one broke the uptime rule; attempt two didn't. `struct` went from `FAIL` to `ok`. The contract caught the error, the feedback loop fixed it, and no human was involved.

**Lesson 2 — valid is still not right.** The validated output has the *established* session's uptime as `67` when the table says `0d:0h:1m:11s`, which is 71. That's an integer, it's non-negative, the session is established so an uptime is expected — the schema is completely satisfied. It's just wrong. **No schema catches this, and no retry fires**, because nothing failed. Only the answer key sees it. On other runs you may instead see the `active` session's three prefix counters come back as `0` rather than `null` — same category: structurally fine, factually wrong, invisible to Pydantic.

Retries fix contract violations. They cannot fix confident wrong answers. The eval sees both; the schema sees only one. And when the eval shows you a *pattern* of wrong-but-valid values, the move is to **tighten the contract** so the next retry can fix them too — for the prefix counters, that's one more clause in `uptime_matches_state` requiring them to be `null` whenever the state isn't `established`. Eval finds, contract tightens, eval re-runs. That loop is the job.

> **Optional, over the break:** the full local run. `python eval_parser.py --local --attempts 3` takes six to seven minutes on four cores. When we ran it, the cloud model scored 48/48 in 8 seconds and the local model landed in the mid-60s percent, with the two failure kinds above spread across files. Whether that's "good enough" depends entirely on what the parser is for — and now you have the number to argue with.

> **Reasonable question: why not just use the cloud model and skip all this?** For this task, you probably should — and the eval is what lets you say so with a number rather than a feeling. But the loop costs nothing when the model is good (zero retries, zero extra tokens), and it's what makes a weaker, cheaper, or on-prem model *usable* when the data can't leave the building. Lab 1's framework was "the smallest model that's good enough." The eval is how you find out what "good enough" is.

---

## Step 6: Context injection — correctness from reference data

Schemas give you a clean *shape*. The golden set tells you when a *value* is wrong. Neither helps the model know what a BGP state *means*. If you ask for a diagnosis and the model misremembers what `active` indicates, you'll get a confidently wrong sentence in a beautifully validated object.

The cheapest fix: paste the reference material into the prompt. This is Retrieval-Augmented Generation with the retrieval done by hand.

> **Heads up — this file is already in the repo.** `analyzer.py` is here in this lab folder. Lab 3's tool is built on this exact schema — the `diagnosis` field is what the agent reads back to the user.

The relevant parts of `analyzer.py`:

```python
BGP_REFERENCE = """
BGP session states, per RFC 4271:
- idle:        starting state, no resources allocated
- connect:     trying to complete TCP/179 connection to peer
- active:      TCP connection failed, retrying. Usually indicates the
               peer is not configured to accept this session — check
               peer-side config, not local reachability.
- opensent:    TCP up, OPEN message sent, waiting for peer's OPEN
- openconfirm: peer's OPEN accepted, waiting for KEEPALIVE
- established: session up, prefixes are being exchanged
"""


class BgpNeighbor(BaseModel):
    peer_ip: str = Field(description="IP address of the BGP peer")
    group: str = Field(description="Peer group name")
    peer_as: int = Field(description="Peer AS number")
    state: str = Field(description="BGP session state")
    diagnosis: str = Field(
        description="One-sentence explanation of what this state means "
                    "operationally, citing the reference data."
    )


SYSTEM_PROMPT = f"""You are a network engineer parsing SR Linux BGP output.

Use this reference to diagnose each session:
{BGP_REFERENCE}

If you don't have enough information to diagnose, say "insufficient data" — do not guess.
"""
```

Run it:

```bash
python Lab_2_Structured_Network_Data/analyzer.py
```

**Expected:**
```
10.0.0.2 (established, AS65001)
  → The BGP session is up and prefixes are being exchanged.

10.1.13.2 (active, AS65002)
  → TCP connection failed and is being retried; check whether the peer is configured to accept this session.
```

The second diagnosis is lifted almost verbatim from the reference. That's the point: the model isn't recalling BGP from training, it's *reading* the definition you gave it.

**Try the experiment:** comment out the `Use this reference to diagnose each session:\n{BGP_REFERENCE}` lines in `SYSTEM_PROMPT`, re-run, and compare. Current models usually still get `active` roughly right — it's well-represented in training data — but the wording drifts, and on anything vendor-specific or internal to your company the model has nothing to draw on. Reference data is how you give it something.

> **How would you eval this?** There's no single right sentence for a diagnosis, so `expected.json` can't hold one. This is where Lab 5's *LLM-as-judge* comes in: a second model grades the diagnosis against the reference text on a rubric. Different mechanism, same question — "is this output right?" — asked at scale.

---

## Going Further

If you finish the core lab early:

### 1. The other direction — validate *generated* config

Parsing is text → schema. Generation is schema → text, and it's scarier, because a plausible-looking `set` line that's subtly wrong gets *committed*. Check it the same way: with code.

> **Heads up — this file is already in the repo.** `config_roundtrip.py` is here in this lab folder.

The idea in one diagram:

```
  intent (Pydantic)  --LLM-->  SR Linux 'set' lines  --regex-->  intent again
                                                                     |
                                                must equal the original
```

```bash
python Lab_2_Structured_Network_Data/config_roundtrip.py
```

**Expected:** three generated `set` lines for an eBGP peer, then `ROUND-TRIP OK — the config says what we meant.` Read `parse_back()`: it's two regular expressions and no LLM. The validator for *generated* text doesn't need to be clever, it needs to be deterministic. Try changing the intent to `peer_as=65003` and confirm the round-trip still holds; then break `SYSTEM_PROMPT` so the model emits the neighbor line without the group line and watch `parse_back()` refuse it. Lab 4's UI generates config the same way — now you know how to check it.

### 2. Three devices, one prompt, one planted fault

Single-device parsing is table stakes. The interesting questions span devices. `golden/` has the routing-relevant config of all three nodes (~40 lines each) plus a version of r3's with its eBGP neighbor line missing.

> **Heads up — this file is already in the repo.** `consistency_check.py` is here in this lab folder.

```bash
python Lab_2_Structured_Network_Data/consistency_check.py             # healthy trio
python Lab_2_Structured_Network_Data/consistency_check.py --broken    # r3 missing its neighbor
```

**Expected (healthy):** `Context used: ~2400 input tokens`, then a list of `ok` findings — iBGP matches, eBGP matches, both /30s pair up, OSPF on the right link — and no errors.

**Expected (broken, effort none):** the model notices *something* — `BGP sessions the configs intend to form: 2` instead of 3 — but typically **does not report an error** about the missing line. It's holding three configs, cross-referencing neighbor statements against peer ASes against subnets, and at `reasoning_effort="none"` it loses the thread.

Now:

```bash
python Lab_2_Structured_Network_Data/consistency_check.py --broken --effort high
```

**Expected:** an `ERROR r1+r3` finding quoting r1's neighbor line and stating that r3 has no matching statement. This is Lab 1's reasoning dial, on a question that finally deserves it: multi-device, multi-step, and the kind of thing you'd actually want a co-pilot to catch in a change review.

Two more things to try. Delete the "Design intent" paragraph from `SYSTEM_PROMPT` and re-run the healthy trio: the model, not knowing r3 is an external AS, will usually flag the r1–r3 link for missing OSPF. Intent is context, and the model can't infer yours. Then run with `--full` to send the *complete* running configs (~680 lines each, mostly ACL and system defaults):

```bash
python Lab_2_Structured_Network_Data/consistency_check.py --full
```

**Expected:** `Context used: ~51,000 input tokens`. The cloud model has a million-token window and doesn't blink. The local model's window is 40,960 — this prompt doesn't fit. "Just send everything" is a cloud-model habit; the local model makes you decide what matters, which is usually the better engineering anyway.

### 3. "Say I don't know" — explicit anti-hallucination

`analyzer.py`'s system prompt ends with `do not guess`. Remove it, then feed the analyzer a deliberately under-specified input — an empty string, or a single row with the state column blank. Compare with and without the instruction. Then add a row with a state that isn't in the reference (`"flapping"`) and see whether the model says `insufficient data` or invents a definition.

### 4. Does reasoning help extraction?

`parse_bgp.py` runs at `reasoning_effort="none"`. Change `make_llm()` to use `"high"` and re-run `eval_parser.py`. Compare the score and the total time. For pure extraction from a well-formed table, you'll usually find the dial buys nothing but latency — which is a useful thing to be able to say with a number. Then try the same on the local model (`reasoning=True` in `make_llm`) and budget ten minutes.

### 5. Cross-vendor parsing

Ask the cloud model to generate a plausible Cisco IOS `show ip bgp summary` output for the same three-router topology. Save it as `golden/r1_bgp_ios.txt` and run `parse_bgp.py` against it. The schema is vendor-neutral — `peer_ip`, `peer_as`, `state` mean the same thing everywhere — but the system prompt says "SR Linux." Generalize the prompt, add the IOS file and a hand-verified entry to `expected.json`, and you've got a multi-vendor parser *and* the eval that proves it. This is one of the most realistic uses of the whole pattern: different routers, same downstream object.

---

## What's next

In **Lab 3 (LangChain Network Agent with LangGraph)**, `parse_bgp_neighbors()` becomes a *tool*. Instead of you calling it with a file name, an agent decides when to call it, which node to ask about, and what to do with the answer — and you'll watch that decision happen step by step in a LangGraph trace. The schema discipline you built here is what makes the tool's output safe for the agent to reason over.
