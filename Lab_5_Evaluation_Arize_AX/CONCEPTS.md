# Lab 5 Concepts: Application Evaluation with Arize AX

> 10-15 min introduction before hands-on starts.

## The big picture

Four labs in, you have a working network co-pilot. You've watched it answer correctly a few dozen times. That is not evidence. That is anecdote, and the first time it confidently invents a BGP neighbor in front of your director, "it worked when I tried it" is going to be a bad sentence.

Lab 5 is about replacing that sentence with a number. Not one number — a few, each answering a different version of the question *is it right?*:

- **On the cases we know the answer to?** → an experiment against a dataset with an answer key.
- **Did my change help?** → the same experiment run twice, side by side.
- **Does it make things up?** → traps in the dataset, and a judge that checks.
- **Right now, on real traffic?** → an online eval that grades every answer as it arrives.

You run the first three today: once in Arize's web UI, with a prompt, and once from code, with your agent. The fourth you read about, with screenshots from our space.

Nothing gets built today. Everything gets measured.

## The vocabulary, once

```
   TRACE        what happened          one run of the agent: every model call, every tool call,
                                       every token, every millisecond. Labs 3–4 produce these.

   EVAL         a judgement on a trace  a label + score + explanation attached to a span.
                                       "correct", 0.0, "the answer names r4, which doesn't exist."

   EVALUATOR    the thing that judges   either CODE (exact, cheap, needs an answer key)
                                       or an LLM JUDGE (flexible, fallible, needs a rubric).

   DATASET      inputs you chose        rows with inputs and (ideally) known-good outputs.
                                       Lab 2's golden set is one.

   EXPERIMENT   task × dataset × evals  run the thing on every row, score every output,
                                       keep the results so two runs can be compared.

   ONLINE EVAL  evaluator × live traffic  the evaluator runs on new traces as they land.
```

Two of these you've already made. Lab 2's `expected.json` is a dataset. Lab 2's `eval_parser.py` is an experiment with a terminal for a UI. Lab 5 does the same thing on a platform, which adds the parts a terminal can't do: LLM judges, side-by-side comparison, a history, and live traffic.

## One change, two runs

One experiment gives you a score. The score means little until there is a second one to set beside it. So the working loop is: run the task over the dataset, **change one thing**, run it again, and compare the two runs row by row.

```
   DATASET (fixed) ──┬──►  task, version 1  ──►  judge  ──►  score
                     └──►  task, version 2  ──►  judge  ──►  score
                                                              │
                                    which rows moved, and which didn't?
```

The rows that didn't move matter as much as the ones that did. A control row that stays correct says the change broke nothing. A trap row that stays correct says the change didn't make the model overconfident.

Step 2 does this with a prompt in Arize's playground. Step 3 runs the same kind of experiment from code, with your agent as the task.

## Code evaluators and LLM judges

When you have an answer key, compare in code. `FieldsMatch` from Lab 2 is exact, free, and deterministic. There is no better evaluator for data that has a right answer.

But most of what an agent produces is prose, and prose has no answer key. "r1 has two established sessions, both healthy" and "Both of r1's BGP neighbors are up" are the same answer. For that you need an **LLM judge**: a second model that reads the question, the answer, and either a rubric or the facts the answer should contain, and grades it.

Judges are useful and fallible in specific ways — they miss arithmetic more than structure, they're swayed by confident tone, and they drift when the template changes. So the discipline is: **give the judge something to check against, and then check the judge.** In Steps 2 and 3 the judge reads an answer key alongside the answer, and you read its explanation on every row that surprises you. Going Further #1 takes the next step and runs a judge next to a code evaluator on the same rows. Where they agree, you've earned the right to use the judge alone on rows that have no key.

## Online versus offline

```
   ONLINE  ──  traffic you didn't choose, as it happens.
               Tells you WHAT IS HAPPENING. Catches the Tuesday-afternoon failure.
               Becomes a dashboard, then an alert.

   OFFLINE ──  a dataset you did choose, on demand.
               Tells you WHETHER A CHANGE HELPED. Run it before a prompt edit ships.
               Becomes the regression test for your AI feature.
```

You need both. A team with only online evals finds out about regressions from users. A team with only offline evals never sees the questions real users actually ask.

Today you run the offline kind (Steps 2 and 3) and read about the online kind (Step 4).

## Hallucination is testable

"Does it hallucinate?" sounds like a philosophical question. It isn't. Ask about something that doesn't exist — a router r4, OSPF on a router that doesn't run it — and read the answer. A correct agent says *there is no r4*. A hallucinating agent describes r4's neighbors.

Two things made the correct answer possible, and both are earlier labs: the tool returned a **clear error string** instead of raising (Lab 3), and the agent was instructed to use tools rather than its own knowledge for router-specific questions (Lab 3's system prompt). The judge just verifies that the design held. Put the traps in the dataset, and hallucination becomes a row with a score.

Step 2 has a mild trap: which NTP server the routers use, which nobody wrote down. Step 3 has the two sharper ones above, aimed at an agent that has a working tool and could be tempted to use it.

## Two views of one execution, completed

Lab 4 ended with the user's view (the status box) and the engineer's view (the trace) of the same run. Lab 5 adds the third: the **evaluator's view**. The same question and answer, now with a label, a score and an explanation beside them. In an experiment the label sits on a dataset row. In production (Step 4) it sits on the trace itself. The platform is where the three meet.

## Alyx, and why it comes last

Arize ships an agent, Alyx, that builds evaluators, configures tasks and compares experiments from a sentence. It comes at the end on purpose: Step 4 describes it, and Going Further #5 has prompts to try. After half an hour of doing these things by hand you can *read* what Alyx proposes and know whether it's right — which is the only safe way to use an agent that configures your evaluation pipeline. Understanding first, acceleration second. That ordering is the workshop's whole argument about AI tooling, applied to AI tooling.

## Where this fits — the end of the arc

```
   Lab 1   models + the reasoning dial
   Lab 2   a contract, and your first eval            ◄── the answer key
   Lab 3   an agent, traced                           ◄── the traces
   Lab 4   a UI that shows the work, tags sessions    ◄── more traces, grouped
   Lab 5   experiments on an answer key · an LLM judge · comparison · traps
```

The thread: **you can't trust what you can't measure, and you can measure all of it.** That's what separates a demo from something you'd put your name on.
