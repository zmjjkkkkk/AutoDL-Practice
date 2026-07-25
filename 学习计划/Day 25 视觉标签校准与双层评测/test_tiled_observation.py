"""Offline tests for deterministic tile geometry and safe label merging."""

from tiled_observation import merge_observations, tile_boxes


def main():
    assert tile_boxes(100, 80, 2, 2, 0) == [
        (0, 0, 50, 40),
        (50, 0, 100, 40),
        (0, 40, 50, 80),
        (50, 40, 100, 80),
    ]
    assert tile_boxes(100, 80, 2, 2, 0.1)[0] == (0, 0, 55, 44)
    try:
        tile_boxes(100, 80, 2, 2, 0.5)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("expected invalid overlap rejection")

    merged = merge_observations(
        [
            {
                "scene_labels": ["daylight", "open_area"],
                "hazards": ["water"],
                "visible_blocks": ["sand", "water", "stone", "grass_block"],
                "visible_entities": ["sheep", "zombie"],
            },
            {
                "scene_labels": ["daylight", "desert"],
                "hazards": ["fall"],
                "visible_blocks": ["sand", "cactus", "dirt", "oak_log"],
                "visible_entities": ["zombie", "player", "cow", "pig", "villager"],
            },
        ]
    )
    assert merged["scene_labels"] == ["daylight", "open_area", "desert"]
    assert merged["hazards"] == ["water", "fall"]
    assert merged["visible_blocks"] == ["sand", "water", "stone", "grass_block", "cactus", "dirt"]
    assert merged["visible_entities"] == ["sheep", "zombie", "player", "cow"]
    print("Day 25 tiled observation tests passed: 2/2")


if __name__ == "__main__":
    main()
