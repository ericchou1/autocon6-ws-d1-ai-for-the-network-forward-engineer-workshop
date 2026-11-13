"""upload_dataset.py — Lab 2's golden set becomes an Arize dataset.

Each example carries the raw router output (the task's input), the hand-verified
neighbors from expected.json (the answer key), and a little metadata. Nothing
here calls an LLM; this is the answer key moving from a JSON file on disk to a
place where every experiment can be scored against it.
"""
import json

from arize_common import PARSER_DATASET, arize_client, get_or_create_dataset
from parse_bgp import GOLDEN


def build_examples() -> list[dict]:
    answer_key = json.loads((GOLDEN / "expected.json").read_text())
    examples = []
    for filename, expected in answer_key.items():
        if filename.startswith("_"):
            continue
        examples.append({
            "case": filename,
            "node": filename.split("_")[0],
            "raw_output": (GOLDEN / filename).read_text(),
            "expected_neighbors": json.dumps(expected),
            "expected_count": len(expected),
            "scenario": ("degraded" if "degraded" in filename
                         else "empty" if "empty" in filename else "healthy"),
        })
    return examples


if __name__ == "__main__":
    examples = build_examples()
    print(f"{len(examples)} golden cases:")
    for ex in examples:
        print(f"  {ex['case']:<22} {ex['scenario']:<9} {ex['expected_count']} expected neighbor(s), "
              f"{len(ex['raw_output'].splitlines())} lines of raw output")
    client = arize_client()
    get_or_create_dataset(client, PARSER_DATASET, examples)
    print("\nOpen Arize → Datasets → autocon6-golden-bgp to see the rows.")
