"""run_noc_experiment.py — Step 2's playground experiment, as a script.

Step 2 of the lab is done in the Arize UI: a four-question dataset, a prompt, the
Q&A evaluator, the same prompt with our network's facts added, and a comparison.
This script runs the same thing from your Codespace — same CSV, same two prompts,
a judge with the same job — for when a dialog has moved since we wrote the lab,
or when you'd rather read the loop as code.

Usage:
  python run_noc_experiment.py                  # baseline prompt: no network facts
  python run_noc_experiment.py --prompt fixed   # the same prompt with the facts added
  python run_noc_experiment.py --dataset-only   # create the dataset in Arize, then stop
  python run_noc_experiment.py --dry-run        # run everything, upload no results
"""
import argparse
import csv
from pathlib import Path

from arize.experiments import EvaluationResult, Evaluator
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from arize_common import NOC_DATASET, SPACE_ID, arize_client, get_or_create_dataset, run_name

CSV_FILE = Path(__file__).resolve().parent / "noc-questions.csv"

# The two prompts from Step 2, word for word. {question} is filled from the dataset row.
PROMPTS = {
    "baseline": """You are a NOC engineer. Answer the user's question.

Question: {question}""",

    "fixed": """You are a NOC engineer. Answer the user's question.

Our network:
- r1 and r2 are in AS 65001 and run iBGP between their loopbacks, 10.0.0.1 (r1) and 10.0.0.2 (r2).
- r3 is in AS 65002 and runs eBGP with r1.
- r1 connects to r2 on ethernet-1/1 (10.1.12.1/30).
- r1 connects to r3 on ethernet-1/2 (10.1.13.1/30). r3's end of that link is 10.1.13.2.

Question: {question}""",
}


def make_task(template: str):
    """The task: one dataset row in, one answer out. In the UI this is the playground prompt."""
    llm = ChatOpenAI(model="gpt-6-luna")

    def answer_task(dataset_row) -> str:
        return llm.invoke(template.format(question=dataset_row["question"])).text

    return answer_task


class QaVerdict(BaseModel):
    correct: bool = Field(description="True if the answer correctly answers the question according to the reference")
    explanation: str = Field(description="One sentence saying why")


class QaJudge(Evaluator):
    """The Q&A evaluator from Step 2, as a class: question + reference + answer -> correct / incorrect."""
    def __init__(self):
        self.judge = ChatOpenAI(model="gpt-6-luna", reasoning_effort="low").with_structured_output(QaVerdict)

    def evaluate(self, *, output=None, dataset_row=None, **_) -> EvaluationResult:
        v = self.judge.invoke(
            "You are given a question, a reference text and an answer. Decide whether the answer "
            "correctly answers the question based on the reference text.\n\n"
            f"[Question]: {dataset_row['question']}\n\n"
            f"[Reference]: {dataset_row['expected_answer']}\n\n"
            f"[Answer]: {output}"
        )
        return EvaluationResult(score=1.0 if v.correct else 0.0,
                                label="correct" if v.correct else "incorrect", explanation=v.explanation)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", choices=list(PROMPTS), default="baseline")
    ap.add_argument("--dataset-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--name")
    args = ap.parse_args()

    with open(CSV_FILE, newline="") as f:
        rows = list(csv.DictReader(f))

    client = arize_client()
    get_or_create_dataset(client, NOC_DATASET, rows)
    if args.dataset_only:
        raise SystemExit(f"Open Arize → Datasets → {NOC_DATASET}")

    name = args.name or run_name(f"noc-{args.prompt}")
    print(f"\nexperiment '{name}' on dataset '{NOC_DATASET}'{' (dry run)' if args.dry_run else ''}\n")
    experiment, results = client.experiments.run(
        name=name, dataset=NOC_DATASET, space=SPACE_ID,
        task=make_task(PROMPTS[args.prompt]), evaluators=[QaJudge()],
        dry_run=args.dry_run, concurrency=4,
        metadata={"prompt": args.prompt, "model": "gpt-6-luna"},
    )
    print(results[["eval.QaJudge.label", "eval.QaJudge.explanation"]].to_string(index=False))
    print(f"\ncorrect: {int(results['eval.QaJudge.score'].sum())}/{len(results)}")
    if experiment:
        print(f"Uploaded. Open Arize → Datasets → {NOC_DATASET} → Experiments → {name}")
