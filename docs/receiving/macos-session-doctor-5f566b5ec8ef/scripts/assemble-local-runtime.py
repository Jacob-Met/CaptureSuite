# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import datetime, hashlib, json, os, re, shutil, subprocess

ROOT = Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
ORIGINAL = ROOT / "build/tools/session_doctor/session_doctor"
DESTINATION = ROOT / "receiver/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
EXPECTED_BINARY = "4bb8872c854d0c344150c806d55674b4d0b6743355982552b6b494f785a19ce3"
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
LOAD_COMMANDS = {"LC_LOAD_DYLIB", "LC_LOAD_WEAK_DYLIB", "LC_REEXPORT_DYLIB", "LC_LOAD_UPWARD_DYLIB"}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def metadata(path):
    result = subprocess.run(["/usr/bin/otool", "-arch", "arm64", "-l", str(path)], text=True, capture_output=True, check=True)
    command = None
    loads, rpaths, identity = [], [], None
    for line in result.stdout.splitlines():
        value = line.strip()
        if value.startswith("cmd "):
            command = value[4:]
        elif command in LOAD_COMMANDS and value.startswith("name "):
            loads.append(re.fullmatch(r"name (.+) \(offset \d+\)", value).group(1))
        elif command == "LC_ID_DYLIB" and value.startswith("name "):
            identity = re.fullmatch(r"name (.+) \(offset \d+\)", value).group(1)
        elif command == "LC_RPATH" and value.startswith("path "):
            rpaths.append(re.fullmatch(r"path (.+) \(offset \d+\)", value).group(1))
    return {"loads": loads, "rpaths": rpaths, "identity": identity}

assert digest(ORIGINAL) == EXPECTED_BINARY
assert not DESTINATION.exists()
nodes, queue, names = {}, [ORIGINAL], {}
while queue:
    path = queue.pop(0).resolve(strict=True)
    if str(path) in nodes:
        continue
    info = metadata(path)
    info.update({"origin": str(path), "size": path.stat().st_size, "sha256": digest(path)})
    nodes[str(path)] = info
    for dependency in info["loads"]:
        if dependency.startswith(SYSTEM_PREFIXES):
            continue
        if not dependency.startswith("/opt/homebrew/"):
            raise RuntimeError(f"Unrecognized non-system dependency: {dependency}")
        resolved = Path(dependency).resolve(strict=True)
        if not str(resolved).startswith("/opt/homebrew/Cellar/") or not resolved.is_file():
            raise RuntimeError(f"Dependency is outside the admitted installed package tree: {resolved}")
        previous = names.setdefault(resolved.name, resolved)
        if previous != resolved:
            raise RuntimeError(f"Dependency basename collision: {previous} / {resolved}")
        queue.append(resolved)

DESTINATION.mkdir()
(DESTINATION / "bin").mkdir()
(DESTINATION / "lib").mkdir()
receipt = {
    "schema": "capturesuite.canonical-macos-runtime-package/1",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "canonical_source": "d43bdea867d6198a707a5f55e29216c76054517e",
    "native_source": "6a1a32e6240dc89892f340f241b03ef25a8ac8fc",
    "package": str(DESTINATION),
    "original_binary_sha256": EXPECTED_BINARY,
    "source_libraries": list(nodes.values()),
    "mutations": [],
}
log_path = ROOT / "evidence/runtime-package-commands.log"
with log_path.open("w") as log:
    copied = {}
    for source, info in nodes.items():
        source_path = Path(source)
        target = DESTINATION / ("bin/session_doctor" if source_path == ORIGINAL.resolve() else "lib/" + source_path.name)
        shutil.copy2(source_path, target)
        target.chmod(0o755)
        assert digest(target) == info["sha256"]
        copied[source] = target
    for source, target in copied.items():
        info = nodes[source]
        args = ["/usr/bin/install_name_tool"]
        if info["identity"] is not None:
            args.extend(["-id", "@rpath/" + target.name])
        changes = []
        for old in info["loads"]:
            if old.startswith(SYSTEM_PREFIXES):
                continue
            source_dep = Path(old).resolve(strict=True)
            new = ("@executable_path/../lib/" if target.parent.name == "bin" else "@loader_path/") + source_dep.name
            args.extend(["-change", old, new])
            changes.append({"old": old, "new": new})
        for old in info["rpaths"]:
            args.extend(["-delete_rpath", old])
        if len(args) > 1:
            args.append(str(target))
            log.write(json.dumps(args) + "\n")
            log.flush()
            subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True)
        receipt["mutations"].append({"path": str(target.relative_to(DESTINATION)), "loads": changes, "removed_rpaths": info["rpaths"]})
    # Local development signatures cover the copied, rewritten Mach-O bytes.
    # No source/system binary or trust setting is modified.
    for target in copied.values():
        args = ["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none", str(target)]
        log.write(json.dumps(args) + "\n")
        log.flush()
        subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(target)], stdout=log, stderr=subprocess.STDOUT, check=True)

receipt["files"] = []
for source, target in copied.items():
    info = metadata(target)
    for dependency in info["loads"]:
        if dependency.startswith(SYSTEM_PREFIXES):
            continue
        if dependency.startswith("@executable_path/"):
            resolved = (DESTINATION / "bin" / dependency.removeprefix("@executable_path/")).resolve(strict=True)
        elif dependency.startswith("@loader_path/"):
            resolved = (target.parent / dependency.removeprefix("@loader_path/")).resolve(strict=True)
        else:
            raise RuntimeError(f"Unrelocated dependency remains: {dependency}")
        assert resolved.is_relative_to(DESTINATION) and resolved.is_file()
    assert not info["rpaths"]
    assert digest(Path(source)) == nodes[source]["sha256"], source
    receipt["files"].append({"path": str(target.relative_to(DESTINATION)), "size": target.stat().st_size, "sha256": digest(target), "mode": "100755", "load_commands": info})
receipt["original_inputs_unchanged"] = True
receipt["commands_log_sha256"] = digest(log_path)
manifest = ROOT / "evidence/runtime-package.json"
manifest.write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"package": str(DESTINATION), "files": len(receipt["files"]), "bytes": sum(f["size"] for f in receipt["files"]), "binary_sha256": next(f["sha256"] for f in receipt["files"] if f["path"] == "bin/session_doctor"), "receipt_sha256": digest(manifest), "original_inputs_unchanged": True}, indent=2))
