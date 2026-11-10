# SPDX-License-Identifier: GPL-3.0-only
"""Collect compatible retained measurements, keeping each row's experimental context."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as parquet

from capture_analysis.feature_collection_report import write_collection_review
from capture_analysis.feature_table_export import (
    FeatureTableExportError,
    _destination,
    _identity,
    _json_bytes,
    open_feature_table,
)

_CONTEXT = (
    ("capture_input", pa.int32()),
    ("capture_condition", pa.string()),
    ("capture_session_id", pa.string()),
    ("capture_job_id", pa.string()),
    ("capture_source_id", pa.string()),
    ("capture_stream_id", pa.string()),
    ("capture_scope_start_ns", pa.int64()),
    ("capture_scope_end_ns", pa.int64()),
    ("capture_gap_policy", pa.string()),
    ("capture_job_status", pa.string()),
    ("capture_warning_count", pa.int32()),
    ("capture_row", pa.int64()),
)
_CONTEXT_NAMES = {name for name, _ in _CONTEXT}
# These identify the selection or execution, rather than the feature calculation.
_SELECTION_PARAMS = {
    "command",
    "startSessionNs",
    "endSessionNs",
    "checkpointSection",
    "sources",
    "maxRamBytes",
    "overwriteJobId",
}


@dataclass(frozen=True)
class FeatureTableInput:
    """One explicitly labeled saved table; repeated conditions support repeated trials."""

    condition: str
    job_dir: Path
    table: str


def _recipe(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key not in _SELECTION_PARAMS}


def _context_values(index: int, item: FeatureTableInput, selected) -> dict[str, Any]:
    manifest = selected.documents["job_manifest.json"][1]
    metadata = selected.schema_record["tableMetadata"]
    scope = manifest.get("timeRange") or {}
    warnings = manifest.get("warnings") or []
    return {
        "capture_input": index,
        "capture_condition": item.condition,
        "capture_session_id": manifest["sessionId"],
        "capture_job_id": manifest["jobId"],
        "capture_source_id": metadata.get("sourceId"),
        "capture_stream_id": metadata.get("streamId"),
        "capture_scope_start_ns": scope.get("startSessionNs"),
        "capture_scope_end_ns": scope.get("endSessionNs"),
        "capture_gap_policy": manifest.get("gapPolicy"),
        "capture_job_status": manifest["status"],
        "capture_warning_count": len(warnings),
    }


def collect_feature_tables(
    inputs: Sequence[FeatureTableInput],
    output_dir: Path,
    *,
    columns: Sequence[str] | None = None,
    output_format: str = "both",
    batch_size: int = 8192,
) -> dict[str, Any]:
    """Stack compatible saved rows without averaging, aligning or rerunning analysis.

    Inputs remain in the caller's order, followed by their original row order.
    Every input must contain the same selected column definitions and Arrow types.
    Differences in analysis settings remain explicit and make the result warn.
    Admission failures leave no output directory; later failures leave a failed
    result, never a completed manifest.
    """
    items = list(inputs)
    if len(items) < 2:
        raise FeatureTableExportError(
            "Choose at least two saved tables to collect; use export-table for one table."
        )
    if output_format not in {"csv", "parquet", "both"}:
        raise FeatureTableExportError("output_format must be csv, parquet, or both")
    if type(batch_size) is not int or batch_size < 1:
        raise FeatureTableExportError("batch_size must be a positive integer")
    if any(not isinstance(item.condition, str) or not item.condition.strip() for item in items):
        raise FeatureTableExportError("Every input needs a nonempty condition label.")

    with ExitStack() as stack:
        selections = [
            stack.enter_context(
                open_feature_table(
                    item.job_dir,
                    item.table,
                    columns=columns,
                    output_format=output_format,
                )
            )
            for item in items
        ]
        first = selections[0]
        chosen = first.selected
        collisions = _CONTEXT_NAMES.intersection(chosen)
        if collisions:
            raise FeatureTableExportError(
                f"Selected feature names conflict with collection context: {sorted(collisions)}"
            )
        # Check every source boundary before creating the destination.
        output = _destination(Path(output_dir), first.package)
        for selected in selections[1:]:
            _destination(output, selected.package)
        seen = set()
        first_metadata = first.schema_record["tableMetadata"]
        for index, selected in enumerate(selections):
            key = (selected.job, items[index].table)
            if key in seen:
                raise FeatureTableExportError(
                    f"Input {index + 1} repeats a saved table; select each table only once."
                )
            seen.add(key)
            metadata = selected.schema_record["tableMetadata"]
            if chosen != selected.selected:
                raise FeatureTableExportError(
                    f"Input {index + 1} has different columns; choose shared --column names."
                )
            if metadata["featureSchemaVersion"] != first_metadata["featureSchemaVersion"]:
                raise FeatureTableExportError(
                    f"Input {index + 1} uses a different feature schema version."
                )
            for name, expected, actual in zip(
                chosen,
                first_metadata["columns"],
                metadata["columns"],
                strict=True,
            ):
                if expected != actual:
                    raise FeatureTableExportError(
                        f"Input {index + 1} has incompatible metadata for {name!r}: "
                        "units, calibration, timing or feature meaning differ. "
                        "Export those measurements separately."
                    )
                if not first.schema.field(name).equals(
                    selected.schema.field(name),
                    check_metadata=True,
                ):
                    raise FeatureTableExportError(
                        f"Input {index + 1} has a different Arrow field for {name!r}; "
                        "collection does not silently coerce measurements."
                    )
        # Input-specific schema metadata belongs in source records, not on a
        # combined table where it would misdescribe all but the first input.
        schema = pa.schema(
            [pa.field(name, kind) for name, kind in _CONTEXT] + list(first.schema),
            metadata={b"capture.schema": b"capture.feature_collection/1"},
        )
        records = []
        notices = []
        first_recipe = _recipe(first.documents["params.json"][1])
        first_versions = {
            name: first.documents["job_manifest.json"][1].get(name)
            for name in ("captureAnalysisVersion", "pluginManifestVersion")
        }
        for index, (item, selected) in enumerate(zip(items, selections, strict=True)):
            manifest = selected.documents["job_manifest.json"][1]
            metadata = selected.schema_record["tableMetadata"]
            params = selected.documents["params.json"][1]
            values = _context_values(index, item, selected)
            # Materialize context once to catch malformed retained values before
            # creating an export that a consumer might mistake for completed.
            for name, kind in _CONTEXT:
                if name != "capture_row":
                    pa.array([values[name]], type=kind)
            if values["capture_source_id"] is None or values["capture_stream_id"] is None:
                notices.append(
                    f"Input {index + 1} has no recorded per-table source/stream identity; "
                    "the corresponding context cells remain null."
                )
            recipe = _recipe(params)
            changed = sorted(
                key
                for key in first_recipe.keys() | recipe.keys()
                if first_recipe.get(key) != recipe.get(key)
            )
            if changed:
                notices.append(
                    f"Input {index + 1} analysis settings differ from input 1: "
                    f"{', '.join(changed)}."
                )
            versions = {name: manifest.get(name) for name in first_versions}
            if versions != first_versions:
                notices.append(f"Input {index + 1} analysis/plugin versions differ from input 1.")
            if selected.rows == 0:
                notices.append(f"Input {index + 1} contains no saved measurement rows.")
            records.append(
                {
                    "input": index,
                    "condition": item.condition,
                    "rows": selected.rows,
                    "sessionId": manifest["sessionId"],
                    "jobId": manifest["jobId"],
                    "jobStatus": manifest["status"],
                    "tableRelativePath": item.table,
                    "sourceId": metadata.get("sourceId"),
                    "streamId": metadata.get("streamId"),
                    "timeRange": manifest.get("timeRange"),
                    "gapPolicy": manifest.get("gapPolicy"),
                    "paramsDigest": manifest.get("paramsDigest"),
                    "warnings": manifest.get("warnings") or [],
                    "analysisSettings": recipe,
                    "analysisSettingsDiffer": changed,
                    "toolVersions": versions,
                    "tooling": manifest.get("tooling", {}),
                    "pluginIds": manifest.get("pluginIds", []),
                    "tableMetadata": metadata,
                    "sourceArrowSchemaBase64": selected.schema_record["sourceArrowSchemaBase64"],
                    "sourceInputs": [
                        {"relativePath": name, **identity}
                        for name, identity in selected.inputs.items()
                    ],
                }
            )
        source_warns = any(
            record["jobStatus"] == "completed_with_warnings" or record["warnings"]
            for record in records
        )
        status = "completed_with_warnings" if source_warns or notices else "completed"
        schema_record = {
            "schemaId": "capture.feature_collection_schema/1",
            "arrowSchemaBase64": base64.b64encode(schema.serialize()).decode("ascii"),
            "fields": [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in schema
            ],
            "measurementColumns": first_metadata["columns"],
            "contextColumns": [name for name, _ in _CONTEXT],
            "context": {
                "capture_input": "Zero-based input index in manifest.json.",
                "capture_row": "Zero-based original row index within the selected input table.",
                "capture_scope_start_ns": "Recorded analysis scope in native session nanoseconds.",
                "capture_scope_end_ns": "Recorded inclusive analysis endpoint, not a new sample.",
                "capture_source_id": "Null means the saved table did not record this binding.",
                "capture_stream_id": "Null means the saved table did not record this binding.",
                "capture_warning_count": "Original warnings; full text per input in manifest.json.",
            },
            "rowPolicy": "input-order-then-original-row-order",
            "csv": first.schema_record["csv"],
        }
        output.mkdir()
        try:
            (output / "_schema.json").write_bytes(_json_bytes(schema_record))
            written = 0
            previews = [[] for _ in items]
            data_files = []
            with ExitStack() as writers:
                csv_writer = parquet_writer = None
                if output_format in {"csv", "both"}:
                    csv_writer = writers.enter_context(
                        arrow_csv.CSVWriter(str(output / "table.csv"), schema)
                    )
                    data_files.append("table.csv")
                if output_format in {"parquet", "both"}:
                    parquet_writer = writers.enter_context(
                        parquet.ParquetWriter(output / "table.parquet", schema)
                    )
                    data_files.append("table.parquet")
                for index, (item, selected) in enumerate(zip(items, selections, strict=True)):
                    values = _context_values(index, item, selected)
                    local_row = 0
                    for batch in selected.reader.iter_batches(batch_size=batch_size):
                        remaining = 3 - len(previews[index])
                        if remaining > 0:
                            previews[index].extend(
                                batch.select(selected.indices[:6]).slice(0, remaining).to_pylist()
                            )
                        context_arrays = [
                            pa.array(
                                range(local_row, local_row + batch.num_rows)
                                if name == "capture_row"
                                else [values[name]] * batch.num_rows,
                                type=kind,
                            )
                            for name, kind in _CONTEXT
                        ]
                        collected = pa.RecordBatch.from_arrays(
                            context_arrays + [batch.column(column) for column in selected.indices],
                            schema=schema,
                        )
                        if csv_writer is not None:
                            csv_writer.write_batch(collected)
                        if parquet_writer is not None:
                            parquet_writer.write_batch(collected)
                        local_row += batch.num_rows
                    if local_row != selected.rows:
                        raise FeatureTableExportError(
                            "Saved input row count changed during collection."
                        )
                    written += local_row
            for selected in selections:
                selected.revalidate()
            write_collection_review(
                output / "index.html",
                records,
                first_metadata["columns"],
                notices,
                previews,
                output_format,
            )
            result = {
                "schemaId": "capture.feature_collection/1",
                "status": status,
                "createdUtc": datetime.now(UTC).isoformat(),
                "selection": {
                    "columns": chosen,
                    "rows": written,
                    "rowPolicy": "input-order-then-original-row-order",
                },
                "format": output_format,
                "inputs": records,
                "notices": notices,
                "interpretation": (
                    "These are retained feature windows, not independent experimental replicates. "
                    "Collection does not align sessions, aggregate windows, perform statistical "
                    "tests, or validate hardware, physiology or experimental comparability."
                ),
                "outputs": [
                    {"relativePath": name, **_identity(output / name)}
                    for name in [*data_files, "_schema.json", "index.html"]
                ],
            }
            pending = output / "manifest.pending.json"
            pending.write_bytes(_json_bytes(result))
            pending.rename(output / "manifest.json")
            return result
        except Exception as exc:
            (output / "manifest.json").unlink(missing_ok=True)
            try:
                (output / "failure.json").write_bytes(
                    _json_bytes(
                        {
                            "schemaId": "capture.feature_collection/1",
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                )
            except OSError:
                pass
            exc.add_note(f"Incomplete collection retained at {output}; it has no success manifest.")
            raise
