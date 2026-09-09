# SPDX-License-Identifier: GPL-3.0-only
"""Exercise every Capture toolbar/Setup action the UI buttons call.

Simulates operator clicks at the ControlClient layer (same RPCs as DaemonLink)
and optionally drives the real Qt MainWindow offscreen.

Usage:
  python tools/probe_ui_actions.py           # RPC matrix
  python tools/probe_ui_actions.py --qt      # also click Qt buttons offscreen
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "desktop"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402


def _ms(t0: float) -> float:
    return (time.time() - t0) * 1000.0


def _ok(reply) -> bool:
    err = getattr(reply, "error", None)
    return not (err is not None and getattr(err, "code", ""))


class StepResult:
    def __init__(self, name: str, ok: bool, ms: float, detail: str = "") -> None:
        self.name = name
        self.ok = ok
        self.ms = ms
        self.detail = detail


def run_rpc_matrix() -> list[StepResult]:
    results: list[StepResult] = []
    client = ControlClient(timeout_s=15.0)
    t0 = time.time()
    client.connect()
    results.append(StepResult("connect", True, _ms(t0)))

    def step(name: str, fn) -> object:
        t = time.time()
        try:
            reply = fn()
            ok = _ok(reply) if reply is not None else True
            detail = ""
            if reply is not None and hasattr(reply, "error") and reply.error.code:
                detail = f"{reply.error.code}: {reply.error.message}"
            results.append(StepResult(name, ok, _ms(t), detail))
            return reply
        except Exception as exc:  # noqa: BLE001
            results.append(StepResult(name, False, _ms(t), str(exc)))
            return None

    srcs = step("list_sources", client.list_sources)
    if srcs is None:
        return results
    cams = [
        s for s in srcs.sources if s.source_type == "camera" and "brio" in (s.alias or "").lower()
    ]
    if not cams:
        cams = [s for s in srcs.sources if s.source_type == "camera"][:1]
    radars = [s for s in srcs.sources if s.source_id.startswith("radar.")]
    # Prefer TR13C first then LTR11 — both selected so dual-radar path is covered.
    radars_sorted = sorted(
        radars,
        key=lambda s: (0 if "TR13C" in (s.alias or "") else 1, s.source_id),
    )
    ids = [s.source_id for s in cams[:1]] + [s.source_id for s in radars_sorted]
    if not ids:
        results.append(StepResult("pick_sources", False, 0, "no camera/radar"))
        return results
    results.append(
        StepResult(
            "pick_sources",
            True,
            0,
            ",".join(ids),
        )
    )

    try:
        client.stop_rehearsal()
    except Exception:
        pass

    step("create_session", lambda: client.create_session(f"ui-probe-{int(time.time())}"))
    step("select_sources", lambda: client.select_sources(ids))
    step("preflight", lambda: client.run_preflight(ids))
    step("subscribe", lambda: client.subscribe_status(include_preview=True))
    step("rehearse", lambda: client.start_rehearsal(ids))

    # Concurrent RPC: session view while a longer call is in flight (lock regression).
    view_ms: list[float] = []
    view_err: list[str] = []

    def poll_view() -> None:
        t = time.time()
        try:
            client.get_session_view()
            view_ms.append(_ms(t))
        except Exception as exc:  # noqa: BLE001
            view_err.append(str(exc))

    # Schema + apply on first radar if present, else camera.
    target = radars[0].source_id if radars else ids[0]
    schema = step("get_config_schema", lambda: client.get_config_schema(target))
    if schema is not None and _ok(schema) and target.startswith("radar."):
        thr = threading.Thread(target=poll_view, daemon=True)
        thr.start()
        step(
            "apply_preview_view",
            lambda: client.apply_config(target, {"preview_view": "range_doppler"}),
        )
        thr.join(timeout=30)
        concurrent_ok = bool(view_ms) and not view_err
        results.append(
            StepResult(
                "concurrent_view_during_apply",
                concurrent_ok,
                view_ms[0] if view_ms else 0,
                view_err[0] if view_err else f"view={view_ms[0]:.0f}ms",
            )
        )

    step("stop_rehearse", client.stop_rehearsal)
    step("rescan", client.rescan_sources)
    # Re-select after rescan (daemon restores selection, UI re-pushes).
    step("select_after_rescan", lambda: client.select_sources(ids))
    step("rehearse_after_rescan", lambda: client.start_rehearsal(ids))
    time.sleep(2.0)
    step("start_selected", client.start_selected)
    time.sleep(3.0)
    stats = step("recording_stats", client.get_recording_stats)
    if stats is not None:
        live = {s.source_id: s.sample_count for s in stats.streams}
        results.append(
            StepResult(
                "samples_live",
                any(v > 0 for v in live.values()),
                0,
                str(live),
            )
        )
    tok = step("request_stop", client.request_stop)
    if tok is not None and tok.confirmation_token:
        step(
            "stop_session",
            lambda: client.stop_session(tok.confirmation_token),
        )
    return results


def run_qt_clicks() -> list[StepResult]:
    """Drive real MainWindow button slots offscreen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from capture_desktop.app import MainWindow
    from PySide6.QtWidgets import QApplication

    results: list[StepResult] = []
    app = QApplication.instance() or QApplication([])
    win = MainWindow(auto_connect=True)

    deadline = time.time() + 45.0
    while time.time() < deadline and not win.state.connected:
        app.processEvents()
        time.sleep(0.05)
    results.append(StepResult("qt_connect", win.state.connected, 0, win.state.status_line))
    if not win.state.connected:
        return results

    # Wait boot to leave list_sources / create_session.
    deadline = time.time() + 60.0
    while time.time() < deadline and win._boot_stage not in (
        "ready",
        "rehearse",
        "select_sources",
        "subscribe",
    ):
        app.processEvents()
        time.sleep(0.05)
    # Allow auto-rehearse boot to settle.
    deadline = time.time() + 90.0
    while time.time() < deadline and win._boot_stage != "ready":
        app.processEvents()
        time.sleep(0.05)
    results.append(
        StepResult(
            "qt_boot_ready",
            win._boot_stage == "ready",
            0,
            f"stage={win._boot_stage} status={win.state.status_line!r}",
        )
    )

    def click(name: str, btn, expect_substr: str | None = None) -> None:
        t = time.time()
        before = win.state.status_line
        btn.click()
        app.processEvents()
        # Immediate feedback should update status within a few processEvents.
        for _ in range(5):
            app.processEvents()
            time.sleep(0.02)
        after = win.state.status_line
        immediate = after != before or (
            expect_substr is not None and expect_substr.lower() in after.lower()
        )
        # Wait for RPC to finish (status changes again or button re-enabled).
        settle = time.time() + 90.0
        while time.time() < settle and win.link._inflight > 0:
            app.processEvents()
            time.sleep(0.05)
        app.processEvents()
        results.append(
            StepResult(
                name,
                immediate,
                _ms(t),
                f"before={before!r} after_click={after!r} final={win.state.status_line!r}",
            )
        )

    click("qt_btn_preflight", win.btn_preflight, "preflight")
    # Close preflight dialog if shown.
    for w in app.topLevelWidgets():
        if w is not win and w.isVisible():
            w.close()
            app.processEvents()

    click("qt_btn_rescan", win.btn_rescan, "rescan")
    click("qt_btn_rehearse", win.btn_rehearse, "rehears")
    click("qt_btn_stop_rehearse", win.btn_stop_rehearse, "stop")

    # Setup Apply if a source is focused.
    if win.state.sources:
        sid = next(
            (s.source_id for s in win.state.sources if s.source_id.startswith("radar.")),
            win.state.sources[0].source_id,
        )
        win.setup._list.setCurrentRow(0)
        for i in range(win.setup._list.count()):
            item = win.setup._list.item(i)
            if item and sid in (item.data(0) or ""):
                win.setup._list.setCurrentRow(i)
                break
        app.processEvents()
        t = time.time()
        win._load_setup_schema(sid)
        while time.time() < t + 60 and win.link._inflight > 0:
            app.processEvents()
            time.sleep(0.05)
        results.append(
            StepResult(
                "qt_load_schema",
                "schema" in win.state.status_line.lower()
                or "loaded" in win.state.status_line.lower()
                or bool(win.setup.form.schema),
                _ms(t),
                win.state.status_line,
            )
        )

    win.close()
    app.processEvents()
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qt", action="store_true", help="also drive Qt MainWindow")
    args = ap.parse_args()

    all_results: list[StepResult] = []
    print("=== RPC button matrix ===")
    all_results.extend(run_rpc_matrix())
    for r in all_results:
        flag = "PASS" if r.ok else "FAIL"
        print(f"  {flag:4} {r.name:32} {r.ms:8.0f} ms  {r.detail}")

    if args.qt:
        print("\n=== Qt offscreen clicks ===")
        qt_results = run_qt_clicks()
        all_results.extend(qt_results)
        for r in qt_results:
            flag = "PASS" if r.ok else "FAIL"
            print(f"  {flag:4} {r.name:32} {r.ms:8.0f} ms  {r.detail}")

    failed = [r for r in all_results if not r.ok]
    print(f"\n{len(all_results) - len(failed)}/{len(all_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
