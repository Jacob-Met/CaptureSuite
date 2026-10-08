# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import datetime, hashlib, json, os, re, resource, shutil, struct, subprocess, traceback

ROOT = Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
PACKAGE = ROOT / "receiver/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
WORK = ROOT / "receiving-process-controls"
RELOCATED = WORK / "Session Doctor 雪"
EXPECTED = "401f7ef7eb1212799c00ff7bdb22ac48a31bf6feb22a17b3a4fefcfc8e485772"
assert not WORK.exists()
WORK.mkdir()
shutil.copytree(PACKAGE, RELOCATED)
(WORK / "unrelated-working-directory").mkdir()
EXE = RELOCATED / "bin/session_doctor"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory(root):
    rows = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            rows[rel] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            rows[rel] = {"kind": "file", "size": path.stat().st_size, "sha256": digest(path)}
    return rows

env = {k:v for k,v in os.environ.items() if not k.startswith(("DYLD_", "LD_", "CAPTURE_", "MCAP_"))}
env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

calls = []
def run(label, args, diagnostic=False):
    current_env = dict(env)
    if diagnostic:
        current_env["DYLD_PRINT_LIBRARIES"] = "1"
    result = subprocess.run([str(EXE), *map(str,args)], cwd=WORK / "unrelated-working-directory",
                            env=current_env, text=True, capture_output=True, timeout=15, preexec_fn=no_core)
    row = {"label":label, "argv":[str(EXE), *map(str,args)], "exit":result.returncode,
           "stdout":result.stdout, "stderr":result.stderr}
    calls.append(row)
    return result

receipt = {"schema":"capturesuite.canonical-mac-receiver-process/1",
           "started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "binary_sha256":digest(EXE), "package":str(PACKAGE), "relocated":str(RELOCATED),
           "cases":[], "calls":calls, "qualification":"Private authored/copied synthetic fixtures only; no physical capture or existing installation invoked."}
initial_package = inventory(PACKAGE)
initial_source = json.loads((ROOT / "evidence/source-inputs.json").read_text())
failures = []

def check(name, operation):
    try:
        detail = operation()
        receipt["cases"].append({"name":name, "passed":True, "detail":detail})
    except Exception as error:
        receipt["cases"].append({"name":name, "passed":False, "error":repr(error), "traceback":traceback.format_exc()})
        failures.append(name)

def relocated_help():
    assert digest(EXE) == EXPECTED
    assert inventory(RELOCATED) == initial_package
    result = run("relocated-help-and-dynamic-loads", ["--help"], diagnostic=True)
    assert result.returncode == 0 and result.stdout.startswith("Usage: session_doctor")
    loaded = []
    for line in result.stderr.splitlines():
        match = re.search(r"(/.+)$", line)
        if match:
            loaded.append(match.group(1))
    non_system = [p for p in loaded if not p.startswith(("/usr/lib/", "/System/Library/"))]
    assert len(non_system) >= 87, non_system
    assert all(Path(p).is_relative_to(RELOCATED) for p in non_system), non_system
    assert "/opt/homebrew/" not in result.stderr and str(ROOT / "build") not in result.stderr
    return {"loaded_non_system_images":len(non_system), "non_system_images":non_system,
            "path":env["PATH"], "working_directory":str(WORK / "unrelated-working-directory")}

def usage_failure():
    result = run("no-arguments", [])
    assert result.returncode == 1 and result.stdout.startswith("Usage: session_doctor") and not result.stderr
    return {"exit":result.returncode}

def absent_failure():
    path = WORK / "missing.mmsession"
    result = run("missing-session", [path])
    assert result.returncode == 2 and not result.stdout and "recovery failed:" in result.stderr
    assert not path.exists()
    return {"exit":result.returncode, "directory_created":False}

def malformed_failure():
    path = WORK / "malformed.mmsession"
    path.mkdir()
    (path / "manifest.json").write_bytes(b"{malformed authored fixture\n")
    before = inventory(path)
    result = run("malformed-manifest", [path])
    assert result.returncode == 2 and not result.stdout and "manifest parse failed" in result.stderr
    assert inventory(path) == before
    return {"exit":result.returncode, "files_unchanged":True}

def finalized_preservation():
    path = WORK / "finalized copy 雪.mmsession"
    shutil.copytree(ROOT / "source/tests/fixtures/mini_session", path)
    before = inventory(path)
    result = run("finalized-copy", [path])
    assert result.returncode == 0 and "state=finalized recovered=false" in result.stdout and not result.stderr
    assert inventory(path) == before
    return {"files_unchanged":len(before), "manifest_sha256":digest(path / "manifest.json")}

def mcap_record(opcode, body):
    return bytes([opcode]) + struct.pack("<Q",len(body)) + body

def mcap_string(value):
    return struct.pack("<I",len(value)) + value

MAGIC = b"\x89MCAP0\r\n"
RECORDING = WORK / "authored recording 雪.mmsession"
UNSEALED_REL = Path("sources/sim.packet/streams/sim.numeric/segments/000000.mcap")
SEALED_REL = Path("sources/sim.packet/streams/sim.numeric/segments/000001.mcap")

