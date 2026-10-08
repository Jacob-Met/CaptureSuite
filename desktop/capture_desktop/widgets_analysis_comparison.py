# SPDX-License-Identifier: GPL-3.0-only
"""Native read-only inspection and comparison of retained analysis settings."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_job_comparison import (
    JobParameterError,
    JobParameters,
    ParameterDifference,
    compare_job_parameters,
    load_job_parameters,
    revalidate_job_parameters,
)


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _viewer() -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setFont(theme.mono(9))
    return view


def _provenance(source: JobParameters) -> str:
    manifest = source.manifest
    return "\n".join(
        (
            f"Job: {source.job_id}",
            f"Status: {manifest['status']}",
            f"Session: {source.session_id}",
            "Recorded analysis version: "
            f"{manifest.get('captureAnalysisVersion', '(not recorded)')}",
            "Recorded capture manifest SHA-256: "
            f"{manifest.get('manifestSha256', '(not recorded)')}",
            f"Recorded paramsDigest (verified): {manifest['paramsDigest']}",
            f"Actual params.json SHA-256: {source.params_sha256}",
            f"Actual job_manifest.json SHA-256: {source.manifest_sha256}",
            f"Saved directory: {source.job_dir}",
        )
    )


class JobParameterDialog(QDialog):
    """Inspect one immutable read and explicitly compare a chosen saved sibling."""

    def __init__(self, source: JobParameters, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        revalidate_job_parameters(source)
        self.setWindowTitle("Saved analysis parameters")
        self.resize(1080, 760)
        self._job_dir = source.job_dir
        self._source: JobParameters | None = source
        self._other_dir: Path | None = None
        self._rows: tuple[ParameterDifference, ...] = ()

        root = QVBoxLayout(self)
        self._heading = _label()
        self._heading.setFont(theme.ui(11, bold=True))
        root.addWidget(self._heading)
        self._notice = _label(
            "Read-only saved settings. Comparing parameters does not rerun a job or establish "
            "that its data, software or results are equivalent."
        )
        self._notice.setObjectName("Dim")
        root.addWidget(self._notice)
        self._error = _label()
        self._error.setObjectName("Warning")
        root.addWidget(self._error)

        actions = QHBoxLayout()
        self._choose = QPushButton("Compare with saved job…")
        self._choose.setObjectName("ChooseComparisonJob")
        self._choose.clicked.connect(self._choose_other)
        self._reload = QPushButton("Reload saved parameters")
        self._reload.setObjectName("ReloadJobParameters")
        self._reload.clicked.connect(self._reload_sources)
        actions.addWidget(self._choose)
        actions.addWidget(self._reload)
        actions.addStretch(1)
        root.addLayout(actions)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)
        params_page = QWidget()
        params_layout = QVBoxLayout(params_page)
        self._params = _viewer()
        self._params.setObjectName("SavedParametersJson")
        params_layout.addWidget(self._params, 1)
        params_layout.addWidget(
            _label("Input provenance · recorded capture identity is not reverified here")
        )
        self._provenance = _viewer()
        self._provenance.setMaximumHeight(165)
        params_layout.addWidget(self._provenance)
        self._tabs.addTab(params_page, "Loaded job parameters")

        compare_page = QWidget()
        compare_layout = QVBoxLayout(compare_page)
        self._other = _label("Choose a different completed job from this session's jobs directory.")
        compare_layout.addWidget(self._other)
        self._count = _label("No comparison selected")
        compare_layout.addWidget(self._count)
        self._table = QTableWidget(0, 4)
        self._table.setObjectName("ParameterDifferences")
        self._table.setHorizontalHeaderLabels(
            ["Parameter", "Difference", "Other job", "Loaded job"]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setWordWrap(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.currentCellChanged.connect(self._show_difference)
        compare_layout.addWidget(self._table, 1)
        self._selected = _label("Select a difference to read its complete values.")
        compare_layout.addWidget(self._selected)
        values = QSplitter()
        self._other_value = _viewer()
        self._loaded_value = _viewer()
        self._other_value.setPlaceholderText("Complete value in the other job")
        self._loaded_value.setPlaceholderText("Complete value in the loaded job")
        values.addWidget(self._other_value)
        values.addWidget(self._loaded_value)
        values.setMaximumHeight(190)
        compare_layout.addWidget(values)
        self._tabs.addTab(compare_page, "Parameter comparison")

        provenance_page = QWidget()
        provenance_layout = QVBoxLayout(provenance_page)
        self._comparison_provenance = _viewer()
        self._comparison_provenance.setPlaceholderText(
            "Choose a comparison to inspect both source records."
        )
        provenance_layout.addWidget(self._comparison_provenance)
        self._tabs.addTab(provenance_page, "Comparison provenance")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._show_loaded(source)

    def _show_loaded(self, source: JobParameters) -> None:
        self._source = source
        self._heading.setText(f"Loaded job: {source.job_id} · session {source.session_id}")
        self._params.setPlainText(
            json.dumps(source.params, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        )
        self._provenance.setPlainText(_provenance(source))
        self._choose.setEnabled(True)
        self._error.clear()

    def _clear_comparison(self) -> None:
        self._rows = ()
        self._table.setRowCount(0)
        self._count.setText("No valid comparison")
        self._other.setText("Choose a different completed job from this session's jobs directory.")
        self._selected.setText("Select a difference to read its complete values.")
        self._other_value.clear()
        self._loaded_value.clear()
        self._comparison_provenance.clear()

    def _invalidate_loaded(self, message: str) -> None:
        self._source = None
        self._params.clear()
        self._provenance.clear()
        self._choose.setEnabled(False)
        self._clear_comparison()
        self._error.setText(f"{message} Use Reload saved parameters to read the current files.")

    def _choose_other(self) -> None:
        if self._source is None:
            return
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose a completed job from the same session", str(self._job_dir.parent)
        )
        if chosen:
            self._read_other(Path(chosen))

    def _read_other(self, path: Path) -> None:
        if self._source is None:
            return
        self._other_dir = path
        try:
            revalidate_job_parameters(self._source)
        except JobParameterError as exc:
            self._invalidate_loaded(str(exc))
            return
        try:
            selected = path.resolve(strict=True)
            if selected.parent != self._job_dir.parent or selected == self._job_dir:
                raise JobParameterError(
                    "Choose a different job in the loaded session's jobs directory."
                )
            other = load_job_parameters(path)
            rows = compare_job_parameters(other, self._source)
        except (JobParameterError, OSError) as exc:
            try:
                revalidate_job_parameters(self._source)
            except JobParameterError as changed:
                self._invalidate_loaded(str(changed))
                return
            self._clear_comparison()
            self._error.setText(f"Comparison unavailable: {exc}")
            self._tabs.setCurrentIndex(1)
            return
        self._other_dir = other.job_dir
        self._error.clear()
        self._rows = rows
        self._other.setText(f"Other job: {other.job_id} · {other.manifest['status']}")
        self._comparison_provenance.setPlainText(
            "OTHER JOB\n"
            + _provenance(other)
            + "\n\nLOADED JOB\n"
            + _provenance(self._source)
            + "\n\nThese are the exact saved metadata reads checked for this comparison. "
            "Reload explicitly reads later changes. Historical manifest self-hashes and "
            "raw capture/artifact hashes are not verified by this viewer."
        )
        self._count.setText(
            f"{len(rows)} parameter difference{'s' if len(rows) != 1 else ''}"
            if rows
            else "No parameter differences. Source data, software and results may still differ."
        )
        self._table.setRowCount(len(rows))
        changes = {
            "only_other": "Only in other",
            "only_loaded": "Only in loaded",
            "changed": "Changed",
        }
        for index, row in enumerate(rows):
            for column, value in enumerate(
                (row.pointer, changes[row.change], row.other_json, row.loaded_json)
            ):
                full = "(absent)" if value is None else value
                preview = full if len(full) <= 160 else full[:157] + "…"
                item = QTableWidgetItem(preview)
                item.setToolTip(json.dumps(full, ensure_ascii=False) if column == 0 else full)
                self._table.setItem(index, column, item)
        self._tabs.setCurrentIndex(1)
        if rows:
            self._table.setCurrentCell(0, 0)
            self._show_difference(0)
            self._table.setFocus()
        else:
            self._selected.setText("The saved parameter objects contain the same values and types.")
            self._other_value.clear()
            self._loaded_value.clear()

    def _show_difference(self, row: int, *_unused: int) -> None:
        if not 0 <= row < len(self._rows):
            return
        difference = self._rows[row]
        self._selected.setText(
            "Parameter path: "
            + json.dumps(difference.pointer, ensure_ascii=False)
            + " · / separates keys or array indexes; ~1 means / and ~0 means ~ within a key."
        )
        for view, value in (
            (self._other_value, difference.other_json),
            (self._loaded_value, difference.loaded_json),
        ):
            view.setPlainText("(absent — no such field)" if value is None else value)

    def _reload_sources(self) -> None:
        try:
            source = load_job_parameters(self._job_dir)
        except JobParameterError as exc:
            self._invalidate_loaded(str(exc))
            return
        self._show_loaded(source)
        self._clear_comparison()
        if self._other_dir is not None:
            self._read_other(self._other_dir)


class JobParameterBar(QWidget):
    """Compose inspection with the existing inspector's clear/load lifecycle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source: JobParameters | None = None
        self._dialog: JobParameterDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._button = QPushButton("Parameters / compare…")
        self._button.setObjectName("InspectJobParameters")
        self._button.setEnabled(False)
        self._button.clicked.connect(self._open)
        layout.addWidget(self._button)
        self._status = _label("Load a completed saved job to inspect its parameters.")
        self._status.setObjectName("Dim")
        self._status.setFont(theme.ui(8))
        layout.addWidget(self._status)

    def clear(self) -> None:
        self._source = None
        self._button.setEnabled(False)
        self._status.setText("Load a completed saved job to inspect its parameters.")
        dialog, self._dialog = self._dialog, None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        try:
            self._source = load_job_parameters(job_dir)
        except JobParameterError as exc:
            self._status.setText(f"Parameters unavailable: {exc}")
            return
        self._button.setEnabled(True)
        self._status.setText("Read-only saved settings; compare another job from this session.")

    def _open(self) -> None:
        if self._source is None:
            return
        try:
            revalidate_job_parameters(self._source)
            dialog = JobParameterDialog(self._source, self)
        except JobParameterError as exc:
            self.clear()
            self._status.setText(f"Parameters unavailable: {exc} Reload this job to try again.")
            return
        if self._dialog is not None:
            previous, self._dialog = self._dialog, None
            previous.close()
            previous.deleteLater()
        self._dialog = dialog
        dialog.finished.connect(lambda: self._closed(dialog))
        dialog.open()

    def _closed(self, dialog: JobParameterDialog) -> None:
        if self._dialog is dialog:
            self._dialog = None
        dialog.deleteLater()
