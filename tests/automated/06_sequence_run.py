"""Folder stepping through actual local Core and installed Cognex FIFO.

Starts only private test sessions. No adapter configuration or user-session stop.
"""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from vic_control.engine06 import EngineClient,DEFAULTS
from vic_control.gige06 import GigESourceService

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--release',type=Path,required=True);p.add_argument('--sdk',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True);release=a.release.resolve();fixtures=ROOT/'tests/evidence/06-sequence/fixtures'
    c=dict(DEFAULTS,name='VIC Sequence',serial='SEQ06',source_kind='sequence',path=str(fixtures),width=64,height=48,fps_milli=1000,trigger_mode=1)
    client=EngineClient(out/'local',release/'backend/VICEngine.exe');bridge=GigESourceService(out/'remote');bridge.backend=release/'gige06/VICGigEControl.exe'
    report={'status':'FAIL','cases':{},'QuickBuild_manual':'NOT TESTED'}
    def wait(fn,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=fn()
            if value:return value
            time.sleep(.01)
        raise RuntimeError('Timeout')
    def stop_remote():
        if bridge.alive():bridge.stop();wait(lambda:not bridge.alive())
    try:
        assert client.start().get('sequence_resume')==1,'Package contains an old local Engine'
        client.request(3,c);last=0;seen=[]
        for i in range(9):
            client.request(4);client.request(6)
            frame=wait(lambda:client.frame(after_id=last));last=frame['frame_id'];expected=(i%4+1)*40
            assert frame['pixels']==bytes([expected])*(64*48),(i,frame['pixels'][0]);seen.append(i%4+1)
            client.request(5);time.sleep(.03);assert client.frame(after_id=last) is None
        report['cases']['local_trigger_stop_resume']={'status':'PASS','source_images':seen,'all_pixels_checked':True}
        if a.sdk:
            # Each probe issues three Acquire calls then Disconnect. Reopening
            # the FIFO in the next process must continue the SAME source cursor.
            for mode in ['mono','rgb','software','rgb-software']:
                c.update(trigger_mode=int(mode.endswith('software')),pixel_format=0x02180014 if mode.startswith('rgb') else 0x01080001)
                bridge.publish(c);sequence=[];case=out/mode;case.mkdir()
                for group in range(3):
                    folder=case/str(group);folder.mkdir()
                    with (folder/'sdk.txt').open('wb') as log:
                        result=subprocess.run([str(ROOT/'out/06-resolution/source-probe.exe'),mode,str(folder),'10.203.0.2','SEQ06'],stdout=log,stderr=subprocess.STDOUT,timeout=100,creationflags=subprocess.CREATE_NO_WINDOW)
                    text=(folder/'sdk.txt').read_text(encoding='utf-8-sig');assert result.returncode==0,text
                    assert 'PASS: FIFO_CREATED' in text and 'PASS: GenICam' in text and 'TARGET_DISCONNECTED' in text
                    for i in range(3):
                        rgb=mode.startswith('rgb');path=folder/f"frame-{i}.{'ppm' if rgb else 'pgm'}";header,pixels=path.read_bytes().split(b'\n255\n',1)
                        assert header==(b'P6' if rgb else b'P5')+b'\n64 48'
                        expected=(len(sequence)%4+1)*40
                        assert pixels==bytes([expected])*(64*48*(3 if rgb else 1)),(mode,group,i,expected,pixels[0])
                        sequence.append(expected//40)
                    if mode.endswith('software'):assert text.count('TRIGGER_SOFTWARE_EXECUTED')==3
                stop_remote()
                report['cases'][mode]={'discovered':'PASS','xml':'PASS','opened_fifo':'PASS','acquisition_started':'PASS','valid_frames':'PASS','all_pixels_checked':True,'source_images':sequence,'disconnect_reopen':'PASS','stop':'PASS'}
                print(mode,json.dumps(report['cases'][mode]),flush=True)
        report['status']='PASS';print(json.dumps(report),flush=True)
    finally:
        stop_remote()
        if client.alive():client.request(1);wait(lambda:not client.alive())
        (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
