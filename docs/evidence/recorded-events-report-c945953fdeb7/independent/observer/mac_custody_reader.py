import os,pathlib,json,hashlib,stat,datetime,re,subprocess
ROOT=pathlib.Path('/Users/me/Developer/capturesuite-recorded-report-receiving-c945953fdeb7')
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}
def snapshot():
 out=[]
 for base,dirs,names in os.walk(ROOT):
  if pathlib.Path(base)==ROOT:dirs[:]=[x for x in dirs if x!='browser']
  for name in sorted(names):
   p=pathlib.Path(base)/name;s=p.lstat()
   if not stat.S_ISREG(s.st_mode) or s.st_size>1024**2:raise RuntimeError('nonregular/oversized owned file')
   b=p.read_bytes()
   out.append({'path':p.relative_to(ROOT).as_posix(),**pin(b),'mode':format(stat.S_IMODE(s.st_mode),'04o'),'mtime_ns':str(s.st_mtime_ns),'allocated_bytes':s.st_blocks*512})
 return sorted(out,key=lambda x:x['path'])
v=subprocess.run(['/usr/bin/vm_stat'],capture_output=True,text=True,check=True,timeout=5).stdout
page=int(re.search(r'page size of (\d+) bytes',v).group(1))
mem=sum(int(re.search(r'^'+re.escape(k)+r':\s+(\d+)',v,re.M).group(1)) for k in ('Pages free','Pages inactive','Pages speculative'))*page
s=os.statvfs('/Users/me');before=snapshot()
guard={'free_disk_bytes':s.f_bavail*s.f_frsize,'conservative_memory_bytes':mem,'owned_bytes':sum(x['bytes'] for x in before),'owned_allocated_bytes':sum(x['allocated_bytes'] for x in before),'disk_floor_bytes':256*1024**2,'memory_floor_bytes':2*1024**3,'owned_cap_bytes':2*1024**2}
if guard['free_disk_bytes']<guard['disk_floor_bytes'] or mem<guard['memory_floor_bytes'] or max(guard['owned_bytes'],guard['owned_allocated_bytes'])>guard['owned_cap_bytes']:raise RuntimeError('frozen custody guard refused')
contents=[]
for item in before:
 if item['path'].endswith('.png'):continue
 b=(ROOT/item['path']).read_bytes()
 if pin(b)!={k:item[k] for k in ('bytes','sha256','git_blob')}:raise RuntimeError('artifact changed during export')
 contents.append({'path':item['path'],'content':b.decode('utf-8')})
after=snapshot()
if after!=before:raise RuntimeError('owned files changed during read-only custody')
print(json.dumps({'schema':'capturesuite-mac-readonly-native-custody-v1','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),'root':str(ROOT),'guard':guard,'files':before,'utf8_contents':contents,'unchanged_after_export':True,'physical_writes':0,'browser_calls':0,'node_calls':0,'png_transport':'Original PNG bytes are separately read via RDC image, verified against this binary pin and stored in exact-read-back base64 carrier.'},ensure_ascii=True))
