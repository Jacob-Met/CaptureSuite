#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Evaluate one cold/warm vcpkg cache pair against a predeclared useful threshold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_RATIO = 0.50
MIN_SECONDS_SAVED = 300.0


def evaluate(cold: dict, warm: dict) -> dict:
    problems: list[str] = []
    for label, item in (("cold", cold), ("warm", warm)):
        receipt = item.get("receipt", {})
        if receipt.get("schema") != "capturesuite.vcpkg-cache-receipt.v1":
            problems.append(f"{label}: wrong or missing cache receipt schema")
        seconds = item.get("configure_seconds")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
            problems.append(f"{label}: configure_seconds must be positive")
    cr, wr = cold.get("receipt", {}), warm.get("receipt", {})
    for field in ("cache_key", "vcpkg_manifest_sha256"):
        if cr.get(field) != wr.get(field) or not cr.get(field):
            problems.append(f"cold/warm {field} must match")
    if cr.get("cache_hit") is not False:
        problems.append("cold run must record cache_hit=false")
    if wr.get("cache_hit") is not True:
        problems.append("warm run must record cache_hit=true")
    cg, wg = cr.get("github", {}), wr.get("github", {})
    if cg.get("GITHUB_SHA") != wg.get("GITHUB_SHA") or not cg.get("GITHUB_SHA"):
        problems.append("cold/warm source SHA must match")
    if cg.get("GITHUB_RUN_ID") != wg.get("GITHUB_RUN_ID") or not cg.get("GITHUB_RUN_ID"):
        problems.append("benchmark must use two attempts of the same Actions run")
    if cg.get("GITHUB_RUN_ATTEMPT") == wg.get("GITHUB_RUN_ATTEMPT"):
        problems.append("cold/warm Actions attempts must differ")
    ratio = None
    saved = None
    csec, wsec = cold.get("configure_seconds"), warm.get("configure_seconds")
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in (csec, wsec)):
        ratio = wsec / csec
        saved = csec - wsec
        if ratio > MAX_RATIO:
            problems.append(f"warm configure ratio {ratio:.3f} exceeds {MAX_RATIO:.2f}")
        if saved < MIN_SECONDS_SAVED:
            problems.append(f"warm run saves only {saved:.1f}s; need {MIN_SECONDS_SAVED:.1f}s")
    return {
        "schema": "capturesuite.vcpkg-cache-benchmark.v1",
        "accepted": not problems,
        "configure_ratio": ratio,
        "seconds_saved": saved,
        "threshold": {"max_ratio": MAX_RATIO, "min_seconds_saved": MIN_SECONDS_SAVED},
        "problems": problems,
        "scope": (
            "Hosted configure latency and exact cache reuse only; no product correctness claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        pair = json.loads(args.pair.read_text(encoding="utf-8"))
        result = evaluate(pair["cold"], pair["warm"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {
            "schema": "capturesuite.vcpkg-cache-benchmark.v1",
            "accepted": False,
            "problems": [f"invalid benchmark input: {type(exc).__name__}"],
        }
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
