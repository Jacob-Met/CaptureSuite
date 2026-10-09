import os,sys,json,pathlib,hashlib,base64,stat,subprocess,re,datetime,time
ROOT=pathlib.Path('/Users/me/Developer/capturesuite-recorded-report-continuation-c945953fdeb7')
ORIGINAL=pathlib.Path('/Users/me/Developer/capturesuite-recorded-report-receiving-c945953fdeb7')
E=json.loads(base64.b64decode('eyJvcmlnaW5hbCI6W3sicGF0aCI6IkFVVEhPUklUWS5qc29uIiwiYnl0ZXMiOjU4NTcsInNoYTI1NiI6ImVkNDBhNjQyMTZjNGY5OTEyOTA2NDQ0MGJhNWEyOWI3Y2U4MmIyNWY5NWM4NjhjNGE0ZDM5YTE4OTY4ZjZkMWMiLCJnaXRfYmxvYiI6IjAzYTNlYWRmZDBlMGMwZTFjZGQ1ZmVlOTE4YTA5ZDA0MDVmNWNkZDMiLCJtb2RlIjoiMDQ0NCIsIm10aW1lX25zIjoiMTc5MTU0Mjk4NDkyNTc0NzY2NiJ9LHsicGF0aCI6IkNPTlRSQUNULm1kIiwiYnl0ZXMiOjE1MTg5LCJzaGEyNTYiOiJkNDBmMDRiZTNjYzg5OWZkYTc0MzU1YzFmMWQ2ODU0NzlkZjVkODMyNzJmYzRmOTU0MmRlMDFiM2NlY2ZkZDFhIiwiZ2l0X2Jsb2IiOiI3ZmQ5MzhiNzgzZmViNTZiM2Y3YmJiMjlhZTUyZDYwMTQ2MzU5NjAwIiwibW9kZSI6IjA0NDQiLCJtdGltZV9ucyI6IjE3OTE1NDI5ODQ5MjUzOTY4NzAifSx7InBhdGgiOiJPVVRFUi1FWEVDVVRJT04uanNvbiIsImJ5dGVzIjo1OTA1LCJzaGEyNTYiOiJhMDg0ZTczN2VkMGRjNDI3NGVlNDgyNTBmNjcyNzI2Y2Y3YzZjYWZkODM2ZDQ5ZWU4NGU1ODk2ZTVkNzc4OTQzIiwiZ2l0X2Jsb2IiOiIxMWMzZDkyMWI5ODdlZGFiNzIyNDE5ZGQyNjIyMTM2NzRhOTI5NTlkIiwibW9kZSI6IjA0NDQiLCJtdGltZV9ucyI6IjE3OTE1NDI5OTU5Njk2MzMyNTcifSx7InBhdGgiOiJTT1VSQ0UtUFJFUEFSQVRJT04uanNvbiIsImJ5dGVzIjoyNTg5LCJzaGEyNTYiOiIxNDU5ZTEyMzIwZjY0ZDJjNjcwYTI1MzZiMTAyYzA4NTI4ZTE2OGY2NjRlOGY2ZGI5YTgxOGQxOGVhZmIzYWJlIiwiZ2l0X2Jsb2IiOiIxYjYyMjcxNDExM2EwODE5ODFlZTlhMmViM2U0MjUxOWY3M2MzNWVhIiwibW9kZSI6IjA0NDQiLCJtdGltZV9ucyI6IjE3OTE1NDI5ODQ5MjU5MjE2NjgifSx7InBhdGgiOiJub2RlLnN0ZGVyci50eHQiLCJieXRlcyI6MCwic2hhMjU2IjoiZTNiMGM0NDI5OGZjMWMxNDlhZmJmNGM4OTk2ZmI5MjQyN2FlNDFlNDY0OWI5MzRjYTQ5NTk5MWI3ODUyYjg1NSIsImdpdF9ibG9iIjoiZTY5ZGUyOWJiMmQxZDY0MzRiOGIyOWFlNzc1YWQ4YzJlNDhjNTM5MSIsIm1vZGUiOiIwNDQ0IiwibXRpbWVfbnMiOiIxNzkxNTQyOTg0OTI4MjgzMTUzIn0seyJwYXRoIjoibm9kZS5zdGRvdXQudHh0IiwiYnl0ZXMiOjEwNzUsInNoYTI1NiI6ImY5Mzg0NWQzMzQ0ZjkzZGZlOWE1Nzc1ODc1YTE2ZDAwOTUyMGQwMTg4NGMwMGNkOWQ3NjIxZWIxNjA3NTQ4ZDkiLCJnaXRfYmxvYiI6ImQ3YTliODAwOWQ5YTc3NGFjYTMzNjk2NzUyYTZhOWVkYTg5YTJlYmYiLCJtb2RlIjoiMDQ0NCIsIm10aW1lX25zIjoiMTc5MTU0Mjk5NTkxNDExNzcxMyJ9LHsicGF0aCI6InJlY2VpdmVyLm1qcyIsImJ5dGVzIjoyMTQ4Niwic2hhMjU2IjoiMTFiZTUwMzgxOTg2ZGI4MjBiZGUwZjU1ZjM0NzU0NTFiNGQ1MjZjZWNiY2IzYjVkYjBmOWY3M2FjNTE4NGYzOCIsImdpdF9ibG9iIjoiMzU2Nzg0YTcwZTQ2ZTUzMmJiM2EzZjkzODQ3NWZkNjMzMWFhMDkyNCIsIm1vZGUiOiIwNDQ0IiwibXRpbWVfbnMiOiIxNzkxNTQyOTg0OTI1NTc1NDk3In0seyJwYXRoIjoicmVjb3JkZWQtZXZlbnRzLmh0bWwiLCJieXRlcyI6MTE5MDEsInNoYTI1NiI6ImY2NzY4ZDdkOGQzMDc4MmY2Y2E0MDBhYzliOTI1MzI1NGY5ZjVkNDgzODI1NTg3YzMxZGFmYmUyYzkyNWUxNmYiLCJnaXRfYmxvYiI6ImZhYzFmOGM5M2I3NDE2MGYxZWUyYjI2NzVkZTgyMzJiZDEyMGUwY2UiLCJtb2RlIjoiMDQ0NCIsIm10aW1lX25zIjoiMTc5MTU0Mjk4NDkyNTE4MjU3NiJ9LHsicGF0aCI6InJlc3VsdHMvMDEtb3ZlcnZpZXcucG5nIiwiYnl0ZXMiOjE1NTkwMiwic2hhMjU2IjoiMGQzN2ZjOTI4YThlODliNTVjYTI3NGE2NDYzYzQxYWE1NjJjZTE4ZjM0NTkxOTM1ZDE0YmExNDY0NzI2YmJmOCIsImdpdF9ibG9iIjoiODExY2JhODg4NjA2NjRhZGRhOWJjNTU3OGE2OWE1YjMwNTJmZmNlZiIsIm1vZGUiOiIwNjAwIiwibXRpbWVfbnMiOiIxNzkxNTQyOTg1NjQzNDU5MDI5In0seyJwYXRoIjoicmVzdWx0cy9FTlRSWS1ET00uanNvbiIsImJ5dGVzIjo2NDQ2LCJzaGEyNTYiOiI4ODYzOGJjM2NhYTI3ZWM3ZDAxNWE4ODI4NGNjOWUyNWJmYzExMjhlMzBhZTRiZGY4NWYxODBhYmI2YTgxMjk2IiwiZ2l0X2Jsb2IiOiJjOTRlZTE3ZGNjODU0Y2NkMmE1MTYyOWYxMDRkZWIzMjBlOGJjMDMxIiwibW9kZSI6IjA2MDAiLCJtdGltZV9ucyI6IjE3OTE1NDI5ODU1NTI4MzE4ODAifSx7InBhdGgiOiJyZXN1bHRzL0ZBSUxVUkUtSURFTlRJVFktQUZURVIuanNvbiIsImJ5dGVzIjoxODQyLCJzaGEyNTYiOiI0NzUwZjE3ODJmMjI4NDJkYTE3Y2U3NTVlZTUyNTUxZmM1MzFmNTVkOTQwNmIzYzUzZWNjZDVkZGQyOWY5YzA1IiwiZ2l0X2Jsb2IiOiI1NGYyNDVjZTFiZGJlYzA4NjQyZGFkNzdmYjE4Y2NlNGQ3ZjNiYTI4IiwibW9kZSI6IjA2MDAiLCJtdGltZV9ucyI6IjE3OTE1NDI5OTU5MTA5ODE1MTEifSx7InBhdGgiOiJyZXN1bHRzL0lERU5USVRZLUJFRk9SRS5qc29uIiwiYnl0ZXMiOjE4NDIsInNoYTI1NiI6IjQ3NTBmMTc4MmYyMjg0MmRhMTdjZTc1NWVlNTI1NTFmYzUzMWY1NWQ5NDA2YjNjNTNlY2NkNWRkZDI5ZjljMDUiLCJnaXRfYmxvYiI6IjU0ZjI0NWNlMWJkYmVjMDg2NDJkYWQ3N2ZiMThjY2U0ZDdmM2JhMjgiLCJtb2RlIjoiMDYwMCIsIm10aW1lX25zIjoiMTc5MTU0Mjk4NDk5OTcxOTA4NiJ9LHsicGF0aCI6InJlc3VsdHMvTUFDLVJFQ0VJUFQuanNvbiIsImJ5dGVzIjoxNzM2NCwic2hhMjU2IjoiNjZlNmYxODRmOTVlNDRiMTdhMjMzOWE0ODU1Njk1NmZiM2UxZjczYjRmYWRhMDQzNWRjYzJmNzhiZDAxOGVmNSIsImdpdF9ibG9iIjoiOTA4ZjU2OTQwMDIxMTNiZjk5YzEzY2Q1MjZhODlmNDU4YWM0OWEzYyIsIm1vZGUiOiIwNjAwIiwibXRpbWVfbnMiOiIxNzkxNTQyOTk1OTEzODE3NDE4In0seyJwYXRoIjoicmVzdWx0cy9jaHJvbWUuc3RkZXJyLnR4dCIsImJ5dGVzIjoyNzkyLCJzaGEyNTYiOiJkZmRlMWZhMjgzNmFjYWM0MmNlYWRkYTc1NWZkZThhYmZiY2FkMDkxMmFhOWNhNzhmZDA5NThhNjlhNzcwZmE0IiwiZ2l0X2Jsb2IiOiIzZTM5NjVkYjBmYzYwMmVlNDFmZDVhNDgyMmM0YTQzNGI5M2QxYTAyIiwibW9kZSI6IjA2MDAiLCJtdGltZV9ucyI6IjE3OTE1NDI5OTU5MDk5MTczNzQifSx7InBhdGgiOiJyZXN1bHRzL2Nocm9tZS5zdGRvdXQudHh0IiwiYnl0ZXMiOjAsInNoYTI1NiI6ImUzYjBjNDQyOThmYzFjMTQ5YWZiZjRjODk5NmZiOTI0MjdhZTQxZTQ2NDliOTM0Y2E0OTU5OTFiNzg1MmI4NTUiLCJnaXRfYmxvYiI6ImU2OWRlMjliYjJkMWQ2NDM0YjhiMjlhZTc3NWFkOGMyZTQ4YzUzOTEiLCJtb2RlIjoiMDYwMCIsIm10aW1lX25zIjoiMTc5MTU0Mjk5NTkwOTc1NjM3MiJ9XSwicHJvcG9zYWwiOlt7InBhdGgiOiJyZWNlaXZlci5tanMiLCJieXRlcyI6MjYwNDMsInNoYTI1NiI6IjExZjQ5ODg0YjgzMTkwZDFlYjM5YWFkZjVmMmUwOWUyNmEzMzE1NjQ1MGQ4MGMzNDczZTYwMWRkMTZlOWI3MTYiLCJnaXRfYmxvYiI6IjU2N2YzZTNlYTEwNDAyZjRlODhhNDMxY2MwZmEwYjQ5OTUyYmYyYWEifSx7InBhdGgiOiJDT1JSRUNUSU9OLUNPTlRSQUNULm1kIiwiYnl0ZXMiOjEwOTE5LCJzaGEyNTYiOiIxMDFmMGVlYjJmYTI1Y2VlMWE5ZWMzNTIyMDIyMTFiYWJlZTNhYjMxYmIzODMxM2QxMjhiNDZjYzdjZWE5NzE2IiwiZ2l0X2Jsb2IiOiJhNTE3NGNkZGMxMTAwMWUyZDIxNGNlNzQzODJlY2EzMDA5ZDkyODFkIn0seyJwYXRoIjoiUkVWSVNJT04uanNvbiIsImJ5dGVzIjo1ODgwLCJzaGEyNTYiOiIzZmQ3YjdjMWQxMjc1ZTZkNjdhNmFkNDYzNzJhZTk5MDQ4NDhjMmI1MTlmNDQ1ZmNjZjM5YWJlN2U1N2FhZWY3IiwiZ2l0X2Jsb2IiOiI2ZWU1OGVlMzAyOWY3ZjEzM2JjNDdmMmI5ZmUzMTAwOGIxYmI4MGQwIn1dLCJvdXRlcl9naXQiOiIxMWY0ZTAxZWM0ZjFkM2MzM2FmNzU3Y2Q2ZTZmOTIzMWM3NDJhNzZiIiwicnVudGltZSI6eyJweXRob24iOnsicGF0aCI6Ii9MaWJyYXJ5L0ZyYW1ld29ya3MvUHl0aG9uLmZyYW1ld29yay9WZXJzaW9ucy8zLjEzL2Jpbi9weXRob24zLjEzIiwiYnl0ZXMiOjExOTYwMCwic2hhMjU2IjoiNDA2ZDczZDA3ZTMzZTE2NGQ5ODYzMjZmZGUwMGI4NWMyYjhmNGVkMmMzMzI3ODE0MmM4NDMxNTg4ZmUyZGYxNCIsIm1vZGUiOiIwbzc3NSIsIm10aW1lX25zIjoiMTc1NTE5MjgwMDAwMDAwMDAwMCJ9LCJub2RlIjp7InBhdGgiOiIvb3B0L2hvbWVicmV3L0NlbGxhci9ub2RlLzI2LjMuMC9iaW4vbm9kZSIsImJ5dGVzIjo2ODM4NCwic2hhMjU2IjoiNTY2OTRjODFiMDkzY2M4ZGEyNzNmYTAxN2NmOTE3NjViMzY1M2U1ZjY0ZjE2NzI3OTc2ZmZhYTg3YjJiNmIzMSIsIm1vZGUiOiIwbzU1NSIsIm10aW1lX25zIjoiMTc4MTA0MzY2NDI5MDk3NzYxMCJ9LCJjaHJvbWUiOnsicGF0aCI6Ii9BcHBsaWNhdGlvbnMvR29vZ2xlIENocm9tZS5hcHAvQ29udGVudHMvTWFjT1MvR29vZ2xlIENocm9tZSIsImJ5dGVzIjozNjc2OTYsInNoYTI1NiI6Ijc2NGY1ZjZlZTUyM2U2ZDUyY2FmNmU1NmNlNzUwMWU5MzJjNGY2ZTUyZDA2ZDI2Nzg4N2NiN2VhNzAzNTAxMDIiLCJtb2RlIjoiMG83NzUiLCJtdGltZV9ucyI6IjE3OTE1MDIxMzMxOTg1NDU2MTUifX19'))
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}
def identity(p):
 s=p.lstat()
 if not stat.S_ISREG(s.st_mode):raise RuntimeError('regular file required: '+str(p))
 b=p.read_bytes();a=p.lstat()
 if (s.st_ino,s.st_size,s.st_mtime_ns)!=(a.st_ino,a.st_size,a.st_mtime_ns):raise RuntimeError('changed during read')
 return {**pin(b),'mode':format(stat.S_IMODE(s.st_mode),'04o'),'mtime_ns':str(s.st_mtime_ns),'allocated_bytes':s.st_blocks*512},b
