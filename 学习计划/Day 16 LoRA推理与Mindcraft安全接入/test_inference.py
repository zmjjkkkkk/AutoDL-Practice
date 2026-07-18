"""Run English scored checks and Chinese exploratory checks against the LoRA adapter."""

import argparse
import json
from pathlib import Path

from infer_mindcraft_command import MindcraftCommandModel


TEST_CASES = [
    {"language": "en", "user": "could you walk over to me", "expected": '!goToPlayer("robot", 2)'},
    {"language": "en", "user": "stay close and follow me", "expected": '!followPlayer("robot", 3)'},
    {"language": "en", "user": "please halt now", "expected": "!stop"},
    {"language": "en", "user": "show me what you have", "expected": "!inventory"},
    {"language": "en", "user": "scan the blocks around us", "expected": "!nearbyBlocks"},
    {"language": "en", "user": "go chop four oak logs", "expected": '!collectBlocks("oak_log", 4)'},
    {"language": "en", "user": "look for an oak log nearby", "expected": '!searchForBlock("oak_log", 32)'},
    {"language": "en", "user": "make a batch of oak planks", "expected": '!craftRecipe("oak_planks", 1)'},
    {"language": "en", "user": "hello there", "expected": "Hello! What can I help with?"},
    {"language": "zh", "user": "请跟着我"},
    {"language": "zh", "user": "停下"},
    {"language": "zh", "user": "看看附近有什么方块"},
    {"language": "zh", "user": "背包里有什么"},
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--model_name", default="Qwen/Qwen3-4B")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--report_path", default="inference_smoke_report.json")
    return parser.parse_args()


def main():
    args = parse_args()
    agent = MindcraftCommandModel(args.model_name, args.adapter_dir, args.device)
    results = []

    for case in TEST_CASES:
        response = agent.respond(case["user"])
        expected = case.get("expected")
        actual = response["guard"]["value"]
        results.append({
            **case,
            **response,
            "exact_match": actual == expected if expected else None,
        })

    scored = [item for item in results if item["exact_match"] is not None]
    correct = sum(item["exact_match"] for item in scored)
    report = {
        "scored_examples": len(scored),
        "exact_match_count": correct,
        "exact_match_accuracy": correct / len(scored) if scored else 0.0,
        "note": "Chinese cases are exploratory because the Day 15 SFT dataset contains English requests.",
        "results": results,
    }
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"English exact match: {correct}/{len(scored)} = {report['exact_match_accuracy']:.1%}")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
