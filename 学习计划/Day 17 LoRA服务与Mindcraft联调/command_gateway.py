"""Serve approved Mindcraft commands from the LoRA model over local HTTP."""

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DAY16_DIR = PROJECT_DIR.parent / "Day 16 LoRA推理与Mindcraft安全接入"
if str(DAY16_DIR) not in sys.path:
    sys.path.append(str(DAY16_DIR))

from infer_mindcraft_command import MindcraftCommandModel


MAX_REQUEST_BYTES = 16_384


class GatewayHandler(BaseHTTPRequestHandler):
    agent = None

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
        self._send_json(HTTPStatus.OK, {"ok": True, "service": "mindcraft-lora-gateway"})

    def do_POST(self):
        if self.path != "/command":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request_size"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            text = payload["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("text must be a non-empty string")
        except (KeyError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            return

        response = self.agent.respond(text.strip())
        self._send_json(HTTPStatus.OK, response)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run a loopback-only Mindcraft LoRA command gateway.")
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--model_name", default="Qwen/Qwen3-4B")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("For safety, bind only to 127.0.0.1 and use an SSH tunnel for remote access.")

    print("Loading the base model and LoRA adapter once before serving requests...")
    GatewayHandler.agent = MindcraftCommandModel(args.model_name, args.adapter_dir, args.device)
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"Gateway ready at http://{args.host}:{args.port}")
    print("Endpoints: GET /health, POST /command with JSON {'text': 'please follow me'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down gateway.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
