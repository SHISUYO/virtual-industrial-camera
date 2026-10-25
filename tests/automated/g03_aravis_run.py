"""G03 acceptance with actual Aravis, isolated per-run files and deterministic sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]


def wait_for_camera_port(timeout_s=60):
    """Let a previous timed test finish; never stop another process."""
    deadline=time.monotonic()+timeout_s
    announced=False
    while True:
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                probe.bind(('',3956))
            if announced:
                print('READY: UDP3956 released; continuing the test.',flush=True)
            return
        except OSError as error:
            if time.monotonic()>=deadline:
                raise RuntimeError(f'UDP3956 unavailable after {timeout_s:g}s; another camera test/application may still be running. No process was stopped. Details: {error}') from error
            if not announced:
                print(f'WAIT: UDP3956 unavailable; waiting up to {timeout_s:g}s for release.',flush=True)
                announced=True
            time.sleep(min(.25,max(0,deadline-time.monotonic())))


def run_case(ip,out,kind,options,regression=False,port_wait_seconds=60,server_exe=None,build_id="G03-0.3.0"):
    out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    env['PATH']=str(ROOT/'out/g00/msys64/ucrt64/bin')+os.pathsep+str(ROOT/'out/g00/build/src')+os.pathsep+env['PATH']
    server=None
    result=dict(status='FAIL',discovered='NOT TESTED',opened='NOT TESTED',acquisition='NOT TESTED',valid_frames='NOT TESTED')
    log=out/'server.txt'
    try:
        wait_for_camera_port(port_wait_seconds)
        with (out/'server-console.txt').open('w',encoding='utf-8') as console:
            server=subprocess.Popen([str(server_exe or ROOT/'out/g03/build/VICGigE.exe'),'--bind',ip,'--config',str(ROOT/'assets/g01-camera.ini'),
                '--duration-ms','45000' if regression else '14000','--log',str(log),'--dump-xml',str(out/'device.xml'),*options],
                cwd=ROOT,stdout=console,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            limit=time.monotonic()+5
            while not log.exists() or ('READY build='+build_id+' ') not in log.read_text(encoding='utf-8'):
                assert time.monotonic()<limit and server.poll() is None,'Server did not become ready; see server-console.txt'
                time.sleep(.02)
            sys.path.insert(0,str(ROOT/'out/g01/python-tools'))
            from lxml import etree
            schema=Path('C:/Program Files/Cognex/Common/genicam/xml/GenApi/GenApiSchema_Version_1_1.xsd')
            etree.XMLSchema(etree.parse(str(schema))).assertValid(etree.parse(str(out/'device.xml')))
            print('PASS: XML Schema / '+kind,flush=True)
            consumer_args=[str(ROOT/'out/g02/g02-aravis-consumer.exe'),ip,str(out/'sample.pgm')] if regression else [str(ROOT/'out/g03/g03-aravis-consumer.exe'),ip,kind,str(out/'sample.ppm')]
            consumer=subprocess.Popen(consumer_args,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            watchdog=threading.Timer(42 if regression else 12.5,consumer.kill);watchdog.start()
            try:
                with (out/'consumer.txt').open('w',encoding='utf-8') as evidence:
                    for raw in consumer.stdout:
                        line=raw.decode('utf-8',errors='replace').rstrip()
                        print(line,flush=True);evidence.write(line+'\n');evidence.flush()
                        for prefix,key in [('DISCOVERED','discovered'),('OPENED','opened'),('STARTED','acquisition')]:
                            if line.startswith(prefix): result[key]='PASS'
                        if line.startswith('STARTED'): result['valid_frames']='FAIL'
                assert consumer.wait()==0,'External Aravis consumer failed; see consumer.txt'
            finally:
                watchdog.cancel()
                if consumer.poll() is None: consumer.kill();consumer.wait()
            result['valid_frames']='PASS';result['checked_frames']=1020 if regression else 49
            if not regression:
                # Render the ACTUALLY RECEIVED RGB sample as PNG, without an image dependency.
                import struct,zlib,binascii
                header,payload=(out/'sample.ppm').read_bytes().split(b'\n255\n',1)
                magic,dimensions=header.split(b'\n');w,h=map(int,dimensions.split())
                assert magic==b'P6' and len(payload)==w*h*3
                def chunk(name,data):
                    return struct.pack('!I',len(data))+name+data+struct.pack('!I',binascii.crc32(name+data)&0xffffffff)
                rows=b''.join(b'\0'+payload[y*w*3:(y+1)*w*3] for y in range(h))
                (out/'sample.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
            result['server_exit']=server.wait(timeout=47)
            assert result['server_exit']==0,'Server did not exit cleanly'
            text=log.read_text(encoding='utf-8')
            assert 'send_errors=0' in text and 'GVSP_SEND_ERROR' not in text and 'CORE_ERROR' not in text,'Server send/Core error'
            result.update(status='PASS',send_errors=0)
            print('PASS: source='+kind,flush=True)
    except Exception as error:
        result['error']=repr(error)
        raise
    finally:
        if server and server.poll() is None:
            try: server.wait(timeout=47)
            except subprocess.TimeoutExpired: server.kill();server.wait()
        (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ip',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--only',choices=['regression','pattern','png','jpg','bmp','sequence','video'])
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    exe=ROOT/'out/g03/build/VICGigE.exe'
    summary=dict(status='FAIL',build='G03-0.3.0',bind_ip=args.ip,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest().upper(),
                 cases={},gentl_regression='BLOCKED: GenTL implementation does not exist',packet_capture='BLOCKED: no verified capture',standards_review='BLOCKED: normative specification unavailable',external_consumers=dict(VisionPro='NOT TESTED',HALCON='NOT TESTED',Harvester='NOT TESTED'))
    fixtures=out/'fixtures'
    try:
        subprocess.run([str(ROOT/'out/g03/build/g03_core.exe'),'--fixtures',str(fixtures)],check=True,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        cases=[('regression',[],True),('pattern',[],False),('png',['--image',str(fixtures/'red.png')],False),
               ('jpg',['--image',str(fixtures/'red.jpg')],False),('bmp',['--image',str(fixtures/'red.bmp')],False),
               ('sequence',['--sequence',str(fixtures/'sequence')],False),('video',['--video',str(fixtures/'colors.avi')],False)]
        for kind,options,regression in cases:
            if args.only and kind!=args.only: continue
            print('\nTEST: '+kind,flush=True)
            try:
                summary['cases'][kind]=run_case(args.ip,out/kind,kind,options,regression)
            except Exception:
                failed=out/kind/'result.json'
                summary['cases'][kind]=json.loads(failed.read_text(encoding='utf-8')) if failed.exists() else {'status':'FAIL'}
                raise
        summary['status']='PASS'
        print('PASS: G03 selected checks' if args.only else 'PASS: G03 Core sources / Mono8 + RGB8 / FPS / software trigger / stop + restart / G02 regression',flush=True)
        print('EVIDENCE: '+str(out),flush=True)
    finally:
        (out/'result.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__=='__main__': main()
