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
    verify: bool = True
    write_sidecar: bool = True


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
        self.setMinimumWidth(480)
        self.setFont(theme.ui(9))

        root = QVBoxLayout(self)
        intro = QLabel(
            "Export continuous streams offline. Raw package is never modified. "
            "A provenance sidecar (export_manifest.json) is written to the destination."
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
        self._verify = QCheckBox("Verify export (--verify)")
        self._verify.setChecked(True)
        self._sidecar = QCheckBox("Write provenance sidecar (export_manifest.json)")
        self._sidecar.setChecked(True)
        for box in (self._radar, self._video, self._emg, self._imu, self._verify, self._sidecar):
            root.addWidget(box)

        pkg = QLabel(package_path)
        pkg.setObjectName("Faint")
        pkg.setWordWrap(True)
        root.addWidget(pkg)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _pick_dir(self) -> None:
        start = self._path.text() or str(Path(self._package_path).parent)
        out = QFileDialog.getExistingDirectory(self, "Export folder", start)
        if out:
            self._path.setText(out)

    def _accept(self) -> None:
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
            verify=self._verify.isChecked(),
            write_sidecar=self._sidecar.isChecked(),
        )
        self.accept()


def run_export(package_path: str, options: ExportOptions, *, repo_root: Path | None = None) -> tuple[int, str]:
    """Run tools/export_session.py; return (exit_code, combined_output_tail)."""
    root = repo_root or Path(__file__).resolve().parents[2]
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
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    tail = (proc.stderr or proc.stdout)[-800:]
    if proc.returncode == 0 and options.write_sidecar:
        sidecar = Path(options.out_dir) / "provenance_sidecar.json"
        manifest_path = Path(options.out_dir) / "export_manifest.json"
        if manifest_path.is_file():
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
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    return proc.returncode, tail
