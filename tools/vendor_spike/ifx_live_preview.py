# SPDX-License-Identifier: GPL-3.0-only
"""Pump live BGT60TR13C range-Doppler into a file the daemon can preview.

Run alongside capture_daemon with CAPTURE_IFX_PREVIEW=1. Does not use the
worker pipe yet — this is the interim bridge until radar.ifx worker lands.

Output (atomic replace):
  %LOCALAPPDATA%\\CaptureSuite\\ifx_radar_preview\\meta.json
  %LOCALAPPDATA%\\CaptureSuite\\ifx_radar_preview\\matrix.f32
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np


def preview_dir() -> Path:
    override = os.environ.get("CAPTURE_IFX_PREVIEW_DIR")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "CaptureSuite" / "ifx_radar_preview"


def range_doppler_db(frame_rx0: np.ndarray, mti_state: list[np.ndarray | None]) -> np.ndarray:
    """Minimal RD map for preview (RX0). Not a copy of Infineon DopplerAlgo."""
    data = np.asarray(frame_rx0, dtype=np.float32)
    data = data - np.mean(data)
    if mti_state[0] is None:
        mti_state[0] = np.zeros_like(data)
    mti = data - mti_state[0]
    mti_state[0] = 0.8 * data + 0.2 * mti_state[0]
    # range FFT per chirp
    win_r = np.hanning(data.shape[1]).astype(np.float32)
    range_fft = np.fft.rfft(mti * win_r, axis=1)
    # doppler FFT across chirps
    win_d = np.hanning(data.shape[0]).astype(np.float32).reshape(-1, 1)
    rd = np.fft.fftshift(np.fft.fft(range_fft * win_d, axis=0), axes=0)
    mag = 20.0 * np.log10(np.abs(rd) + 1e-6)
    return mag.astype(np.float32)


def atomic_write(meta: dict, matrix: np.ndarray, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    mat_tmp = directory / "matrix.f32.tmp"
    meta_tmp = directory / "meta.json.tmp"
    mat_tmp.write_bytes(matrix.astype("<f4", copy=False).tobytes(order="C"))
    meta_tmp.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    mat_tmp.replace(directory / "matrix.f32")
    meta_tmp.replace(directory / "meta.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=12.0, help="frame rate target")
    parser.add_argument("--source-id", default="sim.radar.1")
    args = parser.parse_args()

    try:
        from ifxradarsdk import get_version_full
        from ifxradarsdk.fmcw import DeviceFmcw
        from ifxradarsdk.fmcw.types import FmcwMetrics, FmcwSimpleSequenceConfig
    except ImportError as exc:
        print("ifxradarsdk missing — install RDK wheel first", file=sys.stderr)
        raise SystemExit(2) from exc

    out = preview_dir()
    print(f"writing preview to {out}")
    print(f"SDK {get_version_full()}")

    mti_state: list[np.ndarray | None] = [None]
    seq = 0
    with DeviceFmcw() as device:
        print("sensor", device.get_sensor_type(), "uuid", device.get_board_uuid())
        info = device.get_sensor_information()
        num_rx = int(info["num_rx_antennas"])
        metrics = FmcwMetrics(
            range_resolution_m=0.15,
            max_range_m=4.8,
            max_speed_m_s=2.45,
            speed_resolution_m_s=0.2,
            center_frequency_Hz=60_750_000_000,
        )
        sequence = device.create_simple_sequence(FmcwSimpleSequenceConfig())
        sequence.loop.repetition_time_s = 1.0 / max(1.0, args.hz)
        chirp_loop = sequence.loop.sub_sequence.contents
        device.sequence_from_metrics(metrics, chirp_loop)
        chirp = chirp_loop.loop.sub_sequence.contents.chirp
        chirp.sample_rate_Hz = 1_000_000
        chirp.rx_mask = (1 << num_rx) - 1
        chirp.tx_mask = 1
        chirp.tx_power_level = 31
        chirp.if_gain_dB = 33
        chirp.lp_cutoff_Hz = 500000
        chirp.hp_cutoff_Hz = 80000
        device.set_acquisition_sequence(sequence)

        while True:
            frame = device.get_next_frame()[0]
            rd = range_doppler_db(frame[0], mti_state)
            # Match UI contract-ish size: downsample to <= 64 x 128
            rows, cols = rd.shape
            target_r, target_c = 64, 128
            rr = np.linspace(0, rows - 1, min(target_r, rows)).astype(int)
            cc = np.linspace(0, cols - 1, min(target_c, cols)).astype(int)
            small = rd[np.ix_(rr, cc)]
            # normalize 0..1 for MATRIX_2D display_min/max
            lo = float(np.percentile(small, 5))
            hi = float(np.percentile(small, 99))
            if hi <= lo:
                hi = lo + 1.0
            norm = np.clip((small - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)
            host_ns = time.perf_counter_ns()
            meta = {
                "source_id": args.source_id,
                "uuid": device.get_board_uuid(),
                "sensor": str(device.get_sensor_type()),
                "rows": int(norm.shape[0]),
                "cols": int(norm.shape[1]),
                "sequence": seq,
                "host_qpc_ns": host_ns,
                "display_min": 0.0,
                "display_max": 1.0,
                "dtype": "float32_le",
            }
            atomic_write(meta, norm, out)
            if seq % 20 == 0:
                print(
                    f"seq={seq} shape={norm.shape} peak={float(norm.max()):.3f} "
                    f"-> {out / 'meta.json'}"
                )
            seq += 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("stopped")
        raise SystemExit(0) from None
