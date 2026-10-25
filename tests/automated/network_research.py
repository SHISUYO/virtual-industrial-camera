"""Bounded, configuration-free socket/installed Cognex observations.

Only the VICGE000001 test server is controlled. No adapter, route, firewall,
driver or Hyper-V changes. Socket hex transcripts are NOT NIC packet captures.
GVCP definitions come from existing g01_client, GVSP layout from G02 sources.
"""
import argparse
import hashlib
import ipaddress
import json
import socket
import struct
import subprocess
import time
from pathlib import Path
from g01_client import Client

ROOT=Path(__file__).resolve().parents[2]
EXE=ROOT/'out/g04/build/VICGigE.exe'
PROBE=ROOT/'out/g04/g04-visionpro-probe.exe'
FLAGS=subprocess.CREATE_NO_WINDOW

def save(path,value):
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def start_server(ip,folder,seconds):
    folder.mkdir()
    console=(folder/'console.txt').open('wb')
    server=subprocess.Popen([str(EXE),'--bind',ip,'--config',str(ROOT/'assets/g01-camera.ini'),
        '--duration-ms',str(seconds*1000),'--log',str(folder/'server.txt')],cwd=ROOT,
        stdout=console,stderr=subprocess.STDOUT,creationflags=FLAGS)
    try:
        deadline=time.monotonic()+5
        while not (folder/'server.txt').exists() or 'READY ' not in (folder/'server.txt').read_text():
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server startup failed; see console.txt')
            time.sleep(.05)
    except Exception:
        if server.poll() is None:server.terminate();server.wait()
        console.close();raise
    return server,console

def finish(server,console):
    try:return server.wait(timeout=35)
    except subprocess.TimeoutExpired:
        server.terminate();server.wait();return 'watchdog'
    finally:console.close()

def socket_case(ip,folder):
    server,console=start_server(ip,folder,8)
    result={'discovery_unicast':'NOT TESTED','discovery_broadcast':'NOT TESTED','valid_frames':'NOT TESTED'}
    try:
        with (folder/'gvcp-socket-transcript.jsonl').open('w',encoding='utf-8') as trace:
            client=Client(ip,trace)
            try:
                for name,destination in [('unicast',ip),('broadcast','255.255.255.255')]:
                    reply=client.exchange(2,destination=destination,flags=0x11)
                    camera_ip=socket.inet_ntoa(reply[0x24:0x28])
                    assert camera_ip==ip
                    result['discovery_'+name]='PASS'
                    result['discovery_ack']={'ip':camera_ip,'mac':(reply[10:12]+reply[12:16]).hex(':'),'udp_source':[ip,3956]}
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
                    receiver.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,8*1024*1024)
                    receiver.bind((ip,0));receiver.settimeout(2)
                    port=receiver.getsockname()[1]
                    client.write(0xa00,2)
                    try:
                        client.write(0xd00,port);client.write(0xd04,1500)
                        client.write(0xd18,int(ipaddress.IPv4Address(ip)))
                        source_port=client.read(0xd1c)[0]
                        result['stream']={'source':[ip,source_port],'destination':[ip,port],'packet_size':1500}
                        client.write(0x20000,1) # VIC-private AcquisitionStart register mapped by XML.
                        valid=0;block=None;payload=bytearray();next_id=0
                        with (folder/'gvsp-socket-datagrams.jsonl').open('w',encoding='utf-8') as packets:
                            deadline=time.monotonic()+4
                            while valid<3 and time.monotonic()<deadline:
                                data,peer=receiver.recvfrom(65535)
                                packets.write(json.dumps({'time_ns':time.time_ns(),'source':peer,'destination':[ip,port],'hex':data.hex()})+'\n')
                                assert peer==(ip,source_port)
                                status,bid,info=struct.unpack('!HHI',data[:8]);kind=info>>24;pid=info&0xffffff
                                assert status==0 and bid!=0
                                if kind==1:
                                    assert len(data)==44 and pid==0
                                    pfnc,w,h=struct.unpack('!III',data[20:32]);assert (pfnc,w,h)==(0x01080001,640,480)
                                    block=bid;payload=bytearray();next_id=1
                                elif block==bid:
                                    assert pid==next_id;next_id+=1
                                    if kind==3:payload.extend(data[8:])
                                    elif kind==2:
                                        assert len(payload)==640*480
                                        assert all(value==((x+y+bid)&255) for y in range(480) for x,value in enumerate(payload[y*640:(y+1)*640]))
                                        valid+=1;block=None
                            assert valid==3
                        result['valid_frames']='PASS';result['verified_frames']=valid
                    finally:
                        client.write(0x20000,0);client.write(0xa00,0)
            finally:client.sock.close()
    except Exception as error:result['error']=repr(error);result['valid_frames']='FAIL'
    finally:result['server_exit']=finish(server,console);save(folder/'result.json',result)
    print('SOCKET: '+json.dumps(result),flush=True)
    return result

