"""Validate model output before it is allowed to reach Mindcraft."""

from dataclasses import asdict, dataclass


SAFE_TEXT_RESPONSES = {
    "Hello! What can I help with?",
}

ALLOWED_COMMANDS = {
    "!stop",
    "!inventory",
    "!nearbyBlocks",
    '!goToPlayer("robot", 2)',
    '!followPlayer("robot", 3)',
    '!searchForBlock("oak_log", 32)',
    '!collectBlocks("oak_log", 4)',
    '!craftRecipe("oak_planks", 1)',
}

BLOCKED_REPLY = "I could not map that request to a verified Mindcraft action."


@dataclass(frozen=True)
class GuardResult:
    accepted: bool
    kind: str
    value: str
    candidate: str
    reason: str

    def to_dict(self):
        return asdict(self)


def first_nonempty_line(text: str) -> str:
    """Extract one candidate only; multiline output is never executed as a script."""
    cleaned = text.replace("<|im_end|>", "").strip()
    return next((line.strip() for line in cleaned.splitlines() if line.strip()), "")


def validate_model_output(raw_output: str) -> GuardResult:
    """Return an approved command/text reply or a blocked safe reply."""
    candidate = first_nonempty_line(raw_output)

    if candidate in ALLOWED_COMMANDS:
        return GuardResult(True, "command", candidate, candidate, "verified_command")
    if candidate in SAFE_TEXT_RESPONSES:
        return GuardResult(True, "text", candidate, candidate, "approved_text")
    if candidate.startswith("!"):
        reason = "unknown_command"
    elif not candidate:
        reason = "empty_output"
    else:
        reason = "unapproved_text"
    return GuardResult(False, "blocked", BLOCKED_REPLY, candidate, reason)
