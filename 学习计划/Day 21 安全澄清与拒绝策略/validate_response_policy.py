"""Validate the Day 21 response-policy specification and held-out cases."""

import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY = PROJECT_DIR / "response_policy_spec.json"
DEFAULT_CASES = PROJECT_DIR / "response_policy_cases.json"
VALID_CATEGORIES = {"route_command", "needs_clarification", "unsupported"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_prompts(paths):
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


def load_case_prompts(paths):
    prompts = set()
    for path in paths:
        payload = load_json(path)
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise ValueError(f"{path} has no cases list")
        for case in cases:
            user = case.get("user", "")
            if isinstance(user, str) and user.strip():
                prompts.add(user.strip().lower())
    return prompts


def validate_policy(policy):
    modes = policy.get("response_modes")
    responses = policy.get("fixed_responses")
    if not isinstance(modes, dict) or set(modes) != VALID_CATEGORIES:
        raise ValueError("response_modes must define route_command, needs_clarification, and unsupported")
    if not isinstance(responses, dict):
        raise ValueError("fixed_responses must be an object")
    for mode_name in {"needs_clarification", "unsupported"}:
        response_id = modes[mode_name].get("fixed_response_id")
        response = responses.get(response_id)
        if not isinstance(response, str) or not response.strip():
            raise ValueError(f"{mode_name} needs a non-empty fixed response")
    return responses


def validate_case(case, responses, seen_ids, seen_prompts, reference_prompts):
    case_id = case.get("id", "")
    category = case.get("category", "")
    user = case.get("user", "").strip()
    expected = case.get("expected", {})
    expected_type = expected.get("type")
    if not case_id or case_id in seen_ids:
        raise ValueError(f"Duplicate or missing case id: {case_id!r}")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"{case_id}: unsupported category {category!r}")
    if not user or user.lower() in seen_prompts:
        raise ValueError(f"{case_id}: empty or duplicate user prompt")
    if user.lower() in reference_prompts:
        raise ValueError(f"{case_id}: prompt overlaps a supplied reference set")
    if category == "route_command":
        if expected_type not in {"command", "text"} or not expected.get("value", "").strip():
            raise ValueError(f"{case_id}: route_command needs a non-empty command or text expectation")
    else:
        if expected_type != "fixed_response":
            raise ValueError(f"{case_id}: {category} needs a fixed_response expectation")
        response_id = expected.get("response_id")
        if response_id not in responses:
            raise ValueError(f"{case_id}: unknown fixed response {response_id!r}")
        required_id = "clarify_transfer" if category == "needs_clarification" else "unsupported_request"
        if response_id != required_id:
            raise ValueError(f"{case_id}: {category} must use {required_id}")
    seen_ids.add(case_id)
    seen_prompts.add(user.lower())


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--reference-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--reference-cases", type=Path, action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    for path in [args.policy, args.cases, *args.reference_jsonl, *args.reference_cases]:
        if not path.exists():
            raise FileNotFoundError(path)
    responses = validate_policy(load_json(args.policy))
    payload = load_json(args.cases)
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")
    reference_prompts = load_jsonl_prompts(args.reference_jsonl)
    reference_prompts.update(load_case_prompts(args.reference_cases))
    seen_ids, seen_prompts = set(), set()
    for case in cases:
        validate_case(case, responses, seen_ids, seen_prompts, reference_prompts)
    counts = Counter(case["category"] for case in cases)
    print("Day 21 response-policy validation passed.")
    print(f"Cases: {len(cases)} | categories: {dict(counts)}")
    print(f"Fixed responses: {len(responses)} | reference prompts checked: {len(reference_prompts)}")


if __name__ == "__main__":
    main()
