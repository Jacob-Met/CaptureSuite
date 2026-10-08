# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
import pathlib
import platform
import struct
import subprocess
import sys
import traceback
import types

root = pathlib.Path("/Users/me/Developer/capturesuite-framing-integration-72ac1419")
sys.path.insert(0, str(root / "libs/python/capture_protocol"))
import capture_protocol
import capture_protocol.framing as candidate
import google.protobuf
from capture_protocol.constants import FRAME_MAGIC, MAX_PAYLOAD_LEN

expected_head = "4359c21f3da93ed863de617331edfc853cf8385d"
expected_base = "65b76c9909f0c28d34c9f44f07d306b924955da8"
def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
assert git("rev-parse", "HEAD") == expected_head
assert git("rev-parse", "HEAD^") == expected_base
assert git("status", "--porcelain=v1") == ""
source_rel = "libs/python/capture_protocol/capture_protocol/framing.py"
assert pathlib.Path(candidate.__file__).resolve() == root / source_rel
source = (root / source_rel).read_bytes()
assert hashlib.sha256(source).hexdigest() == "3ff7c7284d9907a2ad516c83fab383a4151996da3f2d5a1d27e24d7c7575d92e"
base_source = subprocess.check_output(["git", "-C", str(root), "show", expected_base + ":" + source_rel])
assert hashlib.sha256(base_source).hexdigest() == "4bc45fb94866658fe44be9ad0871dc12a9e2b1bfedf88c48fd15e2246f62e08d"

# Execute exact historical module without altering the installed current package or the clone.
base = types.ModuleType("capture_protocol._peer_predecessor")
sys.modules[base.__name__] = base
exec(compile(base_source, expected_base + ":" + source_rel, "exec"), base.__dict__)

negative = []
for kind, magic, size in [("magic", 0, 0), ("length", FRAME_MAGIC, MAX_PAYLOAD_LEN + 1)]:
    dec = base.FrameDecoder()
    try:
        dec.feed(struct.pack("<IIII", magic, size, 1, 37))
    except base.FrameError as error:
        assert error.__traceback__ is not None
        try:
            dec.reset()
        except BufferError as reset_error:
            negative.append({"kind": kind, "frame_error": str(error), "reset_error": str(reset_error)})
        else:
            raise AssertionError("Exact predecessor did not reproduce retained active-handler borrow")
    else:
        raise AssertionError("Exact predecessor swallowed protocol error")

valid_wire = candidate.encode_frame(7, b"original", 9)
cases = [
    ("partial-header", b"CSP", ValueError, "incomplete header"),
    ("partial-payload", valid_wire[:-1], ValueError, "incomplete payload"),
    ("bad-magic", struct.pack("<IIII", 0, 0, 1, 37), candidate.FrameError, "bad magic: expected b'CSP1', got b'\\x00\\x00\\x00\\x00'"),
    ("oversized-length", struct.pack("<IIII", FRAME_MAGIC, MAX_PAYLOAD_LEN + 1, 1, 37), candidate.FrameError, f"payload_len {MAX_PAYLOAD_LEN + 1} exceeds max {MAX_PAYLOAD_LEN}"),
    ("valid", valid_wire, None, None),
]
passed = []
for mode in ["bytearray", "caller-view", "readonly-view", "sliced-view"]:
    for kind, wire, error_type, message in cases:
        buffer = bytearray(b"xx" + wire + b"yy") if mode == "sliced-view" else bytearray(wire)
        if mode == "bytearray":
            argument = buffer
        elif mode == "caller-view":
            argument = memoryview(buffer)
        elif mode == "readonly-view":
            argument = memoryview(buffer).toreadonly()
        else:
            argument = memoryview(buffer)[2:2 + len(wire)]
        retained = []
        frame = None
        try:
            frame, consumed = candidate.decode_frame(argument)
        except ValueError as error:
            assert type(error) is error_type, (mode, kind, type(error), error_type)
            assert str(error) == message, (mode, kind, str(error), message)
            retained.append(error)
        else:
            assert error_type is None, (mode, kind)
            assert frame == candidate.Frame(7, 9, b"original")
            assert consumed == len(wire)
        assert len(retained) == int(error_type is not None), (mode, kind)
        if isinstance(argument, memoryview):
            assert argument.tobytes() == wire, (mode, kind)
            assert argument.readonly == (mode == "readonly-view"), (mode, kind)
            try:
                buffer.extend(b"extension")
            except BufferError:
                pass
            else:
                raise AssertionError((mode, kind, "caller view was unexpectedly released"))
            argument.release()
        buffer.clear()
        buffer.extend(b"replacement")
        if frame is not None:
            assert frame.payload == b"original"
            assert isinstance(frame.payload, bytes)
        for saved in retained:
            assert saved.__traceback__ is not None
            assert message in "".join(traceback.format_exception(saved))
        passed.append(mode + ":" + kind)

assert git("status", "--porcelain=v1") == ""
print(json.dumps({
    "receiver": "integration/capture_peer",
    "head": expected_head,
    "parent": expected_base,
    "tree": git("rev-parse", "HEAD^{tree}"),
    "platform": platform.platform(),
    "python": sys.version.split()[0],
    "protobuf": google.protobuf.__version__,
    "package": capture_protocol.__file__,
    "candidate_source_sha256": hashlib.sha256(source).hexdigest(),
    "predecessor_source_sha256": hashlib.sha256(base_source).hexdigest(),
    "retained_predecessor_failures": negative,
    "independent_candidate_cases_passed": passed,
    "count": len(passed),
    "working_tree": "clean_before_and_after",
    "windows_qualification": "not_performed"
}, indent=2))

