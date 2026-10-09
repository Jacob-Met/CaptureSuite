# SPDX-License-Identifier: GPL-3.0-only
"""Actual Qt decoder and user-control receiving for two retained frames."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from capture_desktop import theme
from capture_desktop.widgets_review_video import RecordedVideoReview
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, Qt, QTimer
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/review_video"


def wait_for(predicate, seconds=10):
    end = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < end, "Native Qt predicate timed out"
        loop = QEventLoop()
        QTimer.singleShot(20, loop.quit)
        loop.exec()


def pixel_hash(image):
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def fixture_hashes():
    return {
        p.relative_to(FIXTURE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in FIXTURE.rglob("*")
        if p.is_file()
    }


def test_actual_retained_pair_journey(tmp_path):
    evidence = Path(os.environ.get("CAPTURE_FRAME_PAIR_EVIDENCE", str(tmp_path)))
    evidence.mkdir(parents=True, exist_ok=True)
    for font in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/seguisb.ttf"):
        if Path(font).is_file():
            QFontDatabase.addApplicationFont(font)
    before = fixture_hashes()
    w = RecordedVideoReview()
    observations = []
    try:
        w.resize(800, 650)
        w.show()
        w._toggle.setChecked(True)
        w._compare_frames.click()
        panel = w._comparison
        assert panel.isVisible() and not panel.isModal()
        panel._keep["A"].click()
        assert panel.frames == {"A": None, "B": None}
        assert "Frame not kept" in panel._notice.text()
        w.load_package(str(FIXTURE), state="finalized")

        def select(source, tail):
            index = next(
                i + 1
                for i, s in enumerate(w._segments)
                if s.source_id == source and s.relative_path.endswith(tail)
            )
            w._choice.setCurrentIndex(index)
            wait_for(lambda: w._player is not None and w._ready)
            player = w._player
            assert player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
            w._play.click()
            wait_for(lambda: w._video.videoSink().videoFrame().isValid() and player.position() > 0)
            w._play.click()
            wait_for(lambda: player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
            return player

        player = select("sim.left <literal>", "0001.mkv")
        current = w._video.videoSink().videoFrame()
        expected = pixel_hash(current.toImage())
        position, stamp = player.position(), current.startTime()
        QTest.mouseClick(panel._keep["A"], Qt.MouseButton.LeftButton)
        a = panel.frames["A"]
        assert a is not None and pixel_hash(a.image) == expected
        assert a.frame_start_us == stamp and a.player_position_ms == position
        assert "sim.left <literal>" in panel._metadata["A"].text()
        assert "front & camera" in panel._metadata["A"].text()
        assert panel._metadata["A"].textFormat() == Qt.TextFormat.PlainText
        assert player.position() == position
        observations.append(
            {"group": "actual A pixels and literal source/clock identity", "pass": True}
        )

        w._play.click()
        wait_for(lambda: player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        panel._keep["B"].click()
        assert panel.frames["A"] is a and panel.frames["B"] is None
        assert "Pause Recorded video" in panel._notice.text()
        assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        w._play.click()
        wait_for(lambda: player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
        old_player, old_generation = player, w._generation

        player = select("sim.right <literal>", "0001.mkv")
        w._sync(old_player, old_generation)
        w._failed(old_player, old_generation, "late obsolete error")
        assert w._player is player and panel.frames["A"] is a
        current = w._video.videoSink().videoFrame()
        expected_b = pixel_hash(current.toImage())
        panel._keep["B"].click()
        b = panel.frames["B"]
        assert b is not None and b.segment.source_id == "sim.right <literal>"
        assert pixel_hash(b.image) == expected_b and expected_b != expected
        assert pixel_hash(a.image) == expected
        observations.append(
            {"group": "playing refusal and distinct same-basename segment B", "pass": True}
        )

        player.setPosition(400)
        w._set_a()
        player.setPosition(1200)
        w._set_b()
        w._repeat.setChecked(True)
        w._rate.setCurrentIndex(1)
        player.setPosition(800)
        state = (
            player.position(),
            player.playbackState(),
            player.playbackRate(),
            w._interval.start_ms,
            w._interval.end_ms,
            w._interval.enabled,
        )
        panel._keep["A"].click()
        assert panel.frames["B"] is b and panel.frames["A"] is not a
        assert state == (
            player.position(),
            player.playbackState(),
            player.playbackRate(),
            w._interval.start_ms,
            w._interval.end_ms,
            w._interval.enabled,
        )
        panel.close()
        assert not panel.isVisible() and panel.frames["B"] is b
        w._compare_frames.click()
        assert panel.isVisible()
        observations.append(
            {
                "group": "replace preserves paused position/rate/repeat; close reopens",
                "pass": True,
            }
        )

        # Both retained frames survive a failed selected file and a normal reload.
        saved = dict(panel.frames)
        invalid = next(
            i + 1 for i, s in enumerate(w._segments) if s.relative_path.endswith("invalid.mkv")
        )
        w._choice.setCurrentIndex(invalid)
        wait_for(lambda: w._player is None)
        panel._keep["A"].click()
        assert all(panel.frames[k] is saved[k] for k in saved)
        player = select("sim.left <literal>", "0002.mkv")
        assert all(panel.frames[k] is saved[k] for k in saved)
        panel._keep["A"].click()
        yellow = panel.frames["A"]
        assert yellow is not None and yellow.segment.relative_path.endswith("0002.mkv")
        assert pixel_hash(yellow.image) not in (expected, expected_b)
        w._reload.click()
        wait_for(lambda: w._player is not None and w._ready)
        assert panel.frames["A"] is yellow and panel.frames["B"] is b
        observations.append({"group": "new-segment error and reload retain the pair", "pass": True})

        for setting in ("dark", "light"):
            theme.apply_theme(APP, setting=setting)
            panel.resize(720, 620)
            panel.show()
            APP.processEvents()
            assert panel.width() == 720 and panel.height() == 620
            for slot in ("A", "B"):
                assert panel._keep[slot].isVisible() and panel._clear[slot].isVisible()
                assert panel._canvases[slot].width() >= 140
            assert panel.grab().save(str(evidence / f"comparison-{setting}-720x620.png"))
        panel.activateWindow()
        panel._clear["A"].setFocus()
        QTest.keyClick(panel._clear["A"], Qt.Key.Key_Space)
        assert panel.frames["A"] is None and panel.frames["B"] is b
        w._toggle.setChecked(False)
        assert panel.frames["B"] is b
        w.reset()
        assert panel.frames == {"A": None, "B": None}
        assert fixture_hashes() == before
        observations.append(
            {
                "group": "compact theme/keyboard and collapse/package reset/raw preservation",
                "pass": True,
            }
        )
        (evidence / "journey.json").write_text(
            json.dumps({"groups": observations, "raw_files": before}, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        w.reset()
        w._comparison.close()
        w.close()
        w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()


def test_destroyed_panel_drops_owned_image_references():
    from capture_desktop.review_video import RecordedVideoSegment
    from capture_desktop.review_video_frames import retain_video_frame
    from capture_desktop.widgets_review_video_frames import FrameComparisonDialog
    from PySide6.QtGui import QColor
    from PySide6.QtMultimedia import QVideoFrame

    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    retained = retain_video_frame(
        QVideoFrame(image), RecordedVideoSegment("source", "stream", "segments/one.mkv"), 0
    )
    panel = FrameComparisonDialog()
    panel.set_frame("A", retained)
    panel.set_frame("B", retained)
    frames, canvases = panel.frames, panel._canvases
    panel.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert frames == {"A": None, "B": None}
    assert canvases["A"].frame is None and canvases["B"].frame is None


def test_only_focused_frame_buttons_override_application_space():
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import QPushButton

    w = RecordedVideoReview()
    outside = QPushButton("Outside the recorded viewer")
    hits = []
    space = QShortcut(QKeySequence("Space"), w)
    modified = QShortcut(QKeySequence("Ctrl+Space"), w)
    for shortcut in (space, modified):
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    space.activated.connect(lambda: hits.append("space"))
    modified.activated.connect(lambda: hits.append("modified"))
    try:
        w.show()
        w._toggle.setChecked(True)
        w.activateWindow()
        w._compare_frames.setFocus()
        APP.processEvents()
        QTest.keyClick(w._compare_frames, Qt.Key.Key_Space)
        wait_for(lambda: w._comparison.isVisible())
        panel = w._comparison
        panel.activateWindow()
        panel._keep["A"].setFocus()
        APP.processEvents()
        QTest.keyClick(panel._keep["A"], Qt.Key.Key_Space)
        assert "Frame not kept" in panel._notice.text() and hits == []
        QTest.keyClick(panel._keep["A"], Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        assert hits == ["modified"]
        outside.show()
        outside.activateWindow()
        outside.setFocus()
        APP.processEvents()
        QTest.keyClick(outside, Qt.Key.Key_Space)
        assert hits == ["modified", "space"]
    finally:
        w.reset()
        w._comparison.close()
        outside.close()
        w.close()
        outside.deleteLater()
        w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
