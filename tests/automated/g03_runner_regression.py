"""Regression for overlapping timed tests and native stderr in Windows PowerShell."""
import argparse
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[2]


def occupied_port():
    port=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    port.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    port.bind(('',3956))
    return port


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('g03_run',ROOT/'tests/automated/g03_aravis_run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    results={}
    # Actual occupied UDP socket, released later as with a previous timed G02 run.
    port=occupied_port();release=threading.Timer(.4,port.close);release.start();start=time.monotonic()
    try:
        runner.wait_for_camera_port(3)
        assert time.monotonic()-start>=.35,'Did not wait for the occupied port'
    finally:
        release.cancel();release.join();port.close()
    results['wait_then_continue']='PASS'
    # A permanently occupied port must fail with complete per-case evidence.
    with occupied_port():
        try:
            runner.run_case('172.17.240.1',out/'timeout','pattern',[],port_wait_seconds=.1)
        except RuntimeError as error:
            assert 'UDP3956 unavailable' in str(error)
        else:
            raise AssertionError('Occupied port incorrectly passed')
        record=json.loads((out/'timeout/result.json').read_text())
        assert record['status']=='FAIL' and record['acquisition']=='NOT TESTED' and 'UDP3956' in record['error']
    results['timeout_evidence']='PASS'
    helper=str(ROOT/'scripts/invoke-python-logged.ps1').replace("'","''")
    for shell in ['powershell.exe','pwsh.exe']:
        for code in [0,3]:
            name=shell.split('.')[0]+'-exit'+str(code)
            log=out/(name+'.log');script=out/(name+'.ps1')
            # Both stderr lines must reach console + log. Failure must never print SUCCESS.
            source="import sys; print('STDOUT_LINE'); print('STDERR_ONE',file=sys.stderr); print('STDERR_TWO',file=sys.stderr); sys.exit("+str(code)+")"
            script.write_text("$ErrorActionPreference='Stop'\n. '"+helper+"'\ntry {\n"+
                              "Invoke-PythonLogged -Arguments @('-u','-c',\""+source+"\") -LogPath '"+str(log).replace("'","''")+"'\n"+
                              "if ($ErrorActionPreference -ne 'Stop') {exit 8}\nWrite-Output 'SUCCESS'\n"+
                              "} catch {\nif ($ErrorActionPreference -ne 'Stop') {exit 9}\nWrite-Output $_.Exception.Message\nWrite-Output 'EXPECTED_FAILURE'\n}\n",encoding='ascii')
            check=subprocess.run([shell,'-NoProfile','-File',str(script)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
            (out/(name+'.console')).write_bytes(check.stdout)
            console=check.stdout.decode('utf-8',errors='replace')
            raw=log.read_bytes();text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
            assert check.returncode==0 and all(line in console and line in text for line in ['STDOUT_LINE','STDERR_ONE','STDERR_TWO']),(name,console)
            assert ('EXPECTED_FAILURE' in console)==(code!=0) and ('SUCCESS' in console)==(code==0),(name,console)
            results[name]='PASS'
    (out/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    for name,result in results.items(): print(result+': '+name,flush=True)


if __name__=='__main__': main()
