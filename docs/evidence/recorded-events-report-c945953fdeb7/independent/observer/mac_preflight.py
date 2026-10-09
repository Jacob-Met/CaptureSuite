import os,json,pathlib,subprocess,re,hashlib,plistlib,datetime
ROOT=pathlib.Path('/Users/me/Developer/capturesuite-recorded-report-receiving-c945953fdeb7')
def pin(p):
 p=pathlib.Path(p).resolve();s=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return {'path':str(p),'bytes':s.st_size,'sha256':h.hexdigest(),'mode':oct(s.st_mode&0o7777),'mtime_ns':str(s.st_mtime_ns)}
v=subprocess.run(['/usr/bin/vm_stat'],capture_output=True,text=True,check=True,timeout=5).stdout
page=int(re.search(r'page size of (\d+) bytes',v).group(1))
mem=sum(int(re.search(r'^'+re.escape(k)+r':\s+(\d+)',v,re.M).group(1)) for k in ('Pages free','Pages inactive','Pages speculative'))*page
s=os.statvfs('/Users/me');free=s.f_bavail*s.f_frsize
out={'schema':'capturesuite-mac-preparation-readonly-admission-v1','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),'root':str(ROOT),'root_absent':not os.path.lexists(ROOT),'disk_free_bytes':free,'conservative_memory_bytes':mem,'disk_floor_bytes':256*1024**2,'memory_floor_bytes':2*1024**3,'owned_files_written':0,'browser_calls':0}
out['admitted']=out['root_absent'] and free>=256*1024**2 and mem>=2*1024**3
if out['admitted']:
 out['runtime']={'python':pin('/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'),'node':pin('/opt/homebrew/bin/node'),'chrome':pin('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')}
 with open('/Applications/Google Chrome.app/Contents/Info.plist','rb') as f:out['chrome_version']=plistlib.load(f)['CFBundleShortVersionString']
print(json.dumps(out,ensure_ascii=True))
raise SystemExit(0 if out['admitted'] else 2)
