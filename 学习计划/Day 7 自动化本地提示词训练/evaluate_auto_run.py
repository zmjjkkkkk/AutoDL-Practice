import argparse
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_PATH = BASE_DIR / "output" / "latest_run.json"
ENGLISH_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9+-]*\b")
FORBIDDEN_PATTERNS = [
    "作为AI语言模型",
    "关门弟子",
    "我发表过",
    "我在腾讯工作",
    "我在阿里工作",
    "你爸妈认识我",
    "我在UCLA见过",
    "我跟UCLA",
    "我当年",
    "昨天我路过",
    "上周有个",
]
ARTICLE_MARKERS = ["标题：", "导语：", "正文：", "结语："]
REPETITIVE_PATTERNS = [
    "别问为什么",
    "三个月后你再问我",
    "别急着感动",
]


def expected_gangzhen_range(turn_number):
    if turn_number <= 2:
        return 0, 1
    if turn_number <= 5:
        return 1, 1
    return 1, 2


def evaluate_turn(turn):
    answer = turn.get("assistant", "")
    turn_number = turn["id"]
    gangzhen_count = answer.count("港真")
    english_terms = ENGLISH_PATTERN.findall(answer)
    forbidden_hits = [item for item in FORBIDDEN_PATTERNS if item in answer]
    article_hits = [item for item in ARTICLE_MARKERS if item in answer]
    repetitive_hits = [item for item in REPETITIVE_PATTERNS if item in answer]
    expected_min, expected_max = expected_gangzhen_range(turn_number)

    score = 100
    notes = []

    if not expected_min <= gangzhen_count <= expected_max:
        score -= 15
        notes.append(
            f"港真次数 {gangzhen_count}，目标 {expected_min}-{expected_max}"
        )
    if not english_terms:
        score -= 10
        notes.append("没有中英混用")
    elif len(english_terms) > 15:
        score -= 10
        notes.append("英文点缀过多")
    if forbidden_hits:
        score -= 25
        notes.append(f"疑似虚构身份/AI腔：{forbidden_hits}")
    if article_hits:
        score -= 10
        notes.append(f"出现文章结构标记：{article_hits}")
    if repetitive_hits:
        score -= 5 * len(repetitive_hits)
        notes.append(f"出现模板化口癖：{repetitive_hits}")
    if len(answer) > 1400:
        score -= 10
        notes.append("回答过长，不像对话")
    if not answer:
        score = 0
        notes.append("本轮没有生成回答")

    return {
        "id": turn_number,
        "score": max(score, 0),
        "gangzhen_count": gangzhen_count,
        "english_terms": english_terms,
        "forbidden_hits": forbidden_hits,
        "repetitive_hits": repetitive_hits,
        "notes": notes,
    }


def evaluate_run(run_path: Path):
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    completed_turns = [
        turn for turn in payload["turns"] if turn.get("status") == "completed"
    ]
    reports = [evaluate_turn(turn) for turn in completed_turns]
    average_score = (
        sum(report["score"] for report in reports) / len(reports)
        if reports
        else 0
    )

    report_payload = {
        "run_file": str(run_path),
        "completed_turns": len(completed_turns),
        "average_score": round(average_score, 2),
        "total_usage": payload.get("total_usage", {}),
        "turn_reports": reports,
    }

    report_json = run_path.with_name(run_path.stem + "_report.json")
    report_md = run_path.with_name(run_path.stem + "_report.md")
    report_json.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Day 7 自动对话风格报告",
        "",
        f"- 完成轮数：{len(completed_turns)}/10",
        f"- 平均规范分：{average_score:.1f}",
        f"- 总 token：{payload.get('total_usage', {}).get('total_tokens', 0)}",
        "",
        "## 分轮结果",
        "",
    ]
    for report in reports:
        notes = "；".join(report["notes"]) if report["notes"] else "通过基础规则检查"
        lines.append(
            f"- 第 {report['id']} 轮：{report['score']} 分；"
            f"港真={report['gangzhen_count']}；"
            f"英文={report['english_terms']}；{notes}"
        )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_json, report_md, report_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN_PATH)
    args = parser.parse_args()

    report_json, report_md, report = evaluate_run(args.run)
    print(f"完成轮数：{report['completed_turns']}/10")
    print(f"平均规范分：{report['average_score']}")
    print(f"JSON 报告：{report_json}")
    print(f"Markdown 报告：{report_md}")


if __name__ == "__main__":
    main()
