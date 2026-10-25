"""Approved, bounded live experiment on the recorded dedicated R2 adapter.

No IP/route/DNS/firewall/binding changes or driver installation. Runs the actual
Cognex probe. Packet capture at the TAP boundary alone never proves SDK delivery.
"""
import argparse,ctypes,json,socket,struct,subprocess,sys,time,xml.etree.ElementTree as ET
from g01_client import Client
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FLAGS=subprocess.CREATE_NO_WINDOW

def save(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--deployment',type=Path,required=True);p.add_argument('--network-only',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--seconds',type=int,default=100,choices=range(1,121))
    p.add_argument('--write-depth',type=int,default=64,choices=range(1,65));p.add_argument('--only',choices=['mono','rgb','continuous','software','reconnect']);a=p.parse_args()
    deployment=a.deployment.resolve()
    identity=json.loads((deployment/'configure-result.json').read_text(encoding='utf-8-sig'))
    if identity['status']!='PASS':raise RuntimeError('R2 configuration not confirmed')
    identity=identity['identity'];assert identity['host_ip']=='10.203.0.1' and identity['camera_ip']=='10.203.0.2'
    case=a.out.resolve() if a.out else deployment/('live-'+time.strftime('%Y%m%d_%H%M%S'));case.mkdir(parents=True)
    log=case/'poc.txt';result={'arp':'NOT TESTED','discovery_unicast':'NOT TESTED','discovery_broadcast':'NOT TESTED','sdk':'NOT TESTED'}
    console=(case/'console.txt').open('wb');server=None
    try:
        server=subprocess.Popen([str(ROOT/'out/tap-poc/build/VICTapPoC.exe'),'--live','--owned-adapter-consent',
            '--adapter-guid',identity['guid'],'--host-ip',identity['host_ip'],'--camera-ip',identity['camera_ip'],
            '--seconds','20' if a.network_only else str(a.seconds),'--write-depth',str(a.write_depth),'--log',str(log),'--pcap',str(case/'device-boundary.pcap')],cwd=ROOT,
            stdout=console,stderr=subprocess.STDOUT,creationflags=FLAGS)
        save(case/'process.json',{'pid':server.pid,'identity':identity})
        deadline=time.monotonic()+8
        while not log.exists() or 'READY build=' not in log.read_text():
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Live startup failed; see console.txt')
            time.sleep(.05)
        # Allow Windows DAD after the new TAP media becomes connected.
        time.sleep(3)
        query="Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceIndex,IPAddress,AddressState | ConvertTo-Json -Compress"
        raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=FLAGS)
        (case/'live-addresses.json').write_bytes(raw);addresses=json.loads(raw.decode('utf-8-sig'))
        assert not any(x['IPAddress']==identity['camera_ip'] for x in addresses),'Camera IP is Windows-owned'
        host=[x for x in addresses if x['IPAddress']==identity['host_ip'] and x['InterfaceIndex']==identity['ifIndex']]
        assert len(host)==1 and host[0]['AddressState']==4,'Host IPv4 not Preferred on recorded TAP'
        # SendARP performs actual resolution, not a neighbor-table/configuration edit.
        mac=(ctypes.c_ubyte*6)();length=ctypes.c_ulong(6)
        dst=struct.unpack('<I',socket.inet_aton(identity['camera_ip']))[0]
        src=struct.unpack('<I',socket.inet_aton(identity['host_ip']))[0]
        code=ctypes.windll.iphlpapi.SendARP(ctypes.c_ulong(dst),ctypes.c_ulong(src),mac,ctypes.byref(length))
        result['arp_api']='PASS' if code==0 and bytes(mac)==bytes.fromhex('025649430001') else 'FAIL'
        result['arp_details']={'return_code':code,'mac':bytes(mac).hex(':'),'length':length.value}
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.bind((identity['host_ip'],0));s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);s.settimeout(2)
            trace=[]
            for request,(name,dest) in enumerate([('unicast',identity['camera_ip']),('broadcast','10.203.0.255')],1):
                command=struct.pack('!BBHHH',0x42,0x11,2,0,request)
                entry={'destination':[dest,3956],'request_hex':command.hex()}
                try:
                    s.sendto(command,(dest,3956));data,peer=s.recvfrom(65535)
                    entry.update(source=peer,reply_hex=data.hex())
                    status,ack,size,rid=struct.unpack('!HHHH',data[:8])
                    ok=peer==(identity['camera_ip'],3956) and (status,ack,rid)==(0,3,request) and len(data)==size+8 and socket.inet_ntoa(data[8+0x24:8+0x28])==identity['camera_ip']
                    result['discovery_'+name]='PASS' if ok else 'FAIL'
                except socket.timeout:result['discovery_'+name]='FAIL';entry['error']='receive timeout'
                trace.append(entry)
            save(case/'gvcp-socket.json',trace)
        # The ordinary Windows socket control path is a diagnostic, not Cognex XML validation.
        with (case/'socket-control.jsonl').open('w',encoding='utf-8') as trace:
            client=Client(identity['host_ip'],trace);client.ip=identity['camera_ip']
            try:
                registers=client.read(0x600,0x900,0x904)
                url=client.memory(0x200,512).split(b'\0')[0].decode('ascii')
                scheme,address,size=url.split(';');assert scheme.startswith('Local:')
                address,size=int(address,16),int(size,16);assert 0<size<1024*1024
                xml=bytearray()
                for offset in range(0,(size+3)&~3,512):xml.extend(client.memory(address+offset,min(512,((size+3)&~3)-offset)))
                xml=bytes(xml[:size]);ET.fromstring(xml);(case/'socket-camera.xml').write_bytes(xml)
                result['socket_control']='PASS';result['socket_registers']=registers;result['socket_xml_bytes']=len(xml)
            except Exception as exc:result['socket_control']='FAIL';result['socket_control_error']=str(exc)
            finally:client.sock.close()
        save(case/'network-result.json',result)
        if not a.network_only:
            sdk_command=[sys.executable,'-u',str(ROOT/'tests/automated/tap_visionpro_run.py'),
                '--camera-ip',identity['camera_ip'],'--host-ip',identity['host_ip'],'--server-log',str(log),
                '--out',str(case/'sdk')]
            if a.only:sdk_command+=['--only',a.only]
            sdk=subprocess.run(sdk_command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                timeout=80,creationflags=FLAGS)
            (case/'sdk-console.txt').write_bytes(sdk.stdout);print(sdk.stdout.decode('utf-8',errors='replace'),flush=True)
            result['sdk']='PASS' if sdk.returncode==0 else 'FAIL';result['sdk_exit']=sdk.returncode
    except Exception as exc:
        result['error']=str(exc);print('STOP: '+str(exc),flush=True)
    finally:
        if server is not None:
            try:result['server_exit']=server.wait(timeout=105)
            except subprocess.TimeoutExpired:
                server.terminate();server.wait();result['server_exit']='watchdog'
        console.close();save(case/'result.json',result);print('EVIDENCE: '+str(case),flush=True)
        # Confirm actual request/reply bytes from the closed live TAP capture.
        pcap=case/'device-boundary.pcap'
        if pcap.exists():
            data=pcap.read_bytes();pos=24;request=reply=False
            while pos+16<=len(data):
                _,_,length,_=struct.unpack_from('<IIII',data,pos);pos+=16;frame=data[pos:pos+length];pos+=length
                if len(frame)>=42 and frame[12:14]==b'\x08\x06':
                    op=struct.unpack_from('!H',frame,20)[0]
                    if frame[28:32]==socket.inet_aton(identity['host_ip']) and frame[38:42]==socket.inet_aton(identity['camera_ip']) and op==1:request=True
                    if frame[28:32]==socket.inet_aton(identity['camera_ip']) and frame[38:42]==socket.inet_aton(identity['host_ip']) and frame[22:28]==bytes.fromhex('025649430001') and op==2:reply=True
            result['arp']='PASS' if request and reply else 'NOT TESTED'
        save(case/'result.json',result)
    return 0 if (result.get('socket_control')=='PASS' if a.network_only else result['sdk']=='PASS') else 1
if __name__=='__main__':raise SystemExit(main())
