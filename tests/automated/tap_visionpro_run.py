"""Post-approval test of a separately running TAP PoC using the REAL Cognex SDK.

Does not install, configure or open an adapter. Never starts the Sandbox/server.
Requires a fresh live PoC log; current live execution status is NOT TESTED.
"""
import argparse,ipaddress,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--camera-ip',required=True);p.add_argument('--host-ip',required=True)
    p.add_argument('--server-log',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--only',choices=['mono','rgb','continuous','software','reconnect']);a=p.parse_args()
    camera=str(ipaddress.IPv4Address(a.camera_ip));host=str(ipaddress.IPv4Address(a.host_ip))
    assert camera!=host
    log=a.server_log.resolve();before=log.read_text(encoding='utf-8')
    if not any('READY build='+v+' mode=LIVE' in before for v in ['TAP-POC-0.1.0','TAP-POC-0.1.1','G05-0.5.0']) or 'STOP rx=' in before:
        raise RuntimeError('A fresh running live PoC is required; no SDK test was started')
    if 'camera_ip='+camera+' host_ip='+host not in before:raise RuntimeError('PoC addresses differ')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'compatibility':'NOT VERIFIED; manual acceptance and packet path pending','cases':{}}
    deadline=time.monotonic()+70
    try:
        for name,mode in [('mono','mono'),('rgb','rgb'),('continuous','continuous'),('software','software'),('reconnect','mono')]:
            if a.only and name!=a.only:continue
            if time.monotonic()+20>deadline or 'STOP rx=' in log.read_text(encoding='utf-8'):
                report['cases'][name]={'valid_frames':'NOT TESTED','reason':'Live PoC ended or test time budget exhausted'};continue
            case=out/name;case.mkdir();offset=len(log.read_text(encoding='utf-8'))
            try:
                probe=subprocess.run([str(ROOT/'out/g04/g04-visionpro-probe.exe'),mode,str(case),camera],cwd=ROOT,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                raw=probe.stdout;code=probe.returncode
            except subprocess.TimeoutExpired as e:raw=e.stdout or b'';code='watchdog'
            (case/'consumer.txt').write_bytes(raw);text=raw.decode('utf-8',errors='replace')
            segment=log.read_text(encoding='utf-8')[offset:];(case/'server-segment.txt').write_text(segment,encoding='utf-8')
            independent=('GIGE_IP='+camera+' HOST_IP='+host) in text
            valid=code==0 and independent and text.count('VALID_FRAME=')==3
            result={'discovered':'PASS' if 'PASS: discovered' in text else 'FAIL',
                'xml':'PASS' if 'PASS: GenICam' in text else 'NOT TESTED',
                'opened_fifo':'PASS' if 'PASS: FIFO_CREATED' in text else 'NOT TESTED',
                'acquisition_started':'PASS' if 'STREAM_CONFIG acquiring=1' in segment else 'NOT TESTED',
                'acquisition_stopped':'PASS' if segment.rfind('STREAM_CONFIG acquiring=0')>segment.rfind('STREAM_CONFIG acquiring=1')>=0 else 'NOT TESTED',
                'valid_frames':'PASS' if valid else ('FAIL' if 'PASS: FIFO_CREATED' in text else 'NOT TESTED'),
                'disconnect':'PASS' if 'TARGET_DISCONNECTED' in text else 'FAIL','exit_code':code}
            if mode=='software':result['camera_software_trigger']='PASS' if valid and text.count('TRIGGER_SOFTWARE_EXECUTED')==3 and segment.count('address=131096 value=1 status=0')>=3 else ('FAIL' if 'PASS: FIFO_CREATED' in text else 'NOT TESTED')
            report['cases'][name]=result;(case/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(name+': '+json.dumps(result),flush=True)
    finally:(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    required=['discovered','xml','opened_fifo','acquisition_started','acquisition_stopped','valid_frames','disconnect']
    passed=bool(report['cases']) and all(all(c.get(key)=='PASS' for key in required) and c.get('camera_software_trigger','PASS')=='PASS' for c in report['cases'].values())
    print(('PASS' if passed else 'FAIL/NOT TESTED')+': SDK image cases; complete compatibility not inferred',flush=True)
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
