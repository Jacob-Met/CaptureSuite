# SPDX-License-Identifier: GPL-3.0-only
"""Browse and export retained numeric tables inside the analysis workspace."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets_feature_time import FeatureTimeSelection


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class _TableTask(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, action, parent):
        super().__init__(parent)
        self._action = action

    def run(self) -> None:
        try:
            result = self._action(self.isInterruptionRequested, self.progress.emit)
        except Exception as exc:  # UI boundary; retain the source and expose the failure.
            self.failed.emit("\n".join([str(exc), *getattr(exc, "__notes__", ())]))
        else:
            self.succeeded.emit(result)


class FeatureTableView(QWidget):
    """An explicit saved-table selection, real preview and ordered export."""

    busy_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job: Path | None = None
        self._generation = 0
        self._tasks: set[_TableTask] = set()
        self._export_task: _TableTask | None = None
        self._preview_ready = False
        self._exported: Path | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(8)

        heading = QHBoxLayout()
        heading.addWidget(QLabel("Saved table"))
        self._tables = QComboBox()
        self._tables.setObjectName("analysisFeatureTable")
        self._tables.setAccessibleName("Saved feature table")
        self._tables.setMinimumContentsLength(20)
        self._tables.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        heading.addWidget(self._tables, 1)
        self._row_count = _label()
        heading.addWidget(self._row_count)
        root.addLayout(heading)

        self._warning = _label()
        self._warning.setObjectName("Dim")
        root.addWidget(self._warning)

        split = QSplitter()
        split.setChildrenCollapsible(False)
        selection = QWidget()
        selection_layout = QVBoxLayout(selection)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        self._columns = QTreeWidget()
        self._columns.setObjectName("analysisExportColumns")
        self._columns.setAccessibleName("Columns in export order")
        self._columns.setHeaderLabels(["Column", "Unit", "Calibration"])
        self._columns.setRootIsDecorated(False)
        self._columns.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._columns.setMinimumWidth(260)
        self._columns.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._columns.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._columns.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        selection_layout.addWidget(self._columns, 1)
        choices = QHBoxLayout()
        self._all = QPushButton("All")
        self._none = QPushButton("None")
        self._up = QPushButton("Up")
        self._down = QPushButton("Down")
        self._up.setAccessibleName("Move column earlier in export")
        self._down.setAccessibleName("Move column later in export")
        for button in (self._all, self._none, self._up, self._down):
            choices.addWidget(button)
        selection_layout.addLayout(choices)
        split.addWidget(selection)

        preview_host = QWidget()
        preview_layout = QVBoxLayout(preview_host)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_note = _label("Open a saved result to inspect its values.")
        self._preview_note.setObjectName("Dim")
        preview_layout.addWidget(self._preview_note)
        self._preview = QTableWidget()
        self._preview.setObjectName("analysisFeaturePreview")
        self._preview.setAccessibleName("Saved feature values")
        self._preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview.setFont(theme.mono(9))
        self._preview.setAlternatingRowColors(True)
        preview_layout.addWidget(self._preview, 1)
        split.addWidget(preview_host)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

        self._time_selection = FeatureTimeSelection()
        root.addWidget(self._time_selection)

        destination = QHBoxLayout()
        destination.addWidget(QLabel("Save in"))
        self._parent_path = QLineEdit(str(Path.home()))
        self._parent_path.setObjectName("analysisExportParent")
        self._parent_path.setAccessibleName("Export parent folder")
        destination.addWidget(self._parent_path, 1)
        self._browse = QPushButton("Choose folder…")
        destination.addWidget(self._browse)
        root.addLayout(destination)
        options = QHBoxLayout()
        options.addWidget(QLabel("New folder"))
        self._folder_name = QLineEdit("table-export")
        self._folder_name.setObjectName("analysisExportName")
        self._folder_name.setAccessibleName("New export folder name")
        options.addWidget(self._folder_name, 1)
        self._format = QComboBox()
        self._format.setObjectName("analysisExportFormat")
        self._format.setAccessibleName("Export format")
        for label, value in (
            ("CSV + Parquet", "both"), ("CSV", "csv"), ("Parquet", "parquet"),
        ):
            self._format.addItem(label, value)
        options.addWidget(self._format)
        self._export = QPushButton("Export selected columns")
        self._export.setObjectName("Primary")
        self._export.setAccessibleName("Export selected feature columns")
        options.addWidget(self._export)
        root.addLayout(options)
        feedback = QHBoxLayout()
        self._status = _label()
        self._status.setObjectName("analysisTableStatus")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        feedback.addWidget(self._status, 1)
        self._cancel = QPushButton("Cancel export")
        self._cancel.setVisible(False)
        feedback.addWidget(self._cancel)
        self._open = QPushButton("Open export folder")
        self._open.setEnabled(False)
        feedback.addWidget(self._open)
        root.addLayout(feedback)
        self._progress = QProgressBar()
        self._progress.hide()
        root.addWidget(self._progress)

        self._time_selection.selection_changed.connect(self._sync)
        self._tables.currentIndexChanged.connect(self._select_table)
        self._columns.itemChanged.connect(self._sync)
        self._parent_path.textChanged.connect(self._sync)
        self._folder_name.textChanged.connect(self._sync)
        self._all.clicked.connect(lambda: self._set_checks(Qt.CheckState.Checked))
        self._none.clicked.connect(lambda: self._set_checks(Qt.CheckState.Unchecked))
        self._up.clicked.connect(lambda: self._move_column(-1))
        self._down.clicked.connect(lambda: self._move_column(1))
        self._browse.clicked.connect(self._choose_parent)
        self._export.clicked.connect(self._start_export)
        self._cancel.clicked.connect(self._cancel_export)
        self._open.clicked.connect(self._open_export)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)
        self.clear()

    @property
    def busy(self) -> bool:
        return self._export_task is not None

    def _task(self, action, on_success, *, generation=None) -> _TableTask:
        token = self._generation if generation is None else generation
        worker = _TableTask(action, self)
        self._tasks.add(worker)
        worker.succeeded.connect(
            lambda value: on_success(value) if token == self._generation else None
        )
        worker.failed.connect(
            lambda message: self._status.setText(message) if token == self._generation else None
        )
        worker.finished.connect(lambda: self._finished(worker))
        return worker

    def _finished(self, worker: _TableTask) -> None:
        self._tasks.discard(worker)
        if worker is self._export_task:
            self._export_task = None
            self._progress.hide()
            self._cancel.hide()
            self.busy_changed.emit(False)
        worker.deleteLater()
        self._sync()

    def clear(self) -> None:
        self._generation += 1
        for worker in self._tasks:
            worker.requestInterruption()
        self._job = None
        self._preview_ready = False
        self._tables.blockSignals(True)
        self._tables.clear()
        self._tables.blockSignals(False)
        self._columns.clear()
        self._preview.clear()
        self._preview.setRowCount(0)
        self._preview.setColumnCount(0)
        self._row_count.clear()
        self._time_selection.set_columns([])
        self._warning.clear()
        self._status.setText("Open a saved analysis result to browse its tables.")
        self._preview_note.setText("Values are read from the saved result.")
        self._exported = None
        self._open.setEnabled(False)
        self._sync()

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        self._job = Path(job_dir)
        self._status.setText("Loading saved tables…")

        def inventory(cancel, _progress):
            from capture_analysis.feature_table_export import list_feature_tables

            if cancel():
                raise InterruptedError("Table loading cancelled.")
            return list_feature_tables(job_dir)

        worker = self._task(inventory, self._show_inventory)
        worker.start()

    def _show_inventory(self, inventory: dict) -> None:
        self._tables.blockSignals(True)
        for table in inventory["tables"]:
            label = f"{table.get('sourceId') or 'Session'} · {table.get('streamId') or 'Features'}"
            siblings = [row for row in inventory["tables"]
                        if (row.get("sourceId"), row.get("streamId")) ==
                        (table.get("sourceId"), table.get("streamId"))]
            if len(siblings) > 1:
                label += f" · {table['relativePath']}"
            self._tables.addItem(label, table)
            self._tables.setItemData(
                self._tables.count() - 1, table["relativePath"], Qt.ItemDataRole.ToolTipRole
            )
        self._tables.blockSignals(False)
        self._warning.setText(
            "This result contains warnings. Read Result details before using its values."
            if inventory["jobStatus"] == "completed_with_warnings" else ""
        )
        if not inventory["tables"]:
            self._status.setText(
                "This job has no feature tables. Run Features + plots or Features only."
            )
            return
        self._select_table()

    def _select_table(self, *_args) -> None:
        table = self._tables.currentData()
        if not isinstance(table, dict) or self._job is None:
            return
        self._generation += 1
        for worker in self._tasks:
            if worker is not self._export_task:
                worker.requestInterruption()
        self._preview_ready = False
        self._columns.clear()
        self._preview.clear()
        self._preview.setRowCount(0)
        self._preview.setColumnCount(0)
        self._time_selection.set_columns(table["columns"])
        for column in table["columns"]:
            item = QTreeWidgetItem([
                column["name"], column["units"],
                "Calibrated" if column.get("calibrated") else "Not calibrated",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, column["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            self._columns.addTopLevelItem(item)
        if self._columns.topLevelItemCount():
            self._columns.setCurrentItem(self._columns.topLevelItem(0))
        self._row_count.setText(
            f"{table['rows']:,} saved rows" if table.get("rows") is not None else ""
        )
        name = re.sub(r"[^\w.-]+", "-", str(table.get("streamId") or "table")).strip(".-")
        self._folder_name.setText(f"{name or 'table'}-export")
        self._status.setText("Reading saved values…")
        job, relative = self._job, table["relativePath"]

        def preview(cancel, _progress):
            from capture_analysis.feature_table_export import preview_feature_table

            return preview_feature_table(job, relative, cancel=cancel)

        worker = self._task(preview, self._show_preview)
        worker.start()
        self._sync()

    def _show_preview(self, result: dict) -> None:
        names, units, rows = result["columns"], result["units"], result["rows"]
        self._preview.setColumnCount(len(names))
        self._preview.setRowCount(len(rows))
        self._preview.setHorizontalHeaderLabels([
            f"{name}\n{unit}" if unit else name for name, unit in zip(names, units, strict=True)
        ])
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                text = "null" if value is None else str(value)
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self._preview.setItem(row_index, column_index, item)
        self._preview.resizeColumnsToContents()
        self._preview_note.setText(
            f"First {len(rows)} of {result['totalRows']:,} saved rows · original values"
        )
        self._preview_ready = True
        self._status.setText(
            "Choose columns in export order, then a new folder outside the recording."
        )
        self._sync()

    def selected_columns(self) -> tuple[str, ...]:
        return tuple(
            self._columns.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self._columns.topLevelItemCount())
            if self._columns.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        )

    def _set_checks(self, state) -> None:
        for i in range(self._columns.topLevelItemCount()):
            self._columns.topLevelItem(i).setCheckState(0, state)

    def _move_column(self, delta: int) -> None:
        item = self._columns.currentItem()
        if item is None:
            return
        index = self._columns.indexOfTopLevelItem(item)
        target = index + delta
        if 0 <= target < self._columns.topLevelItemCount():
            item = self._columns.takeTopLevelItem(index)
            self._columns.insertTopLevelItem(target, item)
            self._columns.setCurrentItem(item)

    def _choose_parent(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Save exported data in", self._parent_path.text()
        )
        if folder:
            self._parent_path.setText(folder)

    def _sync(self, *_args) -> None:
        self._export.setEnabled(
            self._preview_ready and bool(self.selected_columns())
            and bool(self._parent_path.text().strip() and self._folder_name.text().strip())
            and self._time_selection.selection is not None
            and not self.busy
        )
        for widget in (
            self._tables, self._columns, self._all, self._none, self._up, self._down,
            self._parent_path, self._folder_name, self._browse, self._format,
            self._time_selection,
        ):
            widget.setEnabled(not self.busy)

    def _start_export(self) -> None:
        if not self._export.isEnabled() or self._job is None:
            return
        name = self._folder_name.text().strip()
        if name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
            self._status.setText("Enter a single new folder name.")
            return
        destination = Path(self._parent_path.text()).expanduser() / name
        job = self._job
        relative = self._tables.currentData()["relativePath"]
        columns = self.selected_columns()
        output_format = str(self._format.currentData())
        time_selection = self._time_selection.selection
        if time_selection is None:
            return

        def export(cancel, progress):
            from capture_analysis.feature_table_export import export_feature_table

            return export_feature_table(
                job, relative, destination, columns=columns, output_format=output_format,
                cancel=cancel, progress=progress, **time_selection,
            )

        def succeeded(result):
            self._exported = destination
            self._open.setEnabled(True)
            self._status.setText(
                f"Exported {result['selection']['rows']:,} rows and {len(columns)} columns "
                f"to {destination}. Units and source warnings are included."
            )

        worker = self._task(export, succeeded)
        worker.progress.connect(self._on_progress)
        self._export_task = worker
        self._progress.setRange(0, 0)
        self._progress.show()
        self._cancel.show()
        self._status.setText("Checking the saved data and preparing export…")
        self._open.setEnabled(False)
        self.busy_changed.emit(True)
        self._sync()
        worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(done)

    def _cancel_export(self) -> None:
        if self._export_task is not None:
            self._export_task.requestInterruption()
            self._status.setText("Cancelling export…")

    def _open_export(self) -> None:
        if self._exported is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._exported)))

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        self._generation += 1
        for worker in list(self._tasks):
            worker.requestInterruption()
        for worker in list(self._tasks):
            worker.wait()
