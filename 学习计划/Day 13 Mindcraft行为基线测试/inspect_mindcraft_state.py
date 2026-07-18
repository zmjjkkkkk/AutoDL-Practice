import json
import shutil
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
MINDCRAFT_DIR = PROJECT_ROOT / "学习计划" / "Day 11 Mindcraft训练项目启动" / "mindcraft-develop"
BOT_DIR = MINDCRAFT_DIR / "bots" / "deepseek_env"
RAW_LOG_DIR = PROJECT_ROOT / "data" / "mindcraft_training" / "raw_logs"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    print("Mindcraft 状态扫描")
    print(f"Bot 目录：{BOT_DIR}")

    if not BOT_DIR.exists():
        print("未找到 bot 目录。请先成功运行一次 Mindcraft。")
        return

    for child in sorted(BOT_DIR.iterdir()):
        if child.is_dir():
            count = sum(1 for _ in child.rglob("*"))
            print(f"- {child.name}/ ({count} items)")
        else:
            print(f"- {child.name} ({child.stat().st_size} bytes)")

    memory_path = BOT_DIR / "memory.json"
    if memory_path.exists():
        memory = read_json(memory_path)
        turns = memory.get("turns", [])
        print(f"\nmemory.json turns: {len(turns)}")
        for turn in turns[-8:]:
            role = turn.get("role", "?")
            content = str(turn.get("content", "")).replace("\n", " ")
            print(f"{role}: {content[:160]}")

        RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = RAW_LOG_DIR / f"deepseek_env_memory_{timestamp}.json"
        shutil.copy2(memory_path, snapshot_path)
        print(f"\n已保存 memory 快照：{snapshot_path}")
    else:
        print("\n未找到 memory.json。")


if __name__ == "__main__":
    main()

