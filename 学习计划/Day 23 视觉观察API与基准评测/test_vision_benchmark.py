"""Offline unit tests for Day 23 benchmark scoring."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from run_vision_benchmark import label_coverage, load_manifest, summarize


def main():
    expected = {
        "scene_labels": ["daylight", "water"],
        "hazards": ["water"],
        "visible_blocks": ["water", "stone"],
        "visible_entities": ["zombie"],
    }
    observation = {
        "scene_labels": ["daylight", "open_area", "water"],
        "hazards": ["water"],
        "visible_blocks": ["water"],
        "visible_entities": ["zombie"],
    }
    score = label_coverage(expected, observation)
    assert score["scene_labels"]["coverage"] == 1.0
    assert score["hazards"]["coverage"] == 1.0
    assert score["visible_blocks"]["coverage"] == 0.5
    assert score["visible_entities"]["coverage"] == 1.0
    assert score["overall_required_label_coverage"] == 5 / 6

    summary = summarize([{"ok": True, "coverage": score}, {"ok": False}])
    assert summary["cases"] == 2
    assert summary["accepted_cases"] == 1
    assert summary["accepted_rate"] == 0.5
    assert summary["mean_required_label_coverage"] == 5 / 6

    base_case = {
        "id": "one",
        "image_path": "private/one.png",
        "expected": {
            "scene_labels": ["daylight"],
            "hazards": [],
            "visible_blocks": ["stone"],
            "visible_entities": [],
        },
    }
    with TemporaryDirectory() as directory:
        manifest_path = Path(directory) / "manifest.json"
        manifest_path.write_text(json.dumps({"cases": [base_case]}), encoding="utf-8")
        assert load_manifest(manifest_path) == [base_case]

        too_many_blocks = json.loads(json.dumps(base_case))
        too_many_blocks["expected"]["visible_blocks"] = [
            "stone", "dirt", "sand", "water", "grass_block", "cactus", "oak_log"
        ]
        manifest_path.write_text(json.dumps({"cases": [too_many_blocks]}), encoding="utf-8")
        try:
            load_manifest(manifest_path)
        except ValueError as exc:
            assert "at most 6 labels" in str(exc)
        else:
            raise AssertionError("expected an over-limit visible_blocks validation error")
    print("Day 23 vision benchmark tests passed: 2/2")


if __name__ == "__main__":
    main()
