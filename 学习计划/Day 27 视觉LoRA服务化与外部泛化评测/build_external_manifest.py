"""Build a deterministic, private external-test manifest from sheep/pig new folders."""

import argparse
import json
import random
from pathlib import Path


LABELS = ("sheep", "pig")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def collect(data_root: Path) -> list[dict]:
    records = []
    for label in LABELS:
        directory = data_root / label / "new"
        if not directory.is_dir():
            raise ValueError(f"missing directory: {directory}")
        images = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
        if len(images) != 6:
            raise ValueError(f"{directory} must contain exactly 6 supported images, found {len(images)}")
        records.extend({"image_path": str(path.resolve()), "label": label} for path in images)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()
    try:
        records = collect(args.data_root)
    except ValueError as exc:
        parser.error(str(exc))
    random.Random(args.seed).shuffle(records)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "external_test.jsonl"
    manifest.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    summary = {"seed": args.seed, "examples": len(records), "by_label": {label: sum(x["label"] == label for x in records) for label in LABELS}}
    (args.output / "external_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
