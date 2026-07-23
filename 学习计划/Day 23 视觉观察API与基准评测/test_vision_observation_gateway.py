"""Offline tests for Day 23 image intake, before any visual model call."""

import base64
import io
import sys
from pathlib import Path

from PIL import Image


DAY23_DIR = Path(__file__).resolve().parent
DAY22_DIR = DAY23_DIR.parent / "Day 22 多模态观察与安全辅助决策"
sys.path.insert(0, str(DAY22_DIR))

from vision_observation_gateway import parse_image_payload


def make_png_base64() -> str:
    image = Image.new("RGB", (1600, 900), color=(80, 160, 220))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def expect_value_error(payload: dict, expected: str):
    try:
        parse_image_payload(payload, 768)
    except ValueError as exc:
        assert expected in str(exc), (str(exc), expected)
        return
    raise AssertionError(f"Expected ValueError containing {expected}")


def main():
    data_url, metadata = parse_image_payload(
        {"image_base64": make_png_base64(), "mime_type": "image/png"},
        768,
    )
    assert data_url.startswith("data:image/jpeg;base64,")
    assert metadata["original_size"] == {"width": 1600, "height": 900}
    assert metadata["sent_size"] == {"width": 768, "height": 432}

    expect_value_error({"image_base64": "not base64", "mime_type": "image/png"}, "invalid_base64")
    expect_value_error({"image_base64": make_png_base64(), "mime_type": "image/gif"}, "unsupported_mime_type")
    expect_value_error({"image_base64": make_png_base64(), "mime_type": "image/png", "prompt": "move"}, "exactly")
    print("Day 23 vision observation gateway tests passed: 4/4")


if __name__ == "__main__":
    main()
