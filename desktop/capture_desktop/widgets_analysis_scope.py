# SPDX-License-Identifier: GPL-3.0-only
"""Sealed-session scope controls using the analysis backend's window semantics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

WINDOW_COMMANDS = frozenset({"features", "plots", "all", "pose"})


def seconds_text(nanoseconds: int) -> str:
    """Format the exact session-clock value without a float round trip."""
    whole, fraction = divmod(abs(nanoseconds), 1_000_000_000)
    return ("-" if nanoseconds < 0 else "") + f"{whole}.{fraction:09d}"


def parse_seconds(text: str) -> int:
    try:
        seconds = Decimal(text.strip())
        if not seconds.is_finite():
            raise ValueError
        if seconds.is_zero():
            return 0
        if not -9 <= seconds.adjusted() <= 9:
            raise ValueError
        # Integer scaling prevents the Decimal context from rounding away a
        # sub-nanosecond suffix. Bounding the exponent also bounds this work.
        numerator, denominator = seconds.as_integer_ratio()
        value, remainder = divmod(numerator * 1_000_000_000, denominator)
        if remainder or not -(2**63) <= value < 2**63:
            raise ValueError
        return value
    except (InvalidOperation, ValueError):
        raise ValueError("Enter session seconds with at most nine decimal places.") from None


@dataclass(frozen=True)
class ScopeSelection:
    mode: str = "full"
    section_name: str | None = None
    start_ns: int | None = None
    end_ns: int | None = None

    def job_fields(self) -> dict:
        if self.mode == "full":
            return {}
        if self.mode not in {"range", "section"}:
            raise ValueError("Select Full session, Checkpoint section, or Time range.")
        if self.start_ns is None or self.end_ns is None or self.start_ns >= self.end_ns:
            raise ValueError("The end of the scope must be after its start.")
        if self.mode == "section":
            if not self.section_name:
                raise ValueError("Choose a checkpoint section.")
            return {"checkpoint_section": self.section_name}
        return {"start_session_ns": self.start_ns, "end_session_ns": self.end_ns}

    def describe(self) -> str:
        if self.mode == "full":
            return "Full session"
        bounds = f"{seconds_text(self.start_ns)}–{seconds_text(self.end_ns)} s"
        return f"Section {self.section_name}: {bounds}" if self.mode == "section" else bounds


class AnalysisScopePicker(QWidget):
    """A selection is None while the operator is editing invalid bounds."""

    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._summary = None
        self._cursor_ns = 0
        self._selection: ScopeSelection | None = ScopeSelection()
        self._unavailable_sections: list[str] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(3)
        row = QHBoxLayout()
        row.addWidget(QLabel("Analysis scope"))
        self._mode = QComboBox()
        self._mode.setAccessibleName("Analysis scope mode")
        for label, value in (
            ("Full session", "full"),
            ("Checkpoint section", "section"),
            ("Time range", "range"),
        ):
            self._mode.addItem(label, value)
        row.addWidget(self._mode)
        self._sections = QComboBox()
        self._sections.setAccessibleName("Checkpoint section")
        row.addWidget(self._sections, 1)
        self._range = QWidget()
        range_row = QHBoxLayout(self._range)
        range_row.setContentsMargins(0, 0, 0, 0)
        self._start = QLineEdit("0.000000000")
        self._end = QLineEdit("1.000000000")
        for label, widget in (
            ("Start (session seconds)", self._start),
            ("End (session seconds)", self._end),
        ):
            range_row.addWidget(QLabel(label.split()[0] + " (s)"))
            widget.setAccessibleName(label)
            widget.setToolTip(label + "; up to nanosecond precision")
            widget.setMaxLength(40)
            range_row.addWidget(widget)
        self._mark_start = QPushButton("Start at cursor")
        self._mark_end = QPushButton("End at cursor")
        self._mark_start.clicked.connect(lambda: self._start.setText(seconds_text(self._cursor_ns)))
        self._mark_end.clicked.connect(lambda: self._end.setText(seconds_text(self._cursor_ns)))
        range_row.addWidget(self._mark_start)
        range_row.addWidget(self._mark_end)
        row.addWidget(self._range, 2)
        row.addStretch(1)
        outer.addLayout(row)
        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setFont(theme.ui(8))
        outer.addWidget(self._message)
        self._section_notice = QLabel()
        self._section_notice.setWordWrap(True)
        self._section_notice.setFont(theme.ui(8))
        self._section_notice.setStyleSheet(f"color: {theme.ORANGE.name()};")
        outer.addWidget(self._section_notice)
        self._mode.currentIndexChanged.connect(self._update_selection)
        self._sections.currentIndexChanged.connect(self._update_selection)
        self._start.textChanged.connect(self._update_selection)
        self._end.textChanged.connect(self._update_selection)
        self._update_selection()

    @property
    def selection(self) -> ScopeSelection | None:
        return self._selection

    def set_cursor(self, nanoseconds: int) -> None:
        self._cursor_ns = nanoseconds

    def set_summary(self, summary, selection: ScopeSelection | None) -> None:
        from capture_analysis.windows import (
            _checkpoint_id,
            _checkpoint_time_ns,
            checkpoint_section_window,
        )

        self._summary = summary
        selected = selection or ScopeSelection("range")
        blockers = [QSignalBlocker(w) for w in (self._mode, self._sections, self._start, self._end)]
        self._sections.clear()
        self._unavailable_sections = []
        seen = set()
        for cp in summary.checkpoints:
            key = _checkpoint_id(cp)
            if not key or key in seen:
                continue
            seen.add(key)
            label = str(cp.get("name") or key)
            if label != key:
                label += f" ({key})"
            try:
                # The existing backend accepts both IDs and display names. Keep
                # its matching order, but never offer a different checkpoint's
                # interval under the selected checkpoint's stable ID.
                first_match = next(
                    row
                    for row in sorted(summary.checkpoints, key=_checkpoint_time_ns)
                    if _checkpoint_id(row) == key or str(row.get("name") or "") == key
                )
                if first_match is not cp:
                    self._unavailable_sections.append(
                        f"{label} is unavailable: another checkpoint uses '{key}' "
                        "as its name or ID. Use Time range for this section."
                    )
                    continue
                window = checkpoint_section_window(summary, key)
                candidate = ScopeSelection(
                    "section", key, window.start_session_ns, window.end_session_ns
                )
                candidate.job_fields()
            except (TypeError, ValueError):
                self._unavailable_sections.append(
                    f"{label} is unavailable: its time bounds cannot be resolved. Use Time range."
                )
                continue
            self._sections.addItem(label, candidate)
        self._section_notice.setText("\n".join(self._unavailable_sections))
        self._mode.setCurrentIndex(self._mode.findData(selected.mode))
        if selected.mode == "section":
            index = next(
                (
                    i
                    for i in range(self._sections.count())
                    if self._sections.itemData(i).section_name == selected.section_name
                ),
                -1,
            )
            self._sections.setCurrentIndex(index)
        start = selected.start_ns if selected.start_ns is not None else 0
        end = selected.end_ns if selected.end_ns is not None else max(summary.duration_ns, 1)
        self._start.setText(seconds_text(start))
        self._end.setText(seconds_text(end))
        if selection is None:
            # A previously invalid selection must never become an executable full job
            # just because the session chrome was refreshed or another tab was visited.
            self._start.clear()
            self._end.clear()
        del blockers
        self._update_selection()

    def _update_selection(self) -> None:
        mode = self._mode.currentData()
        self._sections.setVisible(mode == "section")
        self._range.setVisible(mode == "range")
        self._section_notice.setVisible(mode == "section" and bool(self._unavailable_sections))
        try:
            if mode == "full":
                selection = ScopeSelection()
            elif mode == "section":
                selection = self._sections.currentData()
                if selection is None:
                    raise ValueError(
                        "No usable checkpoint section. Choose Full session or Time range."
                    )
            else:
                selection = ScopeSelection(
                    "range",
                    start_ns=parse_seconds(self._start.text()),
                    end_ns=parse_seconds(self._end.text()),
                )
            selection.job_fields()
            self._selection = selection
            self._message.setText(selection.describe() + ". Raw streams stay unchanged.")
            self._message.setStyleSheet(f"color: {theme.TEXT_DIM.name()};")
        except ValueError as exc:
            self._selection = None
            self._message.setText(str(exc))
            self._message.setStyleSheet(f"color: {theme.RED.name()};")
        self.selection_changed.emit(self._selection)
