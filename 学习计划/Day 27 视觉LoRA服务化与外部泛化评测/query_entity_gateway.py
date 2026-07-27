"""Submit one local image to the loopback-tunneled Day 27 entity gateway."""

import argparse
import base64
import json
import mimetypes
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18769")
    args = parser.parse_args()
    mime_type, _ = mimetypes.guess_type(args.image.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        parser.error("only PNG, JPEG, and WebP images are supported")
    payload = {"image_base64": base64.b64encode(args.image.read_bytes()).decode("ascii"), "mime_type": mime_type}
    request = urllib.request.Request(args.gateway_url.rstrip("/") + "/classify-entity", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        print(json.dumps(json.loads(response.read().decode("utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
