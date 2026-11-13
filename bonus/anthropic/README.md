# Bonus: Anthropic — Same Workshop, Different Provider

**Time:** ~5 min
**Prerequisites:** Lab 3 or Lab 4 completed.

The talk is called "Choose Your Own AI Adventure." This is the smallest possible demonstration of why — swap OpenAI for Anthropic Claude in code you've already written, and see what changes.

## Why bother?

Three reasons to know how to swap providers:

1. **Vendor risk.** Single-provider dependency is a real production concern. Outages happen; pricing changes; terms of service change. Knowing your code works against two providers is the cheapest insurance.
2. **Capability differences.** No two models are identical. Claude is often noticeably stronger on long-context reasoning and following complex instructions; GPT models often shine on raw speed and cost at the small end. Empirical comparison on *your* workload beats marketing benchmarks.
3. **The talk's framing.** "Choose Your Own AI Adventure" only works if you've actually walked through more than one adventure. This is the cheapest second adventure.

## Setup

```bash
pip install langchain-anthropic
```

No version pin needed: the workshop image is on the LangChain 1.x line, and so is the current `langchain-anthropic`.

Get an Anthropic API key:

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Add some credit (~$5 will more than cover this lab; the small Claude models are inexpensive)
3. Generate an API key
4. Add to your `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

## The swap

Open `Lab_3_LangChain_Network_Agent/agent.py`. The whole provider choice lives in one function:

```python
def make_llm(local: bool = False, effort: str = "low"):
    if local:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=LOCAL_MODEL, reasoning=False)
    return ChatOpenAI(model=CLOUD_MODEL, use_responses_api=True, reasoning={"effort": effort})
```

Change the last line to:

```python
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model="claude-haiku-5-5")
```

Re-run `python Lab_3_LangChain_Network_Agent/agent.py`. That's it — same tools, same prompt, same questions, different brain. Because Lab 4's `chat_app.py` imports `build_agent()` from the same file, the Streamlit app switched too. (Lab 2's parser still runs on OpenAI; it has its own `make_llm` in `parse_bgp.py` if you want to swap that as well.)

> **Model strings.** `claude-haiku-5-5` is the current Haiku-tier model — the same price bracket as `gpt-6-luna` ($0.10 in / $0.50 out per million tokens). If it errors with "model not found," check Anthropic's models page and use the current Haiku identifier. Don't pass `temperature`: like GPT-6, current Claude models reject non-default sampling settings and expose a reasoning/effort control instead.

> **No `use_responses_api` here.** That flag was OpenAI-specific plumbing for GPT-6 tool calling. Anthropic tool calling works through its standard Messages API; LangChain hides the difference, which is the point of the exercise.

## What to compare

Run the same four questions from Lab 3 with both providers. Notice:

- **Tone and style.** Claude tends to be more cautious and explanatory; GPT tends to be more direct. Neither is "better" — they're different.
- **Tool-calling reliability.** Both small-tier models handle Lab 3's tool calls well, including issuing the two "compare" calls in one turn. Bigger models on either side (Sonnet/Opus, or the larger GPT-6 tiers) handle long multi-tool chains more reliably — Lab 5's experiment harness is how you'd measure that rather than assert it.
- **Latency.** First-token latency is roughly comparable. Total response time varies more by question than by provider.
- **Cost per call.** Both pricing tiers are similar at the small-model level. Pricing structures differ — Anthropic charges per million input/output tokens, OpenAI similarly. Check current rates.

## Going Further

### 1. Run all five labs against Claude

Lab 1 (raw API calls) needs the most adaptation — Anthropic's Messages API has a different shape from OpenAI's Chat Completions. The LangChain wrapper hides this; the raw SDK doesn't. Worth looking at both side-by-side to understand the abstraction LangChain provides. Lab 1 Step 6's reasoning dial maps to Anthropic's `effort` setting (low → max) rather than `reasoning_effort`.

### 2. Mix providers within one agent

There's no rule that says "all the LLM calls in your pipeline must come from one provider." A common pattern: use a frontier model for the high-stakes reasoning step and a cheaper model (`gpt-6-luna`, `claude-haiku-5-5`, or the local Qwen) for auxiliary tasks like extraction or formatting — Lab 3 already does a version of this, with the parser inside the tool on a cheaper setting than the agent. The agent code doesn't care.

### 3. Try Anthropic's prompt caching

Anthropic supports prompt caching — repeating the same large system prompt across many calls becomes much cheaper because the prompt is cached server-side. For agents with long static context (large tool descriptions, big reference docs), this is a significant cost reduction. See the `cache_control` parameter in LangChain's `ChatAnthropic`.

### 4. Build a provider abstraction layer

For production, you probably want to encapsulate the choice of provider behind your own interface — `get_llm(name)` returning a unified object. This makes A/B testing painless and removes the provider mention from your business logic. LiteLLM, LangChain's own routing, and OpenRouter are three off-the-shelf options.
