"""Small deterministic pre-policy for safe non-command Mindcraft replies."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


POLICY_PATH = Path(__file__).with_name("response_policy_spec.json")
TRANSFER_REQUEST = re.compile(
    r"\b(give|pass|hand|share|transfer|throw)\b|\b(can|could)\s+i\s+have\b",
    re.IGNORECASE,
)
SUPPORTED_OAK_TRANSFER = re.compile(r"\b(one|1)\s+oak\s+log(s)?\b", re.IGNORECASE)
UNSUPPORTED_PATTERNS = (
    ("prompt_override", re.compile(r"\b(ignore|bypass)\b.*\b(safety|rule|guard)\b", re.IGNORECASE)),
    ("building", re.compile(r"\b(build|construct|make)\b.*\b(castle|house|tower|portal)\b", re.IGNORECASE)),
    ("knowledge", re.compile(r"\b(who|what|when|where|why|how)\b.*\b(recipe|beacon|minecraft|invented|created)\b", re.IGNORECASE)),
    ("multi_step", re.compile(r"\b(find|search)\b.*\b(and|then)\b.*\b(mine|make|craft)\b", re.IGNORECASE)),
    ("relative_move", re.compile(r"\b(walk|run|go|move)\s+(north|south|east|west)\b", re.IGNORECASE)),
    ("broad_combat", re.compile(r"\b(fight|kill|attack)\b.*\b(any|whichever|all)\b", re.IGNORECASE)),
    ("broad_destruction", re.compile(r"\b(clear|destroy)\b.*\b(whole|entire|all)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class PolicyDecision:
    mode: str
    response_id: str | None
    reply: str | None
    reason: str

    @property
    def model_required(self) -> bool:
        return self.mode == "route_command"

    def to_dict(self):
        return {
            "mode": self.mode,
            "response_id": self.response_id,
            "reply": self.reply,
            "reason": self.reason,
            "model_required": self.model_required,
        }


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def decide_request(text: str, policy: dict | None = None) -> PolicyDecision:
    """Route only high-confidence cases; everything else stays with the existing guard."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    policy = policy or load_policy()
    normalized = " ".join(text.split())
    responses = policy["fixed_responses"]

    for reason, pattern in UNSUPPORTED_PATTERNS:
        if pattern.search(normalized):
            return PolicyDecision(
                "unsupported",
                "unsupported_request",
                responses["unsupported_request"],
                reason,
            )

    if TRANSFER_REQUEST.search(normalized) and not SUPPORTED_OAK_TRANSFER.search(normalized):
        return PolicyDecision(
            "needs_clarification",
            "clarify_transfer",
            responses["clarify_transfer"],
            "incomplete_or_unverified_transfer",
        )

    return PolicyDecision("route_command", None, None, "defer_to_model_and_exact_guard")
