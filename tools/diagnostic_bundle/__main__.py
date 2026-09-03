# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

INCLUDE_NAMES = {
    "manifest.json",
    "integrity.json",
    "clock_mappings.json",
    "arrays.json",
}

INCLUDE_DIR_PREFIXES = (
    "events/",
    "logs/",
    "recovery/",
    "presets_snapshot/",
    "mappings/",
    "calibrations/",
)

INCLUDE_LEAF_NAMES = {
    "source.json",
    "sensors.json",
    "stream.json",
    "gaps.jsonl",
    "overloads.jsonl",
}

RAW_SUFFIXES = {".mcap", ".mkv", ".mp4", ".timing.mcap"}


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _is_raw(rel: Path) -> bool:
    name = rel.name.lower()
    if name.endswith(".timing.mcap"):
        return True
    return rel.suffix.lower() in RAW_SUFFIXES or name.endswith(".mcap")


def _should_include(rel: Path, *, include_raw: bool) -> bool:
    text = rel.as_posix()
    if text in INCLUDE_NAMES:
        return True
    if any(text.startswith(p) for p in INCLUDE_DIR_PREFIXES):
        return True
    if rel.name in INCLUDE_LEAF_NAMES:
        return True
    if text.startswith("processing/"):
        return include_raw
    if _is_raw(rel):
        return include_raw
    return False


def _redact_manifest(data: dict, *, include_identifiers: bool) -> dict:
    if include_identifiers:
        return data
    out = dict(data)
    for key in ("participant", "participantId", "participant_id"):
        if key in out and isinstance(out[key], dict):
            guid = out[key].get("id") or out[key].get("participant_id")
            out[key] = {"id": guid} if guid else None
        elif key in out and isinstance(out[key], str):
            # Keep GUID-shaped values; drop display names stored as strings.
            if len(out[key]) < 32:
                out[key] = "<redacted>"
    return out


def _journal_summary(package: Path) -> dict:
    db = package / "journal.sqlite"
    if not db.is_file():
        return {"available": False}
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT kind, COUNT(*) FROM events GROUP BY kind ORDER BY kind"
            ).fetchall()
            total = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            con.close()
        return {
            "available": True,
            "total_events": total,
            "by_kind": {kind: count for kind, count in rows},
        }
    except sqlite3.Error as exc:
        return {"available": False, "error": str(exc)}


def _machine_profile() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "node": platform.node(),
    }


def build_bundle(
    package: Path,
    output: Path,
    *,
    include_raw: bool = False,
    include_identifiers: bool = False,
) -> dict:
    package = package.resolve()
    if not package.is_dir():
        raise FileNotFoundError(f"session package not found: {package}")

    included: list[str] = []
    excluded: list[str] = []

    with tempfile.TemporaryDirectory(prefix="capture_diag_") as tmp:
        root = Path(tmp) / "bundle"
        root.mkdir()

        for path in package.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(package)
            if not _should_include(rel, include_raw=include_raw):
                excluded.append(rel.as_posix())
                continue
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if rel.name == "manifest.json" and not include_identifiers:
                data = json.loads(path.read_text(encoding="utf-8"))
                dest.write_text(
                    json.dumps(
                        _redact_manifest(data, include_identifiers=False),
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            else:
                shutil.copy2(path, dest)
            included.append(rel.as_posix())

        # App-level logs if present.
        local = Path(
            __import__("os").environ.get("LOCALAPPDATA", "")
        ) / "CaptureSuite" / "logs"
        if local.is_dir():
            log_dest = root / "app_logs"
            log_dest.mkdir(exist_ok=True)
            for log in local.glob("*.log*"):
                shutil.copy2(log, log_dest / log.name)
                included.append(f"app_logs/{log.name}")

        summary = {
            "created_utc": datetime.now(UTC).isoformat(),
            "package_path": str(package),
            "include_raw": include_raw,
            "include_identifiers": include_identifiers,
            "machine": _machine_profile(),
            "journal": _journal_summary(package),
            "included": sorted(included),
            "excluded_count": len(excluded),
            "excluded_sample": sorted(excluded)[:40],
        }
        (root / "bundle_manifest.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in root.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a CaptureSuite diagnostic zip (no raw data by default)."
    )
    parser.add_argument("package", type=Path, help="Path to a .mmsession folder")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output zip path (default: ./capture_diag_<utc>.zip)",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include MCAP/video segments and processing/",
    )
    parser.add_argument(
        "--include-identifiers",
        action="store_true",
        help="Keep participant display identifiers in manifest.json",
    )
    args = parser.parse_args(argv)
    output = args.output or Path(f"capture_diag_{_utc_stamp()}.zip")
    summary = build_bundle(
        args.package,
        output,
        include_raw=args.include_raw,
        include_identifiers=args.include_identifiers,
    )
    print(f"Wrote {output}")
    print(f"Included {len(summary['included'])} files; "
          f"excluded {summary['excluded_count']} (raw/processing by default).")
    print("See bundle_manifest.json inside the zip for the full inventory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
