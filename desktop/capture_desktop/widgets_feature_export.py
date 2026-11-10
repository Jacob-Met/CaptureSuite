# SPDX-License-Identifier: GPL-3.0-only
"""Choose recorded measurement columns and export through the maintained exporter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_job_comparison import JobParameterError, read_job_manifest


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class _TableExportWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, job, table, destination, columns, output_format, parent):
        super().__init__(parent)
        self._arguments = (job, table, destination)
        self._columns = tuple(columns)
        self._format = output_format

    def run(self) -> None:
        try:
            from capture_analysis.feature_table_export import export_feature_table

            result = export_feature_table(
                *self._arguments,
                columns=self._columns,
                output_format=self._format,
            )
        except Exception as exc:  # Preserve the real failure and keep a retry available.
            self.failed.emit("\n".join([str(exc), *getattr(exc, "__notes__", ())]))
        else:
            self.succeeded.emit(result)


class FeatureExportDialog(QDialog):
    """A selected saved table, explicit column order, and a new external destination."""

    def __init__(self, job_dir: Path, listing: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Export measurements")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(760, 640)
        self._job = job_dir
        self._listing = listing
        self._worker: _TableExportWorker | None = None
        self._invalidated = False
        self._closing = False
        self._destination: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        try:
            session = str(read_job_manifest(job_dir).get("sessionId") or job_dir.parents[2].name)
        except (JobParameterError, OSError):
            session = job_dir.parents[2].name
        self._context = _label(f"Session {session}\nSaved result {listing['jobId']}")
        self._context.setToolTip(str(job_dir))
        self._context.setAccessibleName("Session and saved result being exported")
        layout.addWidget(self._context)
        self._summary = _label()
        self._summary.setFont(theme.ui(10, bold=True))
        layout.addWidget(self._summary)
        self._warning = _label(
            "This analysis completed with warnings. Review the saved QC report before using "
            "its measurements. The export carries the original warnings and units."
            if listing["jobStatus"] == "completed_with_warnings"
            else "Export all recorded rows in their original order, with units and source details."
        )
        self._warning.setObjectName("Dim")
        layout.addWidget(self._warning)

        form = QFormLayout()
        self._table = QComboBox()
        self._table.setAccessibleName("Saved measurement table")
        for table in listing["tables"]:
            context = " / ".join(str(table[key]) for key in ("sourceId", "streamId") if table[key])
            name = context or table["relativePath"]
            self._table.addItem(name, table)
            self._table.setItemData(
                self._table.count() - 1, table["relativePath"], Qt.ItemDataRole.ToolTipRole
            )
        form.addRow("Table", self._table)
        layout.addLayout(form)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Find a column or unit…")
        self._search.setAccessibleName("Find measurement columns")
        self._search.setClearButtonEnabled(True)
        layout.addWidget(self._search)

        self._columns = QTreeWidget()
        self._columns.setHeaderLabels(["Column", "Unit", "Calibration recorded"])
        self._columns.setRootIsDecorated(False)
        self._columns.setUniformRowHeights(True)
        self._columns.setAccessibleName("Columns in export order")
        self._columns.setColumnWidth(0, 350)
        self._columns.setColumnWidth(1, 100)
        layout.addWidget(self._columns, 1)
        selection = QHBoxLayout()
        self._all = QPushButton("Select all")
        self._none = QPushButton("Clear selection")
        self._up = QPushButton("Move up")
        self._down = QPushButton("Move down")
        self._count = _label()
        for widget in (self._all, self._none, self._up, self._down):
            selection.addWidget(widget)
        selection.addWidget(self._count, 1)
        layout.addLayout(selection)

        destination_form = QFormLayout()
        self._format = QComboBox()
        for title, value in (("CSV + Parquet", "both"), ("CSV", "csv"), ("Parquet", "parquet")):
            self._format.addItem(title, value)
        destination_form.addRow("Format", self._format)
        location_row = QHBoxLayout()
        self._parent = QLineEdit()
        self._parent.setPlaceholderText("Choose an existing folder outside this session…")
        self._parent.setAccessibleName("Export parent folder")
        self._browse = QPushButton("Browse…")
        location_row.addWidget(self._parent, 1)
        location_row.addWidget(self._browse)
        destination_form.addRow("Save in", location_row)
        self._name = QLineEdit(f"{listing['jobId']}-measurements")
        self._name.setAccessibleName("New export folder name")
        destination_form.addRow("New folder", self._name)
        layout.addLayout(destination_form)
        self._status = _label()
        self._status.setAccessibleName("Measurement export status")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status)
        actions = QHBoxLayout()
        self._open_folder = QPushButton("Open exported folder")
        self._open_folder.setVisible(False)
        self._close = QPushButton("Close")
        self._export = QPushButton("Export measurements")
        self._export.setObjectName("Primary")
        actions.addWidget(self._open_folder)
        actions.addStretch(1)
        actions.addWidget(self._close)
        actions.addWidget(self._export)
        layout.addLayout(actions)

        self._table.currentIndexChanged.connect(self._table_changed)
        self._search.textChanged.connect(self._filter)
        self._columns.itemChanged.connect(self._sync)
        self._columns.currentItemChanged.connect(self._sync)
        self._all.clicked.connect(lambda: self._check_all(True))
        self._none.clicked.connect(lambda: self._check_all(False))
        self._up.clicked.connect(lambda: self._move(-1))
        self._down.clicked.connect(lambda: self._move(1))
        self._parent.textChanged.connect(self._sync)
        self._name.textChanged.connect(self._sync)
        self._browse.clicked.connect(self._choose_parent)
        self._export.clicked.connect(self._start)
        self._close.clicked.connect(self.reject)
        self._open_folder.clicked.connect(self._open_destination)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._settle)
        self._table_changed()

    def selected_columns(self) -> tuple[str, ...]:
        return tuple(
            self._columns.topLevelItem(i).text(0)
            for i in range(self._columns.topLevelItemCount())
            if self._columns.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        )

    def _table_changed(self, *_args) -> None:
        table = self._table.currentData()
        self._columns.blockSignals(True)
        self._columns.clear()
        if table:
            for column in table["columns"]:
                item = QTreeWidgetItem(
                    [
                        column["name"],
                        column["units"],
                        "Yes" if column.get("calibrated") else "No",
                    ]
                )
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                self._columns.addTopLevelItem(item)
            rows = table["rows"]
            self._summary.setText(
                f"{self._table.currentText()} · {rows:,} rows"
                if isinstance(rows, int)
                else self._table.currentText()
            )
            self._summary.setToolTip(
                f"Saved job: {self._listing['jobId']}\n{table['relativePath']}"
            )
        self._columns.blockSignals(False)
        self._filter()

    def _filter(self, *_args) -> None:
        query = self._search.text().casefold()
        for index in range(self._columns.topLevelItemCount()):
            item = self._columns.topLevelItem(index)
            item.setHidden(query not in f"{item.text(0)} {item.text(1)}".casefold())
        self._sync()

    def _check_all(self, checked: bool) -> None:
        self._columns.blockSignals(True)
        for index in range(self._columns.topLevelItemCount()):
            self._columns.topLevelItem(index).setCheckState(
                0,
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked,
            )
        self._columns.blockSignals(False)
        self._sync()

    def _move(self, delta: int) -> None:
        item = self._columns.currentItem()
        if item is None:
            return
        index = self._columns.indexOfTopLevelItem(item)
        target = index + delta
        if 0 <= target < self._columns.topLevelItemCount():
            self._columns.takeTopLevelItem(index)
            self._columns.insertTopLevelItem(target, item)
            self._columns.setCurrentItem(item)
        self._sync()

    def _sync(self, *_args) -> None:
        busy = self._worker is not None
        total = self._columns.topLevelItemCount()
        visible = sum(not self._columns.topLevelItem(i).isHidden() for i in range(total))
        selected = self.selected_columns()
        self._count.setText(f"{len(selected)} / {total} selected · {visible} shown")
        item = self._columns.currentItem()
        index = self._columns.indexOfTopLevelItem(item) if item else -1
        self._up.setEnabled(not busy and not self._invalidated and index > 0)
        self._down.setEnabled(not busy and not self._invalidated and 0 <= index < total - 1)
        name = self._name.text().strip()
        valid_name = bool(name and name not in {".", ".."} and "/" not in name and "\\" not in name)
        self._export.setEnabled(
            bool(selected and self._parent.text().strip() and valid_name)
            and not busy
            and not self._invalidated
        )

    def _choose_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choose export parent folder",
            self._parent.text() or str(Path.home()),
        )
        if path:
            self._parent.setText(path)

    def _start(self) -> None:
        if not self._export.isEnabled():
            return
        table = self._table.currentData()
        destination = Path(self._parent.text().strip()).expanduser() / self._name.text().strip()
        self._destination = destination
        worker = _TableExportWorker(
            self._job,
            table["relativePath"],
            destination,
            self.selected_columns(),
            self._format.currentData(),
            self,
        )
        self._worker = worker
        worker.succeeded.connect(self._succeeded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self._open_folder.setVisible(False)
        self._status.setText("Checking the saved table and writing the selected columns…")
        for widget in (
            self._table,
            self._columns,
            self._search,
            self._all,
            self._none,
            self._browse,
            self._parent,
            self._name,
            self._format,
            self._close,
        ):
            widget.setEnabled(False)
        self._sync()
        worker.start()

    def _succeeded(self, result: dict) -> None:
        selection = result["selection"]
        self._status.setText(
            f"Exported {selection['rows']:,} rows and {len(selection['columns'])} columns.\n"
            f"{self._destination}"
        )
        self._open_folder.setVisible(True)

    def _failed(self, message: str) -> None:
        self._status.setText(f"Export failed. {message}")
        self._open_folder.setVisible(False)

    def _finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        for widget in (
            self._table,
            self._columns,
            self._search,
            self._all,
            self._none,
            self._browse,
            self._parent,
            self._name,
            self._format,
            self._close,
        ):
            widget.setEnabled(not self._invalidated)
        self._sync()
        if self._invalidated or self._closing:
            super().reject()

    def _open_destination(self) -> None:
        if self._destination is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._destination.resolve())))

    def _settle(self) -> None:
        if self._worker is not None:
            self._worker.wait()

    def invalidate_source(self) -> None:
        self._invalidated = True
        self._sync()
        self.reject()

    def reject(self) -> None:
        if self._worker is not None:
            self._closing = True
            self._status.setText(
                "Export is still writing. It will finish before this window closes."
            )
        else:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)


class FeatureExportBar(QWidget):
    """Bind the existing table exporter to the result actually open in the inspector."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._job: Path | None = None
        self._listing: dict | None = None
        self._dialog: FeatureExportDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._button = QPushButton("Export measurements…")
        self._button.setAccessibleName("Export selected measurement columns")
        self._button.clicked.connect(self._open_dialog)
        self._status = _label()
        self._status.setObjectName("Dim")
        self._status.setFont(theme.ui(8))
        layout.addWidget(self._button)
        layout.addWidget(self._status)
        self.clear()

    def clear(self) -> None:
        if self._dialog is not None:
            self._dialog.invalidate_source()
        self._job = None
        self._listing = None
        self._button.setEnabled(False)
        self._status.setText("Open a saved feature result to select its measurements.")

    def load_job_dir(self, job: Path) -> None:
        self.clear()
        try:
            from capture_analysis.feature_table_export import list_feature_tables

            listing = list_feature_tables(job)
        except (ImportError, OSError, ValueError) as exc:
            self._status.setText(f"Measurements unavailable: {exc}")
            return
        self._job, self._listing = job, listing
        count = len(listing["tables"])
        self._button.setEnabled(count > 0)
        self._status.setText(
            f"{count} recorded table{'s' if count != 1 else ''} · recorded units retained"
            if count
            else "No measurement tables in this result. Run Features to create them."
        )

    def _open_dialog(self) -> None:
        if self._job is None:
            return
        if self._dialog is not None:
            self._dialog.raise_()
            return
        try:
            from capture_analysis.feature_table_export import list_feature_tables

            listing = list_feature_tables(self._job)
        except (ImportError, OSError, ValueError) as exc:
            self._status.setText(f"Measurements unavailable: {exc}")
            return
        if not listing["tables"]:
            return
        self._dialog = FeatureExportDialog(self._job, listing, self)
        self._dialog.finished.connect(self._dialog_finished)
        self._dialog.open()

    def _dialog_finished(self, _result: int) -> None:
        dialog, self._dialog = self._dialog, None
        if dialog is not None:
            dialog.deleteLater()
