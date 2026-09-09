#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prove MSVC still rejects an owned narrowing conversion after external-header seating."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = ROOT / "build/evidence" / ("warning-boundary-" + uuid.uuid4().hex[:10])
    out.mkdir(parents=True, exist_ok=False)
    records = []

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
        owned, output = run(
            "owned_conversion",
            ["cmake", "--build", str(out / "build"), "--target", "owned_conversion"],
        )
        accepted = control == 0 and generated == 0 and owned not in (0, None) and "C4267" in output
    receipt = {
        "accepted": accepted,
        "checks": records,
        "scope": "Only unmodified generated headers are external; owned C4267 remains fatal",
    }
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(receipt, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
