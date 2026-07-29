"""Loopback-only coordinator for independent Day 21 text and Day 27 vision services."""

import argparse
import json
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from multimodal_contract import command_result, compose_reply, observation_result, parse_assist_payload


MAX_REQUEST_BYTES = 7 * 1024 * 1024


class JsonClient:
    def __init__(self, base_url: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_health(self) -> dict:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=5) as response:
                return {"reachable": response.status == HTTPStatus.OK, "status": response.status}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            return {"reachable": False, "detail": str(exc)}

    def post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("upstream service is unavailable") from exc
        if not isinstance(body, dict):
            raise RuntimeError("upstream service returned an invalid response")
        return body


class GatewayHandler(BaseHTTPRequestHandler):
    command_client: JsonClient | None = None
    vision_client: JsonClient | None = None

    def send_json(self, status: HTTPStatus, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "reason": "not_found"})
            return
        self.send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "mindcraft-multimodal-safety-gateway",
                "command_upstream": self.command_client.get_health(),
                "vision_upstream": self.vision_client.get_health(),
            },
        )

    def do_POST(self):
        if self.path != "/assist":
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "reason": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= MAX_REQUEST_BYTES:
                raise ValueError("invalid_request_size")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            request = parse_assist_payload(payload)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "reason": "invalid_request", "detail": str(exc)})
            return

        command_upstream = None
        vision_upstream = None
        unavailable = []
        if request.text is not None:
            try:
                command_upstream = self.command_client.post("/command", {"text": request.text})
            except RuntimeError:
                unavailable.append("command")
        if request.image is not None:
            try:
                vision_upstream = self.vision_client.post("/classify-entity", request.image)
            except RuntimeError:
                unavailable.append("vision")

        command = command_result(command_upstream)
        observation = observation_result(vision_upstream)
        response = {
            "ok": not unavailable,
            "reply": compose_reply(command, observation),
            "command": command,
            "observation": observation,
            "execution": "This gateway does not execute commands.",
        }
        if unavailable:
            response["reason"] = "requested_upstream_unavailable"
            response["unavailable"] = unavailable
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, response)
            return
        self.send_json(HTTPStatus.OK, response)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command-url", default="http://127.0.0.1:8767")
    parser.add_argument("--vision-url", default="http://127.0.0.1:8769")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Bind only to loopback and use an SSH tunnel for remote access.")
    GatewayHandler.command_client = JsonClient(args.command_url, args.timeout)
    GatewayHandler.vision_client = JsonClient(args.vision_url, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"Day 28 multimodal safety gateway ready at http://{args.host}:{args.port}")
    print(f"Command upstream: {args.command_url} | Vision upstream: {args.vision_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down Day 28 multimodal safety gateway.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
