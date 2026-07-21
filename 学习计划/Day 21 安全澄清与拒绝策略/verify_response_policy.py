"""Run the Day 21 static policy against its held-out non-command cases."""

import json
from pathlib import Path

from response_policy import decide_request, load_policy


PROJECT_DIR = Path(__file__).resolve().parent
CASES_PATH = PROJECT_DIR / "response_policy_cases.json"


def main():
    policy = load_policy()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    failures = []
    checked = 0

    for case in cases:
        decision = decide_request(case["user"], policy)
        expected = case["expected"]
        category = case["category"]
        if category == "route_command":
            passed = decision.mode == "route_command"
        else:
            expected_reply = policy["fixed_responses"][expected["response_id"]]
            passed = decision.mode == category and decision.reply == expected_reply
        checked += 1
        if not passed:
            failures.append({"id": case["id"], "expected": category, "actual": decision.to_dict()})

    if failures:
        raise RuntimeError(f"Day 21 static policy failures: {failures}")
    print(f"Day 21 static policy passed: {checked}/{checked}")


if __name__ == "__main__":
    main()
