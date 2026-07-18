import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# 课件原始文件目录。所有 PDF/TXT/MD 课件都放到这里。
RAW_DIR = Path("data/raw")

# 对话记录输出目录。程序退出时会把本次问答保存成 JSON。
LOG_DIR = Path("logs")

# 大模型 API 配置。
# 约定：把 API key 放在环境变量 guiji 中；如需换模型/接口，可额外设置下面两个环境变量。
LLM_API_KEY_ENV = "guiji"
LLM_BASE_URL = os.getenv("GUIJI_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
LLM_MODEL = os.getenv("GUIJI_MODEL", "Qwen/Qwen3-32B")

# 小型中英文术语表：用于把中文问题扩展成英文关键词。
# 这不是翻译模型，只是让当前 TF-IDF 检索更容易命中英文课件。
TERM_ALIASES = {
    "离散数学": "discrete mathematics",
    "数学归纳法": "mathematical induction",
    "归纳法": "induction",
    "强归纳法": "strong induction",
    "良序原理": "well ordering principle",
    "集合": "set sets",
    "函数": "function mapping",
    "映射": "mapping function",
    "双射": "bijection one-to-one onto",
    "计数": "counting",
    "图": "graph",
    "图论": "graph theory",
    "染色": "coloring graph coloring",
    "二分图": "bipartite graph",
    "鸽巢原理": "pigeonhole principle",
    "模运算": "modular arithmetic",
    "中国剩余定理": "Chinese remainder theorem",
    "不变量": "invariant method",
    "递推": "recurrence",
    "证明": "proof",
}


def read_pdf(path: Path) -> str:
    """读取 PDF 文件，把每一页能提取到的文字拼成一个长文本。"""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            # 保留文件名和页码，方便回答时知道依据来自哪里。
            pages.append(f"[{path.name} 第{i + 1}页]\n{text}")
    return "\n\n".join(pages)


def load_documents():
    """扫描 data/raw 目录，加载当前支持的课件格式。"""
    docs = []
    for path in RAW_DIR.iterdir():
        if path.suffix.lower() == ".pdf":
            text = read_pdf(path)
        elif path.suffix.lower() in [".txt", ".md"]:
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            continue

        if text.strip():
            docs.append((path.name, text))

    return docs


def chunk_text(text: str, chunk_size=500, overlap=100):
    """把长课件切成较小片段，方便后续检索。

    chunk_size 表示每段大约多少字符。
    overlap 表示相邻片段重叠多少字符，用来减少切断关键句子的概率。
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def expand_question(question: str) -> str:
    """用术语表扩展问题，缓解中文问题和英文课件之间的关键词不匹配。"""
    aliases = []
    for chinese_term, english_terms in TERM_ALIASES.items():
        if chinese_term in question:
            aliases.append(english_terms)

    if not aliases:
        return question

    return question + " " + " ".join(aliases)


def build_index():
    """建立一个最小版检索索引。

    当前版本使用 TF-IDF，不调用大模型，也不需要 GPU。
    它会把每个课件片段变成一个向量，后续用相似度找到最相关片段。
    """
    docs = load_documents()
    chunks = []

    for filename, text in docs:
        for chunk in chunk_text(text):
            chunks.append({
                "source": filename,
                "text": chunk,
            })

    if not chunks:
        raise RuntimeError("没有读取到课件内容。请确认 data/raw 里有可读取文字的 PDF、TXT 或 MD 文件。")

    # 中文没有天然空格分词，所以这里用字符级 n-gram。
    # 简单理解：把文本拆成连续的 2-4 个字组合，再统计它们的重要程度。
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        max_features=50000,
    )

    # matrix 的每一行对应一个课件片段的 TF-IDF 向量。
    matrix = vectorizer.fit_transform([c["text"] for c in chunks])
    return chunks, vectorizer, matrix


def split_sentences(text: str):
    """把课件片段粗略切成句子，供后续生成参考答案草稿。"""
    normalized = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.!?。！？])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def build_answer_draft(question: str, results, vectorizer, max_sentences=5):
    """从检索片段中抽取最相关的几句话，组成一个朴素的参考答案草稿。

    当前版本仍然不调用大模型，所以它不是自由生成，而是 extractive QA：
    从课件原文中抽句子，再按相关度排序。
    """
    candidates = []
    for result in results:
        for sentence in split_sentences(result["text"]):
            if 20 <= len(sentence) <= 300:
                candidates.append({
                    "source": result["source"],
                    "sentence": sentence,
                })

    if not candidates:
        return "暂时无法从课件片段中抽取出合适的答案句子。"

    q_vec = vectorizer.transform([question])
    sentence_matrix = vectorizer.transform([item["sentence"] for item in candidates])
    scores = cosine_similarity(q_vec, sentence_matrix).flatten()
    top_indices = scores.argsort()[::-1][:max_sentences]

    answer_lines = []
    used_sentences = set()
    for idx in top_indices:
        sentence = candidates[idx]["sentence"]
        if sentence in used_sentences:
            continue
        used_sentences.add(sentence)
        answer_lines.append(f"- {sentence}（来源：{candidates[idx]['source']}）")

    return "\n".join(answer_lines)


def build_context(results, max_chars=2400):
    """把检索结果整理成大模型可读的上下文，并限制长度避免请求过大。"""
    blocks = []
    total_chars = 0

    for result in results:
        block = (
            f"来源：{result['source']}；相关度：{result['score']:.4f}\n"
            f"{result['text']}"
        )
        if total_chars + len(block) > max_chars:
            break
        blocks.append(block)
        total_chars += len(block)

    return "\n\n---\n\n".join(blocks)


def call_llm_api(question: str, results):
    """调用大模型 API，基于课件片段生成自然语言答案。

    当前按 OpenAI-compatible Chat Completions 接口组织请求。
    API key 从环境变量 guiji 读取，代码里不保存密钥。
    """
    api_key = os.getenv(LLM_API_KEY_ENV)
    if not api_key:
        return {
            "ok": False,
            "content": "未检测到环境变量 guiji，已跳过大模型生成。",
            "error": "missing_api_key",
        }

    context = build_context(results)
    system_prompt = (
        "你是一个严谨的课程问答助手。"
        "请只基于用户提供的课件片段回答问题；"
        "如果课件片段不足以回答，要明确说资料不足。"
        "回答要清楚、分点、适合初学者，并在关键句后标注来源文件名。"
    )
    user_prompt = f"""用户问题：
{question}

课件片段：
{context}

请输出：
1. 简洁答案
2. 关键依据
3. 如果资料不足，请说明还需要哪类课件内容
"""

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
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
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "content": f"大模型 API HTTP 错误：{exc.code}\n{error_body[:500]}",
            "error": "http_error",
        }
    except Exception as exc:
        return {
            "ok": False,
            "content": f"大模型 API 调用失败：{exc}",
            "error": "request_failed",
        }

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {
            "ok": False,
            "content": "大模型 API 返回格式不符合预期。",
            "error": "invalid_response",
            "raw_response": data,
        }

    return {
        "ok": True,
        "content": content,
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
    }


def ask(question: str, chunks, vectorizer, matrix, top_k=3, min_score=0.0001):
    """根据用户问题，从课件片段中找出最相关的 top_k 个参考内容。"""
    expanded_question = expand_question(question)

    # 把问题也转成和课件片段同一种 TF-IDF 向量。
    q_vec = vectorizer.transform([expanded_question])

    # 计算问题向量和每个课件片段向量的余弦相似度。
    # 分数越高，表示这个片段越可能和问题相关。
    scores = cosine_similarity(q_vec, matrix).flatten()
    top_indices = scores.argsort()[::-1][:top_k]

    print("\n问题：", question)
    if expanded_question != question:
        print("扩展检索词：", expanded_question)
    print("\n根据课件，最相关内容如下：\n")

    results = []
    for rank, idx in enumerate(top_indices, start=1):
        chunk = chunks[idx]
        score = scores[idx]

        results.append({
            "rank": rank,
            "source": chunk["source"],
            "score": float(score),
            "text": chunk["text"][:800],
        })

        print(f"--- 参考 {rank} | 来源：{chunk['source']} | 相关度：{score:.4f} ---")
        print(chunk["text"][:800])
        print()

    if not results or results[0]["score"] < min_score:
        print("提示：最高相关度接近 0，说明课件中可能没有找到和问题直接相关的内容。")
        print("建议：换成课件语言提问，或确认课件本身是否包含该主题。")
        answer_status = "no_relevant_context"
        extractive_answer = ""
        llm_answer = ""
        llm_meta = {"ok": False, "error": "no_relevant_context"}
    else:
        answer_status = "retrieved"
        extractive_answer = build_answer_draft(expanded_question, results, vectorizer)
        print("抽取式参考草稿：")
        print(extractive_answer)

        print("\n正在调用大模型生成答案...")
        llm_meta = call_llm_api(question, results)
        llm_answer = llm_meta["content"]
        print("\n大模型答案：")
        print(llm_answer)

    return {
        "question": question,
        "expanded_question": expanded_question,
        "status": answer_status,
        "top_score": results[0]["score"] if results else 0.0,
        "extractive_answer": extractive_answer,
        "llm_answer": llm_answer,
        "llm_meta": llm_meta,
        "results": results,
    }


def save_conversation(history):
    """把本次问答记录保存为 JSON，方便后续复盘和做训练/评测数据。"""
    if not history:
        print("本次没有有效提问，不保存对话记录。")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = LOG_DIR / f"conversation_{timestamp}.json"

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_dir": str(RAW_DIR),
        "question_count": len(history),
        "history": history,
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"对话记录已保存：{output_path}")


def main():
    """程序入口：先建索引，再进入循环问答。"""
    print("正在读取课件并建立索引...")
    chunks, vectorizer, matrix = build_index()
    print(f"已加载 {len(chunks)} 个课件片段。")

    history = []
    while True:
        question = input("\n请输入问题，输入 q 退出：").strip()
        if question.lower() in ["q", "quit", "exit"]:
            save_conversation(history)
            break
        if not question:
            continue
        record = ask(question, chunks, vectorizer, matrix)
        history.append(record)


if __name__ == "__main__":
    main()
