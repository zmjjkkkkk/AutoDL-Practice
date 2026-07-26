"""Offline tests for label parsing and deterministic image downscaling."""

from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from vision_classifier_common import extract_label, prepare_image


def main():
    assert extract_label("sheep") == "sheep"
    assert extract_label(" PIG ") == "pig"
    assert extract_label("a sheep") is None
    assert extract_label("cow") is None
    with TemporaryDirectory() as directory:
        path = Path(directory) / "image.png"
        Image.new("RGB", (2560, 1494), color="white").save(path)
        resized = prepare_image(path, 768)
        assert resized.size == (768, 448)
    print("Day 26 vision classifier helper tests passed: 2/2")


if __name__ == "__main__":
    main()
