import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ARTICLES_JSONL = OUTPUT_DIR / "wechat_articles.jsonl"
STYLE_PROFILE_JSON = OUTPUT_DIR / "style_profile.json"


def read_pdf(path: Path) -> str:
    """Extract text from one PDF article."""
    reader = PdfReader(str(path))
    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(text)

    return "\n\n".join(pages)


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving paragraph boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            if should_skip_line(line):
                continue
            lines.append(line)

    return "\n".join(lines)


def should_skip_line(line: str) -> bool:
    """Drop PDF export noise, such as page footers and WeChat URLs."""
    noise_patterns = [
        r"https?://",
        r"mp\.weixin\.qq\.com",
        r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}",
        r"\d+/\d+$",
        r"喜欢作者",
        r"微信扫一扫",
        r"继续滑动看下一个",
    ]
    return any(re.search(pattern, line) for pattern in noise_patterns)


def split_paragraphs(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_opening(paragraphs, max_paragraphs=3):
    return "\n".join(paragraphs[:max_paragraphs])


def extract_ending(paragraphs, max_paragraphs=3):
    return "\n".join(paragraphs[-max_paragraphs:])


def count_connectors(text: str):
    candidates = [
        "但", "但是", "不过", "于是", "所以", "其实", "当然", "换句话说",
        "问题是", "更重要的是", "说到底", "某种程度上", "这意味着",
        "你会发现", "不难发现", "换个角度看", "最后",
    ]
    return {word: text.count(word) for word in candidates if text.count(word)}


def build_articles():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    articles = []

    for pdf_path in pdf_files:
        raw_text = read_pdf(pdf_path)
        text = clean_text(raw_text)
        paragraphs = split_paragraphs(text)

        if len(text) < 300 or len(paragraphs) < 3:
            continue

        articles.append({
            "source_file": str(pdf_path.relative_to(PROJECT_ROOT)),
            "title": pdf_path.stem,
            "char_count": len(text),
            "paragraph_count": len(paragraphs),
            "avg_paragraph_chars": round(len(text) / max(len(paragraphs), 1), 2),
            "opening": extract_opening(paragraphs),
            "ending": extract_ending(paragraphs),
            "text": text,
        })

    return articles


def build_style_profile(articles):
    title_chars = Counter()
    connector_counts = Counter()
    paragraph_lengths = []
    title_examples = []
    opening_examples = []
    ending_examples = []

    for article in articles:
        title_examples.append(article["title"])
        opening_examples.append(article["opening"])
        ending_examples.append(article["ending"])

        for char in article["title"]:
            if char.strip():
                title_chars[char] += 1

        connector_counts.update(count_connectors(article["text"]))
        for paragraph in split_paragraphs(article["text"]):
            paragraph_lengths.append(len(paragraph))

    paragraph_lengths.sort()
    median_paragraph_chars = (
        paragraph_lengths[len(paragraph_lengths) // 2] if paragraph_lengths else 0
    )

    return {
        "article_count": len(articles),
        "avg_article_chars": round(
            sum(article["char_count"] for article in articles) / max(len(articles), 1),
            2,
        ),
        "median_paragraph_chars": median_paragraph_chars,
        "title_examples": title_examples[:20],
        "opening_examples": opening_examples[:8],
        "ending_examples": ending_examples[:8],
        "common_title_chars": title_chars.most_common(30),
        "common_connectors": connector_counts.most_common(20),
        "style_rules": [
            "用中文回答，语气要像公众号文章：有观点、有转折、有节奏。",
            "回答时可以有一点叙事感，但不要复制原文句子。",
            "先给判断，再解释原因，最后落到一个可执行建议或一句收束。",
            "段落不要太长，适合手机阅读。",
            "可以使用反问、对比、轻微调侃，但不要油腻夸张。",
            "涉及事实和课程内容时保持准确，不知道就说明不确定。",
        ],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    articles = build_articles()
    with ARTICLES_JSONL.open("w", encoding="utf-8") as f:
        for article in articles:
            f.write(json.dumps(article, ensure_ascii=False) + "\n")

    style_profile = build_style_profile(articles)
    STYLE_PROFILE_JSON.write_text(
        json.dumps(style_profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"有效文章数：{len(articles)}")
    print(f"文章语料：{ARTICLES_JSONL}")
    print(f"风格画像：{STYLE_PROFILE_JSON}")


if __name__ == "__main__":
    main()
