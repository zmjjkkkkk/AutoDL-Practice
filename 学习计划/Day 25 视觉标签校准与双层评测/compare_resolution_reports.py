"""Compare two private benchmark reports that differ only in image resolution."""

import argparse
import json
from pathlib import Path


def read_report(path: Path) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(results, list) or not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in results):
        raise ValueError(f"{path}: report must contain result objects with ids")
    return report


def case_coverage(result: dict) -> float | None:
    coverage = result.get("coverage")
    value = coverage.get("overall_required_label_coverage") if isinstance(coverage, dict) else None
    return value if isinstance(value, (int, float)) else None


def summarize(report: dict) -> dict:
    values = [case_coverage(result) for result in report["results"] if result.get("ok") is True]
    values = [value for value in values if value is not None]
    accepted = sum(result.get("ok") is True for result in report["results"])
    return {
        "cases": len(report["results"]),
        "accepted_cases": accepted,
        "accepted_rate": accepted / len(report["results"]) if report["results"] else 0.0,
        "mean_required_label_coverage": sum(values) / len(values) if values else None,
    }


def compare(baseline: dict, candidate: dict) -> dict:
    baseline_by_id = {result["id"]: result for result in baseline["results"]}
    candidate_by_id = {result["id"]: result for result in candidate["results"]}
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError("reports must contain the same case ids")

    baseline_summary = summarize(baseline)
    candidate_summary = summarize(candidate)
    cases = []
    for case_id in sorted(baseline_by_id):
        before = baseline_by_id[case_id]
        after = candidate_by_id[case_id]
        before_value = case_coverage(before)
        after_value = case_coverage(after)
        cases.append(
            {
                "id": case_id,
                "baseline_accepted": before.get("ok") is True,
                "candidate_accepted": after.get("ok") is True,
                "baseline_coverage": before_value,
                "candidate_coverage": after_value,
                "coverage_delta": (
                    None if before_value is None or after_value is None else after_value - before_value
                ),
                "baseline_sent_size": before.get("image", {}).get("sent_size"),
                "candidate_sent_size": after.get("image", {}).get("sent_size"),
            }
        )
    return {
        "baseline": baseline_summary,
        "candidate": candidate_summary,
        "accepted_rate_delta": candidate_summary["accepted_rate"] - baseline_summary["accepted_rate"],
        "mean_required_label_coverage_delta": (
            None
            if baseline_summary["mean_required_label_coverage"] is None
            or candidate_summary["mean_required_label_coverage"] is None
            else candidate_summary["mean_required_label_coverage"] - baseline_summary["mean_required_label_coverage"]
        ),
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/resolution_comparison.json"))
    args = parser.parse_args()

    try:
        result = compare(read_report(args.baseline), read_report(args.candidate))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Resolution comparison written: {args.output}")


if __name__ == "__main__":
    main()
