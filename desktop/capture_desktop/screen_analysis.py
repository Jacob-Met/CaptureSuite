# SPDX-License-Identifier: GPL-3.0-only
"""Offline Analysis workbench — jobs in QThread; figures in-app via PyQtGraph."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .persistence import DesktopPersistence
from .state import CaptureState, fmt_time
from .widgets_analysis_jobs import AnalysisJobExtras, peek_ml_bundle_summary
from .widgets_analysis_plots import FigureGallery, JobInspector
from .widgets_mappings import AnatomicalMappingPanel


class _AnalysisWorker(QObject):
    progress = Signal(str, float)
    finished = Signal(object)  # JobResult
    failed = Signal(str)

    def __init__(
        self,
        package: str,
        command: str,
        gap_policy: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._package = package
        self._command = command
        self._gap_policy = gap_policy
        self._extra = dict(extra or {})
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            from capture_analysis import JobParams, run

            def on_progress(stage: str, frac: float) -> None:
                self.progress.emit(stage, float(frac))

            result = run(
                self._package,
                JobParams(
                    command=self._command,
                    gap_policy=self._gap_policy,
                    extra=self._extra,
                ),
                progress=on_progress,
                cancel=self._cancel,
            )
            self.finished.emit(result)
        except InterruptedError:
            self.failed.emit("cancelled")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AnalysisScreen(QWidget):
    """Analysis workbench — never talks to the daemon."""

    def __init__(
        self,
        state: CaptureState,
        persistence: DesktopPersistence | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._persistence = persistence
        self._package = ""
        self._last_job_dir = ""
        self._thread: QThread | None = None
        self._worker: _AnalysisWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        title = QLabel("Analysis")
        title.setFont(theme.ui(14, bold=True))
        root.addWidget(title)

        self._banner = QLabel(
            "Offline jobs write under processing/jobs/. Raw streams are never modified."
        )
        self._banner.setObjectName("Dim")
        self._banner.setWordWrap(True)
        root.addWidget(self._banner)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left = QWidget()
        left.setMinimumWidth(300)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        self._build_controls(left_layout)
        self._mappings = AnatomicalMappingPanel(persistence)
        left_layout.addWidget(self._mappings)
        splitter.addWidget(left)

        self._gallery = FigureGallery()
        splitter.addWidget(self._gallery)

        self._inspector = JobInspector()
        self._inspector.setMinimumWidth(240)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

    def _build_controls(self, root: QVBoxLayout) -> None:
        path_row = QHBoxLayout()
        self._path = QLabel("No package selected")
        self._path.setObjectName("Dim")
        self._path.setWordWrap(True)
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.clicked.connect(self._browse)
        self._btn_use_open = QPushButton("Use open session")
        self._btn_use_open.clicked.connect(self._use_open_session)
        path_row.addWidget(self._path, 1)
        path_row.addWidget(self._btn_use_open)
        path_row.addWidget(self._btn_browse)
        root.addLayout(path_row)

        cards = QHBoxLayout()
        self._card_session = QLabel("—")
        self._card_sources = QLabel("—")
        self._card_gaps = QLabel("—")
        self._card_duration = QLabel("—")
        for label, widget in (
            ("Session", self._card_session),
            ("Sources", self._card_sources),
            ("Gaps", self._card_gaps),
            ("Duration", self._card_duration),
        ):
            box = QWidget()
            box.setObjectName("Card")
            col = QVBoxLayout(box)
            col.setContentsMargins(8, 6, 8, 6)
            head = QLabel(label)
            head.setObjectName("Faint")
            head.setFont(theme.ui(8))
            widget.setFont(theme.ui(10, bold=True))
            widget.setWordWrap(True)
            col.addWidget(head)
            col.addWidget(widget)
            cards.addWidget(box, 1)
        root.addLayout(cards)

        opts = QVBoxLayout()
        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel("Command"))
        self._command = QComboBox()
        for label, value in (
            ("QC only", "qc"),
            ("Features + plots", "all"),
            ("Features only", "features"),
            ("Plots only", "plots"),
            ("Pose (body teacher)", "pose"),
            ("Kinematics (Tier A)", "kinematics"),
            ("ML bundle", "ml_bundle"),
            ("Eval report", "eval"),
        ):
            self._command.addItem(label, value)
        self._command.currentIndexChanged.connect(self._on_command_changed)
        cmd_row.addWidget(self._command, 1)
        opts.addLayout(cmd_row)
        gap_row = QHBoxLayout()
        gap_row.addWidget(QLabel("Gap policy"))
        self._gap_policy = QComboBox()
        for policy in ("mask", "split", "fail"):
            self._gap_policy.addItem(policy, policy)
        gap_row.addWidget(self._gap_policy, 1)
        opts.addLayout(gap_row)
        root.addLayout(opts)

        self._extras = AnalysisJobExtras()
        self._extras.set_command("qc")
        root.addWidget(self._extras)

        actions = QHBoxLayout()
        self._btn_run = QPushButton("Run")
        self._btn_run.setObjectName("Primary")
        self._btn_run.clicked.connect(self._start_job)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._cancel_job)
        actions.addWidget(self._btn_run)
        actions.addWidget(self._btn_cancel)
        root.addLayout(actions)

        aux = QHBoxLayout()
        self._btn_open_job = QPushButton("Open job folder")
        self._btn_open_job.setEnabled(False)
        self._btn_open_job.clicked.connect(self._open_job_folder)
        self._btn_open_report = QPushButton("Open QC report (HTML)")
        self._btn_open_report.setEnabled(False)
        self._btn_open_report.clicked.connect(self._open_report)
        aux.addWidget(self._btn_open_job)
        aux.addWidget(self._btn_open_report)
        root.addLayout(aux)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        root.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(theme.mono(9))
        self._log.setPlaceholderText("Job log…")
        self._log.setMaximumHeight(160)
        root.addWidget(self._log)
        root.addStretch(1)

    def _on_command_changed(self) -> None:
        command = str(self._command.currentData() or "qc")
        self._extras.set_command(command)
        self._extras.refresh()

    def set_package(self, package_path: str) -> None:
        if not package_path:
            return
        self._package = package_path
        self._path.setText(package_path)
        self._extras.set_package(package_path)
        self._refresh_summary()
        self._sync_enabled()

    def refresh_from_state(self) -> None:
        if self._state.package_path:
            self.set_package(self._state.package_path)
        self._sync_enabled()

    def _recording_locked(self) -> bool:
        from capture_protocol.generated.capture.v1 import control_pb2

        return self._state.session_state in (
            control_pb2.SESSION_STATE_RECORDING,
            control_pb2.SESSION_STATE_ARMING,
        )

    def _sync_enabled(self) -> None:
        busy = self._thread is not None and self._thread.isRunning()
        locked = self._recording_locked()
        has_pkg = bool(self._package)
        self._btn_run.setEnabled(has_pkg and not busy and not locked)
        self._btn_cancel.setEnabled(busy)
        self._btn_browse.setEnabled(not busy)
        self._btn_use_open.setEnabled(not busy and bool(self._state.package_path))
        self._command.setEnabled(not busy)
        self._gap_policy.setEnabled(not busy)
        if locked:
            self._banner.setText(
                "Analysis is disabled while the session is arming or recording."
            )

    def _refresh_summary(self) -> None:
        try:
            from capture_session import load_review_summary

            summary = load_review_summary(self._package)
        except Exception as exc:  # noqa: BLE001
            self._banner.setText(f"Could not load package: {exc}")
            return
        self._banner.setText(
            f"State {summary.state}. Jobs write only under processing/jobs/."
        )
        self._card_session.setText(summary.session_id or "—")
        self._card_sources.setText(str(len(summary.source_ids)))
        self._card_gaps.setText(
            f"{len(summary.gaps)} · {summary.open_gap_count} open"
        )
        dur = summary.duration_ns / 1e9 if summary.duration_ns > 1 else 0.0
        self._card_duration.setText(fmt_time(dur) if dur else "unknown")

    def _browse(self) -> None:
        start = self._package or str(
            Path(os.environ.get("LOCALAPPDATA", "")) / "CaptureSuite" / "sessions"
        )
        path = QFileDialog.getExistingDirectory(self, "Select .mmsession package", start)
        if path:
            self.set_package(path)

    def _use_open_session(self) -> None:
        if self._state.package_path:
            self.set_package(self._state.package_path)

    def _append_log(self, line: str) -> None:
        self._log.append(line)

    def _start_job(self) -> None:
        if not self._package or (self._thread and self._thread.isRunning()):
            return
        if self._recording_locked():
            QMessageBox.warning(
                self,
                "Analysis",
                "Stop recording before running offline analysis.",
            )
            return
        command = str(self._command.currentData())
        gap_policy = str(self._gap_policy.currentData())
        err = self._extras.validate_for(command)
        if err:
            QMessageBox.warning(self, "Analysis", err)
            return
        extra = self._extras.build_extra(command)
        self._log.clear()
        self._gallery.clear()
        self._inspector.clear()
        self._append_log(f"Starting {command} on {self._package}")
        if extra:
            self._append_log(f"extra={extra}")
        self._progress.setValue(0)

        thread = QThread(self)
        worker = _AnalysisWorker(self._package, command, gap_policy, extra)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._sync_enabled()
        thread.start()

    def _cancel_job(self) -> None:
        if self._worker is not None:
            self._append_log("Cancel requested…")
            self._worker.request_cancel()

    @Slot(str, float)
    def _on_progress(self, stage: str, frac: float) -> None:
        self._progress.setValue(int(max(0.0, min(1.0, frac)) * 100))
        self._append_log(f"{stage} ({frac:.0%})")

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        job_dir = str(getattr(result, "job_dir", "") or "")
        status = str(getattr(result, "status", "") or "")
        job_id = str(getattr(result, "job_id", "") or "")
        self._last_job_dir = job_dir
        self._progress.setValue(100)
        self._append_log(f"Done status={status} job_id={job_id}")
        self._append_log(f"dir={job_dir}")
        self._btn_open_job.setEnabled(bool(job_dir))
        report = Path(job_dir) / "reports" / "qc.html" if job_dir else Path()
        self._btn_open_report.setEnabled(report.is_file())
        if job_dir:
            path = Path(job_dir)
            self._gallery.load_job_dir(path)
            self._inspector.load_job_dir(path)
            self._append_log("Figures loaded in-app (sync dashboard + gallery tabs).")
            ml_summary = peek_ml_bundle_summary(path)
            if ml_summary:
                self._append_log(ml_summary)
            eval_path = path / "eval" / "eval_report.json"
            if eval_path.is_file():
                self._append_log(f"Eval report: {eval_path.name}")
            self._extras.refresh()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._append_log(f"FAIL: {message}")
        if message != "cancelled":
            QMessageBox.warning(self, "Analysis failed", message)

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._sync_enabled()

    def _open_job_folder(self) -> None:
        if self._last_job_dir and Path(self._last_job_dir).is_dir():
            os.startfile(self._last_job_dir)  # noqa: S606 — explorer only

    def _open_report(self) -> None:
        path = Path(self._last_job_dir) / "reports" / "qc.html"
        if path.is_file():
            os.startfile(str(path))  # noqa: S606 — HTML QC external per workbench spec
