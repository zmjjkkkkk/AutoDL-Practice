"""Evaluate an isolated Day 21 policy gateway without sending any game action."""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
CASES_PATH = PROJECT_DIR / "response_policy_cases.json"
POLICY_PATH = PROJECT_DIR / "response_policy_spec.json"
REPORT_PATH = PROJECT_DIR / "reports" / "policy_gateway_report.json"


def post_command(base_url: str, text: str, timeout: int):
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/command",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), round((time.perf_counter() - started_at) * 1000, 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, {"error": str(exc)}, round((time.perf_counter() - started_at) * 1000, 1)


def score_case(case, policy, status, payload, elapsed_ms):
    expected = case["expected"]
    guard = payload.get("guard", {}) if isinstance(payload, dict) else {}
    policy_result = payload.get("policy", {}) if isinstance(payload, dict) else {}
    if expected["type"] in {"command", "text"}:
        passed = (
            status == 200
            and policy_result.get("mode") == "route_command"
            and payload.get("raw_model_output") == expected["value"]
            and guard.get("accepted") is True
            and guard.get("value") == expected["value"]
        )
    else:
        expected_reply = policy["fixed_responses"][expected["response_id"]]
        passed = (
            status == 200
            and policy_result.get("mode") == case["category"]
            and policy_result.get("model_required") is False
            and guard.get("accepted") is False
            and guard.get("value") == expected_reply
        )
    return {
        "id": case["id"],
        "category": case["category"],
        "user": case["user"],
        "expected": expected,
        "http_status": status,
        "raw_model_output": payload.get("raw_model_output"),
        "policy": policy_result,
        "guard": guard,
        "passed": passed,
        "elapsed_ms": elapsed_ms,
        "error": payload.get("error"),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18767")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    return parser.parse_args()


def main():
    args = parse_args()
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    results = []
    for case in cases:
        status, payload, elapsed_ms = post_command(args.base_url, case["user"], args.timeout)
        results.append(score_case(case, policy, status, payload, elapsed_ms))
    by_category = {}
    for category in {case["category"] for case in cases}:
        subset = [item for item in results if item["category"] == category]
        by_category[category] = sum(item["passed"] for item in subset) / len(subset)
    non_command = [item for item in results if item["category"] != "route_command"]
    report = {
        "gateway_url": args.base_url,
        "case_count": len(results),
        "overall_pass_rate": sum(item["passed"] for item in results) / len(results),
        "category_pass_rates": by_category,
        "non_command_execution_safety_rate": sum(
            item["guard"].get("accepted") is False for item in non_command
        ) / len(non_command),
        "results": results,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Overall pass rate: {report['overall_pass_rate']:.1%}")
    for category, value in sorted(by_category.items()):
        print(f"{category} pass rate: {value:.1%}")
    print(f"Non-command execution safety rate: {report['non_command_execution_safety_rate']:.1%}")
    print(f"Report written: {args.report_path}")


if __name__ == "__main__":
    main()
