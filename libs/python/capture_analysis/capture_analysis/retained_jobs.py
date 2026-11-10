# SPDX-License-Identifier: GPL-3.0-only
"""Read saved analysis history without opening original recordings or running jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .feature_table_export import (
    FeatureTableExportError,
    _job_file,
    _job_root,
    _linked,
    _read_document,
    list_feature_tables,
)


def list_retained_jobs(package: Path, *, limit: int = 20) -> dict[str, Any]:
    """List newest saved manifests, keeping damaged entries visible for recovery.

    No original packagePath is followed. Feature metadata hashes are checked, but
    this is not raw-data or complete output validation. Exports check their inputs.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a nonnegative integer; zero lists all jobs")
    root = Path(package).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("choose a session package directory")
    jobs = root
    for part in ("processing", "jobs"):
        jobs = jobs / part
        if _linked(jobs):
            raise FeatureTableExportError(f"saved jobs path must not be linked: {jobs}")
        if jobs.exists() and not jobs.is_dir():
            raise FeatureTableExportError(f"saved jobs path is not a directory: {jobs}")
    entries = []
    hidden_attempts = 0
    if jobs.is_dir():
        for child in jobs.iterdir():
            if child.name.startswith("."):
                hidden_attempts += 1
                continue
            if not child.is_dir() and not _linked(child):
                continue
            entry: dict[str, Any] = {
                "jobId": child.name,
                "jobPath": str(child),
                "createdUtc": "",
                "recordedStatus": None,
                "readStatus": "ok",
                "warnings": [],
                "errors": [],
                "tables": [],
                "problems": [],
            }
            try:
                _, job = _job_root(child)
                _, manifest = _read_document(_job_file(job, "job_manifest.json"))
                if (
                    manifest.get("schemaId") != "capture.analysis_job/1"
                    or manifest.get("jobId") != child.name
                    or manifest.get("status")
                    not in {"completed", "completed_with_warnings", "failed"}
                ):
                    raise FeatureTableExportError("saved manifest identity or status is invalid")
                for key in ("warnings", "errors"):
                    values = manifest.get(key, [])
                    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                        raise FeatureTableExportError(f"saved {key} must be a list of strings")
                    entry[key] = values
                entry.update(
                    {
                        "recordedStatus": manifest["status"],
                        "createdUtc": str(manifest.get("createdUtc", "")),
                        "sessionId": manifest.get("sessionId"),
                        "timeRange": manifest.get("timeRange"),
                        "sourcesSelected": manifest.get("sourcesSelected", []),
                        "modalities": manifest.get("modalities", []),
                    }
                )
                if manifest["status"] != "failed":
                    entry["tables"] = list_feature_tables(job)["tables"]
            except (OSError, ValueError) as exc:
                entry["readStatus"] = "unreadable"
                entry["problems"].append(str(exc))
            entries.append(entry)
    entries.sort(key=lambda item: (item["createdUtc"], item["jobId"]), reverse=True)
    total = len(entries)
    if limit:
        entries = entries[:limit]
    return {
        "packagePath": str(root),
        "totalJobs": total,
        "shownJobs": len(entries),
        "hiddenInternalEntries": hidden_attempts,
        "verification": "retained metadata only; export verifies selected table payloads",
        "jobs": entries,
    }
