import base64,gzip,hashlib,io,json,pathlib,tarfile,xml.etree.ElementTree as ET,zipfile
root=pathlib.Path('/dev/shm/capturesuite-normal-37820127011-234cae4aee53')
dig=lambda b:hashlib.sha256(b).hexdigest()
specs={
 'python': {'artifact_id':11569102903,'bytes':1624472,'sha256':'61927abac7743720d508158e09edb399422ecece921b075dff8628da25709729','prefix':'python-20261008T175556Z-2ddcc792/'},
 'native': {'artifact_id':11569309376,'bytes':290404,'sha256':'74fcf7f6c42d2d13baf96177a8e7989308647fff046b1530d45dd90ae36109bd','prefix':'evidence/native-20261008T181343Z-9bf5cbfb/'}
}
members={}; results={}
for kind,s in specs.items():
 raw=(root/(kind+'.zip')).read_bytes()
 assert len(raw)==s['bytes'] and dig(raw)==s['sha256']
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  paths=[s['prefix']+p for p in ['receipt.json','source-manifest.json','pytest.xml','pytest.log']]
  paths+=['analysis-sources-234cae4aee53/windows-mainwindow.png'] if kind=='python' else ['windows-release/ctest-results.xml','windows-release/Testing/Temporary/LastTest.log']
  for p in paths: members[kind+'/'+p]=z.read(p)
  receipt=json.loads(z.read(s['prefix']+'receipt.json'))
  source=json.loads(z.read(s['prefix']+'source-manifest.json'))
  xml=z.read(s['prefix']+'pytest.xml'); log=z.read(s['prefix']+'pytest.log')
  assert receipt['accepted'] is True and receipt['process_exit']==0 and not receipt['problems']
  assert receipt['source_unchanged_during_test'] is True
  assert receipt['source_commit']=='d08a27ba0b147b9b7e4c0a5c30f9b56205add44a'
  assert source['commit']==receipt['source_commit']
  assert dig(xml)==receipt['junit_sha256'] and dig(log)==receipt['log_sha256']
  canonical=json.dumps(source['files'],sort_keys=True,separators=(',',':')).encode()
  assert dig(canonical)==source['tree_sha256']==receipt['source_tree_sha256']
  cases=ET.fromstring(xml).findall('.//testcase')
  counts={'tests':len(cases),'passed':sum(not any(c.find(t) is not None for t in ['failure','error','skipped']) for c in cases),'failures':sum(c.find('failure') is not None for c in cases),'errors':sum(c.find('error') is not None for c in cases),'skipped':sum(c.find('skipped') is not None for c in cases)}
  assert counts==receipt['counts']
  results[kind]={'artifact':{k:v for k,v in s.items() if k!='prefix'},'receipt':receipt,'source_manifest':source,'counts_recomputed_from_junit':counts,'scope_cases':[{'classname':c.get('classname'),'name':c.get('name'),'seconds':c.get('time'),'outcome':'passed'} for c in cases if c.get('classname')=='tests.ui.test_analysis_sources']}
  if kind=='native':
   ct=ET.fromstring(z.read('windows-release/ctest-results.xml')); cc=ct.findall('.//testcase')
   assert len(cc)==30 and ct.get('tests')=='30' and ct.get('failures')=='0'
   assert not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cc)
   results[kind]['ctest']={'tests':len(cc),'passed':len(cc),'failures':0,'errors':0,'skipped':0,'seconds':ct.get('time')}
p=results['python']['source_manifest']; n=results['native']['source_manifest']
assert p['worktree_dirty'] is False and n['worktree_dirty'] is True
assert len(p['files'])==1137 and len(n['files'])==1138
assert set(n['files'])-set(p['files'])=={'vcpkg/'} and n['files']['vcpkg/'] is None
assert not(set(p['files'])-set(n['files']))
assert all(n['files'][f]==h for f,h in p['files'].items())
assert len(results['python']['scope_cases'])==12
scope_hashes={f:p['files'][f] for f in ['desktop/capture_desktop/widgets_analysis_sources.py','desktop/capture_desktop/screen_analysis.py','tests/ui/test_analysis_sources.py']}
for v in results.values(): del v['source_manifest']
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w',format=tarfile.USTAR_FORMAT) as tar:
 for name,data in sorted(members.items()):
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
  tar.addfile(info,io.BytesIO(data))
archive=gzip.compress(buf.getvalue(),mtime=0)
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
 assert {m.name:tar.extractfile(m).read() for m in tar.getmembers()}==members
record={'schema':'capturesuite.normal-run-receiving.v1','run_id':37820127011,'python_job_id':113458700529,'native_job_id':113458700816,'qualified_head':'86ef1035136e89d25327671544a8635fc5f3900d','tested_synthetic_merge':'d08a27ba0b147b9b7e4c0a5c30f9b56205add44a','tested_and_actual_merge_tree':'6db730722413523f2d54d2feccdec622a6e2908d','actual_merge':'6ef303bbcf019d32288723a7741b99ce36003fd5','actual_merge_parents':['11cc78297d8d214407aea693548af4de855d61da','86ef1035136e89d25327671544a8635fc5f3900d'],'issue_62':{'state':'closed','reason':'completed','closed_at':'2026-10-08T18:48:01Z'},'results':results,'source_comparison':{'common_files':1137,'different_common_file_hashes':[],'only_python':[],'only_native':['vcpkg/'],'native_extra_value':None,'explanation':'The native build adds vcpkg/. source_snapshot records this directory as null and truthfully reports the worktree dirty; all 1,137 common source-file digests match the clean Python snapshot. Both runners record source unchanged during their tests.'},'scope_source_hashes':scope_hashes,'local_receiving_driver_history':{'initial_result':'An initial local artifact-inspection assertion required both snapshots to be clean and exited with AssertionError on the native dirty flag. The corrected receiver retains this difference and explicitly verifies the sole added vcpkg/ directory. No CI failure or product repair is inferred.'},'presentation':{'png':'python/analysis-sources-234cae4aee53/windows-mainwindow.png','visually_inspected':True,'finding':'Missing-glyph boxes throughout the offscreen Windows screenshot. Functional MainWindow receiving passed; readable Windows font presentation is not claimed.'},'custody':{'download_route':'Supported GitHub workflow-artifact download followed by ordinary cloud HTTPS transfer; both full ZIP digests and lengths matched immutable artifact metadata. No Mac retry.','selected_archive':'selected-evidence.tar.gz.b64','selected_archive_decoded_bytes':len(archive),'selected_archive_sha256':dig(archive),'members':[{'path':name,'bytes':len(data),'sha256':dig(data)} for name,data in sorted(members.items())],'full_zip_locations':[str(root/'python.zip'),str(root/'native.zip')]},'native_checkout_qualifier':'The older Mac checkout was interrupted by ENOSPC and remains partially materialized and unqualified. These hosted results make no new clean Mac checkout claim.'}
print(json.dumps({'receipt':record,'archive_base64':base64.b64encode(archive).decode()}))
