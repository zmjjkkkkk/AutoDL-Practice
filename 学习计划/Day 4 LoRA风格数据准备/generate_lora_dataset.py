import argparse
import json
import os
import random
import re
import urllib.error
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DAY3_OUTPUT_DIR = BASE_DIR.parent / "Day 3 公众号风格对话智能体" / "output"
STYLE_SPEC_JSON = BASE_DIR / "style_spec.json"
CORE_BELIEFS_JSON = BASE_DIR / "core_beliefs.json"
STYLE_PROFILE_JSON = DAY3_OUTPUT_DIR / "style_profile.json"
ARTICLES_JSONL = DAY3_OUTPUT_DIR / "wechat_articles.jsonl"
DEFAULT_OUTPUT_JSONL = BASE_DIR / "sft_dataset.generated.jsonl"
FAILED_OUTPUT_JSONL = BASE_DIR / "sft_dataset.failed.jsonl"

API_KEY_ENV = "guiji"
LLM_BASE_URL = os.getenv("GUIJI_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("GUIJI_MODEL", "Qwen/Qwen3-32B")


SEED_TASKS = [
    {
        "task_type": "advice",
        "style_strength": "wechat_medium",
        "user": "我刚进科研组，老师让我学 AutoDL 和大模型训推，我该怎么安排？",
    },
    {
        "task_type": "opinion",
        "style_strength": "wechat_strong",
        "user": "为什么现在大家一边骂学历崇拜，一边又拼命读研？",
    },
    {
        "task_type": "technical_explain",
        "style_strength": "wechat_light",
        "user": "用通俗一点的方式解释，LoRA 到底是在训练什么？",
    },
    {
        "task_type": "anxiety_response",
        "style_strength": "wechat_medium",
        "user": "我感觉自己什么都不会，但身边同学好像已经会很多了，怎么办？",
    },
    {
        "task_type": "rewrite",
        "style_strength": "wechat_medium",
        "user": "把这句话改成该公众号口吻：我今天成功用 VS Code 连接了 AutoDL，并运行了 GPU 测试。",
    },
    {
        "task_type": "opinion",
        "style_strength": "wechat_medium",
        "user": "实习越来越卷，是不是说明普通学生已经没机会了？",
    },
    {
        "task_type": "technical_advice",
        "style_strength": "wechat_medium",
        "user": "我想做公众号风格智能体，prompt、RAG、LoRA 这三个应该怎么排序？",
    },
    {
        "task_type": "fact_with_uncertainty",
        "style_strength": "wechat_light",
        "user": "H800、A100、V100 这些 GPU 对科研新人来说区别大吗？",
    },
]

TASK_TYPES = [
    "advice",
    "opinion",
    "technical_explain",
    "anxiety_response",
    "rewrite",
    "technical_advice",
    "fact_with_uncertainty",
    "self_intro",
    "career_observation",
    "study_plan",
]

STYLE_STRENGTHS = ["wechat_light", "wechat_medium", "wechat_strong"]

USER_PROMPT_POOL = [
    "我刚进科研组，老师让我学 AutoDL 和大模型训推，我该怎么安排？",
    "学历还值钱吗？",
    "我应该先学机器学习算法，还是先做一个能跑的 Agent？",
    "如何看待实习越来越卷？",
    "我想做一个公众号风格智能体，应该先 prompt 还是先 LoRA？",
    "为什么现在大家一边骂学历崇拜，一边又拼命读研？",
    "用通俗一点的方式解释，LoRA 到底是在训练什么？",
    "我感觉自己什么都不会，但身边同学好像已经会很多了，怎么办？",
    "把这句话改成该公众号口吻：我今天成功用 VS Code 连接了 AutoDL，并运行了 GPU 测试。",
    "H800、A100、V100 这些 GPU 对科研新人来说区别大吗？",
    "普通学生还有机会进大厂吗？",
    "为什么我越努力越焦虑？",
    "导师让我先读论文，我完全读不进去怎么办？",
    "我应该把时间花在刷课、看论文，还是做项目？",
    "港中深到底值不值得读？",
    "UCLA 为什么总让人有滤镜？",
    "一年制硕士真的很水吗？",
    "本科生现在还有必要提前实习吗？",
    "如果我没有名校背景，是不是就没什么机会了？",
    "为什么很多人拿到 offer 之后还是不快乐？",
    "大模型时代，普通学生该怎么避免被淘汰？",
    "我想做科研，但又担心就业，应该怎么平衡？",
    "AutoDL、OpenAI API、本地模型这三种路线怎么选？",
    "我今天只学会了 SSH，会不会太慢？",
    "如何看待所谓的 AI 取代应届生？",
    "我应该先学 Python 基础，还是直接上手大模型项目？",
    "为什么有些人看起来什么都会？",
    "如果家里不支持读研，我还应该坚持吗？",
    "读研是为了逃避就业吗？",
    "学校排名和专业实力，到底哪个更重要？",
    "请用这个公众号口吻回答：不要把平台当成能力本身。",
    "请用这个公众号口吻回答：年轻人最怕的是路径不透明。",
    "请用这个公众号口吻回答：实习不是万能药。",
    "请用这个公众号口吻解释：什么是 RAG？",
    "请用这个公众号口吻解释：为什么微调不是万能的？",
    "请用这个公众号口吻解释：为什么数据质量比数据数量更重要？",
    "我做了一个课件问答 Agent，但感觉很粗糙，正常吗？",
    "我想让智能体像某个公众号，是不是一定要 LoRA？",
    "我该怎么判断生成数据够不够像？",
    "如果生成的数据很油腻，是不是说明风格设定过猛？",
    "我担心自己做的是玩具项目，怎么办？",
    "科研新人第一周最容易踩什么坑？",
    "为什么远程服务器关机后再开机可能连不上？",
    "按量计费和包月算力，哪个更适合新人？",
    "怎么理解 GPU 显存对大模型推理的影响？",
    "我想把今天的学习记录写得像公众号，但不要写成长文。",
    "给一个刚学大模型的新生一点不好听但有用的建议。",
    "怎么看待同龄人之间的信息差？",
    "为什么选择比努力更容易被神化？",
    "如果只能做一个项目，课件问答 Agent 和公众号风格 Agent 选哪个？",
]


def infer_task_type(user_prompt: str) -> str:
    if "解释" in user_prompt or "什么是" in user_prompt or "区别" in user_prompt:
        return "technical_explain"
    if "怎么办" in user_prompt or "焦虑" in user_prompt or "担心" in user_prompt:
        return "anxiety_response"
    if "怎么安排" in user_prompt or "怎么选" in user_prompt or "建议" in user_prompt:
        return "advice"
    if "改成" in user_prompt or "口吻回答" in user_prompt:
        return "rewrite"
    if "如何看待" in user_prompt or "为什么" in user_prompt or "值不值得" in user_prompt:
        return "opinion"
    return random.choice(TASK_TYPES)


def build_task_pool(count: int):
    """Build as many generation tasks as requested.

    The first tasks are handwritten seeds. Extra tasks are built from a larger
    prompt pool so --count 50 really means 50 generated records.
    """
    tasks = SEED_TASKS.copy()
    seen_users = {task["user"] for task in tasks}

    for user_prompt in USER_PROMPT_POOL:
        if user_prompt in seen_users:
            continue
        tasks.append({
            "task_type": infer_task_type(user_prompt),
            "style_strength": random.choice(STYLE_STRENGTHS),
            "user": user_prompt,
        })
        seen_users.add(user_prompt)

    while len(tasks) < count:
        base_prompt = random.choice(USER_PROMPT_POOL)
        style_strength = random.choice(STYLE_STRENGTHS)
        variant = random.choice([
            f"请用更{style_strength}的公众号口吻回答：{base_prompt}",
            f"换成饭局中年人式说教口吻回答：{base_prompt}",
            f"回答这个问题，要求先泼冷水再给下一步：{base_prompt}",
            f"回答这个问题，少端水，多给判断：{base_prompt}",
        ])
        if variant in seen_users:
            continue
        tasks.append({
            "task_type": infer_task_type(base_prompt),
            "style_strength": style_strength,
            "user": variant,
        })
        seen_users.add(variant)

    random.shuffle(tasks)
    return tasks[:count]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_article_examples(limit=6):
    if not ARTICLES_JSONL.exists():
        return []

    examples = []
    with ARTICLES_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            article = json.loads(line)
            examples.append({
                "title": article["title"],
                "opening": article["opening"][:450],
                "ending": article["ending"][:260],
            })
            if len(examples) >= limit:
                break
    return examples


def compact_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def strip_code_fence(text: str) -> str:
    text = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def extract_json_object(text: str) -> str:
    """Extract the first plausible JSON object from model output."""
    text = strip_code_fence(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start:end + 1]


def build_generation_prompt(style_spec, core_beliefs, style_profile, article_examples, task):
    style_rules = "\n".join(f"- {item}" for item in style_spec["signature_moves"])
    avoid_rules = "\n".join(f"- {item}" for item in style_spec["avoid"])
    belief_rules = "\n".join(
        f"- {item['principle']}：{item['dialogue_effect']}"
        for item in core_beliefs["beliefs"]
    )
    red_lines = "\n".join(f"- {item}" for item in core_beliefs["red_lines"])
    reasoning_pattern = " -> ".join(core_beliefs["preferred_reasoning_pattern"])
    examples = "\n\n".join(
        f"标题：{item['title']}\n开头：{item['opening']}\n收束：{item['ending']}"
        for item in article_examples
    )

    return f"""你正在为一个中文公众号口吻对话智能体生成 LoRA/SFT 训练样本。

目标：生成一条高质量的“用户问题 -> 理想回答”样本。

风格说明 style_spec：
{compact_json(style_spec)}

思想钢印 core_beliefs：
{compact_json(core_beliefs)}

从 77 篇公众号文章抽取出的风格画像 style_profile 摘要：
- 文章数量：{style_profile.get("article_count")}
- 标题示例：{"、".join(style_profile.get("title_examples", [])[:12])}
- 常用连接表达：{"、".join(word for word, _ in style_profile.get("common_connectors", [])[:12])}
- 段落中位长度：约 {style_profile.get("median_paragraph_chars")} 字

参考片段，不要复制原句，只学习节奏：
{examples}

本条任务：
- task_type: {task["task_type"]}
- style_strength: {task["style_strength"]}
- user: {task["user"]}

必须遵守的风格动作：
{style_rules}

必须遵守的思想钢印：
{belief_rules}

推荐推理路径：
{reasoning_pattern}

必须避免：
{avoid_rules}

思想红线：
{red_lines}

输出要求：
1. 只输出 JSON 对象，不要输出 Markdown。
2. JSON 字段必须包括 instruction, input, output, metadata。
3. output 是 assistant 的理想回答，必须是原创中文，不要复制参考文章原句。
4. output 不要写成完整公众号文章，而要像对话回复。
5. output 保持 4 到 8 个短段落。
6. 字符串内部如果需要引号，必须使用中文引号“”，不要使用未转义英文双引号。

JSON 格式：
{{
  "instruction": "用户问题",
  "input": "",
  "output": "理想回答",
  "metadata": {{
    "task_type": "{task["task_type"]}",
    "style_strength": "{task["style_strength"]}",
    "belief_profile": "{core_beliefs["name"]}",
    "source": "synthetic_by_llm"
  }}
}}
"""


def call_llm(prompt: str):
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise RuntimeError('未检测到环境变量 guiji，请先运行：export guiji="你的API Key"')

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是严格的数据集生成器。只输出可解析 JSON，不输出解释。",
            },
            {"role": "user", "content": prompt},
        ],
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


