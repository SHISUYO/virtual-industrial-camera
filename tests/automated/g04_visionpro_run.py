"""Run the installed Cognex consumer; preserve failures, never infer compatibility."""
import argparse,importlib.util,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('g03',ROOT/'tests/automated/g03_aravis_run.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    report={'stage':'G04','compatibility':'NOT VERIFIED','cases':{},'packet_capture':'BLOCKED','QuickBuild':'NOT TESTED by this CLI','HALCON':'NOT TESTED','Harvester':'NOT TESTED'}
    try:
        for mode in ['mono','rgb','continuous','software']:
            folder=out/mode;folder.mkdir();helper.wait_for_camera_port()
            with (folder/'server-console.txt').open('wb') as console:
                server=subprocess.Popen([str(ROOT/'out/g04/build/VICGigE.exe'),'--bind',a.ip,'--config',str(ROOT/'assets/g01-camera.ini'),'--duration-ms','25000','--log',str(folder/'server.txt')],cwd=ROOT,stdout=console,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                result={'discovered':'NOT TESTED','xml':'NOT TESTED','opened_fifo':'NOT TESTED','acquisition_started':'NOT TESTED','valid_frames':'NOT TESTED'}
                try:
                    deadline=time.monotonic()+5
                    while not (folder/'server.txt').exists() or 'READY ' not in (folder/'server.txt').read_text():
                        if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server startup failed')
                        time.sleep(.03)
                    probe=subprocess.Popen([str(ROOT/'out/g04/g04-visionpro-probe.exe'),mode,str(folder)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:raw,_=probe.communicate(timeout=23)
                    except subprocess.TimeoutExpired:
                        probe.kill();raw,_=probe.communicate();result['watchdog']='FAIL'
                    (folder/'consumer.txt').write_bytes(raw);text=raw.decode('utf-8',errors='replace');print(text,flush=True)
                    result['exit_code']=probe.returncode
                    for marker,key in [('PASS: discovered','discovered'),('PASS: GenICam','xml'),('PASS: FIFO_CREATED','opened_fifo')]:
                        if marker in text:result[key]='PASS'
                    if 'ACQUISITION_REQUEST=' in text:result['valid_frames']='FAIL'
                    if 'IMAGE_RECEIVED=' in text:result['images_received']='PASS';result['valid_frames']='NOT TESTED: pixel verification required'
                except Exception as error:result['error']=repr(error)
                finally:
                    try:result['server_exit']=server.wait(timeout=28)
                    except subprocess.TimeoutExpired:server.kill();server.wait();result['server_exit']='watchdog'
                    log=(folder/'server.txt').read_text(errors='replace') if (folder/'server.txt').exists() else ''
                    if 'STREAM_CONFIG acquiring=1' in log:result['acquisition_started']='PASS'
                    result['camera_software_trigger']='OBSERVED' if 'address=131096 data_word=1 status=0' in log else 'NOT TESTED: no TriggerSoftware command observed'
                    result['send_errors']=0 if 'send_errors=0' in log else 'NOT TESTED'
                    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');report['cases'][mode]=result
                    print('RESULT '+mode+': '+json.dumps(result),flush=True)
        print('G04 CHECK FINISHED: compatibility is NOT VERIFIED; inspect FAIL/BLOCKED items.',flush=True)
        print('EVIDENCE: '+str(out),flush=True)
    finally:(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
