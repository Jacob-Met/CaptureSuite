#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Record the configured vcpkg binary-cache restore without exposing arbitrary env."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from run_ci_tests import github_context

ROOT = Path(__file__).resolve().parents[1]


def build_receipt(root: Path, env: dict[str, str]) -> dict:
    raw_hit = env.get("CAPTURE_VCPKG_CACHE_HIT", "")
    if raw_hit not in ("", "true", "false"):
        raise ValueError("cache-hit must be empty, true, or false")
    key = env.get("CAPTURE_VCPKG_CACHE_KEY", "")
    sources = env.get("CAPTURE_VCPKG_BINARY_SOURCES", "")
    if not re.fullmatch(r"vcpkg-Windows-[0-9.]+-[0-9a-f]{64}", key):
        raise ValueError("cache key is missing its Windows/toolchain/manifest binding")
    match = re.fullmatch(r"clear;files,([A-Za-z]:[\\/][^;]+),readwrite", sources)
    if match is None:
        raise ValueError(
            "binary sources must use one absolute read-write files provider after clear"
        )
    manifest = (root / "vcpkg.json").read_bytes()
    return {
        "schema": "capturesuite.vcpkg-cache-receipt.v1",
        "cache_hit": True if raw_hit == "true" else False if raw_hit == "false" else None,
        "cache_key": key,
        "binary_source_kind": "files",
        "vcpkg_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "github": github_context(env),
        "scope": "Binary dependency reuse only; no build/test/clinical acceptance claim",
    }


def main() -> int:
    try:
        receipt = build_receipt(ROOT, dict(os.environ))
    except (OSError, ValueError) as exc:
        print(json.dumps({"accepted": False, "error": str(exc)}, indent=2))
        return 1
    receipt["created_at"] = datetime.now(UTC).isoformat()
    out = ROOT / "build/evidence" / f"vcpkg-cache-{env_run_id(receipt)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, indent=2))
    return 0


def env_run_id(receipt: dict) -> str:
    run_id = receipt["github"].get("GITHUB_RUN_ID", "local")
    return run_id if run_id.isdigit() else "local"


if __name__ == "__main__":
    raise SystemExit(main())
