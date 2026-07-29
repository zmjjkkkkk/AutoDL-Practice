"""Pure validation and response-composition rules for the Day 28 gateway."""

import base64
from dataclasses import dataclass


ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_ENTITIES = {"sheep", "pig"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 2_000


@dataclass(frozen=True)
class AssistRequest:
    text: str | None
    image: dict | None


def parse_assist_payload(payload: object) -> AssistRequest:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    allowed_keys = {"text", "image_base64", "mime_type"}
    if not set(payload).issubset(allowed_keys):
        raise ValueError("payload contains unsupported fields")

    text = payload.get("text")
    if text is not None:
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise ValueError("text must be a non-empty string within the size limit")
        text = text.strip()

    has_image_base64 = "image_base64" in payload
    has_mime_type = "mime_type" in payload
    if has_image_base64 != has_mime_type:
        raise ValueError("image_base64 and mime_type must be supplied together")
    image = None
    if has_image_base64:
        encoded = payload["image_base64"]
        mime_type = payload["mime_type"]
        if not isinstance(encoded, str) or mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError("unsupported image payload")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError("image_base64 must be valid base64") from exc
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError("image payload exceeds the allowed size")
        image = {"image_base64": encoded, "mime_type": mime_type}

    if text is None and image is None:
        raise ValueError("request must include text, image, or both")
    return AssistRequest(text=text, image=image)


def command_result(upstream: dict | None) -> dict:
    if upstream is None:
        return {"status": "not_requested", "command": None, "reply": None, "reason": None}
    guard = upstream.get("guard") if isinstance(upstream, dict) else None
    if not isinstance(guard, dict):
        return {"status": "unavailable", "command": None, "reply": None, "reason": "invalid_command_upstream_response"}
    if guard.get("accepted") is True and guard.get("kind") == "command" and isinstance(guard.get("value"), str):
        return {"status": "verified_command", "command": guard["value"], "reply": None, "reason": guard.get("reason")}
    reply = guard.get("value") if isinstance(guard.get("value"), str) else None
    return {"status": "no_command", "command": None, "reply": reply, "reason": guard.get("reason", "command_not_verified")}


def observation_result(upstream: dict | None) -> dict:
    if upstream is None:
        return {"status": "not_requested", "entity": None, "summary": None, "reason": None}
    if not isinstance(upstream, dict) or upstream.get("ok") is not True:
        return {"status": "unavailable", "entity": None, "summary": None, "reason": "vision_not_verified"}
    entity = upstream.get("entity")
    if entity not in ALLOWED_ENTITIES:
        return {"status": "unavailable", "entity": None, "summary": None, "reason": "invalid_vision_label"}
    return {"status": "verified_observation", "entity": entity, "summary": f"I can see a {entity}.", "reason": upstream.get("reason")}


def compose_reply(command: dict, observation: dict) -> str | None:
    parts = []
    if observation["status"] == "verified_observation":
        parts.append(observation["summary"])
    if command["status"] == "verified_command":
        parts.append("A command was verified but was not executed by this gateway.")
    elif command["reply"]:
        parts.append(command["reply"])
    return " ".join(parts) or None
