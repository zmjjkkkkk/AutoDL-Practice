"""Offline tests for resolution-report comparison."""

from compare_resolution_reports import compare


def report(coverage, accepted=True, size=None):
    return {
        "results": [
            {
                "id": "one",
                "ok": accepted,
                "coverage": {"overall_required_label_coverage": coverage},
                "image": {"sent_size": size or {"width": 768, "height": 448}},
            }
        ]
    }


def main():
    result = compare(report(0.2), report(0.4, size={"width": 1024, "height": 597}))
    assert result["baseline"]["accepted_rate"] == 1.0
    assert result["candidate"]["mean_required_label_coverage"] == 0.4
    assert result["mean_required_label_coverage_delta"] == 0.2
    assert result["cases"][0]["coverage_delta"] == 0.2
    assert result["cases"][0]["candidate_sent_size"] == {"width": 1024, "height": 597}

    try:
        compare(report(0.2), {"results": [{"id": "other", "ok": True, "coverage": {}}]})
    except ValueError as exc:
        assert "same case ids" in str(exc)
    else:
        raise AssertionError("expected different case ids to fail")
    print("Day 25 resolution comparison tests passed: 2/2")


if __name__ == "__main__":
    main()
