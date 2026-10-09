#!/usr/bin/env python3
"""One live private custody process for CaptureSuite's three physical CLI calls."""
import sys, os, pathlib, json, hashlib, stat, time, datetime, uuid, termios
import io, base64, zipfile, traceback, runpy

attrs = termios.tcgetattr(sys.stdin.fileno())
attrs[3] &= ~(termios.ECHO | termios.ICANON)
attrs[6][termios.VMIN] = 1
attrs[6][termios.VTIME] = 0
termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attrs)
os.umask(0o077)
ROOT = None
STAGED = False
RUN_CALLED = False
RESULT = None
EXPORT = None
EXPORT_MANIFEST = None
STAGED_MANIFEST = None
CAP = 2 * 1024**2
MAX_FILE = 1024**2
MEM_FLOOR = 2 * 1024**3
FREE_FLOOR = 128 * 1024**2

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}

def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)

def all_files():
    if ROOT is None:
        return []
    found = []
    for base, dirs, names in os.walk(ROOT):
        for name in dirs + names:
            path = pathlib.Path(base) / name
            if path.is_symlink():
                raise RuntimeError("Owned symlink refused")
        found.extend(pathlib.Path(base) / name for name in names)
    return sorted(found)

def inventory():
    result = []
    for path in all_files():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
            raise RuntimeError("Nonregular or oversized owned file")
        result.append({"path": path.relative_to(ROOT).as_posix(), **pin(path.read_bytes()),
                       "mode": format(stat.S_IMODE(info.st_mode), "04o"),
                       "mtime_ns": str(info.st_mtime_ns), "allocated_bytes": info.st_blocks * 512})
    return result

def guard(label):
    memory = None
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            memory = int(line.split()[1]) * 1024
    vfs = os.statvfs("/dev")
    info = [p.lstat() for p in all_files()]
    obs = {"label": label, "time_utc": now(), "free_bytes": vfs.f_bavail * vfs.f_frsize,
           "mem_available_bytes": memory, "owned_bytes": sum(x.st_size for x in info),
           "owned_allocated_bytes": sum(x.st_blocks * 512 for x in info),
           "owned_files": len(info), "disk_floor_bytes": FREE_FLOOR,
           "memory_floor_bytes": MEM_FLOOR, "owned_cap_bytes": CAP,
           "per_file_cap_bytes": MAX_FILE}
    obs["admitted"] = (memory is not None and memory >= MEM_FLOOR
                       and obs["free_bytes"] >= FREE_FLOOR
                       and max(obs["owned_bytes"], obs["owned_allocated_bytes"]) <= CAP
                       and all(x.st_size <= MAX_FILE for x in info))
    if not obs["admitted"]:
        raise RuntimeError("Frozen admission refused: " + json.dumps(obs))
    return obs

def safe_relative(text):
    rel = pathlib.PurePosixPath(text)
    if rel.is_absolute() or not rel.parts or str(rel) != text or any(x in (".", "..") for x in rel.parts):
        raise ValueError("Unsafe receiving-relative path")
    return rel

