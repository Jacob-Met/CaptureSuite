# SPDX-License-Identifier: GPL-3.0-only
"""Native selection, preview and destination workflow for analysis figure bundles."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .analysis_figure_export import (
    FigureSource,
    export_figure_bundle,
    load_figure_source,
    read_figure,
)


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class _ExportWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, source, selected, destination, replace_existing, parent):
        super().__init__(parent)
        self._arguments = (source, selected, destination)
        self._replace = replace_existing

    def run(self) -> None:
        try:
            result = export_figure_bundle(
                *self._arguments,
                replace_existing=self._replace,
                cancel=self.isInterruptionRequested,
            )
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:  # GUI boundary: keep the dialog available for a retry.
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class FigureExportDialog(QDialog):
    """Select exact job artifacts, preview them and save a ZIP outside the source."""

    def __init__(self, source: FigureSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export analysis figures")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(800, 610)
        self._source = source
        self._worker: _ExportWorker | None = None
        self._closing = False
        self._invalidated = False
        self._preview_image = QImage()
        layout = QVBoxLayout(self)
        manifest = source.manifest
        self._summary = _label(
            f"Job: {source.job_id}\nSession: {manifest['sessionId']}\n"
            f"Gap policy: {manifest.get('gapPolicy', 'not recorded')} · "
            f"Parameters: {manifest['paramsDigest'][:12]} · "
            f"Status: {manifest['status']}"
        )
        layout.addWidget(self._summary)
        layout.addWidget(
            _label(
                "Choose original PNG figures. The ZIP includes the saved job manifest and "
                "parameters, including recorded session identifiers, paths and warnings."
            )
        )
        body = QHBoxLayout()
        self._figures = QListWidget()
        self._figures.setAccessibleName("Figures to include in the bundle")
        self._figures.setMinimumWidth(260)
        for figure in source.figures:
            item = QListWidgetItem(figure.relative_path)
            item.setData(Qt.ItemDataRole.UserRole, figure.relative_path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(f"{figure.byte_count:,} bytes · SHA-256 {figure.sha256}")
            self._figures.addItem(item)
        body.addWidget(self._figures, 1)
        self._preview = _label("Select a figure to preview.")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(260, 180)
        body.addWidget(self._preview, 1)
        layout.addLayout(body, 1)
        selections = QHBoxLayout()
        self._all = QPushButton("Select &all")
        self._none = QPushButton("Select &none")
        self._count = _label()
        selections.addWidget(self._all)
        selections.addWidget(self._none)
        selections.addWidget(self._count, 1)
        layout.addLayout(selections)
        destination_row = QHBoxLayout()
        self._destination = QLineEdit()
        self._destination.setReadOnly(True)
        self._destination.setPlaceholderText("Choose where to save the ZIP…")
        self._destination.setAccessibleName("Figure bundle destination")
        self._browse = QPushButton("&Choose ZIP…")
        destination_row.addWidget(self._destination, 1)
        destination_row.addWidget(self._browse)
        layout.addLayout(destination_row)
        self._status = _label()
        self._status.setAccessibleName("Export status")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self._cancel = QPushButton("&Close")
        self._export = QPushButton("&Export ZIP")
        self._export.setObjectName("Primary")
        self._export.setStyleSheet(
            "QPushButton#Primary:disabled { background: palette(button); "
            "color: palette(mid); border-color: palette(mid); }"
        )
        self._export.setDefault(True)
        actions.addWidget(self._cancel)
        actions.addWidget(self._export)
        layout.addLayout(actions)
        self._all.clicked.connect(lambda: self._set_checks(Qt.CheckState.Checked))
        self._none.clicked.connect(lambda: self._set_checks(Qt.CheckState.Unchecked))
        self._figures.itemChanged.connect(self._selection_changed)
        self._figures.currentItemChanged.connect(self._show_preview)
        self._browse.clicked.connect(self._choose_destination)
        self._export.clicked.connect(self._start_export)
        self._cancel.clicked.connect(self.reject)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown)
        self._selection_changed()
        if self._figures.count():
            self._figures.setCurrentRow(0)

    def selected_paths(self) -> tuple[str, ...]:
        return tuple(
            self._figures.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._figures.count())
            if self._figures.item(i).checkState() == Qt.CheckState.Checked
        )

    def _set_checks(self, state: Qt.CheckState) -> None:
        for index in range(self._figures.count()):
            self._figures.item(index).setCheckState(state)

    def _selection_changed(self) -> None:
        selected = self.selected_paths()
        self._count.setText(f"{len(selected)} of {self._figures.count()} figures selected")
        self._export.setEnabled(
            bool(selected and self._destination.text())
            and self._worker is None
            and not self._invalidated
        )

    def _show_preview(self, current, _previous=None) -> None:
        self._preview_image = QImage()
        self._preview.clear()
        if current is None:
            return
        relative = current.data(Qt.ItemDataRole.UserRole)
        try:
            data = read_figure(self._source, relative)
        except (OSError, ValueError) as exc:
            self._preview.setText(f"Preview unavailable: {exc}")
        else:
            self._preview_image = QImage.fromData(data, "PNG")
            self._scale_preview()

    def _scale_preview(self) -> None:
        if not self._preview_image.isNull():
            self._preview.setPixmap(
                QPixmap.fromImage(self._preview_image).scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_preview()

    def _choose_destination(self) -> None:
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Save figure bundle",
            f"{self._source.job_id}-figures.zip",
            "Figure bundle (*.zip)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not selected:
            return
        if not selected.lower().endswith(".zip"):
            selected += ".zip"
        self._destination.setText(selected)
        self._status.clear()
        self._selection_changed()

    def _start_export(self) -> None:
        if not self._export.isEnabled():
            return
        destination = Path(self._destination.text())
        replace = destination.exists()
        if (
            replace
            and QMessageBox.question(
                self,
                "Replace figure bundle?",
                f"Replace the existing file at {destination}?\n"
                "It will be replaced only after the new bundle is fully prepared.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._worker = _ExportWorker(
            self._source,
            self.selected_paths(),
            destination,
            replace,
            self,
        )
        self._worker.succeeded.connect(self._export_succeeded)
        self._worker.failed.connect(
            lambda message: self._status.setText(f"Export failed: {message}")
        )
        self._worker.cancelled.connect(lambda: self._status.setText("Export cancelled."))
        self._worker.finished.connect(self._export_finished)
        self._status.setText("Validating figures and saving the bundle…")
        self._cancel.setText("&Cancel export")
        for widget in (self._figures, self._all, self._none, self._browse):
            widget.setEnabled(False)
        self._selection_changed()
        self._worker.start()

    def _export_succeeded(self, result) -> None:
        self._status.setText(f"Exported {result.figure_count} figures to {result.path}")

    def _export_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        self._cancel.setText("&Close")
        for widget in (self._figures, self._all, self._none, self._browse):
            widget.setEnabled(not self._invalidated)
        self._selection_changed()
        if self._closing:
            super().reject()

    def _shutdown(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait()

    def invalidate_source(self) -> None:
        self._invalidated = True
        self._selection_changed()
        self.reject()

    def reject(self) -> None:
        if self._worker is not None:
            self._closing = True
            self._worker.requestInterruption()
            self._status.setText("Cancelling export…")
        else:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)


class FigureExportBar(QWidget):
    """Gallery hook retaining the existing clear/load_job_dir lifecycle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source: FigureSource | None = None
        self._dialog: FigureExportDialog | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._status = _label()
        self._status.setObjectName("Dim")
        self._button = QPushButton("Export &figures…")
        self._button.setAccessibleName("Export selected analysis figures")
        self._button.clicked.connect(self._open_dialog)
        layout.addWidget(self._status, 1)
        layout.addWidget(self._button)
        self.clear()

    def clear(self) -> None:
        if self._dialog is not None:
            self._dialog.invalidate_source()
        self._source = None
        self._button.setEnabled(False)
        self._status.setText("Load a completed job to export figures.")

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        try:
            source = load_figure_source(job_dir)
        except (OSError, ValueError) as exc:
            self._status.setText(f"Figure export unavailable: {exc}")
            return
        self._source = source
        self._button.setEnabled(bool(source.figures))
        self._status.setText(
            f"{len(source.figures)} recorded PNG figures available for export."
            if source.figures
            else "This job has no recorded PNG figures to export."
        )

    def _open_dialog(self) -> None:
        if self._source is None or not self._source.figures:
            return
        if self._dialog is not None:
            self._dialog.raise_()
            return
        dialog = FigureExportDialog(self._source, self)
        self._dialog = dialog
        dialog.finished.connect(self._dialog_finished)
        dialog.open()

    def _dialog_finished(self, _result: int) -> None:
        dialog, self._dialog = self._dialog, None
        if dialog is not None:
            dialog.deleteLater()