def to_chat_sft_record(record):
    system_prompt = (
        "你是一个公众号口吻对话智能体。回答要短段落、有判断、有现实感，"
        "但不要写成完整公众号文章。你必须优先遵守思想钢印：先看现实约束，"
        "反对廉价鸡血，区分事实和判断，强调行动空间但不责备用户。"
    )
    user_content = record["instruction"]
    if record.get("input"):
        user_content += "\n\n" + record["input"]

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": record["output"]},
        ],
        "metadata": record.get("metadata", {}),
    }


def parse_record(text: str):
    raw = extract_json_object(text)
    record = json.loads(raw)
    required = {"instruction", "input", "output", "metadata"}
    missing = required - set(record)
    if missing:
        raise ValueError(f"生成结果缺少字段：{missing}")
    return record


def save_failed_sample(task, response_text, error):
    FAILED_OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task,
        "error": str(error),
        "response_text": response_text,
    }
    with FAILED_OUTPUT_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def generate_record_with_retries(style_spec, core_beliefs, style_profile, article_examples, task, retries=2):
    last_response = ""
    last_error = None

    for attempt in range(1, retries + 2):
        prompt = build_generation_prompt(style_spec, core_beliefs, style_profile, article_examples, task)
        if attempt > 1:
            prompt += (
                "\n\n上一轮输出不是合法 JSON。请重新生成。"
                "只输出一个 JSON 对象，不要解释，不要 Markdown，"
                "不要在字符串里使用未转义英文双引号。"
            )

        last_response = call_llm(prompt)
        try:
            return parse_record(last_response)
        except Exception as exc:
            last_error = exc
            print(f"解析失败，准备重试 {attempt}/{retries + 1}：{exc}")

    save_failed_sample(task, last_response, last_error)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=8, help="要生成的样本数量")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--dry-run", action="store_true", help="只打印第一条生成提示，不调用 API")
    args = parser.parse_args()

    style_spec = load_json(STYLE_SPEC_JSON)
    core_beliefs = load_json(CORE_BELIEFS_JSON)
    style_profile = load_json(STYLE_PROFILE_JSON)
    article_examples = load_article_examples()

    tasks = build_task_pool(args.count)

    if args.dry_run:
        print(build_generation_prompt(style_spec, core_beliefs, style_profile, article_examples, tasks[0]))
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    generated_count = 0

    with args.output.open("a", encoding="utf-8") as f:
        for task in tasks:
            record = generate_record_with_retries(
                style_spec,
                core_beliefs,
                style_profile,
                article_examples,
                task,
            )
            if record is None:
                print(f"已跳过坏样本：{task['task_type']} | {task['style_strength']}")
                continue
            chat_record = to_chat_sft_record(record)
            f.write(json.dumps(chat_record, ensure_ascii=False) + "\n")
            generated_count += 1
            print(f"已生成 {generated_count}/{args.count}：{task['task_type']} | {task['style_strength']}")

    print(f"生成完成：{args.output}")
    if generated_count < args.count:
        print(f"注意：目标 {args.count} 条，实际成功 {generated_count} 条。失败样本见：{FAILED_OUTPUT_JSONL}")


if __name__ == "__main__":
    main()
