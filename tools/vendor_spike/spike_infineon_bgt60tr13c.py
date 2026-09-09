# SPDX-License-Identifier: GPL-3.0-only
"""Standalone Infineon BGT60TR13C spike (VENDOR_SPIKE.md).

Requires the Infineon Radar SDK Python wheel (`ifxradarsdk`) from RDK 3.6.x.
Does not talk to capture_daemon.

Usage:
  & "$env:LOCALAPPDATA\\Programs\\Python\\Python312\\python.exe" `
    tools/vendor_spike/spike_infineon_bgt60tr13c.py [--seconds 8] [--write-notes]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _require_sdk():
    try:
        from ifxradarsdk import get_version, get_version_full  # noqa: F401
        from ifxradarsdk.fmcw import DeviceFmcw  # noqa: F401
        from ifxradarsdk.fmcw.types import (  # noqa: F401
            FmcwSequenceChirp,
            FmcwSimpleSequenceConfig,
        )
    except ImportError as exc:
        print(
            "ifxradarsdk not installed. Install the Windows wheel from RDK, e.g.\n"
            r'  pip install "C:\Users\<you>\Infineon\Tools\radar_sdk_3.6.5'
            r'\radar_sdk\python_wheels\ifxradarsdk-*-win_amd64.whl"',
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def run_spike(*, seconds: float) -> dict:
    import numpy as np
    from ifxradarsdk import get_version, get_version_full
    from ifxradarsdk.fmcw import DeviceFmcw
    from ifxradarsdk.fmcw.types import FmcwSequenceChirp, FmcwSimpleSequenceConfig

    # Faster than the stock raw_data example (~3 Hz) so we can measure rate
    # and see fan motion in the range profile within a few seconds.
    config = FmcwSimpleSequenceConfig(
        frame_repetition_time_s=50e-3,
        chirp_repetition_time_s=500e-6,
        num_chirps=32,
        tdm_mimo=False,
        chirp=FmcwSequenceChirp(
            start_frequency_Hz=60e9,
            end_frequency_Hz=61.5e9,
            sample_rate_Hz=2e6,
            num_samples=128,
            rx_mask=7,  # three RX antennas on TR13C
            tx_mask=1,
            tx_power_level=31,
            lp_cutoff_Hz=500000,
            hp_cutoff_Hz=80000,
            if_gain_dB=33,
        ),
    )

    report: dict = {
        "sdk_version": get_version(),
        "sdk_version_full": get_version_full(),
        "host_os": sys.platform,
        "python": sys.version.split()[0],
        "config": {
            "frame_repetition_time_s": config.frame_repetition_time_s,
            "num_chirps": config.num_chirps,
            "num_samples": config.chirp.num_samples,
            "rx_mask": config.chirp.rx_mask,
            "tx_mask": config.chirp.tx_mask,
            "start_frequency_Hz": config.chirp.start_frequency_Hz,
            "end_frequency_Hz": config.chirp.end_frequency_Hz,
        },
        "frames": [],
    }

    with DeviceFmcw() as device:
        report["board_uuid"] = device.get_board_uuid()
        report["sensor_type"] = str(device.get_sensor_type())
        try:
            report["temperature_C"] = float(device.get_temperature())
        except Exception as exc:  # noqa: BLE001
            report["temperature_error"] = f"{type(exc).__name__}: {exc}"

        sequence = device.create_simple_sequence(config)
        device.set_acquisition_sequence(sequence)
        chirp_loop = sequence.loop.sub_sequence.contents
        metrics = device.metrics_from_sequence(chirp_loop)
        report["metrics"] = {
            "max_range_m": float(metrics.max_range_m),
            "max_speed_m_s": float(metrics.max_speed_m_s),
            "range_resolution_m": float(metrics.range_resolution_m),
            "speed_resolution_m_s": float(metrics.speed_resolution_m_s),
        }

        print(f"SDK {report['sdk_version_full']}")
        print(f"Sensor {report['sensor_type']}  uuid={report['board_uuid']}")
        print(
            f"metrics max_range={report['metrics']['max_range_m']:.2f} m  "
            f"max_speed={report['metrics']['max_speed_m_s']:.2f} m/s"
        )

        t0 = time.perf_counter_ns()
        wall0 = time.time()
        deadline = wall0 + seconds
        energy_series: list[float] = []
        peak_bin_series: list[int] = []
        intervals_ms: list[float] = []
        last_ns: int | None = None
        seq = 0
        first_sample_latency_ms: float | None = None

        arm_ns = time.perf_counter_ns()
        while time.time() < deadline:
            frame_contents = device.get_next_frame()
            now_ns = time.perf_counter_ns()
            if first_sample_latency_ms is None:
                first_sample_latency_ms = (now_ns - arm_ns) / 1e6
            if last_ns is not None:
                intervals_ms.append((now_ns - last_ns) / 1e6)
            last_ns = now_ns

            # frame_contents: list of (num_rx, num_chirps, num_samples)
            frame = frame_contents[0]
            # Range profile proxy: mean |FFT| across chirps on RX0
            chirp0 = np.asarray(frame[0], dtype=np.float32)
            windowed = chirp0 * np.hanning(chirp0.shape[-1])
            spec = np.fft.rfft(windowed, axis=-1)
            profile = np.mean(np.abs(spec), axis=0)
            energy = float(np.sum(profile**2))
            peak_bin = int(np.argmax(profile))
            energy_series.append(energy)
            peak_bin_series.append(peak_bin)

            if seq < 5 or seq % 10 == 0:
                print(
                    f"frame={seq:04d} host_qpc_ns={now_ns - t0} "
                    f"shape={tuple(frame.shape)} energy={energy:.3e} "
                    f"peak_bin={peak_bin}"
                )
            seq += 1

        elapsed_s = (time.perf_counter_ns() - t0) / 1e9
        rate_hz = seq / elapsed_s if elapsed_s > 0 else 0.0
        energy_cv = (
            statistics.pstdev(energy_series) / statistics.fmean(energy_series)
            if len(energy_series) > 1 and statistics.fmean(energy_series) > 0
            else 0.0
        )
        report["acquisition"] = {
            "requested_seconds": seconds,
            "frames": seq,
            "elapsed_s": elapsed_s,
            "measured_rate_hz": rate_hz,
            "first_sample_latency_ms": first_sample_latency_ms,
            "interval_ms_p50": (float(statistics.median(intervals_ms)) if intervals_ms else None),
            "interval_ms_p95": (
                float(sorted(intervals_ms)[int(0.95 * (len(intervals_ms) - 1))])
                if len(intervals_ms) >= 2
                else None
            ),
            "energy_mean": float(statistics.fmean(energy_series)) if energy_series else 0.0,
            "energy_cv": float(energy_cv),
            "peak_bin_mode": (
                max(set(peak_bin_series), key=peak_bin_series.count) if peak_bin_series else None
            ),
            "payload_bytes_per_frame_est": int(np.asarray(frame_contents[0]).nbytes) if seq else 0,
        }
        print(
            f"done frames={seq} rate={rate_hz:.2f} Hz "
            f"first_latency={first_sample_latency_ms:.1f} ms "
            f"energy_cv={energy_cv:.3f} (fan motion => higher CV)"
        )
    return report


def write_notes(report: dict) -> Path:
    notes_dir = ROOT / "docs" / "design" / "adapters" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / f"infineon_bgt60tr13c_{date.today().isoformat()}.md"
    acq = report.get("acquisition", {})
    metrics = report.get("metrics", {})
    body = f"""# Infineon BGT60TR13C spike notes — {date.today().isoformat()}

