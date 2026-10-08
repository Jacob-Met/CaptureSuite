# SPDX-License-Identifier: GPL-3.0-only
"""Native saved-result picker and read-only analysis details."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_history import SavedJob, SavedJobDetails, list_saved_jobs, load_saved_job


class AnalysisHistory(QWidget):
    """Explicitly open a saved result; choosing one never starts or edits a job."""

    job_loaded = Signal(object)  # SavedJobDetails
    view_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._package = ""
        self._busy = False
        self._loaded: SavedJobDetails | None = None
        self._dialog: QDialog | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        row = QHBoxLayout()
        label = QLabel("Saved analysis")
        label.setFont(theme.ui(9, bold=True))
        row.addWidget(label)
        self._jobs = QComboBox()
        self._jobs.setObjectName("analysisHistoryJob")
        self._jobs.setAccessibleName("Saved analysis job")
        self._jobs.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._jobs.setMinimumContentsLength(24)
        self._jobs.currentIndexChanged.connect(self._selection_changed)
        row.addWidget(self._jobs, 1)
        self._refresh = QPushButton("Refresh")
        self._refresh.setObjectName("analysisHistoryRefresh")
        self._refresh.clicked.connect(lambda: self.refresh())
        row.addWidget(self._refresh)
        self._open = QPushButton("Open saved result")
        self._open.setObjectName("analysisHistoryOpen")
        self._open.clicked.connect(self._open_selected)
        row.addWidget(self._open)
        self._details = QPushButton("Result details…")
        self._details.setObjectName("analysisHistoryDetails")
        self._details.clicked.connect(self._show_details)
        row.addWidget(self._details)
        root.addLayout(row)
        self._status = QLabel("Select a package to browse its saved analysis.")
        self._status.setObjectName("Dim")
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        self._status.setWordWrap(True)
        self._status.setFont(theme.ui(8))
        root.addWidget(self._status)
        self._sync_enabled()

    @property
    def package(self) -> str:
        return self._package

    @property
    def loaded_job_id(self) -> str:
        return self._loaded.job.job_id if self._loaded else ""

    def set_package(self, package: str) -> None:
        identity = str(Path(package).resolve()) if package else ""
        if identity == self._package:
            return
        self._package = identity
        self.clear_loaded()
        self.view_cleared.emit()
        self.refresh()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._sync_enabled()

    def clear_loaded(self) -> None:
        self._loaded = None
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None
        self._sync_enabled()

    def _selected(self) -> SavedJob | None:
        value = self._jobs.currentData()
        return value if isinstance(value, SavedJob) else None

    def _sync_enabled(self, *_args) -> None:
        row = self._selected()
        self._jobs.setEnabled(bool(self._package) and not self._busy)
        self._refresh.setEnabled(bool(self._package) and not self._busy)
        self._open.setEnabled(row is not None and not row.problem and not self._busy)
        self._details.setEnabled(self._loaded is not None and not self._busy)
        if row is not None and row.problem:
            self._status.setText(f"{row.job_id}: {row.problem}")

    def _selection_changed(self, *_args) -> None:
        row = self._selected()
        if row is not None and not row.problem:
            self._status.setText(
                f"Selected {row.job_id} · {row.status}. Open to inspect this result."
            )
        self._sync_enabled()

    def refresh(self, preferred_job_id: str | None = None) -> None:
        selected = self._selected()
        preferred = preferred_job_id or (selected.job_id if selected else "")
        self._jobs.blockSignals(True)
        self._jobs.clear()
        try:
            jobs = list_saved_jobs(self._package) if self._package else []
        except (OSError, ValueError) as exc:
            jobs = []
            message = f"Could not read saved analysis: {exc}"
        else:
            usable = sum(not job.problem for job in jobs)
            message = (
                f"{usable} saved result(s). Select a job and open it in the gallery and inspector."
                if usable else "No readable saved analysis results in this package."
            )
            unavailable = len(jobs) - usable
            if unavailable:
                message += f" {unavailable} unavailable job(s) are listed with their reason."
        found = -1
        for job in jobs:
            text = f"{job.job_id} · {job.status if not job.problem else 'unavailable'}"
            self._jobs.addItem(text, job)
            if job.job_id == preferred:
                found = self._jobs.count() - 1
        if found >= 0:
            self._jobs.setCurrentIndex(found)
        self._jobs.blockSignals(False)
        if self._loaded and not any(
            job.job_id == self._loaded.job.job_id and not job.problem for job in jobs
        ):
            self.clear_loaded()
            self.view_cleared.emit()
        if self._loaded is not None:
            self.show_loaded(self._loaded)
        else:
            self._status.setText(message)
        self._sync_enabled()

    def show_loaded(self, details: SavedJobDetails) -> None:
        self._loaded = details
        job = details.job
        when = f" · {job.created_utc}" if job.created_utc else ""
        self._status.setText(f"Viewing {job.job_id} · {job.status}{when}")
        self._sync_enabled()

    def _open_selected(self) -> None:
        selected = self._selected()
        if self._busy or selected is None or selected.problem:
            return
        try:
            details = load_saved_job(self._package, selected.job_id)
        except (OSError, ValueError, UnicodeError) as exc:
            self._status.setText(f"Could not open {selected.job_id}: {exc}. Refresh the job list.")
            return
        self.show_loaded(details)
        self.job_loaded.emit(details)

    def _show_details(self) -> None:
        if self._loaded is None or self._busy:
            return
        if self._dialog is not None:
            self._dialog.close()
        details = self._loaded
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setObjectName("analysisHistoryDetailsDialog")
        dialog.setWindowTitle(f"Analysis result — {details.job.job_id}")
        dialog.resize(780, 560)
        layout = QVBoxLayout(dialog)
        location = QLabel(str(details.job.directory))
        location.setTextFormat(Qt.TextFormat.PlainText)
        location.setWordWrap(True)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(location)
        tabs = QTabWidget()
        for title, text in (
            ("Parameters", details.params_text),
            ("Log", details.log_text),
            ("Manifest", json.dumps(details.manifest, ensure_ascii=False, indent=2,
                                    sort_keys=True)),
        ):
            editor = QPlainTextEdit()
            editor.setObjectName(f"analysisHistory{title}")
            editor.setReadOnly(True)
            editor.setFont(theme.mono(9))
            editor.setPlainText(text)
            tabs.addTab(editor, title)
        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.finished.connect(self._details_closed)
        self._dialog = dialog
        dialog.show()

    def _details_closed(self, _result: int) -> None:
        self._dialog = None
