"""Offline tests for Day 24 benchmark analysis."""

from analyze_vision_benchmark import analyze


def result(case_id, accepted, overall, block_coverage, missing):
    return {
        "id": case_id,
        "ok": accepted,
        "coverage": {
            "overall_required_label_coverage": overall,
            "scene_labels": {"coverage": 1.0, "missing": []},
            "hazards": {"coverage": None, "missing": []},
            "visible_blocks": {"coverage": block_coverage, "missing": missing},
            "visible_entities": {"coverage": 1.0, "missing": []},
        },
    }


def main():
    results = [
        result("near", True, 0.8, 0.5, ["ice"]),
        result("far", True, 0.4, 0.0, ["ice", "coal_ore"]),
        {"id": "broken", "ok": False},
    ]
    metadata = {"near": ["near", "daylight"], "far": ["far", "daylight"]}
    analysis = analyze(results, metadata)

    assert analysis["cases"] == 3
    assert analysis["accepted_cases"] == 2
    assert analysis["accepted_rate"] == 2 / 3
    assert abs(analysis["mean_required_label_coverage"] - 0.6) < 1e-9
    assert abs(analysis["field_mean_coverage"]["visible_blocks"] - 0.25) < 1e-9
    assert analysis["most_missed_labels"]["visible_blocks"][0] == {"label": "ice", "misses": 2}
    assert abs(
        analysis["coverage_by_case_tag"]["daylight"]["mean_required_label_coverage"] - 0.6
    ) < 1e-9

    empty = analyze([])
    assert empty["accepted_rate"] == 0.0
    assert empty["mean_required_label_coverage"] is None
    print("Day 24 vision benchmark analysis tests passed: 2/2")


if __name__ == "__main__":
    main()
