import json
import random
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "source_data"
CORRECTION_FILE = BASE_DIR / "correction_samples.jsonl"
OUTPUT_DIR = BASE_DIR / "data"


def read_jsonl(path):
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} JSON 错误：{exc}") from exc
        messages = record.get("messages", [])
        if len(messages) < 3 or messages[-1].get("role") != "assistant":
            raise ValueError(f"{path.name}:{line_number} 不是完整对话样本")
        records.append(record)
    return records


def user_key(record):
    return "\n".join(
        message["content"].strip()
        for message in record["messages"]
        if message["role"] == "user"
    )


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    source_files = sorted(SOURCE_DIR.glob("*.jsonl"))
    if not source_files:
        raise FileNotFoundError(f"{SOURCE_DIR} 中没有 Day 5 数据")

    records = []
    for source_file in source_files:
        records.extend(read_jsonl(source_file))
    correction_records = read_jsonl(CORRECTION_FILE)
    records.extend(correction_records)

    unique = {}
    for record in records:
        key = user_key(record)
        is_correction = record.get("metadata", {}).get("source") == "day8_manual_correction"
        if key not in unique or is_correction:
            unique[key] = record

    final_records = list(unique.values())
    random.Random(42).shuffle(final_records)
    eval_count = max(2, round(len(final_records) * 0.15))
    eval_records = final_records[:eval_count]
    train_records = final_records[eval_count:]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT_DIR / "train.jsonl", train_records)
    write_jsonl(OUTPUT_DIR / "eval.jsonl", eval_records)

    print(f"Day 5 原始文件：{len(source_files)}")
    print(f"人工纠偏样本：{len(correction_records)}")
    print(f"去重后总样本：{len(final_records)}")
    print(f"最终训练集：{len(train_records)}")
    print(f"最终验证集：{len(eval_records)}")


if __name__ == "__main__":
    main()
