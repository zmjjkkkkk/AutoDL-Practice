"""Validate future vision-language output before it reaches the Mindcraft UI."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = PROJECT_DIR / "vision_observation_contract.json"
SAFE_FALLBACK = "I could not verify a visual observation."
IDENTIFIER = re.compile(r"^[a-z0-9_]{1,48}$")
REQUIRED_KEYS = {
    "summary",
    "scene_labels",
    "visible_blocks",
    "visible_entities",
    "hazards",
    "confidence",
    "uncertainties",
}
ALLOWED_SCENE_LABELS = {
    "daylight",
    "night",
    "tree",
    "open_area",
    "water",
    "cave",
    "inventory_screen",
    "unknown",
}
ALLOWED_HAZARDS = {"water", "lava", "fall", "hostile_mob", "unknown"}


@dataclass(frozen=True)
class ObservationResult:
    accepted: bool
    kind: str
    value: str
    candidate: str
    reason: str
    observation: dict | None = None

    def to_dict(self):
        return asdict(self)


def reject(candidate: str, reason: str) -> ObservationResult:
    return ObservationResult(False, "blocked", SAFE_FALLBACK, candidate, reason)


def valid_identifiers(values, limit: int) -> bool:
    return (
        isinstance(values, list)
        and len(values) <= limit
        and all(isinstance(value, str) and IDENTIFIER.fullmatch(value) for value in values)
    )


def validate_vision_output(raw_output: str) -> ObservationResult:
    """Accept only one complete observation object with no action-carrying fields."""
    if not isinstance(raw_output, str) or not raw_output.strip():
        return reject("", "empty_output")
    candidate = raw_output.strip()
    if "\n" in candidate:
        return reject(candidate, "multiline_output")
    try:
        observation = json.loads(candidate)
    except json.JSONDecodeError:
        return reject(candidate, "invalid_json")
    if not isinstance(observation, dict):
        return reject(candidate, "not_an_object")
    if set(observation) != REQUIRED_KEYS:
        return reject(candidate, "unexpected_fields")

    summary = observation["summary"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 240 or "!" in summary or "\n" in summary:
        return reject(candidate, "unsafe_summary")
    if not isinstance(observation["scene_labels"], list) or not set(observation["scene_labels"]).issubset(ALLOWED_SCENE_LABELS):
        return reject(candidate, "invalid_scene_labels")
    if not valid_identifiers(observation["visible_blocks"], 8):
        return reject(candidate, "invalid_visible_blocks")
    if not valid_identifiers(observation["visible_entities"], 8):
        return reject(candidate, "invalid_visible_entities")
    if not isinstance(observation["hazards"], list) or not set(observation["hazards"]).issubset(ALLOWED_HAZARDS):
        return reject(candidate, "invalid_hazards")
    confidence = observation["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        return reject(candidate, "invalid_confidence")
    uncertainties = observation["uncertainties"]
    if (
        not isinstance(uncertainties, list)
        or len(uncertainties) > 4
        or not all(isinstance(item, str) and 0 < len(item) <= 120 and "!" not in item and "\n" not in item for item in uncertainties)
    ):
        return reject(candidate, "invalid_uncertainties")

    return ObservationResult(True, "observation", summary.strip(), candidate, "verified_observation", observation)


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
