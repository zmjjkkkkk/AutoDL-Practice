"""Offline tests for focused-observation scoring."""

from compare_observation_focus import score


def main():
    expected = {
        "scene_labels": ["daylight"],
        "hazards": [],
        "visible_blocks": ["chest", "stone"],
        "visible_entities": ["sheep"],
    }
    observation = {
        "scene_labels": ["daylight"],
        "hazards": [],
        "visible_blocks": ["chest", "dirt"],
        "visible_entities": ["player"],
    }
    result = score(expected, observation)
    assert result["overall_required_label_coverage"] == 0.5
    assert result["fields"]["visible_blocks"]["coverage"] == 0.5
    assert result["fields"]["visible_entities"]["coverage"] == 0.0
    assert result["fields"]["visible_entities"]["missing"] == ["sheep"]
    print("Day 25 focus comparison tests passed: 2/2")


if __name__ == "__main__":
    main()
