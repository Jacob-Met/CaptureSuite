# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import base64,datetime,gzip,hashlib,io,json,os,shutil,stat,subprocess,tarfile,traceback
ROOT=Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
PACKAGE=ROOT/"receiver/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
DOCS=json.loads("{\"README.md\":\"# CaptureSuite session doctor — Mac receiver\\n\\nThis directory contains the native arm64 command-line receiver built from CaptureSuite commit `d43bdea867d6198a707a5f55e29216c76054517e`. It was qualified on macOS 26.6.2. The executable and its 86 non-system dynamic libraries are kept together, so this received build does not require Homebrew on its runtime search path.\\n\\n## Run the received tool\\n\\nKeep `bin/` and `lib/` together when moving this directory. Set the following path to the location where you extracted this receiver:\\n\\n```sh\\nreceiver_dir=\\\"/absolute/path/CaptureSuite-Session-Doctor-d43bdea-macos-arm64\\\"\\n\\\"$receiver_dir/bin/session_doctor\\\" --help\\n```\\n\\nThe existing CLI accepts one session-directory path. Recovery can truncate an unsealed segment and write recovery metadata in that directory. Use an explicitly selected working copy when examining retained data:\\n\\n```sh\\nsession_copy=\\\"/absolute/path/to/a-working-copy.mmsession\\\"\\n\\\"$receiver_dir/bin/session_doctor\\\" \\\"$session_copy\\\"\\n```\\n\\nExit 0 reports a successful or already-finalized result. No arguments print usage and exit 1. An ordinary recovery refusal prints `recovery failed: ...` on stderr and exits 2. A missing runtime library is an operating-system loader failure before the CLI starts.\\n\\n## Try the included finalized fixture\\n\\nThe repository fixture is small, synthetic and already finalized. Copy it to a new private directory before invoking the tool; this demonstrates the no-op receiving path and leaves the packaged source intact:\\n\\n```sh\\nfixture_parent=\\\"$(mktemp -d /tmp/capturesuite-doctor.XXXXXX)\\\"\\ncp -R \\\"$receiver_dir/source/tests/fixtures/mini_session\\\" \\\"$fixture_parent/example.mmsession\\\"\\n\\\"$receiver_dir/bin/session_doctor\\\" \\\"$fixture_parent/example.mmsession\\\"\\n```\\n\\n## What was actually qualified\\n\\n- The unchanged portable CMake target configured and built with AppleClang 21.0.0, CMake 4.2.3 and Ninja 1.13.2. All 17 available native CTest cases passed.\\n- A copy under a path containing spaces and Unicode ran from an unrelated directory with only system command directories on `PATH`. Dynamic-loader tracing showed all 87 non-system images came from that copy.\\n- Actual CLI controls covered no arguments, a missing session, malformed JSON, exact preservation of the finalized repository fixture, authored unsealed-tail recovery, sealed-file and pre-existing temporary-symlink preservation, and a byte-preserving repeated call.\\n- The first process harness passed seven cases, then stopped on an incorrect assumed library filename before the missing-library operation began. Its original failure is retained. A focused replay using the unchanged package manifest verified missing-library refusal and exact restoration.\\n- The original build executable, qualified package runtime files and 96 canonical source inputs are pinned separately. Packaging changes only the copied Mach-O library references and local ad-hoc signatures; it does not change the C++ implementation.\\n\\n## Scope\\n\\nThis is a distinct receiver for the already-merged canonical portable implementation. It does not replace the older Mac worktree or its unmerged recovery implementation. The Linux GNU linker-wrapped failure tests were not compiled on macOS. The qualification does not cover Windows, daemon or GUI operation, camera/radar hardware, Python analysis, arbitrary damaged recordings, other Mac architectures, or older macOS releases.\\n\\nThe copied Mach-O files have locally verified ad-hoc signatures. This packet is not an Apple-notarized installer and does not install a service, alter a default executable, or modify system trust settings.\\n\\n## Contents and provenance\\n\\n`CONTENTS.json` records the size, SHA-256 and mode of every payload file except the manifest and checksum list themselves. `SHA256SUMS` also covers `CONTENTS.json`. From this receiver directory, `/usr/bin/shasum -a 256 -c SHA256SUMS` verifies the file bytes.\\n\\n`source/` contains the 96 exact canonical inputs used for this portable target, including its source, schemas, CMake definitions and fixtures. It is a targeted source snapshot, not a complete repository checkout. `source-dependencies/mcap/` contains the exact 13 MCAP headers used. See `BUILD.md`, `source-manifest.json`, `runtime-manifest.json`, `dependency-records/` and `notices/` for the build and library correspondence.\\n\\n`qualification/` retains the native build and receiving receipts, including the original harness failure and focused replay. The archive extraction receipt lives beside the archive because it can only be written after the completed archive is extracted and exercised.\\n\",\"BUILD.md\":\"# Source and build correspondence\\n\\nCaptureSuite canonical commit: `d43bdea867d6198a707a5f55e29216c76054517e`.\\nNative immutable source snapshot: `6a1a32e6240dc89892f340f241b03ef25a8ac8fc`.\\nThe 96 inputs in `source-manifest.json` were checked against the canonical Git blob IDs before the build and checked again afterward.\\n\\nMCAP: repository `https://github.com/foxglove/mcap`, tag `releases/cpp/v2.1.1`, commit `b2953496735e7b89d5b2ea58be73abed85317c5f`. The included headers are under `source-dependencies/mcap/cpp/mcap/include`.\\n\\n## Build the portable target\\n\\nThe recorded build used macOS 26.6.2 arm64, AppleClang 21.0.0, CMake 4.2.3 and Ninja 1.13.2. Build-time dependencies were supplied by the existing `/opt/homebrew` installation: protobuf/protoc, spdlog, fmt, Abseil, Zstandard, LZ4, BLAKE3, SQLite headers, Catch2 and nlohmann-json. The linked receiver uses the macOS system SQLite library. Runtime dependency versions and original bytes are recorded in `runtime-manifest.json`; available Homebrew formula definitions are copied under `dependency-records/`.\\n\\nWith equivalent build dependencies available, choose a new build directory and use the existing portable CMake path:\\n\\n```sh\\nreceiver_dir=\\\"/absolute/path/CaptureSuite-Session-Doctor-d43bdea-macos-arm64\\\"\\nbuild_dir=\\\"/absolute/path/to/a-new-build-directory\\\"\\nexport MCAP_INCLUDE_DIR=\\\"$receiver_dir/source-dependencies/mcap/cpp/mcap/include\\\"\\ncmake -S \\\"$receiver_dir/source\\\" -B \\\"$build_dir\\\" -G Ninja \\\\\\n  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ \\\\\\n  \\\"-DCMAKE_PREFIX_PATH=/opt/homebrew;$receiver_dir/source/cmake/linux-shims\\\" \\\\\\n  -DCAPTURE_BUILD_TESTS=ON \\\\\\n  -DCAPTURE_ENABLE_CAMERA_WORKER=OFF -DCAPTURE_ENABLE_RADAR_WORKER=OFF \\\\\\n  -DCAPTURE_WERROR=OFF\\ncmake --build \\\"$build_dir\\\" --parallel 2\\nctest --test-dir \\\"$build_dir\\\" --output-on-failure --no-tests=error\\n```\\n\\n`linux-shims` is the existing repository directory name used by this portable configuration. No preset, bootstrap, schema, recovery, storage or worker source was changed for this receiver. The host-specific snapshot scripts under `qualification/` preserve the commands and checks actually performed; their original owned paths are evidence, not a generic installation API.\\n\\n## Runtime assembly\\n\\nOriginal build binary SHA-256: `4bb8872c854d0c344150c806d55674b4d0b6743355982552b6b494f785a19ce3`.\\nReceived binary SHA-256: `401f7ef7eb1212799c00ff7bdb22ac48a31bf6feb22a17b3a4fefcfc8e485772`.\\n\\nThe assembly copies the original executable and every resolved non-system dependency. It rewrites only the copies to use package-relative load commands, removes copied runtime search paths, and signs those copies ad hoc. Original build and installed library bytes are verified unchanged. The manifest records all 87 copied images and their source identities. `@rpath` admission uses the declaring image's explicit paths and refuses missing or ambiguous resolution; it does not rely on an ambient loader search.\\n\\nThe archive is a native receiving artifact. Its source and dependency records identify the exact received build; a newly compiled result is not claimed to be byte-identical across compiler or dependency updates.\\n\",\"NOTICE.md\":\"# Included software and source records\\n\\nCaptureSuite source and license are copied from the pinned canonical commit. MCAP headers and license are copied from its pinned native checkout. The corresponding license texts are retained under `notices/`; this file does not replace them.\\n\\nThe packaged dynamic libraries come from the existing Homebrew versions spdlog 1.17.0, fmt 12.2.0, protobuf 36.2 (including utf8_validity), Abseil 20260817.0, Zstandard 1.5.7_1, LZ4 1.10.0 and BLAKE3 1.8.7. Their original paths, file hashes and copied load commands are in `runtime-manifest.json`. The installed license files and available formula source definitions are included.\\n\\nBLAKE3's installed Cellar directory did not include license files. The three upstream license files were fetched from tag 1.8.7's exact commit `f3149ec5bb5449af877ba20377a11008ff499fa2` and checked against their Git blob IDs. Its installed formula records the source archive URL and SHA-256. `notices/manifest.json` records each notice's origin and bytes.\\n\\nmacOS libraries under `/usr/lib` and `/System/Library` remain system dependencies and are not copied into the receiver. This package is held as a local native receiver; no public binary release or installer has been published.\\n\"}")
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def encoded(value): return (json.dumps(value,indent=2,ensure_ascii=False)+"\n").encode()
def mode(path): return "100755" if path.stat().st_mode & 0o111 else "100644"
def verify(path,record):
    assert path.is_file() and not path.is_symlink(),str(path)
    data=path.read_bytes()
    assert len(data)==record["size"] and sha(data)==record["sha256"],str(path)
    assert mode(path)==record["mode"],str(path)
    if "git_blob_sha" in record: assert blob(data)==record["git_blob_sha"],str(path)
    return data