def recover_authored():
    (RECORDING / UNSEALED_REL).parent.mkdir(parents=True)
    (RECORDING / "manifest.json").write_text(json.dumps({"sessionSchemaVersion":"1.0.0","sessionId":"canonical-mac-packet","state":"recording"})+"\n")
    (RECORDING / UNSEALED_REL).write_bytes(MAGIC + b"\x06")
    complete = (MAGIC + mcap_record(1, mcap_string(b"") + mcap_string(b"canonical Mac receiving"))
                + mcap_record(15, struct.pack("<I",0)) + mcap_record(2, struct.pack("<QQI",0,0,0)) + MAGIC)
    (RECORDING / SEALED_REL).write_bytes(complete)
    (RECORDING / "integrity.json").write_text(json.dumps({"sessionId":"canonical-mac-packet","sessionSchemaVersion":"1.0.0","files":[{"path":SEALED_REL.as_posix(),"status":"sealed"}]})+"\n")
    # The copied raw fixture is the target of an unrelated pre-existing old-style
    # temporary name. R3's actual writer must neither follow nor remove this link.
    link = RECORDING / "manifest.json.tmp"
    link.symlink_to(SEALED_REL)
    sealed_before = digest(RECORDING / SEALED_REL)
    result = run("authored-truncated-and-sealed", [RECORDING])
    assert result.returncode == 0 and "state=finalized_recovered recovered=true" in result.stdout and not result.stderr
    assert (RECORDING / UNSEALED_REL).read_bytes() == MAGIC
    assert digest(RECORDING / SEALED_REL) == sealed_before
    assert link.is_symlink() and os.readlink(link) == str(SEALED_REL)
    reports = list((RECORDING / "recovery").glob("report_*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["truncated"] == [UNSEALED_REL.as_posix()]
    assert SEALED_REL.as_posix() in report["trusted"]
    assert json.loads((RECORDING / "manifest.json").read_text())["state"] == "finalized_recovered"
    gaps = list((RECORDING / "sources").rglob("gaps.jsonl"))
    assert len(gaps) == 1 and json.loads(gaps[0].read_text())["note"] == "truncated_recovered"
    return {"unsealed_before_bytes":9,"unsealed_after_bytes":8,"sealed_bytes":len(complete),"sealed_sha256":sealed_before,
            "old_temporary_symlink_preserved":True, "report_sha256":digest(reports[0]), "gap_sha256":digest(gaps[0])}

def second_recovery():
    before = inventory(RECORDING)
    result = run("recovered-repeat", [RECORDING])
    assert result.returncode == 0 and "state=finalized_recovered recovered=false" in result.stdout and not result.stderr
    assert inventory(RECORDING) == before
    return {"all_entries_unchanged":len(before)}

def missing_library():
    library = RELOCATED / "lib/libblake3.0.dylib"
    held = WORK / "withheld-libblake3.0.dylib"
    original = digest(library)
    library.rename(held)
    try:
        result = run("withheld-local-library", ["--help"])
        assert result.returncode != 0 and not result.stdout
        assert "libblake3.0.dylib" in result.stderr and "Library not loaded" in result.stderr
    finally:
        held.rename(library)
    assert digest(library) == original
    restored = run("restored-local-library", ["--help"])
    assert restored.returncode == 0 and restored.stdout.startswith("Usage: session_doctor") and not restored.stderr
    assert inventory(RELOCATED) == initial_package
    return {"missing_exit":result.returncode,"restored_exit":restored.returncode,"all_package_bytes_restored":True}

for name, operation in [
    ("relocated-runtime-loads-only-local-and-system-images", relocated_help),
    ("no-argument-process-contract", usage_failure),
    ("missing-session-does-not-create-output", absent_failure),
    ("malformed-json-refuses-without-writing", malformed_failure),
    ("finalized-repository-fixture-byte-preservation", finalized_preservation),
    ("authored-tail-recovery-sealed-file-and-old-temp-preservation", recover_authored),
    ("second-recovery-preserves-every-fixture-entry", second_recovery),
    ("missing-local-dependency-refuses-and-exact-restoration-recovers", missing_library),
]:
    check(name, operation)

source_errors = []
for row in initial_source["files"]:
    path = ROOT / "source" / row["path"]
    if path.stat().st_size != row["size"] or digest(path) != row["sha256"]:
        source_errors.append(row["path"])
receipt["source_input_errors"] = source_errors
receipt["original_package_unchanged"] = inventory(PACKAGE) == initial_package
receipt["relocated_package_unchanged"] = inventory(RELOCATED) == initial_package
receipt["git_status"] = subprocess.check_output(["git","-C",str(ROOT / "source"),"status","--porcelain"],text=True)
receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt["failed_cases"] = failures
out = ROOT / "evidence/receiver-process-first.json"
out.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"cases":receipt["cases"],"source_input_errors":source_errors,"original_package_unchanged":receipt["original_package_unchanged"],"relocated_package_unchanged":receipt["relocated_package_unchanged"],"git_status":receipt["git_status"],"receipt_sha256":digest(out)},indent=2))
assert not failures and not source_errors and receipt["original_package_unchanged"] and receipt["relocated_package_unchanged"] and not receipt["git_status"]
