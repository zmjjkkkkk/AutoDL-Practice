"""Generate answers for the held-out Mindcraft SFT set and score exact matches."""

import argparse
import json
import os
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(PROJECT_DIR / "hf-cache"))


def apply_chat_template(tokenizer, messages):
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def first_line(text):
    cleaned = text.replace("<|im_end|>", "").strip()
    return next((line.strip() for line in cleaned.splitlines() if line.strip()), "")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", default="Qwen/Qwen3-4B")
    parser.add_argument("--adapter_dir", default=str(PROJECT_DIR / "artifacts" / "qwen3_4b_mindcraft_lora" / "adapter"))
    parser.add_argument("--eval_file", default=str(PROJECT_DIR / "output" / "mindcraft_sft_eval.jsonl"))
    parser.add_argument("--report_path", default=str(PROJECT_DIR / "artifacts" / "qwen3_4b_mindcraft_lora" / "command_eval.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    adapter_path = Path(args.adapter_dir)
    # Trainer checkpoints contain adapter weights but do not necessarily include tokenizer files.
    tokenizer_source = args.adapter_dir if (adapter_path / "tokenizer_config.json").exists() else args.model_name
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    model = PeftModel.from_pretrained(model, args.adapter_dir).to("cuda").eval()

    rows = [json.loads(line) for line in Path(args.eval_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for row in rows:
        messages = row["messages"]
        prompt = apply_chat_template(tokenizer, messages[:-1])
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=64,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        new_tokens = generated[0, inputs["input_ids"].shape[1]:]
        prediction = first_line(tokenizer.decode(new_tokens, skip_special_tokens=True))
        expected = messages[-1]["content"].strip()
        results.append({
            "intent_id": row["metadata"]["intent_id"],
            "user": messages[1]["content"],
            "expected": expected,
            "prediction": prediction,
            "exact_match": prediction == expected,
        })

    correct = sum(item["exact_match"] for item in results)
    report = {
        "model_name": args.model_name,
        "adapter_dir": args.adapter_dir,
        "examples": len(results),
        "exact_match_count": correct,
        "exact_match_accuracy": correct / len(results) if results else 0.0,
        "results": results,
    }
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exact command match: {correct}/{len(results)} = {report['exact_match_accuracy']:.1%}")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
