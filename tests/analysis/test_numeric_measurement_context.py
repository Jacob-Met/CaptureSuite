# SPDX-License-Identifier: GPL-3.0-only
"""Regressions for interpreting projected measurements after they leave a session."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import jsonschema
import pyarrow as pa
import pyarrow.csv as arrow_csv
import pyarrow.parquet as parquet
import pytest
from capture_analysis.feature_table_export import export_feature_table
from capture_analysis.jobs import JobParams, run
from test_feature_table_export import TABLE, make_job
from test_numeric_cli_receiving import make_package

ROOT = Path(__file__).resolve().parents[2]


def _read_context(output: Path) -> pa.Table:
    schema = json.loads((output / "_schema.json").read_text())["rowContext"]
    arrow = pa.ipc.read_schema(pa.BufferReader(base64.b64decode(schema["arrowSchemaBase64"])))
    return arrow_csv.read_csv(
        output / "row_context.csv",
        convert_options=arrow_csv.ConvertOptions(column_types=arrow),
    )


@pytest.mark.parametrize("output_format", ["csv", "parquet", "both"])
def test_projection_keeps_exact_row_support_after_time_selection(tmp_path, output_format):
    package = make_package(tmp_path / "signals.mmsession")
    result = run(package, JobParams(command="features", sources=["sampler.a"]))
    metadata = json.loads((result.job_dir / "features/_schema.json").read_text())
    table, detail = next(
        (name, item) for name, item in metadata["tables"].items() if item["streamId"] == "voltage"
    )
    jsonschema.validate(
        detail["measurementContext"],
        json.loads(
            (
                ROOT / "schemas/session/jsonschema/analysis_numeric_measurement_context.schema.json"
            ).read_text()
        ),
    )
    output = tmp_path / "handoff"
    receipt = export_feature_table(
        result.job_dir,
        table,
        output,
        columns=["input 1_mean"],
        time_column="t_start_ns",
        start_ns=1_200_000_000,
        end_ns=2_100_000_000,
        output_format=output_format,
        batch_size=1,
    )
    assert receipt["selection"]["rows"] == 2
    support = _read_context(output).to_pylist()
    assert [row["export_row"] for row in support] == [1, 2]
    assert [row["t_start_ns"] for row in support] == [1_500_000_000, 2_000_000_000]
    assert [row["t_end_ns"] for row in support] == [2_500_000_000, 3_000_000_000]
    assert [row["sample_count"] for row in support] == [20, 20]
    assert [row["valid_sample_count"] for row in support] == [20, 20]
    assert [row["gap_fraction"] for row in support] == [0, 0]
    if output_format in {"parquet", "both"}:
        data = parquet.read_table(output / "table.parquet")
        assert data.column_names == ["input 1_mean"]
        assert data["input 1_mean"].to_pylist() == pytest.approx([1.45, 1.45])
    html = (output / "README.html").read_text()
    assert detail["measurementContext"]["methodId"] == "numeric.basic.v2"
    assert "Elapsed window" in html
    assert "expected_sample_count" in html
    assert "Retained slots" not in html
    assert "not time-weighted" in html
    assert "do not crop or recompute" in html
    assert "Windows overlap" in html
    assert "one-based" in html
    assert "1.200000000" in html and "2.100000000" in html
    for entry in receipt["outputs"]:
        payload = (output / entry["relativePath"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]


def test_empty_selection_stays_empty_in_data_support_and_readme(tmp_path):
    package = make_package(tmp_path / "empty.mmsession")
    job = run(package, JobParams(command="features", sources=["sampler.a"]))
    metadata = json.loads((job.job_dir / "features/_schema.json").read_text())
    table = next(iter(metadata["tables"]))
    output = tmp_path / "empty-export"
    receipt = export_feature_table(
        job.job_dir,
        table,
        output,
        columns=["input 1_mean"],
        time_column="t_start_ns",
        start_ns=1_100_000_000,
        end_ns=1_200_000_000,
    )
    assert receipt["selection"]["rows"] == 0
    assert _read_context(output).num_rows == 0
    assert parquet.read_table(output / "table.parquet").num_rows == 0
    assert "No retained rows matched" in (output / "README.html").read_text()


def test_legacy_export_does_not_invent_window_settings(tmp_path):
    job, _ = make_job(tmp_path)
    output = tmp_path / "legacy"
    export_feature_table(job, TABLE, output, columns=["value"])
    assert not (output / "row_context.csv").exists()
    html = (output / "README.html").read_text()
    assert "No method has been inferred" in html
    assert "synthetic provisional values" in html
    assert "Missing support has not been reconstructed" in html
    assert "Nominal duration" not in html