source=json.loads((ROOT/"evidence/source-inputs.json").read_text())
runtime=json.loads((ROOT/"evidence/runtime-package.json").read_text())
assert len(source["files"])==96 and len(runtime["files"])==87
assert not (PACKAGE/"CONTENTS.json").exists(),"receiver already sealed"
for item in runtime["files"]: verify(PACKAGE/item["path"],item)
assert sha((ROOT/"build/tools/session_doctor/session_doctor").read_bytes())==runtime["original_binary_sha256"]
materials={}
def put(name,data,permissions=0o644):
    assert name not in materials,name
    assert not (PACKAGE/name).exists() and not (PACKAGE/name).is_symlink(),name
    materials[name]=(data,permissions)
for name,body in DOCS.items(): put(name,body.encode())
for item in source["files"]:
    put("source/"+item["path"],verify(ROOT/"source"/item["path"],item),0o755 if item["mode"]=="100755" else 0o644)
put("source-manifest.json",(ROOT/"evidence/source-inputs.json").read_bytes())
put("runtime-manifest.json",(ROOT/"evidence/runtime-package.json").read_bytes())
mcap=ROOT/"dependencies/mcap"
assert subprocess.check_output(["/usr/bin/git","-C",str(mcap),"rev-parse","HEAD"],text=True).strip()=="b2953496735e7b89d5b2ea58be73abed85317c5f"
headers=sorted(p for p in (mcap/"cpp/mcap/include").rglob("*") if p.is_file())
assert len(headers)==13
for path in headers:
    assert not path.is_symlink()
    put("source-dependencies/mcap/"+path.relative_to(mcap).as_posix(),path.read_bytes())
