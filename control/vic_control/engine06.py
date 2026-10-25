"""06 local Engine IPC and latest-frame reader. Does not implement GenTL."""
import ctypes,ctypes.wintypes as w,json,os,struct,subprocess,sys,time,uuid
from pathlib import Path
from .service import api,close,process_identity,atomic_json,create_file,write,read,set_pipe_mode,wait_pipe,INVALID

ROOT=Path(__file__).resolve().parents[2]
BACKEND=(Path(sys.executable).parent/'backend/VICEngine.exe') if getattr(sys,'frozen',False) else ROOT/'out/06-sequence/build/VICEngine.exe'
HEADER=struct.Struct('<4sHHIQ16sI');DEVICE=b'VIC-DEVICE-0001'.ljust(16,b'\0')
FRAME=struct.Struct('<4sIIIIQQI');MAX_DIMENSION=6000;CAPACITY=40+MAX_DIMENSION*MAX_DIMENSION*3
open_mapping=api('OpenFileMappingW',[w.DWORD,w.BOOL,w.LPCWSTR],w.HANDLE)
map_view=api('MapViewOfFile',[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,ctypes.c_size_t],w.LPVOID)
unmap_view=api('UnmapViewOfFile',[w.LPCVOID])
open_mutex=api('OpenMutexW',[w.DWORD,w.BOOL,w.LPCWSTR],w.HANDLE)
wait=api('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD)
release_mutex=api('ReleaseMutex',[w.HANDLE])
DEFAULTS={'name':'VIC Camera 01','model':'VIC-1000','serial':'VIC000001','source_kind':'pattern','path':'','fit':1,'width':640,'height':480,'pixel_format':0x01080001,'fps_milli':30000,'trigger_mode':0,'delay_us':0,'drop_percent':0,'seed':1}


class EngineClient:
    def probe_source(self,config):
        folder=self.data/'probes';folder.mkdir(exist_ok=True);path=folder/(uuid.uuid4().hex+'.json');atomic_json(path,config)
        try:
            result=subprocess.run([str(self.backend),'--probe-source',str(path.resolve())],capture_output=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:raise RuntimeError('无法读取来源分辨率：'+result.stderr[-2048:])
            dimensions=json.loads(result.stdout)
            if not all(isinstance(dimensions.get(k),int) and 0<dimensions[k]<=MAX_DIMENSION for k in ('width','height')):
                raise ValueError(f"来源分辨率{dimensions.get('width')}×{dimensions.get('height')}超出1–6000；未截断，请关闭自动检测后手动设置输出尺寸。")
            return dimensions
        finally:path.unlink(missing_ok=True)
    def __init__(self,data=None,backend=None):
        self.data=Path(data or Path(os.environ['LOCALAPPDATA'])/'VIC/Control06');self.data.mkdir(parents=True,exist_ok=True)
        self.backend=Path(backend or BACKEND).resolve();self.record=None;self.shared=None;self.mutex=None;self.address=None
        try:self.record=json.loads((self.data/'active.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    def alive(self):
        if not self.record:return False
        try:
            prior=self.record['identity'];now=process_identity(prior['pid'])
            return bool(now and now==prior and Path(now['exe']).name=='VICEngine.exe')
        except (KeyError,TypeError):return False
    def start(self,seconds=28800):
        if self.alive():return self.request(2)
        if not self.backend.is_file():raise RuntimeError('VICEngine.exe missing: '+str(self.backend))
        token=uuid.uuid4().hex;folder=self.data/'sessions'/(time.strftime('%Y%m%d_%H%M%S')+'_'+token[:8]);folder.mkdir(parents=True)
        with (folder/'console.txt').open('wb') as output:
            process=subprocess.Popen([str(self.backend),'--session',token,'--seconds',str(seconds)],stdout=output,stderr=subprocess.STDOUT,cwd=self.backend.parent,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
        identity=process_identity(process.pid)
        if not identity:raise RuntimeError('Engine startup failed; see '+str(folder/'console.txt'))
        self.close_preview();self.record={'identity':identity,'token':token,'session':str(folder),'backend':str(self.backend)};atomic_json(self.data/'active.json',self.record)
        state=self.request(2)
        try:saved=json.loads((self.data/'settings.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return state
        return self.request(3,saved)
    def request(self,command,payload=None):
        if not self.alive():raise RuntimeError('Engine is not running')
        token=self.record['token']
        if len(token)!=32 or any(x not in '0123456789abcdef' for x in token):raise RuntimeError('Invalid Engine session token')
        name='\\\\.\\pipe\\VIC.06.'+token;h=INVALID;deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            h=create_file(name,0xc0000000,0,None,3,0,None)
            if h!=INVALID:break
            wait_pipe(name,100);time.sleep(.01)
        if h==INVALID:raise RuntimeError('Engine control channel unavailable')
        try:
            mode=w.DWORD(3)
            if not set_pipe_mode(h,ctypes.byref(mode),None,None):raise ctypes.WinError(ctypes.get_last_error())
            body=json.dumps(payload or {},ensure_ascii=False).encode('utf-8');rid=time.monotonic_ns();data=HEADER.pack(b'V06C',1,command,HEADER.size+len(body),rid,DEVICE,0)+body
            if len(data)>16384:raise ValueError('Engine request exceeds16KiB')
            count=w.DWORD()
            if not write(h,data,len(data),ctypes.byref(count),None) or count.value!=len(data):raise RuntimeError('Engine request write failed')
            response=ctypes.create_string_buffer(16384);deadline=time.monotonic()+(30 if command==3 else 5)
            while time.monotonic()<deadline:
                if read(h,response,len(response),ctypes.byref(count),None):break
                error=ctypes.get_last_error()
                if error not in (232,536):raise ctypes.WinError(error)
                time.sleep(.01)
            else:raise RuntimeError('Engine request timed out')
            if count.value<40:raise RuntimeError('Truncated Engine reply')
            magic,version,cmd,length,request,device,status=HEADER.unpack(response.raw[:40])
            if (magic,version,cmd,length,request,device)!=(b'V06C',1,command,count.value,rid,DEVICE):raise RuntimeError('Engine reply identity mismatch')
            reply=json.loads(response.raw[40:count.value].decode('utf-8'));write(h,b'\x06',1,ctypes.byref(count),None)
            if status:raise RuntimeError(reply.get('error','Engine rejected command'))
            if command in (3,7):atomic_json(self.data/'settings.json',reply['config'])
            return reply
        finally:close(h)
    def frame(self,after_id=None):
        if not self.alive():self.close_preview();return None
        if not self.address:
            name='Local\\VIC.06.'+self.record['token'];self.shared=open_mapping(4,False,name);self.mutex=open_mutex(0x100001,False,name+'.lock')
            if not self.shared or not self.mutex:self.close_preview();return None
            self.address=map_view(self.shared,4,0,0,CAPACITY)
            if not self.address:self.close_preview();raise ctypes.WinError(ctypes.get_last_error())
        result=wait(self.mutex,0)
        if result not in (0,128):return None
        try:
            header=FRAME.unpack(ctypes.string_at(self.address,40));magic,version,width,height,pfnc,fid,stamp,n=header
            if magic==b'\0'*4:return None
            if magic!=b'V06F' or version!=1 or not 0<width<=MAX_DIMENSION or not 0<height<=MAX_DIMENSION or pfnc not in (0x01080001,0x02180014) or n!=width*height*(3 if pfnc==0x02180014 else 1) or n>CAPACITY-40:raise RuntimeError('Invalid shared frame metadata')
            if after_id is not None and fid<=after_id:return None
            return {'width':width,'height':height,'pixel_format':pfnc,'frame_id':fid,'timestamp_ns':stamp,'pixels':ctypes.string_at(self.address+40,n)}
        finally:release_mutex(self.mutex)
    def close_preview(self):
        if self.address:unmap_view(self.address)
        for h in (self.shared,self.mutex):
            if h:close(h)
        self.address=self.shared=self.mutex=None
