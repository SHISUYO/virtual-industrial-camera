"""Real startup of the supplied large-folder configuration; no network writes."""
import argparse,hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from vic_control.gige06 import GigESourceService

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--release',required=True,type=Path);p.add_argument('--diagnostics',required=True,type=Path);p.add_argument('--sdk',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True);private=ROOT/'out/06-startup'/out.name
    with zipfile.ZipFile(a.diagnostics) as z:source=json.loads(z.read('gigE/source.json'))
    paths=[p for p in Path(source['path']).iterdir() if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.bmp')]
    # Keep the input images/dimensions; isolate SDK identity from the user's FIFO.
    source.update(name='VIC Startup',serial='START06',fps_milli=1000)
    service=GigESourceService(private);service.backend=a.release.resolve()/'gige06/VICGigEControl.exe'
    report={'status':'FAIL','source_files':len(paths),'encoded_bytes':sum(p.stat().st_size for p in paths),'input_zip_sha256':hashlib.sha256(a.diagnostics.read_bytes()).hexdigest(),'source_pixels_comparison':'NOT TESTED'}
    began=time.monotonic()
    try:
        service.publish(source);report['startup_seconds']=round(time.monotonic()-began,3)
        report['ready']='PASS';report['alive']='PASS' if service.alive() else 'FAIL';assert service.alive()
        startup=json.loads((Path(service.record['session'])/'startup.json').read_text(encoding='utf-8'));report['startup']=startup
        if a.sdk:
            frames=private/'sdk';frames.mkdir()
            with (out/'sdk.txt').open('wb') as log:
                result=subprocess.run([str(ROOT/'out/06-resolution/source-probe.exe'),'mono',str(frames),'10.203.0.2','START06'],stdout=log,stderr=subprocess.STDOUT,timeout=100,creationflags=subprocess.CREATE_NO_WINDOW)
            text=(out/'sdk.txt').read_text(encoding='utf-8-sig');assert result.returncode==0,text
            captured=list(frames.glob('frame-*.pgm'));assert len(captured)==3
            for frame in captured:
                header,pixels=frame.read_bytes().split(b'\n255\n',1)
                assert header==f"P5\n{source['width']} {source['height']}".encode() and len(pixels)==source['width']*source['height']
            report.update(discovered='PASS',xml='PASS',opened_fifo='PASS',acquisition_started='PASS',images_received='PASS',frames=3,disconnect='PASS' if 'TARGET_DISCONNECTED' in text else 'FAIL')
        report['backend_sha256']=service.record['backend_sha256'];report['status']='PASS'
    finally:
        if service.alive():
            service.stop();deadline=time.monotonic()+15
            while service.alive() and time.monotonic()<deadline:time.sleep(.05)
            report['normal_stop']='PASS' if not service.alive() else 'FAIL'
        (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
if __name__=='__main__':main()
