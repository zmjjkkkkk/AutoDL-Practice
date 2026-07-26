"""Offline tests for manifest building and validation rules."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from build_vision_dataset import collect_records, validate_balance
from validate_vision_dataset import read_manifest


def write_image(path: Path) -> None:
    Image.new("RGB", (16, 16), color="white").save(path)


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for label in ("sheep", "pig"):
            for split in ("train", "test"):
                folder = root / label / split
                folder.mkdir(parents=True)
                write_image(folder / f"{label}_{split}.png")
        records = collect_records(root)
        validate_balance(records)
        assert len(records["train"]) == 2
        manifest = root / "train.jsonl"
        manifest.write_text(
            "".join(json.dumps(record) + "\n" for record in records["train"]), encoding="utf-8"
        )
        assert len(read_manifest(manifest)) == 2

        (root / "pig" / "test" / "extra.png").touch()
        try:
            validate_balance(collect_records(root))
        except ValueError as exc:
            assert "balanced" in str(exc)
        else:
            raise AssertionError("expected split imbalance rejection")
    print("Day 26 vision dataset tests passed: 2/2")


if __name__ == "__main__":
    main()
