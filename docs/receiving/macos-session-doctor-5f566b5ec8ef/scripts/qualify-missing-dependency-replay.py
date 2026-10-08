# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import datetime, hashlib, json, os, resource, subprocess, traceback

ROOT=Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
RELOCATED=ROOT/"receiving-process-controls/Session Doctor 雪"
EXE=RELOCATED/"bin/session_doctor"
OUTPUT=ROOT/"missing-dependency-replay"
OUTPUT.mkdir()
manifest=json.loads((ROOT/"evidence/runtime-package.json").read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def errors():
    return [f["path"] for f in manifest["files"] if digest(RELOCATED/f["path"])!=f["sha256"] or (RELOCATED/f["path"]).stat().st_size!=f["size"]]
assert not errors()
candidates=[f for f in manifest["files"] if f["path"].startswith("lib/libblake3.")]
assert len(candidates)==1
entry=candidates[0];library=RELOCATED/entry["path"];held=OUTPUT/library.name
assert not held.exists()
env={k:v for k,v in os.environ.items() if not k.startswith(("DYLD_","LD_","CAPTURE_","MCAP_"))}
env["PATH"]="/usr/bin:/bin:/usr/sbin:/sbin"
def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def run():
    r=subprocess.run([str(EXE),"--help"],cwd=OUTPUT,env=env,text=True,capture_output=True,timeout=15,preexec_fn=no_core)
    return {"exit":r.returncode,"stdout":r.stdout,"stderr":r.stderr}
receipt={"schema":"capturesuite.canonical-mac-dependency-replay/1","observed_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "prior_receipt_sha256":digest(ROOT/"evidence/receiver-process-first.json"),
         "correction":"The original seven receiver controls passed. Its eighth control failed before moving or launching because it assumed the Homebrew symlink filename rather than the exact resolved filename in runtime-package.json. This replay selects the single pinned BLAKE3 file from that unchanged manifest and executes only that remaining control.",
         "binary_sha256":digest(EXE),"library":entry,"passed":False}
try:
    library.rename(held)
    try:
        receipt["withheld"]=run()
    finally:
        held.rename(library)
    receipt["restored"]=run()
    assert receipt["withheld"]["exit"]!=0 and not receipt["withheld"]["stdout"]
    assert library.name in receipt["withheld"]["stderr"] and "Library not loaded" in receipt["withheld"]["stderr"]
    assert receipt["restored"]["exit"]==0 and receipt["restored"]["stdout"].startswith("Usage: session_doctor") and not receipt["restored"]["stderr"]
    receipt["package_errors_after"]=errors()
    assert not receipt["package_errors_after"]
    receipt["passed"]=True
except Exception as error:
    receipt["error"]=repr(error);receipt["traceback"]=traceback.format_exc()
out=ROOT/"evidence/receiver-dependency-replay.json";out.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"passed":receipt["passed"],"library":entry["path"],"withheld":receipt.get("withheld"),"restored":receipt.get("restored"),"package_errors_after":receipt.get("package_errors_after"),"receipt_sha256":digest(out)},indent=2))
assert receipt["passed"]
