"""Shared closed-set entity classification helpers for Day 27."""

import json
from pathlib import Path

from PIL import Image


LABELS = ("sheep", "pig")
USER_PROMPT = "Classify the single Minecraft animal in this image. Reply with exactly one lowercase label: sheep or pig."


def read_manifest(path: Path) -> list[dict]:
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not records:
        raise ValueError(f"{path} is empty")
    for record in records:
        if not isinstance(record, dict) or set(record) != {"image_path", "label"}:
            raise ValueError(f"{path} contains an invalid record")
        if record["label"] not in LABELS or not Path(record["image_path"]).is_file():
            raise ValueError(f"invalid record: {record}")
    return records


def prepare_image(image: Image.Image, max_side: int = 768) -> Image.Image:
    if max_side <= 0:
        raise ValueError("max_side must be positive")
    image = image.convert("RGB")
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    return image


def user_messages() -> list[dict]:
    return [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": USER_PROMPT}]}]


def extract_label(text: str) -> str | None:
    normalized = text.strip().lower()
    return normalized if normalized in LABELS else None
