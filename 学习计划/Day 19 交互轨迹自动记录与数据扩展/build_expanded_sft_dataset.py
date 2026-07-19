"""Build a Day 19 experimental SFT dataset without changing the Day 15 archive."""

import argparse
import json
import random
from collections import Counter
from pathlib import Path


DAY19_DIR = Path(__file__).resolve().parent
ROOT_DIR = DAY19_DIR.parents[1]
DAY15_SEED = ROOT_DIR / "学习计划" / "Day 15 Mindcraft真实轨迹SFT数据构造" / "seed_behaviors.json"
EXTENSION_SEED = DAY19_DIR / "extension_behaviors.json"
OUTPUT_DIR = DAY19_DIR / "output"
EVAL_PER_INTENT = 2
SPLIT_SEED = 20260719


def read_records(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["system_prompt"], data["records"]


def split_variants(record):
    variants = list(dict.fromkeys(text.strip() for text in record["variants"] if text.strip()))
    if len(variants) <= EVAL_PER_INTENT:
        raise ValueError(f"{record['id']} needs more than {EVAL_PER_INTENT} variants")
    rng = random.Random(f"{SPLIT_SEED}:{record['id']}")
    rng.shuffle(variants)
    return variants[EVAL_PER_INTENT:], variants[:EVAL_PER_INTENT]


def make_example(system_prompt, record, user_text, source):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": record["assistant"]},
        ],
        "metadata": {
            "intent_id": record["id"],
            "source": source,
            "label_status": record["label_status"],
            "runtime_requirement": record.get("runtime_requirement"),
            "augmentation": "human_reviewed_paraphrase",
        },
    }


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build Day 19 experimental Mindcraft SFT data.")
    parser.add_argument(
        "--include-provisional",
        action="store_true",
        help="Include source-API-confirmed records that still need a real game test.",
    )
    args = parser.parse_args()

    system_prompt, base_records = read_records(DAY15_SEED)
    extension_prompt, extension_records = read_records(EXTENSION_SEED)
    if system_prompt != extension_prompt:
        raise ValueError("Day 15 and Day 19 system prompts must match before merging data")

    records = [(record, "day15_verified") for record in base_records if record.get("include_in_training")]
    if args.include_provisional:
        records.extend(
            (record, "day19_provisional")
            for record in extension_records
            if record.get("include_in_experimental_training")
        )

    seen_prompts = set()
    train_rows = []
    eval_rows = []
    manifest_intents = {}
    for record, source in records:
        train_variants, eval_variants = split_variants(record)
        rows_by_split = {"train": train_variants, "eval": eval_variants}
        for split_name, variants in rows_by_split.items():
            for variant in variants:
                key = variant.lower()
                if key in seen_prompts:
                    raise ValueError(f"Duplicate prompt across intents: {variant!r}")
                seen_prompts.add(key)
                row = make_example(system_prompt, record, variant, source)
                (train_rows if split_name == "train" else eval_rows).append(row)
        manifest_intents[record["id"]] = {
            "train": len(train_variants),
            "eval": len(eval_variants),
            "assistant": record["assistant"],
            "source": source,
            "label_status": record["label_status"],
        }

    random.Random(SPLIT_SEED).shuffle(train_rows)
    random.Random(SPLIT_SEED + 1).shuffle(eval_rows)
    OUTPUT_DIR.mkdir(exist_ok=True)
    train_path = OUTPUT_DIR / "mindcraft_sft_train.jsonl"
    eval_path = OUTPUT_DIR / "mindcraft_sft_eval.jsonl"
    manifest_path = OUTPUT_DIR / "mindcraft_sft_manifest.json"
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)
    manifest = {
        "split_seed": SPLIT_SEED,
        "include_provisional": args.include_provisional,
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "intents": manifest_intents,
        "train_command_counts": dict(Counter(row["messages"][-1]["content"] for row in train_rows)),
        "eval_command_counts": dict(Counter(row["messages"][-1]["content"] for row in eval_rows)),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated train={len(train_rows)}, eval={len(eval_rows)}")
    print(f"Provisional Day 19 records included: {args.include_provisional}")
    print(f"Train: {train_path}")
    print(f"Eval: {eval_path}")


if __name__ == "__main__":
    main()
