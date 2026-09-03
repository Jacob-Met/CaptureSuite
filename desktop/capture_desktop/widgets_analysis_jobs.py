# SPDX-License-Identifier: GPL-3.0-only
"""Analysis job dependency pickers (pose / kinematics / ml_bundle / eval)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme


def list_job_ids(package: Path, *, require_rel: str | None = None) -> list[str]:
    """List processing/jobs/* ids, optionally requiring a relative path under the job."""
    jobs = package / "processing" / "jobs"
    if not jobs.is_dir():
        return []
    out: list[str] = []
    for child in sorted(jobs.iterdir(), reverse=True):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if require_rel and not (child / require_rel).exists():
            continue
        out.append(child.name)
    return out


class AnalysisJobExtras(QWidget):
    """Extra fields for advanced analysis commands."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._package = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._box = QGroupBox("Job dependencies")
        form = QFormLayout(self._box)
        self._pose_job = QComboBox()
        self._pose_job.setEditable(True)
        self._kin_job = QComboBox()
        self._kin_job.setEditable(True)
        self._feat_job = QComboBox()
        self._feat_job.setEditable(True)
        self._bundle_job = QComboBox()
        self._bundle_job.setEditable(True)
        self._window_sec = QLineEdit("1.0")
        self._hop_sec = QLineEdit("0.05")
        form.addRow("Pose job", self._pose_job)
        form.addRow("Kinematics job", self._kin_job)
        form.addRow("Features job", self._feat_job)
        form.addRow("ML bundle job", self._bundle_job)
        win_row = QHBoxLayout()
        win_row.addWidget(QLabel("Window s"))
        win_row.addWidget(self._window_sec)
        win_row.addWidget(QLabel("Hop s"))
        win_row.addWidget(self._hop_sec)
        form.addRow("ML windows", win_row)
        root.addWidget(self._box)

        hint = QLabel(
            "Pose → kinematics → ml_bundle → eval. "
            "Features job supplies radar motion energy when present."
        )
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        hint.setFont(theme.ui(8))
        root.addWidget(hint)

    def set_package(self, package: str) -> None:
        self._package = package
        self.refresh()

    def refresh(self) -> None:
        pkg = Path(self._package) if self._package else None
        self._refill(
            self._pose_job,
            list_job_ids(pkg, require_rel="pose") if pkg else [],
        )
        self._refill(
            self._kin_job,
            list_job_ids(pkg, require_rel="kinematics/kinematics.parquet") if pkg else [],
        )
        self._refill(
            self._feat_job,
            list_job_ids(pkg, require_rel="features") if pkg else [],
        )
        self._refill(
            self._bundle_job,
            list_job_ids(pkg, require_rel="ml_bundle/manifest.json") if pkg else [],
        )

    @staticmethod
    def _refill(combo: QComboBox, ids: list[str]) -> None:
        current = combo.currentText().strip()
        combo.clear()
        combo.addItem("")
        for jid in ids:
            combo.addItem(jid)
        if current:
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(current)

    def set_command(self, command: str) -> None:
        need_pose = command == "kinematics"
        need_kin = command == "ml_bundle"
        need_feat = command == "ml_bundle"
        need_bundle = command == "eval"
        need_win = command == "ml_bundle"
        self._pose_job.setEnabled(need_pose)
        self._kin_job.setEnabled(need_kin)
        self._feat_job.setEnabled(need_feat)
        self._bundle_job.setEnabled(need_bundle)
        self._window_sec.setEnabled(need_win)
        self._hop_sec.setEnabled(need_win)
        self.setVisible(
            command in ("pose", "kinematics", "ml_bundle", "eval")
        )

    def build_extra(self, command: str) -> dict:
        extra: dict = {}
        if command == "kinematics":
            pid = self._pose_job.currentText().strip()
            if pid:
                extra["pose_job_id"] = pid
        elif command == "ml_bundle":
            extra["kinematics_job_id"] = self._kin_job.currentText().strip()
            extra["features_job_id"] = self._feat_job.currentText().strip()
            try:
                extra["window_sec"] = float(self._window_sec.text() or "1.0")
                extra["hop_sec"] = float(self._hop_sec.text() or "0.05")
            except ValueError:
                extra["window_sec"] = 1.0
                extra["hop_sec"] = 0.05
        elif command == "eval":
            bid = self._bundle_job.currentText().strip()
            if bid:
                extra["ml_bundle_job_id"] = bid
        return extra

    def validate_for(self, command: str) -> str | None:
        extra = self.build_extra(command)
        if command == "kinematics" and not extra.get("pose_job_id"):
            return "Select a pose job (run Pose first)."
        if command == "ml_bundle":
            if not extra.get("kinematics_job_id"):
                return "Select a kinematics job."
            if not extra.get("features_job_id"):
                return "Select a features job (radar preferred)."
        if command == "eval" and not extra.get("ml_bundle_job_id"):
            return "Select an ml_bundle job."
        return None


def peek_ml_bundle_summary(job_dir: Path) -> str:
    man = job_dir / "ml_bundle" / "manifest.json"
    if not man.is_file():
        return ""
    try:
        doc = json.loads(man.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    n = len(doc.get("targetColumns") or [])
    grids = doc.get("analysisGrids") or []
    grid = grids[0].get("gridId") if grids else "—"
    return f"ML bundle · grid={grid} · {n} target cols · provisional={doc.get('provisional')}"
