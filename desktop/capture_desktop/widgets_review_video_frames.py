# SPDX-License-Identifier: GPL-3.0-only
"""Viewer-owned, session-local comparison of two retained decoded images."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .review_video import media_time
from .review_video_frames import RetainedVideoFrame


class _FrameCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame: RetainedVideoFrame | None = None
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        if self.frame is None:
            painter.setPen(self.palette().text().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No retained frame")
            return
        image = self.frame.image
        size = image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRect(
            (self.width() - size.width()) // 2,
            (self.height() - size.height()) // 2,
            size.width(),
            size.height(),
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, image)


class FrameComparisonDialog(QDialog):
    """Closing hides the panel; package reset explicitly clears its two slots."""

    keep_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare recorded frames")
        self.setModal(False)
        self.resize(840, 540)
        self.frames: dict[str, RetainedVideoFrame | None] = {"A": None, "B": None}
        self._canvases: dict[str, _FrameCanvas] = {}
        self._metadata: dict[str, QLabel] = {}
        self._keep: dict[str, QPushButton] = {}
        self._clear: dict[str, QPushButton] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        hint = self._label(
            "Pause Recorded video, then keep its current decoded frame. "
            "You can choose another segment while this panel stays open."
        )
        root.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cards = QHBoxLayout(content)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(12)
        for slot in ("A", "B"):
            card = QWidget()
            card.setObjectName("Card")
            column = QVBoxLayout(card)
            column.setContentsMargins(8, 8, 8, 8)
            column.setSpacing(8)
            heading = QLabel(f"Frame {slot}")
            heading.setFont(theme.ui(11, bold=True))
            column.addWidget(heading)
            actions = QHBoxLayout()
            keep = QPushButton(f"Keep frame {slot}")
            clear = QPushButton(f"Clear {slot}")
            keep.setAccessibleName(f"Keep paused decoded frame as {slot}")
            clear.setAccessibleName(f"Clear retained frame {slot}")
            keep.clicked.connect(lambda _checked=False, s=slot: self.keep_requested.emit(s))
            clear.clicked.connect(lambda _checked=False, s=slot: self.clear_slot(s))
            for button in (keep, clear):
                button.installEventFilter(self)
                actions.addWidget(button)
            column.addLayout(actions)
            canvas = _FrameCanvas()
            canvas.setAccessibleName(f"Retained frame {slot} image")
            column.addWidget(canvas, 1)
            metadata = self._label("")
            metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            column.addWidget(metadata)
            self._keep[slot], self._clear[slot] = keep, clear
            self._canvases[slot], self._metadata[slot] = canvas, metadata
            cards.addWidget(card, 1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        note = self._label(
            "Frame PTS and player position are segment-local observations, not session "
            "time or a camera/checkpoint alignment. Images stay in memory until cleared "
            "or the package changes; nothing is saved or exported."
        )
        note.setObjectName("Faint")
        root.addWidget(note)
        self._notice = self._label("")
        self._notice.setObjectName("HonestyBanner")
        root.addWidget(self._notice)
        self.clear_all()

        # QObject destruction does not necessarily drop a retained Python wrapper.
        # Release image references without calling Qt methods during destruction.
        frames, canvases = self.frames, self._canvases

        def release_images(*_args) -> None:
            for slot in frames:
                frames[slot] = None
                canvases[slot].frame = None

        self.destroyed.connect(release_images)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setFont(theme.ui(8))
        return label

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            watched in (*self._keep.values(), *self._clear.values())
            and event.type() == QEvent.Type.ShortcutOverride
            and event.key() == Qt.Key.Key_Space
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def set_notice(self, message: str) -> None:
        self._notice.setText(message)

    def set_frame(self, slot: str, frame: RetainedVideoFrame) -> None:
        if slot not in self.frames:
            raise ValueError("Choose frame A or B.")
        self.frames[slot] = frame
        self._canvases[slot].frame = frame
        self._canvases[slot].update()
        stamp = f"{frame.frame_start_us} µs" if frame.frame_start_us is not None else "unavailable"
        self._metadata[slot].setText(
            f"Source: {frame.segment.source_id}\nStream: {frame.segment.stream_id}\n"
            f"Package path: {frame.segment.relative_path}\n"
            f"Decoded frame PTS: {stamp}\n"
            f"Player position when kept: {media_time(frame.player_position_ms)}\n"
            f"Decoded pixels: {frame.decoded_width} × {frame.decoded_height}; "
            f"presentation rotation {frame.rotation_degrees}°, "
            f"mirrored {'yes' if frame.mirrored else 'no'}"
        )
        self._clear[slot].setEnabled(True)
        self.set_notice(f"Frame {slot} retained. The other slot and playback are unchanged.")

    def clear_slot(self, slot: str) -> None:
        if slot not in self.frames:
            raise ValueError("Choose frame A or B.")
        self.frames[slot] = None
        self._canvases[slot].frame = None
        self._canvases[slot].update()
        self._metadata[slot].setText("No frame retained.")
        self._clear[slot].setEnabled(False)
        self.set_notice(f"Frame {slot} cleared.")

    def clear_all(self) -> None:
        for slot in self.frames:
            self.clear_slot(slot)
        self.set_notice("Pause a loaded video, then keep frame A or B.")
