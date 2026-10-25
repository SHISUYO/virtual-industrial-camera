"""Windows user-mode service lifecycle. No network configuration or driver changes.

Backend outlives the GUI. Local named-pipe commands include version, fixed length,
request id and device id; PID creation time/path guard against process reuse.
"""
import ctypes,ctypes.wintypes as w,hashlib,json,os,struct,subprocess,sys,time,uuid,zipfile
from pathlib import Path

K=ctypes.WinDLL('kernel32',use_last_error=True)
def api(name,args,result=w.BOOL):
    fn=getattr(K,name);fn.argtypes=args;fn.restype=result;return fn
open_process=api('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],w.HANDLE)
close=api('CloseHandle',[w.HANDLE])
process_times=api('GetProcessTimes',[w.HANDLE,ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME)])
query_path=api('QueryFullProcessImageNameW',[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)])
wait=api('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD)
create_file=api('CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,w.LPVOID,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE)
write=api('WriteFile',[w.HANDLE,w.LPCVOID,w.DWORD,ctypes.POINTER(w.DWORD),w.LPVOID])
read=api('ReadFile',[w.HANDLE,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD),w.LPVOID])
wait_pipe=api('WaitNamedPipeW',[w.LPCWSTR,w.DWORD])
set_pipe_mode=api('SetNamedPipeHandleState',[w.HANDLE,ctypes.POINTER(w.DWORD),w.LPVOID,w.LPVOID])
INVALID=ctypes.c_void_p(-1).value
MESSAGE=struct.Struct('<4sHHIQ16sI')
DEVICE=b'VICGE000001'.ljust(16,b'\0')
ROOT=Path(__file__).resolve().parents[2]
if getattr(sys,'frozen',False):BACKEND=Path(sys.executable).parent/'backend/VICGigEControl.exe'
else:BACKEND=ROOT/'out/g05/build/VICGigEControl.exe'

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def process_identity(pid):
    h=open_process(0x1000|0x100000,False,pid)
    if not h:return None
    try:
        if wait(h,0)!=258:return None
        created=w.FILETIME();other=[w.FILETIME() for _ in range(3)];name=ctypes.create_unicode_buffer(32768);length=w.DWORD(len(name))
        if not process_times(h,ctypes.byref(created),*[ctypes.byref(x) for x in other]) or not query_path(h,0,name,ctypes.byref(length)):return None
        return {'pid':pid,'created':(created.dwHighDateTime<<32)|created.dwLowDateTime,'exe':str(Path(name.value).resolve())}
    finally:close(h)

def matches(record):
    identity=process_identity(record['identity']['pid'])
    return bool(identity and identity['created']==record['identity']['created'] and identity['exe'].casefold()==record['identity']['exe'].casefold() and Path(identity['exe']).name=='VICGigEControl.exe')

def command(record,kind=2):
    if not matches(record):raise RuntimeError('Recorded camera process is no longer running')
    name=record['pipe']
    if not name.startswith('\\\\.\\pipe\\VIC.G05.') or len(name.rsplit('.',1)[-1])!=32:raise RuntimeError('Invalid session control pipe')
    # PIPE_NOWAIT bounds the client's response loop; never blocks a GUI thread.
    deadline=time.monotonic()+3;h=INVALID
    while time.monotonic()<deadline:
        h=create_file(name,0xc0000000,0,None,3,0,None)
        if h!=INVALID:break
        wait_pipe(name,100);time.sleep(.02)
    if h==INVALID:raise RuntimeError('Camera control channel is unavailable')
    try:
        mode=w.DWORD(2|1) # message read mode + nonblocking client
        if not set_pipe_mode(h,ctypes.byref(mode),None,None):raise ctypes.WinError(ctypes.get_last_error())
        request=time.monotonic_ns()&0xffffffffffffffff;data=MESSAGE.pack(b'VIC1',1,kind,MESSAGE.size,request,DEVICE,0);count=w.DWORD()
        if not write(h,data,len(data),ctypes.byref(count),None) or count.value!=len(data):raise RuntimeError('Control write failed')
        response=ctypes.create_string_buffer(MESSAGE.size)
        while time.monotonic()<deadline:
            if read(h,response,MESSAGE.size,ctypes.byref(count),None):break
            error=ctypes.get_last_error()
            if error not in (232,536):raise ctypes.WinError(error)
            time.sleep(.01)
        else:raise RuntimeError('Control response timeout')
        if count.value!=MESSAGE.size:raise RuntimeError('Truncated control response')
        magic,version,cmd,length,rid,device,status=MESSAGE.unpack(response.raw)
        if (magic,version,cmd,length,rid,device)!=(b'VIC1',1,kind,MESSAGE.size,request,DEVICE):raise RuntimeError('Control response identity mismatch')
        write(h,b'\x06',1,ctypes.byref(count),None)
        if status:raise RuntimeError('Control rejected command: '+str(status))
    finally:close(h)

def enumerate_adapters():
    # Read-only inventory; no Set-/New-/Enable-/Disable- network commands.
    ps="""$ErrorActionPreference='Stop';$items=@(Get-NetAdapter -IncludeHidden | Where-Object {$_.Name -eq 'VIC-PoC-TAP' -and $_.InterfaceDescription -match 'TAP-Windows'} | ForEach-Object {$a=$_;Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '169.254.*' -and $_.PrefixLength -eq 24} | ForEach-Object {[pscustomobject]@{name=$a.Name;guid=[string]$a.InterfaceGuid;index=$a.ifIndex;ip=$_.IPAddress;prefix=$_.PrefixLength;skip=$_.SkipAsSource;status=[string]$a.Status;driver=$a.DriverVersion}}});ConvertTo-Json -InputObject $items -Compress"""
    run=subprocess.run(['powershell.exe','-NoProfile','-Command',ps],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    if run.returncode:raise RuntimeError(run.stderr.decode('utf-8',errors='replace'))
    return json.loads(run.stdout.decode('utf-8-sig'))

class Service:
    def __init__(self,data_dir=None,backend=None):
        self.data=Path(data_dir or Path(os.environ['LOCALAPPDATA'])/'VIC/Control');self.data.mkdir(parents=True,exist_ok=True)
        self.backend=Path(backend or BACKEND).resolve();self.record=None;self.process=None
        try:
            record=json.loads((self.data/'active.json').read_text(encoding='utf-8'))
            # Retain the last session after shutdown so failure logs can still be
            # exported on reopening. alive() separately verifies process identity.
            if record.get('protocol')==1 and Path(record['session']).parent==self.data/'sessions':self.record=record
        except (OSError,ValueError,KeyError):pass
    def alive(self):return self.record is not None and matches(self.record)
    def extra_arguments(self,settings,session):return []
    def start(self,settings,adapter):
        if self.alive():raise RuntimeError('A camera is already running')
        if not self.backend.is_file():raise RuntimeError('G05 backend executable is missing')
        token=uuid.uuid4().hex;session=self.data/'sessions'/(time.strftime('%Y%m%d_%H%M%S')+'_'+token[:8]);session.mkdir(parents=True)
        pipe='\\\\.\\pipe\\VIC.G05.'+token
        args=[str(self.backend),'--live','--owned-adapter-consent','--adapter-guid',adapter['guid'],'--host-ip',adapter['ip'],'--camera-ip',settings['camera_ip'],'--seconds',str(settings.get('seconds',28800)),
            '--log',str(session/'camera.txt'),'--pcap',str(session/'device-boundary.pcap') if settings.get('capture') else '-',
            '--pipe',pipe,'--packet-size',str(settings['packet_size']),'--trigger-delay-us',str(settings['delay_ms']*1000),'--drop-percent',str(settings['drop_percent']),'--seed',str(settings['seed'])]
        args+=self.extra_arguments(settings,session)
        with (session/'console.txt').open('wb') as output:
            self.process=subprocess.Popen(args,stdout=output,stderr=subprocess.STDOUT,cwd=self.backend.parent,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
        identity=None
        for _ in range(40):
            identity=process_identity(self.process.pid)
            if identity:break
            if self.process.poll() is not None:break
            time.sleep(.01)
        if not identity:raise RuntimeError('Backend exited during startup; see '+str(session/'console.txt'))
        self.record={'protocol':1,'identity':identity,'pipe':pipe,'session':str(session),'adapter':adapter,'settings':settings,'backend_sha256':hashlib.sha256(self.backend.read_bytes()).hexdigest()}
        atomic_json(session/'session.json',self.record);atomic_json(self.data/'active.json',self.record);atomic_json(self.data/'settings.json',settings)
        return self.record
    def stop(self):command(self.record,1)
    def export(self,target):
        if not self.record:raise RuntimeError('No session to export')
        session=Path(self.record['session'])
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            for name in ['session.json','console.txt','camera.txt','device-boundary.pcap']:
                p=session/name
                if p.exists():z.write(p,name)
            for name in ['settings.json']:
                p=self.data/name
                if p.exists():z.write(p,name)
        return str(target)
