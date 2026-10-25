"""Native Cognex verification against the isolated camera, never a host server."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    guest=json.loads((ROOT/'tests/evidence/G04/sandbox/guest.json').read_text(encoding='utf-8-sig'))
    report={'guest':guest,'compatibility':'NOT VERIFIED: QuickBuild/manual acceptance pending','cases':{}}
    for mode in ['mono','rgb','continuous','software','mono']:
        name='reconnect' if mode=='mono' and 'mono' in report['cases'] else mode
        folder=out/name;folder.mkdir()
        try:
            probe=subprocess.run([str(ROOT/'out/g04/g04-visionpro-probe.exe'),mode,str(folder),guest['IPAddress']],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW)
            raw=probe.stdout;code=probe.returncode
        except subprocess.TimeoutExpired as error:raw=error.stdout or b'';code='watchdog'
        (folder/'consumer.txt').write_bytes(raw);text=raw.decode('utf-8',errors='replace')
        distinct='GIGE_IP='+guest['IPAddress']+' HOST_IP=' in text and ('HOST_IP='+guest['IPAddress']) not in text
        result={'discovered':'PASS' if 'PASS: discovered' in text else 'FAIL',
                'xml':'PASS' if 'PASS: GenICam' in text else 'NOT TESTED',
                'opened_fifo':'PASS' if 'PASS: FIFO_CREATED' in text else 'NOT TESTED',
                'acquisition_started':'PASS' if 'IMAGE_RECEIVED=' in text else 'NOT TESTED',
                'valid_frames':'PASS' if code==0 and distinct and text.count('VALID_FRAME=')==3 else 'FAIL',
                'disconnect':'PASS' if 'TARGET_DISCONNECTED' in text else 'FAIL',
                'independent_ip':'PASS' if distinct else 'FAIL','exit_code':code}
        if mode=='software':result['camera_software_trigger']='PASS' if text.count('TRIGGER_SOFTWARE_EXECUTED')==3 and result['valid_frames']=='PASS' else 'FAIL'
        report['cases'][name]=result
        print('RESULT '+name+': '+json.dumps(result),flush=True)
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    passed=all(r['valid_frames']=='PASS' for r in report['cases'].values())
    print(('PASS' if passed else 'FAIL')+': native SDK pixel checks; QuickBuild/manual acceptance pending',flush=True)
    print('EVIDENCE: '+str(out),flush=True)
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
