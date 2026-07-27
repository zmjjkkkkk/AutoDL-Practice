"""Strictly compare base and LoRA reports that use the same external images."""

import argparse
import json
from pathlib import Path


def read_report(path: Path) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(report.get("results"), list) or not report["results"]:
        raise ValueError(f"{path} has no results")
    return report


def compare(baseline: dict, candidate: dict) -> dict:
    before = {item["image_path"]: item for item in baseline["results"]}
    after = {item["image_path"]: item for item in candidate["results"]}
    if set(before) != set(after):
        raise ValueError("reports must contain exactly the same images")
    cases = [{"image_path": path, "expected": before[path]["expected"], "baseline_prediction": before[path]["prediction"], "candidate_prediction": after[path]["prediction"], "baseline_exact_match": before[path]["exact_match"], "candidate_exact_match": after[path]["exact_match"]} for path in sorted(before)]
    base_accuracy = sum(case["baseline_exact_match"] for case in cases) / len(cases)
    lora_accuracy = sum(case["candidate_exact_match"] for case in cases) / len(cases)
    return {"examples": len(cases), "baseline_accuracy": base_accuracy, "candidate_accuracy": lora_accuracy, "accuracy_delta": lora_accuracy - base_accuracy, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compare(read_report(args.baseline), read_report(args.candidate))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Base external accuracy: {result['baseline_accuracy']:.1%}")
    print(f"LoRA external accuracy: {result['candidate_accuracy']:.1%}")
    print(f"Accuracy delta: {result['accuracy_delta']:+.1%}")
    print(f"Report written: {args.output}")


if __name__ == "__main__":
    main()
