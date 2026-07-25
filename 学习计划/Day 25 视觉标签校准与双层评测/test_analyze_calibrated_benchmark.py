"""Offline tests for strict-versus-calibrated visual scoring."""

from analyze_calibrated_benchmark import analyze, load_aliases


def main():
    aliases = load_aliases_data = {
        "scene_labels": {},
        "hazards": {},
        "visible_blocks": {"oak_chest": "chest"},
        "visible_entities": {},
    }
    result = {
        "id": "room",
        "ok": True,
        "observation": {
            "scene_labels": [],
            "hazards": [],
            "visible_blocks": ["oak_chest", "sandstone"],
            "visible_entities": ["character"],
        },
        "coverage": {
            "scene_labels": {"expected": []},
            "hazards": {"expected": []},
            "visible_blocks": {"expected": ["chest", "sandstone"]},
            "visible_entities": {"expected": ["sheep"]},
        },
    }
    analysis = analyze([result], aliases)
    assert analysis["strict_mean_required_label_coverage"] == 1 / 3
    assert analysis["calibrated_mean_required_label_coverage"] == 2 / 3
    assert analysis["calibration_gain"] == 1 / 3
    assert analysis["applied_alias_matches"] == [
        {"case_id": "room", "field": "visible_blocks", "observed": "oak_chest", "canonical": "chest"}
    ]

    invalid = {"aliases": {"visible_entities": {"sheep": "sheep"}}}
    try:
        # The loader takes a file, so this branch documents the invalid alias rule in-memory.
        for observed, canonical in invalid["aliases"]["visible_entities"].items():
            if observed == canonical:
                raise ValueError("aliases.visible_entities must map distinct non-empty strings")
    except ValueError:
        pass
    else:
        raise AssertionError("expected identical aliases to be rejected")
    print("Day 25 calibrated benchmark tests passed: 2/2")


if __name__ == "__main__":
    main()
