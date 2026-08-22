"""Create or update the LangSmith eval dataset for LOGFLOWS Knowledge RAG."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLES_PATH = BASE_DIR / "evals" / "dataset_examples.json"
DEFAULT_DATASET_NAME = "LOGFLOWS Knowledge RAG Q&A"

for env_file in (BASE_DIR / ".env.development", BASE_DIR / ".env", BASE_DIR / ".env.example"):
    if env_file.is_file():
        load_dotenv(env_file, override=False)
        break


def load_examples(path: Path) -> list[dict]:
    """Load LangSmith example rows from JSON."""
    if not path.is_file():
        raise FileNotFoundError(f"examples file not found: {path}")
    raw = json.loads(path.read_text())
    if not isinstance(raw, list) or not raw:
        raise ValueError("examples file must be a non-empty JSON array")
    for index, example in enumerate(raw):
        if not isinstance(example, dict):
            raise ValueError(f"example at index {index} must be an object")
        if "inputs" not in example or "outputs" not in example:
            raise ValueError(f"example at index {index} must include inputs and outputs")
    return raw


def get_or_create_dataset(client: Client, dataset_name: str, description: str):
    """Return an existing dataset by name or create a new one."""
    existing = list(client.list_datasets(dataset_name=dataset_name))
    if existing:
        return existing[0]
    return client.create_dataset(
        dataset_name=dataset_name,
        description=description,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create LangSmith eval dataset from bundled Q&A examples.")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--examples-path", type=Path, default=DEFAULT_EXAMPLES_PATH)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing examples in the dataset before uploading.",
    )
    args = parser.parse_args()

    examples = load_examples(args.examples_path)
    client = Client()
    dataset = get_or_create_dataset(
        client,
        dataset_name=args.dataset_name,
        description=(
            "Ground-truth Q&A for LOGFLOWS sample logistics docs (SOP-001, SOP-006, "
            "POL-HAZ-005, CUST-ACME-003, INC-2026-014). Includes answerable and refusal cases."
        ),
    )

    if args.replace:
        for example in client.list_examples(dataset_id=dataset.id):
            client.delete_example(example.id)

    client.create_examples(dataset_id=dataset.id, examples=examples)

    print(
        "langsmith_dataset_ready",
        f"name={args.dataset_name}",
        f"dataset_id={dataset.id}",
        f"examples={len(examples)}",
        f"source={args.examples_path}",
    )


if __name__ == "__main__":
    main()
