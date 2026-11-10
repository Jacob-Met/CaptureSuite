#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Frozen entry point for the offline CaptureSuite analysis CLI.

Use the maintained CLI and orchestrator. Frozen packages relocate data files,
so adjust only the resource paths, never analysis semantics or generated input.
"""

from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _assets = Path(sys._MEIPASS)  # noqa: SLF001
    from capture_analysis import jobs
    from capture_analysis.plugins import registry

    jobs.SCHEMA_DIR = _assets / "schemas" / "session" / "jsonschema"
    registry.DEFAULT_MANIFEST = (
        _assets / "capture_analysis" / "plugins" / "manifest.yaml"
    )
    registry.SCHEMA_PATH = (
        _assets
        / "docs"
        / "design"
        / "research"
        / "schemas"
        / "analysis_plugin_manifest.schema.json"
    )
    # No cache is populated before resolving these paths.
    if not jobs.SCHEMA_DIR.joinpath("analysis_job.schema.json").is_file():
        raise RuntimeError("QC binary is missing bundled job validation schema")
    if not registry.DEFAULT_MANIFEST.is_file() or not registry.SCHEMA_PATH.is_file():
        raise RuntimeError("QC binary is missing bundled plugin manifest/schema")

from export_feature_table import main as export_main  # noqa: E402
from review_qc_packages import main as review_main  # noqa: E402
from run_analysis import main  # noqa: E402


def entrypoint() -> int:
    """Restrict experimental release claims to exercised native workflows."""
    supported = {"qc", "features", "plots", "all", "export-table", "review"}
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in {"--version", "-V"}:
        source_pin = Path(sys.executable).resolve().parent / "SOURCE_COMMIT"
        if not source_pin.is_file():
            raise RuntimeError("standalone release is missing source provenance")
        print("CaptureSuite Offline Analysis source " + source_pin.read_text().strip())
        return 0
    if command in {"-h", "--help", ""}:
        print(
            "CaptureSuite Offline Analysis (experimental Linux x86_64)\n"
            "Usage: capturesuite-analysis COMMAND PACKAGE [options]\n"
            "Available commands: qc, features, plots, all, export-table, review\n"
            "Export: capturesuite-analysis export-table JOB_DIR --list\n"
            "Compare: capturesuite-analysis review PACKAGE... --output NEW_DIR --inspect-payloads\n"
            "Try 'capturesuite-analysis qc --help' for command flags.\n"
            "For pose, kinematics, ML bundle or evaluation, use full CaptureSuite."
        )
        return 0 if command else 2
    if command not in supported:
        print(
            f"Unsupported standalone command: {command!r}. "
            f"Supported: {', '.join(sorted(supported))}.",
            file=sys.stderr,
        )
        return 2
    if command == "review":
        return review_main(sys.argv[2:], prog=f"{Path(sys.argv[0]).name} review")
    if command == "export-table":
        return export_main(sys.argv[2:], prog=f"{Path(sys.argv[0]).name} export-table")
    return main()


if __name__ == "__main__":
    raise SystemExit(entrypoint())
