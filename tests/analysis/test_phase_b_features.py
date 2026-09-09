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


def _write_emg_imu_package(dest: Path) -> Path:
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
