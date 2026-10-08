# SPDX-License-Identifier: GPL-3.0-only
"""Lazy native playback of one explicitly selected retained video segment."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .review_video import local_video_path, media_time, recorded_video_segments


class RecordedVideoReview(QWidget):
    """A local-media clock, deliberately separate from session timestamps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._package = ""
        self._segments = ()
        self._generation = 0
        self._player: QMediaPlayer | None = None
        self._video: QVideoWidget | None = None
        self._ready = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self._toggle = QToolButton()
        self._toggle.setText("Recorded video")
        self._toggle.setCheckable(True)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        root.addWidget(self._toggle)
        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        root.addWidget(self._body)
        self._body.hide()
        self._toggle.toggled.connect(self._expand)
        note = self._label(
            "Position is within this media segment, not session time. "
            "This view does not align cameras or checkpoints. Video only; audio is not played."
        )
        note.setObjectName("Faint")
        body.addWidget(note)
        row = QHBoxLayout()
        caption = QLabel("&Segment")
        self._choice = QComboBox()
        self._choice.setAccessibleName("Recorded video segment")
        self._choice.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._choice.setMinimumContentsLength(20)
        caption.setBuddy(self._choice)
        self._reload = QPushButton("Reload selected")
        row.addWidget(caption)
        row.addWidget(self._choice, 1)
        row.addWidget(self._reload)
        body.addLayout(row)
        self._identity = self._label("")
        self._identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self._identity)
        self._viewport = QVBoxLayout()
        self._placeholder = self._label("Choose a recorded video segment.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setMinimumHeight(180)
        self._viewport.addWidget(self._placeholder)
        body.addLayout(self._viewport)
        controls = QHBoxLayout()
        self._play = QPushButton("Play")
        self._play.setAccessibleName("Play or pause selected video")
        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 10_000)
        self._seek.setTracking(False)
        self._seek.setAccessibleName("Position within selected video segment")
        self._clock = self._label("Media position —")
        controls.addWidget(self._play)
        controls.addWidget(self._seek, 1)
        controls.addWidget(self._clock)
        body.addLayout(controls)
        self._status = self._label("")
        self._status.setObjectName("HonestyBanner")
        body.addWidget(self._status)
        self._choice.currentIndexChanged.connect(self._open_selected)
        self._reload.clicked.connect(self._open_selected)
        self._play.clicked.connect(self._play_pause)
        self._seek.valueChanged.connect(self._seek_to)
        self.reset()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setFont(theme.ui(8))
        return label

    def _expand(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        if not expanded and self._player is not None:
            self._player.pause()
        self._body.setVisible(expanded)

    def _retire_media(self) -> None:
        self._generation += 1
        player, video = self._player, self._video
        self._player = None
        self._video = None
        self._ready = False
        if video is not None:
            video.hide()
            self._viewport.removeWidget(video)
        if player is not None:
            player.stop()
            player.setVideoOutput(None)
            player.setSource(QUrl())
            player.deleteLater()
        if video is not None:
            video.deleteLater()
        self._placeholder.show()
        self._play.setText("Play")
        self._play.setEnabled(False)
        self._seek.setEnabled(False)
        self._seek.blockSignals(True)
        self._seek.setValue(0)
        self._seek.blockSignals(False)
        self._clock.setText("Media position —")

    def reset(self, message: str = "Open a finalized package to inspect recorded video.") -> None:
        self._retire_media()
        self._package = ""
        self._segments = ()
        self._choice.blockSignals(True)
        self._choice.clear()
        self._choice.addItem("Choose a recorded video segment…")
        self._choice.blockSignals(False)
        self._choice.setEnabled(False)
        self._reload.setEnabled(False)
        self._identity.clear()
        self._toggle.setText("Recorded video")
        self._status.setText(message)

    def load_package(self, package_path: str, *, state: str) -> None:
        self.reset("Loading recorded video inventory…")
        if state not in {"finalized", "finalized_recovered"}:
            self._status.setText("Recorded video review requires a finalized package.")
            return
        try:
            segments = recorded_video_segments(package_path)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(
                f"Could not read video inventory: {exc}. Reopen the package to retry."
            )
            return
        self._package = package_path
        self._segments = segments
        self._choice.blockSignals(True)
        for segment in segments:
            self._choice.addItem(segment.label)
        self._choice.blockSignals(False)
        self._choice.setEnabled(bool(segments))
        self._toggle.setText(f"Recorded video · {len(segments)} listed segment(s)")
        self._status.setText(
            "Choose a segment, then press Play. Nothing plays automatically."
            if segments
            else "No recorded MKV segments were listed in this package."
        )

    def _open_selected(self, *_args) -> None:
        self._retire_media()
        self._identity.clear()
        index = self._choice.currentIndex() - 1
        self._reload.setEnabled(0 <= index < len(self._segments))
        if index < 0 or index >= len(self._segments):
            self._status.setText("Choose a recorded video segment.")
            return
        segment = self._segments[index]
        self._identity.setText(
            f"Source: {segment.source_id} · Stream: {segment.stream_id}\n"
            f"Package path: {segment.relative_path}"
        )
        try:
            path = local_video_path(self._package, segment)
        except (OSError, ValueError) as exc:
            self._status.setText(
                f"Could not open the selected segment: {exc}. "
                "Restore its availability and reload, or choose another segment."
            )
            return
        generation = self._generation
        player = QMediaPlayer(self)
        video = QVideoWidget(self._body)
        video.setMinimumHeight(180)
        self._viewport.addWidget(video)
        self._placeholder.hide()
        self._player, self._video = player, video
        player.setVideoOutput(video)
        # A new player/output per selection and guarded callbacks retire queued old media events.
        for signal in (
            player.mediaStatusChanged,
            player.playbackStateChanged,
            player.durationChanged,
            player.positionChanged,
            player.seekableChanged,
            player.hasVideoChanged,
        ):
            signal.connect(lambda *_args, p=player, g=generation: self._sync(p, g))
        player.errorOccurred.connect(
            lambda _error, text, p=player, g=generation: self._failed(p, g, text)
        )
        self._status.setText("Loading selected segment…")
        player.setSource(QUrl.fromLocalFile(str(path)))

    def _current(self, player: QMediaPlayer, generation: int) -> bool:
        return player is self._player and generation == self._generation

    def _failed(self, player: QMediaPlayer, generation: int, text: str) -> None:
        if not self._current(player, generation):
            return
        self._retire_media()
        self._status.setText(
            f"Cannot play this segment: {text or 'the decoder refused the media'}. "
            "Reload to retry or choose another segment; original files are unchanged."
        )

    def _sync(self, player: QMediaPlayer, generation: int) -> None:
        if not self._current(player, generation):
            return
        status = player.mediaStatus()
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._failed(player, generation, player.errorString())
            return
        loaded = status in {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        }
        self._ready = loaded and player.hasVideo()
        self._play.setEnabled(self._ready)
        duration, position = player.duration(), player.position()
        self._seek.setEnabled(self._ready and player.isSeekable() and duration > 0)
        self._clock.setText(
            f"Media position {media_time(position)} / {media_time(duration)}"
            if duration > 0
            else f"Media position {media_time(position)} / duration unavailable"
        )
        if not self._seek.isSliderDown():
            self._seek.blockSignals(True)
            self._seek.setValue(min(10_000, position * 10_000 // duration) if duration > 0 else 0)
            self._seek.blockSignals(False)
        playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._play.setText("Pause" if playing else "Play")
        if loaded:
            self._status.setText(
                "Playing this segment."
                if playing
                else "Ready. Press Play to inspect this segment."
                if player.hasVideo()
                else "No video track is available in this segment. Choose another segment."
            )
        if status == QMediaPlayer.MediaStatus.StalledMedia:
            self._status.setText("Playback is waiting for media. Pause or reload to retry.")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._status.setText("End of this segment. Press Play to start it again.")

    def _play_pause(self) -> None:
        player = self._player
        if player is None or not self._ready:
            return
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
        else:
            if player.duration() > 0 and player.position() >= player.duration():
                player.setPosition(0)
            player.play()

    def _seek_to(self, value: int) -> None:
        player = self._player
        if player is not None and self._ready and player.isSeekable() and player.duration() > 0:
            player.setPosition(player.duration() * value // 10_000)

    def hideEvent(self, event) -> None:  # noqa: N802
        if self._player is not None:
            self._player.pause()
        super().hideEvent(event)
