"""arize_common.py — one place for the Arize client and the lab's naming."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Sibling labs on the import path: Lab 2 for the parser + golden set, Lab 3 for the agent.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Lab_2_Structured_Network_Data"))
sys.path.insert(0, str(ROOT / "Lab_3_LangChain_Network_Agent"))

SPACE_ID = os.getenv("ARIZE_SPACE_ID")
API_KEY = os.getenv("ARIZE_API_KEY")

NOC_DATASET = "autocon6-noc-questions"        # Step 2's four questions (noc-questions.csv)
PARSER_DATASET = "autocon6-golden-bgp"        # Lab 2's golden captures + answer key
AGENT_DATASET = "autocon6-agent-questions"    # questions with known-good answers


def arize_client():
    """ArizeClient reads ARIZE_API_KEY from the environment; we pass it explicitly
    so a missing key fails here with a clear message, not deep inside a request."""
    if not (SPACE_ID and API_KEY):
        sys.exit("ARIZE_SPACE_ID / ARIZE_API_KEY are not set in .env — see WORKSHOP_FAQ.md")
    from arize import ArizeClient
    return ArizeClient(api_key=API_KEY)


def get_or_create_dataset(client, name: str, examples: list[dict]):
    """Datasets are append-only and names are unique per space, so re-running the
    lab must not try to create the same one twice."""
    from arize import NotFoundError
    try:
        ds = client.datasets.get(dataset=name, space=SPACE_ID)
        print(f"dataset '{name}' already exists (id {ds.id}) — reusing it")
        return ds
    except NotFoundError:
        ds = client.datasets.create(name=name, space=SPACE_ID, examples=examples)
        print(f"created dataset '{name}' (id {ds.id}) with {len(examples)} examples")
        return ds


def run_name(base: str) -> str:
    """Experiment names are unique per dataset, so stamp the time on: re-running
    the lab must never collide with an earlier run (even a failed one)."""
    from datetime import datetime
    return f"{base}-{datetime.now().strftime('%H%M%S')}"
