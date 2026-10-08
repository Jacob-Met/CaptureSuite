# SPDX-License-Identifier: GPL-3.0-only
"""Bounded, read-only previews of retained feature tables."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .analysis_job_comparison import (
    JobParameterError,
    JobParameters,
    _decode,
    _read_regular,
    load_job_parameters,
    revalidate_job_parameters,
)

MAX_ROWS = 200
MAX_COLUMNS = 128
MAX_TABLES = 512
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_DECODED_BYTES = 32 * 1024 * 1024
MAX_PREVIEW_BYTES = 8 * 1024 * 1024
MAX_CELL_CHARS = 4096
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_METADATA_ITEMS = 100_000
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class FeaturePreviewError(ValueError):
    """A complete preview cannot be produced from the retained inputs."""


@dataclass(frozen=True)
class FeatureColumn:
    name: str
    arrow_type: str
    units: str
    calibrated: bool
    description: str = ""


@dataclass(frozen=True)
class FeatureCatalog:
    source: JobParameters
    tables: tuple[str, ...]


@dataclass(frozen=True)
class FeaturePreview:
    job_id: str
    session_id: str
    relative_path: str
    table_sha256: str
    manifest_sha256: str
    total_rows: int
    columns: tuple[FeatureColumn, ...]
    rows: tuple[tuple[object, ...], ...]


def format_feature_value(value: object) -> str:
    """Keep integers exact and distinguish missing, nonfinite and literal text."""
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return repr(value)
    raise FeaturePreviewError("The table contains an unsupported scalar value.")


def _cancelled(event: threading.Event | None) -> None:
    if event is not None and event.is_set():
        raise FeaturePreviewError("Preview cancelled.")


def _parts(relative: str) -> list[str]:
    if not isinstance(relative, str):
        raise FeaturePreviewError("A retained output path must be a string.")
    parts = relative.split("/")
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or "\x00" in relative
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise FeaturePreviewError(f"Unsafe retained output path: {relative!r}.")
    return parts


def _entry(manifest: dict[str, Any], relative: str, kind: str) -> dict[str, Any]:
    entries = [row for row in manifest["outputs"] if row.get("relativePath") == relative]
    if len(entries) != 1 or entries[0].get("kind") != kind:
        raise FeaturePreviewError(f"The job must list exactly one {kind} output at {relative}.")
    row = entries[0]
    if (
        type(row.get("bytes")) is not int
        or row["bytes"] < 0
        or not isinstance(row.get("sha256"), str)
        or not _HASH.fullmatch(row["sha256"])
    ):
        raise FeaturePreviewError(f"The recorded identity is invalid for {relative}.")
    return row


def load_feature_catalog(
    job_dir: Path, *, cancel_event: threading.Event | None = None
) -> FeatureCatalog:
    """Reuse the existing completed-job and parameter identity admission."""
    try:
        _cancelled(cancel_event)
        source = load_job_parameters(job_dir)
        manifest = source.manifest
        tables: list[str] = []
        for entry in manifest["outputs"]:
            if entry.get("kind") != "feature_parquet":
                continue
            relative = entry.get("relativePath")
            _parts(relative)
            _entry(manifest, relative, "feature_parquet")
            tables.append(relative)
            if len(tables) > MAX_TABLES:
                raise FeaturePreviewError("More than 512 feature tables; use the retained outputs.")
        if len(tables) != len(set(tables)):
            raise FeaturePreviewError("The job repeats a feature table path.")
        _cancelled(cancel_event)
        return FeatureCatalog(source, tuple(tables))
    except (JobParameterError, OSError) as exc:
        raise FeaturePreviewError(str(exc)) from exc


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _path(
    source: JobParameters, relative: str
) -> tuple[Path, tuple[tuple[Path, tuple[int, int]], ...]]:
    parts = _parts(relative)
    path = source.job_dir
    parents: list[tuple[Path, tuple[int, int]]] = []
    for part in parts[:-1]:
        path /= part
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or path.is_junction():
            raise FeaturePreviewError("Retained output directories must not be linked.")
        parents.append((path, (info.st_dev, info.st_ino)))
    path /= parts[-1]
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_junction() or info.st_nlink != 1:
        raise FeaturePreviewError("Retained outputs must be regular files without links.")
    return path, tuple(parents)


def _parents_unchanged(parents: tuple[tuple[Path, tuple[int, int]], ...]) -> None:
    for path, identity in parents:
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or path.is_junction()
            or (info.st_dev, info.st_ino) != identity
        ):
            raise FeaturePreviewError("A retained output directory changed; reload this job.")


def _identity(data: bytes, entry: dict[str, Any], relative: str) -> None:
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise FeaturePreviewError(f"{relative} differs from its recorded size or SHA-256.")


@contextmanager
def _table_stream(source: JobParameters, relative: str):
    """Stream Parquet using portable path/handle identity checks, without writes."""
    path, parents = _path(source, relative)
    before = path.lstat()
    if before.st_size > MAX_FILE_BYTES:
        raise FeaturePreviewError("This table exceeds the 256 MiB preview file limit.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        # Windows path and handle ctime have different meanings. Compare complete
        # metadata within each family, and only file IDs across API families.
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise FeaturePreviewError("The retained table changed while being opened.")
        yield stream
        if _signature(opened) != _signature(os.fstat(stream.fileno())):
            raise FeaturePreviewError("The retained table changed during preview; reload this job.")
    current = path.lstat()
    if not stat.S_ISREG(current.st_mode) or _signature(before) != _signature(current):
        raise FeaturePreviewError(
            "The retained table was replaced during preview; reload this job."
        )
    _parents_unchanged(parents)


def _hash_table(stream: BinaryIO, event: threading.Event | None) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    while True:
        _cancelled(event)
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        count += len(chunk)
        if count > MAX_FILE_BYTES:
            raise FeaturePreviewError("This table exceeds the 256 MiB preview file limit.")
        digest.update(chunk)
    stream.seek(0)
    return count, digest.hexdigest()


def _column_metadata(document: dict[str, Any], relative: str) -> dict[str, Any]:
    tables = document.get("tables")
    if (
        document.get("schemaId") != "capture.analysis_feature_schema/1"
        or not isinstance(tables, dict)
        or not isinstance(tables.get(relative), dict)
    ):
        raise FeaturePreviewError("The feature schema does not identify the selected table.")
    metadata = tables[relative]
    if (
        type(metadata.get("featureSchemaVersion")) is not int
        or metadata["featureSchemaVersion"] < 1
        or not isinstance(metadata.get("columns"), list)
    ):
        raise FeaturePreviewError("The feature table has invalid version or column metadata.")
    return metadata


def _read_preview(
    catalog: FeatureCatalog, relative: str, event: threading.Event | None
) -> FeaturePreview:
    import pyarrow as pa
    import pyarrow.parquet as parquet

    source = catalog.source
    if relative not in catalog.tables:
        raise FeaturePreviewError("Choose a feature table listed by the loaded job.")
    revalidate_job_parameters(source)
    manifest = source.manifest
    table_entry = _entry(manifest, relative, "feature_parquet")
    schema_entry = _entry(manifest, "features/_schema.json", "feature_schema")
    schema_path, schema_parents = _path(source, "features/_schema.json")
    schema_bytes = _read_regular(schema_path)
    _identity(schema_bytes, schema_entry, "features/_schema.json")
    document = _decode(schema_bytes, "features/_schema.json")
    metadata = _column_metadata(document, relative)
    _cancelled(event)

    with _table_stream(source, relative) as stream:
        size, digest = _hash_table(stream, event)
        if size != table_entry["bytes"] or digest != table_entry["sha256"]:
            raise FeaturePreviewError(
                "The feature table differs from its recorded size or SHA-256."
            )
        reader = parquet.ParquetFile(
            stream,
            pre_buffer=False,
            thrift_string_size_limit=MAX_METADATA_BYTES,
            thrift_container_size_limit=MAX_METADATA_ITEMS,
        )
        schema = reader.schema_arrow
        names = schema.names
        if (
            not names
            or len(names) > MAX_COLUMNS
            or any(not name for name in names)
            or len(names) != len(set(names))
        ):
            raise FeaturePreviewError("Preview requires 1–128 columns with unique nonempty names.")
        for field in schema:
            kind = field.type
            if not (
                pa.types.is_boolean(kind)
                or pa.types.is_integer(kind)
                or pa.types.is_floating(kind)
                or pa.types.is_string(kind)
                or pa.types.is_large_string(kind)
                or pa.types.is_null(kind)
            ):
                raise FeaturePreviewError(
                    f"Column {field.name!r} has unsupported preview type {kind}; "
                    "open the retained output in an analysis tool."
                )
        by_name: dict[str, dict[str, Any]] = {}
        for row in metadata["columns"]:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("name"), str)
                or row["name"] in by_name
                or not isinstance(row.get("units"), str)
                or type(row.get("calibrated")) is not bool
                or not isinstance(row.get("description", ""), str)
            ):
                raise FeaturePreviewError(
                    "Feature column metadata is missing, ambiguous or invalid."
                )
            by_name[row["name"]] = row
        if set(by_name) != set(names):
            raise FeaturePreviewError(
                "Feature metadata column names disagree with the Parquet table."
            )
        total_rows = reader.metadata.num_rows
        if total_rows < 0:
            raise FeaturePreviewError("The retained table has an invalid row count.")
        if "rows" in metadata and (
            type(metadata["rows"]) is not int or metadata["rows"] != total_rows
        ):
            raise FeaturePreviewError(
                "Feature metadata row count disagrees with the Parquet table."
            )

        groups: list[int] = []
        available_rows = 0
        decoded_bytes = 0
        for index in range(reader.num_row_groups):
            if available_rows >= MAX_ROWS:
                break
            _cancelled(event)
            group = reader.metadata.row_group(index)
            if group.num_rows < 0 or group.num_columns != len(names):
                raise FeaturePreviewError("The retained row group has invalid dimensions.")
            chunk_bytes = 0
            for column in range(group.num_columns):
                chunk = group.column(column)
                if chunk.file_path not in (None, ""):
                    raise FeaturePreviewError("External Parquet column files are not supported.")
                if chunk.total_uncompressed_size < 0:
                    raise FeaturePreviewError("The retained column has an invalid decoded size.")
                chunk_bytes += chunk.total_uncompressed_size
            if group.total_byte_size < 0:
                raise FeaturePreviewError("The retained row group has an invalid decoded size.")
            decoded_bytes += max(chunk_bytes, group.total_byte_size)
            if decoded_bytes > MAX_DECODED_BYTES:
                raise FeaturePreviewError(
                    "The first preview row groups exceed 32 MiB uncompressed; "
                    "open the retained output in an analysis tool."
                )
            groups.append(index)
            available_rows += group.num_rows

        rows: list[tuple[object, ...]] = []
        preview_bytes = 0
        display_bytes = 0
        # Dictionary values can expand far beyond encoded row-group sizes.
        # Admit one row before asking Arrow to materialize the next one.
        for batch in reader.iter_batches(batch_size=1, row_groups=groups, use_threads=False):
            _cancelled(event)
            batch = batch.slice(0, MAX_ROWS - len(rows))
            preview_bytes += batch.nbytes
            if preview_bytes > MAX_PREVIEW_BYTES:
                raise FeaturePreviewError("Preview values exceed the 8 MiB decoded result limit.")
            # Column indices keep dots and other punctuation literal. Arrow
            # scalars preserve nullable int64/uint64 without float coercion.
            values = [batch.column(index).to_pylist() for index in range(batch.num_columns)]
            for row in zip(*values, strict=True):
                for value in row:
                    if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
                        raise FeaturePreviewError(
                            "A text cell exceeds 4,096 characters; open the retained output "
                            "in an analysis tool."
                        )
                    display_bytes += len(format_feature_value(value).encode("utf-8"))
                    if display_bytes > MAX_PREVIEW_BYTES:
                        raise FeaturePreviewError("Preview display exceeds the 8 MiB result limit.")
                rows.append(tuple(row))
            if len(rows) >= MAX_ROWS:
                break
        if len(rows) != min(total_rows, MAX_ROWS):
            raise FeaturePreviewError(
                "The retained table did not supply its declared preview rows."
            )
        _cancelled(event)

    _parents_unchanged(schema_parents)
    current_schema_path, _ = _path(source, "features/_schema.json")
    if _read_regular(current_schema_path) != schema_bytes:
        raise FeaturePreviewError("Feature metadata changed during preview; reload this job.")
    revalidate_job_parameters(source)
    _cancelled(event)
    columns = tuple(
        FeatureColumn(
            field.name, str(field.type), by_name[field.name]["units"],
            by_name[field.name]["calibrated"], by_name[field.name].get("description", "")
        )
        for field in schema
    )
    return FeaturePreview(
        source.job_id, source.session_id, relative, digest, source.manifest_sha256,
        total_rows, columns, tuple(rows)
    )


def load_feature_preview(
    catalog: FeatureCatalog,
    relative_path: str,
    *,
    cancel_event: threading.Event | None = None,
) -> FeaturePreview:
    """Verify one retained table and read its bounded first rows off the UI thread."""
    try:
        _cancelled(cancel_event)
        return _read_preview(catalog, relative_path, cancel_event)
    except FeaturePreviewError:
        raise
    except ImportError as exc:
        raise FeaturePreviewError(
            "Install the project's Analysis dependencies to preview tables."
        ) from exc
    except (
        JobParameterError, OSError, ValueError, TypeError, OverflowError, NotImplementedError
    ) as exc:
        raise FeaturePreviewError(f"Cannot preview the retained table: {exc}") from exc