def inventory(root,content=False):
 out={}
 for base,dirs,names in os.walk(root,followlinks=False):
  if pathlib.Path(base)==root:dirs[:]=[n for n in dirs if n!='browser']
  for name in dirs+names:
   if (pathlib.Path(base)/name).is_symlink():raise RuntimeError('owned nonprofile symlink')
  for name in names:
   p=pathlib.Path(base)/name;rel=p.relative_to(root).as_posix();meta,b=identity(p)
   if len(b)>1024**2:raise RuntimeError('per-file read cap')
   out[rel]=meta
   if content and p.suffix!='.png':out[rel]['content']=b.decode('utf-8')
 return dict(sorted(out.items()))
def sans_content(row):return {k:v for k,v in row.items() if k!='content'}
def equal_expected(actual,expected):return all(actual[k]==expected[k] for k in ('bytes','sha256','git_blob','mode','mtime_ns'))
started=time.monotonic()
ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,pgid=,command='],capture_output=True,text=True,check=True,timeout=5)
if len(ps.stdout.encode())>2*1024**2:raise RuntimeError('process snapshot cap')
rows=[]
for line in ps.stdout.splitlines():
 m=re.match(r'\s*(\d+)\s+(\d+)\s+(\d+)\s+(.+)',line)
 if m:
  row={'pid':int(m[1]),'ppid':int(m[2]),'pgid':int(m[3]),'command':m[4]}
  if row['pid'] in (81736,81778) or row['pgid']==81778 or (m[4].startswith('/Applications/Google Chrome.app/') and str(ROOT/'browser'/'profile') in m[4]):rows.append(row)
