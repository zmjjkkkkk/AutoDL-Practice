"""Supervised LoRA training for a narrow Minecraft sheep/pig visual classification task."""

import argparse
import json
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from torch.utils.data import Dataset
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration, Trainer, TrainingArguments

from vision_classifier_common import full_messages, prepare_image, read_manifest, user_messages


class EntityDataset(Dataset):
    def __init__(self, records: list[dict], max_image_side: int):
        self.records = records
        self.max_image_side = max_image_side

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        return {
            "image": prepare_image(record["image_path"], self.max_image_side),
            "label": record["label"],
        }


class EntityCollator:
    def __init__(self, processor):
        self.processor = processor
        self.processor.tokenizer.padding_side = "right"

    def __call__(self, examples):
        images = [example["image"] for example in examples]
        full_texts = [
            self.processor.apply_chat_template(full_messages(example["label"]), tokenize=False, add_generation_prompt=False)
            for example in examples
        ]
        prompt_texts = [
            self.processor.apply_chat_template(user_messages(), tokenize=False, add_generation_prompt=True)
            for _ in examples
        ]
        batch = self.processor(text=full_texts, images=images, padding=True, return_tensors="pt")
        prompt_batch = self.processor(text=prompt_texts, images=images, padding=True, return_tensors="pt")
        labels = batch["input_ids"].clone()
        labels[batch["attention_mask"] == 0] = -100
        prompt_lengths = prompt_batch["attention_mask"].sum(dim=1)
        for index, prompt_length in enumerate(prompt_lengths.tolist()):
            labels[index, :prompt_length] = -100
        batch["labels"] = labels
        return batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--train-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=float, default=15)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--max-image-side", type=int, default=768)
    parser.add_argument("--seed", type=int, default=20260726)
    args = parser.parse_args()
    try:
        records = read_manifest(args.train_manifest)
    except ValueError as exc:
        parser.error(str(exc))
    if not torch.cuda.is_available():
        parser.error("CUDA is required for this visual LoRA training run")

    torch.manual_seed(args.seed)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    processor = AutoProcessor.from_pretrained(args.model_dir)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(args.model_dir, torch_dtype=dtype)
    model.config.use_cache = False
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
        remove_unused_columns=False,
        bf16=dtype == torch.bfloat16,
        fp16=dtype == torch.float16,
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=EntityDataset(records, args.max_image_side),
        data_collator=EntityCollator(processor),
    )
    result = trainer.train()
    adapter_dir = args.output_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapter_dir)
    processor.save_pretrained(adapter_dir)
    summary = {
        "train_examples": len(records),
        "epochs": args.epochs,
        "max_image_side": args.max_image_side,
        "train_loss": result.training_loss,
        "adapter_dir": str(adapter_dir),
    }
    (args.output_dir / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
