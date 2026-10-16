#!/usr/bin/env python3
"""Reassemble and verify the complete Metric Human Lab historical ZIP."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "PARTS_MANIFEST.json").read_text(encoding="utf-8"))
output = root / manifest["filename"]
temporary = root / (manifest["filename"] + ".partial")
whole = hashlib.sha256()
count = 0
try:
    with temporary.open("wb") as dest:
        for part in manifest["parts"]:
            data = (root / "parts" / part["name"]).read_bytes()
            if len(data) != part["bytes"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError("Part missing or corrupted: " + part["name"])
            dest.write(data)
            whole.update(data)
            count += len(data)
    if count != manifest["bytes"] or whole.hexdigest() != manifest["sha256"]:
        raise ValueError("Complete archive hash/size mismatch")
    os.replace(temporary, output)
    print(f"Verified: {output} ({count} bytes, SHA256 {whole.hexdigest()})")
except BaseException:
    temporary.unlink(missing_ok=True)
    raise
