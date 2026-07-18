"""Two-GPU bf16 LoRA SFT for the small Mindcraft command dataset."""

import argparse
import json
import os
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments


PROJECT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(PROJECT_DIR / "hf-cache"))


def apply_chat_template(tokenizer, messages, add_generation_prompt):
    """Keep Qwen3 in direct-answer mode for command-oriented SFT."""
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=False,
        )
    except TypeError:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )


class MindcraftSftDataset(Dataset):
    def __init__(self, path, tokenizer, max_length):
        self.examples = []
        for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row["messages"]
            prompt = apply_chat_template(tokenizer, messages[:-1], add_generation_prompt=True)
            completion = messages[-1]["content"] + tokenizer.eos_token
            full_text = prompt + completion

            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            full_ids = tokenizer(full_text, add_special_tokens=False, truncation=True, max_length=max_length)["input_ids"]
            completion_start = min(len(prompt_ids), len(full_ids))
            labels = [-100] * completion_start + full_ids[completion_start:]
            if all(token == -100 for token in labels):
                raise ValueError(f"{path}:{line_number} was truncated before its target answer")
            self.examples.append({"input_ids": full_ids, "labels": labels})

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        return self.examples[index]


class SftDataCollator:
    def __init__(self, tokenizer):
        self.pad_token_id = tokenizer.pad_token_id

    def __call__(self, features):
        input_ids = [torch.tensor(feature["input_ids"], dtype=torch.long) for feature in features]
        labels = [torch.tensor(feature["labels"], dtype=torch.long) for feature in features]
        padded_input_ids = pad_sequence(input_ids, batch_first=True, padding_value=self.pad_token_id)
        return {
            "input_ids": padded_input_ids,
            "attention_mask": padded_input_ids.ne(self.pad_token_id).long(),
            "labels": pad_sequence(labels, batch_first=True, padding_value=-100),
        }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", default="Qwen/Qwen3-4B")
    parser.add_argument("--train_file", default=str(PROJECT_DIR / "output" / "mindcraft_sft_train.jsonl"))
    parser.add_argument("--eval_file", default=str(PROJECT_DIR / "output" / "mindcraft_sft_eval.jsonl"))
    parser.add_argument("--output_dir", default=str(PROJECT_DIR / "artifacts" / "qwen3_4b_mindcraft_lora"))
    parser.add_argument("--max_length", type=int, default=256)
    parser.add_argument("--epochs", type=float, default=12.0)
    return parser.parse_args()


def main():
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    train_dataset = MindcraftSftDataset(args.train_file, tokenizer, args.max_length)
    eval_dataset = MindcraftSftDataset(args.eval_file, tokenizer, args.max_length)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=1e-4,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        bf16=True,
        tf32=True,
        gradient_checkpointing=True,
        logging_steps=1,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],
        remove_unused_columns=False,
        ddp_find_unused_parameters=False,
        seed=20260715,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=SftDataCollator(tokenizer),
    )
    if trainer.is_world_process_zero():
        print(f"Training examples: {len(train_dataset)} | Evaluation examples: {len(eval_dataset)}")
        model.print_trainable_parameters()

    train_result = trainer.train()
    metrics = trainer.evaluate()
    trainer.accelerator.wait_for_everyone()
    if trainer.is_world_process_zero():
        adapter_dir = Path(args.output_dir) / "adapter"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        trainer.accelerator.unwrap_model(trainer.model).save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        summary = {
            "model_name": args.model_name,
            "world_size": int(os.environ.get("WORLD_SIZE", "1")),
            "precision": "bf16",
            "lora": {"r": 16, "alpha": 32, "dropout": 0.05},
            "train_examples": len(train_dataset),
            "eval_examples": len(eval_dataset),
            "train_metrics": train_result.metrics,
            "eval_metrics": metrics,
        }
        (Path(args.output_dir) / "training_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Saved LoRA adapter: {adapter_dir}")
        print(f"Final eval loss: {metrics.get('eval_loss')}")


if __name__ == "__main__":
    main()
