# Lab 1 Concepts: Foundations

> 10-15 min introduction before hands-on starts.

## The big picture

You've all used ChatGPT in a browser. What you're about to do is the same conversation — but happening inside your code. Programmatically, repeatably, automatable. That shift is the entire workshop, and it starts here.

Lab 1 gets the basics right:

- How does my code actually talk to an LLM?
- What's the difference between running one locally vs. calling one in the cloud?
- What is this "reasoning" thing every model now advertises, and what does it cost me?
- What happens when I stop asking questions and start feeding the model *data*?

By Lab 1's end you'll have made calls to both Ollama (local, on your Codespace) and OpenAI (cloud), worked the reasoning dial on each, written exactly one Python script that talks to either, and watched a naive prompt fall apart on real router output.

## Two kinds of LLMs: local vs cloud

|                          | **Local (Ollama)**         | **Cloud (OpenAI)**          |
|--------------------------|----------------------------|-----------------------------|
| Where the model runs     | Your machine               | Their data centers          |
| Cost per call            | Free (electricity only)    | Per-token, pennies-to-$$$   |
| Speed                    | Bound by your CPU/GPU      | Fast — they have GPUs       |
| Quality                  | Smaller models, weaker     | Frontier models, sharper    |
| Data leaves your network | No                         | Yes                         |
| Network required         | No (after first download)  | Yes, always                 |
| Privacy / sovereignty    | Total control              | Trust their data policies   |
| Reasoning                | A toggle; you can read it  | A dial; you can only bill it|

This isn't "local good, cloud bad" or vice-versa. It's a series of trade-offs you make per task, per data sensitivity, per latency budget, per dollar budget.

The framework I want you to leave the workshop with:

> **Pick the smallest LLM that's good enough for the task, running as close to your data as the data's sensitivity demands — and turn its reasoning up only as far as the question needs.**

That sentence shapes every decision in the rest of the workshop.

## The "same shape" promise

Here's what makes this practical: both Ollama and OpenAI expose chat-completion APIs that look the same.

Same `messages` array structure (`{role: "user", content: "..."}`). Same response shape (`choices[0].message.content`). Same basic invocation pattern. This isn't an accident — Ollama deliberately mirrors OpenAI's API surface.

What this means for your application code:

```
                  ┌──────────────────────────┐
   Your code ────►│       LangChain          │
                  │  (one interface for      │
                  │   any LLM provider)      │
                  └─────┬──────────┬─────────┘
                        │          │
                  ┌─────▼────┐ ┌───▼──────────┐
                  │  Ollama  │ │  OpenAI      │
                  │ (local)  │ │  (cloud)     │
                  └──────────┘ └──────────────┘
```

Two providers, one interface. You pick at runtime, based on the task.

## Reasoning is a dial, not a feature

A year or two ago "reasoning model" meant a separate, expensive product. Today it's a setting on the model you're already using. Before it writes an answer, the model can write a private scratchpad — restating the question, listing what it knows, checking itself — and then answer. You never see the scratchpad on a cloud provider. You *do* pay for it: those are output tokens.

Three things to internalize, because the labs lean on them:

1. **It defaults to on.** Today's cloud model ships at `reasoning_effort="medium"`. Ask it for one sentence about OSPF and it will spend ~45 tokens thinking first. Multiply by every call your agent makes in Lab 3.
2. **It's worth it for multi-step questions, and worthless for lookups.** "What's the OSPF hello interval?" gains nothing. "Given this topology, will r2 re-advertise this prefix?" gains a lot. The skill is matching the dial to the question.
3. **Locally, you can read it.** Our local model is a *hybrid* — thinking on or off — and when it's on, Ollama hands you the thinking text. That's the most honest view you'll get all day of what an LLM does between prompt and answer, and it's why we picked this model over a faster one.

The vocabulary differs per provider (`reasoning_effort` on OpenAI, `think` on Ollama, `effort` on Anthropic) but the concept is identical, and LangChain hides the spelling inside the constructor.

## From questions to data

The first half of Lab 1 is "ask a question, read the answer." The second half flips it: the model becomes a **component in a pipeline**. Raw SR Linux output goes in; something your code can use comes out. That changes what "good output" means — "correct" is no longer enough, it has to be *predictable*.

You'll see a naive prompt produce a different format on every run, and a single worked example (few-shot) stabilize it. That's the cheapest prompt-engineering trick there is, and also the limit of what prompting alone can promise you. Lab 2 picks up exactly there.

## Why this matters at work

The talk's framing comes from real choices teams make every day:

- **Logs that mention customer names** → can't go to a cloud LLM without legal review. Local model.
- **Marketing copy for next quarter's release** → no sensitive data, cloud LLM is fine, you want the best quality you can get.
- **A 3 AM on-call query about a routing issue** → speed matters more than perfect quality. Reasoning off, whichever responds first wins.
- **A change-review question with six interacting policies** → reasoning up, latency be damned.

Once you've made a clean call to both in this lab, you've earned the right to have an opinion about which one to use, when — and how hard to let it think. That opinion is the real takeaway.

## Where this fits in the workshop arc

Lab 1 is foundation. Every subsequent lab calls an LLM — Lab 2 puts a schema contract around it, Lab 3 wraps it in an agent, Lab 4 wraps the agent in a UI, and Lab 5 asks the question that makes all of it defensible: *how do I know it's right?* We won't measure anything today beyond tokens and seconds. But notice, as you go, every place you find yourself eyeballing an answer and thinking "that looks about right." Lab 5 is where we stop eyeballing.

Spend the 35-40 minutes here getting comfortable with the basics. The rest of the workshop is recipes built on this base.
