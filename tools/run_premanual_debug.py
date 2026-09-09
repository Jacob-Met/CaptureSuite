# SPDX-License-Identifier: GPL-3.0-only
"""Orchestrate pre-manual camera/radar debug matrix; write a report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)

REPORT_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", str(ROOT / ".debug_runs"))) / "CaptureSuite" / "debug_runs"
)


def _ensure_idle() -> bool:
    """Best-effort: stop rehearsal / finalize any stuck session before next step."""
    sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]
    try:
        from capture_protocol.control_client import ControlClient
        from capture_protocol.generated.capture.v1 import control_pb2

        client = ControlClient(timeout_s=30.0)
        client.connect()
        try:
            client.stop_rehearsal()
        except Exception:
            pass
        view = client.get_session_view()
        # PREPARING/ARMING/RECORDING/STOPPING/RECOVERING/FAILED all need cleanup.
        active = {
            control_pb2.SESSION_STATE_PREPARING,
            control_pb2.SESSION_STATE_ARMING,
            control_pb2.SESSION_STATE_RECORDING,
            control_pb2.SESSION_STATE_STOPPING,
            control_pb2.SESSION_STATE_RECOVERING,
            control_pb2.SESSION_STATE_FAILED,
        }
        if view.state in active or view.rehearsal_active:
            try:
                tok = client.request_stop()
                if tok.confirmation_token:
                    client.stop_session(tok.confirmation_token)
            except Exception as exc:
                print(f"WARN: ensure_idle stop failed: {exc}")
                return False
            try:
                client.stop_rehearsal()
            except Exception:
                pass
        return True
    except Exception as exc:
        print(f"WARN: ensure_idle: {exc}")
        return False


def _restart_daemon() -> bool:
    """Hard reset daemon/workers when the control plane is wedged."""
    print("\n=== restart_daemon ===")
    subprocess.run(
        [
            "cmd",
            "/c",
            "taskkill /F /IM capture_daemon.exe >nul 2>&1 "
            "& taskkill /F /IM capture_worker_camera.exe >nul 2>&1 "
            "& taskkill /F /IM capture_worker_radar.exe >nul 2>&1 & exit /b 0",
        ],
        check=False,
    )
    time.sleep(2.0)
    log_path = ROOT / "daemon_premanual_out.txt"
    err_path = ROOT / "daemon_premanual_err.txt"
    env = os.environ.copy()
    env["CAPTURE_WORKER_STDERR_LOG"] = str(ROOT / "worker_err.txt")
    with log_path.open("w", encoding="utf-8") as out, err_path.open("w", encoding="utf-8") as err:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "tools" / "run-daemon-gstreamer.ps1"),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=out,
            stderr=err,
        )
    sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]
    from capture_protocol.control_client import ControlClient

    deadline = time.time() + 45.0
    while time.time() < deadline:
        try:
            client = ControlClient(timeout_s=5.0)
            client.connect()
            srcs = list(client.list_sources().sources)
            if any(s.source_type == "camera" for s in srcs) and any(
                s.source_id.startswith("radar.") for s in srcs
            ):
                print("daemon ready; sources", len(srcs))
                return True
        except Exception:
            time.sleep(0.5)
    print("FAIL: daemon did not become ready after restart")
    return False


def _run(label: str, argv: list[str], *, cwd: Path | None = None) -> dict:
    if not _ensure_idle():
        _restart_daemon()
    t0 = time.time()
    print(f"\n=== {label} ===")
    print("+", " ".join(argv))
    proc = subprocess.run(argv, cwd=str(cwd or ROOT))
    elapsed = time.time() - t0
    entry = {
        "label": label,
        "argv": argv,
        "exit_code": proc.returncode,
        "elapsed_s": round(elapsed, 2),
        "ok": proc.returncode == 0,
    }
    status = "PASS" if entry["ok"] else "FAIL"
    print(f"--- {status} {label} ({elapsed:.1f}s) ---")
    if not _ensure_idle():
        _restart_daemon()
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--continue",
        dest="keep_going",
        action="store_true",
        help="continue after failures",
    )
    ap.add_argument(
        "--skip-offline",
        action="store_true",
        help="skip pytest offline suite",
    )
    ap.add_argument(
        "--soak-s",
        type=float,
        default=300.0,
        help="medium soak duration seconds (default 300)",
    )
    ap.add_argument(
        "--skip-soak",
        action="store_true",
        help="skip 5-minute soak",
    )
    args = ap.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPORT_ROOT / f"premanual_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    steps: list[tuple[str, list[str]]] = []
    if not args.skip_offline:
        steps.append(
            (
                "pytest_protocol",
                [str(PY), "-m", "pytest", "tests/protocol", "-q"],
            )
        )

    steps.extend(
        [
            # No hardware — validates sim IMU/EMG MCAP fidelity first.
            ("sim_imu_emg_record", [str(PY), "tools/probe_sim_imu_emg_record.py"]),
            ("preflight", [str(PY), "tools/probe_preflight.py"]),
            # Restrict to Brio — rehearsing every virtual cam times out spawn.
            ("camera_preview", [str(PY), "tools/probe_camera_preview.py", "8", "brio"]),
            ("radar_preview_views", [str(PY), "tools/probe_radar_preview_views.py"]),
            ("radar_chirp_config", [str(PY), "tools/probe_radar_chirp_config.py"]),
            ("radar_doppler_live", [str(PY), "tools/probe_radar_doppler_live.py"]),
            ("dual_radar_record", [str(PY), "tools/probe_dual_radar_record.py"]),
            ("ltr11_record", [str(PY), "tools/probe_ltr11_record.py"]),
            ("soak_short", [str(PY), "tools/soak_camera_radar.py", "25"]),
            ("ui_actions", [str(PY), "tools/probe_ui_actions.py"]),
            ("worker_reopen", [str(PY), "tools/probe_worker_reopen.py"]),
        ]
    )

    for label, argv in steps:
        entry = _run(label, argv)
        results.append(entry)
        if not entry["ok"] and not args.keep_going:
            break

    # Export short soak package when that step passed (may not be last label).
    soak_short = next((r for r in results if r["label"] == "soak_short"), None)
    if soak_short and soak_short["ok"]:
        sessions = Path(os.environ.get("LOCALAPPDATA", "")) / "CaptureSuite" / "sessions"
        pkgs = sorted(
            sessions.glob("soak-cam-radar-*.mmsession"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if pkgs:
            export_out = out_dir / "export_short"
            entry = _run(
                "export_short",
                [
                    str(PY),
                    "tools/export_session.py",
                    str(pkgs[0]),
                    str(export_out),
                    "--verify",
                ],
            )
            results.append(entry)
            if not entry["ok"] and not args.keep_going:
                _write_report(out_dir, results)
                return 1

    aborted = any(not r["ok"] for r in results) and not args.keep_going
    if not aborted:
        # Fresh daemon before destructive fault probes.
        if not _restart_daemon():
            results.append(
                {
                    "label": "restart_before_faults",
                    "argv": [],
                    "exit_code": 1,
                    "elapsed_s": 0,
                    "ok": False,
                }
            )
            aborted = not args.keep_going
    fault_steps = [
        (
            "kill_camera_worker",
            [str(PY), "tools/probe_kill_worker_mid_record.py", "--kill", "camera"],
        ),
        (
            "kill_radar_worker",
            [str(PY), "tools/probe_kill_worker_mid_record.py", "--kill", "radar"],
        ),
        ("inject_disconnect", [str(PY), "tools/probe_inject_disconnect.py"]),
        (
            "open_recover_export",
            [str(PY), "tools/probe_open_recover_export.py"],
        ),
    ]
    for label, argv in fault_steps:
        if aborted:
            break
        entry = _run(label, argv)
        results.append(entry)
        if not entry["ok"] and not args.keep_going:
            aborted = True

    if not aborted and not args.skip_soak:
        entry = _run(
            "soak_5min",
            [str(PY), "tools/soak_camera_radar.py", str(args.soak_s)],
        )
        results.append(entry)
        if entry["ok"]:
            sessions = Path(os.environ.get("LOCALAPPDATA", "")) / "CaptureSuite" / "sessions"
            pkgs = sorted(
                sessions.glob("soak-cam-radar-*.mmsession"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if pkgs:
                results.append(
                    _run(
                        "export_5min",
                        [
                            str(PY),
                            "tools/export_session.py",
                            str(pkgs[0]),
                            str(out_dir / "export_5min"),
                            "--verify",
                        ],
                    )
                )

    _copy_stderr_tails(out_dir, results)
    report_path = _write_report(out_dir, results)
    failed = [r for r in results if not r["ok"]]
    print(f"\nReport: {report_path}")
    if failed:
        print(f"FAILED ({len(failed)}):", ", ".join(r["label"] for r in failed))
        return 1
    print("ALL PASS")
    return 0


def _copy_stderr_tails(out_dir: Path, results: list[dict]) -> None:
    """On any FAIL, archive worker/daemon stderr tails next to the report."""
    if not any(not r["ok"] for r in results):
        return
    triage = out_dir / "stderr_tails"
    triage.mkdir(parents=True, exist_ok=True)
    for name in (
        "worker_err.txt",
        "daemon_premanual_err.txt",
        "daemon_premanual_out.txt",
        "radar_worker_err.txt",
    ):
        src = ROOT / name
        if not src.is_file():
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
            (triage / name).write_text(text[-80_000:], encoding="utf-8")
        except OSError:
            pass


def _write_report(out_dir: Path, results: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "results": results,
        "manual_handoff": [
            "Physical USB unplug of camera mid-record",
            "Physical USB unplug of each radar mid-record",
            "Radar USB wedge under cable/hub stress if reopen-after-kill failed",
            "Unplug/replug TR13C after kill-radar PASS_WITH_BLOCKER; then Rescan",
            "UVC exposure/gain visual check in live preview",
            "Human/subject motion for Doppler usefulness (fan covered liveliness)",
            "Desktop Setup UI for radar.ifx/3 + camera.gstreamer/4 fields",
        ],
    }
    json_path = out_dir / "report.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_lines = [
        "# Pre-manual debug report",
        "",
        f"Generated: {payload['generated_utc']}",
        "",
        "| Step | Result | Seconds |",
        "|---|---|---|",
        "",
    ]
    # Drop accidental blank after header separator rewrite
    md_lines = [
        "# Pre-manual debug report",
        "",
        f"Generated: {payload['generated_utc']}",
        "",
        "| Step | Result | Seconds |",
        "|---|---|---|",
    ]
    for r in results:
        md_lines.append(f"| {r['label']} | {'PASS' if r['ok'] else 'FAIL'} | {r['elapsed_s']} |")
    md_lines.extend(["", "## Manual handoff", ""])
    for item in payload["manual_handoff"]:
        md_lines.append(f"- {item}")
    if any(not r["ok"] for r in results):
        md_lines.extend(["", "## Triage", "", f"See `{out_dir / 'stderr_tails'}` for log tails."])
    md_path = out_dir / "report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    # Also publish a stable summary name for handoff.
    summary = REPORT_ROOT / f"premanual_summary_{datetime.now(UTC).strftime('%Y%m%d')}.md"
    summary.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path


if __name__ == "__main__":
    raise SystemExit(main())
