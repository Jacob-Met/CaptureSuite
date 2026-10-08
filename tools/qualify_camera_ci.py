#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Qualify the real Windows camera worker and both existing staged layouts.

This runner uses the existing three native camera cases with GStreamer. It does
not substitute a loader fixture, emulate capture, or claim physical-device
qualification. Receipt acceptance requires process, native XML, source, SDK,
binary identity and the restored missing-DLL control to agree.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from run_ci_tests import github_context, source_snapshot

ROOT = Path(__file__).resolve().parents[1]
TEST_NAMES = (
    "worker host spawns camera worker Identify",
    "camera worker start/stop with videotestsrc",
    "camera worker bridge seals into session package",
)
DLL_NAMES = ("abseil_dll.dll", "blake3.dll", "libprotobuf.dll", "lz4.dll", "zstd.dll")
LAYOUTS = {
    "original": Path("workers/camera"),
    "plugin": Path("daemon/plugins/camera_gstreamer"),
    "legacy": Path("daemon/workers/camera"),
}
SDK_VERSION = "1.24.13"
INSTALLER_PINS = {
    "gstreamer-1.0-msvc-x86_64-1.24.13.msi":
        "66915d82adda34189703c36a5d2ef145d2e3afb7afc12c66fcf2ea506e2466d2",
    "gstreamer-1.0-devel-msvc-x86_64-1.24.13.msi":
        "0afb4394c2cba3999c0f5e74f28c2ac5d98f03131140e09246d4dcd60a0a0395",
}
VENDOR_URL_PREFIX = "https://gstreamer.freedesktop.org/data/pkg/windows/1.24.13/msvc/"
MAX_XML_BYTES = 8 * 1024 * 1024
DLL_NOT_FOUND = 0xC0000135


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def regular_file(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), f"Required regular file missing: {path}")


def read_json(path: Path) -> dict:
    regular_file(path)
    require(path.stat().st_size <= 2 * 1024 * 1024, "Metadata exceeds supported size")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), "Expected a metadata object")
    return value


def _count(element: ET.Element, name: str) -> int:
    raw = element.get(name)
    require(isinstance(raw, str) and re.fullmatch(r"0|[1-9][0-9]*", raw) is not None,
            f"Native XML has no valid {name} count")
    return int(raw)


def evaluate_xml(path: Path, process_exit: int | None) -> dict:
    """Read Catch2 XML format 3; assertion totals are not test-case totals."""
    report = {
        "accepted": False, "process_exit": process_exit, "test_names": [],
        "cases": None, "assertions": None, "xml_sha256": None, "problems": [],
    }
    if type(process_exit) is not int or process_exit != 0:
        report["problems"].append("Native test process did not exit successfully")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_XML_BYTES + 1)
        require(len(raw) <= MAX_XML_BYTES, "Native XML exceeds supported size")
        report["xml_sha256"] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig")
        require("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(),
                "DTD/entity declarations are unsupported")
        root = ET.fromstring(text)
        require(root.tag == "Catch2TestRun" and root.get("xml-format-version") == "3",
                "Expected native Catch2 XML format 3")
        require(re.fullmatch(r"3\.[0-9]+\.[0-9]+", root.get("catch2-version", "")) is not None,
                "Missing native Catch2 version")
        cases = root.findall("TestCase")
        names = [case.get("name") for case in cases]
        report["test_names"] = names
        require(len(cases) == len(TEST_NAMES) and set(names) == set(TEST_NAMES),
                "Expected exactly the three distinct camera test cases")
        require(len(list(root.iter("TestCase"))) == len(cases), "Nested test cases unsupported")
        for case in cases:
            results = case.findall("OverallResult")
            require(len(results) == 1 and results[0].get("success") == "true",
                    f"Camera case did not succeed: {case.get('name')}")
            require(_count(results[0], "skips") == 0, "A camera case skipped assertions")
        for tag in ("Failure", "Exception", "FatalErrorCondition", "Skip"):
            require(not list(root.iter(tag)), f"Native XML contains {tag}")
        require(all(node.get("success") == "true" for node in root.iter("Expression")),
                "Native XML contains a failed expression")
        for tag, key in (("OverallResultsCases", "cases"), ("OverallResults", "assertions")):
            nodes = root.findall(tag)
            require(len(nodes) == 1, f"Expected one root {tag}")
            counts = {name: _count(nodes[0], name)
                      for name in ("successes", "failures", "expectedFailures", "skips")}
            report[key] = counts
            require(all(counts[name] == 0 for name in ("failures", "expectedFailures", "skips")),
                    f"{tag} includes failure or skip evidence")
            require(counts["successes"] == 3 if key == "cases" else counts["successes"] > 0,
                    f"{tag} does not establish executed success")
        report["catch2_version"] = root.get("catch2-version")
    except (OSError, UnicodeError, ET.ParseError, ValueError, TypeError) as exc:
        report["problems"].append(f"Native XML unavailable or invalid: {exc}")
    report["accepted"] = not report["problems"]
    return report


