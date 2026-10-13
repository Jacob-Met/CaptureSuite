# SPDX-License-Identifier: GPL-3.0-only
"""Feature CSV mirrors retain the parent and stem of the Parquet output."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from capture_analysis.features.io import write_feature_table  # noqa: E402


@pytest.mark.parametrize(
    ("relative", "parquet_relative", "csv_relative", "unrelated_relative"),
    [
        (
            "features/imu/sim.imu.upper/windows.parquet",
            "features/imu/sim.imu.upper/windows.parquet",
            "features/imu/sim.imu.upper/windows.csv",
            "features/imu/other/windows.csv",
        ),
        (
            "features/imu/sim.imu.parquet/windows.parquet",
            "features/imu/sim.imu.parquet/windows.parquet",
            "features/imu/sim.imu.parquet/windows.csv",
            "features/imu/sim.imu.csv/windows.csv",
        ),
        (
            "features/radar/source/frame.parquet.summary.parquet",
            "features/radar/source/frame.parquet.summary.parquet",
            "features/radar/source/frame.parquet.summary.csv",
            "features/radar/source/frame.csv.summary.csv",
        ),
        (
            "features.parquet/radar.parquet/source.parquet/window.parquet.part.parquet",
            "features.parquet/radar.parquet/source.parquet/window.parquet.part.parquet",
            "features.parquet/radar.parquet/source.parquet/window.parquet.part.csv",
            "features.csv/radar.csv/source.csv/window.csv.part.csv",
        ),
        (
            "features/測定.parquet α/windows.parquet",
            "features/測定.parquet α/windows.parquet",
            "features/測定.parquet α/windows.csv",
            "features/測定.csv α/windows.csv",
        ),
        (
            r"features\imu\sim.imu.parquet\windows.parquet",
            "features/imu/sim.imu.parquet/windows.parquet",
            "features/imu/sim.imu.parquet/windows.csv",
            "features/imu/sim.imu.csv/windows.csv",
        ),
    ],
)
def test_feature_csv_keeps_parent_and_stem(
    tmp_path: Path,
    relative: str,
    parquet_relative: str,
    csv_relative: str,
    unrelated_relative: str,
) -> None:
    unrelated = tmp_path / unrelated_relative
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_bytes(b"previous unrelated output\n")
    frame = pd.DataFrame(
        {
            "t_ns": [9_000_000_000_000_000_001, 9_000_000_000_000_000_003],
            "source_id": ["sim.imu.parquet", "測定.parquet α"],
            "value": [1.25, -2.5],
            "valid": [True, False],
        }
    )
    source_before = frame.copy(deep=True)
    columns = [{"name": "t_ns", "units": "ns"}]
    previous_output = {"relativePath": unrelated_relative, "kind": "existing"}
    outputs = [previous_output.copy()]
    schema = {"schemaId": "capture.analysis_feature_schema/1", "tables": {"prior": {"rows": 7}}}

    write_feature_table(
        tmp_path,
        relative,
        frame,
        feature_schema_version=1,
        columns_meta=columns,
        schema_doc=schema,
        outputs=outputs,
    )

    assert unrelated.read_bytes() == b"previous unrelated output\n"
    parquet_path = tmp_path / parquet_relative
    csv_path = tmp_path / csv_relative
    assert csv_path.is_file()
    pd.testing.assert_frame_equal(pd.read_parquet(parquet_path), frame)
    pd.testing.assert_frame_equal(pd.read_csv(csv_path), frame)
    pd.testing.assert_frame_equal(frame, source_before)
    assert outputs[0] == previous_output
    assert [item["relativePath"] for item in outputs[1:]] == [parquet_relative, csv_relative]
    for output, kind in zip(outputs[1:], ("feature_parquet", "feature_csv"), strict=True):
        data = (tmp_path / output["relativePath"]).read_bytes()
        assert output == {
            "relativePath": output["relativePath"],
            "kind": kind,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    assert schema["tables"] == {
        "prior": {"rows": 7},
        parquet_relative: {"featureSchemaVersion": 1, "columns": columns, "rows": 2},
    }
