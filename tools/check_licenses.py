#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify CaptureSuite license split and SPDX headers on source files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APACHE_TREES = (
    ROOT / "schemas",
    ROOT / "libs" / "python" / "capture_protocol",
    ROOT / "libs" / "python" / "capture_worker",
    ROOT / "workers" / "stub",
)

REQUIRED_ROOT_FILES = (
    "LICENSE",
    "LICENSING.md",
    "NOTICE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "CITATION.cff",
)

SOURCE_SUFFIXES = {".py", ".cpp", ".hpp", ".h", ".c", ".cc", ".proto", ".cmake"}
SKIP_DIR_NAMES = {
    ".git",
    "build",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "generated",
    "node_modules",
    "third_party",
}


def _is_apache_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for tree in APACHE_TREES:
        try:
            resolved.relative_to(tree.resolve())
            return True
        except ValueError:
            continue
    return False


def _expected_spdx(path: Path) -> str:
    if _is_apache_path(path):
        return "SPDX-License-Identifier: Apache-2.0"
    return "SPDX-License-Identifier: GPL-3.0-only"


def check_structure() -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_ROOT_FILES:
        if not (ROOT / name).is_file():
            errors.append(f"missing root file: {name}")
    for tree in APACHE_TREES:
        if not tree.is_dir():
            errors.append(f"missing Apache tree: {tree.relative_to(ROOT)}")
            continue
        if not (tree / "LICENSE").is_file():
            errors.append(f"missing LICENSE in {tree.relative_to(ROOT)}")
        if not (tree / "NOTICE").is_file():
            errors.append(f"missing NOTICE in {tree.relative_to(ROOT)}")
    root_license = (ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace")
    if "GNU GENERAL PUBLIC LICENSE" not in root_license:
        errors.append("root LICENSE does not look like GPL-3.0")
    return errors


def iter_source_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES and path.name != "CMakeLists.txt":
            continue
        # Generated protobuf Python bindings are regenerated; skip deep generated trees
        if "generated" in path.parts:
            continue
        out.append(path)
    return out


def check_spdx(*, enforce: bool) -> list[str]:
    errors: list[str] = []
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        head = "\n".join(text.splitlines()[:40])
        expected = _expected_spdx(path)
        if expected not in head:
            rel = path.relative_to(ROOT)
            if enforce:
                errors.append(f"missing {expected} in {rel}")
            else:
                errors.append(f"WARN missing {expected} in {rel}")
    return errors


def add_spdx_headers() -> int:
    """Insert SPDX header into files that lack one. Returns count updated."""
    updated = 0
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        expected = _expected_spdx(path)
        if expected in "\n".join(text.splitlines()[:40]):
            continue
        if path.suffix.lower() == ".py":
            lines = text.splitlines(keepends=True)
            insert_at = 0
            if lines and lines[0].startswith("#!"):
                insert_at = 1
            if insert_at < len(lines) and "coding" in lines[insert_at]:
                insert_at += 1
            header = f"# {expected}\n"
            new = "".join(lines[:insert_at]) + header + "".join(lines[insert_at:])
        elif path.suffix.lower() in {".cpp", ".hpp", ".h", ".c", ".cc"} or path.name == "CMakeLists.txt" or path.suffix.lower() == ".cmake":
            header = f"// {expected}\n" if path.suffix.lower() != ".cmake" and path.name != "CMakeLists.txt" else f"# {expected}\n"
            if path.suffix.lower() in {".cmake"} or path.name == "CMakeLists.txt":
                header = f"# {expected}\n"
            else:
                header = f"// {expected}\n"
            new = header + text
        elif path.suffix.lower() == ".proto":
            new = f"// {expected}\n" + text
        else:
            continue
        path.write_text(new, encoding="utf-8", newline="\n")
        updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enforce-spdx",
        action="store_true",
        help="Fail if source files lack SPDX headers (CI mode).",
    )
    parser.add_argument(
        "--add-spdx",
        action="store_true",
        help="Insert missing SPDX headers in place.",
    )
    args = parser.parse_args()
    if args.add_spdx:
        n = add_spdx_headers()
        print(f"updated {n} files with SPDX headers")
    errors = check_structure()
    spdx_msgs = check_spdx(enforce=args.enforce_spdx)
    if args.enforce_spdx:
        errors.extend(spdx_msgs)
    else:
        for msg in spdx_msgs[:20]:
            print(msg)
        if len(spdx_msgs) > 20:
            print(f"... and {len(spdx_msgs) - 20} more SPDX warnings")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("license check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
