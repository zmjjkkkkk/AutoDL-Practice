import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
STYLE_PROFILE_JSON = OUTPUT_DIR / "style_profile.json"
ARTICLES_JSONL = OUTPUT_DIR / "wechat_articles.jsonl"
CONVERSATION_DIR = OUTPUT_DIR / "conversations"

API_KEY_ENV = "guiji"
LLM_BASE_URL = os.getenv("GUIJI_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("GUIJI_MODEL", "Qwen/Qwen3-32B")


def load_style_profile():
    if not STYLE_PROFILE_JSON.exists():
        raise FileNotFoundError("请先运行 build_style_corpus.py 生成 style_profile.json")

    return json.loads(STYLE_PROFILE_JSON.read_text(encoding="utf-8"))


def load_article_examples(limit=6):
    if not ARTICLES_JSONL.exists():
        return []

    examples = []
    with ARTICLES_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if len(examples) >= limit:
                break
            article = json.loads(line)
            examples.append({
                "title": article["title"],
                "opening": article["opening"][:500],
                "ending": article["ending"][:300],
            })

    return examples


def build_system_prompt(style_profile, examples):
    title_examples = "、".join(style_profile["title_examples"][:12])
    connectors = "、".join(word for word, _ in style_profile["common_connectors"][:12])
    article_examples = "\n\n".join(
        f"标题：{item['title']}\n开头示例：{item['opening']}\n收束示例：{item['ending']}"
        for item in examples
    )

    return f"""你是一个公众号语言风格对话智能体。

你的任务不是写公众号长文，而是在日常对话里保持这些文章的口吻。
你要像一个观察教育、升学、就业和青年处境的中文公众号作者：有判断、有一点调侃、有温度，但不装腔。

风格画像：
- 文章数量：{style_profile['article_count']}
- 常见标题风格示例：{title_examples}
- 常用连接表达：{connectors}
- 典型段落中位长度：约 {style_profile['median_paragraph_chars']} 字

风格规则：
{chr(10).join("- " + rule for rule in style_profile["style_rules"])}

参考片段：
{article_examples}

回答要求：
- 核心目标是“对话口吻”，不是“文章生成”。除非用户明确要求，不要输出标题和完整文章结构。
- 每次回答先给一句判断，再拆开讲两三层，最后用一句自然的收束或追问结束。
- 段落短，适合手机阅读。一般 4-8 个短段即可。
- 可以有公众号式节奏，但不要堆砌金句，不要过度煽情。
- 少用“首先、其次、最后”这种模板腔，多用“说白了”“问题是”“换句话说”“但真正麻烦的地方在于”这类自然转折。
- 不要声称自己读过不存在的资料。
- 如果用户要求事实判断，要先讲清楚依据和不确定性。
- 不要直接复制参考文章原句。
- 不要说“作为AI语言模型”。
"""


def call_llm(messages):
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise RuntimeError("未检测到环境变量 guiji，请先 export guiji=\"你的API Key\"")

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 1200,
    }

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
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"API HTTP 错误：{exc.code}\n{body[:800]}") from exc

    return data["choices"][0]["message"]["content"]


def save_conversation(history):
    CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": LLM_MODEL,
        "turn_count": len(history),
        "history": history,
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_path = CONVERSATION_DIR / "latest_conversation.json"
    dated_path = CONVERSATION_DIR / f"conversation_{timestamp}.json"

    latest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dated_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"对话记录已保存：{latest_path}")


def print_style_brief(style_profile):
    title_examples = "、".join(style_profile["title_examples"][:8])
    connectors = "、".join(word for word, _ in style_profile["common_connectors"][:10])
    print("\n当前风格画像：")
    print(f"- 文章数：{style_profile['article_count']}")
    print(f"- 标题气质：{title_examples}")
    print(f"- 常用转折：{connectors}")
    print(f"- 段落中位长度：约 {style_profile['median_paragraph_chars']} 字")


def trim_messages(messages, keep_turns=6):
    """Keep system prompt and recent conversation turns to avoid unlimited context growth."""
    system_message = messages[0]
    recent_messages = messages[1:][-keep_turns * 2:]
    return [system_message] + recent_messages


def main():
    style_profile = load_style_profile()
    examples = load_article_examples()
    system_prompt = build_system_prompt(style_profile, examples)

    messages = [{"role": "system", "content": system_prompt}]
    history = []

    print("公众号风格对话智能体已启动。输入 q 退出，输入 /style 查看风格画像，输入 /reset 清空上下文。")
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"q", "quit", "exit"}:
            save_conversation(history)
            break
        if user_input == "/style":
            print_style_brief(style_profile)
            continue
        if user_input == "/reset":
            messages = [{"role": "system", "content": system_prompt}]
            history.append({"command": "/reset"})
            print("上下文已清空，但风格画像仍然保留。")
            continue
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        answer = call_llm(messages)
        messages.append({"role": "assistant", "content": answer})
        messages = trim_messages(messages)
        history.append({"user": user_input, "assistant": answer})

        print("\n智能体：")
        print(answer)


if __name__ == "__main__":
    main()
