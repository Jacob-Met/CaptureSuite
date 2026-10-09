#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Create an editable external-prediction template without running a model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs/python/capture_analysis"),
    str(ROOT / "libs/python/capture_session"),
    str(ROOT / "libs/python/capture_protocol"),
]

from capture_analysis.eval.template import prepare_prediction_template  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare source-bound external predictions with unavailable null placeholders."
    )
    parser.add_argument("package", type=Path, help="selected .mmsession package")
    parser.add_argument("--bundle-job", required=True, help="existing ML bundle job ID")
    parser.add_argument("--model-id", required=True, help="caller-supplied model/experiment label")
    parser.add_argument("--output", type=Path, required=True,
                        help="new JSON file outside the selected package; parent must exist")
    args = parser.parse_args(argv)
    try:
        result = prepare_prediction_template(
            args.package, args.bundle_job, args.model_id, args.output
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    print(f"Created {result['output']}")
    print(
        f"{result['windowCount']} windows, {result['targetCount']} targets: "
        "all values are unavailable null placeholders. No model was run."
    )
    print(
        "Fill the null values with predictions, then use the existing eval --predictions command."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
