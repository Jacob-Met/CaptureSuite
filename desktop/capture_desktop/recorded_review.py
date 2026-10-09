# SPDX-License-Identifier: GPL-3.0-only
"""A modeless recorded-package Review window with its own session context."""

from __future__ import annotations

from pathlib import Path

from capture_protocol.generated.capture.v1 import control_pb2
from capture_session import load_review_summary
from capture_session.package_reader import SessionPackageError
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from . import theme
from .screen_review import ReviewScreen
from .state import CaptureState


class RecordedPackageWindow(QDialog):
    """Reuse Review without connecting to or retargeting the capture daemon."""

    export_requested = Signal(str)

    def __init__(self, package_path: str, parent: QWidget | None = None) -> None:
        # Admit the package with the maintained reader before allocating a viewer.
        path = str(Path(package_path).resolve())
        summary = load_review_summary(path)
        if summary.state not in {"finalized", "finalized_recovered"}:
            raise SessionPackageError(
                "Recorded Review requires a finalized or finalized_recovered package "
                f"(found {summary.state or 'unspecified'})."
            )

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(f"Recorded package — {summary.session_id}")
        self.resize(1100, 780)
        self.state = CaptureState(
            session_id=summary.session_id,
            package_path=path,
            session_state=control_pb2.SESSION_STATE_FINALIZED,
            elapsed_session_ns=summary.duration_ns,
            review_mode=True,
        )

        layout = QVBoxLayout(self)
        identity = QLabel(f"Recorded package · {summary.session_id}")
        identity.setTextFormat(Qt.TextFormat.PlainText)
        identity.setWordWrap(True)
        identity.setFont(theme.ui(12, bold=True))
        layout.addWidget(identity)
        location = QLabel(path)
        location.setTextFormat(Qt.TextFormat.PlainText)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        location.setWordWrap(True)
        location.setObjectName("Faint")
        layout.addWidget(location)

        self.review = ReviewScreen(self.state, self)
        layout.addWidget(self.review, 1)
        try:
            self.review.load_package(
                path, recovered=summary.state == "finalized_recovered"
            )
            # The maintained loader reports read failures in its banner and
            # returns None on both success and failure. A fresh view's Session
            # card stays unpopulated on that path; do not show an empty viewer
            # if a package disappears between admission and the widget's read.
            if self.review._card_session.text() == "—":
                raise SessionPackageError(self.review._banner.text())
        except Exception:
            self._release_media()
            self.deleteLater()
            raise
        self.review.export_requested.connect(self.export_requested.emit)
        self.finished.connect(self._release_media)

    def _release_media(self, _result: int = 0) -> None:
        # finished covers window-close, Escape and programmatic reject/accept.
        self.review._recorded_video.reset("Recorded package closed.")
