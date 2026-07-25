"""Evaluate fixed-tile observations against the existing private Day24 manifest."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DAY23_DIR = Path(__file__).resolve().parents[1] / "Day 23 视觉观察API与基准评测"
sys.path.insert(0, str(DAY23_DIR))

from run_vision_benchmark import label_coverage, load_manifest, summarize
from tiled_observation import observe_tiled_image


def run_case(case: dict, manifest_dir: Path, args) -> dict:
    image_path = manifest_dir / case["image_path"]
    result = {"id": case["id"]}
    if not image_path.is_file():
        result.update({"ok": False, "error": "image_not_found"})
        return result
    try:
        tiled = observe_tiled_image(
            image_path,
            args.gateway_url,
            args.rows,
            args.columns,
            args.overlap,
            args.timeout,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        result.update({"ok": False, "error": str(exc)})
        return result

    observation = tiled["observation"] if tiled["ok"] else None
    result.update(
        {
            "ok": tiled["ok"],
            "reason": "verified_tiled_observation" if tiled["ok"] else "no_verified_tiles",
            "tile_count": tiled["tile_count"],
            "accepted_tile_count": tiled["accepted_tile_count"],
            # Private reports may retain only guard-accepted tile observations and
            # scaling metadata for diagnosis. They never retain image bytes or raw output.
            "tiles": tiled["tiles"],
            "observation": observation,
            "coverage": label_coverage(case["expected"], observation),
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:18768")
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--overlap", type=float, default=0.10)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--case-id", action="append", help="Run only this manifest case; repeat for multiple cases.")
    parser.add_argument("--report", type=Path, default=Path("reports/vision_tiled_benchmark.json"))
    args = parser.parse_args()
    try:
        cases = load_manifest(args.manifest)
        if args.rows <= 0 or args.columns <= 0 or not 0 <= args.overlap < 0.5:
            raise ValueError("rows/columns must be positive and overlap must be in [0, 0.5)")
    except ValueError as exc:
        parser.error(str(exc))

    if args.case_id:
        requested_ids = set(args.case_id)
        available_ids = {case["id"] for case in cases}
        unknown_ids = requested_ids - available_ids
        if unknown_ids:
            parser.error(f"unknown case ids: {', '.join(sorted(unknown_ids))}")
        cases = [case for case in cases if case["id"] in requested_ids]

    results = [run_case(case, args.manifest.parent, args) for case in cases]
    report = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gateway_url": args.gateway_url,
        "tiling": {"rows": args.rows, "columns": args.columns, "overlap": args.overlap},
        "summary": summarize(results),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report written: {args.report}")
    sys.exit(0 if report["summary"]["accepted_cases"] == len(results) else 2)


if __name__ == "__main__":
    main()
