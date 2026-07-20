"""Validate the Day 20 gateway regression suite before it is executed."""

import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = PROJECT_DIR / "command_regression_cases.json"
VALID_CATEGORIES = {
    "baseline_regression",
    "day19_experimental",
    "ambiguous_intent",
    "must_block",
    "known_regression",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_reference_prompts(paths):
    prompts = set()
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                prompts.add(row["messages"][1]["content"].strip().lower())
            except (IndexError, KeyError, TypeError) as exc:
                raise ValueError(f"{path}:{line_number} has no user message") from exc
    return prompts


def validate_case(case, seen_ids, seen_prompts, reference_prompts):
    case_id = case.get("id", "")
    category = case.get("category", "")
    metric_group = case.get("metric_group", "")
    user = case.get("user", "").strip()
    expected = case.get("expected", {})
    expected_type = expected.get("type")

    if not case_id or case_id in seen_ids:
        raise ValueError(f"Duplicate or missing case id: {case_id!r}")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"{case_id}: unsupported category {category!r}")
    if metric_group not in {"headline", "known_regression"}:
        raise ValueError(f"{case_id}: unsupported metric group {metric_group!r}")
    if not user or user.lower() in seen_prompts:
        raise ValueError(f"{case_id}: empty or duplicate user prompt")
    if expected_type not in {"command", "text", "blocked"}:
        raise ValueError(f"{case_id}: unsupported expected type {expected_type!r}")
    if expected_type in {"command", "text"} and not expected.get("value", "").strip():
        raise ValueError(f"{case_id}: expected {expected_type} needs a value")
    if expected_type == "blocked" and "value" in expected:
        raise ValueError(f"{case_id}: blocked cases must not prescribe a model output")
    if metric_group == "known_regression" and category != "known_regression":
        raise ValueError(f"{case_id}: known_regression metric group needs matching category")

    overlaps_reference = user.lower() in reference_prompts
    if overlaps_reference and not case.get("allow_reference_overlap", False):
        raise ValueError(f"{case_id}: prompt overlaps a supplied training/eval reference")

    seen_ids.add(case_id)
    seen_prompts.add(user.lower())


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--reference-jsonl",
        type=Path,
        action="append",
        default=[],
        help="Optional generated train/eval JSONL files used to detect accidental prompt reuse.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_json(args.cases)
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")

    for path in args.reference_jsonl:
        if not path.exists():
            raise FileNotFoundError(path)
    reference_prompts = load_reference_prompts(args.reference_jsonl)
    seen_ids, seen_prompts = set(), set()
    for case in cases:
        validate_case(case, seen_ids, seen_prompts, reference_prompts)

    counts = Counter(case["category"] for case in cases)
    headline = sum(case["metric_group"] == "headline" for case in cases)
    print("Day 20 regression suite validation passed.")
    print(f"Cases: {len(cases)} | headline: {headline} | categories: {dict(counts)}")
    if args.reference_jsonl:
        print(f"Checked against {len(reference_prompts)} reference prompts.")


if __name__ == "__main__":
    main()
