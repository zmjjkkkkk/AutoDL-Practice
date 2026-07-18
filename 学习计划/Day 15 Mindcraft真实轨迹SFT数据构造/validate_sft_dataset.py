"""Validate the generated Mindcraft SFT JSONL files before training."""

import json
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATASETS = {
    "train": BASE_DIR / "output" / "mindcraft_sft_train.jsonl",
    "eval": BASE_DIR / "output" / "mindcraft_sft_eval.jsonl",
}


def load_jsonl(path):
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} is not valid JSON: {exc}") from exc
    return rows


def inspect_rows(name, rows):
    prompts = set()
    commands = Counter()
    for row in rows:
        messages = row.get("messages", [])
        if [message.get("role") for message in messages] != ["system", "user", "assistant"]:
            raise ValueError(f"{name}: invalid message roles")
        prompt = messages[1].get("content", "").strip().lower()
        if not prompt or prompt in prompts:
            raise ValueError(f"{name}: empty or duplicate user prompt: {prompt!r}")
        prompts.add(prompt)
        assistant = messages[2].get("content", "")
        intent = row.get("metadata", {}).get("intent_id")
        if intent != "greeting" and not assistant.startswith("!"):
            raise ValueError(f"{name}: {intent} is missing a command label")
        commands[assistant] += 1
    return prompts, commands


def main():
    loaded = {name: load_jsonl(path) for name, path in DATASETS.items()}
    train_prompts, train_commands = inspect_rows("train", loaded["train"])
    eval_prompts, eval_commands = inspect_rows("eval", loaded["eval"])
    overlap = train_prompts & eval_prompts
    if overlap:
        raise ValueError(f"Train/eval prompt leakage: {sorted(overlap)}")

    print("Dataset validation passed.")
    print(f"Train examples: {len(loaded['train'])} | commands: {dict(train_commands)}")
    print(f"Eval examples: {len(loaded['eval'])} | commands: {dict(eval_commands)}")


if __name__ == "__main__":
    main()