notices=[]
def notice(destination,path,origin=None):
    data=path.read_bytes()
    put("notices/"+destination,data)
    notices.append({"path":destination,"origin":origin or str(path),"size":len(data),"sha256":sha(data),"git_blob_sha":blob(data)})
notice("CaptureSuite/LICENSE",ROOT/"source/LICENSE","Jacob-Met/CaptureSuite@"+source["canonical_base"]+":LICENSE")
notice("mcap/LICENSE",mcap/"LICENSE","foxglove/mcap@b2953496735e7b89d5b2ea58be73abed85317c5f:LICENSE")
packages={"spdlog":"1.17.0","fmt":"12.2.0","protobuf":"36.2","abseil":"20260817.0","zstd":"1.5.7_1","lz4":"1.10.0","blake3":"1.8.7"}
for name,version in packages.items():
    cellar=Path("/opt/homebrew/Cellar")/name/version
    formula=cellar/".brew"/(name+".rb")
    put("dependency-records/"+name+".rb",formula.read_bytes())
    if name!="blake3": notice(name+"/LICENSE",cellar/"LICENSE")
    if name=="zstd": notice(name+"/COPYING",cellar/"COPYING")
blake=json.loads((ROOT/"evidence/blake3-license-inputs.json").read_text())
assert blake["ref"]=="f3149ec5bb5449af877ba20377a11008ff499fa2" and len(blake["files"])==3
for item in blake["files"]:
    data=base64.b64decode("".join(item["content"].split()),validate=True)
    assert blob(data)==item["sha"],item["path"]
    destination="blake3/"+item["path"]
    put("notices/"+destination,data)
    notices.append({"path":destination,"origin":blake["upstream"]+"/blob/"+blake["ref"]+"/"+item["path"],"size":len(data),"sha256":sha(data),"git_blob_sha":blob(data)})
