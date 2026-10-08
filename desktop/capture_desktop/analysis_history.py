# SPDX-License-Identifier: GPL-3.0-only
"""Read saved analysis jobs from the selected package without changing them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

_JSON_LIMIT = 4 * 1024 * 1024
_LOG_LIMIT = 256 * 1024
_STATUSES = {"completed", "completed_with_warnings", "failed"}


@dataclass(frozen=True)
class SavedJob:
    job_id: str
    directory: Path
    status: str = ""
    created_utc: str = ""
    problem: str = ""


@dataclass(frozen=True)
class SavedJobDetails:
    job: SavedJob
    manifest: dict[str, Any]
    params_text: str
    log_text: str


def _direct_path(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Saved analysis paths must stay inside this package: {path}")


def _jobs_root(package: str | Path) -> Path:
    if not package:
        raise ValueError("Select a package before opening saved analysis.")
    root = Path(package).resolve()
    if not root.is_dir():
        raise ValueError(f"Package is unavailable: {root}")
    for path in (root / "processing", root / "processing" / "jobs"):
        _direct_path(path)
        if path.exists() and not path.is_dir():
            raise ValueError(f"Analysis job location is not a directory: {path}")
    return root / "processing" / "jobs"


def _job_directory(package: str | Path, job_id: str) -> Path:
    if (
        not isinstance(job_id, str)
        or not job_id
        or job_id.startswith(".")
        or job_id.endswith((".", " "))
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in job_id)
        or PureWindowsPath(job_id).is_reserved()
    ):
        raise ValueError("Select a visible analysis job from this package.")
    path = _jobs_root(package) / job_id
    _direct_path(path)
    if not path.is_dir():
        raise ValueError(f"Saved analysis job is unavailable: {job_id}")
    return path


def job_belongs_to_package(package: str | Path, job_dir: str | Path) -> bool:
    """Check the directory itself; recorded packagePath can predate a package copy."""
    if not package or not job_dir:
        return False
    try:
        candidate = Path(job_dir).absolute()
        return _job_directory(package, candidate.name) == candidate
    except (OSError, ValueError):
        return False


def _read_json(path: Path) -> dict[str, Any]:
    _direct_path(path)
    if not path.is_file():
        raise ValueError(f"Saved file is unavailable: {path.name}")
    with path.open("rb") as stream:
        raw = stream.read(_JSON_LIMIT + 1)
    if len(raw) > _JSON_LIMIT:
        raise ValueError(f"{path.name} exceeds the 4 MiB viewer limit.")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return doc


def _package_session_id(package: str | Path) -> str:
    manifest = _read_json(Path(package).resolve() / "manifest.json")
    identity = manifest.get("identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("Package identity is malformed.")
    # Only an explicit identity is stable when a package directory is copied.
    return str(manifest.get("sessionId") or identity.get("sessionId") or "")


def _read_job(
    package: str | Path, job_id: str, *, session_id: str
) -> tuple[SavedJob, dict[str, Any]]:
    path = _job_directory(package, job_id)
    manifest = _read_json(path / "job_manifest.json")
    if manifest.get("schemaId") != "capture.analysis_job/1":
        raise ValueError("This saved job uses an unsupported manifest schema.")
    if manifest.get("jobId") != job_id:
        raise ValueError("Saved manifest identity does not match its job directory.")
    if session_id and manifest.get("sessionId") != session_id:
        raise ValueError("Saved job belongs to a different session.")
    status = manifest.get("status")
    if not isinstance(status, str) or status not in _STATUSES:
        raise ValueError("This job has no completed or failed result to inspect yet.")
    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list) or any(not isinstance(row, dict) for row in outputs):
        raise ValueError("Saved manifest output inventory is malformed.")
    return SavedJob(job_id, path, status, str(manifest.get("createdUtc") or "")), manifest


def list_saved_jobs(package: str | Path) -> list[SavedJob]:
    """Visible jobs, including explicit unavailable rows; hidden attempts stay hidden."""
    jobs = _jobs_root(package)
    if not jobs.exists():
        return []
    session_id = _package_session_id(package)
    result = []
    for child in sorted(jobs.iterdir(), key=lambda p: p.name, reverse=True):
        if child.name.startswith(".") or not child.is_dir():
            continue
        try:
            job, _ = _read_job(package, child.name, session_id=session_id)
        except (OSError, ValueError, UnicodeError) as exc:
            job = SavedJob(child.name, child, problem=str(exc))
        result.append(job)
    return result


def load_saved_job(package: str | Path, job_id: str) -> SavedJobDetails:
    """Re-read the selected job at Open time; no cached catalog row authorizes a path."""
    job, manifest = _read_job(package, job_id, session_id=_package_session_id(package))
    try:
        params = _read_json(job.directory / "params.json")
        params_text = json.dumps(params, ensure_ascii=False, indent=2, sort_keys=True)
    except (OSError, ValueError, UnicodeError) as exc:
        params_text = f"Parameters unavailable: {exc}"
    try:
        logs = job.directory / "logs"
        _direct_path(logs)
        log = logs / "job.log"
        _direct_path(log)
        if not log.is_file():
            raise ValueError("No saved job.log file.")
        with log.open("rb") as stream:
            # Show the end of long logs, where completion/failure diagnostics live.
            size = stream.seek(0, 2)
            stream.seek(max(0, size - _LOG_LIMIT))
            log_text = stream.read(_LOG_LIMIT).decode("utf-8", errors="replace")
        if size > _LOG_LIMIT:
            log_text = f"Showing the final {_LOG_LIMIT:,} bytes of {size:,}.\n\n{log_text}"
    except (OSError, ValueError) as exc:
        log_text = f"Log unavailable: {exc}"
    return SavedJobDetails(job, manifest, params_text, log_text)
