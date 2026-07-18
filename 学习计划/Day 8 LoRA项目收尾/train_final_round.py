import argparse
from dataclasses import dataclass
from pathlib import Path

import torch
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class SFTDataCollator:
    tokenizer: object

    def __call__(self, features):
        max_length = max(len(feature["input_ids"]) for feature in features)
        remainder = max_length % 8
        if remainder:
            max_length += 8 - remainder

        input_ids = []
        attention_masks = []
        labels = []
        for feature in features:
            padding = max_length - len(feature["input_ids"])
            input_ids.append(
                feature["input_ids"] + [self.tokenizer.pad_token_id] * padding
            )
            attention_masks.append(feature["attention_mask"] + [0] * padding)
            labels.append(feature["labels"] + [-100] * padding)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def chat_text(tokenizer, messages, add_generation_prompt):
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=False,
    )


def build_tokenizer_function(tokenizer, max_length):
    def tokenize(record):
        messages = record["messages"]
        full_tokens = tokenizer(
            chat_text(tokenizer, messages, False),
            truncation=True,
            max_length=max_length,
            add_special_tokens=False,
        )
        prompt_tokens = tokenizer(
            chat_text(tokenizer, messages[:-1], True),
            truncation=True,
            max_length=max_length,
            add_special_tokens=False,
        )
        labels = full_tokens["input_ids"].copy()
        prompt_length = min(len(prompt_tokens["input_ids"]), len(labels))
        labels[:prompt_length] = [-100] * prompt_length
        return {
            "input_ids": full_tokens["input_ids"],
            "attention_mask": full_tokens["attention_mask"],
            "labels": labels,
        }

    return tokenize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--train-file", type=Path, default=BASE_DIR / "data" / "train.jsonl")
    parser.add_argument("--eval-file", type=Path, default=BASE_DIR / "data" / "eval.jsonl")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "outputs" / "wechat-agent-final-v2")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--max-length", type=int, default=1024)
    args = parser.parse_args()

    set_seed(42)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"加载本地基座模型：{args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.adapter, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        attn_implementation="sdpa",
    )
    base_model.config.use_cache = False
    base_model.gradient_checkpointing_enable()
    base_model.enable_input_require_grads()

    print(f"加载旧 LoRA adapter 并继续训练：{args.adapter}")
    model = PeftModel.from_pretrained(
        base_model,
        args.adapter,
        is_trainable=True,
    )
    model.print_trainable_parameters()

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(args.train_file),
            "eval": str(args.eval_file),
        },
    )
    tokenized = dataset.map(
        build_tokenizer_function(tokenizer, args.max_length),
        remove_columns=dataset["train"].column_names,
        desc="分词并屏蔽提示词标签",
    )

    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        bf16=True,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
        optim="adamw_torch",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["eval"],
        data_collator=SFTDataCollator(tokenizer),
    )

    print("开始最终继续训练：1 epoch")
    trainer.train()

    final_adapter = args.output_dir / "final_adapter_v2"
    model.save_pretrained(final_adapter)
    tokenizer.save_pretrained(final_adapter)
    trainer.save_state()
    print(f"最终 adapter 已保存：{final_adapter}")


if __name__ == "__main__":
    main()