def pe_identity(path: Path) -> dict:
    """Inspect actual PE32+ headers and direct imports, without executing a file."""
    regular_file(path)
    raw = path.read_bytes()
    require(len(raw) >= 64 and raw[:2] == b"MZ", f"Not a PE executable: {path}")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    require(pe + 24 <= len(raw) and raw[pe:pe + 4] == b"PE\0\0", f"Invalid PE header: {path}")
    machine, sections = struct.unpack_from("<HH", raw, pe + 4)
    optional_size, characteristics = struct.unpack_from("<HH", raw, pe + 20)
    optional = pe + 24
    require(machine == 0x8664 and 0 < sections <= 96, f"Expected x64 PE: {path}")
    require(optional_size >= 128 and optional + optional_size + sections * 40 <= len(raw),
            f"Truncated PE headers: {path}")
    require(struct.unpack_from("<H", raw, optional)[0] == 0x20B, f"Expected PE32+: {path}")
    require(struct.unpack_from("<I", raw, optional + 108)[0] >= 2,
            f"PE import directory missing: {path}")
    headers_size = struct.unpack_from("<I", raw, optional + 60)[0]
    regions = []
    for index in range(sections):
        section = optional + optional_size + index * 40
        virtual_size, address, size, offset = struct.unpack_from("<IIII", raw, section + 8)
        regions.append((address, virtual_size, size, offset))

    def offset_of(rva: int, size: int = 1) -> int:
        if rva < headers_size and rva + size <= min(headers_size, len(raw)):
            return rva
        for address, virtual_size, raw_size, offset in regions:
            if address <= rva < address + max(virtual_size, raw_size):
                delta = rva - address
                require(delta + size <= raw_size and offset + delta + size <= len(raw),
                        f"PE RVA escapes file-backed bytes: {path}")
                return offset + delta
        raise ValueError(f"Unmapped PE RVA: {path}")

    imports = []
    import_rva, import_size = struct.unpack_from("<II", raw, optional + 120)
    if import_rva:
        require(import_size >= 20, f"Invalid PE import size: {path}")
        for index in range(min(import_size // 20, 4096)):
            entry = offset_of(import_rva + index * 20, 20)
            fields = struct.unpack_from("<IIIII", raw, entry)
            if not any(fields):
                break
            require(fields[3] != 0, f"PE import name missing: {path}")
            name_at = offset_of(fields[3])
            end = raw.find(b"\0", name_at, min(name_at + 512, len(raw)))
            require(end > name_at, f"PE import name invalid: {path}")
            imports.append(raw[name_at:end].decode("ascii").lower())
        else:
            raise ValueError(f"PE import directory is unterminated: {path}")
    return {
        "path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "machine": "x64", "format": "PE32+", "is_dll": bool(characteristics & 0x2000),
        "entrypoint_rva": struct.unpack_from("<I", raw, optional + 16)[0],
        "direct_imports": imports,
    }


def validate_sdk_metadata(value: dict) -> None:
    require(isinstance(value, dict), "SDK manifest must be an object")
    require(value.get("schema") == "capturesuite.camera-sdk.v1" and value.get("accepted") is True,
            "SDK manifest did not accept the expected preparation")
    require(value.get("gstreamer_version") == SDK_VERSION, "SDK version is not pinned 1.24.13")
    require(value.get("binary_coverage") == "all_sdk_dll_and_exe",
            "SDK manifest does not cover the complete extracted binary set")
    installers = value.get("installers")
    require(isinstance(installers, list) and len(installers) == 2,
            "Expected both official SDK MSIs")
    names = set()
    for row in installers:
        require(isinstance(row, dict), "SDK installer record must be an object")
        name = row.get("name")
        require(isinstance(name, str) and name in INSTALLER_PINS and name not in names,
                "SDK installer identity missing, unknown or duplicated")
        names.add(name)
        require(row.get("sha256") == row.get("expected_sha256") == INSTALLER_PINS[name],
                "SDK installer name and SHA256 pins differ")
        require(type(row.get("bytes")) is int and row["bytes"] > 0, "SDK installer bytes missing")
        require(row.get("url") == VENDOR_URL_PREFIX + name,
                "SDK installer name and official vendor URL differ")
    extractions = value.get("extractions")
    require(isinstance(extractions, list) and len(extractions) == 2,
            "Expected both SDK extraction records")
    extracted_names = set()
    for row in extractions:
        require(isinstance(row, dict), "SDK extraction record must be an object")
        name = row.get("name")
        require(isinstance(name, str) and name in names and name not in extracted_names,
                "SDK extraction identities differ")
        extracted_names.add(name)
        require(type(row.get("exit_code")) is int and row["exit_code"] == 0,
                "SDK extraction did not exit successfully")
    probe = value.get("probe")
    require(isinstance(probe, dict) and type(probe.get("exit_code")) is int and
            probe["exit_code"] == 0, "SDK version probe did not exit successfully")
    require(isinstance(probe.get("output"), str) and
            f"GStreamer {SDK_VERSION}" in (line.strip() for line in probe["output"].splitlines()),
            "SDK preparation probe does not report GStreamer 1.24.13")


def inside(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    require(not path.is_symlink(), f"Symbolic input path unsupported: {path}")
    resolved = path.resolve()
    require(resolved.is_relative_to(root.resolve()), f"Path escapes required root: {path}")
    return resolved


def reject_sdk_link(path: Path) -> None:
    # rglob deliberately does not follow directory links. Refuse those entries
    # before filtering extensions so a linked runtime tree cannot be omitted.
    # FILE_ATTRIBUTE_REPARSE_POINT (0x0400) is present only on Windows.
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    require(not path.is_symlink() and not (attributes & 0x0400),
            f"SDK symbolic link or reparse point unsupported: {path}")


def inspect_sdk(manifest_path: Path) -> tuple[Path, dict]:
    value = read_json(manifest_path)
    validate_sdk_metadata(value)
    sdk = Path(value["gstreamer_root"])
    require(sdk.is_absolute() and sdk.is_dir() and not sdk.is_symlink(), "SDK root unavailable")
    reject_sdk_link(sdk)
    sdk = sdk.resolve()
    env_root = os.environ.get("GSTREAMER_1_0_ROOT_MSVC_X86_64", "")
    require(env_root and Path(env_root).resolve() == sdk,
            "Configured SDK root differs from manifest")
    files = value.get("files")
    require(isinstance(files, list) and files, "SDK file manifest missing")
    checked = {}
    for row in files:
        require(isinstance(row, dict), "SDK file record must be an object")
        path = inside(sdk, row["path"])
        regular_file(path)
        name = path.relative_to(sdk).as_posix().lower()
        require(name not in checked, "Duplicate SDK file identity")
        require(type(row.get("bytes")) is int and path.stat().st_size == row["bytes"] and
                sha256(path) == row.get("sha256"), f"SDK file bytes changed: {name}")
        checked[name] = {"path": str(path), "bytes": row["bytes"], "sha256": row["sha256"]}
    require({"include/gstreamer-1.0/gst/gst.h", "lib/gstreamer-1.0.lib",
             "lib/gstapp-1.0.lib", "lib/gstvideo-1.0.lib",
             "bin/gst-inspect-1.0.exe", "bin/gst-launch-1.0.exe"} <= set(checked),
            "SDK manifest omits required headers, import libraries or executables")
    actual_binaries = set()
    for path in sdk.rglob("*"):
        reject_sdk_link(path)
        if path.suffix.lower() in {".dll", ".exe"}:
            regular_file(path)
            relative = inside(sdk, path).relative_to(sdk).as_posix().lower()
            require(relative not in actual_binaries, "Ambiguous SDK binary identity")
            actual_binaries.add(relative)
    recorded_binaries = {name for name in checked if Path(name).suffix in {".dll", ".exe"}}
    require(recorded_binaries == actual_binaries,
            "SDK DLL/EXE enumeration differs from the complete manifest")
    for extraction in value["extractions"]:
        # Preparation records log basenames relative to its evidence directory.
        log = inside(manifest_path.parent, extraction["log"])
        regular_file(log)
        require(sha256(log) == extraction.get("log_sha256"), "SDK extraction log changed")
    return sdk, {
        "manifest_path": str(manifest_path), "manifest_sha256": sha256(manifest_path),
        "version": SDK_VERSION, "root": str(sdk), "installers": value["installers"],
        "files": checked, "preparation_probe": value["probe"],
        "binary_coverage": value["binary_coverage"],
        "coverage_scope": "All recursive SDK DLL/EXE files plus manifest-listed headers/libraries",
    }


def inspect_build(build: Path) -> dict:
    cache = build / "CMakeCache.txt"
    regular_file(cache)
    require(re.search(r"^CAPTURE_ENABLE_CAMERA_WORKER:BOOL=ON\s*$",
                      cache.read_text(encoding="utf-8"), re.M) is not None,
            "The actual build did not enable the camera worker")
    binaries = {}
    for layout, relative in LAYOUTS.items():
        folder = inside(build, relative)
        records = {}
        for name in ("capture_worker_camera.exe", *DLL_NAMES):
            path = inside(build, folder / name)
            records[name] = pe_identity(path)
            require(records[name]["is_dll"] == name.endswith(".dll"), "PE file kind differs")
        require("libprotobuf.dll" in records["capture_worker_camera.exe"]["direct_imports"],
                "Camera worker does not directly import the withheld protobuf DLL")
        binaries[layout] = records
    original = binaries["original"]
    for layout in ("plugin", "legacy"):
        for name, record in original.items():
            require((binaries[layout][name]["bytes"], binaries[layout][name]["sha256"]) ==
                    (record["bytes"], record["sha256"]),
                    f"Packaged {layout}/{name} differs from original build")
    plugin = inside(build, LAYOUTS["plugin"] / "plugin.json")
    regular_file(plugin)
    require(plugin.read_bytes() == (ROOT / "plugins/camera_gstreamer/plugin.json").read_bytes(),
            "Packaged plugin manifest differs from source")
    return {
        "build": str(build), "cache_sha256": sha256(cache), "layouts": binaries,
        "test_executable": pe_identity(inside(build, "tests/cpp/capture_core_tests.exe")),
        "daemon_executable": pe_identity(inside(build, "daemon/capture_daemon.exe")),
        "plugin_manifest": {"path": str(plugin), "sha256": sha256(plugin)},
    }


@contextmanager
def inherited_error_mode():
    """Avoid interactive Windows loader dialogs, preserving the caller's mode."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetErrorMode.argtypes = []
    kernel.GetErrorMode.restype = ctypes.c_uint
    kernel.SetErrorMode.argtypes = [ctypes.c_uint]
    kernel.SetErrorMode.restype = ctypes.c_uint
    previous = kernel.GetErrorMode()
    kernel.SetErrorMode(previous | 0x0001 | 0x0002)
    try:
        yield
    finally:
        kernel.SetErrorMode(previous)


def execution_env(sdk: Path, directory: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(sdk / "bin")
    env["GSTREAMER_1_0_ROOT_MSVC_X86_64"] = str(sdk)
    for name in ("CAPTURE_CAMERA_FAKE", "CAPTURE_CAMERA_WORKER_EXE",
                 "CAPTURE_TEST_CAMERA_WORKER_EXE",
                 "GST_PLUGIN_PATH", "GST_PLUGIN_PATH_1_0", "GST_PLUGIN_SYSTEM_PATH",
                 "GST_PLUGIN_SYSTEM_PATH_1_0", "GST_REGISTRY", "GST_REGISTRY_1_0"):
        env.pop(name, None)
    temporary = directory / "temporary"
    temporary.mkdir()
    env["TMP"] = env["TEMP"] = str(temporary)
    env["GST_REGISTRY_1_0"] = str(directory / "gstreamer-registry.bin")
    env["CAPTURE_CAMERA_FAKE"] = "1"
    return env


def run_layout(name: str, binaries: dict, sdk: Path, out: Path) -> dict:
    directory = out / name
    directory.mkdir()
    cwd = directory / "cwd"
    cwd.mkdir()
    env = execution_env(sdk, directory)
    worker = binaries["layouts"][name]["capture_worker_camera.exe"]["path"]
    if name != "original":
        env["CAPTURE_TEST_CAMERA_WORKER_EXE"] = worker
    xml = directory / "native.xml"
    argv = [binaries["test_executable"]["path"], ",".join(TEST_NAMES),
            "--reporter", "xml", "--out", str(xml), "--durations", "yes", "--order", "decl"]
    require(not any(cwd.iterdir()), "Native execution CWD must start empty")
    log = directory / "native.log"
    code = None
    with log.open("w", encoding="utf-8") as stream, inherited_error_mode():
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=180)
            code = result.returncode
        except subprocess.TimeoutExpired:
            stream.write("\nNative camera case group timed out.\n")
    result = evaluate_xml(xml, code)
    result.update({
        "layout": name, "worker": worker, "argv": argv, "cwd": str(cwd),
        "cwd_started_empty": True, "path": env["PATH"], "camera_fake": True,
        "test_selector": env.get("CAPTURE_TEST_CAMERA_WORKER_EXE"),
        "log": str(log), "log_sha256": sha256(log),
    })
    return result


def pipe_connection_observed(succeeded: bool, error: int) -> bool:
    """PIPE_NOWAIT success only starts listening; it does not mean connected.

    Microsoft documents ERROR_PIPE_CONNECTED as the connection observation.
    ERROR_NO_DATA also disqualifies this control: a prior client reached the pipe.
    """
    if succeeded or error == 536:  # available / ERROR_PIPE_LISTENING
        return False
    if error in (535, 232):  # ERROR_PIPE_CONNECTED / ERROR_NO_DATA
        return True
    raise OSError(error, "Unexpected negative-control pipe state")


def missing_dll_control(binaries: dict, sdk: Path, out: Path) -> dict:
    """Observe the actual plugin process failing before connecting to its pipe."""
    from ctypes import wintypes

    directory = out / "missing-plugin-dll"
    directory.mkdir()
    cwd = directory / "cwd"
    cwd.mkdir()
    env = execution_env(sdk, directory)
    worker = Path(binaries["layouts"]["plugin"]["capture_worker_camera.exe"]["path"])
    dll = worker.parent / "libprotobuf.dll"
    expected_hash = binaries["layouts"]["plugin"]["libprotobuf.dll"]["sha256"]
    backup = dll.with_name(dll.name + ".withheld-" + uuid.uuid4().hex)
    require(not backup.exists(), "Withheld-DLL backup already exists")
    require(not (sdk / "bin/libprotobuf.dll").exists(), "SDK PATH would mask missing plugin DLL")
    system = Path(os.environ["SystemRoot"])
    require(not (system / "System32/libprotobuf.dll").exists() and
            not (system / "libprotobuf.dll").exists(), "System DLL search would mask the control")
    pipe_name = "\\\\.\\pipe\\capturesuite-camera-ci-" + uuid.uuid4().hex
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    ]
    kernel.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel.ConnectNamedPipe.restype = wintypes.BOOL
    kernel.PeekNamedPipe.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel.PeekNamedPipe.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # PIPE_NOWAIT keeps ConnectNamedPipe nonblocking; this is a negative probe,
    # not the production protocol implementation.
    handle = kernel.CreateNamedPipeW(pipe_name, 0x00000003 | 0x00080000,
                                    0x00000001, 1, 65536, 65536, 0, None)
    require(handle not in (None, ctypes.c_void_p(-1).value), "Could not create control pipe")
    result = {
        "accepted": False, "worker": str(worker), "withheld": str(dll),
        "withheld_sha256": expected_hash, "cwd": str(cwd), "path": env["PATH"],
        "process_exit": None, "windows_status": None, "pipe_connected": False,
        "pipe_bytes_available": 0, "restored": False, "problems": [],
        "scope": "Actual direct-import loader refusal before Hello; no fake binary",
    }
    process = None
    log = directory / "worker.log"
    moved = False

    def observe_pipe() -> None:
        if not result["pipe_connected"]:
            connected = bool(kernel.ConnectNamedPipe(handle, None))
            error = ctypes.get_last_error() if not connected else 0
            result["pipe_connected"] = pipe_connection_observed(connected, error)
        if result["pipe_connected"]:
            available = wintypes.DWORD()
            require(bool(kernel.PeekNamedPipe(handle, None, 0, None,
                                              ctypes.byref(available), None)),
                    "Connected control pipe could not be observed")
            result["pipe_bytes_available"] = max(result["pipe_bytes_available"], available.value)

    try:
        require(not any(cwd.iterdir()), "Negative execution CWD must start empty")
        require(sha256(dll) == expected_hash, "Plugin DLL changed before withholding")
        dll.rename(backup)
        moved = True
        argv = [str(worker), "--pipe", pipe_name, "--worker-id", "camera-ci-negative",
                "--plugin", "camera.gstreamer"]
        result["argv"] = argv
        with log.open("w", encoding="utf-8") as stream, inherited_error_mode():
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, creationflags=0x08000000)
            deadline = time.monotonic() + 15
            while process.poll() is None and time.monotonic() < deadline:
                observe_pipe()
                if result["pipe_connected"]:
                    break
                time.sleep(0.02)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
                result["problems"].append("Withheld-DLL worker connected or did not exit promptly")
            observe_pipe()
            result["process_exit"] = process.returncode
            result["windows_status"] = process.returncode & 0xFFFFFFFF
            if result["windows_status"] != DLL_NOT_FOUND:
                result["problems"].append(
                    "Worker did not exit with STATUS_DLL_NOT_FOUND (0xC0000135)")
            if result["pipe_connected"] or result["pipe_bytes_available"]:
                result["problems"].append(
                    "Worker reached the pipe before the expected loader refusal")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["problems"].append(f"Missing-DLL control failed: {exc}")
    finally:
        try:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            result["problems"].append(f"Control-process cleanup failed: {exc}")
        finally:
            kernel.CloseHandle(handle)
            try:
                if moved:
                    backup.rename(dll)
                result["restored"] = (dll.is_file() and sha256(dll) == expected_hash
                                      and not backup.exists())
            except OSError as exc:
                result["problems"].append(f"Plugin-DLL restoration failed: {exc}")
            if not result["restored"]:
                result["problems"].append("The plugin DLL was not restored exactly")
    if log.exists():
        result["log"] = str(log)
        result["log_sha256"] = sha256(log)
    result["accepted"] = not result["problems"] and result["restored"]
    (directory / "receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--sdk-manifest", required=True)
    args = parser.parse_args()
    out = ROOT / "build/evidence" / (
        "camera-native-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "capturesuite.camera-native-receipt.v1", "accepted": False,
        "created_at": datetime.now(UTC).isoformat(), "run_directory": str(out),
        "test_scope": list(TEST_NAMES), "layouts": [], "negative_control": None,
        "source_unchanged": False, "binaries_unchanged": False,
        "sdk_manifest_files_unchanged": False,
        "github": github_context(), "problems": [],
        "limits": [
            "Native GStreamer synthetic videotestsrc and worker protocol/storage qualification.",
            "Explicit packaged executable selection does not qualify daemon auto-resolution.",
            "No physical camera, driver, real-device capture, deployment or release claim.",
            "Source snapshots bind test-time bytes; hosted fresh-build logs establish compilation.",
        ],
    }
    before = None
    binaries = None
    sdk_record = None
    started = time.monotonic()
    try:
        require(sys.platform == "win32", "Actual camera qualification requires Windows")
        build = inside(ROOT, args.build_dir)
        manifest = inside(ROOT, args.sdk_manifest)
        before = source_snapshot(ROOT)
        (out / "source-manifest.json").write_text(json.dumps(before, indent=2) + "\n",
                                                 encoding="utf-8")
        sdk, sdk_record = inspect_sdk(manifest)
        binaries = inspect_build(build)
        (out / "binary-manifest.json").write_text(json.dumps(binaries, indent=2) + "\n",
                                                 encoding="utf-8")
        probe_dir = out / "sdk-probe"
        probe_dir.mkdir()
        probe_env = execution_env(sdk, probe_dir)
        probe = subprocess.run([str(sdk / "bin/gst-inspect-1.0.exe"), "--version"],
                               cwd=probe_dir, env=probe_env, text=True, encoding="utf-8",
                               errors="replace", stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=30)
        require(probe.returncode == 0 and
                f"GStreamer {SDK_VERSION}" in (line.strip() for line in probe.stdout.splitlines()),
                "Actual SDK version probe did not confirm GStreamer 1.24.13")
        sdk_record["actual_probe"] = {
            "argv": probe.args, "exit_code": probe.returncode, "output": probe.stdout,
            "executable": pe_identity(sdk / "bin/gst-inspect-1.0.exe"),
        }
        report["sdk"] = sdk_record
        for layout in ("original", "legacy"):
            result = run_layout(layout, binaries, sdk, out)
            report["layouts"].append(result)
            report["problems"].extend(f"{layout}: {problem}" for problem in result["problems"])
        report["negative_control"] = missing_dll_control(binaries, sdk, out)
        report["problems"].extend(report["negative_control"]["problems"])
        require(report["negative_control"]["restored"],
                "Plugin DLL was not restored; positive run held")
        # The full plugin group is the positive restored-DLL control, so no
        # identical extra camera group is needed solely for restoration.
        result = run_layout("plugin", binaries, sdk, out)
        report["layouts"].append(result)
        report["problems"].extend(f"plugin: {problem}" for problem in result["problems"])
        report["binaries_unchanged"] = binaries == inspect_build(build)
        _, sdk_after = inspect_sdk(manifest)
        sdk_before = {key: value for key, value in sdk_record.items() if key != "actual_probe"}
        report["sdk_manifest_files_unchanged"] = sdk_before == sdk_after
        require(report["binaries_unchanged"], "Native binaries changed during qualification")
        require(report["sdk_manifest_files_unchanged"],
                "SDK evidence or required files changed during qualification")
    except (OSError, ValueError, KeyError, TypeError, UnicodeError,
            subprocess.SubprocessError, struct.error) as exc:
        report["problems"].append(f"Camera qualification failed: {type(exc).__name__}: {exc}")
    finally:
        if before is not None:
            try:
                after = source_snapshot(ROOT)
                report["source_commit"] = before["commit"]
                report["source_worktree_dirty"] = before["worktree_dirty"]
                report["source_tree_sha256"] = before["tree_sha256"]
                report["source_unchanged"] = before == after
                if not report["source_unchanged"]:
                    report["problems"].append("Source changed during camera qualification")
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                report["problems"].append(f"Source readback failed: {exc}")
    report["seconds"] = time.monotonic() - started
    report["accepted"] = (
        not report["problems"] and report["source_unchanged"] and report["binaries_unchanged"]
        and report["sdk_manifest_files_unchanged"] and len(report["layouts"]) == 3
        and all(item["accepted"] for item in report["layouts"])
        and bool(report["negative_control"] and report["negative_control"]["accepted"])
    )
    (out / "receipt.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
