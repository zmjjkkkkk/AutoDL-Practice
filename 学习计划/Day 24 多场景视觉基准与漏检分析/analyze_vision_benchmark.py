"""Summarize private Day 23 visual benchmark reports without reading screenshots."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


LABEL_FIELDS = ("scene_labels", "hazards", "visible_blocks", "visible_entities")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_metadata(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    document = read_json(path)
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("metadata must contain a cases list")

    mapping = {}
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "tags"}:
            raise ValueError("each metadata case must contain exactly id and tags")
        case_id = case["id"]
        tags = case["tags"]
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in mapping
            or not isinstance(tags, list)
            or not tags
            or not all(isinstance(tag, str) and tag for tag in tags)
        ):
            raise ValueError("metadata ids and tags must be unique non-empty strings")
        mapping[case_id] = sorted(set(tags))
    return mapping


def safe_coverage(result: dict) -> float | None:
    coverage = result.get("coverage")
    if not isinstance(coverage, dict):
        return None
    value = coverage.get("overall_required_label_coverage")
    return value if isinstance(value, (int, float)) else None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def analyze(results: list[dict], metadata: dict[str, list[str]] | None = None) -> dict:
    metadata = metadata or {}
    accepted = [item for item in results if item.get("ok") is True]
    field_values = defaultdict(list)
    missed_labels = {field: Counter() for field in LABEL_FIELDS}
    tag_values = defaultdict(list)

    for result in accepted:
        coverage = result.get("coverage")
        if not isinstance(coverage, dict):
            continue
        for field in LABEL_FIELDS:
            field_score = coverage.get(field)
            if not isinstance(field_score, dict):
                continue
            value = field_score.get("coverage")
            if isinstance(value, (int, float)):
                field_values[field].append(value)
            missing = field_score.get("missing", [])
            if isinstance(missing, list):
                missed_labels[field].update(item for item in missing if isinstance(item, str))

        overall = safe_coverage(result)
        for tag in metadata.get(result.get("id"), []):
            if overall is not None:
                tag_values[tag].append(overall)

    return {
        "cases": len(results),
        "accepted_cases": len(accepted),
        "accepted_rate": len(accepted) / len(results) if results else 0.0,
        "mean_required_label_coverage": mean(
            [value for value in (safe_coverage(item) for item in accepted) if value is not None]
        ),
        "field_mean_coverage": {field: mean(field_values[field]) for field in LABEL_FIELDS},
        "most_missed_labels": {
            field: [
                {"label": label, "misses": count}
                for label, count in missed_labels[field].most_common()
            ]
            for field in LABEL_FIELDS
        },
        "coverage_by_case_tag": {
            tag: {"cases": len(values), "mean_required_label_coverage": mean(values)}
            for tag, values in sorted(tag_values.items())
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/vision_error_analysis.json"),
    )
    args = parser.parse_args()

    try:
        report = read_json(args.report)
        results = report.get("results")
        if not isinstance(results, list):
            raise ValueError("report must contain a results list")
        if not all(isinstance(item, dict) for item in results):
            raise ValueError("report results must be objects")
        analysis = analyze(results, load_metadata(args.metadata))
    except ValueError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    print(f"Analysis written: {args.output}")


if __name__ == "__main__":
    main()
