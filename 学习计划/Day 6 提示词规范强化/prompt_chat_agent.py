import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from build_system_prompt import build_system_prompt


BASE_DIR = Path(__file__).resolve().parent
CONVERSATION_DIR = BASE_DIR / "output" / "conversations"
API_KEY_ENV = "guiji"
LLM_BASE_URL = os.getenv("GUIJI_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("GUIJI_MODEL", "Qwen/Qwen3-32B")


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
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"API HTTP 错误：{exc.code}\n{body[:800]}") from exc
            error = f"API HTTP 错误：{exc.code}"
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            error = f"网络或读取超时：{exc}"

        if attempt < max_attempts:
            wait_seconds = attempt * 3
            print(
                f"API 第 {attempt}/{max_attempts} 次请求失败：{error}；"
                f"{wait_seconds} 秒后自动重试..."
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"API 连续 {max_attempts} 次调用失败：{error}")


def save_conversation(session_id, history):
    CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "model": LLM_MODEL,
        "turn_count": len(history),
        "history": history,
    }
    session_path = CONVERSATION_DIR / f"conversation_{session_id}.json"
    latest_path = CONVERSATION_DIR / "latest_conversation.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    session_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return session_path


def main():
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    dialogue_messages = []
    history = []

    print("Day 6 提示词对话智能体已启动。输入 q 退出，/reset 清空上下文。")
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"q", "quit", "exit"}:
            if history:
                output_path = save_conversation(session_id, history)
                print(f"对话记录已保存：{output_path}")
            break
        if user_input == "/reset":
            dialogue_messages = []
            print("上下文已清空，风格规则仍然保留。")
            continue
        if not user_input:
            continue

        turn_number = len(history) + 1
        system_prompt = build_system_prompt(turn_number)
        request_messages = [
            {"role": "system", "content": system_prompt},
            *dialogue_messages[-12:],
            {"role": "user", "content": user_input},
        ]
        try:
            answer = call_llm(request_messages)
        except RuntimeError as exc:
            print(f"\n本轮生成失败：{exc}")
            print("对话程序仍在运行，可以重新输入刚才的问题，或输入 q 退出。")
            continue

        dialogue_messages.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": answer},
        ])
        history.append({
            "turn": turn_number,
            "user": user_input,
            "assistant": answer,
            "gangzhen_count": answer.count("港真"),
        })
        output_path = save_conversation(session_id, history)

        print("\n智能体：")
        print(answer)
        print(f"\n[第 {turn_number} 轮｜“港真”出现 {answer.count('港真')} 次｜已保存：{output_path}]")


if __name__ == "__main__":
    main()
