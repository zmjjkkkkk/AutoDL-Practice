import argparse
import json
import random
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = BASE_DIR / "source_data"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data"


def read_jsonl(path: Path):
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} 第 {line_number} 行不是合法 JSON：{exc}") from exc
        records.append(record)
    return records


def validate_record(record, source_name):
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) < 3:
        raise ValueError(f"{source_name} 缺少完整 messages")

    roles = [message.get("role") for message in messages]
    if roles[0] != "system" or "user" not in roles or roles[-1] != "assistant":
        raise ValueError(f"{source_name} 的角色顺序不符合 system/user/assistant")

    for message in messages:
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ValueError(f"{source_name} 存在空消息")


def user_key(record):
    user_messages = [
        message["content"].strip()
        for message in record["messages"]
        if message["role"] == "user"
    ]
    return "\n".join(user_messages)


def write_jsonl(path: Path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--eval-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source_files = sorted(args.source_dir.glob("*.jsonl"))
    if not source_files:
        raise FileNotFoundError(f"没有在 {args.source_dir} 找到 JSONL 文件")

    unique_records = {}
    skipped_duplicates = 0

    for source_file in source_files:
        for index, record in enumerate(read_jsonl(source_file), 1):
            validate_record(record, f"{source_file.name}:{index}")
            key = user_key(record)
            if key in unique_records:
                skipped_duplicates += 1
                continue
            unique_records[key] = record

    records = list(unique_records.values())
    random.Random(args.seed).shuffle(records)

    if len(records) < 4:
        raise ValueError("有效样本少于 4 条，不建议开始训练")

    eval_count = max(1, round(len(records) * args.eval_ratio))
    eval_records = records[:eval_count]
    train_records = records[eval_count:]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    train_path = args.output_dir / "train.jsonl"
    eval_path = args.output_dir / "eval.jsonl"
    write_jsonl(train_path, train_records)
    write_jsonl(eval_path, eval_records)

    print(f"来源文件数：{len(source_files)}")
    print(f"去重后样本：{len(records)}")
    print(f"重复样本跳过：{skipped_duplicates}")
    print(f"训练集：{len(train_records)} -> {train_path}")
    print(f"验证集：{len(eval_records)} -> {eval_path}")


if __name__ == "__main__":
    main()
