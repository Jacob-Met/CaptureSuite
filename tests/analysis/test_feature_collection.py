# SPDX-License-Identifier: GPL-3.0-only
"""Researcher-facing collection behavior, independent of extraction internals."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest
from capture_analysis.feature_collection import FeatureTableInput, collect_feature_tables
from capture_analysis.feature_table_export import FeatureTableExportError
from test_feature_table_export import (
    TABLE,
    assert_values,
    identity,
    inventory,
    make_job,
    read_csv,
    write_json,
)


def saved_job(root: Path, session: str, values: list, *, gap: bool = False) -> Path:
    table = pa.table(
        {
            "t_ns": pa.array([i * 100_000_000 for i in range(len(values))], type=pa.int64()),
            "value": pa.array(values, type=pa.float64()),
        }
    )
    job, _ = make_job(root, table)
    manifest_path = job / "job_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest.update(
        sessionId=session,
        status="completed_with_warnings" if gap else "completed",
        warnings=["forearm: recorded disconnect"] if gap else [],
        timeRange={"mode": "custom", "startSessionNs": 0, "endSessionNs": 2_000_000_000},
        gapPolicy="mask",
    )
    write_json(manifest_path, manifest)
    return job


def inputs(tmp_path: Path):
    first = saved_job(tmp_path / "a", "recording-a", [1.0, 2.0])
    second = saved_job(tmp_path / "b", "recording-b", [5.0, None, float("nan"), 7.0])
    return [
        FeatureTableInput("Baseline", first, TABLE),
        FeatureTableInput("Reach", second, TABLE),
    ]


def test_collect_typed_rows_context_and_offline_review(tmp_path: Path) -> None:
    selected = inputs(tmp_path)
    before = [inventory(item.job_dir.parents[2]) for item in selected]
    output = tmp_path / "collected"
    result = collect_feature_tables(
        selected,
        output,
        columns=["value", "t_ns"],
        batch_size=2,
    )
    expected = pa.concat_tables(
        [parquet.read_table(item.job_dir / TABLE).select(["value", "t_ns"]) for item in selected]
    )
    for table in (parquet.read_table(output / "table.parquet"), read_csv(output)):
        assert_values(table.select(["value", "t_ns"]), expected)
        assert table["capture_condition"].to_pylist() == ["Baseline"] * 2 + ["Reach"] * 4
        assert table["capture_session_id"].to_pylist() == ["recording-a"] * 2 + ["recording-b"] * 4
        assert table["capture_row"].to_pylist() == [0, 1, 0, 1, 2, 3]
        assert table["capture_source_id"].to_pylist() == ["source.synthetic"] * 6
        assert table["capture_scope_end_ns"].to_pylist() == [2_000_000_000] * 6
    assert result["status"] == "completed"
    assert result["selection"]["rows"] == 6
    assert result == json.loads((output / "manifest.json").read_bytes())
    review = (output / "index.html").read_text()
    assert "Baseline" in review and "Reach" in review
    assert "0–2 s" in review
    assert "not independent experimental trials" in review
    for item, original in zip(selected, before, strict=True):
        assert inventory(item.job_dir.parents[2]) == original


def test_warning_job_and_changed_settings_stay_visible(tmp_path: Path) -> None:
    selected = inputs(tmp_path)
    second = saved_job(tmp_path / "gap", "interrupted", [8.0, 9.0], gap=True)
    params = json.loads((second / "params.json").read_bytes())
    params["gapPolicy"] = "split"
    write_json(second / "params.json", params)
    manifest = json.loads((second / "job_manifest.json").read_bytes())
    manifest["gapPolicy"] = "split"
    for entry in manifest["outputs"]:
        if entry["relativePath"] == "params.json":
            entry.update(identity(second / "params.json"))
    write_json(second / "job_manifest.json", manifest)
    selected[1] = FeatureTableInput("Reach with dropout", second, TABLE)
    result = collect_feature_tables(selected, tmp_path / "collected")
    assert result["status"] == "completed_with_warnings"
    assert result["inputs"][1]["warnings"] == ["forearm: recorded disconnect"]
    assert result["inputs"][1]["analysisSettingsDiffer"] == ["gapPolicy"]
    assert any("gapPolicy" in notice for notice in result["notices"])
    data = parquet.read_table(tmp_path / "collected/table.parquet")
    assert data["capture_warning_count"].to_pylist() == [0, 0, 1, 1]
    assert "recorded disconnect" in (tmp_path / "collected/index.html").read_text()


@pytest.mark.parametrize("change", ["unit", "type", "missing_column"])
def test_realistic_incompatible_measurements_are_refused(tmp_path: Path, change: str) -> None:
    selected = inputs(tmp_path)
    second = selected[1].job_dir
    schema_path = second / "features/_schema.json"
    document = json.loads(schema_path.read_bytes())
    manifest = json.loads((second / "job_manifest.json").read_bytes())
    if change == "unit":
        document["tables"][TABLE]["columns"][1]["units"] = "mV"
        write_json(schema_path, document)
    else:
        table = parquet.read_table(second / TABLE)
        if change == "type":
            table = table.set_column(1, "value", pa.array([5, None, None, 7], type=pa.float32()))
        else:
            table = table.rename_columns(["t_ns", "another_value"])
            document["tables"][TABLE]["columns"][1]["name"] = "another_value"
            write_json(schema_path, document)
        parquet.write_table(table, second / TABLE)
    for entry in manifest["outputs"]:
        entry.update(identity(second / entry["relativePath"]))
    write_json(second / "job_manifest.json", manifest)
    output = tmp_path / "refused"
    with pytest.raises(FeatureTableExportError):
        collect_feature_tables(selected, output, columns=["value", "t_ns"])
    assert not output.exists()


def test_legacy_missing_binding_remains_explicitly_unknown(tmp_path: Path) -> None:
    selected = inputs(tmp_path)
    job = selected[1].job_dir
    schema_path = job / "features/_schema.json"
    schema = json.loads(schema_path.read_bytes())
    del schema["tables"][TABLE]["sourceId"]
    del schema["tables"][TABLE]["streamId"]
    write_json(schema_path, schema)
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    for entry in manifest["outputs"]:
        if entry["relativePath"] == "features/_schema.json":
            entry.update(identity(schema_path))
    write_json(job / "job_manifest.json", manifest)
    result = collect_feature_tables(selected, tmp_path / "collected")
    data = parquet.read_table(tmp_path / "collected/table.parquet")
    assert data["capture_source_id"].to_pylist() == ["source.synthetic"] * 2 + [None] * 4
    assert result["status"] == "completed_with_warnings"
    assert "no recorded per-table" in result["notices"][0]


def test_repeated_condition_supports_trials_but_same_table_is_not_counted_twice(
    tmp_path: Path,
) -> None:
    selected = inputs(tmp_path)
    repeated_condition = [
        FeatureTableInput("Baseline", item.job_dir, item.table) for item in selected
    ]
    result = collect_feature_tables(repeated_condition, tmp_path / "trials")
    assert result["selection"]["rows"] == 6
    with pytest.raises(FeatureTableExportError, match="repeats"):
        collect_feature_tables([selected[0], selected[0]], tmp_path / "duplicate")
    assert not (tmp_path / "duplicate").exists()


def test_failed_write_cannot_publish_a_success(tmp_path: Path, monkeypatch) -> None:
    selected = inputs(tmp_path)
    import capture_analysis.feature_collection as collection

    def fail(*args, **kwargs):
        raise OSError("disk full while writing collected rows")

    monkeypatch.setattr(collection.parquet, "ParquetWriter", fail)
    output = tmp_path / "incomplete"
    with pytest.raises(OSError, match="disk full"):
        collect_feature_tables(selected, output)
    assert not (output / "manifest.json").exists()
    assert json.loads((output / "failure.json").read_bytes())["status"] == "failed"


def test_actual_mcap_scopes_to_external_condition_table(tmp_path: Path) -> None:
    from capture_analysis.feature_table_export import list_feature_tables
    from capture_analysis.jobs import JobParams, run
    from test_numeric_batch_pipeline import _batch, _write_mcap

    package = tmp_path / "conditions.mmsession"
    package.mkdir()
    write_json(
        package / "manifest.json",
        {
            "sessionId": "condition-recording",
            "state": "finalized",
            "session_schema_version": "1.0.0",
        },
    )
    stream = package / "sources/voltage/streams/input"
    _write_mcap(
        stream / "segments/000000.mcap",
        [
            (
                0,
                _batch(
                    channel_count=1,
                    channel_names=["signal"],
                    samples=[1.0] * 20 + [5.0] * 20,
                    device_time_ns=[i * 100_000_000 for i in range(40)],
                ),
            )
        ],
    )
    write_json(
        stream / "stream.json",
        {
            "sourceId": "voltage",
            "streamId": "input",
            "modality": "numeric",
            "dataSchemaId": "generic.numeric_batch/1",
            "nominalRateHz": 10,
            "units": "V",
            "dimensions": [1],
        },
    )
    jobs = []
    for label, start, end in (("Rest", 0, 1_900_000_000), ("Load", 2_000_000_000, 3_900_000_000)):
        result = run(
            package,
            JobParams(
                command="features",
                start_session_ns=start,
                end_session_ns=end,
                overwrite_job_id=label.lower(),
            ),
        )
        assert result.status in {"completed", "completed_with_warnings"}
        listing = list_feature_tables(result.job_dir)
        assert len(listing["tables"]) == 1
        table = listing["tables"][0]
        assert table["sourceId"] == "voltage" and table["streamId"] == "input"
        jobs.append(FeatureTableInput(label, result.job_dir, table["relativePath"]))
    result = collect_feature_tables(
        jobs,
        tmp_path / "consumer",
        columns=["t_start_ns", "signal_mean", "gap_fraction"],
    )
    frame = parquet.read_table(tmp_path / "consumer/table.parquet").to_pandas()
    means = frame.groupby("capture_condition")["signal_mean"].mean().to_dict()
    assert means == {"Load": 5.0, "Rest": 1.0}
    assert set(frame["capture_source_id"]) == {"voltage"}
    assert frame["capture_scope_start_ns"].unique().tolist() == [0, 2_000_000_000]
    assert result["selection"]["rows"] == len(frame)
