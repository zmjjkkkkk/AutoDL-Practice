"""Offline unit tests for Day 23 benchmark scoring."""

from run_vision_benchmark import label_coverage, summarize


def main():
    expected = {
        "scene_labels": ["daylight", "water"],
        "hazards": ["water"],
        "visible_blocks": ["water", "stone"],
    }
    observation = {
        "scene_labels": ["daylight", "open_area", "water"],
        "hazards": ["water"],
        "visible_blocks": ["water"],
    }
    score = label_coverage(expected, observation)
    assert score["scene_labels"]["coverage"] == 1.0
    assert score["hazards"]["coverage"] == 1.0
    assert score["visible_blocks"]["coverage"] == 0.5
    assert score["overall_required_label_coverage"] == 0.8

    summary = summarize([{"ok": True, "coverage": score}, {"ok": False}])
    assert summary["cases"] == 2
    assert summary["accepted_cases"] == 1
    assert summary["accepted_rate"] == 0.5
    assert summary["mean_required_label_coverage"] == 0.8
    print("Day 23 vision benchmark tests passed: 2/2")


if __name__ == "__main__":
    main()
