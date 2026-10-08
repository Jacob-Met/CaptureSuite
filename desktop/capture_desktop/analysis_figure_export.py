# SPDX-License-Identifier: GPL-3.0-only
"""Copy selected, recorded analysis PNGs into a portable provenance bundle."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from PySide6.QtGui import QImage

SCHEMA_ID = "capture.analysis_figure_bundle/1"
MAX_METADATA_BYTES = 4 * 1024**2
MAX_FIGURE_BYTES = 64 * 1024**2
MAX_SELECTION_BYTES = 512 * 1024**2
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class FigureExportError(ValueError):
    """The selected source or destination cannot produce a truthful bundle."""


@dataclass(frozen=True)
class FigureOutput:
    relative_path: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class FigureSource:
    job_dir: Path
    directory_identity: tuple[int, int]
    manifest_bytes: bytes
    params_bytes: bytes
    figures: tuple[FigureOutput, ...]

    @property
    def manifest(self) -> dict:
        # Return a fresh value so a UI consumer cannot change the saved provenance.
        return json.loads(self.manifest_bytes)

    @property
    def job_id(self) -> str:
        return self.manifest["jobId"]


@dataclass(frozen=True)
class FigureBundleResult:
    path: Path
    figure_count: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_object(data: bytes, name: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"non-finite value {value}")

    try:
        result = json.loads(
            data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant
        )
        if not isinstance(result, dict):
            raise ValueError("expected a JSON object")
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FigureExportError(f"Invalid {name}: {exc}") from exc


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise FigureExportError("An output has no relative path.")
    parts = PurePosixPath(value).parts
    if (
        not parts
        or "/".join(parts) != value
        or value.startswith("/")
        or any(
            part in (".", "..")
            or part.endswith((".", " "))
            or PureWindowsPath(part).is_reserved()
            or any(ch in '<>:"\\|?*' or ord(ch) < 32 for ch in part)
            for part in parts
        )
    ):
        raise FigureExportError(f"Output path is not portable and relative: {value!r}")
    return value


def _read_file(root: Path, relative: str, limit: int) -> bytes:
    path = root
    for part in PurePosixPath(relative).parts:
        path /= part
        if path.is_symlink() or path.is_junction():
            raise FigureExportError(f"Linked analysis files cannot be exported: {relative}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise FigureExportError(f"Analysis output is not a regular file: {relative}")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise FigureExportError(f"{relative} exceeds the export limit of {limit // 1024**2} MiB.")
    return data


def _output(row: dict) -> FigureOutput:
    relative = _relative_path(row.get("relativePath"))
    size, digest = row.get("bytes"), row.get("sha256")
    if (
        type(size) is not int
        or size < 0
        or not isinstance(digest, str)
        or not _DIGEST.fullmatch(digest)
    ):
        raise FigureExportError(f"Missing or invalid recorded size/SHA-256 for {relative}.")
    return FigureOutput(relative, size, digest)


def _check_bytes(data: bytes, output: FigureOutput) -> None:
    if len(data) != output.byte_count or _sha256(data) != output.sha256:
        raise FigureExportError(
            f"{output.relative_path} differs from the saved job. Reload or rerun the job."
        )


def load_figure_source(job_dir: Path) -> FigureSource:
    """Bind a selection to one completed job's saved manifest and parameters."""
    requested = Path(job_dir).absolute()
    if requested.is_symlink() or requested.is_junction():
        raise FigureExportError("Select a direct analysis job directory, not a linked job.")
    root = requested.resolve(strict=True)
    info = root.stat()
    manifest_bytes = _read_file(root, "job_manifest.json", MAX_METADATA_BYTES)
    manifest = _json_object(manifest_bytes, "job_manifest.json")
    if manifest.get("schemaId") != "capture.analysis_job/1":
        raise FigureExportError("This analysis job schema is not supported for figure export.")
    if manifest.get("jobId") != root.name:
        raise FigureExportError("The saved job ID does not match its directory. Reload the job.")
    if manifest.get("status") not in ("completed", "completed_with_warnings"):
        raise FigureExportError("Select a completed analysis job to export figures.")
    if not isinstance(manifest.get("sessionId"), str) or not manifest["sessionId"]:
        raise FigureExportError("The saved job has no session identity.")
    rows = manifest.get("outputs")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise FigureExportError("The saved job has an invalid output inventory.")
    seen: set[str] = set()
    figures = []
    params_output = None
    for row in rows:
        relative = _relative_path(row.get("relativePath"))
        if relative.casefold() in seen:
            raise FigureExportError(f"The job records an ambiguous output path: {relative}")
        seen.add(relative.casefold())
        if relative == "params.json":
            params_output = _output(row)
        elif row.get("kind") == "figure" and relative.lower().endswith(".png"):
            output = _output(row)
            if output.byte_count > MAX_FIGURE_BYTES:
                raise FigureExportError(f"{relative} exceeds the 64 MiB figure export limit.")
            figures.append(output)
    if params_output is None:
        raise FigureExportError("The job does not record its params.json output.")
    params_bytes = _read_file(root, "params.json", MAX_METADATA_BYTES)
    _check_bytes(params_bytes, params_output)
    params = _json_object(params_bytes, "params.json")
    canonical = json.dumps(
        params, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    if manifest.get("paramsDigest") != _sha256(canonical):
        raise FigureExportError("The saved parameters do not match the job's paramsDigest.")
    return FigureSource(
        root,
        (info.st_dev, info.st_ino),
        manifest_bytes,
        params_bytes,
        tuple(sorted(figures, key=lambda item: item.relative_path)),
    )


def _check_source(source: FigureSource) -> None:
    info = source.job_dir.stat()
    if (
        source.job_dir.is_symlink()
        or source.job_dir.is_junction()
        or (info.st_dev, info.st_ino) != source.directory_identity
    ):
        raise FigureExportError("The loaded job directory changed. Reload the job.")
    for relative, original in (
        ("job_manifest.json", source.manifest_bytes),
        ("params.json", source.params_bytes),
    ):
        if _read_file(source.job_dir, relative, MAX_METADATA_BYTES) != original:
            raise FigureExportError(f"{relative} changed after loading. Reload the job.")


def read_figure(source: FigureSource, relative_path: str) -> bytes:
    """Read and decode the exact PNG named in the original job inventory."""
    output = next((item for item in source.figures if item.relative_path == relative_path), None)
    if output is None:
        raise FigureExportError(f"Figure is not recorded in this job: {relative_path}")
    _check_source(source)
    data = _read_file(source.job_dir, output.relative_path, MAX_FIGURE_BYTES)
    _check_bytes(data, output)
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or QImage.fromData(data, "PNG").isNull():
        raise FigureExportError(f"{relative_path} is not a readable PNG image.")
    return data


def _destination(source: FigureSource, destination: Path, replace_existing: bool) -> Path:
    requested = Path(destination).absolute()
    path = requested.parent.resolve(strict=True) / requested.name
    protected = source.job_dir
    if protected.parent.name == "jobs" and protected.parent.parent.name == "processing":
        protected = protected.parent.parent.parent
    else:
        protected = next((p for p in source.job_dir.parents if p.suffix == ".mmsession"), protected)
    if path.is_relative_to(protected):
        raise FigureExportError("Choose an export destination outside the source session/job.")
    if path.suffix.lower() != ".zip":
        raise FigureExportError("Choose a filename ending in .zip.")
    if path.is_symlink() or path.is_junction() or (path.exists() and not path.is_file()):
        raise FigureExportError(
            "The destination must be a regular ZIP file, not a link or directory."
        )
    if path.exists() and not replace_existing:
        raise FileExistsError(
            f"{path.name} already exists. Choose another name or confirm replacement."
        )
    return path


def export_figure_bundle(
    source: FigureSource,
    selected_paths: Iterable[str],
    destination: Path,
    *,
    replace_existing: bool = False,
    cancel: Callable[[], bool] | None = None,
) -> FigureBundleResult:
    """Validate, stage and publish a ZIP; source files are never opened for writing."""
    selected = tuple(selected_paths)
    inventory = {item.relative_path: item for item in source.figures}
    if (
        not selected
        or len(set(selected)) != len(selected)
        or any(p not in inventory for p in selected)
    ):
        raise FigureExportError("Select one or more distinct figures from the loaded job.")
    if sum(inventory[p].byte_count for p in selected) > MAX_SELECTION_BYTES:
        raise FigureExportError("The selection exceeds 512 MiB. Export a smaller selection.")
    path = _destination(source, destination, replace_existing)

    def checkpoint() -> None:
        if cancel is not None and cancel():
            raise InterruptedError("Figure export cancelled.")

    checkpoint()
    _check_source(source)
    fd, temporary = tempfile.mkstemp(prefix=".capture-figures-", suffix=".tmp", dir=path.parent)
    staged = Path(temporary)
    try:
        figure_records = []
        source_records = []
        identities = {}
        with os.fdopen(fd, "w+b") as handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_STORED) as archive:
                for relative in selected:
                    checkpoint()
                    data = read_figure(source, relative)
                    info = (source.job_dir / relative).stat()
                    identities[relative] = (
                        info.st_dev,
                        info.st_ino,
                        info.st_size,
                        info.st_mtime_ns,
                    )
                    archive.writestr(relative, data)
                    figure_records.append(
                        {
                            "path": relative,
                            "sourceRelativePath": relative,
                            "bytes": len(data),
                            "sha256": _sha256(data),
                        }
                    )
                for relative, data in (
                    ("job_manifest.json", source.manifest_bytes),
                    ("params.json", source.params_bytes),
                ):
                    member = f"source/{relative}"
                    archive.writestr(member, data)
                    source_records.append(
                        {
                            "path": member,
                            "sourceRelativePath": relative,
                            "bytes": len(data),
                            "sha256": _sha256(data),
                        }
                    )
                original = source.manifest
                manifest = {
                    "schemaId": SCHEMA_ID,
                    "createdUtc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "jobId": original["jobId"],
                    "sessionId": original["sessionId"],
                    "paramsDigest": original["paramsDigest"],
                    "sourceFiles": source_records,
                    "figures": figure_records,
                }
                archive.writestr(
                    "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n"
                )
            handle.flush()
            os.fsync(handle.fileno())
        _check_source(source)
        for relative, identity in identities.items():
            info = (source.job_dir / relative).stat()
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != identity:
                raise FigureExportError(f"{relative} changed during export. Reload the job.")
        checkpoint()
        # A same-directory staging file keeps failed writes away from prior exports.
        if replace_existing:
            os.replace(staged, path)
        elif os.name == "nt":
            os.rename(staged, path)  # Windows rename refuses an existing destination.
        else:
            os.link(staged, path)  # POSIX publication must also refuse a raced-in file.
        return FigureBundleResult(path, len(selected))
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            logging.getLogger(__name__).warning(
                "Could not remove owned export staging file %s", staged
            )
