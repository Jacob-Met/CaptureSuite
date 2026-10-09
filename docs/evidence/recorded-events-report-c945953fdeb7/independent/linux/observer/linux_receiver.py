# Independent receiving under contract 7fd938b783feb56b3f7bbb29ae52d60146359600.
# No candidate import, optimizer, old suite or replacement reader is used here.
from __future__ import annotations
import datetime, hashlib, json, os, pathlib, re, resource, signal, stat
import subprocess, sys, time, traceback
from html.parser import HTMLParser

MIB = 1024 * 1024
CAP = 2 * MIB
DISK_FLOOR = 128 * MIB
MEM_FLOOR = 2 * 1024 * MIB
PYTHON_SHA = "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def body_pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}

def file_pin(root, path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MIB:
        raise RuntimeError("Nonregular or oversized owned file: " + str(path))
    result = {"path": path.relative_to(root).as_posix(), **body_pin(path.read_bytes()),
              "mode": format(stat.S_IMODE(info.st_mode), "04o"),
              "mtime_ns": str(info.st_mtime_ns), "allocated_bytes": info.st_blocks * 512}
    return result

def files(root):
    result = []
    for base, dirs, names in os.walk(root):
        for name in dirs + names:
            path = pathlib.Path(base) / name
            if path.is_symlink():
                raise RuntimeError("Unexpected owned symlink: " + str(path))
        result.extend(pathlib.Path(base) / name for name in names)
    return sorted(result)

def protected_inventory(root):
    paths = []
    for dirname in ("source", "inputs", "frozen", "observer", "author-offer"):
        paths.extend(files(root / dirname))
    return [file_pin(root, path) for path in sorted(paths)]

def write_new(root, relative, data):
    path = root / relative
    if len(data) > MIB:
        raise RuntimeError("Evidence file exceeds 1 MiB: " + relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if stream.write(data) != len(data):
            raise RuntimeError("Short owned evidence write")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    return file_pin(root, path)

def write_json(root, relative, value):
    return write_new(root, relative, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())

class GuardRefusal(RuntimeError):
    pass

def guard(root, label, observations):
    memory = {}
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key == "MemAvailable":
            memory[key] = int(value.split()[0]) * 1024
    vfs = os.statvfs(root)
    entries = [p.lstat() for p in files(root)]
    obs = {"label": label, "time_utc": now(), "free_bytes": vfs.f_bavail * vfs.f_frsize,
           "mem_available_bytes": memory["MemAvailable"],
           "owned_files": len(entries), "owned_bytes": sum(x.st_size for x in entries),
           "owned_allocated_bytes": sum(x.st_blocks * 512 for x in entries),
           "disk_floor_bytes": DISK_FLOOR, "memory_floor_bytes": MEM_FLOOR,
           "owned_cap_bytes": CAP, "per_file_stream_cap_bytes": MIB}
    obs["admitted"] = (
        obs["free_bytes"] >= DISK_FLOOR and obs["mem_available_bytes"] >= MEM_FLOOR
        and max(obs["owned_bytes"], obs["owned_allocated_bytes"]) <= CAP
        and all(x.st_size <= MIB for x in entries))
    observations.append(obs)
    if not obs["admitted"]:
        raise GuardRefusal("Resource guard refused: " + label)
    return obs

def type_equal(actual, expected, path="$"):
    if type(actual) is not type(expected):
        raise AssertionError(f"{path}: type {type(actual).__name__} != {type(expected).__name__}")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"{path}: object keys differ")
        return 1 + sum(type_equal(actual[k], expected[k], path + "." + k) for k in expected)
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: list length differs")
        return 1 + sum(type_equal(a, e, path + f"[{i}]") for i, (a, e) in enumerate(zip(actual, expected)))
    if actual != expected:
        raise AssertionError(f"{path}: value differs: {actual!r} != {expected!r}")
    return 1

class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.counts = {}
        self.metadata = {}
        self.captures = []
        self.current_label = None
        self.active_tags = []
        self.active_attributes = []
        self.links = []
        self.styles = []
        self.csp = []
        self.visible = []
        self.style_depth = 0
        self.details_open = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ("script", "iframe", "object", "embed", "img", "link", "audio", "video", "source", "base", "form"):
            self.active_tags.append({"tag": tag, "attrs": attrs})
        for key, value in attrs:
            if key.lower().startswith("on"):
                self.active_attributes.append([tag, key, value])
            if key in ("src", "srcset", "action", "formaction", "xlink:href"):
                self.active_attributes.append([tag, key, value])
            if key == "href" and not (tag == "a" and value and value.startswith("#")):
                self.active_attributes.append([tag, key, value])
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            self.active_attributes.append([tag, "refresh", values.get("content")])
        if tag == "meta" and values.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(values.get("content"))
        if tag == "a":
            self.links.append(values.get("href"))
        if tag == "style":
            self.style_depth += 1
        if tag == "details" and "open" in values:
            self.details_open += 1
        if tag == "pre" and "data-kind" in values:
            self.captures.append({"tag": tag, "type": "record", "kind": values["data-kind"],
                                  "index": values.get("data-index"), "text": []})
        elif tag == "td" and values.get("id", "").startswith("count-"):
            self.captures.append({"tag": tag, "type": "count", "key": values["id"], "text": []})
        elif tag in ("dt", "dd"):
            self.captures.append({"tag": tag, "type": tag, "text": []})

    def handle_endtag(self, tag):
        if tag == "style":
            self.style_depth = max(0, self.style_depth - 1)
        if not self.captures or self.captures[-1]["tag"] != tag:
            return
        item = self.captures.pop()
        text = "".join(item["text"])
        if item["type"] == "record":
            self.records.append({"kind": item["kind"], "index": item["index"], "json_text": text,
                                 "value": json.loads(text)})
        elif item["type"] == "count":
            if item["key"] in self.counts:
                raise AssertionError("Duplicate count cell")
            self.counts[item["key"]] = int(text.strip())
        elif item["type"] == "dt":
            self.current_label = text.strip()
        elif item["type"] == "dd":
            if self.current_label in self.metadata:
                raise AssertionError("Duplicate metadata label")
            self.metadata[self.current_label] = json.loads(text)

    def handle_data(self, data):
        for item in self.captures:
            item["text"].append(data)
        if self.style_depth:
            self.styles.append(data)
        else:
            self.visible.append(data)

def observe_html(root, output, expected):
    data = output.read_bytes()
    if not data or len(data) > MIB:
        raise AssertionError("HTML absent or oversized")
    text = data.decode("utf-8")
    parser = ReportParser()
    parser.feed(text)
    parser.close()
    if parser.captures:
        raise AssertionError("Unclosed structured record element")
    kinds = (("checkpoints", "checkpoints"), ("annotations", "annotations"),
             ("sync-anchors", "sync_anchors"), ("gaps", "gaps"))
    all_rows = {}
    comparisons = 0
    expected_record_order = []
    for kind, expected_key in kinds:
        actual_rows = [row for row in parser.records if row["kind"] == kind]
        if [row["index"] for row in actual_rows] != [str(i) for i in range(len(expected[expected_key]))]:
            raise AssertionError("Record indexes/order differ: " + kind)
        values = [row["value"] for row in actual_rows]
        comparisons += type_equal(values, expected[expected_key], "$." + expected_key)
        all_rows[expected_key] = values
        expected_record_order.extend((kind, str(i)) for i in range(len(values)))
        if parser.counts["count-" + kind] != expected["returned_counts"][expected_key]:
            raise AssertionError("Returned count differs: " + kind)
    if [(r["kind"], r["index"]) for r in parser.records] != expected_record_order:
        raise AssertionError("Unexpected or reordered report record groups")
    metadata_expected = {
        "Package path read": str(root / "inputs/positive.mmsession"),
        "Session ID reported": expected["session_id"],
        "State reported": expected["state"],
        "Start wall time reported": "2026-08-09T00:00:00Z",
        "Finalized time reported": "2026-08-09T00:00:10Z",
        "Source identifiers returned": expected["source_ids"],
        "Recovery report paths returned; contents not opened": []}
    comparisons += type_equal(parser.metadata, metadata_expected, "$.reported_metadata")
    if parser.active_tags or parser.active_attributes:
        raise AssertionError("Active markup/resource found in saved HTML")
    css = "".join(parser.styles)
    if re.search(r"@import|url\s*\(", css, re.I):
        raise AssertionError("Unexpected CSS resource expression")
    if not parser.csp or "default-src 'none'" not in parser.csp[0]:
        raise AssertionError("Expected standalone CSP absent")
    visible = "".join(parser.visible)
    if "Recovered session" not in visible or "finalized_recovered" not in visible:
        raise AssertionError("Reported recovered labeling not visible")
    if parser.details_open != 8:
        raise AssertionError("Not all eight returned records are initially disclosed")
    return {"physical_file": file_pin(root, output), "arbitrary_precision_python_json": True,
            "type_sensitive_comparison_nodes": comparisons, "all_full_record_values_and_types_match": True,
            "full_decoded_records": all_rows, "metadata": parser.metadata, "returned_counts": parser.counts,
            "structured_pre_records": parser.records, "local_links": parser.links,
            "active_tags": parser.active_tags, "active_attributes": parser.active_attributes,
            "csp": parser.csp, "initial_open_details": parser.details_open,
            "css_external_resource_expression": False, "visible_text": visible,
            "duration_and_open_closed_aggregate_display": "Not present in this candidate; conditional contract check not applicable.",
            "scope_review": "Human source review retained separately; no inference of capture completeness or raw-gap preservation."}

def limit_child():
    resource.setrlimit(resource.RLIMIT_FSIZE, (MIB, MIB))

def stop_owned(child, record, reason):
    record["termination_reason"] = reason
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        record["sigterm_sent"] = True
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            record["sigkill_sent"] = True
            child.wait()
    return child.returncode

def run_child(root, name, package, output, observations, children):
    guard(root, "before-" + name, observations)
    stdout_path = root / ("evidence/children/" + name + ".stdout.txt")
    stderr_path = root / ("evidence/children/" + name + ".stderr.txt")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(pathlib.Path(sys.executable).resolve()), "-I", "-B",
            str(root / "source/tools/report_recorded_events.py"), str(package), str(output)]
    record = {"name": name, "started_at": now(), "argv": argv, "cwd": str(root / "foreign-cwd"),
              "timeout_seconds": 20, "owned_kill_after_seconds": 2, "stream_limit_bytes": MIB,
              "environment_overrides": {"PYTHONDONTWRITEBYTECODE": "1",
                                         "LOCALAPPDATA": str(root / "absent-appdata-sentinel")},
              "timed_out": False, "sigterm_sent": False, "sigkill_sent": False}
    children.append(record)
    env = os.environ.copy()
    env.update(record["environment_overrides"])
    child = None
    started = time.monotonic()
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            child = subprocess.Popen(argv, cwd=root / "foreign-cwd", env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr, start_new_session=True,
                                     preexec_fn=limit_child)
            record["pid"] = child.pid
            record["owned_process_group"] = child.pid
            next_guard = started + 0.25
            while child.poll() is None:
                current = time.monotonic()
                if current - started > 20:
                    record["timed_out"] = True
                    stop_owned(child, record, "20-second owned child limit")
                    break
                if current >= next_guard:
                    try:
                        guard(root, "monitor-" + name, observations)
                    except GuardRefusal:
                        stop_owned(child, record, "resource guard")
                        raise
                    next_guard = current + 0.25
                time.sleep(0.01)
            record["wait_returncode"] = child.wait()
            record["poll_returncode"] = child.poll()
            record["child_reaped_by_wait"] = True
    except BaseException as error:
        record["observer_exception"] = {"type": type(error).__name__, "message": str(error)}
        if child is not None:
            stop_owned(child, record, "observer exception")
            record["wait_returncode"] = child.wait()
            record["poll_returncode"] = child.poll()
            record["child_reaped_by_wait"] = True
        raise
    finally:
        record["finished_at"] = now()
        record["elapsed_seconds"] = time.monotonic() - started
        for key, path in (("stdout", stdout_path), ("stderr", stderr_path)):
            if path.exists():
                path.chmod(0o444)
                record[key] = {"pin": file_pin(root, path), "text": path.read_bytes().decode("utf-8")}
        record["closure_scope"] = "Popen wait/poll for this owned child only; no separate PID-path or universal process absence claim."
    guard(root, "after-" + name, observations)
    return record

