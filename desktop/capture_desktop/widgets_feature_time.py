# SPDX-License-Identifier: GPL-3.0-only
"""Choose an exact recorded time interval for retained feature row export."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from .widgets_analysis_scope import parse_seconds, seconds_text


class FeatureTimeSelection(QWidget):
    """The backend selects saved rows; this control never recomputes a window."""

    selection_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analysisExportTimeSelection")
        self._selection: dict | None = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(QLabel("Rows"))
        self._mode = QComboBox()
        self._mode.setAccessibleName("Feature export row selection")
        self._mode.addItem("All saved rows", "all")
        self._mode.addItem("Session time interval", "time")
        header.addWidget(self._mode)
        header.addStretch()
        layout.addLayout(header)
        self._range = QWidget()
        interval = QHBoxLayout(self._range)
        interval.setContentsMargins(0, 0, 0, 0)
        interval.addWidget(QLabel("Timestamp"))
        self._column = QComboBox()
        self._column.setAccessibleName("Retained timestamp column")
        self._column.setMinimumContentsLength(12)
        self._column.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        interval.addWidget(self._column, 1)
        self._start = QLineEdit()
        self._end = QLineEdit()
        for title, field, name in (
            ("Start included (s)", self._start, "Export interval start in session seconds"),
            ("End excluded (s)", self._end, "Export interval end in session seconds"),
        ):
            interval.addWidget(QLabel(title))
            field.setAccessibleName(name)
            field.setPlaceholderText("Session seconds")
            field.setMaxLength(40)
            field.setToolTip("Exact session seconds, up to nine decimal places.")
            interval.addWidget(field, 1)
        layout.addWidget(self._range)
        self._message = QLabel()
        self._message.setWordWrap(True)
        layout.addWidget(self._message)
        self._mode.currentIndexChanged.connect(self._update)
        self._column.currentIndexChanged.connect(self._update)
        self._start.textChanged.connect(self._update)
        self._end.textChanged.connect(self._update)
        self.set_columns([])

    @property
    def selection(self) -> dict | None:
        return None if self._selection is None else dict(self._selection)

    def set_columns(self, columns: list[dict]) -> None:
        """Reset scope when changing tables so old trial bounds cannot carry over."""
        blockers = [QSignalBlocker(w) for w in
                    (self._mode, self._column, self._start, self._end)]
        self._mode.setCurrentIndex(0)
        self._column.clear()
        for column in columns:
            if column.get("units") == "ns":
                name = column["name"]
                self._column.addItem(name, name)
        # Prefer the row's ordinary coordinate over an end-of-window column.
        for name in ("t_mid_ns", "t_start_ns", "t_session_ns", "t_ns"):
            index = self._column.findData(name)
            if index >= 0:
                self._column.setCurrentIndex(index)
                break
        self._start.clear()
        self._end.clear()
        del blockers
        self._update()

    def _update(self, *_args) -> None:
        scoped = self._mode.currentData() == "time"
        self._range.setVisible(scoped)
        try:
            if not scoped:
                self._selection = {}
                self._message.setText(
                    "All saved rows in original order. "
                    "Units and source warnings travel with the data."
                )
            else:
                column = self._column.currentData()
                if not column:
                    raise ValueError(
                        "This table has no retained nanosecond column for time selection."
                    )
                if not self._start.text().strip() or not self._end.text().strip():
                    raise ValueError("Enter both bounds in session seconds to select the trial.")
                start = parse_seconds(self._start.text())
                end = parse_seconds(self._end.text())
                if end <= start:
                    raise ValueError("The excluded end must be after the included start.")
                self._selection = {"time_column": column, "start_ns": start, "end_ns": end}
                self._message.setText(
                    f"Use {column} in session interval "
                    f"[{seconds_text(start)}, {seconds_text(end)}) s. "
                    "Saved feature windows are unchanged and can extend outside these bounds. "
                    "The preview shows the original saved table."
                )
        except ValueError as exc:
            self._selection = None
            self._message.setText(str(exc))
        self.selection_changed.emit()
