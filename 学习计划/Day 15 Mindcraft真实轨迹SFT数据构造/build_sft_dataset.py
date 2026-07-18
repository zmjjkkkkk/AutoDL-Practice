"""Build a small, reviewable Mindcraft SFT dataset from verified behavior seeds."""

import json
import random
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "seed_behaviors.json"
OUTPUT_DIR = BASE_DIR / "output"
TRAIN_PATH = OUTPUT_DIR / "mindcraft_sft_train.jsonl"
EVAL_PATH = OUTPUT_DIR / "mindcraft_sft_eval.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "mindcraft_sft_manifest.json"
EVAL_PER_INTENT = 2
SPLIT_SEED = 20260715


def make_example(system_prompt, behavior, user_text):
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": behavior["assistant"]},
        ],
        "metadata": {
            "intent_id": behavior["id"],
            "source_prompt": behavior["source_prompt"],
            "label_status": behavior["label_status"],
            "augmentation": "human_reviewed_paraphrase",
        },
    }


def split_variants(behavior):
    variants = list(dict.fromkeys(item.strip() for item in behavior["variants"] if item.strip()))
    if len(variants) <= EVAL_PER_INTENT:
        raise ValueError(f"{behavior['id']} needs more than {EVAL_PER_INTENT} unique variants")

    rng = random.Random(f"{SPLIT_SEED}:{behavior['id']}")
    rng.shuffle(variants)
    return variants[EVAL_PER_INTENT:], variants[:EVAL_PER_INTENT]


def validate_example(example):
    messages = example["messages"]
    if [message["role"] for message in messages] != ["system", "user", "assistant"]:
        raise ValueError("Every example must contain system, user, and assistant messages in order")
    assistant = messages[-1]["content"]
    intent = example["metadata"]["intent_id"]
    if intent != "greeting" and not assistant.startswith("!"):
        raise ValueError(f"Action intent {intent} does not have a Mindcraft command label")


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    seed_data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    system_prompt = seed_data["system_prompt"]
    train_rows = []
    eval_rows = []
    intent_counts = {}

    for behavior in seed_data["records"]:
        if not behavior.get("include_in_training", False):
            continue
        train_variants, eval_variants = split_variants(behavior)
        train_examples = [make_example(system_prompt, behavior, text) for text in train_variants]
        eval_examples = [make_example(system_prompt, behavior, text) for text in eval_variants]
        for example in train_examples + eval_examples:
            validate_example(example)
        train_rows.extend(train_examples)
        eval_rows.extend(eval_examples)
        intent_counts[behavior["id"]] = {
            "train": len(train_examples),
            "eval": len(eval_examples),
            "assistant": behavior["assistant"],
            "label_status": behavior["label_status"],
        }

    random.Random(SPLIT_SEED).shuffle(train_rows)
    random.Random(SPLIT_SEED + 1).shuffle(eval_rows)
    OUTPUT_DIR.mkdir(exist_ok=True)
    write_jsonl(TRAIN_PATH, train_rows)
    write_jsonl(EVAL_PATH, eval_rows)

    manifest = {
        "schema_version": "1.0",
        "source_baseline": seed_data["source_baseline"],
        "split_seed": SPLIT_SEED,
        "eval_per_intent": EVAL_PER_INTENT,
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "intent_counts": intent_counts,
        "train_command_counts": dict(Counter(row["messages"][-1]["content"] for row in train_rows)),
        "eval_command_counts": dict(Counter(row["messages"][-1]["content"] for row in eval_rows)),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated {len(train_rows)} training examples: {TRAIN_PATH}")
    print(f"Generated {len(eval_rows)} evaluation examples: {EVAL_PATH}")
    print(f"Wrote manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