def endpoints(server_pid,probe_pid,folder,index):
    # Read-only observation. An absent UDP table row does not prove driver ownership.
    command='$ErrorActionPreference="Stop"; Get-NetUDPEndpoint | Where-Object { $_.OwningProcess -in @('+str(server_pid)+','+str(probe_pid)+') } | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress'
    snap=subprocess.run(['powershell.exe','-NoProfile','-Command',command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10,creationflags=FLAGS)
    save(folder/('udp-endpoints-'+str(index)+'.json'),{'time_ns':time.time_ns(),'command':command,'exit_code':snap.returncode,'text':snap.stdout.decode('utf-8',errors='replace')})

def native_case(ip,folder,mode):
    server,console=start_server(ip,folder,20)
    result={'discovered':'NOT TESTED','xml':'NOT TESTED','opened_fifo':'NOT TESTED','acquisition_started':'NOT TESTED','valid_frames':'NOT TESTED'}
    probe=None
    try:
        with (folder/'consumer.txt').open('wb') as output:
            probe=subprocess.Popen([str(PROBE),mode,str(folder),ip],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,creationflags=FLAGS)
            deadline=time.monotonic()+15;index=0
            while probe.poll() is None and time.monotonic()<deadline:
                endpoints(server.pid,probe.pid,folder,index);index+=1;time.sleep(.3)
            if probe.poll() is None:probe.kill();probe.wait();result['watchdog']='FAIL'
            result['exit_code']=probe.returncode
        text=(folder/'consumer.txt').read_text(encoding='utf-8-sig',errors='replace')
        for marker,key in [('PASS: discovered','discovered'),('PASS: GenICam','xml'),('PASS: FIFO_CREATED','opened_fifo')]:
            if marker in text:result[key]='PASS'
        if 'ACQUISITION_REQUEST=' in text:result['valid_frames']='FAIL'
        if probe.returncode==0 and text.count('VALID_FRAME=')==3:result['valid_frames']='PASS'
    except Exception as error:result['error']=repr(error)
    finally:
        if probe is not None and probe.poll() is None:probe.kill();probe.wait()
        result['server_exit']=finish(server,console)
        log=(folder/'server.txt').read_text()
        if 'STREAM_CONFIG acquiring=1' in log:result['acquisition_started']='PASS'
        result['send_errors']=0 if 'send_errors=0' in log else 'NOT TESTED'
        result['camera_software_trigger']='OBSERVED' if 'address=131096 data_word=1 status=0' in log else 'NOT TESTED'
        save(folder/'result.json',result)
    print('COGNEX '+mode+': '+json.dumps(result),flush=True)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--only',choices=['socket','mono','rgb','continuous','software']);a=p.parse_args()
    ip=str(ipaddress.IPv4Address(a.ip));out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    # Fail safely if a camera or another application owns the shared wildcard port.
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as guard:
        guard.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1);guard.bind(('',3956))
    report={'ip':ip,'exe_sha256':hashlib.sha256(EXE.read_bytes()).hexdigest().upper(),
        'probe_sha256':hashlib.sha256(PROBE.read_bytes()).hexdigest().upper(),
        'packet_capture':'NOT TESTED by this runner: socket transcripts only; external ETL/pcap evidence is separate',
        'dual_ip':'NOT TESTED: no approved adapter configuration changes',
        'independent_endpoint':'NOT TESTED: no approved HNS/driver changes','cases':{}}
    try:
        if a.only in (None,'socket'):report['cases']['socket']=socket_case(ip,out/'socket')
        for mode in ['mono','rgb','continuous','software']:
            if a.only and a.only!=mode:continue
            report['cases'][mode]=native_case(ip,out/mode,mode)
    finally:save(out/'result.json',report)
    print('INVESTIGATION FINISHED: observations saved; no compatibility inferred. '+str(out),flush=True)
if __name__=='__main__':main()
