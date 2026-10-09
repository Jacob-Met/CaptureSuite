import datetime,hashlib,json,os,resource,stat,sys
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))
resource.setrlimit(resource.RLIMIT_FSIZE,(2097152,2097152))
resource.setrlimit(resource.RLIMIT_CPU,(10,12))
root=Path(sys.argv[1]); offset=int(sys.argv[2]); previous=sys.argv[3]; chunk_sha=sys.argv[4]; raw=sys.argv[5].encode("utf-8")
expected="/dev/capturesuite-recorded-events-c945953fdeb7-a799b257-9ed0-4ce8-a2fa-1dcff3b8dea8"
if str(root)!=expected or hashlib.sha256(raw).hexdigest()!=chunk_sha:
 raise RuntimeError("unexpected transport root or chunk identity")
exe=Path(sys.executable).resolve()
if str(exe)!="/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12" or sys.version_info[:2]!=(3,12):
 raise RuntimeError("supported runtime not selected")
runtime_sha=hashlib.sha256(exe.read_bytes()).hexdigest()
if runtime_sha!="fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7":
 raise RuntimeError("runtime changed")
space=os.statvfs("/dev")
free=space.f_bavail*space.f_frsize
memory={s.split(":",1)[0]:s.split(":",1)[1] for s in Path("/proc/meminfo").read_text().splitlines()}
available=int(memory["MemAvailable"].split()[0])*1024
guard={"time_utc":datetime.datetime.now(datetime.UTC).isoformat(),"pid":os.getpid(),"uid":os.getuid(),"gid":os.getgid(),"python":str(exe),"python_sha256":runtime_sha,"free_bytes":free,"mem_available_bytes":available,"floor_free_bytes":134217728,"floor_mem_available_bytes":2147483648,"owned_cap_bytes":2097152}
if free<134217728 or available<2147483648:
 print(json.dumps({"admission_refused":guard}));raise SystemExit(78)
os.umask(0o077)
path=root/"INPUT-PAYLOAD.json"
if offset==0:
 if os.path.lexists(root):raise RuntimeError("exclusive target exists")
 if previous!=hashlib.sha256(b"").hexdigest():raise RuntimeError("unexpected initial prefix")
 root.mkdir(mode=0o700)
 descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
else:
 if root.is_symlink() or not root.is_dir():raise RuntimeError("transport root changed")
 old=path.read_bytes()
 if len(old)!=offset or hashlib.sha256(old).hexdigest()!=previous:raise RuntimeError("transport prefix changed")
 descriptor=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
with os.fdopen(descriptor,"wb") as stream:
 if stream.write(raw)!=len(raw):raise OSError("short chunk write")
 stream.flush();os.fsync(stream.fileno())
actual=path.read_bytes()
if len(actual)!=offset+len(raw):raise RuntimeError("unexpected retained payload length")
st=path.lstat()
print(json.dumps({"guard":guard,"path":str(path),"offset":offset,"chunk_bytes":len(raw),"chunk_sha256":chunk_sha,"retained_bytes":len(actual),"retained_sha256":hashlib.sha256(actual).hexdigest(),"mode":format(stat.S_IMODE(st.st_mode),"04o"),"mtime_ns":str(st.st_mtime_ns),"inode":st.st_ino,"device":st.st_dev,"candidate_executed":False}))