def run(root):
    root = pathlib.Path(root)
    record = {"schema": "capturesuite-independent-linux-receiving-v1", "started_at": now(),
              "contract": "7fd938b783feb56b3f7bbb29ae52d60146359600",
              "controller_pid": os.getpid(), "root": str(root),
              "groups": {"C1": "pending", "C2": "pending", "C3": "pending",
                         "C4": "pending: later same-byte Mac artifact receiving", "C5_linux": "pending"},
              "guards": [], "children": [], "failures": [], "independent_cli_calls_planned": 3,
              "old_suites_run": 0, "candidate_imported_in_observer": False}
    before = protected_inventory(root)
    record["protected_before"] = before
    output = root / "exports/recorded-events.html"
    refused = root / "exports/refused.html"
    initial_output_pin = None
    try:
        record["runtime"] = {"executable": str(pathlib.Path(sys.executable).resolve()),
                             "version": sys.version, "uid": os.getuid(), "gid": os.getgid(),
                             **body_pin(pathlib.Path(sys.executable).resolve().read_bytes())}
        if sys.version_info[:2] != (3, 12) or record["runtime"]["sha256"] != PYTHON_SHA:
            raise AssertionError("Supported pinned Python 3.12 runtime mismatch")
        if any(int(item["mode"], 8) & 0o222 for item in before):
            raise AssertionError("A frozen source/input file is writable")
        guard(root, "receiver-entry", record["guards"])
        expected = json.loads((root / "frozen/FROZEN-EXPECTED.json").read_bytes())
        if os.path.lexists(output) or os.path.lexists(refused):
            raise AssertionError("Output destinations were not absent")
        if os.path.lexists(root / "absent-appdata-sentinel"):
            raise AssertionError("Appdata sentinel unexpectedly exists at admission")
        record["groups"]["C1"] = "PASS: exact staged pins plus reviewed ordinary import/source boundary"
        positive = run_child(root, "C2-positive", root / "inputs/positive.mmsession", output,
                             record["guards"], record["children"])
        if positive["wait_returncode"] != 0 or positive["timed_out"]:
            raise AssertionError("Positive physical CLI did not exit 0")
        initial_output_pin = file_pin(root, output)
        observed = observe_html(root, output, expected)
        result = json.loads(positive["stdout"]["text"])
        expected_stdout = {
            "status": "written", "package": str(root / "inputs/positive.mmsession"),
            "output": str(output), "bytes": initial_output_pin["bytes"],
            "sha256": initial_output_pin["sha256"], "reported_state": expected["state"],
            "records_returned": {"checkpoints": 2, "annotations": 2, "sync_anchors": 2, "normalized_gaps": 2}}
        type_equal(result, expected_stdout, "$.stdout")
        if protected_inventory(root) != before:
            raise AssertionError("Protected source/input changed after positive command")
        record["html_observation"] = observed
        record["html_observation_file"] = write_json(root, "evidence/PHYSICAL-HTML-OBSERVATION.json", observed)
        record["positive_output_pin"] = initial_output_pin
        record["groups"]["C2"] = "PASS"
        existing = run_child(root, "C3-existing", root / "inputs/positive.mmsession", output,
                             record["guards"], record["children"])
        if existing["wait_returncode"] == 0 or existing["timed_out"]:
            raise AssertionError("Existing output was not refused")
        if str(output) not in existing["stderr"]["text"] or "exists" not in existing["stderr"]["text"].lower():
            raise AssertionError("Existing-output refusal was not actionable")
        if existing["stdout"]["text"] or file_pin(root, output) != initial_output_pin or protected_inventory(root) != before:
            raise AssertionError("Existing-output refusal changed prior output/input or reported success")
        record["existing_output_refusal_passed"] = True
        malformed = run_child(root, "C3-malformed", root / "inputs/malformed.mmsession", refused,
                              record["guards"], record["children"])
        error_text = malformed["stderr"]["text"]
        exact_gap_path = str(root / "inputs" / expected["malformed_error"]["path_suffix"])
        if malformed["wait_returncode"] == 0 or malformed["timed_out"]:
            raise AssertionError("Malformed physical package was not refused")
        if not all(part in error_text for part in (exact_gap_path, "line 4", "invalid JSON")):
            raise AssertionError("Malformed refusal lacks exact physical path, line 4 or invalid JSON")
        if "Traceback" in error_text or malformed["stdout"]["text"] or os.path.lexists(refused):
            raise AssertionError("Malformed refusal emitted traceback/success or created an output")
        if file_pin(root, output) != initial_output_pin or protected_inventory(root) != before:
            raise AssertionError("Malformed refusal changed protected bytes")
        record["malformed_gap_error"] = {"full_expected_path": exact_gap_path, "physical_line": 4,
                                          "reason": "invalid JSON", "no_output_created": True}
        record["groups"]["C3"] = "PASS"
    except BaseException as error:
        record["failures"].append({"type": type(error).__name__, "message": str(error),
                                   "traceback": traceback.format_exc(),
                                   "classification": "resource admission refusal" if isinstance(error, GuardRefusal)
                                   else "independent receiving/observer failure; inspect original evidence"})
    finally:
        record["protected_after"] = protected_inventory(root)
        record["protected_unchanged"] = record["protected_after"] == before
        record["refused_output_absent"] = not os.path.lexists(refused)
        record["appdata_sentinel_absent"] = not os.path.lexists(root / "absent-appdata-sentinel")
        record["all_started_children_reaped"] = all(c.get("child_reaped_by_wait", False) for c in record["children"])
        record["positive_output_preserved"] = initial_output_pin is not None and output.exists() and file_pin(root, output) == initial_output_pin
        record["independent_cli_calls_actual"] = len(record["children"])
        try:
            record["final_guard"] = guard(root, "linux-closure", record["guards"])
        except BaseException as error:
            record["failures"].append({"type": type(error).__name__, "message": str(error), "phase": "closure guard"})
        preserved = (record["protected_unchanged"] and record["refused_output_absent"]
                     and record["appdata_sentinel_absent"] and record["all_started_children_reaped"]
                     and record["positive_output_preserved"])
        if preserved and not record["failures"] and len(record["children"]) == 3:
            record["groups"]["C5_linux"] = "PASS: measured preservation and actual owned-child reaping"
        else:
            record["groups"]["C5_linux"] = "NOT PASSED: inspect retained closure fields"
        record["linux_accepted"] = (record["groups"]["C2"] == "PASS" and record["groups"]["C3"] == "PASS"
                                    and record["groups"]["C5_linux"].startswith("PASS") and not record["failures"])
        record["finished_at"] = now()
        record["limits"] = [
            "Exactly three independent physical CLI calls; no old reader/author/Windows/Qt/hardware suite.",
            "Mac C4 remains pending. Linux HTML is the sole positive output for later exact-byte transfer.",
            "Physical write/readback and source flush/fsync/close do not establish reboot/power-loss durability or /dev persistence.",
            "Recorded source review and author qualification are distinct from the three actual calls.",
            "No extra PID-path probe; owned Popen wait/poll is the closure evidence."]
        receipt_pin = write_json(root, "evidence/LINUX-RECEIPT.json", record)
    return {"linux_accepted": record["linux_accepted"], "groups": record["groups"],
            "receipt": receipt_pin, "positive_output": record.get("positive_output_pin"),
            "children": [{k: c.get(k) for k in ("name", "pid", "wait_returncode", "poll_returncode", "elapsed_seconds", "timed_out", "child_reaped_by_wait")} for c in record["children"]],
            "failures": record["failures"]}
