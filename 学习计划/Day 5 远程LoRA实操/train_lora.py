import argparse
from dataclasses import dataclass
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
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
    pad_to_multiple_of: int = 8

    def __call__(self, features):
        max_length = max(len(feature["input_ids"]) for feature in features)
        if self.pad_to_multiple_of:
            remainder = max_length % self.pad_to_multiple_of
            if remainder:
                max_length += self.pad_to_multiple_of - remainder

        input_ids = []
        attention_masks = []
        labels = []

        for feature in features:
            padding_length = max_length - len(feature["input_ids"])
            input_ids.append(
                feature["input_ids"] + [self.tokenizer.pad_token_id] * padding_length
            )
            attention_masks.append(
                feature["attention_mask"] + [0] * padding_length
            )
            labels.append(feature["labels"] + [-100] * padding_length)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def apply_chat_template(tokenizer, messages, add_generation_prompt):
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=False,
    )


def build_tokenize_function(tokenizer, max_length):
    def tokenize_record(record):
        messages = record["messages"]
        full_text = apply_chat_template(
            tokenizer,
            messages,
            add_generation_prompt=False,
        )
        prompt_text = apply_chat_template(
            tokenizer,
            messages[:-1],
            add_generation_prompt=True,
        )

        full_tokens = tokenizer(
            full_text,
            truncation=True,
            max_length=max_length,
            add_special_tokens=False,
        )
        prompt_tokens = tokenizer(
            prompt_text,
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

    return tokenize_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    parser.add_argument("--train-file", type=Path, default=BASE_DIR / "data" / "train.jsonl")
    parser.add_argument("--eval-file", type=Path, default=BASE_DIR / "data" / "eval.jsonl")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "outputs" / "wechat-qwen3-8b-lora")
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--epochs", type=float, default=10)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"加载 tokenizer：{args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"加载基座模型：{args.model}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    lora_config = LoraConfig(
        task_type="CAUSAL_LM",
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(args.train_file),
            "eval": str(args.eval_file),
        },
    )
    tokenize_function = build_tokenize_function(tokenizer, args.max_length)
    tokenized_dataset = dataset.map(
        tokenize_function,
        remove_columns=dataset["train"].column_names,
        desc="应用对话模板并分词",
    )

    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        weight_decay=0.01,
        bf16=True,
        fp16=False,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
        dataloader_num_workers=2,
        optim="adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["eval"],
        data_collator=SFTDataCollator(tokenizer),
    )

    print("开始 LoRA 训练")
    trainer.train()

    final_adapter_dir = args.output_dir / "final_adapter"
    model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)
    trainer.save_state()
    print(f"LoRA adapter 已保存：{final_adapter_dir}")


if __name__ == "__main__":
    main()