Auto-generated by `tools/vendor_spike/spike_infineon_bgt60tr13c.py`.
Host had a fan pointed at the sensor during capture.

## Identity

| Field | Value |
|---|---|
| Sensor | `{report.get("sensor_type")}` |
| Board UUID | `{report.get("board_uuid")}` |
| SDK | `{report.get("sdk_version_full")}` |
| Python | `{report.get("python")}` |
| Temperature read | `{report.get("temperature_C", report.get("temperature_error"))}` |

## Metrics (from SDK)

```json
{json.dumps(metrics, indent=2)}
```

## Acquisition

```json
{json.dumps(acq, indent=2)}
```

## Observations for adapter checklist

1. Discovery: `DeviceFmcw()` opens the first attached FMCW board; UUID via `get_board_uuid()`.
2. Threading: blocking `get_next_frame()` on the calling thread (poll model).
3. Timestamps: SDK frame has no host QPC stamp in this spike.
   Host `perf_counter_ns` is recorded at pull time only.
4. Start/stop: `create_simple_sequence` → `set_acquisition_sequence` → `get_next_frame` loop.
   The context manager tears down.
5. Sync: not exercised — do not claim multi-radar hardware sync.
"""
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument(
        "--write-notes",
        action="store_true",
        help="Write docs/design/adapters/notes/infineon_bgt60tr13c_YYYY-MM-DD.md",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path for machine-readable report JSON",
    )
    args = parser.parse_args()
    _require_sdk()
    report = run_spike(seconds=args.seconds)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("wrote", args.json_out)
    if args.write_notes:
        notes = write_notes(report)
        print("wrote", notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
