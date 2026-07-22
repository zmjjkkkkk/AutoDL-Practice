"""Run offline Day 22 observation-guard cases without an image model."""

import json
from pathlib import Path

from vision_observation_guard import validate_vision_output


PROJECT_DIR = Path(__file__).resolve().parent
CASES_PATH = PROJECT_DIR / "vision_observation_cases.json"


def main():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    failures = []
    for case in cases:
        result = validate_vision_output(case["raw_output"])
        expected = case["expected"]
        passed = result.accepted is expected["accepted"]
        if expected["accepted"]:
            passed = passed and result.value == expected["value"]
        else:
            passed = passed and result.reason == expected["reason"]
        if not passed:
            failures.append({"id": case["id"], "expected": expected, "actual": result.to_dict()})
    if failures:
        raise RuntimeError(f"Day 22 observation guard failures: {failures}")
    print(f"Day 22 observation guard passed: {len(cases)}/{len(cases)}")


if __name__ == "__main__":
    main()
