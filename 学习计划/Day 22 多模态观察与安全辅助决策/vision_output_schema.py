"""Shared contract reference and compatible vLLM JSON-object response mode."""

IDENTIFIER_PATTERN = "^[a-z0-9_]{1,48}$"
SAFE_TEXT_PATTERN = "^[^!\\n]{1,240}$"
UNCERTAINTY_PATTERN = "^[^!\\n]{1,120}$"

OBSERVATION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "scene_labels",
        "visible_blocks",
        "visible_entities",
        "hazards",
        "confidence",
        "uncertainties",
    ],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 240, "pattern": SAFE_TEXT_PATTERN},
        "scene_labels": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["daylight", "night", "tree", "open_area", "water", "cave", "desert", "inventory_screen", "unknown"],
            },
        },
        "visible_blocks": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string", "pattern": IDENTIFIER_PATTERN},
        },
        "visible_entities": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "pattern": IDENTIFIER_PATTERN},
        },
        "hazards": {
            "type": "array",
            "items": {"type": "string", "enum": ["water", "lava", "fall", "hostile_mob", "unknown"]},
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainties": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1, "maxLength": 120, "pattern": UNCERTAINTY_PATTERN},
        },
    },
}

RESPONSE_FORMAT = {
    "type": "json_object",
}
