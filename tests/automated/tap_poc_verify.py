"""Independent stdlib reader of the C++ PoC's SYNTHETIC Ethernet pcap.

No driver imports, device access or network configuration. These checks do not
establish live packet delivery or Cognex compatibility.
"""
import argparse,json,struct,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HOST=b'\x0a\xcb\x00\x01';CAMERA=b'\x0a\xcb\x00\x02'
HM=bytes.fromhex('025649431001');CM=bytes.fromhex('025649430001')

def folded(data):
    if len(data)%2:data+=b'\0'
    value=sum(struct.unpack('!'+str(len(data)//2)+'H',data))
    while value>65535:value=(value&65535)+(value>>16)
    return value

def verify(folder):
    exe=ROOT/'out/tap-poc/build/VICTapPoC.exe'
    folder.mkdir(parents=True,exist_ok=False)
    run=subprocess.run([str(exe),'--offline',str(folder)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
    (folder/'consumer.txt').write_bytes(run.stdout);assert run.returncode==0,run.stdout.decode(errors='replace')
    blob=(folder/'synthetic.pcap').read_bytes()
    assert struct.unpack('<IHHiiii',blob[:24])==(0xa1b2c3d4,2,4,0,0,65535,1)
    pos=24;frames={};images=[];arp_reply=discovery=udp_packets=0;software_commands=0
    while pos<len(blob):
        _,_,size,original=struct.unpack('<IIII',blob[pos:pos+16]);pos+=16
        packet=blob[pos:pos+size];pos+=size;assert len(packet)==size==original and size<=1514
        dst,src,kind=packet[:6],packet[6:12],struct.unpack('!H',packet[12:14])[0]
        assert src in (HM,CM)
        if kind==0x0806:
            arp=packet[14:42];assert arp[:6]==bytes.fromhex('000108000604')
            if struct.unpack('!H',arp[6:8])[0]==2:
                assert (src,dst,arp[8:14],arp[14:18],arp[18:24],arp[24:28])==(CM,HM,CM,CAMERA,HM,HOST);arp_reply+=1
            continue
        assert kind==0x0800
        ip=packet[14:34];assert ip[0]==0x45 and ip[9]==17 and folded(ip)==65535
        total=struct.unpack('!H',ip[2:4])[0];udp=packet[34:14+total]
        sport,dport,length,csum=struct.unpack('!HHHH',udp[:8]);assert length==len(udp)==total-20 and csum!=0
        assert folded(ip[12:20]+b'\0\x11'+struct.pack('!H',length)+udp)==65535
        data=udp[8:];udp_packets+=1
        if src==HM:
            if data[:4]==bytes.fromhex('42010082'):
                address,value=struct.unpack('!II',data[8:16]);software_commands+=address==0x20018 and value==1
            continue
        assert src==CM and dst==HM and (ip[12:16],ip[16:20])==(CAMERA,HOST)
        if sport==3956:
            status,command,length,rid=struct.unpack('!HHHH',data[:8]);assert status==0 and len(data)==8+length
            if command==3:
                body=data[8:];assert body[0x24:0x28]==CAMERA and body[10:16]==CM;discovery+=1
            continue
        assert (sport,dport)==(49152,50001)
        status,block,info=struct.unpack('!HHI',data[:8]);assert status==0 and block!=0
        typ,pid=info>>24,info&0xffffff
        if typ==1:
            assert pid==0 and len(data)==44
            pfnc,w,h=struct.unpack('!III',data[20:32]);assert (w,h)==(640,480)
            frames[block]={'next':1,'pfnc':pfnc,'pixels':bytearray()}
        else:
            f=frames[block];assert pid==f['next'];f['next']+=1
            if typ==3:f['pixels'].extend(data[8:])
            else:
                assert typ==2 and len(data)==16
                pixels=f['pixels'];rgb=f['pfnc']==0x02180014
                assert rgb or f['pfnc']==0x01080001
                expected=bytearray()
                for y in range(480):
                    for x in range(640):
                        if rgb:expected.extend(((x+block)&255,(y+block)&255,(x+y+block)&255))
                        else:expected.append((x+y+block)&255)
                assert pixels==expected
                images.append({'block':block,'format':'RGB8' if rgb else 'Mono8','all_pixels_checked':True});del frames[block]
    assert pos==len(blob) and not frames and arp_reply==1 and discovery==1 and software_commands==1
    assert len(images)==4 and [i['format'] for i in images]==['Mono8','RGB8','RGB8','RGB8']
    guard=subprocess.run([str(exe),'--live'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=5)
    (folder/'live-without-consent.txt').write_bytes(guard.stdout)
    assert guard.returncode==1 and b'LIVE REFUSED' in guard.stdout
    result={'offline_wire_validation':'PASS','udp_datagrams':udp_packets,'images':images,'live_guard':'PASS',
        'capture_kind':'SYNTHETIC, not real packet capture','driver_io':'NOT TESTED',
        'VisionPro':{'discovered':'NOT TESTED','opened_fifo':'NOT TESTED','acquisition_started':'NOT TESTED','valid_frames':'NOT TESTED'}}
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PASS: OFFLINE Ethernet/ARP/IP/UDP checksums + GVCP + 4 full-pixel GVSP frames + consent guard')
    print('NOT TESTED: TAP driver I/O and actual VisionPro discovery/open/start/valid frames')
    print('EVIDENCE: '+str(folder))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();verify(a.out.resolve())
