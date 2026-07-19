"""Combine manual T/F notes with Day 19 JSONL traces into a review queue.

The output is intentionally a review artifact, not a training file. A human must
choose the correct expected response before any failed case reaches SFT data.
"""

import argparse
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


DAY19_DIR = Path(__file__).resolve().parent
ROOT_DIR = DAY19_DIR.parents[1]
DEFAULT_LOG_DIR = DAY19_DIR / "logs"
DEFAULT_RECORD_FILE = ROOT_DIR / "record.txt"
COMMAND_DIR = ROOT_DIR / "学习计划" / "Day 11 Mindcraft训练项目启动" / "mindcraft-develop" / "src" / "agent" / "commands"


def parse_manual_record(path: Path):
    labeled = []
    observations = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(
            r"^(\d+)\.\s*(.+?)\s+([TF])(?=(?:\s|[,，]|$))(?:\s*[,，]?\s*(.*))?$",
            line,
            re.IGNORECASE,
        )
        if match:
            labeled.append(
                {
                    "record_index": int(match.group(1)),
                    "prompt": match.group(2).strip(),
                    "human_label": match.group(3).upper(),
                    "human_note": (match.group(4) or "").strip(),
                }
            )
            continue
        observation = re.match(r"^(\d+)\.\s*(.+)$", line)
        if observation:
            observations.append(
                {
                    "record_index": int(observation.group(1)),
                    "observation": observation.group(2).strip(),
                }
            )
    return labeled, observations


def load_trace_records(log_dir: Path):
    records = []
    for path in sorted(log_dir.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            record["_source"] = path.name
            record["_line"] = line_number
            records.append(record)
    return sorted(records, key=lambda item: item.get("timestamp", ""))


def supported_commands():
    names = set()
    for path in COMMAND_DIR.glob("*.js"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        names.update(re.findall(r"name:\s*['\"](![A-Za-z]+)", content))
    return names


def command_name(text):
    match = re.match(r"\s*(![A-Za-z]+)", text or "")
    return match.group(1) if match else None


def normalize(text: str):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def similarity(left: str, right: str):
    left_normalized = normalize(left)
    right_normalized = normalize(right)
    if not left_normalized or not right_normalized:
        return 0.0
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_words = set(left_normalized.split())
    right_words = set(right_normalized.split())
    overlap_score = len(left_words & right_words) / len(left_words | right_words)
    return round(sequence_score * 0.65 + overlap_score * 0.35, 3)


def attach_feedback(records):
    for index, record in enumerate(records):
        if record.get("event") != "model_decision":
            continue
        record["game_feedback"] = None
        session_id = record.get("session_id")
        returned = record.get("returned_to_mindcraft")
        for later in records[index + 1 :]:
            if later.get("session_id") != session_id:
                break
            if later.get("event") == "player_request":
                break
            if later.get("event") == "game_feedback" and later.get("command") == returned:
                record["game_feedback"] = later.get("feedback")
                break
    return [record for record in records if record.get("event") == "model_decision"]


def recommendation(label, decision, supported):
    if label == "T":
        return "confirmed_success", "保留为已验证能力；可补充同义表达作为训练候选。"
    if decision is None:
        return "missing_trace", "没有可靠自动轨迹；仅保留为人工观察，不直接加入 SFT。"

    guard = decision.get("guard") or {}
    raw_command = command_name(decision.get("raw_model_output", ""))
    feedback = (decision.get("game_feedback") or "").lower()
    if guard.get("accepted") is not True:
        if raw_command in supported:
            return "allowlist_or_parameter_gap", "先确认参数和游戏前置条件，再同时扩充训练集、评测集与白名单。"
        return "model_command_mapping_gap", "先在 Mindcraft 源码中确定真实可用命令和参数，再人工写标准答案。"
    if any(token in feedback for token in ("error", "timeout", "path not found", "failed", "no path")):
        return "execution_environment_failure", "模型已给出允许命令；优先排查高度、距离、路径、工具或库存，而不是立刻再训练。"
    return "accepted_but_semantically_wrong", "白名单通过但与玩家意图不符；写出正确目标，作为高优先级对比评测与训练样本。"


def build_queue(manual_items, decisions, supported):
    unused = list(decisions)
    queue = []
    for item in manual_items:
        scored = [(similarity(item["prompt"], decision.get("player_text", "")), decision) for decision in unused]
        score, decision = max(scored, default=(0.0, None), key=lambda pair: pair[0])
        if score < 0.34:
            decision = None
        else:
            unused.remove(decision)

        category, next_step = recommendation(item["human_label"], decision, supported)
        entry = {
            **item,
            "match_confidence": score if decision else 0.0,
            "category": category,
            "recommended_next_step": next_step,
            "needs_human_expected_answer": item["human_label"] == "F" and category not in {"execution_environment_failure", "missing_trace"},
        }
        if decision:
            entry["trace"] = {
                "timestamp": decision.get("timestamp"),
                "source": decision.get("_source"),
                "player_text": decision.get("player_text"),
                "raw_model_output": decision.get("raw_model_output"),
                "guard": decision.get("guard"),
                "returned_to_mindcraft": decision.get("returned_to_mindcraft"),
                "game_feedback": decision.get("game_feedback"),
            }
        queue.append(entry)
    return queue


def main():
    parser = argparse.ArgumentParser(description="Build a human-review queue from record.txt and Day 19 JSONL logs.")
    parser.add_argument("--record-file", type=Path, default=DEFAULT_RECORD_FILE)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_LOG_DIR / "review_queue.json")
    args = parser.parse_args()

    if not args.record_file.exists():
        raise FileNotFoundError(f"Manual record file not found: {args.record_file}")
    if not args.log_dir.exists():
        raise FileNotFoundError(f"Interaction log directory not found: {args.log_dir}")

    manual_items, observations = parse_manual_record(args.record_file)
    decisions = attach_feedback(load_trace_records(args.log_dir))
    supported = sorted(supported_commands())
    queue = build_queue(manual_items, decisions, set(supported))
    categories = Counter(item["category"] for item in queue)

    payload = {
        "manual_record_file": str(args.record_file),
        "trace_log_dir": str(args.log_dir),
        "labeled_items": len(manual_items),
        "unlabeled_observations": observations,
        "supported_mindcraft_commands": supported,
        "category_counts": dict(categories),
        "review_queue": queue,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Review queue written: {args.output}")
    print(f"Labeled items: {len(manual_items)} | Trace decisions: {len(decisions)}")
    print(f"Categories: {dict(categories)}")
    print("Do not train this file directly. Fill in a verified expected answer for each eligible F item first.")


if __name__ == "__main__":
    main()
