# SPDX-License-Identifier: GPL-3.0-only
"""Concurrent BGT60TR13C + BGT60LTR11AIP soak for multi-radar interference.

Runs both boards for --seconds, comparing solo vs concurrent acquisition rates
and TR13C range-profile energy stability. Does not talk to capture_daemon.

Exit 0 always when both boards open; prints a JSON summary and writes
tools/vendor_spike/out/dual_radar_interference_<stamp>.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class BoardStats:
    name: str
    uuid: str = ""
    frames: int = 0
    errors: list[str] = field(default_factory=list)
    intervals_ms: list[float] = field(default_factory=list)
    energy: list[float] = field(default_factory=list)
    first_latency_ms: float | None = None

    def summarize(self) -> dict:
        iv = self.intervals_ms
        en = self.energy
        dur_s = (sum(iv) / 1000.0) if iv else 0.0
        hz = (len(iv) / dur_s) if dur_s > 0 else 0.0
        out: dict = {
            "name": self.name,
            "uuid": self.uuid,
            "frames": self.frames,
            "hz": round(hz, 3),
            "interval_ms_p50": round(statistics.median(iv), 2) if iv else None,
            "interval_ms_p95": round(sorted(iv)[int(0.95 * (len(iv) - 1))], 2)
            if len(iv) >= 2
            else None,
            "first_latency_ms": self.first_latency_ms,
            "errors": self.errors[:20],
            "error_count": len(self.errors),
        }
        if en:
            mean = statistics.mean(en)
            out["energy_mean"] = mean
            out["energy_cv"] = (statistics.pstdev(en) / mean) if mean else None
        return out


def _tr13c_config():
    from ifxradarsdk.fmcw.types import FmcwSequenceChirp, FmcwSimpleSequenceConfig

    return FmcwSimpleSequenceConfig(
        frame_repetition_time_s=50e-3,
        chirp_repetition_time_s=500e-6,
        num_chirps=32,
        tdm_mimo=False,
        chirp=FmcwSequenceChirp(
            start_frequency_Hz=60e9,
            end_frequency_Hz=61.5e9,
            sample_rate_Hz=2e6,
            num_samples=128,
            rx_mask=7,
            tx_mask=1,
            tx_power_level=31,
            lp_cutoff_Hz=500000,
            hp_cutoff_Hz=80000,
            if_gain_dB=33,
        ),
    )


def run_tr13c(seconds: float, stop_event: threading.Event, stats: BoardStats) -> None:
    import numpy as np
    from ifxradarsdk.fmcw import DeviceFmcw

    try:
        with DeviceFmcw() as device:
            stats.uuid = device.get_board_uuid()
            seq = device.create_simple_sequence(_tr13c_config())
            device.set_acquisition_sequence(seq)
            arm = time.perf_counter_ns()
            last = None
            deadline = time.time() + seconds
            while time.time() < deadline and not stop_event.is_set():
                try:
                    frame_contents = device.get_next_frame()
                except Exception as exc:  # noqa: BLE001
                    stats.errors.append(f"{type(exc).__name__}: {exc}")
                    break
                now = time.perf_counter_ns()
                if stats.first_latency_ms is None:
                    stats.first_latency_ms = (now - arm) / 1e6
                if last is not None:
                    stats.intervals_ms.append((now - last) / 1e6)
                last = now
                frame = frame_contents[0]
                chirp0 = np.asarray(frame[0], dtype=np.float32)
                windowed = chirp0 * np.hanning(chirp0.shape[-1])
                spec = np.fft.rfft(windowed, axis=-1)
                profile = np.mean(np.abs(spec), axis=0)
                stats.energy.append(float(np.sum(profile**2)))
                stats.frames += 1
    except Exception as exc:  # noqa: BLE001
        stats.errors.append(f"open/run {type(exc).__name__}: {exc}")


def run_ltr11(seconds: float, stop_event: threading.Event, stats: BoardStats) -> None:
    from ifxradarsdk.ltr11 import DeviceLtr11

    try:
        with DeviceLtr11() as device:
            # UUID not always exposed; firmware description is enough for identity.
            try:
                fw = device.get_firmware_information()
                stats.uuid = str(fw.get("description", "ltr11"))
            except Exception:  # noqa: BLE001
                stats.uuid = "ltr11"
            try:
                cfg = device.get_config_defaults()
                device.set_config(cfg)
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"config {type(exc).__name__}: {exc}")
            try:
                device.start_acquisition()
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"start {type(exc).__name__}: {exc}")
                return
            arm = time.perf_counter_ns()
            last = None
            deadline = time.time() + seconds
            while time.time() < deadline and not stop_event.is_set():
                try:
                    device.get_next_frame()
                except Exception as exc:  # noqa: BLE001
                    stats.errors.append(f"{type(exc).__name__}: {exc}")
                    # keep going briefly; many LTR11 errors are transient
                    if "NO_DEVICE" in str(exc) or "COMMUNICATION" in str(exc).upper():
                        break
                    continue
                now = time.perf_counter_ns()
                if stats.first_latency_ms is None:
                    stats.first_latency_ms = (now - arm) / 1e6
                if last is not None:
                    stats.intervals_ms.append((now - last) / 1e6)
                last = now
                stats.frames += 1
            try:
                device.stop_acquisition()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        stats.errors.append(f"open/run {type(exc).__name__}: {exc}")


def phase(
    label: str,
    seconds: float,
    *,
    tr13c: bool,
    ltr11: bool,
) -> dict:
    print(f"\n=== {label} ({seconds:.1f}s) ===")
    stop = threading.Event()
    s13 = BoardStats("tr13c")
    s11 = BoardStats("ltr11")
    threads: list[threading.Thread] = []
    if tr13c:
        threads.append(threading.Thread(target=run_tr13c, args=(seconds, stop, s13), daemon=True))
    if ltr11:
        threads.append(threading.Thread(target=run_ltr11, args=(seconds, stop, s11), daemon=True))
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=seconds + 15)
    stop.set()
    elapsed = time.time() - t0
    result = {
        "phase": label,
        "requested_seconds": seconds,
        "wall_seconds": round(elapsed, 2),
        "tr13c": s13.summarize() if tr13c else None,
        "ltr11": s11.summarize() if ltr11 else None,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=12.0, help="per-phase duration")
    args = parser.parse_args()

    try:
        from ifxradarsdk import get_version_full
        from ifxradarsdk.fmcw import DeviceFmcw
        from ifxradarsdk.ltr11 import DeviceLtr11
    except ImportError as exc:
        print("ifxradarsdk not installed", file=sys.stderr)
        raise SystemExit(2) from exc

    fmcw = DeviceFmcw.get_list()
    ltr = DeviceLtr11.get_list()
    print(f"SDK {get_version_full()}")
    print(f"FMCW boards: {fmcw}")
    print(f"LTR11 boards: {ltr}")
    if not fmcw or not ltr:
        print("Need both boards attached.", file=sys.stderr)
        return 2

    seconds = max(4.0, float(args.seconds))
    report = {
        "stamp_utc": datetime.now(UTC).isoformat(),
        "sdk": get_version_full(),
        "fmcw_list": fmcw,
        "ltr11_list": ltr,
        "phases": [],
    }

    # Solo baselines, then concurrent, then solo again to catch sticky interference.
    report["phases"].append(phase("solo_tr13c", seconds, tr13c=True, ltr11=False))
    report["phases"].append(phase("solo_ltr11", seconds, tr13c=False, ltr11=True))
    report["phases"].append(phase("concurrent", seconds * 1.5, tr13c=True, ltr11=True))
    report["phases"].append(phase("solo_tr13c_after", seconds, tr13c=True, ltr11=False))

    # Verdict heuristics
    by = {p["phase"]: p for p in report["phases"]}
    solo = by["solo_tr13c"]["tr13c"]
    conc = by["concurrent"]["tr13c"]
    after = by["solo_tr13c_after"]["tr13c"]
    ltr_conc = by["concurrent"]["ltr11"]

    def rate_ok(a: dict | None, b: dict | None, tol: float = 0.15) -> bool:
        if not a or not b or not a.get("hz") or not b.get("hz"):
            return False
        return abs(a["hz"] - b["hz"]) / max(a["hz"], 1e-6) <= tol

    verdict = {
        "tr13c_rate_stable_under_concurrent": rate_ok(solo, conc),
        "tr13c_rate_recovers_after": rate_ok(solo, after),
        "ltr11_got_frames_concurrent": bool(ltr_conc and ltr_conc.get("frames", 0) > 0),
        "tr13c_concurrent_errors": (conc or {}).get("error_count", 0),
        "ltr11_concurrent_errors": (ltr_conc or {}).get("error_count", 0),
        "notes": [],
    }
    if not verdict["tr13c_rate_stable_under_concurrent"]:
        verdict["notes"].append(
            "TR13C frame rate shifted >15% during concurrent acquisition — "
            "treat multi-radar as unvalidated for RF/throughput."
        )
    if not verdict["ltr11_got_frames_concurrent"]:
        verdict["notes"].append("LTR11 produced no frames while TR13C was running.")
    if (
        solo
        and conc
        and solo.get("energy_cv") is not None
        and conc.get("energy_cv") is not None
        and conc["energy_cv"] > max(0.05, 3.0 * (solo["energy_cv"] or 0.0))
    ):
        verdict["notes"].append(
            "TR13C range-profile energy CV rose sharply under concurrent TX — "
            "possible RF interference (or motion in FOV)."
        )
    if not verdict["notes"]:
        verdict["notes"].append(
            "No strong throughput/error degradation observed at this config; "
            "still not a hardware-sync claim."
        )
    report["verdict"] = verdict
    print("\n=== VERDICT ===")
    print(json.dumps(verdict, indent=2))

    out_dir = ROOT / "tools" / "vendor_spike" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"dual_radar_interference_{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