v=subprocess.run(['/usr/bin/vm_stat'],capture_output=True,text=True,check=True,timeout=5).stdout
page=int(re.search(r'page size of (\d+) bytes',v).group(1));mem=sum(int(re.search(r'^'+re.escape(k)+r':\s+(\d+)',v,re.M).group(1)) for k in ('Pages free','Pages inactive','Pages speculative'))*page
s=os.statvfs('/Users/me');capacity={'disk_free_bytes':s.f_bavail*s.f_frsize,'conservative_memory_bytes':mem}
if capacity['disk_free_bytes']<256*1024**2 or mem<2*1024**3:raise RuntimeError('read-only custody capacity guard')
before=inventory(ROOT,True);original_before=inventory(ORIGINAL)
expected_original={x['path']:x for x in E['original']}
original_ok=set(original_before)==set(expected_original) and all(equal_expected(original_before[p],e) for p,e in expected_original.items())
outer=before['OUTER-EXECUTION.json']
if outer['git_blob']!=E['outer_git']:raise RuntimeError('actual outer receipt pin')
outer_data=json.loads(outer['content'])
protected=outer_data['protected_inputs_before']
new_input_ok=all(equal_expected(before[p],e) for p,e in protected.items())
runtime={}
for name,expected in E['runtime'].items():
 meta,b=identity(pathlib.Path(expected['path']).resolve(strict=True));runtime[name]=meta
 if meta['bytes']!=expected['bytes'] or meta['sha256']!=expected['sha256']:raise RuntimeError('runtime identity changed')
