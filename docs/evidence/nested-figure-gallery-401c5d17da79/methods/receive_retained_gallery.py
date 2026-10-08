# SPDX-License-Identifier: GPL-3.0-only
"""Receive the gallery against retained real analysis outputs, without generating jobs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import resource
import sys
import time
import traceback
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--numeric-job", type=Path, required=True)
parser.add_argument("--legacy-job", type=Path, required=True)
args = parser.parse_args()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
sys.path.insert(0, str(args.source_root / "desktop"))

from PySide6 import __version__ as qt_version
from PySide6.QtCore import QBuffer, QIODevice, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from capture_desktop import theme
from capture_desktop.widgets_analysis_plots import FigureGallery

started = time.monotonic()
checks = []
frames = {}
failures = []


def hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)


def pixels(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return (image.width(), image.height(), bytes(image.constBits()))


packages = {name: job.parents[2] for name, job in
            (("numeric", args.numeric_job), ("legacy", args.legacy_job))}
before_packages = {name: hashes(path) for name, path in packages.items()}
source_paths = [args.source_root / relative for relative in (
    "desktop/capture_desktop/widgets_analysis_plots.py",
    "desktop/capture_desktop/theme.py",
    "tests/ui/test_analysis_nested_gallery.py",
)]
before_sources = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths}
app = QApplication([])
theme.apply_theme(app, setting="dark")
gallery = FigureGallery()
gallery.resize(1200, 820)
gallery.setWindowTitle("CaptureSuite saved analysis gallery")
gallery.show()
observed = {}


def invoke(callback):
    try:
        callback()
    except Exception:
        failures.append(traceback.format_exc())
        app.exit(1)


def later(callback):
    QTimer.singleShot(100, lambda: invoke(callback))


def snapshot(name):
    image = gallery.grab().toImage()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise AssertionError("Native widget frame encoding failed")
    data = bytes(buffer.data())
    frames[name] = {
        "png_base64": base64.b64encode(data).decode(),
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "width": image.width(), "height": image.height(),
    }


def receive_job(name, job, expected_titles):
    tabs = gallery._tabs
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    tips = [tabs.tabToolTip(i) for i in range(1, tabs.count())]
    check(f"{name}: exact saved figure tabs", titles == ["Sync", *expected_titles])
    pngs = sorted(path for path in (job / "figures").rglob("*.png")
                  if path.relative_to(job / "figures") != Path("sync_dashboard.png"))
    check(f"{name}: exact path identity", tips == [
        path.relative_to(job / "figures").as_posix() for path in pngs])
    check(f"{name}: all native image pixels equal saved PNGs", all(
        pixels(tabs.widget(i).widget().pixmap().toImage()) == pixels(QImage(str(path)))
        for i, path in enumerate(pngs, 1)))
    doc = json.loads((job / "figures/sync_dashboard_series.json").read_text())
    plots = gallery._sync._linked
    check(f"{name}: native linked series count", len(plots) == len(doc["series"]))
    check(f"{name}: saved plot samples remain exact", all(
        plot.listDataItems()[0].getData()[1].tolist() == row["y"]
        for plot, row in zip(plots, doc["series"], strict=True)))
    observed[name] = {
        "job": str(job), "tabs": titles, "tooltips": tips,
        "linked_series_count": len(plots),
        "saved_png_sizes": [[QImage(str(p)).width(), QImage(str(p)).height()] for p in pngs],
    }


def numeric_loaded():
    receive_job("numeric", args.numeric_job, [
        "lsl / numeric.stream / channel 0", "lsl / numeric.stream / channel 1"])
    gallery._tabs.setCurrentIndex(1)
    later(numeric_visible)


def numeric_visible():
    check("numeric: selected native PNG is visible",
          gallery._tabs.currentWidget().widget().isVisible())
    snapshot("numeric-channel.png")
    gallery.load_job_dir(args.legacy_job)
    gallery._tabs.setCurrentIndex(0)
    later(legacy_loaded)


def legacy_loaded():
    receive_job("legacy", args.legacy_job, [
        "emg sim.emg.main channels"[:24], "imu sim.imu.upper accel"[:24]])
    check("legacy: both linked plot widgets are visible",
          all(plot.isVisible() for plot in gallery._sync._linked))
    snapshot("legacy-linked-plots.png")
    gallery._tabs.setCurrentIndex(2)
    later(legacy_visible)


def legacy_visible():
    check("legacy: selected flat PNG is visible",
          gallery._tabs.currentWidget().widget().isVisible())
    snapshot("legacy-flat-figure.png")
    check("all saved and raw package bytes remain exact",
          {name: hashes(path) for name, path in packages.items()} == before_packages)
    check("all executed gallery/source bytes remain exact", {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    } == before_sources)
    app.quit()


def begin():
    gallery.load_job_dir(args.numeric_job)
    later(numeric_loaded)


QTimer.singleShot(0, lambda: invoke(begin))
QTimer.singleShot(15_000, lambda: invoke(lambda: check("native event-loop deadline", False)))
exit_code = app.exec()
gallery.close()
receipt = {
    "method": "QApplication.exec with QTimer scheduling; retained real jobs; no writer or pipeline runs",
    "canonical_base": "3e3ecc5ecc1cfc79c79901eb5cffe10b0ec5852e",
    "python": sys.version, "pyside6": qt_version,
    "exit": exit_code, "elapsed_seconds": round(time.monotonic() - started, 3),
    "checks": checks, "passed": sum(row["passed"] for row in checks),
    "failures": failures, "observed": observed,
    "source_hashes": before_sources,
    "package_hashes_before_and_after": before_packages,
    "frames": {name: {key: value for key, value in frame.items() if key != "png_base64"}
               for name, frame in frames.items()},
}
print(json.dumps({"receipt": receipt, "frames": frames}))
sys.exit(exit_code or bool(failures))
