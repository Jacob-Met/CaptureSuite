# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import ast,datetime,hashlib,json,subprocess
ROOT=Path("/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef")
PUBLICATION=ROOT/"publication"
PREFIX="docs/receiving/macos-session-doctor-5f566b5ec8ef/"
PACKAGE=ROOT/"receiver-final/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def encoded(value):return (json.dumps(value,indent=2,ensure_ascii=False)+"\n").encode()
inputs=json.loads((ROOT/"publication-inputs.json").read_text())
assert inputs["comparison"]["qualified_input_changes"]==[]
progress=inputs["progress_content"].encode()
assert blob(progress)==inputs["comparison"]["progress_base_git_blob"]
materials={PREFIX+"README.md":inputs["readme"].encode(),"docs/design/research/PROGRESS.md":progress+inputs["progress_append"].encode()}
for source,name in [("README.md","package-README.md"),("BUILD.md","BUILD.md"),("NOTICE.md","NOTICE.md")]:
    materials[PREFIX+name]=(PACKAGE/source).read_bytes()
evidence_names=["claim.json","source-inputs.json","mcap-source.json","mcap-clone.log","native-qualification-first.json","native-configure.log","native-build.log","native-ctest.log","native-ctest.xml","runtime-package.json","runtime-package-commands.log","runtime-package-initial-tool-output.json","receiver-process-first.json","receiver-dependency-replay.json","hydration-initial-tool-output.json","archive-receiving.json","archive-receiving-final.json","historical-receiver-custody.json"]
for name in evidence_names:materials[PREFIX+"evidence/"+name]=(ROOT/"evidence"/name).read_bytes()
historical=json.loads(materials[PREFIX+"evidence/historical-receiver-custody.json"])
assert historical["all_unchanged"] and len(historical["files"])==6
peer=Path("/Users/me/capturesuite-package-review-20261008-5f566b5ec8ef/coordination-review.json").read_bytes()
assert sha(peer)=="546a9d6812e51ae93791762e54268bdd34d955e16664c71dd04b83df1bbe7e1b"
materials[PREFIX+"evidence/coordination-review.json"]=peer
materials[PREFIX+"evidence/receiving-base.json"]=encoded(inputs["comparison"])
materials[PREFIX+"evidence/source-notices-manifest.json"]=(PACKAGE/"source-notices-manifest.json").read_bytes()
materials[PREFIX+"evidence/dependency-notices-manifest.json"]=(PACKAGE/"notices/manifest.json").read_bytes()
helpers=["hydrate-source.py","hydrate-source-corrected.py","prepare-mcap.py","qualify-native-portable.py","assemble-local-runtime.py","assemble-local-runtime-corrected.py","qualify-relocated-receiver.py","qualify-missing-dependency-replay.py","finalize-native-receiver.py","complete-source-notices.py","freeze-publication.py"]
correspondence=[]
for name in helpers:
    original=(ROOT/name).read_bytes()
    text=original.decode("utf-8")
    published=original if text.startswith("# SPDX-License-Identifier: GPL-3.0-only\n") else b"# SPDX-License-Identifier: GPL-3.0-only\n"+original
    equal=ast.dump(ast.parse(original),include_attributes=False)==ast.dump(ast.parse(published),include_attributes=False)
    assert equal,name
    assert published.startswith(b"# SPDX-License-Identifier: GPL-3.0-only\n"),name
    materials[PREFIX+"scripts/"+name]=published
    correspondence.append({"path":"scripts/"+name,"original_native_path":str(ROOT/name),"original_sha256":sha(original),"published_sha256":sha(published),"header_added":published!=original,"ast_identical":equal})
materials[PREFIX+"evidence/helper-header-correspondence.json"]=encoded({"purpose":"Repository SPDX declarations on publication copies; executed originals and runtime are preserved.","files":correspondence})
# No output exists until every source has passed admission.
for path,data in materials.items():data.decode("utf-8")
PUBLICATION.mkdir()
for name,data in materials.items():
    path=PUBLICATION/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as handle:handle.write(data)
    path.chmod(0o644)
def git(*argv):
    return subprocess.check_output(["/usr/bin/git","-C",str(PUBLICATION),*argv],text=True,stderr=subprocess.STDOUT)
git("init","-b","receiving/canonical-mac-session-doctor-5f566b5ec8ef")
git("add","--all")
git("-c","user.name=ChatGPT HAMON receiving worker","-c","user.email=chatgpt+5f566b5ec8ef@users.noreply.github.com","commit","-m","Preserve canonical Mac session-doctor receiver and native qualification")
commit=git("rev-parse","HEAD").strip()
tree=git("rev-parse","HEAD^{tree}").strip()
assert git("status","--porcelain")==""
files=[]
payload_files=[]
for name in sorted(materials):
    path=PUBLICATION/name;data=path.read_bytes()
    assert data==materials[name]
    record={"path":name,"size":len(data),"sha256":sha(data),"git_blob_sha":blob(data),"mode":"100644"}
    files.append(record);payload_files.append({**record,"content":data.decode("utf-8")})
manifest={"schema":"capturesuite.receiving-publication/1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"canonical_base":inputs["comparison"]["canonical_base"],"receiving_base":inputs["comparison"]["receiving_base"],"receiving_base_tree":inputs["comparison"]["receiving_tree"],"native_publication_commit":commit,"native_publication_tree":tree,"git_status":"","files":files}
with (ROOT/"publication-manifest.json").open("xb") as handle:handle.write(encoded(manifest))
with (ROOT/"publication-payload.json").open("xb") as handle:handle.write(encoded({"files":payload_files}))
summary={"native_publication_commit":commit,"native_publication_tree":tree,"files":len(files),"bytes":sum(i["size"] for i in files),"manifest_path":str(ROOT/"publication-manifest.json"),"manifest_sha256":sha((ROOT/"publication-manifest.json").read_bytes()),"bounded_docs":[i for i in files if i["path"].endswith(("/README.md","/package-README.md","/BUILD.md","/NOTICE.md"))]}
print(json.dumps(summary))
