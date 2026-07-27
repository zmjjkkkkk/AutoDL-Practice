"""Validate the Day 27 external manifest without modifying its images."""

import argparse
import json
from pathlib import Path

from PIL import Image

from entity_common import LABELS, read_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        records = read_manifest(args.manifest)
        if len(records) != 12:
            raise ValueError(f"external manifest must contain 12 images, found {len(records)}")
        for label in LABELS:
            if sum(record["label"] == label for record in records) != 6:
                raise ValueError(f"external manifest must contain 6 {label} images")
        for record in records:
            with Image.open(record["image_path"]) as image:
                image.verify()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"examples": len(records), "by_label": {label: sum(x["label"] == label for x in records) for label in LABELS}, "valid": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
