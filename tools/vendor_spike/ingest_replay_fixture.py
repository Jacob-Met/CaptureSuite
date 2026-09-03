# SPDX-License-Identifier: GPL-3.0-only
"""Copy vendor replay JSONL fixtures into local appdata for sim/replay workers."""

from __future__ import annotations

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path

from capture_session.app_paths import appdata_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modality",
        required=True,
        choices=("emg", "imu", "radar"),
        help="Replay modality folder name",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Fixture JSONL or directory to copy",
    )
    args = parser.parse_args()
    src = args.source.resolve()
    if not src.exists():
        raise SystemExit(f"source not found: {src}")

    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    dest_root = appdata_root() / "vendor_replay" / args.modality / stamp
    dest_root.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, dest_root / item.name)
    else:
        shutil.copy2(src, dest_root / src.name)

    print(dest_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
