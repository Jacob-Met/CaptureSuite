# SPDX-License-Identifier: GPL-3.0-only
"""Native, read-only navigation of loaded checkpoint, annotation and gap records."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .review_events import ReviewEvent, events_from_summary, filter_events


class _EventTableModel(QAbstractTableModel):
    HEADERS = ("Session time (ns)", "Event", "Source", "Stream", "Summary")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events: tuple[ReviewEvent, ...] = ()

    def set_events(self, events: tuple[ReviewEvent, ...]) -> None:
        self.beginResetModel()
        self.events = events
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: B008
        return 0 if parent.isValid() else len(self.events)

    def columnCount(self, parent=QModelIndex()):  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.events):
            return None
        event = self.events[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                str(event.time_ns) if event.time_ns is not None else "Unavailable",
                event.kind,
                event.source_id if event.source_id is not None else "No usable source ID",
                event.stream_id if event.stream_id is not None else "—",
                " ".join(event.label.splitlines()),
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return "Select this row to inspect its complete loaded record."
        return None


class ReviewEventBrowser(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ReviewEvents")
        self._events: tuple[ReviewEvent, ...] = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        filters = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.setObjectName("ReviewEventKind")
        self._kind.setAccessibleName("Event kind")
        self._kind.addItem("All event kinds", None)
        for kind in ("Checkpoint", "Annotation", "Gap"):
            self._kind.addItem(kind, kind)
        self._source = QComboBox()
        self._source.setObjectName("ReviewEventSource")
        self._source.setAccessibleName("Event source")
        self._source.setMinimumContentsLength(14)
        self._source.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._search = QLineEdit()
        self._search.setObjectName("ReviewEventSearch")
        self._search.setAccessibleName("Search event records")
        self._search.setPlaceholderText("Search names, notes, tags or recorded fields…")
        self._search.setClearButtonEnabled(True)
        self._reset = QPushButton("Clear filters")
        self._reset.setObjectName("ReviewEventClear")
        for text, control in (("&Kind", self._kind), ("&Source", self._source)):
            label = QLabel(text)
            label.setBuddy(control)
            filters.addWidget(label)
            filters.addWidget(control)
        filters.addWidget(self._search, 1)
        filters.addWidget(self._reset)
        root.addLayout(filters)

        self._count = QLabel()
        self._count.setObjectName("ReviewEventCount")
        self._count.setTextFormat(Qt.TextFormat.PlainText)
        self._count.setWordWrap(True)
        root.addWidget(self._count)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._table = QTableView()
        self._table.setObjectName("ReviewEventTable")
        self._table.setAccessibleName("Recorded events")
        self._model = _EventTableModel(self)
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setWordWrap(False)
        self._table.verticalHeader().hide()
        header = self._table.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate((190, 100, 190, 150)):
            self._table.setColumnWidth(column, width)
        header.setStretchLastSection(True)
        splitter.addWidget(self._table)

        self._details = QPlainTextEdit()
        self._details.setObjectName("ReviewEventDetails")
        self._details.setAccessibleName("Selected event details")
        self._details.setReadOnly(True)
        self._details.setFont(theme.mono(9))
        self._details.setPlaceholderText("Select an event to inspect its complete loaded details.")
        splitter.addWidget(self._details)
        splitter.setSizes([240, 180])
        root.addWidget(splitter, 1)

        note = QLabel(
            "Times are exact session nanoseconds; unavailable times appear last. "
            "Filters affect only this list. Loaded records do not establish "
            "complete capture coverage."
        )
        note.setObjectName("Faint")
        note.setWordWrap(True)
        note.setFont(theme.ui(8))
        root.addWidget(note)
        self._kind.currentIndexChanged.connect(self._apply_filters)
        self._source.currentIndexChanged.connect(self._apply_filters)
        self._search.textChanged.connect(self._apply_filters)
        self._reset.clicked.connect(self._reset_filters)
        self._table.selectionModel().currentRowChanged.connect(self._select_event)
        self.clear()

    def clear(self) -> None:
        self._set_events(())

    def set_summary(self, summary) -> None:
        self._set_events(events_from_summary(summary))

    def _set_events(self, events: tuple[ReviewEvent, ...]) -> None:
        self._events = events
        blockers = [QSignalBlocker(widget) for widget in (self._kind, self._source, self._search)]
        self._kind.setCurrentIndex(0)
        self._source.clear()
        self._source.addItem("All sources", None)
        if any(event.source_id is None for event in events):
            self._source.addItem("No usable source ID", "")
        for source in sorted({event.source_id for event in events if event.source_id is not None}):
            self._source.addItem(f"Source: {source}", source)
        self._search.clear()
        del blockers
        for widget in (self._kind, self._source, self._search, self._reset):
            widget.setEnabled(bool(events))
        self._apply_filters()

    def _reset_filters(self) -> None:
        blockers = [QSignalBlocker(widget) for widget in (self._kind, self._source, self._search)]
        self._kind.setCurrentIndex(0)
        self._source.setCurrentIndex(0)
        self._search.clear()
        del blockers
        self._apply_filters()

    def _apply_filters(self, *_args) -> None:
        events = filter_events(
            self._events, kind=self._kind.currentData(),
            source_id=self._source.currentData(), query=self._search.text(),
        )
        self._model.set_events(events)
        self._details.clear()
        counts = {kind: sum(event.kind == kind for event in self._events)
                  for kind in ("Gap", "Checkpoint", "Annotation")}
        self._count.setText(
            f"Showing {len(events)} of {len(self._events)} loaded events · "
            f"Loaded: {counts['Gap']} gaps, {counts['Checkpoint']} checkpoints, "
            f"{counts['Annotation']} annotations"
        )

    def _select_event(self, current, _previous) -> None:
        if current.isValid() and 0 <= current.row() < len(self._model.events):
            self._details.setPlainText(self._model.events[current.row()].details)
        else:
            self._details.clear()
