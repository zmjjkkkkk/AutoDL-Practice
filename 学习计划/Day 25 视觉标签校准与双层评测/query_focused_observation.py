"""Send one local image to the Day 23 API with a fixed observation focus."""

import argparse
import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path


FOCUSES = ("overview", "blocks", "entities", "hazards")


def build_payload(image_path: Path, focus: str) -> dict:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("image must be PNG, JPEG, or WebP")
    return {
        "image_base64": base64.b64encode(image_path.read_bytes()).decode("ascii"),
        "mime_type": mime_type,
        "focus": focus,
    }


def call_gateway(gateway_url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        gateway_url.rstrip("/") + "/observe",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"focused observation request failed: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--focus", choices=FOCUSES, default="overview")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18768")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"image not found: {args.image}")
    try:
        response = call_gateway(args.gateway_url, build_payload(args.image, args.focus), args.timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
