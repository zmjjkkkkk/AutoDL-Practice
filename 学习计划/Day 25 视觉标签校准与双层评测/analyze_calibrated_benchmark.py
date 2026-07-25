"""Compare strict and explicitly alias-calibrated visual benchmark coverage."""

import argparse
import json
from pathlib import Path


LABEL_FIELDS = ("scene_labels", "hazards", "visible_blocks", "visible_entities")


def read_json(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def load_aliases(path: Path) -> dict[str, dict[str, str]]:
    document = read_json(path)
    aliases = document.get("aliases")
    if not isinstance(aliases, dict) or set(aliases) - set(LABEL_FIELDS):
        raise ValueError("aliases must only contain known label fields")

    normalized = {field: {} for field in LABEL_FIELDS}
    for field, mapping in aliases.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"aliases.{field} must be an object")
        for observed, canonical in mapping.items():
            if (
                not isinstance(observed, str)
                or not observed
                or not isinstance(canonical, str)
                or not canonical
                or observed == canonical
            ):
                raise ValueError(f"aliases.{field} must map distinct non-empty strings")
            normalized[field][observed] = canonical
    return normalized


def coverage(expected: set[str], observed: set[str]) -> float | None:
    return None if not expected else len(expected & observed) / len(expected)


def score_case(result: dict, aliases: dict[str, dict[str, str]]) -> dict:
    if result.get("ok") is not True:
        return {"id": result.get("id"), "ok": False}
    observation = result.get("observation")
    source_coverage = result.get("coverage")
    if not isinstance(observation, dict) or not isinstance(source_coverage, dict):
        raise ValueError(f"{result.get('id')}: accepted results require observation and coverage")

    fields = {}
    strict_total = calibrated_total = expected_total = 0
    for field in LABEL_FIELDS:
        expected_data = source_coverage.get(field)
        if not isinstance(expected_data, dict) or not isinstance(expected_data.get("expected"), list):
            raise ValueError(f"{result.get('id')}: missing expected labels for {field}")
        expected = set(expected_data["expected"])
        observed = set(observation.get(field, []))
        calibrated_observed = {aliases[field].get(label, label) for label in observed}
        strict_matched = sorted(expected & observed)
        calibrated_matched = sorted(expected & calibrated_observed)
        alias_matches = sorted(
            {
                (label, aliases[field][label])
                for label in observed
                if label in aliases[field] and aliases[field][label] in expected and label not in expected
            }
        )
        expected_total += len(expected)
        strict_total += len(strict_matched)
        calibrated_total += len(calibrated_matched)
        fields[field] = {
            "strict_coverage": coverage(expected, observed),
            "calibrated_coverage": coverage(expected, calibrated_observed),
            "strict_matched": strict_matched,
            "calibrated_matched": calibrated_matched,
            "alias_matches": [
                {"observed": observed_label, "canonical": canonical_label}
                for observed_label, canonical_label in alias_matches
            ],
        }

    return {
        "id": result.get("id"),
        "ok": True,
        "strict_required_label_coverage": None if not expected_total else strict_total / expected_total,
        "calibrated_required_label_coverage": None if not expected_total else calibrated_total / expected_total,
        "fields": fields,
    }


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def analyze(results: list[dict], aliases: dict[str, dict[str, str]]) -> dict:
    scored_cases = [score_case(result, aliases) for result in results]
    accepted = [case for case in scored_cases if case["ok"]]
    strict_values = [case["strict_required_label_coverage"] for case in accepted if case["strict_required_label_coverage"] is not None]
    calibrated_values = [case["calibrated_required_label_coverage"] for case in accepted if case["calibrated_required_label_coverage"] is not None]
    alias_matches = []
    for case in accepted:
        for field in LABEL_FIELDS:
            for match in case["fields"][field]["alias_matches"]:
                alias_matches.append({"case_id": case["id"], "field": field, **match})

    return {
        "cases": len(scored_cases),
        "accepted_cases": len(accepted),
        "strict_mean_required_label_coverage": mean(strict_values),
        "calibrated_mean_required_label_coverage": mean(calibrated_values),
        "calibration_gain": None if not strict_values else mean(calibrated_values) - mean(strict_values),
        "applied_alias_matches": alias_matches,
        "cases_detail": scored_cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--aliases", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/calibrated_benchmark_report.json"))
    args = parser.parse_args()

    try:
        report = read_json(args.report)
        results = report.get("results")
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
            raise ValueError("report must contain an object results list")
        analysis = analyze(results, load_aliases(args.aliases))
    except ValueError as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in analysis.items() if key != "cases_detail"}, ensure_ascii=False, indent=2))
    print(f"Calibrated report written: {args.output}")


if __name__ == "__main__":
    main()
