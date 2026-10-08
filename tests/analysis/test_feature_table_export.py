# SPDX-License-Identifier: GPL-3.0-only
"""Real-file consumers and admission/failure checks for retained feature exports."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as parquet
import pytest

from capture_analysis.feature_table_export import FeatureTableExportError, export_feature_table

ROOT = Path(__file__).resolve().parents[2]
TABLE = "features/numeric/selected.parquet"
TEXT = 'label,μ\n"quoted"'


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def inventory(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): identity(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def typed_table() -> pa.Table:
    fields = [
        pa.field("t_ns", pa.int64(), metadata={b"units": b"ns"}),
        pa.field(TEXT, pa.string()),
        pa.field("value", pa.float64()),
        pa.field("u64", pa.uint64()),
        pa.field("flag", pa.bool_()),
    ]
    arrays = [
        pa.array([9007199254740993, 9007199254740995, None, -1, 0, 1, 2, 3], pa.int64()),
        pa.array(["", None, "NaN", "null", "line\nbreak", '"quote"', "👩", "<b>μ</b>"]),
        pa.array([-0.0, 1e-320, 1.7976931348623157e308, float("nan"),
                  float("inf"), -float("inf"), None, 42.125], pa.float64()),
        pa.array([2**64 - 1, None, 0, 1, 2, 3, 4, 5], pa.uint64()),
        pa.array([True, False, None, True, False, None, True, False]),
    ]
    schema = pa.schema(fields, metadata={b"context": b"retained synthetic scientific metadata"})
    return pa.Table.from_arrays(arrays, schema=schema)


def make_job(tmp_path: Path, table: pa.Table | None = None) -> tuple[Path, pa.Table]:
    table = typed_table() if table is None else table
    package = tmp_path / "session.mmsession"
    job = package / "processing/jobs/synthetic-job"
    (job / "features/numeric").mkdir(parents=True)
    (package / "raw.bin").write_bytes(b"retained raw sentinel\x00")
    write_json(package / "manifest.json", {
        "sessionId": "synthetic-export", "state": "finalized", "session_schema_version": "1.0.0",
    })
    parquet.write_table(table, job / TABLE, row_group_size=3)
    write_json(job / "params.json", {"gapPolicy": "mask", "note": "unmodified μ"})
    write_json(job / "features/_schema.json", {
        "schemaId": "capture.analysis_feature_schema/1",
        "tables": {TABLE: {
            "featureSchemaVersion": 1, "rows": table.num_rows,
            "sourceId": "source.synthetic", "streamId": "stream.synthetic", "validFraction": 0.75,
            "columns": [
                {"name": name, "units": "ns" if name == "t_ns" else "a.u.",
                 "calibrated": False, "provisional": True,
                 "timestampMethod": "native", "retainedExtension": {"note": "μ"}}
                for name in table.column_names
            ],
        }},
    })
    write_json(job / "job_manifest.json", {
        "schemaId": "capture.analysis_job/1", "jobId": job.name,
        "sessionId": "synthetic-export", "status": "completed_with_warnings",
        "packagePath": "/an/original/location/that/is/not/followed/session.mmsession",
        "paramsDigest": "original-parameter-digest", "warnings": ["synthetic provisional values"],
        "outputs": [
            {"relativePath": relative, "kind": kind, **identity(job / relative)}
            for relative, kind in (
                (TABLE, "feature_parquet"), ("params.json", "params"),
                ("features/_schema.json", "feature_schema"),
            )
        ],
    })
    return job, table


def read_csv(output: Path) -> pa.Table:
    doc = json.loads((output / "_schema.json").read_bytes())
    schema = pa.ipc.read_schema(pa.BufferReader(base64.b64decode(doc["arrowSchemaBase64"])))
    return arrow_csv.read_csv(
        output / "table.csv",
        parse_options=arrow_csv.ParseOptions(newlines_in_values=True),
        convert_options=arrow_csv.ConvertOptions(
            column_types=schema, null_values=[""], strings_can_be_null=True,
            quoted_strings_can_be_null=False,
        ),
    )


def assert_values(actual: pa.Table, expected: pa.Table) -> None:
    assert actual.column_names == expected.column_names
    assert actual.num_rows == expected.num_rows
    for name in expected.column_names:
        assert actual[name].type == expected[name].type
        assert actual[name].is_null().to_pylist() == expected[name].is_null().to_pylist()
        for got, want in zip(actual[name].to_pylist(), expected[name].to_pylist(), strict=True):
            if isinstance(want, float):
                if math.isnan(want):
                    assert math.isnan(got)
                else:
                    assert got == want
                    if want == 0:
                        assert math.copysign(1, got) == math.copysign(1, want)
            else:
                assert got == want


def test_ordered_typed_values_metadata_provenance_and_hashes(tmp_path: Path) -> None:
    job, table = make_job(tmp_path)
    before = inventory(job.parents[2])
    output = tmp_path / "export"
    columns = [TEXT, "t_ns", "value", "u64", "flag"]
    result = export_feature_table(job, TABLE, output, columns=columns, batch_size=3)
    expected = table.select(columns)
    assert_values(parquet.read_table(output / "table.parquet"), expected)
    assert_values(read_csv(output), expected)
    assert result["selection"] == {
        "columns": columns, "rows": 8, "rowPolicy": "all-in-original-order",
    }
    assert result["source"]["jobStatus"] == "completed_with_warnings"
    assert result == json.loads((output / "manifest.json").read_bytes())
    sidecar = json.loads((output / "_schema.json").read_bytes())
    original = json.loads((job / "features/_schema.json").read_bytes())["tables"][TABLE]
    assert sidecar["tableMetadata"]["columns"] == [
        next(item for item in original["columns"] if item["name"] == name) for name in columns
    ]
    source_schema = pa.ipc.read_schema(
        pa.BufferReader(base64.b64decode(sidecar["sourceArrowSchemaBase64"]))
    )
    assert source_schema.equals(parquet.read_schema(job / TABLE), check_metadata=True)
    assert parquet.read_schema(output / "table.parquet").field("t_ns").metadata == {b"units": b"ns"}
    for original_path, copied_path in (
        ("params.json", "source/params.json"),
        ("job_manifest.json", "source/job_manifest.json"),
        ("features/_schema.json", "source/features_schema.json"),
    ):
        assert (job / original_path).read_bytes() == (output / copied_path).read_bytes()
    for entry in result["outputs"]:
        assert {key: entry[key] for key in ("bytes", "sha256")} == identity(
            output / entry["relativePath"]
        )
    for entry in result["source"]["inputs"]:
        assert {key: entry[key] for key in ("bytes", "sha256")} == identity(
            job / entry["relativePath"]
        )
    assert inventory(job.parents[2]) == before
    assert not (output / "failure.json").exists()


@pytest.mark.parametrize("output_format", ["csv", "parquet", "both"])
@pytest.mark.parametrize("empty", [False, True])
def test_all_columns_and_empty_table(tmp_path: Path, output_format: str, empty: bool) -> None:
    table = typed_table().slice(0, 0) if empty else typed_table()
    job, _ = make_job(tmp_path, table)
    output = tmp_path / "export"
    result = export_feature_table(job, TABLE, output, output_format=output_format, batch_size=2)
    assert result["selection"]["rows"] == table.num_rows
    assert result["selection"]["columns"] == table.column_names
    for suffix in ("csv", "parquet"):
        assert (output / f"table.{suffix}").exists() == (output_format in {suffix, "both"})
    if output_format in {"csv", "both"}:
        assert_values(read_csv(output), table)
    if output_format in {"parquet", "both"}:
        assert_values(parquet.read_table(output / "table.parquet"), table)


def test_dotted_name_is_literal_and_nested_parquet_remains_typed(tmp_path: Path) -> None:
    table = pa.table({
        "a": pa.array([{"b": 1}, {"b": 2}], type=pa.struct([("b", pa.int64())])),
        "a.b": pa.array([99, 88], type=pa.int64()),
    })
    job, _ = make_job(tmp_path, table)
    output = tmp_path / "literal"
    export_feature_table(job, TABLE, output, columns=["a.b"])
    assert_values(read_csv(output), table.select(["a.b"]))
    for output_format in ("csv", "both"):
        refused = tmp_path / output_format
        with pytest.raises(FeatureTableExportError, match="CSV does not support"):
            export_feature_table(job, TABLE, refused, output_format=output_format)
        assert not refused.exists()
    export_feature_table(job, TABLE, tmp_path / "nested", output_format="parquet")
    assert_values(parquet.read_table(tmp_path / "nested/table.parquet"), table)


@pytest.mark.parametrize("columns", [[], ["missing"], ["t_ns", "t_ns"], "t_ns", [None]])
def test_bad_column_selection_leaves_no_destination(tmp_path: Path, columns) -> None:
    job, _ = make_job(tmp_path)
    before = inventory(job.parents[2])
    with pytest.raises(FeatureTableExportError):
        export_feature_table(job, TABLE, tmp_path / "refused", columns=columns)
    assert not (tmp_path / "refused").exists()
    assert inventory(job.parents[2]) == before


@pytest.mark.parametrize("relative", [
    "../outside.parquet", "/absolute.parquet", "features/../outside.parquet",
    "features//x.parquet", "C:/outside.parquet", "features\\x.parquet",
    "features/x.parquet:stream",
])
def test_unsafe_table_path_is_refused(tmp_path: Path, relative: str) -> None:
    job, _ = make_job(tmp_path)
    with pytest.raises(FeatureTableExportError):
        export_feature_table(job, relative, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("field,value", [
    ("status", "failed"), ("status", "running"), ("jobId", "different"),
    ("schemaId", "capture.analysis_job/2"),
])
def test_nonfinal_or_wrong_job_identity_is_refused(tmp_path: Path, field: str, value: str) -> None:
    job, _ = make_job(tmp_path)
    path = job / "job_manifest.json"
    document = json.loads(path.read_bytes())
    document[field] = value
    write_json(path, document)
    with pytest.raises(FeatureTableExportError):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("relative", [TABLE, "params.json", "features/_schema.json"])
def test_stale_declared_identity_is_refused(tmp_path: Path, relative: str) -> None:
    job, _ = make_job(tmp_path)
    with (job / relative).open("ab") as stream:
        stream.write(b" ")
    before = inventory(job.parents[2])
    with pytest.raises(FeatureTableExportError, match="identity mismatch"):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    assert inventory(job.parents[2]) == before


def test_existing_and_in_package_destinations_are_untouched(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_bytes(b"keep me")
    before = inventory(tmp_path)
    for output in (existing, job / "export", job.parents[2] / "export"):
        with pytest.raises(FeatureTableExportError):
            export_feature_table(job, TABLE, output)
    assert inventory(tmp_path) == before


def test_symlinked_selected_file_is_refused(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    original = job / TABLE
    target = tmp_path / "external.parquet"
    original.rename(target)
    try:
        original.symlink_to(target)
    except OSError:
        pytest.skip("host cannot create a synthetic file symlink without extra privileges")
    with pytest.raises(FeatureTableExportError, match="linked"):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_write_failure_keeps_an_explicit_incomplete_export(tmp_path: Path, monkeypatch) -> None:
    job, _ = make_job(tmp_path)
    before = inventory(job.parents[2])
    output = tmp_path / "failed"
    def fail_writer(path, schema):
        Path(path).write_bytes(b"incomplete parquet control")
        raise OSError("injected output capacity failure")
    monkeypatch.setattr(parquet, "ParquetWriter", fail_writer)
    with pytest.raises(OSError, match="capacity failure"):
        export_feature_table(job, TABLE, output)
    assert not (output / "manifest.json").exists()
    assert json.loads((output / "failure.json").read_bytes())["status"] == "failed"
    assert (output / "table.parquet").read_bytes() == b"incomplete parquet control"
    assert inventory(job.parents[2]) == before


def test_actual_native_features_job_to_cli_export(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "native_numeric_fixture", ROOT / "tests/analysis/test_numeric_cli_receiving.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    package = fixture.make_package(tmp_path / "real-feature.mmsession")
    analysis = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/run_analysis.py"), "features",
         str(package), "--strict-warnings"],
        capture_output=True, text=True, timeout=120,
    )
    assert analysis.returncode == 0, analysis.stdout + analysis.stderr
    job = Path(next(line[4:] for line in analysis.stdout.splitlines() if line.startswith("dir=")))
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    relative = next(item["relativePath"] for item in manifest["outputs"]
                    if item["kind"] == "feature_parquet")
    original = parquet.read_table(job / relative)
    columns = [original.column_names[-1], "t_start_ns"]
    before = inventory(package)
    output = tmp_path / "native-export"
    command = [sys.executable, "-B", str(ROOT / "tools/export_feature_table.py"), str(job),
               "--table", relative, "--column", columns[0], "--column", columns[1],
               "--format", "both", "--output", str(output)]
    exported = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert exported.returncode == 0, exported.stdout + exported.stderr
    assert "status=completed" in exported.stdout
    assert_values(read_csv(output), original.select(columns))
    assert_values(parquet.read_table(output / "table.parquet"), original.select(columns))
    assert inventory(package) == before
    repeated = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert repeated.returncode == 1 and "already exists" in repeated.stderr


@pytest.mark.parametrize("column", [
    pa.array([-0.0, 1.401298464324817e-45, 3.4028234663852886e38, None], pa.float32()),
    pa.array(["", None, "μ\nlarge", "NaN"], pa.large_string()),
    pa.array([-32768, -1, None, 32767], pa.int16()),
])
def test_additional_csv_scalar_types(tmp_path: Path, column: pa.Array) -> None:
    table = pa.table({"typed": column})
    job, _ = make_job(tmp_path, table)
    output = tmp_path / "typed"
    export_feature_table(job, TABLE, output)
    assert_values(read_csv(output), table)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "kind"])
def test_selected_table_requires_one_manifest_listing(tmp_path: Path, mutation: str) -> None:
    job, _ = make_job(tmp_path)
    path = job / "job_manifest.json"
    document = json.loads(path.read_bytes())
    if mutation == "missing":
        document["outputs"].pop(0)
    elif mutation == "duplicate":
        document["outputs"].append(dict(document["outputs"][0]))
    else:
        document["outputs"][0]["kind"] = "feature_csv"
    write_json(path, document)
    with pytest.raises(FeatureTableExportError, match="exactly one"):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("mutation", ["rows", "missing_units", "duplicate_name", "wrong_name"])
def test_schema_mismatch_is_refused_after_valid_hashes(tmp_path: Path, mutation: str) -> None:
    job, _ = make_job(tmp_path)
    schema_path = job / "features/_schema.json"
    schema = json.loads(schema_path.read_bytes())
    metadata = schema["tables"][TABLE]
    if mutation == "rows":
        metadata["rows"] += 1
    elif mutation == "missing_units":
        del metadata["columns"][0]["units"]
    elif mutation == "duplicate_name":
        metadata["columns"][1]["name"] = metadata["columns"][0]["name"]
    else:
        metadata["columns"][0]["name"] = "not-in-parquet"
    write_json(schema_path, schema)
    manifest_path = job / "job_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["outputs"][2].update(identity(schema_path))
    write_json(manifest_path, manifest)
    with pytest.raises(FeatureTableExportError):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_input_change_during_real_write_prevents_success(tmp_path: Path, monkeypatch) -> None:
    job, _ = make_job(tmp_path)
    output = tmp_path / "changed"
    actual_writer = arrow_csv.CSVWriter
    class ConcurrentChange:
        def __init__(self, path, schema):
            self.writer = actual_writer(path, schema)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.writer.close()

        def write_batch(self, batch):
            self.writer.write_batch(batch)
            with (job / "params.json").open("ab") as stream:
                stream.write(b" ")
    monkeypatch.setattr(arrow_csv, "CSVWriter", ConcurrentChange)
    with pytest.raises(FeatureTableExportError, match="input changed"):
        export_feature_table(job, TABLE, output, batch_size=3)
    assert not (output / "manifest.json").exists()
    assert json.loads((output / "failure.json").read_bytes())["status"] == "failed"
    assert (output / "source/params.json").read_bytes() != (job / "params.json").read_bytes()


def test_hardlinked_selected_file_is_refused(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    external = tmp_path / "outside.parquet"
    try:
        external.hardlink_to(job / TABLE)
    except OSError:
        pytest.skip("host filesystem does not support synthetic file hardlinks")
    before = inventory(tmp_path)
    with pytest.raises(FeatureTableExportError, match="hard-linked"):
        export_feature_table(job, TABLE, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    assert inventory(tmp_path) == before
