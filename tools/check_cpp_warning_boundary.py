#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prove MSVC still rejects an owned narrowing conversion after external-header seating."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OWNED_CPP_ROOTS = ("daemon", "libs/cpp", "workers", "tools/session_doctor", "tests/cpp")
DIRECT_GETENV = re.compile(r"(?<!_)\b(?:std::)?getenv\s*\(")


def find_deprecated_env_access(root: Path) -> list[str]:
    """Find direct getenv calls that MSVC deprecates under the project's /WX gate."""
    hits = []
    for rel_root in OWNED_CPP_ROOTS:
        folder = root / rel_root
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".cpp", ".cc", ".c", ".hpp", ".h"}:
                continue
            if "generated" in path.parts or "third_party" in path.parts or path.name == "env.hpp":
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if DIRECT_GETENV.search(line):
                    hits.append(f"{path.relative_to(root).as_posix()}:{number}")
    return hits


def main() -> int:
    out = ROOT / "build/evidence" / ("warning-boundary-" + uuid.uuid4().hex[:10])
    out.mkdir(parents=True, exist_ok=False)
    records = []
    deprecated_env = find_deprecated_env_access(ROOT)
    if deprecated_env:
        receipt = {
            "accepted": False,
            "checks": records,
            "deprecated_env_access": deprecated_env,
            "scope": "Owned MSVC portability and external-header warning boundary",
        }
        (out / "receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps(receipt, indent=2))
        return 1

    def run(name, command):
        logfile = out / (name + ".log")
        with logfile.open("w", encoding="utf-8") as log:
            try:
                result = subprocess.run(
                    command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=90
                )
                code = result.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                log.write(type(exc).__name__)
                code = None
        text = logfile.read_text(encoding="utf-8", errors="replace")
        records.append(
            {
                "name": name,
                "exit": code,
                "log_sha256": hashlib.sha256(logfile.read_bytes()).hexdigest(),
            }
        )
        print(name, code)
        return code, text

    configure, _ = run(
        "configure",
        [
            "cmake",
            "-G",
            "Ninja",
            "-S",
            str(ROOT / "tests/cmake/warning_boundary"),
            "-B",
            str(out / "build"),
        ],
    )
    accepted = False
    if configure == 0:
        control, _ = run("control", ["cmake", "--build", str(out / "build"), "--target", "control"])
        generated, _ = run(
            "generated_header",
            ["cmake", "--build", str(out / "build"), "--target", "generated_header"],
        )
        env_helper, _ = run(
            "env_helper", ["cmake", "--build", str(out / "build"), "--target", "env_helper"]
        )
        owned, output = run(
            "owned_conversion",
            ["cmake", "--build", str(out / "build"), "--target", "owned_conversion"],
        )
        accepted = (
            control == 0
            and generated == 0
            and env_helper == 0
            and owned not in (0, None)
            and "C4267" in output
        )
    receipt = {
        "accepted": accepted,
        "checks": records,
        "deprecated_env_access": deprecated_env,
        "scope": (
            "Owned MSVC portability plus generated-header warning boundary; "
            "owned C4267 remains fatal"
        ),
    }
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(receipt, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
