"""Run verified observation on fixed image tiles and merge only safe labels."""

import base64
import io
import json
import math
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


LABEL_LIMITS = {"visible_blocks": 6, "visible_entities": 4}
LABEL_FIELDS = ("scene_labels", "hazards", "visible_blocks", "visible_entities")


def tile_boxes(width: int, height: int, rows: int, columns: int, overlap: float) -> list[tuple[int, int, int, int]]:
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    if rows <= 0 or columns <= 0:
        raise ValueError("rows and columns must be positive")
    if not 0 <= overlap < 0.5:
        raise ValueError("overlap must be in [0, 0.5)")

    cell_width = width / columns
    cell_height = height / rows
    boxes = []
    for row in range(rows):
        for column in range(columns):
            left = max(0, math.floor(column * cell_width - cell_width * overlap))
            top = max(0, math.floor(row * cell_height - cell_height * overlap))
            right = min(width, math.ceil((column + 1) * cell_width + cell_width * overlap))
            bottom = min(height, math.ceil((row + 1) * cell_height + cell_height * overlap))
            boxes.append((left, top, right, bottom))
    return boxes


def image_payload(image: Image.Image, mime_type: str) -> dict:
    output = io.BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=95)
    return {
        "image_base64": base64.b64encode(output.getvalue()).decode("ascii"),
        "mime_type": "image/jpeg",
        "source_mime_type": mime_type,
    }


def call_gateway(gateway_url: str, payload: dict, timeout: int, focus: str | None = None) -> dict:
    request_body = {"image_base64": payload["image_base64"], "mime_type": payload["mime_type"]}
    if focus is not None:
        request_body["focus"] = focus
    request = urllib.request.Request(
        gateway_url.rstrip("/") + "/observe",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"gateway request failed: {exc}") from exc


def merge_observations(observations: list[dict]) -> dict:
    merged = {field: [] for field in LABEL_FIELDS}
    for observation in observations:
        for field in LABEL_FIELDS:
            for label in observation.get(field, []):
                if label not in merged[field]:
                    merged[field].append(label)
    for field, limit in LABEL_LIMITS.items():
        merged[field] = merged[field][:limit]
    return merged


def observe_tiled_image(path: Path, gateway_url: str, rows: int, columns: int, overlap: float, timeout: int) -> dict:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("only PNG, JPEG, and WebP images are supported")
    with Image.open(path) as source:
        source.load()
        boxes = tile_boxes(source.width, source.height, rows, columns, overlap)
        tile_results = []
        accepted_observations = []
        for index, box in enumerate(boxes):
            response = call_gateway(gateway_url, image_payload(source.crop(box), mime_type), timeout)
            observation = response.get("observation") if response.get("ok") is True else None
            tile_results.append(
                {
                    "index": index,
                    "box": {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3]},
                    "ok": response.get("ok") is True,
                    "reason": response.get("reason"),
                    "observation": observation,
                    "image": response.get("image"),
                }
            )
            if isinstance(observation, dict):
                accepted_observations.append(observation)

    return {
        "ok": bool(accepted_observations),
        "tile_count": len(boxes),
        "accepted_tile_count": len(accepted_observations),
        "rows": rows,
        "columns": columns,
        "overlap": overlap,
        "tiles": tile_results,
        "observation": merge_observations(accepted_observations) if accepted_observations else None,
    }
