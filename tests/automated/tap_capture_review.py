"""Read-only review of actual TAP PCAP and PktMon text; never SDK acceptance."""
import argparse,collections,json,re,socket,struct,statistics
from pathlib import Path
from tap_poc_verify import folded

def main():
    p=argparse.ArgumentParser();p.add_argument('--live',type=Path,required=True);p.add_argument('--capture',type=Path);a=p.parse_args()
    data=(a.live/'device-boundary.pcap').read_bytes();assert struct.unpack_from('<I',data)[0]==0xa1b2c3d4
    pos=24;counts=collections.Counter();frames={};images=[];arp=[];bad_checksums=0
    max_ip=fragments=after_stop=0;acquiring=None;commands={}
    while pos<len(data):
        sec,usec,n,original=struct.unpack_from('<IIII',data,pos);pos+=16;f=data[pos:pos+n];pos+=n
        assert len(f)==n==original
        if f[12:14]==b'\x08\x06' and len(f)>=42:
            arp.append({'op':struct.unpack_from('!H',f,20)[0],'sender':socket.inet_ntoa(f[28:32]),'target':socket.inet_ntoa(f[38:42]),'mac':f[22:28].hex(':')})
        if len(f)<42 or f[12:14]!=b'\x08\x00' or f[14]!=0x45 or f[23]!=17:continue
        length=struct.unpack_from('!H',f,16)[0];udp=f[34:14+length]
        sp,dp,le,cs=struct.unpack_from('!HHHH',udp);payload=udp[8:]
        if sp==3956 or dp==3956:
            if len(payload)>=8:
                status,command,size,rid=struct.unpack_from('!HHHH',payload);counts[str(command)]+=1
                if dp==3956 and command==0x82:
                    for offset in range(8,len(payload)-7,8):
                        address,value=struct.unpack_from('!II',payload,offset)
                        if address==0x20000:commands[(sp,rid)]=bool(value)
                        elif address==0xa00 and value==0:commands[(sp,rid)]=False
                elif sp==3956 and command==0x83 and status==0 and (dp,rid) in commands:acquiring=commands.pop((dp,rid))
        if sp!=49152 or f[26:30]!=socket.inet_aton('10.203.0.2'):continue
        max_ip=max(max_ip,length);fragments+=bool(struct.unpack_from('!H',f,20)[0]&0xbfff)
        if acquiring is False:after_stop+=1
        good=folded(f[14:34])==65535 and (cs==0 or folded(f[26:34]+b'\0\x11'+struct.pack('!H',le)+udp)==65535)
        bad_checksums+=not good
        status,block,info=struct.unpack_from('!HHI',payload);typ,pid=info>>24,info&0xffffff;timestamp=sec+usec/1e6
        if typ==1:
            pfnc,w,h=struct.unpack_from('!III',payload,20)
            assert pfnc in (0x01080001,0x02180014) and 0<w<=8192 and 0<h<=8192 and w*h*(3 if pfnc==0x02180014 else 1)<=64*1024*1024,'Unexpected image layout'
            frames[block]={'next':1,'data':bytearray(),'first':timestamp,'times':[timestamp],'pfnc':pfnc,'w':w,'h':h,'port':dp,'ordered':status==0 and pid==0 and block!=0}
        elif block in frames:
            frame=frames[block];frame['ordered'] &= status==0 and pid==frame['next'];frame['next']=pid+1
            frame['times'].append(timestamp)
            if typ==3:frame['data'].extend(payload[8:])
            elif typ==2:
                rgb=frame['pfnc']==0x02180014;expected=bytearray()
                for y in range(frame['h']):
                    for x in range(frame['w']):
                        if rgb:expected.extend(((x+block)&255,(y+block)&255,(x+y+block)&255))
                        else:expected.append((x+y+block)&255)
                times=frame.pop('times');gaps=[(b-a)*1000000 for a,b in zip(times,times[1:])]
                pixels=bytes(frame.pop('data'));frame.update(block=block,bytes=len(pixels),format='RGB8' if rgb else 'Mono8',seconds=round(timestamp-frame.pop('first'),6),gap_median_us=round(statistics.median(gaps),3),gap_max_us=round(max(gaps),3),all_pixels_correct=pixels==expected)
                images.append(frame);del frames[block]
    block_sequence_ok=all(b['block']==(1 if a['block']==65535 else a['block']+1) for a,b in zip(images,images[1:]))
    passed=bool(images) and block_sequence_ok and all(f['ordered'] and f['all_pixels_correct'] for f in images) and not frames and bad_checksums==0 and fragments==0 and max_ip<=1500 and after_stop==0
    report={'kind':'Actual TAP device boundary; SDK reception NOT inferred','wire_integrity':'PASS' if passed else 'FAIL','block_sequence_ok':block_sequence_ok,'max_gvsp_ip_bytes':max_ip,'gvsp_fragments':fragments,'gvsp_packets_after_stop_ack':after_stop,'gvcp_command_counts':dict(counts),'arp_records':arp,'images':images,'incomplete_blocks':list(frames),'bad_gvsp_checksums':bad_checksums}
    (a.live/'capture-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Actual TAP capture: complete frames='+str(len(images))+' bad GVSP checksums='+str(bad_checksums))
    if a.capture:
        raw=(a.capture/'packets.txt').read_bytes();lines=raw.decode('utf-16' if raw[:2]==b'\xff\xfe' else 'utf-8-sig').splitlines();selected=[];drops=collections.Counter();streamdrops=collections.Counter()
        for i,line in enumerate(lines):
            if '10.203.0.2' not in line:continue
            header=lines[i-1] if i else '';selected.extend((header,line));m=re.search(r'DropReason (.*?) [\u3001,]',header)
            if m:
                drops[m.group(1)]+=1
                if '10.203.0.2.49152' in line:streamdrops[m.group(1)]+=1
        (a.capture/'vic-packets.txt').write_text('\n'.join(selected),encoding='utf-8')
        summary={'relevant_records':len(selected)//2,'camera_ip_drop_reasons':dict(drops),'gvsp_source_drop_reasons':dict(streamdrops),'note':'PktMon observations can repeat a packet across components; counts are not unique lost frames. Correlate timeout timing before assigning a cause.'}
        (a.capture/'vic-drop-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    if not passed:raise RuntimeError('TAP wire checks failed; inspect capture-review.json')

if __name__=='__main__':main()
