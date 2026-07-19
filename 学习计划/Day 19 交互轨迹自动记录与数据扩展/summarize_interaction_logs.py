"""Summarize local-only Mindcraft interaction JSONL logs for Day 19 review."""

import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = PROJECT_DIR / "logs"


def load_records(log_dir: Path):
    records = []
    invalid_lines = 0
    for path in sorted(log_dir.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            record["_source"] = path.name
            record["_line"] = line_number
            records.append(record)
    return records, invalid_lines


def main():
    parser = argparse.ArgumentParser(description="Summarize Day 19 Mindcraft interaction logs.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--show-last", type=int, default=10)
    args = parser.parse_args()

    if not args.log_dir.exists():
        print(f"No log directory yet: {args.log_dir}")
        print("Start Mindcraft with the mindcraft_lora profile, then run this command again.")
        return

    records, invalid_lines = load_records(args.log_dir)
    if not records:
        print(f"No JSONL interaction records found in: {args.log_dir}")
        return

    events = Counter(record.get("event", "unknown") for record in records)
    decisions = [record for record in records if record.get("event") == "model_decision"]
    accepted = [record for record in decisions if record.get("guard", {}).get("accepted") is True]
    blocked = [record for record in decisions if record.get("guard", {}).get("accepted") is False]
    reasons = Counter(record.get("guard", {}).get("reason", "missing_guard") for record in blocked)
    commands = Counter(
        record.get("returned_to_mindcraft", "")
        for record in accepted
        if record.get("guard", {}).get("kind") == "command"
    )
    latencies = [record["latency_ms"] for record in decisions if isinstance(record.get("latency_ms"), int)]

    print(f"Log directory: {args.log_dir}")
    print(f"Records: {len(records)} | Invalid JSONL lines: {invalid_lines}")
    print(f"Events: {dict(events)}")
    print(f"Model decisions: {len(decisions)} | Accepted: {len(accepted)} | Blocked: {len(blocked)}")
    if latencies:
        print(f"Decision latency ms: avg={sum(latencies) / len(latencies):.1f}, max={max(latencies)}")
    if commands:
        print("Approved commands:")
        for command, count in commands.most_common():
            print(f"  {count:>3}  {command}")
    if reasons:
        print("Blocked reasons:")
        for reason, count in reasons.most_common():
            print(f"  {count:>3}  {reason}")

    if args.show_last > 0:
        print(f"Last {min(args.show_last, len(decisions))} model decisions:")
        for record in decisions[-args.show_last:]:
            guard = record.get("guard") or {}
            print(
                f"  [{guard.get('reason', 'missing_guard')}] "
                f"{record.get('player_text', '')!r} -> {record.get('returned_to_mindcraft', '')!r}"
            )


if __name__ == "__main__":
    main()
