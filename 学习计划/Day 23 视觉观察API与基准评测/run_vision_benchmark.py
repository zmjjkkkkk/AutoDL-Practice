"""Evaluate private, manually labelled screenshots through the Day 23 observation API."""

import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


LABEL_FIELDS = ("scene_labels", "hazards", "visible_blocks")


def load_manifest(path: Path) -> list[dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read manifest: {exc}") from exc
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain a non-empty cases list")

    seen_ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "image_path", "expected"}:
            raise ValueError("each case must contain exactly id, image_path, and expected")
        case_id = case["id"]
        expected = case["expected"]
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            raise ValueError("case ids must be unique non-empty strings")
        seen_ids.add(case_id)
        if not isinstance(case["image_path"], str) or not case["image_path"]:
            raise ValueError(f"{case_id}: image_path must be a non-empty string")
        if not isinstance(expected, dict) or set(expected) != set(LABEL_FIELDS):
            raise ValueError(f"{case_id}: expected must contain exactly {LABEL_FIELDS}")
        for field in LABEL_FIELDS:
            if not isinstance(expected[field], list) or not all(isinstance(item, str) for item in expected[field]):
                raise ValueError(f"{case_id}: expected.{field} must be a list of strings")
    return cases


def image_request(path: Path) -> dict:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("only PNG, JPEG, and WebP images are supported")
    image_bytes = path.read_bytes()
    return {
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "mime_type": mime_type,
    }


def call_gateway(gateway_url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        gateway_url.rstrip("/") + "/observe",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"gateway request failed: {exc}") from exc


def label_coverage(expected: dict, observation: dict | None) -> dict:
    observation = observation or {}
    scores = {}
    total_expected = 0
    total_matched = 0
    for field in LABEL_FIELDS:
        expected_labels = set(expected[field])
        predicted_labels = set(observation.get(field, []))
        matched = sorted(expected_labels & predicted_labels)
        missing = sorted(expected_labels - predicted_labels)
        total_expected += len(expected_labels)
        total_matched += len(matched)
        scores[field] = {
            "expected": sorted(expected_labels),
            "matched": matched,
            "missing": missing,
            "coverage": None if not expected_labels else len(matched) / len(expected_labels),
        }
    scores["overall_required_label_coverage"] = (
        None if total_expected == 0 else total_matched / total_expected
    )
    return scores


def run_case(case: dict, manifest_dir: Path, gateway_url: str, timeout: int) -> dict:
    image_path = manifest_dir / case["image_path"]
    result = {"id": case["id"]}
    if not image_path.is_file():
        result.update({"ok": False, "error": "image_not_found"})
        return result
    try:
        response = call_gateway(gateway_url, image_request(image_path), timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        result.update({"ok": False, "error": str(exc)})
        return result

    observation = response.get("observation") if response.get("ok") is True else None
    result.update(
        {
            "ok": response.get("ok") is True,
            "reason": response.get("reason"),
            "reply": response.get("reply"),
            "coverage": label_coverage(case["expected"], observation),
        }
    )
    return result


def summarize(results: list[dict]) -> dict:
    accepted = [result for result in results if result.get("ok")]
    coverage_values = [
        result["coverage"]["overall_required_label_coverage"]
        for result in accepted
        if result["coverage"]["overall_required_label_coverage"] is not None
    ]
    return {
        "cases": len(results),
        "accepted_cases": len(accepted),
        "accepted_rate": len(accepted) / len(results) if results else 0,
        "mean_required_label_coverage": (
            sum(coverage_values) / len(coverage_values) if coverage_values else None
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18768")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--report", type=Path, default=Path("reports/vision_benchmark_report.json"))
    args = parser.parse_args()

    try:
        cases = load_manifest(args.manifest)
    except ValueError as exc:
        parser.error(str(exc))

    results = [run_case(case, args.manifest.parent, args.gateway_url, args.timeout) for case in cases]
    report = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gateway_url": args.gateway_url,
        "summary": summarize(results),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report written: {args.report}")
    sys.exit(0 if report["summary"]["accepted_cases"] == len(results) else 2)


if __name__ == "__main__":
    main()
