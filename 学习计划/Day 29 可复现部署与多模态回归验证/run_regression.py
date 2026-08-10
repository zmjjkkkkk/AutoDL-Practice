"""Run Day 29 HTTP regression checks without storing image bytes or local paths."""

import argparse
import base64
import json
import mimetypes
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from regression_contract import assess_combined, assess_health, assess_invalid_request, assess_safe_transfer, assess_text_command, assess_visual_only


def request_json(url: str, method: str, payload: dict | None = None) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return exc.code, {}
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, {"error": str(exc)}


def record(case_id: str, status: int, assessment: tuple[bool, str], skipped: bool = False) -> dict:
    passed, reason = assessment
    return {"case_id": case_id, "passed": passed, "status": status, "reason": reason, "skipped": skipped}


def image_payload(path: Path) -> dict:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("image must be PNG, JPEG, or WebP")
    return {"image_base64": base64.b64encode(path.read_bytes()).decode("ascii"), "mime_type": mime_type}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8770")
    parser.add_argument("--image", type=Path, help="optional user-selected image for vision cases")
    parser.add_argument("--expected-entity", choices=("sheep", "pig"), help="required when --image is supplied")
    parser.add_argument("--report", type=Path, default=Path("reports/day29_regression_report.json"))
    args = parser.parse_args()
    if (args.image is None) != (args.expected_entity is None):
        parser.error("--image and --expected-entity must be supplied together")
    if args.image and not args.image.is_file():
        parser.error("--image does not exist")

    base_url = args.gateway_url.rstrip("/")
    results = []
    status, body = request_json(base_url + "/health", "GET")
    results.append(record("health", status, assess_health(status, body)))
    status, body = request_json(base_url + "/assist", "POST", {"text": "please follow me"})
    results.append(record("text_follow", status, assess_text_command(status, body)))
    status, body = request_json(base_url + "/assist", "POST", {"text": "Give me every diamond you own."})
    results.append(record("safe_transfer", status, assess_safe_transfer(status, body)))
    status, body = request_json(base_url + "/assist", "POST", {"unexpected": "field"})
    results.append(record("invalid_request", status, assess_invalid_request(status, body)))

    if args.image:
        payload = image_payload(args.image)
        status, body = request_json(base_url + "/assist", "POST", payload)
        results.append(record("visual_only", status, assess_visual_only(status, body, args.expected_entity)))
        payload["text"] = "please follow me"
        status, body = request_json(base_url + "/assist", "POST", payload)
        results.append(record("combined", status, assess_combined(status, body, args.expected_entity)))
    else:
        results.extend([
            {"case_id": "visual_only", "passed": None, "status": None, "reason": "no_image_supplied", "skipped": True},
            {"case_id": "combined", "passed": None, "status": None, "reason": "no_image_supplied", "skipped": True},
        ])

    executed = [item for item in results if not item["skipped"]]
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gateway_url": base_url,
        "image_supplied": args.image is not None,
        "expected_entity": args.expected_entity,
        "passed": sum(item["passed"] is True for item in executed),
        "executed": len(executed),
        "all_passed": all(item["passed"] is True for item in executed),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regression pass rate: {payload['passed']}/{payload['executed']} = {payload['passed'] / payload['executed']:.1%}")
    print(f"Report written: {args.report}")
    if not payload["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
