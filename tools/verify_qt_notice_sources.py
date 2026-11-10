#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify retained notice bytes; --fetch also verifies their upstream sources."""

import argparse
import hashlib
import json
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "licenses/qt-6.12.0"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(fetch=False):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    archives = {}
    with tempfile.TemporaryDirectory(prefix="capturesuite-notices-") as temp:
        if fetch:
            for source in manifest["sources"]:
                path = Path(temp) / (source["module"] + ".tar.xz")
                with urllib.request.urlopen(source["url"], timeout=120) as response:
                    path.write_bytes(response.read())
                if digest(path.read_bytes()) != source["sha256"]:
                    raise ValueError("Changed upstream archive: " + source["url"])
                archives[source["module"]] = tarfile.open(path)
        try:
            count = 0
            for group, entries in manifest["groups"].items():
                for entry in entries:
                    data = (ROOT / entry["path"]).read_bytes()
                    if digest(data) != entry["sha256"]:
                        raise ValueError("Changed retained notice: " + entry["path"])
                    if fetch:
                        if "archiveMember" in entry:
                            original = archives[group].extractfile(entry["archiveMember"]).read()
                        else:
                            with urllib.request.urlopen(entry["url"], timeout=120) as response:
                                original = response.read()
                        if digest(original) != entry["sha256"]:
                            raise ValueError("Changed upstream notice: " + entry["path"])
                    count += 1
        finally:
            for archive in archives.values():
                archive.close()
    print(f"Verified {count} retained source notice files")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    verify(parser.parse_args().fetch)
