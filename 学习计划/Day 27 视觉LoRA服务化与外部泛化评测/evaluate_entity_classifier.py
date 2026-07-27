"""Evaluate base or LoRA entity classification on the fixed Day 27 external set."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from peft import PeftModel
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from entity_common import extract_label, prepare_image, read_manifest, user_messages


def load_model(model_dir: Path, adapter_dir: Path | None, device: str):
    dtype = torch.bfloat16 if device.startswith("cuda") and torch.cuda.is_bf16_supported() else torch.float32
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(model_dir, torch_dtype=dtype)
    if adapter_dir:
        model = PeftModel.from_pretrained(model, adapter_dir)
    model.to(device)
    model.eval()
    processor = AutoProcessor.from_pretrained(model_dir)
    processor.tokenizer.padding_side = "right"
    return model, processor


@torch.inference_mode()
def predict(model, processor, image: Image.Image, device: str) -> tuple[str | None, str]:
    prompt = processor.apply_chat_template(user_messages(), tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[prompt], images=[image], padding=True, return_tensors="pt").to(device)
    generated = model.generate(**inputs, do_sample=False, max_new_tokens=8)
    text = processor.batch_decode(generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()
    return extract_label(text), text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--adapter-dir", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-image-side", type=int, default=768)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        records = read_manifest(args.manifest)
    except ValueError as exc:
        parser.error(str(exc))
    model, processor = load_model(args.model_dir, args.adapter_dir, args.device)
    results = []
    for record in records:
        with Image.open(record["image_path"]) as source:
            image = prepare_image(source, args.max_image_side)
        prediction, raw_text = predict(model, processor, image, args.device)
        results.append({"image_path": record["image_path"], "expected": record["label"], "prediction": prediction, "exact_match": prediction == record["label"], "sent_size": {"width": image.width, "height": image.height}, "generated_text": raw_text})
    matched = sum(result["exact_match"] for result in results)
    report = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "model_dir": str(args.model_dir), "adapter_dir": str(args.adapter_dir) if args.adapter_dir else None, "examples": len(results), "exact_match_count": matched, "exact_match_accuracy": matched / len(results), "results": results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exact external accuracy: {matched}/{len(results)} = {report['exact_match_accuracy']:.1%}")
    print(f"Report written: {args.report}")


if __name__ == "__main__":
    main()
