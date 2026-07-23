"""Send one local image to a vLLM vision endpoint and validate its observation."""

import argparse
import base64
import io
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

from vision_observation_guard import validate_vision_output
from vision_output_schema import RESPONSE_FORMAT


SYSTEM_PROMPT = """You are a Minecraft visual observation component.
Describe only what is visible in the supplied image. Never suggest, emit, or execute a game command.
Return exactly one compact JSON object on one line, with exactly these keys:
summary, scene_labels, visible_blocks, visible_entities, hazards, confidence, uncertainties.
Allowed scene_labels: daylight, night, tree, open_area, water, cave, inventory_screen, unknown.
Allowed hazards: water, lava, fall, hostile_mob, unknown.
visible_blocks and visible_entities must use lowercase underscore identifiers.
List at most six unique visible blocks and at most four unique visible entities. Do not list tools, armor, or items.
Use an empty list when uncertain, and stop immediately after closing the JSON object.
confidence must be a number from 0 to 1. Use uncertainties for anything that is unclear.
Do not use Markdown, code fences, explanations, or exclamation marks."""


def image_data_url(path: Path, max_image_side: int) -> tuple[str, dict]:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Only PNG, JPEG, and WebP screenshots are supported.")

    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original)
        original_size = image.size
        image.thumbnail((max_image_side, max_image_side), Image.Resampling.LANCZOS)
        sent_size = image.size
        if image.mode != "RGB":
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90, optimize=True)

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    metadata = {
        "original_size": {"width": original_size[0], "height": original_size[1]},
        "sent_size": {"width": sent_size[0], "height": sent_size[1]},
        "max_image_side": max_image_side,
        "transformation": "in_memory_downscale_to_jpeg",
    }
    return f"data:image/jpeg;base64,{encoded}", metadata


def call_vllm(vllm_url: str, model: str, image_path: Path, max_image_side: int) -> tuple[str, dict]:
    data_url, image_metadata = image_data_url(image_path, max_image_side)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Observe this one frame safely."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0,
        "max_tokens": 240,
        "response_format": RESPONSE_FORMAT,
    }
    request = urllib.request.Request(
        vllm_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"vLLM returned HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to the vision service: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"], image_metadata
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("vLLM response did not contain a chat completion.") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path, help="Local PNG, JPEG, or WebP frame.")
    parser.add_argument("--vllm-url", default="http://127.0.0.1:8001/v1")
    parser.add_argument("--model", default="minecraft-vision")
    parser.add_argument("--max-image-side", type=int, default=768)
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Image does not exist: {args.image}")
    if args.max_image_side < 256:
        parser.error("--max-image-side must be at least 256 pixels.")

    raw_output, image_metadata = call_vllm(
        args.vllm_url,
        args.model,
        args.image,
        args.max_image_side,
    )
    result = validate_vision_output(raw_output).to_dict()
    print(json.dumps({"image": image_metadata, "raw_model_output": raw_output, "guard": result}, ensure_ascii=False, indent=2))
    sys.exit(0 if result["accepted"] else 2)


if __name__ == "__main__":
    main()
