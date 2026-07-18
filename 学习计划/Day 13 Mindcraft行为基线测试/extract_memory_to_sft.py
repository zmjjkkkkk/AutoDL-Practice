import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
MEMORY_PATH = (
    PROJECT_ROOT
    / "学习计划"
    / "Day 11 Mindcraft训练项目启动"
    / "mindcraft-develop"
    / "bots"
    / "deepseek_env"
    / "memory.json"
)
SFT_DIR = PROJECT_ROOT / "data" / "mindcraft_training" / "sft"

SYSTEM_PROMPT = (
    "You are a Minecraft agent controlled through Mindcraft. "
    "Understand the player's instruction, respond briefly, and use valid Mindcraft commands when action is needed."
)


def normalize_user_content(content: str) -> str:
    # Mindcraft history often records messages like "robot: hello".
    if ":" in content:
        return content.split(":", 1)[1].strip()
    return content.strip()


def build_examples(turns):
    examples = []
    last_user = None
    context = []

    for turn in turns:
        role = turn.get("role")
        content = str(turn.get("content", "")).strip()
        if not content:
            continue

        if role == "user":
            last_user = normalize_user_content(content)
        elif role == "assistant" and last_user:
            examples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *context[-6:],
                    {"role": "user", "content": last_user},
                    {"role": "assistant", "content": content},
                ],
                "metadata": {
                    "source": "mindcraft memory.json",
                    "agent": "deepseek_env",
                    "quality": "raw_draft",
                },
            })
            context.append({"role": "user", "content": last_user})
            context.append({"role": "assistant", "content": content})
            last_user = None
        elif role == "system":
            context.append({"role": "system", "content": content})

    return examples


def main():
    if not MEMORY_PATH.exists():
        raise FileNotFoundError(f"未找到 memory.json：{MEMORY_PATH}")

    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    turns = memory.get("turns", [])
    examples = build_examples(turns)

    SFT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = SFT_DIR / f"mindcraft_sft_draft_{timestamp}.jsonl"
    latest_path = SFT_DIR / "latest_mindcraft_sft_draft.jsonl"

    lines = [json.dumps(item, ensure_ascii=False) for item in examples]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    latest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"已生成 {len(examples)} 条 SFT 草稿：{output_path}")
    print(f"latest: {latest_path}")


if __name__ == "__main__":
    main()

