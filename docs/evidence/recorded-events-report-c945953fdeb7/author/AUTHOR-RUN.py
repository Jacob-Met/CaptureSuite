# SPDX-License-Identifier: GPL-3.0-only
"""One bounded physical source preparation and focused report-consumer run.

Invoked only after the independent contract is frozen. All inputs arrive as
an exact JSON payload; this program does not fetch code or install anything.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import resource
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

if sys.stdin.isatty():
    import termios
    attrs = termios.tcgetattr(sys.stdin.fileno())
    attrs[3] &= ~(termios.ECHO | termios.ICANON)
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attrs)


EXPECTED_PYTHON = (
    "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12"
)
EXPECTED_RUNTIME_SHA = "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"
FLOOR_DISK = 128 * 1024 * 1024
FLOOR_MEMORY = 2 * 1024 * 1024 * 1024
OWNED_CAP = 2 * 1024 * 1024


def utc() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard(root: Path) -> dict:
    executable = Path(sys.executable).resolve()
    if str(executable) != EXPECTED_PYTHON or sys.version_info[:2] != (3, 12):
        raise RuntimeError("supported, retained Python runtime is not selected")
    runtime_sha = sha(executable.read_bytes())
    if runtime_sha != EXPECTED_RUNTIME_SHA:
        raise RuntimeError("retained Python runtime changed")
    space = os.statvfs(root.parent)
    free = space.f_bavail * space.f_frsize
    memory = {
        line.split(":", 1)[0]: line.split(":", 1)[1]
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    available = int(memory["MemAvailable"].split()[0]) * 1024
    value = {
        "time_utc": utc(), "uid": os.getuid(), "gid": os.getgid(),
        "python": str(executable), "python_version": sys.version,
        "python_bytes": executable.stat().st_size, "python_sha256": runtime_sha,
        "free_bytes": free, "mem_available_bytes": available,
        "disk_floor_bytes": FLOOR_DISK, "memory_floor_bytes": FLOOR_MEMORY,
        "owned_cap_bytes": OWNED_CAP,
        "mount_namespace": os.readlink("/proc/self/ns/mnt"),
    }
    if free < FLOOR_DISK or available < FLOOR_MEMORY:
        raise RuntimeError("native admission refused: " + json.dumps(value))
    return value


def inspect(path: Path, base: Path) -> dict:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise RuntimeError(f"unexpected nonregular owned file: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": len(data), "sha256": sha(data),
        "git_blob": hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        ).hexdigest(),
        "mode": format(stat.S_IMODE(value.st_mode), "04o"),
        "mtime_ns": str(value.st_mtime_ns),
        "allocated_bytes": value.st_blocks * 512,
    }


def inventory(base: Path) -> list[dict]:
    return [inspect(p, base) for p in sorted(base.rglob("*")) if p.is_file()]


def write_new(path: Path, data: bytes, mode: int = 0o444) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if stream.write(data) != len(data):
            raise OSError("short owned evidence write")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(mode)


def limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (OWNED_CAP,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (20, 22))


def main() -> int:
    payload = json.loads(sys.argv[1])
    root = Path(payload["root"])
    if (
        root.parent != Path("/dev")
        or not root.name.startswith("capturesuite-recorded-events-c945953fdeb7-")
        or os.path.lexists(root)
    ):
        raise RuntimeError("exclusive declared /dev target is not available")
    before_admission = guard(root)
    files = payload["files"]
    names = set()
    total = 0
    for item in files:
        rel = Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts or item["path"] in names:
            raise RuntimeError("unsafe or duplicate declared input path")
        names.add(item["path"])
        data = item["content"].encode("utf-8")
        total += len(data)
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise RuntimeError("input digest mismatch: " + item["path"])
    if total + 512 * 1024 > OWNED_CAP:
        raise RuntimeError("declared source plus execution reserve exceeds owned cap")
    contract = next(f for f in files if f["path"] == "RECEIVING-CONTRACT.md")
    if contract["sha256"] != payload["contract_sha256"]:
        raise RuntimeError("independent contract digest is not bound")

    os.umask(0o077)
    root.mkdir(mode=0o700)
    for item in files:
        write_new(root / item["path"], item["content"].encode("utf-8"))
    (root / "tmp").mkdir(mode=0o700)
    prepared = inventory(root)
    if sum(f["bytes"] for f in prepared) > OWNED_CAP:
        raise RuntimeError("actual prepared source exceeds owned cap")
    preparation = {
        "format": "capturesuite.recorded-events.source-preparation.v1",
        "time_utc": utc(), "root": str(root), "admission": before_admission,
        "contract_sha256": payload["contract_sha256"],
        "original_capsule": payload["original_capsule"],
        "orchestration_source": payload["orchestration_source"],
        "transport": "one outer execution; no cross-call /dev retention claim",
        "files": prepared, "candidate_execution_before_this_record": False,
    }
    write_new(
        root / "SOURCE-PREPARATION.json",
        (json.dumps(preparation, ensure_ascii=True, indent=2) + "\n").encode("utf-8"),
    )
    frozen_inputs = inventory(root)
    execution_admission = guard(root)
    code = (
        "import importlib.util,pathlib,sys,unittest;"
        "r=pathlib.Path(sys.argv[1]);"
        "sys.path[:0]=[str(r),str(r/'libs/python/capture_session')];"
        "p=r/'tests/test_recorded_events_html.py';"
        "s=importlib.util.spec_from_file_location('test_recorded_events_html',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "suite=unittest.defaultTestLoader.loadTestsFromModule(m);"
        "assert suite.countTestCases()==8,suite.countTestCases();"
        "result=unittest.TextTestRunner(verbosity=2).run(suite);"
        "raise SystemExit(0 if result.wasSuccessful() else 1)"
    )
    command = [sys.executable, "-I", "-B", "-c", code, str(root)]
    environment = os.environ.copy()
    environment["TMPDIR"] = str(root / "tmp")
    started = utc()
    monotonic = time.monotonic()
    process = subprocess.Popen(
        command, cwd="/tmp", env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True, preexec_fn=limits,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    elapsed = time.monotonic() - monotonic
    after_inputs = [inspect(root / item["path"], root) for item in frozen_inputs]
    unchanged = after_inputs == frozen_inputs
    try:
        os.killpg(process.pid, 0)
        group_absent = False
    except ProcessLookupError:
        group_absent = True
    write_new(root / "unit.stdout.txt", stdout)
    write_new(root / "unit.stderr.txt", stderr)
    receipt = {
        "format": "capturesuite.recorded-events.author-receipt.v1",
        "started_at": started, "finished_at": utc(), "controller_pid": os.getpid(),
        "child_pid": process.pid, "child_pgid": process.pid, "command": command,
        "cwd": "/tmp", "tmpdir": environment["TMPDIR"],
        "execution_admission": execution_admission,
        "elapsed_seconds": elapsed, "exit_code": process.returncode,
        "timed_out": timed_out, "process_group_absent": group_absent,
        "unit_suite": "tests/test_recorded_events_html.py",
        "expected_cases": 8, "source_before": frozen_inputs, "source_after": after_inputs,
        "all_frozen_inputs_unchanged": unchanged,
        "stdout": inspect(root / "unit.stdout.txt", root),
        "stderr": inspect(root / "unit.stderr.txt", root),
        "gates_not_executed": ["Ruff (absent)", "pytest (absent)", "Windows/full suite"],
        "limitations": (
            "Supported Linux component execution with real files and normal package imports. "
            "No Qt, hardware, capture daemon or Mac application qualification. "
            "The independent physical-report/browser receiving remains separate."
        ),
    }
    write_new(
        root / "AUTHOR-RECEIPT.json",
        (json.dumps(receipt, ensure_ascii=True, indent=2) + "\n").encode("utf-8"),
    )
    final = inventory(root)
    own_bytes = sum(f["bytes"] for f in final)
    accepted = (
        process.returncode == 0 and not timed_out and group_absent
        and unchanged and own_bytes <= OWNED_CAP
    )
    print(json.dumps(
        {
            "accepted": accepted, "root": str(root), "receipt": str(root / "AUTHOR-RECEIPT.json"),
            "child_pid": process.pid, "exit_code": process.returncode,
            "timed_out": timed_out, "process_group_absent": group_absent,
            "all_frozen_inputs_unchanged": unchanged,
            "owned_file_bytes": own_bytes, "owned_files": len(final),
            "elapsed_seconds": elapsed,
            "controller_pid": os.getpid(),
            "custody_ready": True,
            "artifacts": [
                inspect(root / name, root)
                for name in (
                    "SOURCE-PREPARATION.json", "unit.stdout.txt",
                    "unit.stderr.txt", "AUTHOR-RECEIPT.json"
                )
            ],
        },
        ensure_ascii=True,
    ), flush=True)
    # Reuse the established ordinary-driver TTY lifetime pattern. Export is
    # read-only and confined to these four complete artifacts; the source is
    # never re-executed. Keep this invocation alive until every byte is received.
    import base64
    artifact_names = {
        "SOURCE-PREPARATION.json", "unit.stdout.txt",
        "unit.stderr.txt", "AUTHOR-RECEIPT.json",
    }
    signal.alarm(300)
    for raw in sys.stdin:
        request = json.loads(raw)
        if request.get("action") == "read":
            name = request["path"]
            if name not in artifact_names:
                raise ValueError("undeclared artifact")
            offset = request["offset"]
            limit = request["limit"]
            if not isinstance(offset, int) or offset < 0 or not 1 <= limit <= 4096:
                raise ValueError("invalid bounded artifact read")
            data = (root / name).read_bytes()
            part = data[offset:offset + limit]
            print(json.dumps({
                "artifact": name, "offset": offset,
                "total_bytes": len(data), "bytes": len(part),
                "sha256": sha(part),
                "base64": base64.b64encode(part).decode("ascii"),
                "full_identity": inspect(root / name, root),
            }), flush=True)
        elif request.get("action") == "exit":
            unchanged_at_release = inventory(root) == final
            print(json.dumps({
                "custody_released": True, "time_utc": utc(),
                "controller_pid": os.getpid(),
                "all_files_unchanged_since_run": unchanged_at_release,
                "actual_child_wait_exit": process.returncode,
                "child_group_absent_at_run_closure": group_absent,
                "owned_files": len(final), "owned_bytes": own_bytes,
                "source_reexecuted": False,
            }), flush=True)
            signal.alarm(0)
            return 0 if accepted and unchanged_at_release else 1
        else:
            raise ValueError("unknown custody request")
    raise RuntimeError("custody input closed without explicit byte-receipt release")


if __name__ == "__main__":
    raise SystemExit(main())
