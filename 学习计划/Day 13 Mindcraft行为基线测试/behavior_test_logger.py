import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
TEST_CASES_PATH = BASE_DIR / "test_cases.json"
OUTPUT_DIR = BASE_DIR / "output"
EVAL_DATA_DIR = PROJECT_ROOT / "data" / "mindcraft_training" / "eval_results"

FAILURE_TYPES = [
    "none",
    "no_response",
    "misunderstood_instruction",
    "wrong_command",
    "pathfinding_failed",
    "target_not_found",
    "action_started_but_not_completed",
    "inventory_mismatch",
    "too_slow",
    "api_error",
    "other",
]


def ask_bool(prompt: str):
    while True:
        value = input(f"{prompt} [y/n/skip]: ").strip().lower()
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        if value in {"skip", "s", ""}:
            return None
        print("请输入 y、n 或 skip。")


def ask_failure_type():
    print("失败类型：")
    for index, item in enumerate(FAILURE_TYPES, start=1):
        print(f"{index}. {item}")

    while True:
        value = input("选择编号，直接回车默认为 none：").strip()
        if not value:
            return "none"
        if value.isdigit() and 1 <= int(value) <= len(FAILURE_TYPES):
            return FAILURE_TYPES[int(value) - 1]
        print("编号无效，请重新输入。")


def load_test_cases():
    return json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))


def save_run(payload):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"behavior_baseline_{timestamp}.json"
    latest_path = OUTPUT_DIR / "latest_behavior_baseline.json"
    eval_copy_path = EVAL_DATA_DIR / f"behavior_baseline_{timestamp}.json"

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    output_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    eval_copy_path.write_text(text, encoding="utf-8")
    return output_path, eval_copy_path


def main():
    test_cases = load_test_cases()
    print("Mindcraft 行为基线记录器")
    print("请先在 Minecraft 里启动 bot，然后按下面指令逐条测试。")
    print("如果今天不想测完全部，可以随时输入 q 结束并保存。\n")

    records = []
    for index, case in enumerate(test_cases, start=1):
        print("=" * 72)
        print(f"[{index}/{len(test_cases)}] {case['id']} | {case['category']}")
        print(f"请在 Minecraft 聊天里输入：{case['command']}")
        print(f"预期：{case['expected']}")
        print(f"成功标准：{case['success_criteria']}")

        ready = input("完成观察后按回车记录，输入 q 结束：").strip().lower()
        if ready == "q":
            break

        understood = ask_bool("它听懂了吗？")
        acted = ask_bool("它行动了吗？")
        succeeded = ask_bool("这条测试算成功吗？")
        bot_reply = input("bot 主要回复/命令：").strip()
        observed_behavior = input("你观察到的行为：").strip()
        failure_type = ask_failure_type()
        notes = input("备注：").strip()

        records.append({
            "case": case,
            "understood": understood,
            "acted": acted,
            "succeeded": succeeded,
            "bot_reply": bot_reply,
            "observed_behavior": observed_behavior,
            "failure_type": failure_type,
            "notes": notes,
        })

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project": "Mindcraft behavior baseline",
        "agent": "deepseek_env",
        "minecraft_version": "1.21.6",
        "case_count": len(records),
        "records": records,
    }

    output_path, eval_copy_path = save_run(payload)
    print("\n记录已保存：")
    print(output_path)
    print("训练数据目录副本：")
    print(eval_copy_path)


if __name__ == "__main__":
    main()

