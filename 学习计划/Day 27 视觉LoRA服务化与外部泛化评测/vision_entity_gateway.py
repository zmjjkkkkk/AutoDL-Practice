"""Loopback-only, read-only HTTP service for the Day 26 sheep/pig LoRA adapter."""

import argparse
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from peft import PeftModel
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from entity_common import extract_label, prepare_image, user_messages


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


class Classifier:
    def __init__(self, model_dir: Path, adapter_dir: Path, device: str, max_image_side: int):
        dtype = torch.bfloat16 if device.startswith("cuda") and torch.cuda.is_bf16_supported() else torch.float32
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(model_dir, torch_dtype=dtype)
        self.model = PeftModel.from_pretrained(model, adapter_dir).to(device).eval()
        self.processor = AutoProcessor.from_pretrained(model_dir)
        self.processor.tokenizer.padding_side = "right"
        self.device = device
        self.max_image_side = max_image_side

    @torch.inference_mode()
    def classify(self, image: Image.Image) -> str | None:
        prompt = self.processor.apply_chat_template(user_messages(), tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[prompt], images=[image], padding=True, return_tensors="pt").to(self.device)
        generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=8)
        text = self.processor.batch_decode(generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()
        return extract_label(text)


def parse_image_payload(payload: dict) -> tuple[Image.Image, dict]:
    if not isinstance(payload, dict) or set(payload) != {"image_base64", "mime_type"}:
        raise ValueError("payload must contain exactly image_base64 and mime_type")
    if payload["mime_type"] not in ALLOWED_MIME_TYPES or not isinstance(payload["image_base64"], str):
        raise ValueError("unsupported image payload")
    try:
        image_bytes = base64.b64decode(payload["image_base64"], validate=True)
    except ValueError as exc:
        raise ValueError("image_base64 must be valid base64") from exc
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("image payload exceeds the allowed size")
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.load()
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise ValueError("image payload is unreadable") from exc
    return image, {"original_size": {"width": image.width, "height": image.height}}


def make_handler(classifier: Classifier):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, payload: dict):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self.send_json(200, {"ok": True, "service": "minecraft-entity-lora-gateway", "labels": ["sheep", "pig"]})
            else:
                self.send_json(404, {"ok": False, "reason": "not_found"})

        def do_POST(self):
            if self.path != "/classify-entity":
                self.send_json(404, {"ok": False, "reason": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                source, metadata = parse_image_payload(payload)
                image = prepare_image(source, classifier.max_image_side)
                entity = classifier.classify(image)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json(400, {"ok": False, "entity": None, "reason": str(exc)})
                return
            if entity is None:
                self.send_json(200, {"ok": False, "entity": None, "reason": "invalid_model_label"})
                return
            metadata["sent_size"] = {"width": image.width, "height": image.height}
            metadata["max_image_side"] = classifier.max_image_side
            self.send_json(200, {"ok": True, "entity": entity, "reason": "verified_closed_set_entity", "image": metadata})

        def log_message(self, format, *args):
            print("%s - %s" % (self.address_string(), format % args))

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--adapter-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-image-side", type=int, default=768)
    args = parser.parse_args()
    classifier = Classifier(args.model_dir, args.adapter_dir, args.device, args.max_image_side)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(classifier))
    print(f"Day 27 entity gateway ready at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
