# Bonus material

Optional content for after the five labs. Less polished than Labs 1–5 by design — these exist to give early finishers somewhere to go, and to seed the "as time allows" discussion at the end of the workshop.

(Three things that were bonus material at AutoCon 5 — conversation memory, tracing, and evals — are now *in* the labs: Lab 4 Step 6, Lab 3 Step 5, and all of Lab 5. What's left here is what still earns a separate folder.)

## What's here

| | Type | Time | What it shows |
|--|------|------|---------------|
| [mcp/](mcp/) | Hands-on | ~15 min | Reimplement Lab 3's BGP tool as a Model Context Protocol server. Same capability, different boundary. |
| [rag/](rag/) | Hands-on | ~15 min | Replace Lab 2's hardcoded `BGP_REFERENCE` with a small vector store and retrieval over real network reference docs. |
| [anthropic/](anthropic/) | Mini-lab | ~5 min | Swap OpenAI for Anthropic Claude in the Lab 3 agent (and so Lab 4). One function. |
| [DISCUSSION.md](DISCUSSION.md) | Conversation | varies | Prompts for the end-of-workshop discussion: evals, production hardening, security, cost, multi-agent patterns. |

## A note on polish

The main labs are workshop-bulletproof. These bonus items are deliberately lighter: shorter READMEs, fewer guard-rails, more "here's the idea + code + try it." If something doesn't run cleanly on your environment, that's usually interesting — the failure modes here are part of the lesson.

Production-quality versions of all four topics are real software engineering work. What lives in this folder is the smallest viable demonstration that shows you the shape of each pattern.
