# SPDX-License-Identifier: GPL-3.0-only
"""Create a new external review of explicitly selected finalized packages."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package_name in ("capture_protocol", "capture_session", "capture_analysis"):
    package_path = str(ROOT / "libs" / "python" / package_name)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from capture_analysis.qc_packages import (  # noqa: E402
    QcPackageReviewInputError,
    create_qc_package_review,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect exact native QC reports for 1–32 explicitly selected finalized packages "
            "into a new external directory, without writing to the packages."
        )
    )
    parser.add_argument(
        "--output", required=True, metavar="NEW_DIR",
        help="new directory outside every package; its parent must already exist",
    )
    parser.add_argument(
        "packages", nargs="+", metavar="PACKAGE",
        help="ordered finalized or finalized_recovered package paths (1–32)",
    )
    args = parser.parse_args(argv)
    try:
        review = create_qc_package_review(args.packages, args.output)
    except QcPackageReviewInputError as exc:
        parser.error(str(exc))
    except Exception as exc:
        print(
            f"QC review could not be completed: {type(exc).__name__}: {exc}\n"
            f"Output may be partial; retained for inspection: {args.output}",
            file=sys.stderr,
        )
        return 1
    print(
        f"Collected {review['collectedCount']} of {review['packageCount']} packages; "
        f"{review['failedCount']} collection failure(s).\n"
        f"Open {Path(args.output).resolve() / 'index.html'}"
    )
    return 1 if review["failedCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