put("notices/manifest.json",encoded({"files":notices}))
evidence_names=["source-inputs.json","mcap-source.json","native-qualification-first.json","native-configure.log","native-build.log","native-ctest.log","native-ctest.xml","runtime-package.json","runtime-package-commands.log","runtime-package-initial-tool-output.json","receiver-process-first.json","receiver-dependency-replay.json","hydration-initial-tool-output.json"]
for name in evidence_names: put("qualification/"+name,(ROOT/"evidence"/name).read_bytes())
script_names=["qualify-native-portable.py","assemble-local-runtime.py","assemble-local-runtime-corrected.py","qualify-relocated-receiver.py","qualify-missing-dependency-replay.py"]
for name in script_names: put("qualification/"+name,(ROOT/name).read_bytes())
# All expected inputs and destinations are admitted before adding material.
for name,(data,permissions) in materials.items():
    target=PACKAGE/name
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("xb") as handle: handle.write(data)
    target.chmod(permissions)
records=[]
for path in sorted(PACKAGE.rglob("*")):
    if path.is_dir(): continue
    assert path.is_file() and not path.is_symlink(),str(path)
    data=path.read_bytes()
    records.append({"path":path.relative_to(PACKAGE).as_posix(),"size":len(data),"sha256":sha(data),"mode":mode(path)})
manifest={"schema":"capturesuite.native-receiver-contents/1","canonical_base":source["canonical_base"],"qualified_native_source":source["native_commit"],"runtime_files":87,"files":records}
with (PACKAGE/"CONTENTS.json").open("xb") as handle: handle.write(encoded(manifest))
manifest_data=(PACKAGE/"CONTENTS.json").read_bytes()
sums="\n".join(item["sha256"]+"  "+item["path"] for item in records)+"\n"+sha(manifest_data)+"  CONTENTS.json\n"
with (PACKAGE/"SHA256SUMS").open("xb") as handle: handle.write(sums.encode())
complete=[]
for path in sorted(PACKAGE.rglob("*")):
    if path.is_file():
        data=path.read_bytes()
        complete.append({"path":path.relative_to(PACKAGE).as_posix(),"size":len(data),"sha256":sha(data),"mode":mode(path)})
