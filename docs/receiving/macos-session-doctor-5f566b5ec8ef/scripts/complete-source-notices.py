# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import base64,datetime,gzip,hashlib,io,json,os,shutil,subprocess,tarfile
ROOT=Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
OLD=ROOT/"receiver/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
NEW=ROOT/"receiver-final/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def mode(path): return "100755" if path.stat().st_mode & 0o111 else "100644"
def encoded(value): return (json.dumps(value,indent=2,ensure_ascii=False)+"\n").encode()
old=json.loads((ROOT/"evidence/archive-receiving.json").read_text())
assert old["archive"]["sha256"]=="7093ebce7339d67867a7af181515db6eb9bd795ffd6f9e2178aca3adc3643b72"
assert sha(Path(old["archive"]["path"]).read_bytes())==old["archive"]["sha256"]
for item in old["files"]:
    path=OLD/item["path"];data=path.read_bytes()
    assert len(data)==item["size"] and sha(data)==item["sha256"] and mode(path)==item["mode"],item["path"]
payload=json.loads((ROOT/"evidence/project-notice-inputs.json").read_text())
assert payload["canonical_base"]=="d43bdea867d6198a707a5f55e29216c76054517e"
added=[]
for item in payload["files"]:
    data=base64.b64decode("".join(item["content"].split()),validate=True)
    assert blob(data)==item["sha"],item["path"]
    added.append({"path":"source/"+item["path"],"data":data,"git_blob_sha":blob(data)})
assert len(added)==4
shutil.copytree(OLD,NEW)
for item in added:
    path=NEW/item["path"]
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as f:f.write(item["data"])
addition={"canonical_base":payload["canonical_base"],"purpose":"Exact project licensing and notices for the included source; no compiled source or runtime changes.","files":[{"path":i["path"],"size":len(i["data"]),"sha256":sha(i["data"]),"git_blob_sha":i["git_blob_sha"],"mode":"100644"} for i in added]}
with (NEW/"source-notices-manifest.json").open("xb") as f:f.write(encoded(addition))
note=NEW/"NOTICE.md"
note.write_bytes(note.read_bytes()+b"\nThe project's own licensing split is retained in source/LICENSING.md and source/NOTICE. Included schemas retain their separate source/schemas/LICENSE and source/schemas/NOTICE. These four files are exact canonical copies, listed in source-notices-manifest.json.\n")
# Rebuild only final-copy metadata; the earlier package and archive remain exact.
(NEW/"CONTENTS.json").unlink()
(NEW/"SHA256SUMS").unlink()
records=[]
for path in sorted(NEW.rglob("*")):
    if path.is_dir(): continue
    assert path.is_file() and not path.is_symlink(),str(path)
    data=path.read_bytes()
    records.append({"path":path.relative_to(NEW).as_posix(),"size":len(data),"sha256":sha(data),"mode":mode(path)})
manifest={"schema":"capturesuite.native-receiver-contents/1","canonical_base":payload["canonical_base"],"qualified_native_source":"6a1a32e6240dc89892f340f241b03ef25a8ac8fc","runtime_files":87,"files":records}
manifest_bytes=encoded(manifest)
(NEW/"CONTENTS.json").write_bytes(manifest_bytes)
sums="\n".join(item["sha256"]+"  "+item["path"] for item in records)+"\n"+sha(manifest_bytes)+"  CONTENTS.json\n"
(NEW/"SHA256SUMS").write_bytes(sums.encode())
complete=[]
for path in sorted(NEW.rglob("*")):
    if path.is_file():
        data=path.read_bytes();complete.append({"path":path.relative_to(NEW).as_posix(),"size":len(data),"sha256":sha(data),"mode":mode(path)})
