# SPDX-License-Identifier: GPL-3.0-only
"""Export an ordered column selection from an immutable retained feature job."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as parquet

_METADATA_LIMIT = 16 * 1024**2
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_FORMATS = {"csv", "parquet", "both"}
_COMPLETED = {"completed", "completed_with_warnings"}


class FeatureTableExportError(ValueError):
    """The selected retained table cannot be exported under this contract."""


def _fail(message: str) -> None:
    raise FeatureTableExportError(message)


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _relative_parts(relative: str) -> list[str]:
    if not isinstance(relative, str):
        _fail("table and output paths in the job manifest must be strings")
    parts = relative.split("/")
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or "\x00" in relative
        or PureWindowsPath(relative).drive
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _fail(f"unsafe retained-job relative path: {relative!r}")
    return parts


def _job_file(job: Path, relative: str) -> Path:
    path = job
    for part in _relative_parts(relative):
        path = path / part
        if _linked(path):
            _fail(f"linked retained-job path is not supported: {relative}")
    if not path.is_file():
        _fail(f"missing retained-job file: {relative}")
    if path.stat().st_nlink > 1:
        _fail(f"hard-linked retained-job file is not supported: {relative}")
    return path


def _identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            _fail(f"duplicate JSON property: {name}")
        result[name] = value
    return result


def _invalid_constant(value: str) -> None:
    _fail(f"non-JSON numeric constant: {value}")


def _read_document(path: Path) -> tuple[bytes, dict[str, Any]]:
    with path.open("rb") as stream:
        data = stream.read(_METADATA_LIMIT + 1)
    if len(data) > _METADATA_LIMIT:
        _fail(f"retained-job JSON exceeds {_METADATA_LIMIT} bytes: {path.name}")
    try:
        document = json.loads(
            data, object_pairs_hook=_object_pairs, parse_constant=_invalid_constant
        )
    except (ValueError, UnicodeError) as exc:
        raise FeatureTableExportError(f"invalid retained-job JSON: {path.name}: {exc}") from exc
    if not isinstance(document, dict):
        _fail(f"retained-job JSON must be an object: {path.name}")
    return data, document


def _declared_output(
    manifest: dict[str, Any], relative: str, kind: str, actual: dict[str, Any]
) -> None:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        _fail("job manifest has no output inventory")
    entries = [
        entry
        for entry in outputs
        if isinstance(entry, dict) and entry.get("relativePath") == relative
    ]
    if len(entries) != 1 or entries[0].get("kind") != kind:
        _fail(f"job must declare exactly one {kind} output at {relative}")
    entry = entries[0]
    size = entry.get("bytes")
    digest = entry.get("sha256")
    if (
        type(size) is not int
        or size < 0
        or not isinstance(digest, str)
        or not _HASH.fullmatch(digest)
        or size != actual["bytes"]
        or digest.lower() != actual["sha256"]
    ):
        _fail(f"retained-job output identity mismatch: {relative}")


def _job_root(job_dir: Path) -> tuple[Path, Path]:
    given = Path(job_dir).expanduser().absolute()
    if given.parent.name != "jobs" or given.parent.parent.name != "processing":
        _fail("job must be a retained PACKAGE/processing/jobs/JOB_ID directory")
    package = given.parent.parent.parent.resolve(strict=True)
    job = package
    for part in ("processing", "jobs", given.name):
        job = job / part
        if _linked(job) or not job.is_dir():
            _fail(f"job directory must exist without symlinks or junctions: {job}")
    return package, job


def _destination(output_dir: Path, package: Path) -> Path:
    given = Path(output_dir).expanduser().absolute()
    parent = given.parent.resolve(strict=True)
    if not parent.is_dir():
        _fail("export destination parent must be an existing directory")
    output = parent / given.name
    if output == package or package in output.parents:
        _fail("export destination must be outside the entire session package")
    if output.exists() or _linked(output):
        _fail(f"export destination already exists: {output}")
    return output


def _csv_supported(data_type: pa.DataType) -> bool:
    return (
        pa.types.is_boolean(data_type)
        or pa.types.is_integer(data_type)
        or pa.types.is_float32(data_type)
        or pa.types.is_float64(data_type)
        or pa.types.is_string(data_type)
        or pa.types.is_large_string(data_type)
    )


def _json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def list_feature_tables(job_dir: Path) -> dict[str, Any]:
    """Describe the saved job's table inventory without decoding its payloads.

    The feature metadata is checked against the job's recorded hash. Export
    performs the separate payload checks before creating a destination.
    """
    _, job = _job_root(Path(job_dir))
    _, manifest = _read_document(_job_file(job, "job_manifest.json"))
    if (
        manifest.get("schemaId") != "capture.analysis_job/1"
        or manifest.get("jobId") != job.name
        or manifest.get("status") not in _COMPLETED
    ):
        _fail("select a completed capture.analysis_job/1 with the retained directory's jobId")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        _fail("job manifest has no output inventory")
    if not any(
        isinstance(output, dict) and output.get("kind") == "feature_parquet" for output in outputs
    ):
        return {"jobId": manifest["jobId"], "jobStatus": manifest["status"], "tables": []}
    schema_data, schema_document = _read_document(_job_file(job, "features/_schema.json"))
    _declared_output(
        manifest,
        "features/_schema.json",
        "feature_schema",
        {"bytes": len(schema_data), "sha256": hashlib.sha256(schema_data).hexdigest()},
    )
    tables = schema_document.get("tables")
    if schema_document.get("schemaId") != "capture.analysis_feature_schema/1" or not isinstance(
        tables, dict
    ):
        _fail("saved job has no valid feature table inventory")
    summaries = []
    seen = set()
    for output in manifest["outputs"]:
        if not isinstance(output, dict) or output.get("kind") != "feature_parquet":
            continue
        relative = output.get("relativePath")
        _relative_parts(relative)
        if relative in seen:
            _fail(f"job lists a feature table more than once: {relative}")
        seen.add(relative)
        metadata = tables.get(relative)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("columns"), list):
            _fail(f"missing feature column metadata: {relative}")
        columns = metadata["columns"]
        if any(
            not isinstance(column, dict)
            or not isinstance(column.get("name"), str)
            or not isinstance(column.get("units"), str)
            for column in columns
        ):
            _fail(f"invalid feature column metadata: {relative}")
        summaries.append(
            {
                "relativePath": relative,
                "rows": metadata.get("rows"),
                "sourceId": metadata.get("sourceId"),
                "streamId": metadata.get("streamId"),
                "columns": columns,
            }
        )
    return {
        "jobId": manifest["jobId"],
        "jobStatus": manifest["status"],
        "tables": summaries,
    }


@dataclass
class SelectedFeatureTable:
    """A validated open saved table shared by single and collected exports."""

    package: Path
    job: Path
    reader: Any
    schema: pa.Schema
    schema_record: dict[str, Any]
    inputs: dict[str, dict[str, Any]]
    documents: dict[str, tuple[bytes, dict[str, Any]]]
    indices: list[int]
    rows: int
    selected: list[str]

    def revalidate(self) -> None:
        for relative, identity in self.inputs.items():
            if _identity(_job_file(self.job, relative)) != identity:
                _fail(f"retained-job input changed while exporting: {relative}")


@contextmanager
def open_feature_table(
    job_dir: Path,
    table: str,
    *,
    columns: Sequence[str] | None = None,
    output_format: str = "both",
):
    """Open one verified selection without creating or altering any files."""
    if output_format not in _FORMATS:
        _fail("output_format must be csv, parquet, or both")
    package, job = _job_root(Path(job_dir))
    selected_path = _job_file(job, table)
    relatives = ["job_manifest.json", "params.json", "features/_schema.json", table]
    paths = {relative: _job_file(job, relative) for relative in relatives}
    documents = {relative: _read_document(paths[relative]) for relative in relatives[:3]}
    inputs = {relative: _identity(path) for relative, path in paths.items()}
    manifest = documents["job_manifest.json"][1]
    if (
        manifest.get("schemaId") != "capture.analysis_job/1"
        or manifest.get("jobId") != job.name
        or manifest.get("status") not in _COMPLETED
        or not isinstance(manifest.get("sessionId"), str)
        or not manifest["sessionId"]
    ):
        _fail("select a completed capture.analysis_job/1 with the retained directory's jobId")
    for relative, kind in (
        (table, "feature_parquet"),
        ("params.json", "params"),
        ("features/_schema.json", "feature_schema"),
    ):
        _declared_output(manifest, relative, kind, inputs[relative])
    for relative, (data, _) in documents.items():
        if hashlib.sha256(data).hexdigest() != inputs[relative]["sha256"]:
            _fail(f"retained-job metadata changed while admitting export: {relative}")

    schema_document = documents["features/_schema.json"][1]
    tables = schema_document.get("tables")
    if (
        schema_document.get("schemaId") != "capture.analysis_feature_schema/1"
        or not isinstance(tables, dict)
        or not isinstance(tables.get(table), dict)
    ):
        _fail("selected table is absent from capture.analysis_feature_schema/1")
    table_metadata = tables[table]
    version = table_metadata.get("featureSchemaVersion")
    column_metadata = table_metadata.get("columns")
    if type(version) is not int or version < 1 or not isinstance(column_metadata, list):
        _fail("selected feature table has invalid version or column metadata")

    with selected_path.open("rb") as source_stream:
        reader = parquet.ParquetFile(source_stream)
        source_schema = reader.schema_arrow
        names = source_schema.names
        if not names or any(not name for name in names) or len(names) != len(set(names)):
            _fail("retained feature table must have nonempty, unambiguous column names")
        metadata_by_name: dict[str, dict[str, Any]] = {}
        for entry in column_metadata:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("name"), str)
                or entry["name"] in metadata_by_name
                or not isinstance(entry.get("units"), str)
                or type(entry.get("calibrated")) is not bool
            ):
                _fail("feature column metadata must have unique names, units, and calibrated flags")
            metadata_by_name[entry["name"]] = entry
        if set(metadata_by_name) != set(names):
            _fail("feature schema column names do not match the retained Parquet table")
        if isinstance(columns, (str, bytes)):
            _fail("columns must be a sequence of exact names, not one string")
        selected = list(names if columns is None else columns)
        if (
            not selected
            or any(not isinstance(name, str) for name in selected)
            or len(set(selected)) != len(selected)
            or any(name not in names for name in selected)
        ):
            _fail("columns must be a nonempty, unique selection of exact retained column names")
        rows = reader.metadata.num_rows
        declared_rows = table_metadata.get("rows")
        if declared_rows is not None and (type(declared_rows) is not int or declared_rows != rows):
            _fail("feature schema row count does not match the retained Parquet table")
        # Pandas metadata describes the original frame/index, not this projection.
        # Its exact original bytes remain in sourceArrowSchemaBase64 below.
        metadata = {
            key: value for key, value in (source_schema.metadata or {}).items() if key != b"pandas"
        }
        schema = pa.schema([source_schema.field(name) for name in selected], metadata=metadata)
        if output_format in {"csv", "both"}:
            unsupported = [field.name for field in schema if not _csv_supported(field.type)]
            if unsupported:
                _fail(f"CSV does not support these column types; select Parquet: {unsupported!r}")
        indices = [names.index(name) for name in selected]
        schema_record = {
            "schemaId": "capture.feature_table_export_schema/1",
            "tableRelativePath": table,
            "arrowSchemaBase64": base64.b64encode(schema.serialize()).decode("ascii"),
            "sourceArrowSchemaBase64": base64.b64encode(source_schema.serialize()).decode("ascii"),
            "fields": [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in schema
            ],
            "tableMetadata": {
                **table_metadata,
                "columns": [metadata_by_name[name] for name in selected],
                "rows": rows,
            },
            "csv": {
                "encoding": "UTF-8",
                "delimiter": ",",
                "header": True,
                "newlinesInValues": True,
                "ignoreEmptyLines": False,
                "nullValues": [""],
                "stringsCanBeNull": True,
                "quotedStringsCanBeNull": False,
                "columnTypes": "arrowSchemaBase64",
                "floatNaNPayloadBitsPreserved": False,
            }
            if output_format in {"csv", "both"}
            else None,
        }
        yield SelectedFeatureTable(
            package,
            job,
            reader,
            schema,
            schema_record,
            inputs,
            documents,
            indices,
            rows,
            selected,
        )


def export_feature_table(
    job_dir: Path,
    table: str,
    output_dir: Path,
    *,
    columns: Sequence[str] | None = None,
    output_format: str = "both",
    batch_size: int = 8192,
) -> dict[str, Any]:
    """Export all rows, with literal columns in the caller's requested order.

    Admission failures create no destination. A write/read failure after admission
    retains the new directory with failure.json and without manifest.json. The
    original session and job are only read. No original packagePath is followed.
    """
    if output_format not in _FORMATS:
        _fail("output_format must be csv, parquet, or both")
    if type(batch_size) is not int or batch_size < 1:
        _fail("batch_size must be a positive integer")
    with open_feature_table(
        job_dir,
        table,
        columns=columns,
        output_format=output_format,
    ) as prepared:
        output = _destination(Path(output_dir), prepared.package)
        job, reader, schema = prepared.job, prepared.reader, prepared.schema
        schema_record, inputs = prepared.schema_record, prepared.inputs
        documents, indices = prepared.documents, prepared.indices
        rows, selected = prepared.rows, prepared.selected
        manifest = documents["job_manifest.json"][1]
        # Exclusive creation prevents overwriting another caller's result.
        output.mkdir()
        try:
            (output / "source").mkdir()
            copies = {
                "job_manifest.json": "source/job_manifest.json",
                "params.json": "source/params.json",
                "features/_schema.json": "source/features_schema.json",
            }
            for relative, copied in copies.items():
                (output / copied).write_bytes(documents[relative][0])
            (output / "_schema.json").write_bytes(_json_bytes(schema_record))
            written_rows = 0
            data_files: list[str] = []
            with ExitStack() as stack:
                parquet_writer = csv_writer = None
                if output_format in {"parquet", "both"}:
                    parquet_writer = stack.enter_context(
                        parquet.ParquetWriter(output / "table.parquet", schema)
                    )
                    data_files.append("table.parquet")
                if output_format in {"csv", "both"}:
                    csv_writer = stack.enter_context(
                        arrow_csv.CSVWriter(str(output / "table.csv"), schema)
                    )
                    data_files.append("table.csv")
                # Read complete batches then select by index: names containing
                # dots remain literal, rather than Parquet nested-field prefixes.
                for batch in reader.iter_batches(batch_size=batch_size):
                    projected = pa.RecordBatch.from_arrays(
                        [batch.column(index) for index in indices], schema=schema
                    )
                    if parquet_writer is not None:
                        parquet_writer.write_batch(projected)
                    if csv_writer is not None:
                        csv_writer.write_batch(projected)
                    written_rows += batch.num_rows
            if written_rows != rows:
                _fail("retained table row count changed while exporting")
            for relative, identity in inputs.items():
                if _identity(_job_file(job, relative)) != identity:
                    _fail(f"retained-job input changed while exporting: {relative}")
            exported = data_files + ["_schema.json", *copies.values()]
            result = {
                "schemaId": "capture.feature_table_export/1",
                "status": "completed",
                "createdUtc": datetime.now(UTC).isoformat(),
                "source": {
                    "jobId": manifest["jobId"],
                    "sessionId": manifest["sessionId"],
                    "jobStatus": manifest["status"],
                    "paramsDigest": manifest.get("paramsDigest"),
                    "tableRelativePath": table,
                    "inputs": [
                        {"relativePath": relative, **identity}
                        for relative, identity in inputs.items()
                    ],
                },
                "selection": {
                    "columns": selected,
                    "rows": written_rows,
                    "rowPolicy": "all-in-original-order",
                },
                "format": output_format,
                "outputs": [
                    {"relativePath": relative, **_identity(output / relative)}
                    for relative in exported
                ],
            }
            pending = output / "manifest.pending.json"
            with pending.open("xb") as stream:
                stream.write(_json_bytes(result))
            pending.rename(output / "manifest.json")
            return result
        except Exception as exc:
            (output / "manifest.json").unlink(missing_ok=True)
            failure = {
                "schemaId": "capture.feature_table_export/1",
                "status": "failed",
                "error": str(exc),
                "tableRelativePath": table,
                "selection": {"columns": selected},
            }
            try:
                (output / "failure.json").write_bytes(_json_bytes(failure))
            except OSError:
                pass
            exc.add_note(f"Incomplete export retained at {output}; it has no success manifest.")
            raise
