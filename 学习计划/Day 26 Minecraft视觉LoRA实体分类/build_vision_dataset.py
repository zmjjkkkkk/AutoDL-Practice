"""Build deterministic train/test manifests from the private sheep/pig screenshot folders."""

import argparse
import json
import random
from pathlib import Path


LABELS = ("sheep", "pig")
SPLITS = ("train", "test")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def collect_records(data_root: Path) -> dict[str, list[dict]]:
    records_by_split = {split: [] for split in SPLITS}
    for label in LABELS:
        for split in SPLITS:
            directory = data_root / label / split
            if not directory.is_dir():
                raise ValueError(f"missing directory: {directory}")
            images = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
            if not images:
                raise ValueError(f"no supported images in {directory}")
            records_by_split[split].extend(
                {"image_path": str(path.resolve()), "label": label} for path in images
            )
    return records_by_split


def validate_balance(records_by_split: dict[str, list[dict]]) -> None:
    for split, records in records_by_split.items():
        counts = {label: sum(record["label"] == label for record in records) for label in LABELS}
        if any(count == 0 for count in counts.values()):
            raise ValueError(f"{split} requires at least one image for each label: {counts}")
        if len(set(counts.values())) != 1:
            raise ValueError(f"{split} must be balanced across labels: {counts}")


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--seed", type=int, default=20260726)
    args = parser.parse_args()

    try:
        records_by_split = collect_records(args.data_root)
        validate_balance(records_by_split)
    except ValueError as exc:
        parser.error(str(exc))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"schema_version": "1.0", "seed": args.seed, "labels": list(LABELS), "splits": {}}
    for offset, split in enumerate(SPLITS):
        records = list(records_by_split[split])
        random.Random(args.seed + offset).shuffle(records)
        write_jsonl(args.output_dir / f"{split}.jsonl", records)
        summary["splits"][split] = {
            "count": len(records),
            "by_label": {label: sum(record["label"] == label for record in records) for label in LABELS},
        }
    (args.output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
