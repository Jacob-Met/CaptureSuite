import sys,json,re,hashlib,xml.etree.ElementTree as ET,math
print("READY",flush=True)
payload=json.loads(sys.stdin.buffer.readline())
expected="9e9204f76b105426b0affaa74733175c052f27ba"
out={"schema":"capturesuite.root-final-main-receiving.v1","checkout":expected,"logs":{}}
decoded={}
for key,raw in payload.items():
    b=raw.encode("utf-8")
    clean="\n".join(re.sub(r"^\d{4}-\d\d-\d\dT[0-9:.]+Z ","",line) for line in raw.splitlines())
    assert expected in clean.splitlines(),(key,"checkout SHA absent")
    objects=[]
    for m in re.finditer(r"(?m)^\{",clean):
        try:
            value,end=json.JSONDecoder().raw_decode(clean[m.start():])
            if isinstance(value,dict): objects.append(value)
        except json.JSONDecodeError: pass
    decoded[key]=(clean,objects)
    out["logs"][key]={"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"git_blob":hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()}
py=[x for x in decoded["python"][1] if x.get("schema")=="capturesuite.test-receipt.v1"]
native=[x for x in decoded["cmake"][1] if x.get("schema")=="capturesuite.native-test-receipt.v1"]
assert len(py)==len(native)==1
p,n=py[0],native[0]
for x in (p,n):
    assert x["accepted"] and x["process_exit"]==0 and not x["problems"]
    assert x["source_commit"]==expected and x["source_unchanged_during_test"] is True
    assert x["github"]["GITHUB_RUN_ID"]=="37840896851" and x["github"]["GITHUB_EVENT_NAME"]=="push"
assert p["counts"]=={"tests":663,"passed":657,"failures":0,"errors":0,"skipped":6}
assert p["source_file_count"]==1208 and p["source_worktree_dirty"] is False
assert 0<p["seconds"]<300
assert n["counts"]=={"tests":6,"passed":6,"failures":0,"errors":0,"skipped":0}
assert n["source_worktree_dirty"] is True
ctest=re.findall(r"100% tests passed, 0 tests failed out of (\d+)",decoded["cmake"][0])
assert ctest==["30"]
w=[x for x in decoded["python"][1] if "workbench_cases" in x]
assert len(w)==1
w=w[0]
assert w["source_commit"]==expected and w["source_tree_sha256"]==p["source_tree_sha256"]
assert w["junit_sha256"]==p["junit_sha256"] and w["junit_bytes"]==94606
cases=w["workbench_cases"]
assert len(cases)==32
seen={}
for row in cases:
    case=ET.fromstring(row["xml"])
    assert case.tag=="testcase" and case.attrib["name"]==row["name"]
    assert case.attrib["classname"]=="tests.ui.test_analysis_predictions"
    assert not any(case.find(tag) is not None for tag in ("failure","error","skipped"))
    seconds=float(case.attrib["time"])
    assert math.isfinite(seconds) and seconds>=0
    assert row["name"] not in seen
    seen[row["name"]]={"seconds":seconds,"properties":{p.attrib["name"]:p.attrib["value"] for p in case.findall("properties/property")}}
required=["test_evaluation_controls_in_actual_minimum_main_window","test_actual_qt_file_choice_cancel_and_reselection","test_actual_qt_file_choice_error_unwinds_without_replacing_path","test_analysis_button_space_overrides_only_its_application_shortcut","test_actual_qt_leading_space_is_exact_or_refuses_without_replacing_path"]
assert all(k in seen for k in required)
assert seen[required[-1]]["properties"]["literal_file_choice"] in ("exact-selection","bounded-refusal")
out.update({"accepted":True,"python_receipt":p,"native_receipt":n,"ctest":{"passed":30,"failed":0},"emitted_workbench_xml_cases":32,"required_cases":{k:seen[k] for k in required},"junit_complete_bytes":w["junit_bytes"],"full_junit_scope":"Hosted read-only observer hashed complete JUnit and emitted every workbench testcase; no local artifact ZIP download or fresh test execution."})
print(json.dumps(out,ensure_ascii=False))
