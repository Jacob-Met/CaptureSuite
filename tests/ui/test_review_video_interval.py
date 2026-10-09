# SPDX-License-Identifier: GPL-3.0-only
"""Real Windows Qt/decoder interval and rate controls on retained synthetic media."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from capture_desktop.widgets_review_video import RecordedVideoReview
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "review_video"


def wait(qapp, predicate, description, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError(description)


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def opened(qapp, tmp_path):
    package = tmp_path / "video.mmsession"
    shutil.copytree(FIXTURE, package)
    video = RecordedVideoReview()
    video.resize(1060, 730)
    video.show()
    video._toggle.setChecked(True)
    video.load_package(str(package), state="finalized")
    video._choice.setCurrentIndex(1)
    wait(qapp, lambda: video._ready and video._seek.isEnabled(), "seekable native video")
    assert video._player.duration() == 2000
    return video, video._player, package


def click(button):
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def seek(qapp, video, position):
    video._seek.setValue(position * 10_000 // 2000)
    wait(
        qapp,
        lambda: (
            video._player.position() == position
            and f"{position // 1000:02}.{position % 1000:03}" in video._clock.text()
        ),
        f"visible paused seek {position}",
    )


def interval(qapp, video, start=400, end=1200):
    seek(qapp, video, start)
    click(video._mark_a)
    seek(qapp, video, end)
    click(video._mark_b)
    assert not video._repeat.isChecked()
    click(video._repeat)
    assert video._repeat.isChecked()


def close_video(qapp, video):
    # Finish this owned native QWidget's deferred destruction before the next
    # decoder is created; otherwise PySide GC may retire its output mid-callback.
    video.reset()
    video.close()
    video.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def evidence(name, data):
    root = os.environ.get("CAPTURE_REPEAT_EVIDENCE")
    if root:
        Path(root, name + ".json").write_text(json.dumps(data, indent=2) + "\n")


def test_paused_configuration_outside_seek_invalid_b_and_explicit_play(qapp, tmp_path):
    video, player, package = opened(qapp, tmp_path)
    before = hashes(package)
    try:
        interval(qapp, video)
        assert player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
        seek(qapp, video, 200)
        click(video._mark_b)
        assert (video._interval.start_ms, video._interval.end_ms, video._interval.enabled) == (
            400,
            1200,
            True,
        )
        assert "B must be after A" in video._interval_label.text()
        assert player.position() == 200
        click(video._play)
        wait(
            qapp,
            lambda: (
                player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and 400 <= player.position() < 1200
            ),
            "Play normalizes outside interval",
        )
        click(video._play)
        assert player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        position = player.position()
        QTest.qWait(200)
        assert player.position() == position
        assert hashes(package) == before
    finally:
        close_video(qapp, video)


def test_actual_repeat_cycles_then_disable_clear_and_playing_seek(qapp, tmp_path):
    video, player, package = opened(qapp, tmp_path)
    before = hashes(package)
    try:
        interval(qapp, video)
        positions = []
        click(video._play)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            qapp.processEvents()
            positions.append([time.monotonic(), player.position()])
            if sum(b[1] < a[1] - 300 for a, b in zip(positions, positions[1:], strict=False)) >= 3:
                break
            QTest.qWait(15)
        loops = sum(b[1] < a[1] - 300 for a, b in zip(positions, positions[1:], strict=False))
        evidence("repeat-cycles", {"positions": positions, "loops": loops})
        assert loops >= 3
        assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        video._seek.setValue(8000)
        wait(qapp, lambda: 400 <= player.position() < 1200, "playing outside seek normalizes")
        click(video._repeat)
        position = player.position()
        assert not video._interval.enabled
        assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        click(video._clear_interval)
        assert video._interval.start_ms is None and video._interval.end_ms is None
        assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        wait(qapp, lambda: player.position() > position + 150, "disable and clear preserve playing")
        assert hashes(package) == before
    finally:
        close_video(qapp, video)


def test_end_of_media_interval_repeats_and_collapse_pauses(qapp, tmp_path):
    video, player, _ = opened(qapp, tmp_path)
    try:
        interval(qapp, video, 1200, 2000)
        click(video._play)
        positions = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            qapp.processEvents()
            positions.append(player.position())
            if sum(b < a - 300 for a, b in zip(positions, positions[1:], strict=False)) >= 2:
                break
            QTest.qWait(15)
        assert sum(b < a - 300 for a, b in zip(positions, positions[1:], strict=False)) >= 2
        click(video._toggle)
        assert player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        position = player.position()
        click(video._toggle)
        QTest.qWait(200)
        assert player.position() == position
        click(video._play)
        wait(
            qapp,
            lambda: player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
            "explicit resume",
        )
        video.hide()
        assert player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    finally:
        close_video(qapp, video)


def test_actual_speed_progression_and_selection_reset(qapp, tmp_path):
    video, player, package = opened(qapp, tmp_path)
    before = hashes(package)
    measurements = []
    try:
        for index, rate, lower, upper in [(0, 0.25, 40, 350), (3, 2.0, 600, 1500)]:
            seek(qapp, video, 0)
            video._rate.setCurrentIndex(index)
            assert player.playbackRate() == rate
            assert f"{rate:g}\u00d7" in video._rate_label.text()
            assert player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
            begin = time.monotonic()
            click(video._play)
            wait(
                qapp,
                lambda: player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
                "speed sample begins",
            )
            QTest.qWait(550)
            click(video._play)
            elapsed, position = time.monotonic() - begin, player.position()
            measurements.append({"rate": rate, "wall_seconds": elapsed, "position_ms": position})
            assert lower <= position <= upper, measurements
        evidence("actual-rate-progression", measurements)
        interval(qapp, video)
        old, generation = player, video._generation
        click(video._reload)
        wait(qapp, lambda: video._ready, "reload")
        assert video._interval.start_ms is None and not video._interval.enabled
        assert video._rate.currentData() == 1 and video._player.playbackRate() == 1
        assert video._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
        video._sync(old, generation)
        video._failed(old, generation, "stale repeat/rate")
        assert "stale repeat/rate" not in video._status.text()
        assert hashes(package) == before
    finally:
        close_video(qapp, video)


def test_focused_new_buttons_preserve_native_space_and_other_shortcuts(qapp, tmp_path):
    video, player, _ = opened(qapp, tmp_path)
    hits = []
    shortcut = QShortcut(QKeySequence("Space"), video)
    shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    shortcut.activated.connect(lambda: hits.append("global"))
    video.activateWindow()
    qapp.setActiveWindow(video)
    try:
        seek(qapp, video, 400)
        video._mark_a.setFocus()
        QTest.keyClick(video._mark_a, Qt.Key.Key_Space)
        assert video._interval.start_ms == 400
        seek(qapp, video, 1200)
        video._mark_b.setFocus()
        QTest.keyClick(video._mark_b, Qt.Key.Key_Space)
        video._repeat.setFocus()
        QTest.keyClick(video._repeat, Qt.Key.Key_Space)
        assert video._interval.enabled
        video._clear_interval.setFocus()
        QTest.keyClick(video._clear_interval, Qt.Key.Key_Space)
        assert video._interval.start_ms is None and not video._interval.enabled
        assert hits == []
        video._seek.setFocus()
        QTest.keyClick(video._seek, Qt.Key.Key_Space)
        assert hits == ["global"]
        assert player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    finally:
        shortcut.setEnabled(False)
        close_video(qapp, video)
