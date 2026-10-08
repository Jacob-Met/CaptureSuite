# SPDX-License-Identifier: GPL-3.0-only
"""Actual retained Parquet receiving for the bounded feature-preview reader."""

from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from capture_analysis.features.io import write_feature_table
from capture_desktop.analysis_feature_preview import (
    FeaturePreviewError,
    format_feature_value,
    load_feature_catalog,
    load_feature_preview,
)


def _json(path: Path, document: dict) -> bytes:
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(data)
    return data


def _entry(path: Path, root: Path, kind: str) -> dict:
    data = path.read_bytes()
    return {
        "relativePath": path.relative_to(root).as_posix(),
        "kind": kind,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def make_feature_job(tmp_path: Path, table: pa.Table, *, name: str = "job") -> Path:
    """Use the actual feature writer, then its retained metadata contracts."""
    job = tmp_path / "session.mmsession" / "processing" / "jobs" / name
    job.mkdir(parents=True)
    params = {"command": "features", "gapPolicy": "ignore"}
    _json(job / "params.json", params)
    schema: dict = {}
    outputs = [_entry(job / "params.json", job, "params")]
    metadata = [
        {
            "name": name,
            "units": "ns" if name == "t_ns" else "V" if name == "value" else "",
            "calibrated": name == "value",
            "description": f"Retained {name}",
        }
        for name in table.column_names
    ]
    frame = table.to_pandas(types_mapper=pd.ArrowDtype)
    write_feature_table(
        job, "features/sample.parquet", frame, feature_schema_version=1,
        columns_meta=metadata, schema_doc=schema, outputs=outputs
    )
    _json(job / "features/_schema.json", schema)
    outputs.append(_entry(job / "features/_schema.json", job, "feature_schema"))
    _json(job / "job_manifest.json", {
        "schemaId": "capture.analysis_job/1",
        "jobId": name,
        "sessionId": "retained-session",
        "status": "completed",
        "paramsDigest": hashlib.sha256(
            json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest(),
        "outputs": outputs,
    })
    return job


def _simple_table(rows: int = 3, columns: int = 2) -> pa.Table:
    return pa.table({
        ("t_ns" if column == 0 else f"value.{column}"): pa.array(range(rows), type=pa.int64())
        for column in range(columns)
    })


def _refresh_entry(job: Path, relative: str) -> None:
    manifest = json.loads((job / "job_manifest.json").read_text())
    for row in manifest["outputs"]:
        if row["relativePath"] == relative:
            row.update(_entry(job / relative, job, row["kind"]))
    _json(job / "job_manifest.json", manifest)


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        p.relative_to(root).as_posix(): (
            p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest()
        )
        for p in root.rglob("*") if p.is_file()
    }


def test_real_writer_exact_nullable_values_metadata_and_input_conservation(tmp_path: Path) -> None:
    table = pa.table({
        "t_ns": pa.array([2**53 + 1, 2**63 - 1, None], type=pa.int64()),
        "unsigned": pa.array([2**64 - 1, 0, 1], type=pa.uint64()),
        "value": pa.array([float("nan"), None, -0.0], type=pa.float64()),
        'literal."name': pa.array(["NULL", "NaN", ""], type=pa.string()),
        "flag": pa.array([True, False, None], type=pa.bool_()),
    })
    job = make_feature_job(tmp_path, table)
    before = _snapshot(job.parent.parent.parent)
    catalog = load_feature_catalog(job)
    assert catalog.tables == ("features/sample.parquet",)
    preview = load_feature_preview(catalog, catalog.tables[0])
    assert preview.total_rows == 3
    assert preview.rows[0][0] == 2**53 + 1
    assert type(preview.rows[0][0]) is int
    assert preview.rows[0][1] == 2**64 - 1
    assert math.isnan(preview.rows[0][2])
    assert preview.rows[1][2] is None
    assert format_feature_value(preview.rows[0][3]) == '"NULL"'
    assert format_feature_value(preview.rows[1][3]) == '"NaN"'
    assert format_feature_value(preview.rows[2][3]) == '""'
    assert format_feature_value(preview.rows[1][2]) == "NULL"
    assert format_feature_value(preview.rows[0][2]) == "NaN"
    assert format_feature_value(preview.rows[2][2]) == "-0.0"
    assert format_feature_value(preview.rows[0][4]) == "true"
    assert preview.columns[0].units == "ns"
    assert preview.columns[0].arrow_type == "int64"
    assert preview.columns[2].calibrated is True
    assert preview.columns[3].name == 'literal."name'
    assert preview.table_sha256 == hashlib.sha256(
        (job / catalog.tables[0]).read_bytes()
    ).hexdigest()
    assert before == _snapshot(job.parent.parent.parent)


@pytest.mark.parametrize("rows", [0, 1, 200, 203])
def test_empty_exact_and_truncated_preview_preserves_recorded_order(
    tmp_path: Path, rows: int
) -> None:
    job = make_feature_job(tmp_path, _simple_table(rows))
    preview = load_feature_preview(load_feature_catalog(job), "features/sample.parquet")
    assert preview.total_rows == rows
    assert len(preview.rows) == min(rows, 200)
    assert [row[0] for row in preview.rows] == list(range(min(rows, 200)))


@pytest.mark.parametrize("columns", [128, 129])
def test_all_columns_or_complete_visible_refusal(tmp_path: Path, columns: int) -> None:
    job = make_feature_job(tmp_path, _simple_table(2, columns))
    catalog = load_feature_catalog(job)
    if columns == 128:
        assert len(load_feature_preview(catalog, catalog.tables[0]).columns) == 128
    else:
        with pytest.raises(FeaturePreviewError, match="128"):
            load_feature_preview(catalog, catalog.tables[0])


@pytest.mark.parametrize("relative", [
    "../outside.parquet", "/outside.parquet", "features//x.parquet",
    "features/./x.parquet", "features/../x.parquet", "C:/x.parquet",
    r"features\x.parquet",
])
def test_unsafe_manifest_paths_refuse_before_open(tmp_path: Path, relative: str) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    manifest = json.loads((job / "job_manifest.json").read_text())
    row = next(x for x in manifest["outputs"] if x["kind"] == "feature_parquet")
    row["relativePath"] = relative
    _json(job / "job_manifest.json", manifest)
    with pytest.raises(FeaturePreviewError, match="Unsafe"):
        load_feature_catalog(job)


@pytest.mark.parametrize("change", ["names", "duplicate", "rows", "units", "calibrated"])
def test_schema_disagreement_refuses_complete_preview(tmp_path: Path, change: str) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    schema_path = job / "features/_schema.json"
    schema = json.loads(schema_path.read_text())
    metadata = schema["tables"]["features/sample.parquet"]
    if change == "names":
        metadata["columns"][0]["name"] = "foreign"
    elif change == "duplicate":
        metadata["columns"].append(metadata["columns"][0])
    elif change == "rows":
        metadata["rows"] += 1
    elif change == "units":
        del metadata["columns"][0]["units"]
    else:
        metadata["columns"][0]["calibrated"] = "false"
    _json(schema_path, schema)
    _refresh_entry(job, "features/_schema.json")
    with pytest.raises(FeaturePreviewError, match="metadata"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")


@pytest.mark.parametrize("relative", [
    "job_manifest.json", "params.json", "features/_schema.json", "features/sample.parquet"
])
def test_changed_inputs_never_publish_a_preview(tmp_path: Path, relative: str) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    catalog = load_feature_catalog(job)
    path = job / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(FeaturePreviewError):
        load_feature_preview(catalog, "features/sample.parquet")


def test_missing_unlisted_and_duplicate_table_refusals(tmp_path: Path) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    catalog = load_feature_catalog(job)
    with pytest.raises(FeaturePreviewError, match="listed"):
        load_feature_preview(catalog, "features/foreign.parquet")
    (job / "features/sample.parquet").unlink()
    with pytest.raises(FeaturePreviewError):
        load_feature_preview(catalog, "features/sample.parquet")
    manifest = json.loads((job / "job_manifest.json").read_text())
    manifest["outputs"].append(
        next(x for x in manifest["outputs"] if x["kind"] == "feature_parquet")
    )
    _json(job / "job_manifest.json", manifest)
    with pytest.raises(FeaturePreviewError, match="exactly one"):
        load_feature_catalog(job)


@pytest.mark.parametrize("kind", ["file", "directory", "hardlink"])
def test_linked_outputs_refuse_without_following_them(tmp_path: Path, kind: str) -> None:
    import os
    import shutil

    job = make_feature_job(tmp_path, _simple_table())
    catalog = load_feature_catalog(job)
    source = job / "features/sample.parquet"
    if kind == "directory":
        saved = tmp_path / "outside-features"
        shutil.move(job / "features", saved)
        (job / "features").symlink_to(saved, target_is_directory=True)
    else:
        saved = tmp_path / "outside.parquet"
        shutil.move(source, saved)
        if kind == "file":
            source.symlink_to(saved)
        else:
            os.link(saved, source)
    with pytest.raises(FeaturePreviewError, match="link"):
        load_feature_preview(catalog, catalog.tables[0])


@pytest.mark.parametrize("kind", ["nested", "binary", "timestamp"])
def test_unsupported_native_arrow_types_are_explicit(tmp_path: Path, kind: str) -> None:
    arrays = {
        "nested": pa.array([[1, 2]], type=pa.list_(pa.int64())),
        "binary": pa.array([b"abc"], type=pa.binary()),
        "timestamp": pa.array([1], type=pa.timestamp("ns")),
    }
    job = make_feature_job(tmp_path, pa.table({"value": arrays[kind]}))
    with pytest.raises(FeaturePreviewError, match="unsupported preview type"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")


def test_corrupt_parquet_matching_manifest_is_actionable(tmp_path: Path) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    (job / "features/sample.parquet").write_bytes(b"not a parquet file")
    _refresh_entry(job, "features/sample.parquet")
    with pytest.raises(FeaturePreviewError, match="Cannot preview"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")


def test_cancelled_reads_do_not_touch_retained_outputs(tmp_path: Path) -> None:
    job = make_feature_job(tmp_path, _simple_table())
    before = _snapshot(job)
    catalog = load_feature_catalog(job)
    event = threading.Event()
    event.set()
    with pytest.raises(FeaturePreviewError, match="cancelled"):
        load_feature_catalog(job, cancel_event=event)
    with pytest.raises(FeaturePreviewError, match="cancelled"):
        load_feature_preview(catalog, catalog.tables[0], cancel_event=event)
    assert before == _snapshot(job)


def test_large_compressed_row_group_refuses_before_decoding(tmp_path: Path, monkeypatch) -> None:
    # A genuinely small compressed file declares >32 MiB of decoded column data.
    values = [("x" * (8 * 1024 * 1024)) + str(i) for i in range(5)]
    job = make_feature_job(tmp_path, pa.table({"value": pa.array(values)}))
    path = job / "features/sample.parquet"
    assert path.stat().st_size < 4 * 1024 * 1024
    with pq.ParquetFile(path) as reader:
        assert reader.metadata.row_group(0).column(0).total_uncompressed_size > 32 * 1024 * 1024

    def never_decode(*args, **kwargs):
        raise AssertionError("Row-group budget must be checked before decoding.")

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", never_decode)
    with pytest.raises(FeaturePreviewError, match="32 MiB"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")


def test_oversized_text_and_file_refuse_complete_preview(tmp_path: Path) -> None:
    job = make_feature_job(tmp_path, pa.table({"value": ["x" * 4097]}))
    with pytest.raises(FeaturePreviewError, match="4,096"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")
    path = job / "features/sample.parquet"
    with path.open("r+b") as stream:
        stream.truncate(256 * 1024 * 1024 + 1)
    with pytest.raises(FeaturePreviewError, match="256 MiB"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")


def test_dictionary_amplification_is_bounded_before_accumulation(
    tmp_path: Path, monkeypatch
) -> None:
    job = make_feature_job(tmp_path, pa.table({"value": ["x" * 65536] * 200}))
    path = job / "features/sample.parquet"
    assert path.stat().st_size < 16 * 1024
    original_batches = pq.ParquetFile.iter_batches
    observed: list[tuple[int, int]] = []

    def one_row_batches(reader, *args, **kwargs):
        for batch in original_batches(reader, *args, **kwargs):
            observed.append((batch.num_rows, batch.nbytes))
            assert batch.num_rows == 1
            assert batch.nbytes < 70 * 1024
            yield batch

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", one_row_batches)
    with pytest.raises(FeaturePreviewError, match="4,096"):
        load_feature_preview(load_feature_catalog(job), "features/sample.parquet")
    assert len(observed) == 1
