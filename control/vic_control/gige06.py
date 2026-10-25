"""06 source snapshot -> existing TAP/GVCP/GVSP adapter, no NIC configuration."""
import json,subprocess,sys,time
from pathlib import Path
from .service import Service,atomic_json
from .engine06 import ROOT

BACKEND=(Path(sys.executable).parent/'gige06/VICGigEControl.exe') if getattr(sys,'frozen',False) else ROOT/'out/06-sequence/build/gige06/VICGigEControl.exe'
STARTUP_TIMEOUT=120


def tap_inventory():
    """Keep adapter identity even when its IPv4 configuration is missing."""
    ps="""$ErrorActionPreference='Stop';$items=@(Get-NetAdapter -IncludeHidden | Where-Object {$_.Name -eq 'VIC-PoC-TAP' -and $_.InterfaceDescription -match 'TAP-Windows'} | ForEach-Object {$a=$_;$ips=@(Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object IPAddress,PrefixLength,SkipAsSource);[pscustomobject]@{name=$a.Name;guid=[string]$a.InterfaceGuid;index=$a.ifIndex;status=[string]$a.Status;driver=$a.DriverVersion;addresses=$ips}});ConvertTo-Json -InputObject $items -Depth 4 -Compress"""
    run=subprocess.run(['powershell.exe','-NoProfile','-Command',ps],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    if run.returncode:raise RuntimeError('TAP只读检查失败：'+run.stderr.decode(errors='replace'))
    return json.loads(run.stdout.decode('utf-8-sig'))


def select_tap(adapters):
    if not adapters:raise RuntimeError('未找到已部署的 VIC-PoC-TAP 网卡；本程序不会安装或配置网卡。')
    if len(adapters)!=1:raise RuntimeError('发现多个 VIC-PoC-TAP 网卡，无法安全选择；未修改网卡。')
    adapter=adapters[0]
    ips=adapter['addresses']
    valid=[ip for ip in ips if ip['IPAddress']=='10.203.0.1' and ip['PrefixLength']==24 and not ip['SkipAsSource']]
    if len(valid)!=1:
        actual=', '.join(f"{ip['IPAddress']}/{ip['PrefixLength']} (SkipAsSource={ip['SkipAsSource']})" for ip in ips) or '无IPv4地址'
        raise RuntimeError('已找到 VIC-PoC-TAP，但地址配置不符。需要10.203.0.1/24、SkipAsSource=false；当前：'+actual+'。请联系管理员恢复并持久保存专用TAP地址；未修改网卡。')
    ip=valid[0]
    return {k:v for k,v in adapter.items() if k!='addresses'} | {'ip':ip['IPAddress'],'prefix':ip['PrefixLength'],'skip':ip['SkipAsSource']}


class GigESourceService(Service):
    def __init__(self,data_dir):super().__init__(data_dir,BACKEND)
    def extra_arguments(self,settings,session):
        path=session/'source.json';atomic_json(path,settings['source']);return ['--source-config',str(path)]
    def publish(self,source):
        for key,limit in [('name',15),('model',31),('serial',15)]:
            value=source[key]
            if not value or len(value)>limit or any(ord(c)<32 or ord(c)>126 for c in value):
                raise ValueError(f'GigE {key} 必须为1–{limit}个ASCII可打印字符；请在设备管理中修改后重试。')
        adapter=select_tap(tap_inventory())
        self.start({'camera_ip':'10.203.0.2','packet_size':1400,'delay_ms':source['delay_us']//1000,'drop_percent':0,'seed':1,'capture':True,'seconds':28800,'source':dict(source)},adapter)
        return self.wait_ready()
    def wait_ready(self,timeout=STARTUP_TIMEOUT):
        started=time.monotonic();deadline=started+timeout
        def record(state):
            atomic_json(Path(self.record['session'])/'startup.json',{'state':state,'timeout_seconds':timeout,'elapsed_seconds':round(time.monotonic()-started,3)})
        record('LOADING')
        while time.monotonic()<deadline:
            observed=self.observed()
            if not self.alive():
                record('EXITED')
                raise RuntimeError('GigE启动失败：'+observed.get('last_lines','')+'；日志：'+self.record['session'])
            if observed.get('ready'):
                record('READY');return self.record
            time.sleep(.05)
        record('TIMEOUT')
        # Initialization may still be validating the folder before its control
        # pipe exists. Keep the owned process/record for diagnosis and later stop.
        raise RuntimeError(f'GigE初始化超过{timeout}秒，后台仍可能在校验来源；未自动停止。请稍后点击“停止 VisionPro 相机”或导出日志；日志：'+self.record['session'])
    def observed(self):
        if not self.record:return {}
        try:
            with (Path(self.record['session'])/'console.txt').open('rb') as f:
                head=f.read(65536);f.seek(0,2);length=f.tell();f.seek(max(len(head),length-65536));tail=f.read()
                text=(head+tail).decode('utf-8',errors='replace')
            return {'ready':'READY build=06-GIGE-0.6.5' in text,'last_lines':'\n'.join(text.splitlines()[-2:])}
        except OSError:return {}
