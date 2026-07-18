"""Run the Day 15 LoRA adapter and safely classify one Mindcraft request."""

import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from command_guard import validate_model_output


SYSTEM_PROMPT = (
    "You are a Minecraft agent running in Mindcraft. "
    "The current player's in-game name is robot. "
    "For a pure greeting, reply briefly in natural language. "
    "For a requested action, output exactly one valid Mindcraft command and no explanation."
)


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


class MindcraftCommandModel:
    def __init__(self, model_name: str, adapter_dir: str, device: str):
        self.device = torch.device(device)
        adapter_path = Path(adapter_dir)
        tokenizer_source = adapter_dir if (adapter_path / "tokenizer_config.json").exists() else model_name
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, use_fast=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        dtype = torch.bfloat16 if self.device.type == "cuda" else torch.float32
        base_model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=dtype,
            low_cpu_mem_usage=True,
        )
        self.model = PeftModel.from_pretrained(base_model, adapter_dir).to(self.device).eval()

    def generate_raw(self, user_text: str, max_new_tokens: int = 64) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]
        prompt = apply_chat_template(self.tokenizer, messages)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = generated[0, inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    def respond(self, user_text: str) -> dict:
        raw_output = self.generate_raw(user_text)
        result = validate_model_output(raw_output)
        return {
            "user": user_text,
            "raw_model_output": raw_output,
            "guard": result.to_dict(),
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Safely infer one Mindcraft command from natural language.")
    parser.add_argument("--adapter_dir", required=True, help="Path to the trained LoRA adapter or checkpoint.")
    parser.add_argument("--model_name", default="Qwen/Qwen3-4B")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--prompt", help="One request to run. Omit for interactive mode.")
    return parser.parse_args()


def main():
    args = parse_args()
    agent = MindcraftCommandModel(args.model_name, args.adapter_dir, args.device)

    if args.prompt:
        print(json.dumps(agent.respond(args.prompt), ensure_ascii=False, indent=2))
        return

    print("Mindcraft LoRA inference ready. Type q to exit.")
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in {"q", "quit", "exit"}:
            break
        if prompt:
            print(json.dumps(agent.respond(prompt), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
