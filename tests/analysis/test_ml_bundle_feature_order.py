# SPDX-License-Identifier: GPL-3.0-only
"""Nearest-feature alignment retains real timestamp/value pairs in any row order."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from capture_analysis.ml_bundle.job import DEFAULT_TARGET_COLUMNS, run_ml_bundle_job

ROOT = Path(__file__).resolve().parents[2]
FEATURE_RELATIVE = "features/radar/radar.fixture/energy.parquet"


def _seed_teacher(package: Path, *, base: int = 0, unit: int = 100_000_000) -> Path:
    teacher = {
        "session_time_ns": [base + index * unit for index in range(11)],
        "valid_elbow_L": [index != 3 for index in range(11)],
        "valid_elbow_R": [True] * 11,
    }
    for multiple, column in enumerate(DEFAULT_TARGET_COLUMNS, 1):
        teacher[column] = [float(multiple * index * 10) for index in range(11)]
    path = package / "processing/jobs/kin/kinematics/kinematics.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame(teacher).to_parquet(path, index=False)
    return path


def _seed_features(package: Path, data: dict) -> Path:
    path = package / "processing/jobs/feat" / FEATURE_RELATIVE
    path.parent.mkdir(parents=True)
    pd.DataFrame(data).to_parquet(path, index=False)
    return path


def _read_outputs(work: Path, outputs: list[dict]) -> pd.DataFrame:
    for row in outputs:
        content = (work / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
    manifest = json.loads((work / "ml_bundle/manifest.json").read_bytes())
    windows = work / "ml_bundle/windows.parquet"
    assert manifest["sha256"]["windows.parquet"] == hashlib.sha256(windows.read_bytes()).hexdigest()
    assert manifest["analysisGrids"][0]["method"] == "nearest_feature_window_median_targets"
    assert manifest["normalization"] == {"input": "none", "target": "none"}
    return pd.read_parquet(windows)


def _run_bundle(tmp_path: Path, data: dict, *, base: int = 0, unit: int = 100_000_000):
    package = tmp_path / "package"
    inputs = [_seed_teacher(package, base=base, unit=unit), _seed_features(package, data)]
    before = {path: path.read_bytes() for path in inputs}
    work = tmp_path / "result"
    outputs, warnings = [], []
    run_ml_bundle_job(
        package,
        work,
        SimpleNamespace(session_id="feature-order-fixture"),
        kinematics_job_id="kin",
        features_job_id="feat",
        window_sec=2 * unit / 1e9,
        hop_sec=2 * unit / 1e9,
        outputs=outputs,
        warnings=warnings,
    )
    assert warnings == []
    assert {path: path.read_bytes() for path in inputs} == before
    windows = _read_outputs(work, outputs)
    assert windows["session_time_ns"].tolist() == [base + index * unit for index in (1, 3, 5, 7, 9)]
    assert windows["theta_elbow_flex_L"].tolist() == [10.0, 30.0, 50.0, 70.0, 90.0]
    assert windows["valid_mask"].tolist() == [True, False, True, True, True]
    assert windows["feature_stream_id"].tolist() == ["radar.fixture"] * 5
    return windows


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1), (2, 1, 0), (1, 2, 0)])
@pytest.mark.parametrize(("base", "unit"), [(0, 100_000_000), (2**53 + 1, 100_000_000)])
def test_nearest_values_follow_timestamp_pairs_in_any_row_order(
    tmp_path: Path,
    order: tuple[int, ...],
    base: int,
    unit: int,
) -> None:
    times, energy = [base + index * unit for index in (0, 5, 10)], [10.0, 20.0, 30.0]
    windows = _run_bundle(
        tmp_path,
        {"t_ns": [times[i] for i in order], "energy": [energy[i] for i in order]},
        base=base,
        unit=unit,
    )
    assert windows["motion_energy"].tolist() == [10.0, 20.0, 20.0, 20.0, 30.0]


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1)])
def test_adjacent_nanoseconds_above_float_precision_keep_exact_pairing(
    tmp_path: Path,
    order: tuple[int, ...],
) -> None:
    base = 2**53 + 1
    center = base + 500_000_000
    times, energy = [center - 1, center, center + 1], [11.0, 22.0, 33.0]
    windows = _run_bundle(
        tmp_path,
        {"t_ns": [times[i] for i in order], "energy": [energy[i] for i in order]},
        base=base,
    )
    assert windows["motion_energy"].tolist() == [11.0, 11.0, 22.0, 33.0, 33.0]


@pytest.mark.parametrize("order", [(0, 1, 2, 3), (3, 1, 0, 2)])
def test_duplicate_feature_times_keep_their_relative_order(
    tmp_path: Path,
    order: tuple[int, ...],
) -> None:
    times = [0, 500_000_000, 500_000_000, 1_000_000_000]
    energy = [10.0, 21.0, 22.0, 30.0]
    windows = _run_bundle(
        tmp_path,
        {"t_ns": [times[i] for i in order], "energy": [energy[i] for i in order]},
    )
    # Exact matches use the first equal row. A query just after uses the last
    # preceding equal row, retaining the existing searchsorted selection rule.
    assert windows["motion_energy"].tolist() == [10.0, 21.0, 21.0, 22.0, 30.0]


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_equal_distance_still_selects_the_later_timestamp(
    tmp_path: Path,
    order: tuple[int, ...],
) -> None:
    times, energy = [0, 1_000_000_000], [10.0, 30.0]
    windows = _run_bundle(
        tmp_path,
        {"t_ns": [times[i] for i in order], "energy": [energy[i] for i in order]},
    )
    assert windows["motion_energy"].tolist() == [10.0, 10.0, 30.0, 30.0, 30.0]


def test_numeric_column_mean_keeps_its_timestamp_pair(tmp_path: Path) -> None:
    windows = _run_bundle(
        tmp_path,
        {
            "session_time_ns": [1_000_000_000, 0, 500_000_000],
            "left": [5.0, 1.0, 3.0],
            "right": [7.0, 3.0, 5.0],
            "valid": [1, 1, 1],
            "valid_fraction": [1.0, 1.0, 1.0],
        },
    )
    assert windows["motion_energy"].tolist() == [2.0, 4.0, 4.0, 4.0, 6.0]


def test_single_feature_row_remains_usable(tmp_path: Path) -> None:
    windows = _run_bundle(tmp_path, {"t_ns": [500_000_000], "energy": [42.0]})
    assert windows["motion_energy"].tolist() == [42.0] * 5


def test_native_radar_features_reach_job_api_with_embedded_times_out_of_order(
    tmp_path: Path,
) -> None:
    import numpy as np
    from capture_analysis import JobParams, hash_sources_tree, run
    from capture_analysis.features.io import write_feature_table
    from capture_analysis.features.radar_frame import extract_radar_frame_features
    from capture_analysis.types import GapMask, StreamRef, TimeWindow
    from capture_protocol.generated.capture.v1.data import radar_frame_pb2
    from mcap.writer import CompressionType, Writer

    package = tmp_path / "recording.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", package)
    teacher = _seed_teacher(package)
    mcap_path = tmp_path / "embedded-session-order.mcap"
    with mcap_path.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start(profile="protobuf")
        schema = writer.register_schema(name="radar.frame/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="radar.fixture",
            message_encoding="protobuf",
            schema_id=schema,
        )
        for index, (timestamp, amplitude) in enumerate(
            [(1_000_000_000, 3), (0, 1), (500_000_000, 2)],
        ):
            frame = radar_frame_pb2.RadarFrame(
                num_rx=1,
                num_chirps=1,
                num_samples=1,
                sample_encoding="uint16_le_raw_interleaved",
                payload=np.asarray([amplitude], dtype="<u2").tobytes(),
            )
            frame.timing.session_time_ns = timestamp
            writer.add_message(
                channel_id=channel,
                log_time=index + 1,
                publish_time=index + 1,
                data=frame.SerializeToString(),
            )
        writer.finish()
    mcap_before = mcap_path.read_bytes()

    stream = StreamRef(
        source_id="radar",
        stream_id="radar.fixture",
        modality="radar",
        data_schema_id="radar.frame/1",
        nominal_rate_hz=2.0,
        units="adc_counts",
        mcap_paths=(mcap_path,),
    )
    window = TimeWindow(0, 1_000_000_000)
    features, columns, valid_fraction, radar_warnings = extract_radar_frame_features(
        stream,
        window,
        GapMask(stream, window),
        store_rd_every_n_frames=0,
    )
    assert features["t_ns"].tolist() == [1_000_000_000, 0, 500_000_000]
    assert features["energy"].tolist() == [9.0, 1.0, 4.0]
    assert mcap_path.read_bytes() == mcap_before
    assert valid_fraction == 1.0
    assert "radar timing is host-arrival; not a hardware-sync claim" in radar_warnings
    feature_dir = package / "processing/jobs/feat"
    write_feature_table(
        feature_dir,
        FEATURE_RELATIVE,
        features,
        feature_schema_version=1,
        columns_meta=columns,
        schema_doc={},
        outputs=[],
    )
    feature_path = feature_dir / FEATURE_RELATIVE
    inputs = {path: path.read_bytes() for path in (teacher, mcap_path, feature_path)}
    raw_before = hash_sources_tree(package)
    result = run(
        package,
        JobParams(
            command="ml_bundle",
            overwrite_job_id="ordered-features",
            extra={
                "kinematics_job_id": "kin",
                "features_job_id": "feat",
                "window_sec": 0.2,
                "hop_sec": 0.2,
            },
        ),
    )
    assert hash_sources_tree(package) == raw_before
    assert {path: path.read_bytes() for path in inputs} == inputs
    saved = json.loads((result.job_dir / "job_manifest.json").read_bytes())
    assert saved == result.manifest
    windows = _read_outputs(result.job_dir, saved["outputs"])
    assert windows["motion_energy"].tolist() == [1.0, 4.0, 4.0, 4.0, 9.0]
    assert windows["theta_elbow_flex_L"].tolist() == [10.0, 30.0, 50.0, 70.0, 90.0]
    assert windows["valid_mask"].tolist() == [True, False, True, True, True]