distribution=ROOT/"distribution"
distribution.mkdir(exist_ok=True)
archive=distribution/(PACKAGE.name+".tar.gz")
with archive.open("xb") as raw:
    with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode="w",format=tarfile.PAX_FORMAT) as tar:
            directories=[PACKAGE]+sorted(p for p in PACKAGE.rglob("*") if p.is_dir())
            for path in directories:
                name=PACKAGE.name if path==PACKAGE else PACKAGE.name+"/"+path.relative_to(PACKAGE).as_posix()
                info=tarfile.TarInfo(name); info.type=tarfile.DIRTYPE;info.mode=0o755;info.mtime=0
                tar.addfile(info)
            for item in complete:
                info=tarfile.TarInfo(PACKAGE.name+"/"+item["path"]);info.mode=0o755 if item["mode"]=="100755" else 0o644;info.size=item["size"];info.mtime=0
                tar.addfile(info,io.BytesIO((PACKAGE/item["path"]).read_bytes()))
receiving=ROOT/"archive-receiving"
receiving.mkdir()
extracted=receiving/"extracted"
extracted.mkdir()
with tarfile.open(archive,"r:gz") as tar:
    members=tar.getmembers()
    actual={member.name for member in members if member.isfile()}
    expected={PACKAGE.name+"/"+item["path"] for item in complete}
    assert actual==expected and all(member.isfile() or member.isdir() for member in members)
    tar.extractall(extracted,filter="data")
extracted_package=extracted/PACKAGE.name
for item in complete: verify(extracted_package/item["path"],item)
cwd=receiving/"unrelated-working-directory";cwd.mkdir()
env={key:value for key,value in os.environ.items() if not key.startswith(("DYLD_","LD_","CAPTURE_","MCAP_"))}
env["PATH"]="/usr/bin:/bin:/usr/sbin:/sbin"
call=subprocess.run([str(extracted_package/"bin/session_doctor"),"--help"],cwd=cwd,env=env,capture_output=True,timeout=10)
(receiving/"help.stdout").write_bytes(call.stdout)
(receiving/"help.stderr").write_bytes(call.stderr)
assert call.returncode==0 and call.stdout==b"Usage: session_doctor <path-to-session.mmsession>\n" and not call.stderr
for item in complete: verify(extracted_package/item["path"],item)
for item in runtime["files"]: verify(PACKAGE/item["path"],item)
for item in source["files"]: verify(ROOT/"source"/item["path"],item)
status=subprocess.check_output(["/usr/bin/git","-C",str(ROOT/"source"),"status","--porcelain"],text=True)
assert status=="",status
report={"schema":"capturesuite.native-receiver-archive/1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"archive":{"path":str(archive),"size":archive.stat().st_size,"sha256":sha(archive.read_bytes())},"package":str(PACKAGE),"contents_sha256":sha(manifest_data),"sha256sums_sha256":sha(sums.encode()),"payload_files":len(complete),"payload_bytes":sum(item["size"] for item in complete),"files":complete,"extracted":str(extracted_package),"exact_extracted_files":len(complete),"help":{"exit":call.returncode,"stdout":call.stdout.decode(),"stderr":call.stderr.decode(),"path":env["PATH"],"cwd":str(cwd)},"source_inputs_unchanged":len(source["files"]),"runtime_files_unchanged":len(runtime["files"]),"source_git_status":status,"qualification_phases":{"native_ctest":"17/17 passed; Linux GNU linker-wrapped cases unavailable on Mac","first_process":"7 passed; final case had harness filename failure before operation","dependency_replay":"1 focused replay passed; source and runtime unchanged"}}
receipt=ROOT/"evidence/archive-receiving.json"
with receipt.open("xb") as handle: handle.write(encoded(report))
print(json.dumps({"archive":report["archive"],"receipt":{"path":str(receipt),"sha256":sha(receipt.read_bytes())},"contents_sha256":report["contents_sha256"],"payload_files":len(complete),"payload_bytes":report["payload_bytes"],"help_exit":call.returncode,"source_inputs_unchanged":96,"runtime_files_unchanged":87}))
