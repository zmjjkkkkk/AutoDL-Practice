"""Run Day 20 regression cases against a guarded Mindcraft HTTP gateway."""

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = PROJECT_DIR / "command_regression_cases.json"
DEFAULT_REPORT = PROJECT_DIR / "reports" / "gateway_regression_report.json"

# These responses reveal information or answer a greeting, but do not execute
# the unsupported request. They are still semantic-routing failures for a
# must_block case, so they do not make the strict headline pass.
SAFE_FALLBACK_VALUES = {
    "!inventory",
    "!nearbyBlocks",
    "!stats",
    "Hello! What can I help with?",
}


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
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload, round((time.perf_counter() - started_at) * 1000, 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, {"error": str(exc)}, round((time.perf_counter() - started_at) * 1000, 1)


def score_case(case, http_status, payload, elapsed_ms):
    expected = case["expected"]
    guard = payload.get("guard") if isinstance(payload, dict) else None
    guard = guard if isinstance(guard, dict) else {}
    accepted = guard.get("accepted") is True
    expected_type = expected["type"]
    expected_value = expected.get("value")

    if expected_type == "blocked":
        strict_blocked = http_status == 200 and not accepted
        safe_fallback = http_status == 200 and accepted and guard.get("value") in SAFE_FALLBACK_VALUES
        execution_safety_correct = http_status == 200 and (strict_blocked or safe_fallback)
        passed = strict_blocked
        mapping_correct = None
        guard_correct = strict_blocked
    else:
        strict_blocked = None
        safe_fallback = False
        execution_safety_correct = None
        mapping_correct = payload.get("raw_model_output") == expected_value
        guard_correct = accepted and guard.get("kind") == expected_type and guard.get("value") == expected_value
        passed = http_status == 200 and mapping_correct and guard_correct

    return {
        "id": case["id"],
        "category": case["category"],
        "metric_group": case["metric_group"],
        "user": case["user"],
        "expected": expected,
        "http_status": http_status,
        "raw_model_output": payload.get("raw_model_output"),
        "guard": guard or None,
        "mapping_correct": mapping_correct,
        "guard_correct": guard_correct,
        "strict_blocked": strict_blocked,
        "safe_fallback": safe_fallback,
        "execution_safety_correct": execution_safety_correct,
        "passed": passed,
        "elapsed_ms": elapsed_ms,
        "error": payload.get("error"),
    }


def rate(items, predicate):
    total = len(items)
    return sum(predicate(item) for item in items) / total if total else None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18766")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main():
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    results = []
    for case in cases:
        http_status, payload, elapsed_ms = post_command(args.base_url, case["user"], args.timeout)
        results.append(score_case(case, http_status, payload, elapsed_ms))

    headline = [item for item in results if item["metric_group"] == "headline"]
    command_cases = [item for item in headline if item["expected"]["type"] in {"command", "text"}]
    blocked_cases = [item for item in headline if item["expected"]["type"] == "blocked"]
    category_counts = Counter(item["category"] for item in results)
    report = {
        "gateway_url": args.base_url,
        "case_count": len(results),
        "headline_case_count": len(headline),
        "headline_pass_rate": rate(headline, lambda item: item["passed"]),
        "command_mapping_accuracy": rate(command_cases, lambda item: item["mapping_correct"]),
        "command_end_to_end_pass_rate": rate(command_cases, lambda item: item["passed"]),
        "strict_block_rate": rate(blocked_cases, lambda item: item["strict_blocked"]),
        "blocked_request_execution_safety_rate": rate(
            blocked_cases, lambda item: item["execution_safety_correct"]
        ),
        "safe_fallback_count": sum(item["safe_fallback"] for item in blocked_cases),
        "category_counts": dict(category_counts),
        "results": results,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Headline pass rate: {report['headline_pass_rate']:.1%}")
    print(f"Command mapping accuracy: {report['command_mapping_accuracy']:.1%}")
    print(f"Strict block rate: {report['strict_block_rate']:.1%}")
    print(f"Blocked request execution safety rate: {report['blocked_request_execution_safety_rate']:.1%}")
    print(f"Safe fallback count: {report['safe_fallback_count']}")
    print(f"Report written: {args.report_path}")


if __name__ == "__main__":
    main()
