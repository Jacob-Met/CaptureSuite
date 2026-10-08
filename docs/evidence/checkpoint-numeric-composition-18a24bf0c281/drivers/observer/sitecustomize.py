# SPDX-License-Identifier: GPL-3.0-only
"""Receipt-only observer; no application function, transport or output is replaced."""
import atexit
import hashlib
import json
import os
import sys
from pathlib import Path

def _capture_modules():
    target = os.environ.get("CAPTURE_NUMERIC_MODULE_RECEIPT")
    source = os.environ.get("CAPTURE_NUMERIC_SOURCE")
    if not target or not source:
        return
    root = Path(source).resolve()
    rows = []
    for name, module in sorted(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        p = Path(path).resolve()
        if p.is_file() and p.is_relative_to(root):
            data = p.read_bytes()
            rows.append({"module": name, "path": p.relative_to(root).as_posix(),
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    Path(target).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

atexit.register(_capture_modules)
