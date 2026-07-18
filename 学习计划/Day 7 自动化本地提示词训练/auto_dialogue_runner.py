import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DAY6_DIR = BASE_DIR.parent / "Day 6 提示词规范强化"
sys.path.insert(0, str(DAY6_DIR))

from build_system_prompt import build_system_prompt
from evaluate_auto_run import evaluate_run


QUESTIONS_PATH = BASE_DIR / "questions.json"
OUTPUT_DIR = BASE_DIR / "output"
LATEST_RUN_PATH = OUTPUT_DIR / "latest_run.json"
API_KEY_ENV = "guiji"
LLM_BASE_URL = os.getenv("GUIJI_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("GUIJI_MODEL", "Qwen/Qwen3-32B")


def load_questions():
    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return payload["questions"]


def call_llm(messages, timeout=180, max_attempts=3):
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise RuntimeError("未检测到本地环境变量 guiji")

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "top_p": 0.9,
        "max_tokens": 900,
    }
    last_error = "未知错误"

    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            LLM_BASE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"API HTTP 错误：{exc.code}\n{body[:800]}") from exc
            last_error = f"API HTTP 错误：{exc.code}"
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            last_error = f"网络或读取超时：{exc}"

        if attempt < max_attempts:
            wait_seconds = attempt * 5
            print(
                f"第 {attempt}/{max_attempts} 次请求失败：{last_error}；"
                f"{wait_seconds} 秒后重试"
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"连续 {max_attempts} 次调用失败：{last_error}")


def normalize_usage(usage):
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
        "completion_tokens": int(usage.get("completion_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
    }


def total_usage(turns):
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for turn in turns:
        for key in totals:
            totals[key] += int(turn.get("usage", {}).get(key, 0))
    return totals


def save_run(run_path, payload):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["total_usage"] = total_usage(payload["turns"])
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    run_path.write_text(text, encoding="utf-8")
    LATEST_RUN_PATH.write_text(text, encoding="utf-8")


def reconstruct_dialogue(turns):
    messages = []
    for turn in turns:
        if turn.get("status") != "completed":
            continue
        messages.extend([
            {"role": "user", "content": turn["question"]},
            {"role": "assistant", "content": turn["assistant"]},
        ])
    return messages[-12:]


def create_new_run():
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_path = OUTPUT_DIR / f"auto_run_{session_id}.json"
    payload = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": LLM_MODEL,
        "status": "running",
        "turns": [],
        "total_usage": {},
    }
    return run_path, payload


def load_resume_run(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    session_id = payload["session_id"]
    run_path = OUTPUT_DIR / f"auto_run_{session_id}.json"
    return run_path, payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="从 latest_run.json 续跑")
    parser.add_argument("--delay", type=float, default=2.0, help="每轮间隔秒数")
    parser.add_argument("--max-turns", type=int, default=10)
    args = parser.parse_args()

    questions = load_questions()[: args.max_turns]
    if args.resume:
        if not LATEST_RUN_PATH.exists():
            raise FileNotFoundError("没有 latest_run.json，无法续跑")
        run_path, payload = load_resume_run(LATEST_RUN_PATH)
    else:
        run_path, payload = create_new_run()

    completed_ids = {
        turn["id"] for turn in payload["turns"] if turn.get("status") == "completed"
    }
    dialogue_messages = reconstruct_dialogue(payload["turns"])
    save_run(run_path, payload)

    print(f"自动测试开始：{run_path}")
    for question in questions:
        if question["id"] in completed_ids:
            print(f"跳过已完成第 {question['id']} 轮")
            continue

        turn_number = question["id"]
        print(f"\n[{turn_number}/10] {question['text']}")
        system_prompt = build_system_prompt(turn_number)
        request_messages = [
            {"role": "system", "content": system_prompt},
            *dialogue_messages,
            {"role": "user", "content": question["text"]},
        ]

        try:
            result = call_llm(request_messages)
            answer = result["content"]
            turn_record = {
                "id": turn_number,
                "question": question["text"],
                "focus": question["focus"],
                "assistant": answer,
                "status": "completed",
                "gangzhen_count": answer.count("港真"),
                "usage": normalize_usage(result["usage"]),
            }
            dialogue_messages.extend([
                {"role": "user", "content": question["text"]},
                {"role": "assistant", "content": answer},
            ])
            dialogue_messages = dialogue_messages[-12:]
            print(answer)
        except RuntimeError as exc:
            turn_record = {
                "id": turn_number,
                "question": question["text"],
                "focus": question["focus"],
                "assistant": "",
                "status": "failed",
                "error": str(exc),
                "usage": {},
            }
            print(f"本轮失败：{exc}")

        payload["turns"] = [
            turn for turn in payload["turns"] if turn["id"] != turn_number
        ]
        payload["turns"].append(turn_record)
        payload["turns"].sort(key=lambda item: item["id"])
        save_run(run_path, payload)
        print(f"已保存；累计 token：{payload['total_usage'].get('total_tokens', 0)}")
        time.sleep(args.delay)

    completed_count = sum(
        turn.get("status") == "completed" for turn in payload["turns"]
    )
    payload["status"] = "completed" if completed_count == len(questions) else "partial"
    save_run(run_path, payload)
    report_json, report_md, report = evaluate_run(run_path)

    print(f"\n自动测试结束：完成 {completed_count}/{len(questions)}")
    print(f"总 token：{payload['total_usage'].get('total_tokens', 0)}")
    print(f"平均规范分：{report['average_score']}")
    print(f"对话记录：{run_path}")
    print(f"评测报告：{report_md}")


if __name__ == "__main__":
    main()
