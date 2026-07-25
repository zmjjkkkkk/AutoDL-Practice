"""Offline tests for explicit crop boundary validation."""

from query_region_observation import crop_box


def main():
    assert crop_box(10, 20, 100, 200, 2560, 1494) == (10, 20, 100, 200)
    for bounds in ((0, 0, 0, 10), (0, 0, 2561, 10), (-1, 0, 10, 10), (0, 20, 10, 20)):
        try:
            crop_box(*bounds, 2560, 1494)
        except ValueError:
            continue
        raise AssertionError(f"expected crop rejection: {bounds}")
    print("Day 25 region observation tests passed: 2/2")


if __name__ == "__main__":
    main()