def write_new(relative, data):
    path = ROOT / safe_relative(relative)
    if len(data) > MAX_FILE:
        raise RuntimeError("Owned file cap exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if stream.write(data) != len(data):
            raise RuntimeError("Short owned write")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(path.read_bytes())

emit({"ready": True, "controller_pid": os.getpid(), "python": sys.executable,
      "time_utc": now(), "native_root": None,
      "scope": "No source staging or product call until exact prepare/run commands."})

for line in sys.stdin:
    try:
        command = json.loads(line)
        op = command.get("op")
        if op == "prepare":
            if ROOT is not None:
                raise RuntimeError("Preparation is exclusive and cannot be repeated")
            if sys.version_info[:2] != (3, 12):
                raise RuntimeError("Supported Python 3.12 required")
            runtime_path = pathlib.Path(sys.executable).resolve()
            runtime_pin = pin(runtime_path.read_bytes())
            if runtime_pin["sha256"] != command["runtime_sha256"]:
                raise RuntimeError("Pinned runtime hash mismatch")
            entries = command["files"]
            paths = set()
            total = 0
            for item in entries:
                safe_relative(item["path"])
                if item["path"] in paths:
                    raise RuntimeError("Duplicate offered path")
                paths.add(item["path"])
                data = item["content"].encode("utf-8")
                if len(data) > MAX_FILE or pin(data) != item["pin"]:
                    raise RuntimeError("Offered byte identity mismatch: " + item["path"])
                total += len(data)
                if item["path"] in ("observer/linux_receiver.py", "observer/custodian.py"):
                    compile(data, item["path"], "exec")
            if total > CAP // 2:
                raise RuntimeError("Initial files leave insufficient bounded evidence capacity")
            admission = guard("before-exclusive-stage")
            ROOT = pathlib.Path("/dev") / ("estate-c945953fdeb7-capture-receiver-" + uuid.uuid4().hex)
            ROOT.mkdir(mode=0o700)
            for dirname in ("source", "inputs", "frozen", "observer", "author-offer", "evidence", "exports", "foreign-cwd"):
                (ROOT / dirname).mkdir()
            for item in entries:
                actual = write_new(item["path"], item["content"].encode("utf-8"))
                if actual != item["pin"]:
                    raise RuntimeError("Native materialization mismatch: " + item["path"])
            STAGED_MANIFEST = inventory()
            preparation = {"schema": "capturesuite-independent-source-preparation-v1", "time_utc": now(),
                           "root": str(ROOT), "controller_pid": os.getpid(), "admission": admission,
                           "runtime": {"path": str(runtime_path), "version": sys.version, "uid": os.getuid(),
                                       "gid": os.getgid(), **runtime_pin},
                           "files": STAGED_MANIFEST,
                           "candidate_execution_before_record": False, "observer_syntax_compiled_without_execution": True,
                           "transport": "One live exec/TTY process; no cross-exec /dev persistence assumed.",
                           "after_stage_guard": guard("after-stage")}
            preparation_pin = write_new("evidence/SOURCE-PREPARATION.json",
                                        (json.dumps(preparation, ensure_ascii=False, indent=2) + "\n").encode())
            STAGED = True
            emit({"prepared": True, "root": str(ROOT), "controller_pid": os.getpid(),
                  "source_preparation": preparation_pin, "files": len(STAGED_MANIFEST),
                  "admission": admission, "after_stage": guard("after-preparation"),
                  "product_calls": 0})
        elif op == "run":
            if not STAGED or RUN_CALLED:
                raise RuntimeError("Only one receiving invocation is permitted")
            current = {x["path"]: x for x in inventory()}
            if any(current.get(item["path"]) != item for item in STAGED_MANIFEST):
                raise RuntimeError("Frozen files changed before execution")
            expected = next(x for x in STAGED_MANIFEST if x["path"] == "observer/linux_receiver.py")
            actual = pin((ROOT / expected["path"]).read_bytes())
            if actual != {k: expected[k] for k in ("bytes", "sha256", "git_blob")}:
                raise RuntimeError("Frozen receiver identity mismatch")
            guard("before-independent-three-call-receiver")
            RUN_CALLED = True
            module = runpy.run_path(str(ROOT / "observer/linux_receiver.py"), run_name="independent_capture_observer")
            RESULT = module["run"](ROOT)
            emit({"run_complete": True, **RESULT})
        elif op == "export":
            if RESULT is None or EXPORT is not None:
                raise RuntimeError("Export requires one completed receiver and is single-shot")
            admission = guard("before-byte-export")
            EXPORT_MANIFEST = inventory()
            memory = io.BytesIO()
            with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for item in EXPORT_MANIFEST:
                    data = (ROOT / item["path"]).read_bytes()
                    if pin(data) != {k: item[k] for k in ("bytes", "sha256", "git_blob")}:
                        raise RuntimeError("Export source identity changed")
                    info = zipfile.ZipInfo(item["path"], (2026, 10, 9, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | int(item["mode"], 8)) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
            zipped = memory.getvalue()
            EXPORT = base64.b64encode(zipped).decode("ascii") + "\n"
            emit({"export_ready": True, "carrier": pin(EXPORT.encode()), "zip": pin(zipped),
                  "members": EXPORT_MANIFEST, "admission": admission,
                  "native_carrier_file_created": False})
        elif op == "chunk":
            if EXPORT is None:
                raise RuntimeError("No byte export prepared")
            offset, length = command["offset"], command["length"]
            if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or not 0 < length <= 16000:
                raise RuntimeError("Invalid bounded carrier slice")
            emit({"offset": offset, "slice": EXPORT[offset:offset + length],
                  "total_characters": len(EXPORT)})
        elif op == "read":
            rel = str(safe_relative(command["path"]))
            path = ROOT / rel
            if not path.is_file():
                raise RuntimeError("Owned artifact is absent")
            data = path.read_bytes()
            if len(data) > MAX_FILE:
                raise RuntimeError("Owned read exceeds cap")
            emit({"path": rel, **pin(data), "content": data.decode("utf-8")})
        elif op == "stop-unexecuted":
            if RUN_CALLED:
                raise RuntimeError("Use full custody close after a receiving invocation")
            emit({"stopped_without_product_call": True, "time_utc": now(),
                  "root": str(ROOT) if ROOT else None, "controller_pid": os.getpid(),
                  "staged": STAGED, "owned_files_preserved": inventory()})
            sys.exit(1)
        elif op == "close":
            if EXPORT is None:
                raise RuntimeError("Exact byte custody must be exported before close")
            after = inventory()
            closed = {"schema": "capturesuite-independent-linux-native-closure-v1",
                      "time_utc": now(), "controller_pid": os.getpid(),
                      "files_unchanged_since_export": after == EXPORT_MANIFEST,
                      "all_staged_inputs_unchanged": all(
                          {x["path"]: x for x in after}.get(item["path"]) == item for item in STAGED_MANIFEST),
                      "all_cli_children_reaped": all(c["child_reaped_by_wait"] for c in RESULT["children"]),
                      "actual_cli_wait_exits": [c["wait_returncode"] for c in RESULT["children"]],
                      "linux_accepted": RESULT["linux_accepted"], "guard": guard("final-readonly-closure"),
                      "final_files": len(after), "final_file_bytes": sum(x["bytes"] for x in after),
                      "extra_candidate_calls": 0, "native_root_removed": False,
                      "scope": "Custodian ends after exact export; /dev lifetime is ephemeral, no retention/reboot guarantee."}
            emit(closed)
            sys.exit(0 if closed["linux_accepted"] and closed["files_unchanged_since_export"]
                     and closed["all_staged_inputs_unchanged"] and closed["all_cli_children_reaped"] else 1)
        else:
            raise RuntimeError("Unknown bounded custody operation")
    except Exception as error:
        emit({"custody_error": {"type": type(error).__name__, "message": str(error),
                               "traceback": traceback.format_exc()},
              "time_utc": now(), "root": str(ROOT) if ROOT else None,
              "staged": STAGED, "run_called": RUN_CALLED})
