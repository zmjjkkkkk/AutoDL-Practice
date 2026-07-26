"""Validate that entity-classification manifests are disjoint and point to readable images."""

import argparse
import json
from pathlib import Path

from PIL import Image


LABELS = {"sheep", "pig"}


def read_manifest(path: Path) -> list[dict]:
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not records:
        raise ValueError(f"{path} is empty")
    for record in records:
        if not isinstance(record, dict) or set(record) != {"image_path", "label"}:
            raise ValueError(f"{path} contains an invalid record")
        if record["label"] not in LABELS:
            raise ValueError(f"{path} contains unsupported label: {record['label']}")
        image_path = Path(record["image_path"])
        if not image_path.is_file():
            raise ValueError(f"image not found: {image_path}")
        try:
            with Image.open(image_path) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise ValueError(f"unreadable image {image_path}: {exc}") from exc
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", required=True, type=Path)
    parser.add_argument("--test-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        train_records = read_manifest(args.train_manifest)
        test_records = read_manifest(args.test_manifest)
    except ValueError as exc:
        parser.error(str(exc))

    train_paths = {record["image_path"] for record in train_records}
    test_paths = {record["image_path"] for record in test_records}
    overlap = train_paths & test_paths
    if overlap:
        parser.error(f"train/test leakage detected: {sorted(overlap)[:3]}")
    summary = {
        "train_count": len(train_records),
        "test_count": len(test_records),
        "train_by_label": {label: sum(record["label"] == label for record in train_records) for label in sorted(LABELS)},
        "test_by_label": {label: sum(record["label"] == label for record in test_records) for label in sorted(LABELS)},
        "leakage": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
