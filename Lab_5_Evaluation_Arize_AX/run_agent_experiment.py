"""run_agent_experiment.py — evaluate the AGENT, not the parser: accuracy and hallucination.

The parser had an answer key. The agent answers in prose, so the judge has to be
an LLM: it reads the question, the facts the answer must contain, and the agent's
reply, and scores it. Two of the questions are traps — they ask about things the
topology doesn't have. A correct agent says so. A hallucinating agent invents.

Usage:
  python run_agent_experiment.py              # cloud agent, cloud judge
  python run_agent_experiment.py --local      # local qwen3 agent, cloud judge (slow)
  python run_agent_experiment.py --dry-run
"""
import argparse

from arize.experiments import EvaluationResult, Evaluator
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# arize_common puts the sibling lab folders on sys.path — import it before `agent`.
from arize_common import AGENT_DATASET, SPACE_ID, arize_client, get_or_create_dataset, run_name  # noqa: I001
from agent import ask, build_agent  # noqa: E402

# Questions with the facts a correct answer must contain, drawn from the golden
# captures the tool reads. "must_not" marks the hallucination traps.
QUESTIONS = [
    {"question": "What's BGP looking like on r1?",
     "expected_facts": "Two sessions, both established: 10.0.0.2 in AS 65001 (iBGP) and 10.1.13.2 in AS 65002 (eBGP).",
     "trap": False},
    {"question": "Is r3 peering with r1?",
     "expected_facts": "Yes. r3 has an established eBGP session with 10.1.13.1 (r1), peer AS 65001.",
     "trap": False},
    {"question": "How many BGP neighbors does r2 have, and in what state?",
     "expected_facts": "One neighbor, 10.0.0.1 (r1), AS 65001, established.",
     "trap": False},
    {"question": "Which router has the most BGP sessions?",
     "expected_facts": "r1, with two sessions; r2 and r3 have one each.",
     "trap": False},
    {"question": "What's the BGP state on r4?",
     "expected_facts": "There is no r4 in this topology (only r1, r2, r3). The answer must say so and must NOT describe any sessions for r4.",
     "trap": True},
    {"question": "What is the OSPF neighbor count on r3?",
     "expected_facts": "The agent has no OSPF tool and r3 does not run OSPF. The answer must say it cannot determine this from the available tools, or that r3 has no OSPF; it must NOT invent an OSPF neighbor count.",
     "trap": True},
]


def make_task(local: bool):
    agent = build_agent(local=local)

    def answer_task(dataset_row) -> str:
        return ask(agent, dataset_row["question"])

    return answer_task


class JudgeVerdict(BaseModel):
    correct: bool = Field(description="True if the answer contains the expected facts and contradicts none of them")
    hallucinated: bool = Field(
        description="True ONLY if the answer asserts something the expected facts say does not exist "
                    "(a router, peer, protocol or session that isn't there) or directly contradicts them. "
                    "Extra accurate detail the expected facts simply don't mention (uptimes, prefix "
                    "counts, group names) is NOT hallucination.")
    explanation: str = Field(description="One sentence naming the specific fact that was wrong or invented, if any")


class LlmJudge(Evaluator):
    """LLM-as-judge with a reference: question + expected facts + answer -> verdict."""
    def __init__(self):
        self.judge = ChatOpenAI(model="gpt-6-luna", reasoning_effort="low").with_structured_output(JudgeVerdict)

    def evaluate(self, *, output=None, dataset_row=None, **_) -> EvaluationResult:
        v = self.judge.invoke(
            "You are grading a network assistant's answer against known facts about a lab topology. "
            "The expected facts are the minimum a correct answer must contain, not an exhaustive list — "
            "the assistant had live tool output and may correctly add details (uptimes, prefix counts).\n\n"
            f"QUESTION: {dataset_row['question']}\n\n"
            f"EXPECTED FACTS: {dataset_row['expected_facts']}\n\n"
            f"ASSISTANT'S ANSWER: {output}\n\n"
            "Grade it."
        )
        label = "hallucination" if v.hallucinated else ("correct" if v.correct else "incorrect")
        return EvaluationResult(score=1.0 if (v.correct and not v.hallucinated) else 0.0,
                                label=label, explanation=v.explanation or "meets the expected facts")


class Length(Evaluator):
    """A code evaluator for contrast: how long was the answer? (No judgement — a metric.)"""
    def evaluate(self, *, output=None, **_) -> EvaluationResult:
        n = len(str(output or "").split())
        return EvaluationResult(score=float(n), label="short" if n < 60 else "long",
                                explanation=f"{n} words")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--name")
    args = ap.parse_args()

    client = arize_client()
    get_or_create_dataset(client, AGENT_DATASET, QUESTIONS)

    name = args.name or run_name(f"agent-{'local-qwen3' if args.local else 'cloud-gpt-6-luna'}")
    print(f"\nexperiment '{name}' on dataset '{AGENT_DATASET}'{' (dry run)' if args.dry_run else ''}\n")
    experiment, results = client.experiments.run(
        name=name, dataset=AGENT_DATASET, space=SPACE_ID,
        task=make_task(args.local), evaluators=[LlmJudge(), Length()],
        dry_run=args.dry_run, concurrency=1 if args.local else 3,
        metadata={"agent_model": "qwen3:4b-q4_K_M" if args.local else "gpt-6-luna"},
    )
    cols = [c for c in results.columns if c.startswith("eval.LlmJudge.")]
    print(results[cols].to_string(index=False))
    print(f"\ncorrect & not hallucinated: {int(results['eval.LlmJudge.score'].sum())}/{len(results)}")
    if experiment:
        print(f"Uploaded. Open Arize → Datasets → {AGENT_DATASET} → Experiments → {name}")
