import argparse
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONVERSATION = BASE_DIR / "output" / "conversations" / "latest_conversation.json"

ENGLISH_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9+-]*\b")
FORBIDDEN_PATTERNS = [
    "作为AI语言模型",
    "首先",
    "其次",
    "最后",
    "关门弟子",
    "我发表过",
    "我在腾讯",
    "我在阿里",
]


def score_turn(turn):
    answer = turn["assistant"]
    gangzhen_count = answer.count("港真")
    english_terms = ENGLISH_PATTERN.findall(answer)
    forbidden_hits = [item for item in FORBIDDEN_PATTERNS if item in answer]

    score = 100
    if turn["turn"] <= 2 and gangzhen_count > 1:
        score -= 15
    if 3 <= turn["turn"] <= 5 and gangzhen_count == 0:
        score -= 10
    if turn["turn"] >= 6 and gangzhen_count == 0:
        score -= 15
    if gangzhen_count > 2:
        score -= 20
    if not english_terms:
        score -= 10
    if len(english_terms) > 12:
        score -= 10
    score -= len(forbidden_hits) * 15

    return {
        "turn": turn["turn"],
        "score": max(score, 0),
        "gangzhen_count": gangzhen_count,
        "english_terms": english_terms,
        "forbidden_hits": forbidden_hits,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conversation", type=Path, default=DEFAULT_CONVERSATION)
    args = parser.parse_args()

    payload = json.loads(args.conversation.read_text(encoding="utf-8"))
    reports = [score_turn(turn) for turn in payload["history"]]
    average_score = sum(item["score"] for item in reports) / max(len(reports), 1)

    for report in reports:
        print(
            f"第 {report['turn']} 轮：{report['score']} 分 | "
            f"港真={report['gangzhen_count']} | "
            f"英文={report['english_terms']} | "
            f"禁用命中={report['forbidden_hits']}"
        )
    print(f"\n平均风格规范分：{average_score:.1f}")


if __name__ == "__main__":
    main()