archive=ROOT/"distribution"/(NEW.name+"-source-notices.tar.gz")
with archive.open("xb") as raw:
    with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode="w",format=tarfile.PAX_FORMAT) as tar:
            for path in [NEW]+sorted(p for p in NEW.rglob("*") if p.is_dir()):
                name=NEW.name if path==NEW else NEW.name+"/"+path.relative_to(NEW).as_posix()
                info=tarfile.TarInfo(name);info.type=tarfile.DIRTYPE;info.mode=0o755;info.mtime=0;tar.addfile(info)
            for item in complete:
                info=tarfile.TarInfo(NEW.name+"/"+item["path"]);info.mode=0o755 if item["mode"]=="100755" else 0o644;info.size=item["size"];info.mtime=0
                tar.addfile(info,io.BytesIO((NEW/item["path"]).read_bytes()))
receiving=ROOT/"archive-receiving-final";receiving.mkdir()
extracted=receiving/"extracted";extracted.mkdir()
with tarfile.open(archive,"r:gz") as tar:
    members=tar.getmembers()
    assert {m.name for m in members if m.isfile()}=={NEW.name+"/"+i["path"] for i in complete}
    assert all(m.isfile() or m.isdir() for m in members)
    tar.extractall(extracted,filter="data")
target=extracted/NEW.name
for item in complete:
    path=target/item["path"];data=path.read_bytes()
    assert len(data)==item["size"] and sha(data)==item["sha256"] and mode(path)==item["mode"],item["path"]
cwd=receiving/"unrelated-working-directory";cwd.mkdir()
env={k:v for k,v in os.environ.items() if not k.startswith(("DYLD_","LD_","CAPTURE_","MCAP_"))};env["PATH"]="/usr/bin:/bin:/usr/sbin:/sbin"
call=subprocess.run([str(target/"bin/session_doctor"),"--help"],cwd=cwd,env=env,capture_output=True,timeout=10)
(receiving/"help.stdout").write_bytes(call.stdout);(receiving/"help.stderr").write_bytes(call.stderr)
assert call.returncode==0 and call.stdout==b"Usage: session_doctor <path-to-session.mmsession>\n" and not call.stderr
runtime=json.loads((ROOT/"evidence/runtime-package.json").read_text())
source=json.loads((ROOT/"evidence/source-inputs.json").read_text())
for prefix,items in [(ROOT/"source",source["files"]),(NEW,runtime["files"]),(target,runtime["files"]),(OLD,old["files"])]:
    for item in items:
        path=prefix/item["path"];data=path.read_bytes()
        assert len(data)==item["size"] and sha(data)==item["sha256"] and mode(path)==item["mode"],str(path)
assert sha(Path(old["archive"]["path"]).read_bytes())==old["archive"]["sha256"]
old_map={i["path"]:i for i in old["files"]}
changed=[i["path"] for i in complete if i["path"] in old_map and (i["sha256"],i["mode"])!=(old_map[i["path"]]["sha256"],old_map[i["path"]]["mode"])]
assert sorted(changed)==["CONTENTS.json","NOTICE.md","SHA256SUMS"]
report={"schema":"capturesuite.native-receiver-final-archive/1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"archive":{"path":str(archive),"size":archive.stat().st_size,"sha256":sha(archive.read_bytes())},"original_archive":old["archive"],"original_archive_preserved":True,"package":str(NEW),"contents_sha256":sha(manifest_bytes),"files":complete,"payload_files":len(complete),"payload_bytes":sum(i["size"] for i in complete),"exact_extracted_files":len(complete),"extracted":str(target),"help":{"exit":call.returncode,"stdout":call.stdout.decode(),"stderr":call.stderr.decode(),"cwd":str(cwd),"path":env["PATH"]},"metadata_correction":{"new_files":[i["path"] for i in complete if i["path"] not in old_map],"changed_files":changed},"source_inputs_unchanged":96,"runtime_files_unchanged":87,"qualification_scope":"Only final metadata/archive extraction and actual extracted --help; no build or recovery replay."}
out=ROOT/"evidence/archive-receiving-final.json"
with out.open("xb") as f:f.write(encoded(report))
print(json.dumps({"archive":report["archive"],"receipt_sha256":sha(out.read_bytes()),"contents_sha256":report["contents_sha256"],"payload_files":len(complete),"new_files":report["metadata_correction"]["new_files"],"changed_metadata":changed,"help_exit":call.returncode,"runtime_files_unchanged":87,"original_archive_preserved":True}))
