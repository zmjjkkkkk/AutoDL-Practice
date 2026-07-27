"""Lightweight contract tests for the Day 27 external-evaluation workflow."""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from build_external_manifest import collect
from compare_entity_reports import compare
from entity_common import extract_label, prepare_image


class Day27ContractTests(unittest.TestCase):
    def make_dataset(self, root: Path, count: int = 6):
        for label in ("sheep", "pig"):
            directory = root / label / "new"
            directory.mkdir(parents=True)
            for index in range(count):
                Image.new("RGB", (900, 450), color=(index, 20, 30)).save(directory / f"{index}.png")

    def test_collect_requires_six_images_per_label(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_dataset(root)
            records = collect(root)
            self.assertEqual(len(records), 12)
            self.assertEqual(sum(item["label"] == "sheep" for item in records), 6)

    def test_collect_rejects_incomplete_class(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_dataset(root, count=5)
            with self.assertRaises(ValueError):
                collect(root)

    def test_closed_set_parsing_and_resize(self):
        self.assertEqual(extract_label(" sheep "), "sheep")
        self.assertIsNone(extract_label("a sheep"))
        resized = prepare_image(Image.new("RGB", (1600, 800)), 768)
        self.assertEqual(resized.size, (768, 384))

    def test_comparison_requires_same_images(self):
        baseline = {"results": [{"image_path": "a.png", "expected": "sheep", "prediction": "pig", "exact_match": False}]}
        candidate = {"results": [{"image_path": "a.png", "expected": "sheep", "prediction": "sheep", "exact_match": True}]}
        report = compare(baseline, candidate)
        self.assertEqual(report["accuracy_delta"], 1.0)
        with self.assertRaises(ValueError):
            compare(baseline, {"results": [{"image_path": "b.png", "expected": "sheep", "prediction": "sheep", "exact_match": True}]})


if __name__ == "__main__":
    unittest.main()
