# SPDX-License-Identifier: GPL-3.0-only
"""Read and compare retained job parameters without changing source artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_PARAMETER_NODES = 10_000
MAX_PARAMETER_DEPTH = 48
MAX_DIFFERENCES = 5_000
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MISSING = object()


class JobParameterError(ValueError):
    """Saved settings cannot be read or compared with their stated provenance."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JobParameterError(f"Duplicate JSON key: {key!r}.")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise JobParameterError(f"Non-finite JSON value: {value}.")


def _number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise JobParameterError("JSON number is outside the finite supported range.")
    return result


def _decode(data: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise JobParameterError(f"Cannot read {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise JobParameterError(f"{name} must contain a JSON object.")
    return value


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_junction():
        raise JobParameterError("Choose a real saved job directory, not a linked directory.")
    return info.st_dev, info.st_ino


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_regular(path: Path) -> bytes:
    """Bound allocation and refuse links/devices before consuming any content."""
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise JobParameterError(
                f"{path.name} must be a regular file, not a symbolic link or device."
            )
        if before.st_size > MAX_JSON_BYTES:
            raise JobParameterError(f"{path.name} exceeds the 4 MiB reading limit.")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _file_identity(before) != _file_identity(opened):
                raise JobParameterError(f"{path.name} changed while being opened; reload this job.")
            data = stream.read(MAX_JSON_BYTES + 1)
            after = os.fstat(stream.fileno())
        if len(data) > MAX_JSON_BYTES or len(data) != before.st_size:
            raise JobParameterError(f"{path.name} changed while being read; reload this job.")
        if _file_identity(before) != _file_identity(after):
            raise JobParameterError(f"{path.name} changed while being read; reload this job.")
        return data
    except OSError as exc:
        raise JobParameterError(f"Cannot read {path.name}: {exc}") from exc


def _check_parameter_tree(value: dict[str, Any]) -> None:
    pending: list[tuple[Any, int]] = [(value, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_PARAMETER_NODES or depth > MAX_PARAMETER_DEPTH:
            raise JobParameterError("Saved parameters exceed the supported tree size or depth.")
        if isinstance(node, dict):
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, list):
            pending.extend((child, depth + 1) for child in node)
        elif isinstance(node, float) and not math.isfinite(node):
            raise JobParameterError("Saved parameters contain a non-finite number.")


def read_job_manifest(job_dir: Path) -> dict[str, Any]:
    """Bound the legacy inspector read, including valid failed-job metadata."""
    try:
        requested = Path(job_dir).absolute()
        _directory_identity(requested)
        root = requested.resolve(strict=True)
        identity = _directory_identity(root)
        document = _decode(_read_regular(root / "job_manifest.json"), "job_manifest.json")
        if _directory_identity(root) != identity:
            raise JobParameterError("The saved job directory changed while being read.")
        if (
            document.get("schemaId") != "capture.analysis_job/1"
            or document.get("jobId") != root.name
        ):
            raise JobParameterError("The manifest does not identify this saved analysis job.")
        return document
    except OSError as exc:
        raise JobParameterError(f"Cannot read the saved job directory: {exc}") from exc


@dataclass(frozen=True)
class JobParameters:
    """Original immutable input bytes; callers receive fresh decoded views."""

    job_dir: Path
    directory_identity: tuple[int, int]
    manifest_bytes: bytes
    params_bytes: bytes

    @property
    def manifest(self) -> dict[str, Any]:
        return _decode(self.manifest_bytes, "job_manifest.json")

    @property
    def params(self) -> dict[str, Any]:
        return _decode(self.params_bytes, "params.json")

    @property
    def job_id(self) -> str:
        return self.manifest["jobId"]

    @property
    def session_id(self) -> str:
        return self.manifest["sessionId"]

    @property
    def params_sha256(self) -> str:
        return hashlib.sha256(self.params_bytes).hexdigest()

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest_bytes).hexdigest()


def revalidate_job_parameters(source: JobParameters) -> None:
    """Require the exact loaded directory and metadata bytes at an action boundary."""
    try:
        if _directory_identity(source.job_dir) != source.directory_identity:
            raise JobParameterError("The saved job directory was replaced; reload this job.")
        if (
            _read_regular(source.job_dir / "job_manifest.json") != source.manifest_bytes
            or _read_regular(source.job_dir / "params.json") != source.params_bytes
        ):
            raise JobParameterError("Saved job metadata changed; reload before comparing.")
        if _directory_identity(source.job_dir) != source.directory_identity:
            raise JobParameterError("The saved job directory changed while being read.")
    except OSError as exc:
        raise JobParameterError(f"Cannot read the saved job directory: {exc}") from exc


def load_job_parameters(job_dir: Path) -> JobParameters:
    """Read one completed job and verify its original parameter entry and digest."""
    try:
        requested = Path(job_dir).absolute()
        _directory_identity(requested)
        root = requested.resolve(strict=True)
        identity = _directory_identity(root)
        manifest_bytes = _read_regular(root / "job_manifest.json")
        params_bytes = _read_regular(root / "params.json")
        manifest = _decode(manifest_bytes, "job_manifest.json")
        params = _decode(params_bytes, "params.json")
        _check_parameter_tree(params)
        if manifest.get("schemaId") != "capture.analysis_job/1":
            raise JobParameterError("This is not a supported capture.analysis_job/1 manifest.")
        if manifest.get("jobId") != root.name:
            raise JobParameterError("The recorded job ID does not match the saved directory.")
        if manifest.get("status") not in ("completed", "completed_with_warnings"):
            raise JobParameterError("Only completed saved jobs can be inspected and compared.")
        if not isinstance(manifest.get("sessionId"), str) or not manifest["sessionId"]:
            raise JobParameterError("The saved job has no recorded session identity.")
        outputs = manifest.get("outputs")
        if not isinstance(outputs, list) or any(not isinstance(row, dict) for row in outputs):
            raise JobParameterError("The saved job output inventory is invalid.")
        entries = [row for row in outputs if row.get("relativePath") == "params.json"]
        if len(entries) != 1 or entries[0].get("kind") != "params":
            raise JobParameterError("The job must record exactly one params.json parameter output.")
        entry = entries[0]
        if type(entry.get("bytes")) is not int or entry["bytes"] != len(params_bytes):
            raise JobParameterError("params.json does not match its recorded byte count.")
        file_digest = entry.get("sha256")
        if (
            not isinstance(file_digest, str)
            or not _DIGEST.fullmatch(file_digest)
            or hashlib.sha256(params_bytes).hexdigest() != file_digest
        ):
            raise JobParameterError("params.json does not match its recorded SHA-256.")
        digest = manifest.get("paramsDigest")
        canonical = json.dumps(
            params, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
        if (
            not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
            or hashlib.sha256(canonical).hexdigest() != digest
        ):
            raise JobParameterError("Saved parameters do not match the recorded paramsDigest.")
        result = JobParameters(root, identity, manifest_bytes, params_bytes)
        revalidate_job_parameters(result)
        return result
    except OSError as exc:
        raise JobParameterError(f"Cannot read the saved job directory: {exc}") from exc


@dataclass(frozen=True)
class ParameterDifference:
    """A JSON Pointer and full JSON values; None represents an absent field."""

    pointer: str
    change: str
    other_json: str | None
    loaded_json: str | None


def _value_json(value: Any) -> str | None:
    if value is _MISSING:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _pointer(path: str, key: str | int) -> str:
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"


def _diff(other: dict[str, Any], loaded: dict[str, Any]) -> tuple[ParameterDifference, ...]:
    rows: list[ParameterDifference] = []

    def visit(left: Any, right: Any, path: str) -> None:
        if type(left) is type(right) and isinstance(left, dict):
            for key in sorted(left.keys() | right.keys()):
                visit(left.get(key, _MISSING), right.get(key, _MISSING), _pointer(path, key))
            return
        if type(left) is type(right) and isinstance(left, list):
            for index in range(max(len(left), len(right))):
                visit(
                    left[index] if index < len(left) else _MISSING,
                    right[index] if index < len(right) else _MISSING,
                    _pointer(path, index),
                )
            return
        before, after = _value_json(left), _value_json(right)
        if before == after and type(left) is type(right):
            return
        change = (
            "only_loaded" if left is _MISSING else "only_other" if right is _MISSING else "changed"
        )
        rows.append(ParameterDifference(path, change, before, after))
        if len(rows) > MAX_DIFFERENCES:
            raise JobParameterError(
                "More than 5,000 parameter differences; comparison is not shown."
            )

    visit(other, loaded, "")
    return tuple(rows)


def compare_job_parameters(
    other: JobParameters,
    loaded: JobParameters,
) -> tuple[ParameterDifference, ...]:
    """Compare settings from the same physical jobs directory and recorded session."""
    if other.job_dir.parent != loaded.job_dir.parent or other.session_id != loaded.session_id:
        raise JobParameterError(
            "Choose another saved job from the same session and jobs directory."
        )
    revalidate_job_parameters(other)
    revalidate_job_parameters(loaded)
    result = _diff(other.params, loaded.params)
    revalidate_job_parameters(other)
    revalidate_job_parameters(loaded)
    return result
