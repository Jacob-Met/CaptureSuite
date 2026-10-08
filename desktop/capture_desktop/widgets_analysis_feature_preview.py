# SPDX-License-Identifier: GPL-3.0-only
"""Read-only, asynchronous inspection of retained feature tables."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from threading import Event

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_feature_preview import (
    MAX_COLUMNS,
    MAX_ROWS,
    FeatureCatalog,
    FeatureColumn,
    FeaturePreview,
    format_feature_value,
    load_feature_catalog,
    load_feature_preview,
)

_ROOT_INDEX = QModelIndex()


def _label(text: str = "", parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _viewer(name: str, accessible: str, parent: QWidget) -> QPlainTextEdit:
    viewer = QPlainTextEdit(parent)
    viewer.setObjectName(name)
    viewer.setAccessibleName(accessible)
    viewer.setReadOnly(True)
    viewer.setFont(theme.mono(9))
    return viewer


def _tooltip(text: str) -> str:
    # Qt tooltips may parse rich text; retained strings must stay literal.
    return "<pre>" + escape(text) + "</pre>"


def _column_text(column: FeatureColumn) -> str:
    return json.dumps(
        {
            "name": column.name,
            "arrow_type": column.arrow_type,
            "units": column.units,
            "calibrated": column.calibrated,
            "description": column.description,
        },
        ensure_ascii=False,
        indent=2,
    )


class _RowsModel(QAbstractTableModel):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._preview: FeaturePreview | None = None

    def set_preview(self, preview: FeaturePreview | None) -> None:
        self.beginResetModel()
        self._preview = preview
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() or self._preview is None else len(self._preview.rows)

    def columnCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() or self._preview is None else len(self._preview.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        preview = self._preview
        if (
            not index.isValid()
            or preview is None
            or not 0 <= index.row() < len(preview.rows)
            or not 0 <= index.column() < len(preview.columns)
        ):
            return None
        value = preview.rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            # Return text, never a QVariant numeric conversion of int64/uint64.
            return format_feature_value(value)
        if role == Qt.ItemDataRole.ToolTipRole:
            return _tooltip(format_feature_value(value))
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        preview = self._preview
        if preview is None:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(preview.columns):
            column = preview.columns[section]
            if role == Qt.ItemDataRole.DisplayRole:
                return column.name
            if role == Qt.ItemDataRole.ToolTipRole:
                return _tooltip(_column_text(column))
        elif orientation == Qt.Orientation.Vertical and 0 <= section < len(preview.rows):
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class _ColumnsModel(QAbstractTableModel):
    _HEADERS = ("Name", "Arrow type", "Units", "Calibrated", "Description")

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._columns: tuple[FeatureColumn, ...] = ()

    def set_columns(self, columns: tuple[FeatureColumn, ...]) -> None:
        self.beginResetModel()
        self._columns = columns
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def columnCount(self, parent: QModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._columns):
            return None
        column = self._columns[index.row()]
        values = (
            column.name,
            column.arrow_type,
            column.units,
            "true" if column.calibrated else "false",
            column.description,
        )
        if not 0 <= index.column() < len(values):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return _tooltip(values[index.column()])
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._HEADERS):
                return self._HEADERS[section]
            if orientation == Qt.Orientation.Vertical and 0 <= section < len(self._columns):
                return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


def _table(name: str, accessible: str, parent: QWidget) -> QTableView:
    table = QTableView(parent)
    table.setObjectName(name)
    table.setAccessibleName(accessible)
    table.setFont(theme.mono(9))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setSortingEnabled(False)
    table.setWordWrap(False)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setDefaultSectionSize(170)
    table.verticalHeader().setDefaultSectionSize(26)
    return table


class _FeaturePreviewDialog(QDialog):
    def __init__(self, parent: QWidget, *, job_id: str, relative_path: str) -> None:
        super().__init__(parent)
        self._job_id = job_id
        self._relative_path = relative_path
        self.setObjectName("FeaturePreviewDialog")
        self.setWindowTitle("Retained feature table")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(False)
        self.resize(940, 650)
        self.setFont(theme.ui())
        self._preview: FeaturePreview | None = None

        layout = QVBoxLayout(self)
        self._identity = _label(parent=self)
        self._identity.setObjectName("FeaturePreviewIdentity")
        self._identity.setAccessibleName("Retained feature table identity")
        self._identity.setText(f"Table: {relative_path}\nJob: {job_id}")
        layout.addWidget(self._identity)
        self._summary = _label(parent=self)
        self._summary.setObjectName("FeaturePreviewSummary")
        layout.addWidget(self._summary)
        self._status = _label("Reading retained feature table…", self)
        self._status.setObjectName("FeaturePreviewStatus")
        layout.addWidget(self._status)
        tabs = QTabWidget(self)
        layout.addWidget(tabs, 1)

        rows_page = QWidget(tabs)
        rows_layout = QVBoxLayout(rows_page)
        self._rows_model = _RowsModel(self)
        self._rows_table = _table("FeaturePreviewTable", "Retained feature rows", rows_page)
        self._rows_table.setModel(self._rows_model)
        rows_layout.addWidget(self._rows_table, 1)
        rows_layout.addWidget(_label("Selected cell — complete retained value", rows_page))
        self._cell_value = _viewer(
            "FeaturePreviewCellValue", "Complete retained feature cell value", rows_page
        )
        self._cell_value.setMaximumHeight(100)
        rows_layout.addWidget(self._cell_value)
        tabs.addTab(rows_page, "Rows")
        self._rows_table.selectionModel().currentChanged.connect(self._cell_changed)

        columns_page = QWidget(tabs)
        columns_layout = QVBoxLayout(columns_page)
        self._columns_model = _ColumnsModel(self)
        self._columns_table = _table(
            "FeaturePreviewColumns", "Feature column metadata", columns_page
        )
        self._columns_table.setModel(self._columns_model)
        columns_layout.addWidget(self._columns_table, 1)
        self._column_details = _viewer(
            "FeaturePreviewColumnDetails", "Complete feature column metadata", columns_page
        )
        self._column_details.setMaximumHeight(180)
        columns_layout.addWidget(self._column_details)
        tabs.addTab(columns_page, "Columns")
        self._columns_table.selectionModel().currentChanged.connect(self._column_changed)

        self._provenance = _viewer("FeaturePreviewProvenance", "Retained feature provenance", tabs)
        tabs.addTab(self._provenance, "Provenance")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def clear_preview(self) -> None:
        self._preview = None
        self._rows_model.set_preview(None)
        self._columns_model.set_columns(())
        self._cell_value.clear()
        self._column_details.clear()
        self._provenance.clear()
        self._identity.clear()
        self._summary.clear()
        self._status.clear()

    def show_preview(self, preview: FeaturePreview) -> None:
        self.clear_preview()
        self._preview = preview
        self._identity.setText(f"Table: {preview.relative_path}\nJob: {preview.job_id}")
        self._rows_model.set_preview(preview)
        self._columns_model.set_columns(preview.columns)
        count = len(preview.rows)
        prefix = (
            "Empty retained table (0 rows)."
            if preview.total_rows == 0
            else f"Showing the first {count:,} of {preview.total_rows:,} rows."
        )
        self._summary.setText(
            f"{prefix} {len(preview.columns):,} columns. "
            f"Preview limit: {MAX_ROWS:,} rows and {MAX_COLUMNS:,} columns."
        )
        self._status.setText(
            "Read-only retained values. NULL is null; NaN is numeric; strings are JSON-quoted."
        )
        self._provenance.setPlainText(
            json.dumps(
                {
                    "job_id": preview.job_id,
                    "session_id": preview.session_id,
                    "relative_path": preview.relative_path,
                    "table_sha256": preview.table_sha256,
                    "manifest_sha256": preview.manifest_sha256,
                    "total_rows": preview.total_rows,
                    "shown_rows": count,
                    "preview_row_limit": MAX_ROWS,
                    "preview_column_limit": MAX_COLUMNS,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if count and preview.columns:
            self._rows_table.setCurrentIndex(self._rows_model.index(0, 0))
        if preview.columns:
            self._columns_table.setCurrentIndex(self._columns_model.index(0, 0))

    def show_error(self, message: str) -> None:
        self.clear_preview()
        self._identity.setText(f"Table: {self._relative_path}\nJob: {self._job_id}")
        self._status.setText("Feature preview unavailable: " + message)

    @Slot(QModelIndex, QModelIndex)
    def _cell_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        value = self._rows_model.data(current)
        self._cell_value.setPlainText("" if value is None else value)

    @Slot(QModelIndex, QModelIndex)
    def _column_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        preview = self._preview
        if preview is None or not current.isValid():
            self._column_details.clear()
        else:
            self._column_details.setPlainText(_column_text(preview.columns[current.row()]))


@dataclass(frozen=True)
class _ReadRequest:
    number: int
    generation: int
    kind: str
    job_dir: Path | None = None
    catalog: FeatureCatalog | None = None
    relative_path: str = ""
    cancel: Event = field(default_factory=Event, compare=False)


class _ReadSignals(QObject):
    finished = Signal(object, object, str)


class _ReadTask(QRunnable):
    """No QWidget ownership: active reads can finish after their caller is gone."""

    def __init__(self, request: _ReadRequest) -> None:
        super().__init__()
        self.request = request
        self.signals = _ReadSignals()

    @Slot()
    def run(self) -> None:
        result = None
        error = ""
        try:
            if not self.request.cancel.is_set():
                if self.request.kind == "catalog":
                    result = load_feature_catalog(
                        self.request.job_dir, cancel_event=self.request.cancel
                    )
                else:
                    result = load_feature_preview(
                        self.request.catalog,
                        self.request.relative_path,
                        cancel_event=self.request.cancel,
                    )
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        self.signals.finished.emit(self.request, result, error)


class _ReadLifetime:
    """Cancellation callback has no reference to a widget or its Qt children."""

    def __init__(self) -> None:
        self.active: Event | None = None

    def cancel(self, *_args) -> None:
        if self.active is not None:
            self.active.set()


class FeatureTableBar(QWidget):
    """Open a bounded feature preview for the currently loaded Analysis job."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeatureTableBar")
        self._generation = 0
        self._serial = 0
        self._catalog: FeatureCatalog | None = None
        self._active: _ReadTask | None = None
        self._pending: _ReadRequest | None = None
        self._dialog: _FeaturePreviewDialog | None = None
        self._preview_request: int | None = None
        self._lifetime = _ReadLifetime()
        self.destroyed.connect(self._lifetime.cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = _label("Retained feature tables", self)
        layout.addWidget(title)
        self._choice = QComboBox(self)
        self._choice.setObjectName("FeatureTableChoice")
        self._choice.setAccessibleName("Recorded feature table")
        self._choice.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._choice.setMinimumContentsLength(20)
        self._choice.currentIndexChanged.connect(self._selection_changed)
        layout.addWidget(self._choice)
        self._button = QPushButton("Preview retained feature table…", self)
        self._button.setObjectName("PreviewFeatureTable")
        self._button.setAccessibleName("Preview retained feature table")
        self._button.clicked.connect(self._open_preview)
        layout.addWidget(self._button)
        self._status = _label(parent=self)
        self._status.setObjectName("FeatureTableStatus")
        layout.addWidget(self._status)
        self.clear()

    def clear(self) -> None:
        self._generation += 1
        self._catalog = None
        self._pending = None
        self._lifetime.cancel()
        self._discard_dialog()
        self._choice.blockSignals(True)
        self._choice.clear()
        self._choice.blockSignals(False)
        self._choice.setEnabled(False)
        self._button.setEnabled(False)
        self._status.setText("Load an Analysis job to inspect retained feature tables.")

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        self._status.setText("Reading the retained feature-table catalog…")
        self._queue_read("catalog", job_dir=Path(job_dir))

    def _queue_read(self, kind: str, **kwargs) -> _ReadRequest:
        self._serial += 1
        request = _ReadRequest(self._serial, self._generation, kind, **kwargs)
        # Only the latest waiting request is retained while a read winds down.
        self._pending = request
        self._start_pending()
        return request

    def _start_pending(self) -> None:
        if self._active is not None or self._pending is None:
            return
        request, self._pending = self._pending, None
        worker = _ReadTask(request)
        self._active = worker
        self._lifetime.active = request.cancel
        worker.signals.finished.connect(self._read_finished)
        QThreadPool.globalInstance().start(worker)

    @Slot(object, object, str)
    def _read_finished(self, request: _ReadRequest, result, error: str) -> None:
        if self._active is None or self._active.request.number != request.number:
            return
        self._active = None
        self._lifetime.active = None
        if request.generation == self._generation and not request.cancel.is_set():
            if request.kind == "catalog":
                if error:
                    self._status.setText("Feature tables unavailable: " + error)
                elif result is not None:
                    self._catalog = result
                    self._choice.addItems(result.tables)
                    has_tables = bool(result.tables)
                    self._choice.setEnabled(has_tables)
                    self._button.setEnabled(has_tables)
                    self._status.setText(
                        f"{len(result.tables):,} retained feature table(s). Read-only preview."
                        if has_tables
                        else "This job has no retained feature tables."
                    )
            elif self._dialog is not None and self._preview_request == request.number:
                if error:
                    self._dialog.show_error(error)
                elif result is not None:
                    self._dialog.show_preview(result)
        self._start_pending()

    def _cancel_preview_reads(self) -> None:
        self._preview_request = None
        if self._active is not None and self._active.request.kind == "preview":
            self._active.request.cancel.set()
        if self._pending is not None and self._pending.kind == "preview":
            self._pending.cancel.set()
            self._pending = None

    def _discard_dialog(self) -> None:
        self._cancel_preview_reads()
        if self._dialog is not None:
            self._dialog.clear_preview()
            self._dialog.close()
            self._dialog = None

    @Slot(int)
    def _selection_changed(self, index: int) -> None:
        self._discard_dialog()
        self._button.setEnabled(
            self._catalog is not None
            and index >= 0
            and self._choice.currentText() in self._catalog.tables
        )

    @Slot()
    def _open_preview(self) -> None:
        catalog = self._catalog
        relative_path = self._choice.currentText()
        if (
            catalog is None
            or self._choice.currentIndex() < 0
            or relative_path not in catalog.tables
        ):
            return
        if self._dialog is not None:
            self._dialog.show()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        dialog = _FeaturePreviewDialog(
            self, job_id=catalog.source.job_id, relative_path=relative_path
        )
        self._dialog = dialog
        dialog.finished.connect(self._dialog_finished)
        dialog.show()
        request = self._queue_read("preview", catalog=catalog, relative_path=relative_path)
        self._preview_request = request.number

    @Slot(int)
    def _dialog_finished(self, _result: int) -> None:
        dialog = self.sender()
        if dialog is self._dialog:
            dialog.clear_preview()
            self._dialog = None
            self._cancel_preview_reads()
