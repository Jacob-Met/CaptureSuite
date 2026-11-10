#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Frozen entry point for the existing offline CaptureSuite desktop."""

from __future__ import annotations

import sys
from pathlib import Path


def configure_resources() -> None:
    """Locate the same analysis resources after extracting a frozen bundle."""
    if not getattr(sys, "frozen", False):
        return
    from capture_analysis import jobs
    from capture_analysis.kinematics import registry as kinematics
    from capture_analysis.ml_bundle import job as ml_bundle
    from capture_analysis.plugins import registry

    assets = Path(sys._MEIPASS)  # noqa: SLF001
    jobs.SCHEMA_DIR = assets / "schemas" / "session" / "jsonschema"
    registry.DEFAULT_MANIFEST = assets / "capture_analysis" / "plugins" / "manifest.yaml"
    registry.SCHEMA_PATH = (
        assets / "docs" / "design" / "research" / "schemas" / "analysis_plugin_manifest.schema.json"
    )
    kinematics.REGISTRY_PATH = (
        assets / "schemas" / "kinematics" / "kinematics_columns.registry.json"
    )
    ml_bundle.ML_BUNDLE_SCHEMA = assets / "schemas" / "ml_bundle" / "ml_bundle.manifest.schema.json"
    for resource in (
        jobs.SCHEMA_DIR / "analysis_job.schema.json",
        registry.DEFAULT_MANIFEST,
        registry.SCHEMA_PATH,
        kinematics.REGISTRY_PATH,
        ml_bundle.ML_BUNDLE_SCHEMA,
    ):
        if not resource.is_file():
            raise RuntimeError(f"Desktop bundle is missing a required resource: {resource.name}")


def entrypoint() -> int:
    args = sys.argv[1:]
    if args and args[0] in {"--version", "-V"}:
        source = Path(sys.executable).resolve().parent / "SOURCE_COMMIT"
        print("CaptureSuite Desktop (experimental offline Linux x86_64)")
        print("Source " + source.read_text(encoding="utf-8").strip())
        return 0
    if args and args[0] == "--export-session":
        from export_session import main as export_main

        return export_main(args[1:])
    configure_resources()
    # The Linux distribution reviews existing recordings; Windows capture
    # transport is intentionally not connected by this entry point.
    if "--offline" not in args:
        sys.argv.insert(1, "--offline")
    from capture_desktop.main import main

    return main()


if __name__ == "__main__":
    raise SystemExit(entrypoint())
