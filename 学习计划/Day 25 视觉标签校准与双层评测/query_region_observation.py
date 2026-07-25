"""Send one explicit image region to the read-only vision observation gateway."""

import argparse
import json
import mimetypes
from pathlib import Path

from PIL import Image

from tiled_observation import call_gateway, image_payload


FOCUSES = ("overview", "blocks", "entities", "hazards")


def crop_box(left: int, top: int, right: int, bottom: int, width: int, height: int) -> tuple[int, int, int, int]:
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("crop bounds must be inside the image and have positive width and height")
    return left, top, right, bottom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--left", required=True, type=int)
    parser.add_argument("--top", required=True, type=int)
    parser.add_argument("--right", required=True, type=int)
    parser.add_argument("--bottom", required=True, type=int)
    parser.add_argument("--focus", choices=FOCUSES, default="overview")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18768")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    mime_type, _ = mimetypes.guess_type(args.image.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        parser.error("only PNG, JPEG, and WebP images are supported")
    try:
        with Image.open(args.image) as source:
            source.load()
            box = crop_box(args.left, args.top, args.right, args.bottom, source.width, source.height)
            payload = image_payload(source.crop(box), mime_type)
            response = call_gateway(args.gateway_url, payload, args.timeout, args.focus)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    # Preserve only the gateway's verified response and crop geometry, never image bytes or raw model text.
    result = {
        "ok": response.get("ok") is True,
        "focus": args.focus,
        "region": {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3]},
        "original_size": {"width": source.width, "height": source.height},
        "crop_size": {"width": box[2] - box[0], "height": box[3] - box[1]},
        "reason": response.get("reason"),
        "reply": response.get("reply"),
        "observation": response.get("observation") if response.get("ok") is True else None,
        "image": response.get("image"),
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Report written: {args.output}")


if __name__ == "__main__":
    main()
