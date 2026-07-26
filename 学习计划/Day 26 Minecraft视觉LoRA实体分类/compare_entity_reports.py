"""Compare held-out exact entity accuracy before and after visual LoRA training."""

import argparse
import json
from pathlib import Path


def read_report(path: Path) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(results, list) or not results:
        raise ValueError(f"{path} must contain non-empty results")
    return report


def compare(baseline: dict, candidate: dict) -> dict:
    baseline_by_path = {result["image_path"]: result for result in baseline["results"]}
    candidate_by_path = {result["image_path"]: result for result in candidate["results"]}
    if set(baseline_by_path) != set(candidate_by_path):
        raise ValueError("reports must evaluate exactly the same test images")
    cases = []
    for path in sorted(baseline_by_path):
        before = baseline_by_path[path]
        after = candidate_by_path[path]
        cases.append(
            {
                "image_path": path,
                "expected": before["expected"],
                "baseline_prediction": before["prediction"],
                "candidate_prediction": after["prediction"],
                "baseline_exact_match": before["exact_match"],
                "candidate_exact_match": after["exact_match"],
            }
        )
    baseline_accuracy = sum(item["baseline_exact_match"] for item in cases) / len(cases)
    candidate_accuracy = sum(item["candidate_exact_match"] for item in cases) / len(cases)
    return {
        "examples": len(cases),
        "baseline_accuracy": baseline_accuracy,
        "candidate_accuracy": candidate_accuracy,
        "accuracy_delta": candidate_accuracy - baseline_accuracy,
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/base_vs_lora.json"))
    args = parser.parse_args()
    try:
        result = compare(read_report(args.baseline), read_report(args.candidate))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Base accuracy: {result['baseline_accuracy']:.1%}")
    print(f"LoRA accuracy: {result['candidate_accuracy']:.1%}")
    print(f"Accuracy delta: {result['accuracy_delta']:+.1%}")
    print(f"Report written: {args.output}")


if __name__ == "__main__":
    main()
