"""Compare fixed Day 23 observation focuses on one private benchmark case."""

import argparse
import json
from pathlib import Path

from query_focused_observation import FOCUSES, build_payload, call_gateway


LABEL_FIELDS = ("scene_labels", "hazards", "visible_blocks", "visible_entities")


def load_case(manifest_path: Path, case_id: str) -> dict:
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read manifest: {exc}") from exc
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list):
        raise ValueError("manifest must contain a cases list")
    for case in cases:
        if isinstance(case, dict) and case.get("id") == case_id:
            if not isinstance(case.get("image_path"), str) or not isinstance(case.get("expected"), dict):
                raise ValueError(f"{case_id}: invalid case format")
            return case
    raise ValueError(f"case not found: {case_id}")


def score(expected: dict, observation: dict | None) -> dict:
    observation = observation or {}
    total = matched = 0
    fields = {}
    for field in LABEL_FIELDS:
        expected_labels = set(expected.get(field, []))
        observed_labels = set(observation.get(field, []))
        field_matched = sorted(expected_labels & observed_labels)
        total += len(expected_labels)
        matched += len(field_matched)
        fields[field] = {
            "expected": sorted(expected_labels),
            "matched": field_matched,
            "missing": sorted(expected_labels - observed_labels),
            "coverage": None if not expected_labels else len(field_matched) / len(expected_labels),
        }
    return {
        "overall_required_label_coverage": None if not total else matched / total,
        "fields": fields,
    }


def compare(case: dict, manifest_dir: Path, focuses: list[str], gateway_url: str, timeout: int) -> dict:
    image_path = manifest_dir / case["image_path"]
    if not image_path.is_file():
        raise ValueError(f"image not found: {image_path}")
    results = []
    for focus in focuses:
        response = call_gateway(gateway_url, build_payload(image_path, focus), timeout)
        observation = response.get("observation") if response.get("ok") is True else None
        results.append(
            {
                "focus": focus,
                "ok": response.get("ok") is True,
                "reason": response.get("reason"),
                "observation": observation,
                "score": score(case["expected"], observation),
            }
        )
    return {"case_id": case["id"], "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--focuses", nargs="+", choices=FOCUSES, default=["overview", "blocks"])
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18768")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        case = load_case(args.manifest, args.case_id)
        report = compare(case, args.manifest.parent, args.focuses, args.gateway_url, args.timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Focus comparison report written: {args.output}")
    print(rendered)


if __name__ == "__main__":
    main()
