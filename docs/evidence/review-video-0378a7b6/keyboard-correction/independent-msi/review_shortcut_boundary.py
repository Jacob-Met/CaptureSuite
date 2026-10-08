# SPDX-License-Identifier: GPL-3.0-only
"""Independent boundary matrix for the narrow focused-button Space exception."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(r"C:\Users\minec\hamon-0378a7b6-capturesuite-discovery")
OUT = Path(__file__).resolve().parent
os.environ["QT_QPA_PLATFORM"] = "offscreen"
for path in ("desktop", "libs/python/capture_analysis", "libs/python/capture_session"):
    sys.path.insert(0, str(ROOT / path))
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QPushButton
from capture_desktop.widgets_review_video import RecordedVideoReview

SOURCE = ROOT / "desktop/capture_desktop/widgets_review_video.py"
EXPECTED = "126c4ec87d5af60d151292ff1b2d7f7f3d5ad2f63112507c71d05385bf80f594"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SOURCE) == EXPECTED
app = QApplication([])
view = RecordedVideoReview()
foreign = QPushButton()
rows = []
for name, target in [("play", view._play), ("reload", view._reload), ("toggle", view._toggle),
                     ("choice", view._choice), ("seek", view._seek), ("foreign", foreign)]:
    for key_name, key in [("Space", Qt.Key.Key_Space), ("C", Qt.Key.Key_C), ("Return", Qt.Key.Key_Return)]:
        for mod_name, mod in [("none", Qt.KeyboardModifier.NoModifier),
                              ("ctrl", Qt.KeyboardModifier.ControlModifier),
                              ("alt", Qt.KeyboardModifier.AltModifier),
                              ("shift", Qt.KeyboardModifier.ShiftModifier),
                              ("meta", Qt.KeyboardModifier.MetaModifier)]:
            event = QKeyEvent(QEvent.Type.ShortcutOverride, key, mod)
            event.ignore()
            result = view.eventFilter(target, event)
            expected = name in ("play", "reload", "toggle") and key_name == "Space" and mod_name == "none"
            assert result is expected, (name, key_name, mod_name, result)
            if expected:
                assert event.isAccepted()
            rows.append({"control": name, "key": key_name, "modifiers": mod_name, "claimed": result})
assert sha(SOURCE) == EXPECTED
receipt = {"outcome": "pass", "sourceSha256": EXPECTED, "sourceStable": True,
           "cases": len(rows), "claimed": sum(row["claimed"] for row in rows),
           "rows": rows, "boundary": "Direct native Qt ShortcutOverride boundary matrix; owner separately qualifies actual MainWindow routing."}
(OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({key: value for key, value in receipt.items() if key != "rows"}))
view.close()
foreign.close()
