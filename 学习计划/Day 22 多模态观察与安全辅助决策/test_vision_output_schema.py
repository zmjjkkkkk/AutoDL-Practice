"""Offline validation for the shared vLLM structured-output schema."""

import json

from vision_output_schema import OBSERVATION_JSON_SCHEMA, RESPONSE_FORMAT


def main():
    assert RESPONSE_FORMAT == {"type": "json_object"}
    assert OBSERVATION_JSON_SCHEMA["additionalProperties"] is False
    assert OBSERVATION_JSON_SCHEMA["properties"]["visible_blocks"]["maxItems"] == 6
    assert OBSERVATION_JSON_SCHEMA["properties"]["visible_entities"]["maxItems"] == 4
    assert "uniqueItems" not in OBSERVATION_JSON_SCHEMA["properties"]["visible_blocks"]
    json.dumps(RESPONSE_FORMAT)
    print("Day 22 vision output schema tests passed: 1/1")


if __name__ == "__main__":
    main()
