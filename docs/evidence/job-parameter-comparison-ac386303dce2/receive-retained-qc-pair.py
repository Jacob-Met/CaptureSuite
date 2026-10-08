# SPDX-License-Identifier: GPL-3.0-only
"""Author receiving: read the already qualified QC pair; do not run a producer."""

import argparse
import datetime
import hashlib
import json
import pathlib
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=pathlib.Path, required=True)
parser.add_argument("--fixture-root", type=pathlib.Path, required=True)
parser.add_argument("--evidence-root", type=pathlib.Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source_root / "desktop"))

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from capture_desktop import theme, widgets_analysis_comparison as ui
from capture_desktop.widgets_analysis_plots import JobInspector


def hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


freeze = json.loads((args.evidence_root / "source-freeze-v2.json").read_bytes())


def verify_source():
    for row in freeze["files"]:
        raw = (args.source_root / row["path"]).read_bytes()
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]


verify_source()
before = hashes(args.fixture_root)
loaded = args.fixture_root / "processing/jobs/loaded-qc"
other = args.fixture_root / "processing/jobs/other-qc"
app = QApplication.instance() or QApplication([])
theme.apply_theme(app, setting="dark")
inspector = JobInspector()
inspector.load_job_dir(loaded)
inspector.show()
button = inspector._parameters._button
assert button.isEnabled()
button.setFocus()
QTest.keyClick(button, Qt.Key.Key_Space)
app.processEvents()
dialog = inspector._parameters._dialog
assert dialog is not None and dialog.isVisible()
old_chooser = ui.QFileDialog.getExistingDirectory
try:
    ui.QFileDialog.getExistingDirectory = lambda *_args: str(other)
    QTest.mouseClick(dialog._choose, Qt.MouseButton.LeftButton)
    app.processEvents()
finally:
    ui.QFileDialog.getExistingDirectory = old_chooser
assert not dialog._error.text()
assert {row.pointer for row in dialog._rows} == {
    "/extra/include", "/extra/side", "/extra/threshold", "/overwriteJobId"
}
assert json.loads(dialog._params.toPlainText()) == json.loads((loaded / "params.json").read_bytes())
assert dialog._params.isReadOnly()
assert dialog._other_value.isReadOnly() and dialog._loaded_value.isReadOnly()
QTest.keyClick(dialog._table, Qt.Key.Key_Down)
app.processEvents()
assert json.loads(dialog._other_value.toPlainText()) == "left"
assert json.loads(dialog._loaded_value.toPlainText()) == "right"
for job in (other, loaded):
    for name in ("params.json", "job_manifest.json"):
        assert hashlib.sha256((job / name).read_bytes()).hexdigest() in (
            dialog._comparison_provenance.toPlainText()
        )
image = args.evidence_root / "native-comparison-v2.png"
assert dialog.grab().save(str(image))
inspector.clear()
app.processEvents()
assert inspector._parameters._dialog is None
assert not inspector._parameters._button.isEnabled()
inspector.load_job_dir(other)
assert inspector._parameters._source.job_id == "other-qc"
inspector.close()
app.processEvents()
verify_source()
after = hashes(args.fixture_root)
assert before == after
receipt = {
    "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "command": [sys.executable, *sys.argv],
    "source_freeze": freeze,
    "source_unchanged_before_after": True,
    "fixture_root": str(args.fixture_root),
    "fixture_files_before": before,
    "fixture_files_after": after,
    "fixture_unchanged": before == after,
    "runtime": {"python": sys.version, "PySide6": PySide6.__version__, "Qt": qVersion()},
    "native_boundary": "Actual keyboard, comparison action, typed rows, full read-only values, provenance, clear/reload and rendered dark Qt dialog. Native folder chooser return is controlled. Existing real QC producer artifacts are read; no producer is rerun.",
    "image": {"path": image.name, "bytes": image.stat().st_size, "sha256": hashlib.sha256(image.read_bytes()).hexdigest()},
    "result": "PASS",
}
(args.evidence_root / "retained-qc-pair-v2.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"result": "PASS", "fixture_files_unchanged": len(before), "runtime": receipt["runtime"], "image": receipt["image"]}))
