"""Serve one-image, observation-only requests through the Day 22 safety guard."""

import argparse
import base64
import binascii
import io
import json
import os
import sys
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# The deployed service receives this dependency through PYTHONPATH. This local
# fallback keeps the repository's standalone examples runnable as well.
LOCAL_DAY22_DIR = Path(__file__).resolve().parent.parent / "Day 22 多模态观察与安全辅助决策"
if LOCAL_DAY22_DIR.is_dir():
    sys.path.insert(0, str(LOCAL_DAY22_DIR))

from vision_observation_guard import SAFE_FALLBACK, validate_vision_output
from vision_output_schema import RESPONSE_FORMAT


SYSTEM_PROMPT = """You are a Minecraft visual observation component.
Describe only what is visible in the supplied image. Never suggest, emit, or execute a game command.
Return exactly one compact JSON object on one line, with exactly these keys:
summary, scene_labels, visible_blocks, visible_entities, hazards, confidence, uncertainties.
Allowed scene_labels: daylight, night, tree, open_area, water, cave, desert, inventory_screen, unknown.
Allowed hazards: water, lava, fall, hostile_mob, unknown.
visible_blocks and visible_entities must use lowercase underscore identifiers.
List at most six unique visible blocks and at most four unique visible entities. Do not list tools, armor, or items.
Use an empty list when uncertain, and stop immediately after closing the JSON object.
confidence must be a number from 0 to 1. Use uncertainties for anything that is unclear.
Do not use Markdown, code fences, explanations, or exclamation marks."""

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_REQUEST_BYTES = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_PIXELS = 16_000_000
DEFAULT_MAX_IMAGE_SIDE = 768
Image.MAX_IMAGE_PIXELS = MAX_SOURCE_PIXELS


def parse_image_payload(payload: dict, max_image_side: int) -> tuple[str, dict]:
    """Validate an upload and build a temporary JPEG data URL without writing a file."""
    if set(payload) != {"image_base64", "mime_type"}:
        raise ValueError("request must contain exactly image_base64 and mime_type")
    encoded = payload["image_base64"]
    mime_type = payload["mime_type"]
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("image_base64 must be a non-empty base64 string")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError("unsupported_mime_type")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid_base64") from exc
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("invalid_image_size")

    try:
        with Image.open(io.BytesIO(image_bytes)) as original:
            image = ImageOps.exif_transpose(original)
            original_size = image.size
            if original_size[0] * original_size[1] > MAX_SOURCE_PIXELS:
                raise ValueError("image_has_too_many_pixels")
            image.thumbnail((max_image_side, max_image_side), Image.Resampling.LANCZOS)
            sent_size = image.size
            if image.mode != "RGB":
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90, optimize=True)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("invalid_image") from exc

    metadata = {
        "original_size": {"width": original_size[0], "height": original_size[1]},
        "sent_size": {"width": sent_size[0], "height": sent_size[1]},
        "max_image_side": max_image_side,
        "transformation": "in_memory_downscale_to_jpeg",
    }
    result = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{result}", metadata


class VisionClient:
    def __init__(self, base_url: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = os.getenv("VLLM_API_KEY")

    def observe(self, data_url: str) -> str:
        payload = {
            "model": self.model,
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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"vLLM returned HTTP {exc.code}: {detail[:800]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"vLLM request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("vLLM response did not contain choices[0].message.content") from exc
        if not isinstance(content, str):
            raise RuntimeError("vLLM returned a non-text assistant response")
        return content.strip()

    def health(self) -> dict:
        server_url = self.base_url.removesuffix("/v1")
        try:
            with urllib.request.urlopen(f"{server_url}/health", timeout=5) as response:
                return {"reachable": response.status == HTTPStatus.OK, "status": response.status}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            return {"reachable": False, "detail": str(exc)}


class GatewayHandler(BaseHTTPRequestHandler):
    client: VisionClient | None = None
    max_image_side: int = DEFAULT_MAX_IMAGE_SIDE
    debug_rejected_output: bool = False

    def _send_json(self, status: HTTPStatus, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "mindcraft-vision-observation-gateway",
                "mode": "observation_only",
                "vllm": self.client.health(),
            },
        )

    def do_POST(self):
        if self.path != "/observe":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("invalid_request_size")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request_must_be_an_object")
            data_url, image_metadata = parse_image_payload(payload, self.max_image_side)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            return

        try:
            raw_output = self.client.observe(data_url)
        except RuntimeError as exc:
            print(f"Vision upstream failure: {exc}")
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "vision_service_unavailable"})
            return

        guard = validate_vision_output(raw_output)
        if not guard.accepted and self.debug_rejected_output:
            # This is opt-in, terminal-only diagnostics. It never reaches the API response.
            print(
                "Vision observation rejected "
                f"[{guard.reason}]: {raw_output[:600]!r}"
            )
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": guard.accepted,
                "reply": guard.value if guard.accepted else SAFE_FALLBACK,
                "observation": guard.observation if guard.accepted else None,
                "reason": guard.reason,
                "image": image_metadata,
            },
        )

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-url", default="http://127.0.0.1:8001/v1")
    parser.add_argument("--model", default="minecraft-vision")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--max-image-side", type=int, default=DEFAULT_MAX_IMAGE_SIDE)
    parser.add_argument(
        "--debug-rejected-output",
        action="store_true",
        help="Print a truncated, escaped rejected model response to this remote terminal only.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("For safety, bind only to 127.0.0.1 and use an SSH tunnel for remote access.")
    if args.max_image_side < 256:
        raise ValueError("--max-image-side must be at least 256 pixels")
    GatewayHandler.client = VisionClient(args.vllm_url, args.model, args.timeout)
    GatewayHandler.max_image_side = args.max_image_side
    GatewayHandler.debug_rejected_output = args.debug_rejected_output
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"Day 23 vision observation gateway ready at http://{args.host}:{args.port}")
    print(f"Upstream vLLM: {args.vllm_url} | model: {args.model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down Day 23 vision observation gateway.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
