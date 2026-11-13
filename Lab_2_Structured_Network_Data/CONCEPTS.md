# Lab 2 Concepts: Structuring Network Data with Pydantic

> 10-15 min introduction before hands-on starts.

## The big picture

Lab 1 ended on a cliff. You gave the model one example of the JSON you wanted and it obliged — three runs, three identical outputs. Then the README said: *that's a hint, not a contract.* Nothing guaranteed the fourth run. Nothing guaranteed `peer_as` was an integer. Nothing checked that the number was *right*.

Lab 2 is about closing that gap in three moves:

1. **Contract.** A Pydantic schema the model must satisfy, enforced partly by the provider and partly by your code.
2. **Validation.** Types, ranges, allowed values, cross-field rules — and a retry loop for when the model breaks one.
3. **Eval.** A handful of real captures with hand-verified answers, and a script that scores the parser against them.

By the end you'll have a `parse_bgp_neighbors()` function that Lab 3 can hand to an agent without fear, and a ten-second test that tells you when you've broken it.

## From "vibe prompting" to a contract

**Vibe prompting:**

> *"Hey AI, here's some BGP output, give me the neighbors."*

Output varies every run. Code that parses it is brittle. Six months later nobody can say why production is flaky.

**A contract:**

> *"Return a list of objects matching this schema: `peer_ip` is an IPv4 address, `peer_as` is an integer between 1 and 2³²−1, `state` is one of these six strings, and if `state` isn't `established` then `uptime_seconds` must be null."*

The first half of that sentence the *provider* enforces — it won't let the model emit JSON of the wrong shape. The second half, the cross-field rule, only *your code* can enforce. Pydantic does both halves with one class definition.

## Extraction and validation are two different jobs

This is the single idea to carry out of the lab:

```
   raw text ──► [ MODEL: extraction ] ──► JSON dict ──► [ PYDANTIC: validation ] ──► object
                  "match this shape"                      "obey these rules"
                  provider's job                          your job
```

Keep them separate and three things fall out for free:

- **You can read the errors.** Pydantic tells you which field, what rule, all failures at once.
- **You can retry intelligently.** You still hold the raw JSON, so you can show the model what it said and which rule it broke. That's a far better retry than "try again."
- **You can swap the model.** The validation layer doesn't care who did the extraction. Cloud, local, next year's model — the contract is the same.

## Structural correctness is not correctness

Here's the trap. A schema can guarantee that `uptime_seconds` is a non-negative integer. It cannot know that the right integer was 51. The model can return 31, satisfy every rule, and be wrong.

The only thing that catches that is an **answer key**: inputs you've already seen, outputs you've already verified, and a comparison. That's an eval. Ours is five real router captures and a 40-line JSON file, and it runs in ten seconds.

```
                    ┌──────────────┐          ┌──────────────┐
   parser output ──►│  STRUCTURAL  │── ok ──► │ CORRECTNESS  │──► score
                    │  (Pydantic)  │          │ (answer key) │
                    └──────┬───────┘          └──────┬───────┘
                           │ raise                   │ mismatch
                           ▼                         ▼
                      retry it                  fix the prompt,
                                                the schema, or
                                                the model choice
```

Two layers, two different failure modes, two different fixes. Lab 5 takes this picture and puts it on a platform that runs continuously, with an LLM as the judge when there's no answer key. The picture doesn't change.

## A word about RAG

Step 6's context injection is **Retrieval-Augmented Generation** in its simplest form: the reference text is pasted into the prompt by hand. "Real" RAG embeds your documents into a vector database and retrieves the relevant ones at query time. We skip the retrieval mechanics — the `bonus/rag/` folder has them — because the prompting half is identical, and that's the half that decides whether the answer is grounded.

## Why this matters at work

Every production LLM feature you've seen is built on these primitives. A ticketing bot that files structured incidents: schema. A config generator that gets reviewed before commit: round-trip validation (Going Further #1). A change-review assistant that cross-checks three devices: context injection plus a reasoning budget (Going Further #2). None of it is exotic. All of it is Lab 2.

And every one of those features will eventually face the question *"how do you know it works?"* The honest answer is never "we tried it a few times." It's a number, from an eval, that you can re-run.

## Where this fits in the workshop arc

The Lab 2 parser becomes the first **tool** in Lab 3's agent. The Lab 2 golden set becomes a **dataset** on Lab 5's evaluation platform (Going Further #1 scores this same parser there). Whatever discipline you build here, both of those inherit.

Spend the 35-40 minutes. It pays back twice.
