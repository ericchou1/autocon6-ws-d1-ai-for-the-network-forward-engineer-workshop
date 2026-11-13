"""run_parser_experiment.py — Lab 2's eval, run as an Arize experiment.

Same idea as eval_parser.py: run the parser over every golden case and score it.
Two things are new:
  * the results land in Arize next to the dataset, so two runs (cloud vs local,
    effort none vs high, this prompt vs that prompt) can be compared side by side;
  * one evaluator is an LLM judge — a second model reading the raw table and the
    parsed output and deciding whether they agree. That's the pattern you need
    when there is no answer key, and here you can check it AGAINST the answer key.

Usage:
  python run_parser_experiment.py                 # cloud parser
  python run_parser_experiment.py --local         # qwen3 parser (slow: ~4 min)
  python run_parser_experiment.py --dry-run       # run locally, upload nothing
"""
import argparse
import json
from typing import Literal

from arize.experiments import EvaluationResult, Evaluator
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from arize_common import PARSER_DATASET, SPACE_ID, arize_client, run_name
from parse_bgp import make_llm, parse_bgp_neighbors

FIELDS = ["peer_ip", "group", "peer_as", "state", "uptime_seconds",
          "prefixes_received", "prefixes_active", "prefixes_sent"]


# ---------------------------------------------------------------------------
# The task: what we're evaluating. One dataset row in, one output out.
# ---------------------------------------------------------------------------
def make_task(local: bool, max_attempts: int):
    llm = make_llm(local=local)

    def parse_task(dataset_row) -> dict:
        try:
            result = parse_bgp_neighbors(dataset_row["raw_output"], llm=llm, max_attempts=max_attempts)
            return {"ok": True, "neighbors": [json.loads(n.model_dump_json()) for n in result.neighbors]}
        except ValidationError as e:
            return {"ok": False, "error": str(e), "neighbors": []}

    return parse_task


# ---------------------------------------------------------------------------
# Evaluators: code first (cheap, exact), then an LLM judge (flexible, fallible)
# ---------------------------------------------------------------------------
class StructuralValid(Evaluator):
    """Did the output validate against the schema at all? (Lab 2's first layer.)"""
    def evaluate(self, *, output=None, **_) -> EvaluationResult:
        ok = bool(output and output.get("ok"))
        # Explanations must always be strings: Arize rejects an all-null column.
        return EvaluationResult(score=1.0 if ok else 0.0, label="valid" if ok else "invalid",
                                explanation="validated against the schema" if ok else output.get("error", "")[:300])


class FieldsMatch(Evaluator):
    """Fraction of answer-key fields reproduced exactly. (Lab 2's second layer.)"""
    def evaluate(self, *, output=None, dataset_row=None, **_) -> EvaluationResult:
        expected = json.loads(dataset_row["expected_neighbors"])
        got = {n["peer_ip"]: n for n in (output or {}).get("neighbors", [])}
        checked = matched = 0
        problems = []
        for exp in expected:
            row = got.pop(exp["peer_ip"], None)
            for f in FIELDS:
                checked += 1
                if row is None:
                    continue
                if row.get(f) == exp[f]:
                    matched += 1
                else:
                    problems.append(f"{exp['peer_ip']}.{f}: expected {exp[f]!r}, got {row.get(f)!r}")
            if row is None:
                problems.append(f"{exp['peer_ip']}: missing")
        for extra in got:
            checked += len(FIELDS)
            problems.append(f"{extra}: unexpected extra neighbor")
        score = 1.0 if checked == 0 else matched / checked
        return EvaluationResult(score=score, label="match" if score == 1.0 else "mismatch",
                                explanation="; ".join(problems) or "all fields match")


class Verdict(BaseModel):
    faithful: bool = Field(description="True if every value in the parsed output is supported by the raw table and nothing is missing")
    explanation: str = Field(description="One sentence. Quote the specific value that is wrong if any.")


class LlmJudgeFaithful(Evaluator):
    """A second model reads the raw table and the parsed JSON and says whether they agree.
    No answer key involved — which is exactly why we can check the judge against one here."""
    def __init__(self):
        self.judge = ChatOpenAI(model="gpt-6-luna", reasoning_effort="low").with_structured_output(Verdict)

    def evaluate(self, *, output=None, dataset_row=None, **_) -> EvaluationResult:
        prompt = (
            "You are auditing a parser. Below is raw SR Linux BGP neighbor output and the JSON a "
            "parser produced from it. Uptime must equal the Uptime column converted to seconds; "
            "the three prefix counts must equal the [Rx/Active/Tx] column; a '-' means null.\n\n"
            f"RAW OUTPUT:\n{dataset_row['raw_output'] or '(empty — the command printed nothing)'}\n\n"
            f"PARSED JSON:\n{json.dumps((output or {}).get('neighbors', []), indent=1)}\n\n"
            "Is the parsed JSON a faithful representation of the raw output?"
        )
        v = self.judge.invoke(prompt)
        return EvaluationResult(score=1.0 if v.faithful else 0.0,
                                label="faithful" if v.faithful else "unfaithful",
                                explanation=v.explanation)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="parse with the local qwen3 model")
    ap.add_argument("--attempts", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true", help="run but upload nothing")
    ap.add_argument("--name", help="experiment name (default derived from flags)")
    args = ap.parse_args()

    name = args.name or run_name(f"parser-{'local-qwen3' if args.local else 'cloud-gpt-6-luna'}-attempts{args.attempts}")
    client = arize_client()
    print(f"experiment '{name}' on dataset '{PARSER_DATASET}'{' (dry run)' if args.dry_run else ''}\n")

    experiment, results = client.experiments.run(
        name=name, dataset=PARSER_DATASET, space=SPACE_ID,
        task=make_task(args.local, args.attempts),
        evaluators=[StructuralValid(), FieldsMatch(), LlmJudgeFaithful()],
        dry_run=args.dry_run, concurrency=1 if args.local else 3,
        metadata={"model": "qwen3:4b-q4_K_M" if args.local else "gpt-6-luna", "attempts": str(args.attempts)},
    )

    cols = [c for c in results.columns if c.startswith("eval.") and c.endswith(".score")]
    print("\nper-case scores:")
    print(results[["example_id"] + cols].to_string(index=False) if "example_id" in results.columns else results[cols].to_string(index=False))
    print("\nmeans:", {c.replace("eval.", "").replace(".score", ""): round(results[c].mean(), 2) for c in cols})
    if experiment:
        print(f"\nUploaded. Open Arize → Datasets → {PARSER_DATASET} → Experiments → {name}")
