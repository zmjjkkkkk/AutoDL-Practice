"""Send text with an optional local image to the loopback-tunneled Day 28 gateway."""

import argparse
import base64
import json
import mimetypes
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18770")
    args = parser.parse_args()
    payload = {}
    if args.text is not None:
        payload["text"] = args.text
    if args.image is not None:
        mime_type, _ = mimetypes.guess_type(args.image.name)
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            parser.error("only PNG, JPEG, and WebP images are supported")
        payload["image_base64"] = base64.b64encode(args.image.read_bytes()).decode("ascii")
        payload["mime_type"] = mime_type
    request = urllib.request.Request(
        args.gateway_url.rstrip("/") + "/assist",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        print(json.dumps(json.loads(response.read().decode("utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
