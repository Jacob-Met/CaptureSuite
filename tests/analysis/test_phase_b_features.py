# SPDX-License-Identifier: GPL-3.0-only
"""Phase B: analytic feature tests, gap masks, end-to-end MCAP job."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("matplotlib")
pytest.importorskip("mcap")


def test_emg_analytic_rms_mav() -> None:
    from capture_analysis.features.emg import analytic_mav, analytic_rms, extract_emg_features
    from capture_analysis.types import GapMask, LoadedEmg, StreamRef, TimeWindow

    fs = 2000.0
    amp = 2.0
    t = np.arange(0, 1.0, 1 / fs)
    sig = (amp * np.sin(2 * np.pi * 50.0 * t)).astype(np.float32)
    loaded = LoadedEmg(
        channel_ids=["ch0"],
        t_sample_ns=(t * 1e9).astype(np.int64),
        X=sig.reshape(1, -1),
        fs_hz=fs,
        units="mV",
    )
    stream = StreamRef("sim.emg.main", "batch", "emg", "emg.batch/1", fs, "mV", dimensions=(1,))
    window = TimeWindow(0, int(1e9), "full")
    mask = GapMask(stream=stream, window=window, gaps=[], policy="mask")
    df, _meta, vf = extract_emg_features(loaded, mask, window_s=1.0, hop_s=1.0)
    assert vf == 1.0
    assert not df.empty
    rms = float(df.iloc[0]["ch0_rms"])
    mav = float(df.iloc[0]["ch0_mav"])
    assert abs(rms - analytic_rms(amp)) < 1e-3
    assert abs(mav - analytic_mav(amp)) < 1e-2


def test_gap_mask_valid_fraction() -> None:
    from capture_analysis.types import GapInterval, GapMask, StreamRef, TimeWindow
    from capture_analysis.windows import valid_fraction, validity_mask

    stream = StreamRef("s", "st", "emg", "emg.batch/1", 1000.0, "mV")
    window = TimeWindow(0, 1_000_000_000, "full")
    gaps = [
        GapInterval("s", "st", "disconnect", 250_000_000, 750_000_000, True),
    ]
    mask = GapMask(stream=stream, window=window, gaps=gaps, policy="mask")
    t = np.arange(0, 1_000_000_000, 1_000_000, dtype=np.int64)
    valid = validity_mask(t, mask)
    # ~50% invalid in the middle
    vf = valid_fraction(valid)
    assert 0.4 < vf < 0.6


def test_gap_policy_fail() -> None:
    from capture_analysis.types import GapInterval, GapMask, StreamRef, TimeWindow
    from capture_analysis.windows import enforce_gap_policy, validity_mask

    stream = StreamRef("s", "st", "emg", "emg.batch/1", 1000.0, "mV")
    window = TimeWindow(0, 1_000_000_000, "full")
    gaps = [GapInterval("s", "st", "disconnect", 0, 100_000_000, True)]
    mask = GapMask(stream=stream, window=window, gaps=gaps, policy="fail")
    t = np.arange(0, 1_000_000_000, 10_000_000, dtype=np.int64)
    valid = validity_mask(t, mask)
    with pytest.raises(RuntimeError, match="gap_policy=fail"):
        enforce_gap_policy(mask, valid)


def _write_emg_imu_package(dest: Path, *, second_sensor_frames: int | None = None) -> Path:
    """Build a tiny package with real protobuf MCAP for emg+imu."""
    shutil.copytree(FIXTURE, dest)
    # Remove placeholder mcaps
    for p in dest.rglob("*.mcap"):
        p.unlink()

    from capture_protocol.generated.capture.v1.data import emg_batch_pb2, imu_frame_pb2
    from mcap.writer import Writer

    fs = 2000.0
    n = 400  # 0.2 s
    amp = 1.5
    t = np.arange(n) / fs
    samples = (amp * np.sin(2 * np.pi * 40.0 * t)).astype(np.float32)
    # 2 channels
    mat = np.stack([samples, samples * 0.5], axis=0)

    emg = emg_batch_pb2.EmgBatch()
    emg.timing.session_time_ns = 0
    emg.timing.sequence_number = 1
    emg.first_sample_index = 0
    emg.sample_count = n
    emg.channel_ids.extend(["ch0", "ch1"])
    emg.samples_f32_le = mat.astype("<f4").tobytes()

    emg_path = (
        dest
        / "sources"
        / "sim.emg.main"
        / "streams"
        / "sim.emg.main.batch"
        / "segments"
        / "000000.mcap"
    )
    emg_path.parent.mkdir(parents=True, exist_ok=True)
    with emg_path.open("wb") as fh:
        w = Writer(fh)
        w.start(profile="", library="test")
        sid = w.register_schema(name="emg.batch/1", encoding="protobuf", data=b"")
        cid = w.register_channel(topic="emg", message_encoding="protobuf", schema_id=sid)
        payload = emg.SerializeToString()
        w.add_message(channel_id=cid, log_time=0, data=payload, publish_time=0)
        w.finish()

    # Update stream.json channel dims
    stream_json = emg_path.parents[1] / "stream.json"
    doc = json.loads(stream_json.read_text(encoding="utf-8"))
    doc["dimensions"] = [2]
    stream_json.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    imu_path = (
        dest
        / "sources"
        / "sim.imu.upper"
        / "streams"
        / "sim.imu.upper.frames"
        / "segments"
        / "000000.mcap"
    )
    imu_path.parent.mkdir(parents=True, exist_ok=True)
    with imu_path.open("wb") as fh:
        w = Writer(fh)
        w.start(profile="", library="test")
        sid = w.register_schema(name="imu.frame/1", encoding="protobuf", data=b"")
        cid = w.register_channel(topic="imu", message_encoding="protobuf", schema_id=sid)
        for i in range(30):
            msg = imu_frame_pb2.ImuFrame()
            msg.timing.session_time_ns = int(i * 1e9 / 60.0)
            msg.timing.sequence_number = i
            msg.frame_index = i
            s = msg.sensors.add()
            s.sensor_id = "pelvis"
            s.accel_x = 0.0
            s.accel_y = 0.0
            s.accel_z = 9.81
            s.gyro_x = 0.0
            s.gyro_y = 0.0
            s.gyro_z = 0.0
            s.qw = 1.0
            if second_sensor_frames is not None and i < second_sensor_frames:
                sternum = msg.sensors.add()
                sternum.sensor_id = "sternum"
                sternum.accel_z = 9.81
                sternum.qw = 1.0
            payload = msg.SerializeToString()
            t_ns = msg.timing.session_time_ns
            w.add_message(channel_id=cid, log_time=t_ns, data=payload, publish_time=t_ns)
        w.finish()

    # Fix duration in integrity
    integ = json.loads((dest / "integrity.json").read_text(encoding="utf-8"))
    integ["files"][0]["endSessionTimeNs"] = 500_000_000
    (dest / "integrity.json").write_text(json.dumps(integ, indent=2), encoding="utf-8")
    return dest


def test_job_all_on_synthetic_mcap(tmp_path: Path) -> None:
    from capture_analysis import JobParams, hash_sources_tree, run

    package = _write_emg_imu_package(tmp_path / "synth.mmsession")
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="all", overwrite_job_id="phase-b-all"))
    after = hash_sources_tree(package)
    assert before == after
    assert result.status in ("completed", "completed_with_warnings")
    feat = list((result.job_dir / "features").rglob("*.parquet"))
    figs = list((result.job_dir / "figures").glob("*.png"))
    assert feat, "expected feature parquet files"
    assert figs, "expected figure png files"
    assert (result.job_dir / "figures" / "sync_dashboard.png").is_file()
    assert (result.job_dir / "features" / "_schema.json").is_file()


def test_square_wave_zero_crossings() -> None:
    from capture_analysis.features.emg import extract_emg_features
    from capture_analysis.types import GapMask, LoadedEmg, StreamRef, TimeWindow

    fs = 1000.0
    f0 = 10.0
    T = 1.0
    t = np.arange(0, T, 1 / fs)
    sig = np.sign(np.sin(2 * np.pi * f0 * t)).astype(np.float32)
    loaded = LoadedEmg(
        channel_ids=["ch0"],
        t_sample_ns=(t * 1e9).astype(np.int64),
        X=sig.reshape(1, -1),
        fs_hz=fs,
        units="mV",
    )
    stream = StreamRef("s", "st", "emg", "emg.batch/1", fs, "mV", dimensions=(1,))
    window = TimeWindow(0, int(T * 1e9), "full")
    mask = GapMask(stream=stream, window=window, gaps=[], policy="mask")
    df, _, _ = extract_emg_features(loaded, mask, window_s=1.0, hop_s=1.0)
    zc = int(df.iloc[0]["ch0_zc"])
    expected = int(2 * f0 * T)
    assert abs(zc - expected) <= 2


def _replace_payload_segment(
    package: Path,
    *,
    source_id: str,
    stream_id: str,
    schema_name: str,
    message: object,
) -> None:
    """Replace only a copied fixture MCAP, with a genuine protobuf MCAP."""
    from mcap.writer import Writer

    target = package / "sources" / source_id / "streams" / stream_id / "segments" / "000000.mcap"
    with target.open("wb") as fh:
        writer = Writer(fh)
        writer.start(profile="", library="sample-qc-negative-control")
        sid = writer.register_schema(name=schema_name, encoding="protobuf", data=b"")
        cid = writer.register_channel(topic=source_id, message_encoding="protobuf", schema_id=sid)
        writer.add_message(
            channel_id=cid,
            log_time=0,
            publish_time=0,
            data=message.SerializeToString(),
        )
        writer.finish()


def test_real_emg_and_imu_payload_qc_reports_decoded_measurements(tmp_path: Path) -> None:
    from capture_analysis import collect_qc

    package = _write_emg_imu_package(tmp_path / "real-sensor.mmsession")
    report = collect_qc(package, inspect_payloads=True).to_dict()
    rows = {r["modality"]: r["payloadInspection"] for r in report["streams"]}
    assert rows["emg"]["status"] == "emg_samples_checked"
    assert rows["emg"]["sampleFramesChecked"] == 400
    assert rows["emg"]["channelIds"] == ["ch0", "ch1"]
    assert rows["emg"]["constantChannels"] == []
    assert rows["imu"]["status"] == "imu_frames_checked"
    assert rows["imu"]["sampleFramesChecked"] == 30
    assert rows["imu"]["sensorIds"] == ["pelvis"]
    assert rows["imu"]["zeroQuaternionSensorSamples"] == 0
    assert set(report["trafficLights"].values()) == {"ok"}


@pytest.mark.parametrize("case", ["nan", "bad_length", "flatline"])
def test_emg_payload_quality_is_derived_from_actual_float_bytes(tmp_path: Path, case: str) -> None:
    from capture_analysis import collect_qc
    from capture_protocol.generated.capture.v1.data import emg_batch_pb2

    package = _write_emg_imu_package(tmp_path / "emg.mmsession")
    emg = emg_batch_pb2.EmgBatch()
    emg.timing.session_time_ns = 0
    emg.channel_ids.extend(["ch0", "ch1"])
    emg.sample_count = 2
    if case == "nan":
        emg.samples_f32_le = np.asarray([1.0, float("nan"), 2.0, 3.0], dtype="<f4").tobytes()
    elif case == "bad_length":
        emg.samples_f32_le = np.asarray([1.0, 2.0, 3.0], dtype="<f4").tobytes()
    else:
        emg.samples_f32_le = np.zeros(4, dtype="<f4").tobytes()
    _replace_payload_segment(
        package,
        source_id="sim.emg.main",
        stream_id="sim.emg.main.batch",
        schema_name="emg.batch/1",
        message=emg,
    )

    report = collect_qc(package, inspect_payloads=True).to_dict()
    record = next(x for x in report["streams"] if x["modality"] == "emg")
    inspection = record["payloadInspection"]
    if case == "flatline":
        assert inspection["status"] == "emg_samples_checked"
        assert inspection["sampleFramesChecked"] == 2
        assert inspection["constantChannels"] == ["ch0", "ch1"]
        assert report["trafficLights"]["sim.emg.main"] == "ok"
    else:
        assert inspection["status"] == "failed"
        assert inspection["sampleFramesChecked"] is None
        assert "EMG" in inspection["detail"]
        assert report["trafficLights"]["sim.emg.main"] == "fail"


@pytest.mark.parametrize("case", ["nonfinite", "duplicate_sensor", "wrong_schema"])
def test_imu_payload_qc_rejects_real_protocol_failures(tmp_path: Path, case: str) -> None:
    from capture_analysis import collect_qc
    from capture_protocol.generated.capture.v1.data import emg_batch_pb2, imu_frame_pb2

    package = _write_emg_imu_package(tmp_path / "imu.mmsession")
    frame = imu_frame_pb2.ImuFrame()
    first = frame.sensors.add()
    first.sensor_id = "pelvis"
    first.accel_z = 9.81
    first.qw = 1.0
    if case == "nonfinite":
        first.gyro_x = float("inf")
    elif case == "duplicate_sensor":
        second = frame.sensors.add()
        second.sensor_id = "pelvis"
    if case == "wrong_schema":
        msg = emg_batch_pb2.EmgBatch(sample_count=1)
        msg.channel_ids.append("ch0")
        msg.samples_f32_le = np.asarray([1.0], dtype="<f4").tobytes()
        schema_name = "emg.batch/1"
    else:
        msg = frame
        schema_name = "imu.frame/1"
    _replace_payload_segment(
        package,
        source_id="sim.imu.upper",
        stream_id="sim.imu.upper.frames",
        schema_name=schema_name,
        message=msg,
    )

    report = collect_qc(package, inspect_payloads=True).to_dict()
    record = next(x for x in report["streams"] if x["modality"] == "imu")
    inspection = record["payloadInspection"]
    assert inspection["status"] == "failed"
    assert inspection["sampleFramesChecked"] is None
    assert report["trafficLights"]["sim.imu.upper"] == "fail"


@pytest.mark.parametrize(
    ("second_sensor_frames", "expected_light", "expected_exit"),
    [(30, "ok", 0), (15, "warn", 2)],
)
def test_imu_partial_sensor_presence_is_visible_in_qc_and_strict_cli(
    tmp_path: Path, second_sensor_frames: int, expected_light: str, expected_exit: int
) -> None:
    import subprocess
    import sys

    from capture_analysis import collect_qc, hash_sources_tree

    package = _write_emg_imu_package(
        tmp_path / "sensor-presence.mmsession", second_sensor_frames=second_sensor_frames
    )
    before = hash_sources_tree(package)
    report = collect_qc(package, inspect_payloads=True).to_dict()
    imu = next(s for s in report["streams"] if s["modality"] == "imu")
    evidence = imu["payloadInspection"]
    assert evidence["status"] == "imu_frames_checked"
    assert evidence["sampleFramesChecked"] == 30
    assert evidence["sensorIds"] == ["pelvis", "sternum"]
    assert evidence["sensorFramePresence"] == {
        "pelvis": {"framesPresent": 30, "totalFrames": 30},
        "sternum": {"framesPresent": second_sensor_frames, "totalFrames": 30},
    }
    assert evidence["partiallyPresentSensorIds"] == (
        [] if second_sensor_frames == 30 else ["sternum"]
    )
    assert report["trafficLights"]["sim.imu.upper"] == expected_light
    warnings = [w for w in report["warnings"] if "IMU sensor presence incomplete" in w]
    assert bool(warnings) is (second_sensor_frames == 15)
    if warnings:
        assert "sternum 15/30" in warnings[0]

    command = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        "qc",
        str(package),
        "--inspect-payloads",
        "--strict-warnings",
        "--overwrite-job-id",
        "sensor-presence-cli",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == expected_exit, completed.stdout + completed.stderr
    report_dir = package / "processing/jobs/sensor-presence-cli/reports"
    saved = json.loads((report_dir / "qc.json").read_text(encoding="utf-8"))
    assert saved["trafficLights"]["sim.imu.upper"] == expected_light
    saved_imu = next(s for s in saved["streams"] if s["modality"] == "imu")
    assert saved_imu["payloadInspection"]["sensorFramePresence"] == evidence["sensorFramePresence"]
    html = (report_dir / "qc.html").read_text(encoding="utf-8")
    assert "sensor presence (decoded frames): pelvis 30/30, sternum" in html
    assert f"sternum {second_sensor_frames}/30" in html
    assert hash_sources_tree(package) == before


def test_native_qc_cli_shows_real_emg_imu_payloads_without_changing_sources(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    from capture_analysis import hash_sources_tree

    package = _write_emg_imu_package(tmp_path / "operator.mmsession")
    before = hash_sources_tree(package)
    cli = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        "qc",
        str(package),
        "--inspect-payloads",
        "--strict-warnings",
        "--overwrite-job-id",
        "native-emg-imu",
    ]
    result = subprocess.run(cli, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    report_dir = package / "processing/jobs/native-emg-imu/reports"
    report = json.loads((report_dir / "qc.json").read_text(encoding="utf-8"))
    statuses = {s["modality"]: s["payloadInspection"]["status"] for s in report["streams"]}
    assert statuses == {"emg": "emg_samples_checked", "imu": "imu_frames_checked"}
    page = (report_dir / "qc.html").read_text(encoding="utf-8")
    assert "emg_samples_checked" in page
    assert "imu_frames_checked" in page
    assert "channels: ch0, ch1" in page
    assert "sensors: pelvis" in page
    assert hash_sources_tree(package) == before


@pytest.mark.parametrize(
    "qw,expected_light,expected_exit", [(0.0, "warn", 2), (1.0, "ok", 0), (-1.0, "ok", 0)]
)
def test_zero_orientation_warns_in_saved_report_and_cli(
    tmp_path: Path, qw: float, expected_light: str, expected_exit: int
) -> None:
    import subprocess
    import sys

    from capture_analysis import collect_qc, hash_sources_tree
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2

    package = _write_emg_imu_package(tmp_path / "orientation.mmsession")
    frame = imu_frame_pb2.ImuFrame()
    frame.sensors.add(sensor_id="pelvis", qw=qw, accel_z=9.81)
    _replace_payload_segment(
        package,
        source_id="sim.imu.upper",
        stream_id="sim.imu.upper.frames",
        schema_name="imu.frame/1",
        message=frame,
    )
    before = hash_sources_tree(package)
    report = collect_qc(package, inspect_payloads=True).to_dict()
    assert report["trafficLights"]["sim.imu.upper"] == expected_light
    imu = next(s for s in report["streams"] if s["modality"] == "imu")
    assert imu["payloadInspection"]["status"] == "imu_frames_checked"
    assert imu["payloadInspection"]["zeroQuaternionSensorSamples"] == int(qw == 0)
    assert imu["payloadInspection"]["zeroQuaternionSamplesBySensor"] == (
        {"pelvis": 1} if qw == 0 else {}
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/run_analysis.py"),
            "qc",
            str(package),
            "--inspect-payloads",
            "--strict-warnings",
            "--overwrite-job-id",
            "orientation-cli",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    reports = package / "processing/jobs/orientation-cli/reports"
    html = (reports / "qc.html").read_text()
    assert ("IMU orientation unavailable" in html) == (qw == 0)
    assert ("(pelvis: 1)" in html) == (qw == 0)
    assert hash_sources_tree(package) == before
