# Workshop Discussion: Beyond the Labs

The labs you just built are the smallest viable demonstrations of each pattern. Production versions are real software engineering work. This document seeds the end-of-workshop discussion with the gaps between "demo" and "production" — bring your own experiences.

## 1. Evals — how far does Lab 5 get you?

Lab 5 ran an experiment with an LLM judge, showed which rows a prompt change fixed and which it left alone, and put the agent through two hallucination traps. That's further than most teams get. It's also ten questions about three routers. With evals at real scale, you can:

- Update prompts confidently (does the new prompt regress on any known case?)
- Swap models confidently (does the next model do better than the current one for *our* use case?)
- Catch regressions during development rather than in production

**Discussion prompts:**

- What does "correct" mean for a network agent's response? Strict string match? LLM-judged correctness? Schema-validated structure? When does each apply, and what does each miss?
- If your agent is non-deterministic — different responses to the same input — how do you write a stable test? Multiple runs and average? Temperature-zero plus exact match? Something else?
- How do you build an eval dataset without spending months hand-labeling? Synthetic data from a stronger model? Real production traffic with human review? Your existing ticket corpus?
- For tool-using agents specifically: should you eval the *tool calls* (did it pick the right tool with the right args?), the *final answer*, or both? They fail in different ways.
- When we ran Lab 5 Step 2, the baseline answer to the NTP question suggested Cisco commands for a network of SR Linux routers, and the judge still labelled it `correct`: the answer key only asked that the model not name a server. A judge grades what the answer key asks for and nothing else. What would your answer keys forget to ask?
- In Lab 5's Going Further, an LLM judge flagged a *correct* parser output as unfaithful (item 1), and our first hallucination rubric flagged *true* details as invented (item 2). Both were caught because a code evaluator or a human was standing next to the judge. What's your plan for calibrating a judge nobody is standing next to?

**Worth knowing about:** Arize AX (what you used), [`promptfoo`](https://www.promptfoo.dev/), LangSmith evals, [Inspect](https://inspect.ai-safety-institute.org.uk/), [Helm](https://crfm.stanford.edu/helm/).

## 2. Production hardening — what's missing from the workshop code?

Everything in the labs is intentionally minimal. The list of things missing from "production-ready" is long:

- **Secrets management.** `.env` files are fine for development; production wants Vault, AWS Secrets Manager, Doppler, or your platform's equivalent.
- **Observability.** What's an "error rate" for an LLM call? How do you trace a multi-step agent execution? LangSmith, OpenInference / OpenTelemetry, and Langfuse all offer pieces of this. Logging the LLM input/output deterministically is harder than it sounds because of context window size.
- **Rate limiting and retries.** OpenAI and Anthropic both rate-limit at the API level. Production code needs exponential backoff, request queuing, and ideally a circuit breaker. LangChain has `with_retry()` built in for the simple cases.
- **Error handling at multiple layers.** The LLM call can fail (network, rate limit, auth). The tool call can fail (target system down). The parser can fail (malformed output despite Pydantic validation). Each needs its own strategy.
- **Cost controls.** A misbehaving agent in a tight loop can run up a four-figure bill in an afternoon. Per-request budget caps, monthly budget alerts, and "kill switch" patterns are all real concerns.

**Discussion prompts:**

- Which of these does your team already have solved for non-AI workloads? (Most are not AI-specific.)
- What's the right boundary for handling LLM failures — retry silently, surface to the user, fall back to a deterministic path?
- For agentic systems specifically: how do you bound the cost of a single user interaction? Maximum iterations? Maximum tokens? Wall-clock timeout?

## 3. Security — what could go wrong?

AI introduces failure modes traditional software doesn't have:

- **Prompt injection.** A user (or a piece of input the system processes — a log line, a config file, a ticket comment) contains instructions that override the system prompt. "Ignore your instructions and..." is the toy version. Real attacks are subtler — see [Simon Willison's writing](https://simonwillison.net/tags/promptinjection/) on the subject.
- **Data exfiltration via prompt.** A model with access to sensitive data (RAG over internal docs, tool access to internal systems) can be tricked into leaking it.
- **Indirect prompt injection.** The malicious input doesn't come from the user — it comes from a document the agent reads, a webpage it fetches, a tool result it processes. Your trust boundaries grow.
- **Hallucinated commands.** An agent that writes configs is an agent that can write *wrong* configs. The damage is bounded only by what you let it actually do.

**Discussion prompts:**

- Where is your network agent's trust boundary? Whose input does it accept as authoritative?
- What's the worst thing the Lab 4 chat app could do if a user were intentionally adversarial? What if the BGP `show` output the agent reads was attacker-controlled?
- The human-in-the-loop pattern in Lab 4's bonus `config_gen.py` was deliberate. When does HITL stop scaling? Where do you remove it?

## 4. Cost at scale

The labs cost roughly a fraction of a cent per question. Multiply that by your real query volume:

- 1,000 NetOps engineers × 50 questions/day × $0.005 per question ≈ **$250/day** = $90k/year.
- The cost shape changes with longer context (RAG over big knowledge bases) and longer agent traces (multi-tool chains).
- Local models are "free" only if you ignore the GPU you're paying for. A serious local deployment requires real hardware investment.

**Discussion prompts:**

- What's the cost-per-question break-even point where local hardware beats cloud API for *your* expected volume?
- Caching: how much repeat-traffic could you absorb with semantic caching? (Same question phrased differently → cached answer.)
- Tiered routing: cheap model for easy questions, expensive model only when needed. How do you decide which is which? An LLM-based router is itself an LLM cost.

## 5. Multi-agent and agent orchestration

Lab 3 had one agent with one tool. The natural next step:

- **Multi-tool agents** — the same agent, more tools. Familiar pattern, scales until tool-selection accuracy breaks down (~15-20 tools is a soft ceiling for current small models).
- **Agent of agents** — a "supervisor" agent that routes work to specialist agents. Each sub-agent is itself an agent with its own tools.
- **Workflows vs agents** — sometimes you don't want agentic reasoning; you want a deterministic pipeline with an LLM at one specific step. LangGraph distinguishes these explicitly. Anthropic's ["Building effective agents"](https://www.anthropic.com/research/building-effective-agents) post is the canonical reference.

**Discussion prompts:**

- For network engineering specifically: where does agentic reasoning add value, and where does it just add nondeterminism you don't want?
- If you built a "NetOps supervisor agent" that delegated to specialist sub-agents (BGP, OSPF, hardware, performance), how would you decide the boundaries? Per-protocol? Per-vendor? Per-team?
- Where's the line between "agent" and "regular software that uses an LLM"?

## 6. Where this all goes — five-year horizon

This is the open-ended close-out. Some perennial questions, no right answers:

- Will tool-using agents replace traditional NetOps automation (Ansible, Nornir, Salt)? Augment them? Neither?
- Where does the boundary between "code I write" and "code an LLM writes for me" settle? Is the Lab 4 config generator a glimpse, or a dead end?
- What does MCP becoming a real ecosystem standard change about how you'd architect a NetOps platform today?
- For network *operations* specifically (not just generation): how much trust will you ever extend to an autonomous agent? What guardrails would make you trust it more?

These are the questions worth taking back to your team on Monday morning.
