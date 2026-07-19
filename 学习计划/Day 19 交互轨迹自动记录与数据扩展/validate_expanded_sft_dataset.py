"""Validate Day 19 experimental SFT output before it is sent to remote training."""

import json
from collections import Counter
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "output"
DATASETS = {
    "train": DATA_DIR / "mindcraft_sft_train.jsonl",
    "eval": DATA_DIR / "mindcraft_sft_eval.jsonl",
}


def load_jsonl(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Build the dataset first: {path}")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} is not valid JSON") from exc
    return rows


def inspect_rows(split_name, rows):
    prompts = set()
    intents = Counter()
    sources = Counter()
    for row in rows:
        messages = row.get("messages", [])
        roles = [message.get("role") for message in messages]
        if roles != ["system", "user", "assistant"]:
            raise ValueError(f"{split_name}: invalid message roles: {roles}")
        prompt = messages[1].get("content", "").strip().lower()
        assistant = messages[2].get("content", "").strip()
        metadata = row.get("metadata", {})
        if not prompt or prompt in prompts:
            raise ValueError(f"{split_name}: empty or duplicated prompt: {prompt!r}")
        if not assistant.startswith("!") and metadata.get("intent_id") != "greeting":
            raise ValueError(f"{split_name}: non-greeting without command label: {assistant!r}")
        prompts.add(prompt)
        intents[metadata.get("intent_id", "missing")] += 1
        sources[metadata.get("source", "missing")] += 1
    return prompts, intents, sources


def main():
    loaded = {name: load_jsonl(path) for name, path in DATASETS.items()}
    train_prompts, train_intents, train_sources = inspect_rows("train", loaded["train"])
    eval_prompts, eval_intents, eval_sources = inspect_rows("eval", loaded["eval"])
    overlap = train_prompts & eval_prompts
    if overlap:
        raise ValueError(f"Train/eval prompt leakage: {sorted(overlap)}")

    print("Day 19 expanded dataset validation passed.")
    print(f"Train examples: {len(loaded['train'])} | intents: {len(train_intents)} | sources: {dict(train_sources)}")
    print(f"Eval examples: {len(loaded['eval'])} | intents: {len(eval_intents)} | sources: {dict(eval_sources)}")
    print("Reminder: day19_provisional rows require real-game verification before production allowlist changes.")


if __name__ == "__main__":
    main()
