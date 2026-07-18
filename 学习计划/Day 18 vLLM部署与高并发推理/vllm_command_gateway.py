"""Expose Day 16 command validation while delegating generation to a local vLLM server."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DAY16_DIR = PROJECT_DIR.parent / "Day 16 LoRA推理与Mindcraft安全接入"
if str(DAY16_DIR) not in sys.path:
    sys.path.append(str(DAY16_DIR))

from command_guard import validate_model_output
from infer_mindcraft_command import SYSTEM_PROMPT


MAX_REQUEST_BYTES = 16_384


class VllmClient:
    def __init__(self, base_url: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = os.getenv("VLLM_API_KEY")

    def generate_raw(self, user_text: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0,
            "max_tokens": 64,
            "chat_template_kwargs": {"enable_thinking": False},
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
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
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
    client: VllmClient | None = None

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
            {"ok": True, "service": "mindcraft-vllm-gateway", "vllm": self.client.health()},
        )

    def do_POST(self):
        if self.path != "/command":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("invalid_request_size")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            user_text = payload["text"]
            if not isinstance(user_text, str) or not user_text.strip():
                raise ValueError("text must be a non-empty string")
        except (KeyError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            return

        try:
            raw_output = self.client.generate_raw(user_text.strip())
        except RuntimeError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "vllm_unavailable", "detail": str(exc)})
            return

        guard = validate_model_output(raw_output)
        self._send_json(
            HTTPStatus.OK,
            {"user": user_text, "raw_model_output": raw_output, "guard": guard.to_dict()},
        )

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run a loopback-only Mindcraft vLLM command gateway.")
    parser.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="mindcraft-lora")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("For safety, bind only to 127.0.0.1 and use an SSH tunnel for remote access.")

    GatewayHandler.client = VllmClient(args.vllm_url, args.model, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"vLLM command gateway ready at http://{args.host}:{args.port}")
    print(f"Upstream vLLM: {args.vllm_url} | model: {args.model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down gateway.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
