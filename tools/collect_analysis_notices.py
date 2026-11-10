#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Collect installed license texts for distributions in PyInstaller's actual TOC."""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DISTRIBUTIONS = {
    "capture-analysis",
    "capture-session",
    "capture-protocol",
    "capture-desktop",
}
LICENSE_WORDS = ("license", "licence", "copying", "notice", "copyright")


def toc_entries(toc: Path) -> list[tuple[str, str, str]]:
    entries = []

    def visit(value):
        if isinstance(value, (tuple, list)):
            if (
                len(value) == 3
                and all(isinstance(x, str) for x in value)
                and value[2] in {"PYMODULE", "EXTENSION", "BINARY", "DATA"}
            ):
                entries.append(tuple(value))
            else:
                for child in value:
                    visit(child)

    visit(ast.literal_eval(toc.read_text()))
    return entries


def bundled_distribution_files(toc: Path) -> dict[str, list[str]]:
    """Resolve RECORD ownership, including plugins; namespaces are not owners."""
    sources = {os.path.abspath(source): source for _, source, _ in toc_entries(toc)}
    result = {}
    for dist in metadata.distributions():
        owned = []
        for item in dist.files or []:
            path = os.path.abspath(dist.locate_file(item))
            if path in sources:
                owned.append(str(item))
        name = dist.metadata["Name"]
        # Split PySide wheels repeat the shared namespace initializer in RECORD.
        # That one file alone is not evidence that an optional Qt runtime shipped.
        # Keep its attribution with distributions that own actual bundled modules,
        # libraries or data; a real WebEngine file still requires its own notices.
        only_shared_pyside_init = (
            name.lower().replace("-", "_").startswith("pyside6_")
            and set(owned) == {"PySide6/__init__.py"}
        )
        if owned and not only_shared_pyside_init:
            result[name] = sorted(set(owned))
    result.setdefault("pyinstaller", [])  # included bootloader
    return result


def bundled_distributions(toc: Path) -> set[str]:
    return set(bundled_distribution_files(toc))


def qt_notice_groups(toc: Path) -> set[str]:
    groups = set()
    base = {
        "Core",
        "Gui",
        "Widgets",
        "Network",
        "DBus",
        "Test",
        "Concurrent",
        "OpenGL",
        "OpenGLWidgets",
        "XcbQpa",
        "EglFSDeviceIntegration",
        "EglFsKmsSupport",
    }
    for _, source, kind in toc_entries(toc):
        if kind != "BINARY" or "/PySide6/Qt/" not in source:
            continue
        name = Path(source).name
        match = re.match(r"libQt6(.*?)\.so", name)
        if match:
            module = match[1]
            if module in base:
                group = "qtbase"
            elif module.startswith(("Multimedia", "FFmpegStub")):
                group = "qtmultimedia"
            elif module.startswith(("Qml", "Quick")):
                group = "qtdeclarative"
            elif module.startswith("VirtualKeyboard"):
                group = "qtvirtualkeyboard"
            elif module.startswith(("Wayland", "WlShell")):
                group = "qtwayland"
            elif module.startswith("Svg"):
                group = "qtsvg"
            elif module == "Pdf":
                group = "qtpdf"
            else:
                raise ValueError(f"No source-notice coverage for bundled Qt module: {module}")
            groups.add(group)
        if "/plugins/imageformats/" in source:
            groups.add("qtimageformats")
        if name.startswith("libicu"):
            groups.add("icu")
    return groups


def pyside_source_version(name: str, version: str) -> str:
    normalized = name.lower().replace("-", "_")
    expected = "6.12.0.140" if normalized == "pyside6_pdf" else "6.12.0"
    if version != expected:
        raise ValueError(f"No pinned source notices for {name}=={version}")
    # Official create_wheels.py appends Chromium140 to Pdf's wheel version;
    # the Python binding source remains the PySide6.12.0 source archive.
    return "6.12.0"


def upstream_notices(group: str, version: str, copy, folder: Path) -> list[dict]:
    root = ROOT / "tools/licenses/qt-6.12.0"
    manifest = json.loads((root / "manifest.json").read_text())
    if version != "6.12.0":
        raise ValueError(f"No pinned Qt/PySide source notices for version {version}")
    selected = manifest["groups"].get(group)
    if not selected:
        raise ValueError(f"No upstream notice group {group}")
    copied = []
    for entry in selected:
        source = root / entry["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Changed upstream notice: {entry['path']}")
        copied.append(copy(source, folder / entry["path"]))
    copied.append(copy(root / "manifest.json", folder / "source-manifest.json"))
    return copied


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

    distribution_files = bundled_distribution_files(toc)
    for name in sorted(distribution_files, key=str.lower):
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
        if not notices and name.lower().replace("-", "_") in {
            "pyside6",
            "pyside6_essentials",
            "pyside6_addons",
            "pyside6_pdf",
            "shiboken6",
        }:
            notices = upstream_notices(
                "pyside", pyside_source_version(name, dist.version), copy, Path(folder)
            )
            origin = "Pinned upstream PySide source archive; see source-manifest.json"
        if not notices:
            raise ValueError(f"No license text found for bundled {name}=={dist.version}")
        packages.append(
            {
                "name": name,
                "version": dist.version,
                "origin": origin,
                "notices": notices,
                "bundledFiles": distribution_files[name],
            }
        )
    for group in sorted(qt_notice_groups(toc)):
        # All current wheel Qt libraries are 6.12.0; verify the owning wheel
        # rather than assigning the version from an import namespace.
        versions = {
            pyside_source_version(name, metadata.version(name))
            for name in distribution_files
            if name.lower().startswith("pyside6")
        }
        if versions != {"6.12.0"}:
            raise ValueError(f"Unsupported bundled Qt/PySide versions: {versions}")
        if group == "icu":
            libraries = [
                source
                for _, source, kind in toc_entries(toc)
                if kind == "BINARY"
                and Path(source).name == "libicuuc.so.73"
                and "/PySide6/Qt/" in source
            ]
            if not libraries:
                raise ValueError("ICU notice coverage requires the actual ICU73 library")
            for library in libraries:
                version = (ctypes.c_ubyte * 4)()
                ctypes.CDLL(library).u_getVersion_73(version)
                if list(version) != [73, 2, 0, 0]:
                    raise ValueError(f"No pinned notices for ICU version {list(version)}")
        packages.append(
            {
                "name": "Qt-source-notices-" + group,
                "version": {"icu": "73.2", "qtpdf": "6.140.0"}.get(group, "6.12.0"),
                "origin": (
                    "Upstream source notice subset; conservative module coverage, "
                    "not an exact third-party SBOM"
                ),
                "notices": upstream_notices(group, "6.12.0", copy, Path("Qt") / group),
            }
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
