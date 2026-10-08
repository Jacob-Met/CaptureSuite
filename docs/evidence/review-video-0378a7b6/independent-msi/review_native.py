# SPDX-License-Identifier: GPL-3.0-only
"""Bounded independent review oracle; source is never modified."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(r"C:\Users\minec\hamon-0378a7b6-capturesuite-discovery")
OUT = Path(__file__).resolve().parent
RUN = Path(r"C:\Users\minec\hamon-0378a7b6-capture-runtime\independent-msi-20261008")
EXPECTED = {
    "desktop/capture_desktop/review_video.py": "f8116601de2b920140d430d59460e07b7f80167d8151fb90f80534eda7f181d5",
    "desktop/capture_desktop/widgets_review_video.py": "3d89f1f8453a3d18d2776574941a2c6197f3be59e8df3a7a278f3b5c400134d9",
    "desktop/capture_desktop/screen_review.py": "8ee038aaca15d6f96ae3df8b4894466f404b6da8a0016179f70f267077f3ff36",
}
RUN.mkdir()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for key, suffix in [
    ("LOCALAPPDATA", "local"), ("APPDATA", "roaming"),
    ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
    ("XDG_CACHE_HOME", "cache"),
]:
    folder = RUN / suffix
    folder.mkdir()
    os.environ[key] = str(folder)
for relative in ("desktop", "libs/python/capture_analysis", "libs/python/capture_session",
                 "libs/python/capture_protocol"):
    sys.path.insert(0, str(ROOT / relative))

import PySide6
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()}

def pins():
    return {p: sha(ROOT / p) for p in EXPECTED}

def wait(predicate, message):
    end = time.monotonic() + 12
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError(message)

def state(view):
    return (view._generation, id(view._player), id(view._video), view._status.text(),
            view._identity.text(), view._clock.text(), view._play.isEnabled(),
            view._seek.isEnabled(), view._choice.currentIndex(), view._reload.isEnabled())

receipt = {
    "schema": "capturesuite.independent-video-review.v1",
    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "python": sys.version, "executable": sys.executable, "pyside6": PySide6.__version__,
    "baseHead": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                        text=True).strip(),
    "expectedSourcePins": EXPECTED, "checks": [], "outcome": "started",
    "boundary": "Native Qt offscreen control/decoder state oracle on synthetic retained files; "
                "no onscreen GPU surface acceptance, hardware capture or session alignment claim.",
}
app = QApplication([])
screen = None
fixture = ROOT / "tests/fixtures/review_video"
fixture_before = hashes(fixture)
try:
    assert pins() == EXPECTED, pins()
    package = RUN / "recovered.mmsession"
    shutil.copytree(fixture, package)
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["state"] = "finalized_recovered"
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (package / "events/checkpoints.json").write_text(json.dumps([
        {"checkpointId": "independent-offset", "name": "Large session offset <literal>",
         "effectiveTimestampNs": 9_876_543_210_000_000}
    ]), encoding="utf-8")
    package_before = hashes(package)
    receipt["modifiedFixturePins"] = package_before
    screen = ReviewScreen(CaptureState())
    screen.resize(1100, 800)
    screen.load_package(str(package))
    screen.show()
    view = screen._recorded_video
    view._toggle.setChecked(True)
    assert view._player is None and view._choice.count() == 5
    assert screen._recovered_banner.isVisible()
    assert screen._checkpoints.count() == 1
    receipt["checks"].append("Recovered package inventory stays idle until explicit selection")

    view._choice.setCurrentIndex(1)
    first, first_generation = view._player, view._generation
    # Defer callbacks until after A -> B -> A; no event pump between these changes.
    QTimer.singleShot(0, lambda: view._sync(first, first_generation))
    QTimer.singleShot(0, lambda: view._failed(first, first_generation, "QUEUED-OLD-ERROR"))
    view._choice.setCurrentIndex(3)
    second, second_generation = view._player, view._generation
    view._choice.setCurrentIndex(1)
    current, generation = view._player, view._generation
    assert current is not first and current is not second
    saved = state(view)
    for player in (first, second):
        # Exercise the actual production signal connections before DeferredDelete dispatch.
        player.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.InvalidMedia)
        player.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
        player.durationChanged.emit(999999)
        player.positionChanged.emit(888888)
        player.seekableChanged.emit(True)
        player.hasVideoChanged.emit(True)
        player.errorOccurred.emit(QMediaPlayer.Error.FormatError, "OLD-SIGNAL-ERROR")
    assert state(view) == saved
    wait(lambda: view._ready, "rapid reselected A did not become ready")
    assert view._player is current
    assert "OLD-" not in view._status.text()
    assert "sim.left <literal>" in view._identity.text()
    assert current.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    assert current.position() == 0
    receipt["checks"].append("Rapid A-B-A and 14 actual retired-player signals plus deferred stale callbacks cannot replace current selection or autoplay")

    saved = state(view)
    # Challenge each guard independently instead of making both predicates false.
    view._sync(current, generation - 1)
    view._failed(current, generation - 1, "WRONG-GENERATION")
    class NoRead:
        def __getattr__(self, name):
            raise AssertionError("Retired identity was queried: " + name)
    wrong_identity = NoRead()
    view._sync(wrong_identity, generation)
    view._failed(wrong_identity, generation, "WRONG-IDENTITY")
    assert state(view) == saved
    receipt["checks"].append("Identity and generation guards independently reject stale callbacks before player reads")

    assert current.duration() == 2000 and current.isSeekable()
    view._seek.setValue(3333)
    wait(lambda: current.position() == 666, "fractional segment-local seek")
    assert "00:00:00.666 / 00:00:02.000" in view._clock.text()
    assert current.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    receipt["checks"].append("3333/10000 seek maps to 666 of 2000 media milliseconds despite large independent session checkpoint timestamp")

    view._failed(current, generation, "INDEPENDENT-CURRENT-ERROR")
    assert view._player is None and view._video is None
    assert not view._play.isEnabled() and not view._seek.isEnabled()
    assert view._reload.isEnabled() and view._choice.currentIndex() == 1
    assert "INDEPENDENT-CURRENT-ERROR" in view._status.text()
    assert view._clock.text() == "Media position —"
    view._reload.click()
    wait(lambda: view._ready, "explicit reload after current-error retirement")
    assert view._player is not current
    assert view._player.position() == 0
    assert view._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    receipt["checks"].append("Current error retires media and clock; explicit reload creates fresh stopped media at zero")

    last, last_generation = view._player, view._generation
    screen.load_package(str(RUN / "missing.mmsession"))
    saved = state(view)
    view._sync(last, last_generation)
    view._failed(last, last_generation, "RETIRED-PACKAGE-ERROR")
    assert state(view) == saved
    assert view._player is None and view._video is None and view._identity.text() == ""
    assert view._choice.count() == 1 and not view._choice.isEnabled()
    assert not view._reload.isEnabled()
    assert "Could not load package" in screen._banner.text()
    receipt["checks"].append("Failed package switch retires old media and stale error cannot resurrect its controls or identity")
    assert hashes(package) == package_before
    assert hashes(fixture) == fixture_before
    assert pins() == EXPECTED
    receipt.update(outcome="pass", sourceStable=True, sourceFixturePreserved=True,
                   changedInputPackagePreserved=True)
except Exception:
    receipt["outcome"] = "fail"
    receipt["traceback"] = traceback.format_exc()
    raise
finally:
    receipt["finalSourcePins"] = pins()
    receipt["sourceFixturePreserved"] = hashes(fixture) == fixture_before
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if screen is not None:
        screen.close()
        screen.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    print(json.dumps(receipt), flush=True)
