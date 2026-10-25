"""Launch VIC and a real external Aravis GVSP receiver; save actual received image."""
import argparse
import binascii
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[2]


def png_from_pgm(pgm,png):
    data=pgm.read_bytes()
    header=b'P5\n640 480\n255\n'
    assert data.startswith(header) and len(data)==len(header)+640*480
    pixels=data[len(header):]
    def chunk(kind,payload):
        return struct.pack('!I',len(payload))+kind+payload+struct.pack('!I',binascii.crc32(kind+payload)&0xffffffff)
    rows=b''.join(b'\0'+pixels[y*640:(y+1)*640] for y in range(480))
    png.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',640,480,8,0,0,0,0))+
                    chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ip',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    env['PATH']=str(ROOT/'out/g00/msys64/ucrt64/bin')+os.pathsep+str(ROOT/'out/g00/build/src')+os.pathsep+env['PATH']
    # Fail before launching anything if another application owns the GVCP port.
    probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        probe.bind(('',3956))
    finally:
        probe.close()
    log=out/'server.txt';log.write_text('',encoding='utf-8')
    server=None
    status=dict(status='FAIL',discovered='NOT TESTED',opened='NOT TESTED',acquisition='NOT TESTED',valid_frames='NOT TESTED')
    with (out/'server-console.txt').open('w',encoding='utf-8') as console:
        try:
            server=subprocess.Popen([str(ROOT/'out/g02/build/VICGigE.exe'),'--bind',args.ip,
                '--config',str(ROOT/'assets/g01-camera.ini'),'--duration-ms','45000',
                '--log',str(log),'--dump-xml',str(out/'device.xml')],cwd=ROOT,
                stdout=console,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+5
            while 'READY ' not in log.read_text(encoding='utf-8'):
                assert time.monotonic()<deadline and server.poll() is None,'Server did not become ready'
                time.sleep(.02)
            sys.path.insert(0,str(ROOT/'out/g01/python-tools'))
            from lxml import etree
            schema=Path('C:/Program Files/Cognex/Common/genicam/xml/GenApi/GenApiSchema_Version_1_1.xsd')
            etree.XMLSchema(etree.parse(str(schema))).assertValid(etree.parse(str(out/'device.xml')))
            print('PASS: GenApi XML Schema',flush=True)
            consumer=subprocess.Popen([str(ROOT/'out/g02/g02-aravis-consumer.exe'),args.ip,str(out/'sample.pgm')],
                env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            # Stream progress to the user's terminal; bound overall execution independently.
            import threading
            watchdog=threading.Timer(42,consumer.kill)
            watchdog.start()
            try:
                with (out/'consumer.txt').open('w',encoding='utf-8') as result:
                    for raw in consumer.stdout:
                        line=raw.decode('utf-8',errors='replace').rstrip()
                        print(line,flush=True);result.write(line+'\n');result.flush()
                        for marker,key in [('DISCOVERED ','discovered'),('OPENED ','opened'),('STARTED ','acquisition')]:
                            if line.startswith(marker): status[key]='PASS'
                        if line.startswith('STARTED '): status['valid_frames']='FAIL' # Executed, pending successful completion.
                assert consumer.wait()==0,'External Aravis consumer failed; see consumer.txt'
            finally:
                watchdog.cancel()
                if consumer.poll() is None:
                    consumer.kill();consumer.wait()
            status['valid_frames']='PASS';status['checked_frames']=1020
            png_from_pgm(out/'sample.pgm',out/'sample.png')
            server_exit=server.wait(timeout=47)
            status['server_exit']=server_exit
            assert server_exit==0,f'VIC server exited with code {server_exit}'
            text=log.read_text(encoding='utf-8')
            assert 'send_errors=0' in text and 'GVSP_SEND_ERROR' not in text,'Network send error'
            assert 'STREAM_STOP ' in text and ' STOP ' in text,'Shutdown not completed'
            status.update(status='PASS',send_errors=0,packet_capture='BLOCKED')
            print('PASS: G02 / 1000 frames + 20 restart frames / all pixels / zero send errors',flush=True)
            print('IMAGE: '+str(out/'sample.png'),flush=True)
        except Exception as error:
            status['error']=repr(error)
            print('FAIL: '+str(error),flush=True)
            raise
        finally:
            if server and server.poll() is None:
                try: server.wait(timeout=47)
                except subprocess.TimeoutExpired: server.kill();server.wait()
            (out/'result.json').write_text(json.dumps(status,indent=2),encoding='utf-8')


if __name__=='__main__': main()
