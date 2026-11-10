#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Collect installed license texts for distributions in PyInstaller's actual TOC."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DISTRIBUTIONS = {"capture-analysis", "capture-session", "capture-protocol"}
LICENSE_WORDS = ("license", "licence", "copying", "notice", "copyright")


def bundled_distributions(toc: Path) -> set[str]:
    modules = set()

    def visit(value):
        if isinstance(value, (tuple, list)):
            if (
                len(value) == 3
                and all(isinstance(x, str) for x in value)
                and value[2] in {"PYMODULE", "EXTENSION"}
            ):
                modules.add(value[0].split(".")[0].split("/")[0])
            for child in value:
                visit(child)

    visit(ast.literal_eval(toc.read_text()))
    mapping = metadata.packages_distributions()
    return {name for module in modules for name in mapping.get(module, [])} | {"pyinstaller"}


def collect(toc: Path, bundle: Path) -> dict:
    destination = bundle / "THIRD_PARTY_NOTICES"
    destination.mkdir(exist_ok=True)
    packages = []

    def copy(source, relative):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return {
            "path": relative.as_posix(),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }

    for name in sorted(bundled_distributions(toc), key=str.lower):
        if name.lower() in PROJECT_DISTRIBUTIONS:
            continue
        dist = metadata.distribution(name)
        folder = re.sub(r"[^a-zA-Z0-9._-]", "_", name) + "-" + dist.version
        notices = []
        for item in sorted(dist.files or [], key=str):
            if not any(word in Path(str(item)).name.lower() for word in LICENSE_WORDS):
                continue
            path = Path(dist.locate_file(item))
            if not path.is_file():
                continue
            parts = Path(str(item)).parts
            if ".." in parts or Path(str(item)).is_absolute():
                raise ValueError(f"unsafe distribution notice path for {name}")
            notices.append(copy(path, Path(folder) / str(item)))
        origin = "installed distribution license files"
        if not notices and name.lower() == "mcap" and dist.version == "1.6.0":
            notices.append(
                copy(ROOT / "tools/licenses/mcap-1.6.0/LICENSE", Path(folder) / "LICENSE")
            )
            origin = (
                "https://github.com/foxglove/mcap/blob/"
                "ceaf05f1c33a7b8bca567092865d52cf41639e2d/LICENSE"
            )
        if not notices:
            raise ValueError(f"No license text found for bundled {name}=={dist.version}")
        packages.append(
            {"name": name, "version": dist.version, "origin": origin, "notices": notices}
        )
    native = {}

    def visit_native(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and all(isinstance(x, str) for x in value) and value[2] == "BINARY":
                source = Path(value[1])
                if str(source).startswith(("/lib/", "/usr/lib/")) and not source.name.startswith(
                    "libpython"
                ):
                    canonical = source.resolve()
                    owner = (
                        subprocess.check_output(["dpkg-query", "-S", str(canonical)], text=True)
                        .split(": ", 1)[0]
                        .strip()
                    )
                    version = subprocess.check_output(
                        ["dpkg-query", "-W", "-f=${Version}", owner], text=True
                    ).strip()
                    package = owner.split(":")[0]
                    copyright_file = Path("/usr/share/doc") / package / "copyright"
                    if not copyright_file.is_file():
                        raise ValueError(f"Missing bundled native library copyright: {package}")
                    key = (owner, version)
                    if key not in native:
                        native[key] = {
                            "name": owner,
                            "version": version,
                            "origin": "installed Debian/Ubuntu package copyright",
                            "libraries": [],
                            "notices": [
                                copy(copyright_file, Path("native") / package / "copyright")
                            ],
                        }
                    native[key]["libraries"].append(source.name)
            for child in value:
                visit_native(child)

    visit_native(ast.literal_eval(toc.read_text()))
    # Debian copyright files refer to shared full license texts by absolute path.
    # Keep those texts beside the attribution, without retaining host paths.
    for entry in native.values():
        copyright_text = (destination / entry["notices"][0]["path"]).read_text()
        for license_name in sorted(
            set(re.findall(r"/usr/share/common-licenses/([A-Za-z0-9.+-]+)", copyright_text))
        ):
            license_file = Path("/usr/share/common-licenses") / license_name.rstrip(".")
            if not license_file.is_file():
                raise ValueError(f"Missing shared license text: {license_name}")
            entry["notices"].append(
                copy(license_file, Path("native/common-licenses") / license_file.name)
            )
    packages.extend(native[key] for key in sorted(native))
    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    if not python_license.is_file():
        raise ValueError("Python runtime LICENSE.txt is required in the stdlib directory")
    packages.append(
        {
            "name": "Python",
            "version": sys.version.split()[0],
            "origin": "Python runtime LICENSE.txt",
            "notices": [copy(python_license, Path("Python/LICENSE.txt"))],
        }
    )
    project = []
    for subtree in ("schemas", "libs/python/capture_protocol"):
        for filename in ("LICENSE", "NOTICE"):
            relative = Path("CaptureSuite") / subtree / filename
            project.append(copy(ROOT / subtree / filename, relative))
    report = {
        "schemaVersion": 1,
        "packages": packages,
        "projectNotices": project,
        "scope": (
            "Frozen Python distributions and runtime; bundled wheel notices include "
            "their vendored dependencies. Copied system libraries include installed "
            "Debian/Ubuntu package copyrights."
        ),
    }
    (destination / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    (destination / "README.txt").write_text(
        "Actual bundled distribution versions and notice hashes: manifest.json\n"
        "CaptureSuite is split GPL-3.0-only / Apache-2.0; see ../LICENSING.md.\n"
        "These are copied upstream texts, not replacement licensing terms.\n"
    )
    (bundle / "DEPENDENCY_VERSIONS.txt").write_text(
        "".join(f"{p['name']}=={p['version']}\n" for p in packages)
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("toc", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    report = collect(args.toc, args.bundle)
    print(f"Collected notices for {len(report['packages'])} bundled distributions/runtime")


if __name__ == "__main__":
    main()
