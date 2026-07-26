"""Offline tests for strict held-out entity report comparison."""

from compare_entity_reports import compare


def result(path: str, expected: str, prediction: str):
    return {
        "image_path": path,
        "expected": expected,
        "prediction": prediction,
        "exact_match": expected == prediction,
    }


def main():
    baseline = {"results": [result("a.png", "sheep", "pig"), result("b.png", "pig", "pig")]}
    candidate = {"results": [result("a.png", "sheep", "sheep"), result("b.png", "pig", "pig")]}
    report = compare(baseline, candidate)
    assert report["baseline_accuracy"] == 0.5
    assert report["candidate_accuracy"] == 1.0
    assert report["accuracy_delta"] == 0.5
    try:
        compare(baseline, {"results": [result("other.png", "pig", "pig")]})
    except ValueError as exc:
        assert "same test images" in str(exc)
    else:
        raise AssertionError("expected mismatched-report rejection")
    print("Day 26 entity report comparison tests passed: 2/2")


if __name__ == "__main__":
    main()
