# SPDX-License-Identifier: GPL-3.0-only
"""Actual native Qt decoding and user controls on explicitly synthetic Matroska."""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "review_video"


def _wait(qapp, predicate, description: str, seconds: float = 12) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return
        QTest.qWait(15)
    raise AssertionError(f"Native media condition was not reached: {description}")


def _screen(qapp, tmp_path):
    package = tmp_path / "video.mmsession"
    shutil.copytree(FIXTURE, package)
    screen = ReviewScreen(CaptureState())
    screen.resize(1160, 880)
    screen.load_package(str(package))
    screen.show()
    video = screen._recorded_video
    QTest.mouseClick(video._toggle, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    return screen, video, package


def _color(video, component: int) -> bool:
    if video._video is None:
        return False
    frame = video._video.videoSink().videoFrame()
    if not frame.isValid():
        return False
    image = frame.toImage()
    if image.isNull():
        return False
    rgb = image.pixelColor(image.width() // 2, image.height() // 2).getRgb()[:3]
    return rgb[component] > 200 and all(v < 45 for i, v in enumerate(rgb) if i != component)


def _hashes(package):
    return {
        str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*")
        if p.is_file()
    }


def test_native_play_pause_seek_reads_actual_red_then_blue_frames(qapp, tmp_path):
    screen, video, package = _screen(qapp, tmp_path)
    before = _hashes(package)
    assert video._player is None
    assert video._choice.count() == 5
    assert not video._play.isEnabled()
    video._choice.setCurrentIndex(1)
    _wait(qapp, lambda: video._ready, "first segment ready")
    player = video._player
    assert player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    assert player.position() == 0
    assert player.duration() == 2000
    assert "<literal>" in video._identity.text()
    assert video._identity.textFormat() == Qt.TextFormat.PlainText
    QTest.mouseClick(video._play, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: _color(video, 0), "decoded red frame")
    QTest.mouseClick(video._play, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: player.playbackState() == QMediaPlayer.PlaybackState.PausedState, "paused")
    paused = player.position()
    QTest.qWait(150)
    assert player.position() == paused
    assert video._seek.isEnabled()
    video._seek.setValue(7500)
    _wait(qapp, lambda: _color(video, 2), "decoded blue frame after local seek")
    assert player.position() == 1500
    assert "00:00:01.500 / 00:00:02.000" in video._clock.text()
    assert _hashes(package) == before
    screen.close()


def test_switching_segments_retires_old_player_and_queued_callbacks(qapp, tmp_path):
    screen, video, _ = _screen(qapp, tmp_path)
    video._choice.setCurrentIndex(1)
    _wait(qapp, lambda: video._ready, "first segment ready")
    old, generation = video._player, video._generation
    QTest.mouseClick(video._play, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: _color(video, 0), "first red frame")
    video._choice.setCurrentIndex(3)
    assert video._player is not old
    # Deliberately deliver an old selection's already-queued signal.
    video._failed(old, generation, "OLD ERROR MUST NOT REPLACE CURRENT SELECTION")
    assert "OLD ERROR" not in video._status.text()
    _wait(qapp, lambda: video._ready, "second source ready")
    assert video._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    assert "sim.right" in video._identity.text()
    QTest.mouseClick(video._play, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: _color(video, 1), "actual second-source green frame")
    screen.close()


def test_invalid_media_retains_selection_and_can_reload_after_repair(qapp, tmp_path):
    screen, video, package = _screen(qapp, tmp_path)
    video._choice.setCurrentIndex(4)
    _wait(qapp, lambda: "Cannot play" in video._status.text(), "invalid-media error")
    assert video._player is None and video._video is None
    assert video._placeholder.isVisible()
    assert not video._play.isEnabled() and not video._seek.isEnabled()
    assert video._choice.currentIndex() == 4 and video._reload.isEnabled()
    invalid = package / "sources/sim.right/streams/front/segments/invalid.mkv"
    shutil.copyfile(package / "sources/sim.right/streams/front/segments/0001.mkv", invalid)
    QTest.mouseClick(video._reload, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: video._ready, "explicit reload after fixture repair")
    assert video._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    screen.close()


def test_missing_selected_file_never_keeps_previous_picture(qapp, tmp_path):
    screen, video, package = _screen(qapp, tmp_path)
    video._choice.setCurrentIndex(1)
    _wait(qapp, lambda: video._ready, "ready")
    QTest.mouseClick(video._play, Qt.MouseButton.LeftButton)
    _wait(qapp, lambda: _color(video, 0), "red frame")
    (package / "sources/sim.left/streams/front/segments/0002.mkv").unlink()
    video._choice.setCurrentIndex(2)
    assert video._player is None and video._video is None
    assert "Could not open" in video._status.text()
    assert not video._play.isEnabled()
    assert video._placeholder.isVisible()
    screen.close()


def test_package_failure_empty_and_nonfinalized_retire_media(qapp, tmp_path):
    screen, video, package = _screen(qapp, tmp_path)
    video._choice.setCurrentIndex(1)
    _wait(qapp, lambda: video._ready, "ready")
    screen.load_package(str(tmp_path / "missing"))
    assert video._player is None and video._video is None
    assert video._choice.count() == 1 and not video._choice.isEnabled()
    assert video._identity.text() == ""
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "manifest.json").write_text('{"state":"finalized","sessionId":"empty"}')
    screen.load_package(str(empty))
    assert "No recorded MKV" in video._status.text()
    video.load_package(str(package), state="recording")
    assert "requires a finalized" in video._status.text()
    assert not video._choice.isEnabled()
    screen.close()


def test_hiding_and_keyboard_controls_do_not_autoplay(qapp, tmp_path):
    screen, video, _ = _screen(qapp, tmp_path)
    video._choice.setFocus()
    QTest.keyClick(video._choice, Qt.Key.Key_Down)
    _wait(qapp, lambda: video._ready, "keyboard-selected segment")
    assert video._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    video._play.setFocus()
    QTest.keyClick(video._play, Qt.Key.Key_Space)
    _wait(qapp, lambda: _color(video, 0), "keyboard-started red frame")
    QTest.mouseClick(video._toggle, Qt.MouseButton.LeftButton)
    _wait(
        qapp,
        lambda: video._player.playbackState() == QMediaPlayer.PlaybackState.PausedState,
        "collapse pauses media",
    )
    QTest.mouseClick(video._toggle, Qt.MouseButton.LeftButton)
    assert video._player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    screen.hide()
    qapp.processEvents()
    assert video._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    screen.close()


def test_actual_main_window_video_buttons_keep_space_activation(qapp, tmp_path, monkeypatch):
    from capture_desktop.app import MainWindow
    from PySide6.QtGui import QKeySequence, QShortcut

    for key in ("LOCALAPPDATA", "APPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        directory = tmp_path / key.lower()
        directory.mkdir()
        monkeypatch.setenv(key, str(directory))
    package = tmp_path / "video.mmsession"
    shutil.copytree(FIXTURE, package)
    before = _hashes(package)
    window = MainWindow(auto_connect=False)
    checkpoint_hits = []
    modified_hits = []
    window._on_checkpoint = lambda: checkpoint_hits.append("checkpoint")
    modified = QShortcut(QKeySequence("Ctrl+Space"), window)
    modified.setContext(Qt.ShortcutContext.ApplicationShortcut)
    modified.activated.connect(lambda: modified_hits.append("modified"))
    try:
        window.state.package_path = str(package)
        window.state.review_mode = True
        window.review.load_package(str(package))
        window.tabs.setCurrentWidget(window.review)
        window.resize(1280, 1000)
        window.show()
        window.activateWindow()
        qapp.setActiveWindow(window)
        video = window.review._recorded_video
        video._toggle.setFocus()
        QTest.keyClick(video._toggle, Qt.Key.Key_Space)
        assert video._body.isVisible()
        video._choice.setCurrentIndex(1)
        _wait(qapp, lambda: video._ready, "application segment ready")

        video._play.setFocus()
        assert qapp.focusWidget() is video._play
        QTest.keyClick(video._play, Qt.Key.Key_Space)
        _wait(qapp, lambda: _color(video, 0), "application keyboard Play")
        QTest.keyClick(video._play, Qt.Key.Key_Space)
        assert video._player.playbackState() == QMediaPlayer.PlaybackState.PausedState

        previous = video._player
        video._reload.setFocus()
        QTest.keyClick(video._reload, Qt.Key.Key_Space)
        assert video._player is not previous
        _wait(qapp, lambda: video._ready, "application keyboard reload")
        assert video._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        assert video._player.position() == 0
        video._play.setFocus()
        QTest.keyClick(video._play, Qt.Key.Key_Space)
        _wait(qapp, lambda: _color(video, 0), "application restarted video")
        video._toggle.setFocus()
        QTest.keyClick(video._toggle, Qt.Key.Key_Space)
        assert not video._body.isVisible()
        assert video._player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        QTest.keyClick(video._toggle, Qt.Key.Key_Space)
        assert video._body.isVisible()
        assert video._player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        assert checkpoint_hits == []

        # The local exception does not claim other keys, modifiers or controls.
        video._play.setFocus()
        QTest.keyClick(video._play, Qt.Key.Key_C)
        assert checkpoint_hits == ["checkpoint"]
        QTest.keyClick(video._play, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        assert modified_hits == ["modified"]
        assert checkpoint_hits == ["checkpoint"]
        window.review._streams.setFocus()
        QTest.keyClick(window.review._streams, Qt.Key.Key_Space)
        assert checkpoint_hits == ["checkpoint", "checkpoint"]
        assert _hashes(package) == before
    finally:
        window.link.stop()
        window.close()
        window.deleteLater()
        qapp.processEvents()