runtime_ok=all(equal_expected(runtime[p],e) for p,e in outer_data['runtime_before'].items())
after=inventory(ROOT);original_after=inventory(ORIGINAL)
new_stable={p:sans_content(row) for p,row in before.items()}==after
old_stable=original_before==original_after
statics={'logical':sum(x['bytes'] for x in after.values())+sum(x['bytes'] for x in original_after.values()),
         'allocated':sum(x['allocated_bytes'] for x in after.values())+sum(x['allocated_bytes'] for x in original_after.values())}
if max(statics.values())>2*1024**2:raise RuntimeError('combined static cap')
missing_expected_completion=[p for p in ['results/MAC-RECEIPT.json','results/IDENTITY-AFTER.json','results/chrome.stdout.txt','results/chrome.stderr.txt'] if p not in after]
result={'schema':'capturesuite-continuation-readonly-closure-custody-v1','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'pid':os.getpid(),'elapsed_seconds':time.monotonic()-started,'zero_files_written':True,'zero_application_or_browser_calls':True,
        'source_root':str(ROOT),'original_root':str(ORIGINAL),'capacity':capacity,'owned_pid_group_snapshot':rows,
        'observed_owned_pid_group_absent':len(rows)==0,'node_reaped_by_original_outer':outer_data['node_reaped_by_wait'],
        'original_outer_exit_is_external_tool_evidence':'81736 actual exit 1, separately retained',
        'original_expected_15_exact':original_ok,'new_four_protected_inputs_exact':new_input_ok,'runtime_before_after_exact':runtime_ok,
        'new_custody_files_stable_during_read':new_stable,'original_files_stable_during_read':old_stable,
        'combined_static':statics,'missing_normal_completion_files':missing_expected_completion,
        'new_files':[{'path':p,**row} for p,row in before.items()],
        'original_files':[{'path':p,**row} for p,row in original_after.items()],
        'runtime':runtime,
        'scope':'Read-only byte custody and owned closure after the failed outer census. No actuation, report regeneration, retry or source change.'}
print(json.dumps(result,ensure_ascii=False,separators=(',',':')),flush=True)
raise SystemExit(0 if original_ok and new_input_ok and runtime_ok and new_stable and old_stable and not rows else 1)
