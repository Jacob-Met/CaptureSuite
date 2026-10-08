# SPDX-License-Identifier: GPL-3.0-only
"""Independent Windows filesystem receiving of PR80's exact assertion correction.
No Qt/gallery code is invoked; hosted run 37811945519 supplies the full-suite baseline.
"""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ("native-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
OUT.mkdir()
payload = json.loads((ROOT / "source-payload.json").read_text(encoding="utf-8"))
expected = {
    "original": ("0874d6b51b22cbbeaa8b1e309ed92418efcec2c6", "727340556a0d8e4178b62157ba9680a59d1c43158abb1bf979b21be8c98c591f"),
    "candidate": ("746084780e126b103489902f119b8e46c2fd8c98", "566ff56a05014d47ffd887976751c06f259957a908ec34528725a039269b434f"),
}
source = {}
for name, (git, sha) in expected.items():
    data = payload[name].encode("utf-8")
    assert hashlib.sha256(data).hexdigest() == sha
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == git
    (OUT / (name + ".py")).write_bytes(data)
    source[name] = {"git_blob": git, "sha256": sha, "bytes": len(data)}

def function(text):
    return next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
                and n.name == "test_png_discovery_refuses_external_file_links_and_directories")

def has_call(node, name):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name
               for n in ast.walk(node))

old = function(payload["original"])
new = function(payload["candidate"])
old_after = next(n for n in old.body if isinstance(n, ast.Assert) and has_call(n, "readlink"))
new_before = [n for n in new.body if
              (isinstance(n, ast.Assign) and has_call(n, "readlink"))
              or (isinstance(n, ast.Assert) and has_call(n, "samefile"))]
new_after = next(n for n in new.body if isinstance(n, ast.Assert) and has_call(n, "readlink"))
assert len(new_before) == 2
old_rest = [n for n in old.body if n is not old_after]
new_rest = [n for n in new.body if n not in new_before and n is not new_after]
assert ast.dump(ast.Module(body=old_rest, type_ignores=[])) == ast.dump(ast.Module(body=new_rest, type_ignores=[]))

def statements(nodes, scope):
    try:
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "<exact-source-assertions>", "exec"), scope)
    except Exception as exc:
        return {"status": "rejected", "exception": type(exc).__name__, "message": str(exc)}
    return {"status": "passed"}

def fixture(name, *, relative=False, wrong=False):
    root = OUT / name
    folder = root / "job" / "figures"
    folder.mkdir(parents=True)
    outside = root / "external.png"
    other = root / "other.png"
    outside.write_bytes(b"filesystem identity fixture; not a Qt image\n")
    other.write_bytes(outside.read_bytes())
    foreign = folder / "foreign.png"
    target = other if wrong else outside
    if relative:
        target = Path(os.path.relpath(target, foreign.parent))
    foreign.symlink_to(target)
    return {"foreign": foreign, "outside": outside, "other": other}, root

checks = []
def record(name, result):
    checks.append({"name": name, **result})

scope, root = fixture("absolute")
foreign, outside = scope["foreign"], scope["outside"]
raw_before = foreign.readlink()
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (outside, scope["other"])}
baseline = statements([old_after], dict(scope))
record("original_assertion_on_actual_absolute_windows_link", {
    **baseline, "raw_readlink": str(raw_before), "authored_target": str(outside),
    "samefile": foreign.samefile(outside),
})
assert baseline["status"] == "rejected" and baseline["exception"] == "AssertionError"
assert foreign.samefile(outside)
guard = statements(new_before, scope)
after = statements([new_after], scope)
record("candidate_exact_assertions_unchanged_absolute_link", {"guard": guard, "after": after,
       "raw_target_unchanged": foreign.readlink() == raw_before})
assert guard["status"] == after["status"] == "passed"

scope, _ = fixture("relative", relative=True)
raw = scope["foreign"].readlink()
guard = statements(new_before, scope)
after = statements([new_after], scope)
record("candidate_exact_assertions_unchanged_relative_link", {
    "guard": guard, "after": after, "raw_readlink": str(raw), "samefile": scope["foreign"].samefile(scope["outside"])})
assert guard["status"] == after["status"] == "passed"

scope, _ = fixture("changed_target")
assert statements(new_before, scope)["status"] == "passed"
scope["foreign"].unlink()
scope["foreign"].symlink_to(scope["other"])
changed = statements([new_after], scope)
record("negative_same_bytes_different_target", {**changed, "targets_have_equal_bytes": scope["outside"].read_bytes() == scope["other"].read_bytes()})
assert changed["status"] == "rejected" and changed["exception"] == "AssertionError"

scope, _ = fixture("replaced_regular")
assert statements(new_before, scope)["status"] == "passed"
scope["foreign"].unlink()
scope["foreign"].write_bytes(scope["outside"].read_bytes())
replaced = statements([new_after], scope)
record("negative_link_replaced_by_regular_file", replaced)
assert replaced["status"] == "rejected" and replaced["exception"] in ("OSError", "ValueError")

scope, _ = fixture("wrong_initial_target", wrong=True)
wrong = statements(new_before, scope)
record("negative_initial_wrong_identity_same_bytes", {**wrong, "targets_have_equal_bytes": scope["outside"].read_bytes() == scope["other"].read_bytes()})
assert wrong["status"] == "rejected" and wrong["exception"] == "AssertionError"

assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (outside, root / "other.png")}
for name, (_, sha) in expected.items():
    assert hashlib.sha256((OUT / (name + ".py")).read_bytes()).hexdigest() == sha

receipt = {
    "schema": "capturesuite.pr80.windows-link-assertion-receiving.v1",
    "accepted": True,
    "scope": "Actual Windows filesystem and exact original/candidate assertion statements; no Qt/gallery invocation",
    "gallery_invoked": False,
    "source_ref": payload["source_ref"],
    "source": source,
    "preservation": {"all_other_function_ast_nodes_identical": True, "source_bytes_unchanged": True,
                     "healthy_fixture_target_bytes_unchanged": True},
    "checks": checks,
    "python": {"executable": sys.executable, "version": sys.version},
    "platform": platform.platform(),
    "receipt_directory": str(OUT),
    "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
data = json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
(OUT / "receipt.json").write_bytes(data)
print(data.decode("utf-8"), end="")
print("RECEIPT_SHA256=" + hashlib.sha256(data).hexdigest())
