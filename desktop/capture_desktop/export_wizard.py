# SPDX-License-Identifier: GPL-3.0-only
"""Export wizard for sealed session packages."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from . import theme


@dataclass
class ExportOptions:
    out_dir: str
    include_radar: bool = True
    include_video: bool = True
    include_emg: bool = True
    include_imu: bool = True
    include_numeric: bool = True
    verify: bool = True
    write_sidecar: bool = True


_MODALITY_FLAGS = (
    ("radar", "include_radar"),
    ("video", "include_video"),
    ("emg", "include_emg"),
    ("imu", "include_imu"),
    ("numeric", "include_numeric"),
)


def _build_modalities_args(options: ExportOptions) -> list[str]:
    """Translate the wizard checkboxes into the export_session --modalities contract.

    An explicitly empty selection becomes "--modalities ''", which
    export_session.py rejects with a clear error (metadata-only export is an
    owner decision, not invented here).
    """
    selected = [name for name, attr in _MODALITY_FLAGS if getattr(options, attr)]
    return ["--modalities", ",".join(selected)]


class ExportWizard(QDialog):
    def __init__(
        self,
        package_path: str,
        *,
        default_out: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._package_path = package_path
        self.options = ExportOptions(out_dir=default_out or "")
        self.setWindowTitle("Export session")
        self.setMinimumWidth(600)
        self.setFont(theme.ui(9))

        root = QVBoxLayout(self)
        from capture_session.export_inventory import inspect_export_inventory

        self._inventory = inspect_export_inventory(package_path)
        title = QLabel(Path(package_path).name)
        title.setFont(theme.ui(12))
        title.setWordWrap(True)
        root.addWidget(title)
        intro = QLabel(
            "Choose recorded data to take into another tool. "
            "The original recording stays unchanged. Use a new or empty destination folder."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Dim")
        root.addWidget(intro)

        form = QFormLayout()
        self._path = QLineEdit(default_out)
        browse = QDialogButtonBox()
        btn = browse.addButton("Browse…", QDialogButtonBox.ButtonRole.ActionRole)
        btn.clicked.connect(self._pick_dir)
        path_row = QWidget()
        path_layout = QVBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self._path)
        path_layout.addWidget(browse)
        form.addRow("Destination", path_row)
        root.addLayout(form)

        self._radar = QCheckBox("Radar streams (MCAP summaries + stream.json)")
        self._radar.setChecked(True)
        self._video = QCheckBox("Video (ffmpeg rewrap when available)")
        self._video.setChecked(True)
        self._emg = QCheckBox("EMG batch summaries")
        self._emg.setChecked(True)
        self._imu = QCheckBox("IMU frame summaries")
        self._imu.setChecked(True)
        self._numeric = QCheckBox(
            "Numeric samples (CSV values, channel labels and original clocks)"
        )
        self._numeric.setChecked(True)
        self._verify = QCheckBox("Check that the export contains recorded data")
        self._verify.setChecked(True)
        self._sidecar = QCheckBox("Include a record of these export choices")
        self._sidecar.setChecked(True)
        labels = {
            "radar": "Radar — frames and stream description",
            "video": "Video — media files",
            "emg": "EMG — recorded batch summaries",
            "imu": "IMU — recorded frame summaries",
            "numeric": "Numeric — recorded channel values and original clocks",
        }
        self._data_boxes = []
        absent = []
        for kind, _option in sorted(
            _MODALITY_FLAGS, key=lambda row: not self._inventory.kinds[row[0]].streams
        ):
            box = getattr(self, "_" + kind)
            self._data_boxes.append(box)
            entry = self._inventory.kinds[kind]
            count = len(entry.streams)
            box.setText(labels[kind])
            box.setChecked(bool(count) or bool(self._inventory.incomplete))
            box.setEnabled(bool(count) or bool(self._inventory.incomplete))
            if not count and not self._inventory.incomplete:
                box.setParent(self)
                box.hide()
                absent.append(kind.upper() if kind in {"emg", "imu"} else kind.title())
                continue
            root.addWidget(box)
            if count:
                detail = f"{count} recorded stream{'s' if count != 1 else ''}"
                if kind == "video":
                    detail += f" · {len(entry.files)} media files"
                else:
                    detail += f" · {entry.messages:,} indexed messages"
                detail += " · " + ", ".join(sorted(entry.sources))
            else:
                detail = (
                    "Availability unknown — recording metadata is incomplete"
                    if self._inventory.incomplete
                    else "No recorded data found"
                )
            context = QLabel(detail)
            context.setWordWrap(True)
            context.setObjectName("Dim")
            root.addWidget(context)
        if absent:
            not_recorded = QLabel("Not recorded: " + ", ".join(absent))
            not_recorded.setObjectName("Dim")
            not_recorded.setWordWrap(True)
            root.addWidget(not_recorded)
        self._timing_note = QLabel(
            "Numeric CSV keeps exact device timestamps and separate MCAP clocks. "
            "Session estimates use within-batch clock differences only; they are uncalibrated. "
            "Missing native clocks stay blank. Declared gaps are copied, never filled."
        )
        self._timing_note.setWordWrap(True)
        root.addWidget(self._timing_note)
        self._numeric.toggled.connect(self._timing_note.setVisible)
        self._timing_note.setVisible(self._numeric.isChecked())
        if self._inventory.incomplete:
            self._inventory_note = QLabel(
                "Some recorded metadata could not be classified. Choices remain available; "
                "the exporter will validate selected data. Details: "
                + "; ".join(self._inventory.incomplete[:3])
            )
        else:
            self._inventory_note = QLabel(
                "Counts come from recorded file indexes; messages can contain many samples. "
                "Values are decoded and validated during export."
            )
        self._inventory_note.setWordWrap(True)
        self._inventory_note.setObjectName("Dim")
        root.addWidget(self._inventory_note)
        root.addWidget(self._verify)
        root.addWidget(self._sidecar)

        pkg = QLabel(package_path)
        pkg.setObjectName("Faint")
        pkg.setWordWrap(True)
        root.addWidget(pkg)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._export_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._export_button.setText("Export selected data")
        for box in self._data_boxes:
            box.toggled.connect(self._refresh_selection)
        self._refresh_selection()
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _refresh_selection(self) -> None:
        self._export_button.setEnabled(any(box.isChecked() for box in self._data_boxes))

    def _pick_dir(self) -> None:
        start = self._path.text() or str(Path(self._package_path).parent)
        out = QFileDialog.getExistingDirectory(self, "Export folder", start)
        if out:
            self._path.setText(out)

    def _accept(self) -> None:
        if not any(box.isChecked() for box in self._data_boxes):
            return
        out = self._path.text().strip()
        if not out:
            QMessageBox.warning(self, "Export", "Choose a destination folder.")
            return
        self.options = ExportOptions(
            out_dir=out,
            include_radar=self._radar.isChecked(),
            include_video=self._video.isChecked(),
            include_emg=self._emg.isChecked(),
            include_imu=self._imu.isChecked(),
            include_numeric=self._numeric.isChecked(),
            verify=self._verify.isChecked(),
            write_sidecar=self._sidecar.isChecked(),
        )
        self.accept()


def run_export(
    package_path: str, options: ExportOptions, *, repo_root: Path | None = None
) -> tuple[int, str]:
    """Run the maintained exporter; return (exit_code, combined_output_tail)."""
    root = repo_root or Path(__file__).resolve().parents[2]
    if getattr(sys, "frozen", False):
        # A bundled executable is not a Python interpreter. Re-enter its
        # exporter command instead of looking for a source checkout/script.
        cmd = [sys.executable, "--export-session", package_path, options.out_dir]
        root = Path(package_path).resolve().parent
    else:
        py = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Python"
            / "Python312"
            / "python.exe"
        )
        if not py.is_file():
            py = Path(sys.executable)
        cmd = [str(py), str(root / "tools" / "export_session.py"), package_path, options.out_dir]
    if options.verify:
        cmd.append("--verify")
    cmd += _build_modalities_args(options)
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    tail = (proc.stderr or proc.stdout)[-800:]
    if proc.returncode == 0 and options.write_sidecar:
        sidecar = Path(options.out_dir) / "provenance_sidecar.json"
        manifest_path = Path(options.out_dir) / "export_manifest.json"
        if manifest_path.is_file():
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
            # Requested inclusion is not the same as actual output: record what
            # the exporter really emitted (non-empty manifest stream arrays).
            actual = {m: bool(doc.get(m)) for m in ("radar", "video", "emg", "imu", "numeric")}
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaId": "capture.export_provenance_sidecar/1",
                        "packagePath": package_path,
                        "exportManifest": "export_manifest.json",
                        "streams": {
                            "radar": options.include_radar,
                            "video": options.include_video,
                            "emg": options.include_emg,
                            "imu": options.include_imu,
                            "numeric": options.include_numeric,
                        },
                        "actualStreams": actual,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    return proc.returncode, tail
