"""eval_parser.py — your first eval: run the parser over the golden set and score it.

Two layers, named on purpose:
  * STRUCTURAL  — did the output validate against the schema at all?
  * CORRECTNESS — do the validated values match the hand-verified answer key?

A result can pass the first and fail the second. That gap is the whole reason
evals exist.

Usage:
  python eval_parser.py                 # cloud model, 1 attempt
  python eval_parser.py --local         # local Ollama model
  python eval_parser.py --attempts 3    # allow retries on validation failure
  python eval_parser.py --local --only r1_bgp_degraded.txt --attempts 3
"""
import argparse
import json
import time

from pydantic import ValidationError

from parse_bgp import GOLDEN, make_llm, parse_bgp_neighbors

FIELDS = ["peer_ip", "group", "peer_as", "state", "uptime_seconds",
          "prefixes_received", "prefixes_active", "prefixes_sent"]


def compare(parsed, expected):
    """Return (fields_checked, fields_matched, list_of_mismatch_strings).
    Rows are matched by peer_ip; a missing or extra row counts every field as wrong."""
    got = {str(n.peer_ip): n for n in parsed.neighbors}
    checked = matched = 0
    problems = []
    for exp in expected:
        row = got.pop(exp["peer_ip"], None)
        for f in FIELDS:
            checked += 1
            if row is None:
                continue
            actual = getattr(row, f)
            actual = str(actual) if f == "peer_ip" else actual
            if actual == exp[f]:
                matched += 1
            else:
                problems.append(f"{exp['peer_ip']}.{f}: expected {exp[f]!r}, got {actual!r}")
        if row is None:
            problems.append(f"{exp['peer_ip']}: missing from output")
    for extra in got:
        checked += len(FIELDS)
        problems.append(f"{extra}: unexpected extra neighbor")
    return checked, matched, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="use the local Ollama model")
    ap.add_argument("--attempts", type=int, default=1, help="max attempts per file (retries on validation failure)")
    ap.add_argument("--only", metavar="FILE", help="run a single golden file, e.g. r1_bgp_degraded.txt")
    args = ap.parse_args()

    llm = make_llm(local=args.local)
    answer_key = json.loads((GOLDEN / "expected.json").read_text())
    cases = [k for k in answer_key if not k.startswith("_")]
    if args.only:
        cases = [c for c in cases if c == args.only] or ap.error(f"{args.only} is not in expected.json")

    print(f"Model: {'local ' + llm.model if args.local else 'cloud ' + llm.model_name}   "
          f"attempts: {args.attempts}   cases: {len(cases)}")
    if args.local:
        # The local model prints nothing while it works, so say how long the silence will last.
        print("Local model: allow a minute or two per file. Nothing prints while it works.")
    print()
    print(f"{'file':<22} {'struct':<8} {'fields':<9} {'time':>6}  notes")
    print("-" * 78)

    total_checked = total_matched = structural_pass = 0
    t_all = time.time()
    for name in cases:
        raw = (GOLDEN / name).read_text()
        t = time.time()
        try:
            parsed = parse_bgp_neighbors(raw, llm=llm, max_attempts=args.attempts)
        except ValidationError as e:
            elapsed = time.time() - t
            total_checked += len(answer_key[name]) * len(FIELDS)
            print(f"{name:<22} {'FAIL':<8} {'-':<9} {elapsed:5.1f}s  {e.error_count()} validation error(s): "
                  f"{e.errors()[0]['msg']}")
            continue
        elapsed = time.time() - t
        structural_pass += 1
        checked, matched, problems = compare(parsed, answer_key[name])
        total_checked += checked
        total_matched += matched
        verdict = "ok" if matched == checked else "MISMATCH"
        print(f"{name:<22} {'ok':<8} {matched:>2}/{checked:<6} {elapsed:5.1f}s  {verdict}")
        for p in problems:
            print(f"{'':<22} {'':<8} {'':<9} {'':>6}    - {p}")

    print("-" * 78)
    pct = 100 * total_matched / total_checked if total_checked else 0
    print(f"structural: {structural_pass}/{len(cases)} files validated    "
          f"correctness: {total_matched}/{total_checked} fields ({pct:.0f}%)    "
          f"total time: {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
