"""Source failures must produce explicit errors, no READY, and release UDP 3956."""
import argparse
import json
from pathlib import Path
import socket
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        probe.bind(('',3956))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ip',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'empty').mkdir();(out/'corrupt.png').write_bytes(b'not a PNG');(out/'corrupt.avi').write_bytes(b'not a video')
    cases=[('missing_image',['--image',str(out/'missing.png')],'Missing/empty/oversized image'),
           ('corrupt_image',['--image',str(out/'corrupt.png')],'Cannot decode image'),
           ('missing_video',['--video',str(out/'missing.avi')],'Missing video'),
           ('corrupt_video',['--video',str(out/'corrupt.avi')],'Cannot open video'),
           ('empty_sequence',['--sequence',str(out/'empty')],'Sequence has no JPG/PNG/BMP'),
           ('conflicting_sources',['--image','missing.png','--video','missing.avi'],'Choose only one image source')]
    results={}
    for name,options,message in cases:
        free_port()
        result=subprocess.run([str(ROOT/'out/g03/build/VICGigE.exe'),'--bind',args.ip,'--config',str(ROOT/'assets/g01-camera.ini'),
                               '--duration-ms','100',*options],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        text=result.stdout.decode('utf-8',errors='replace');(out/(name+'.txt')).write_text(text,encoding='utf-8')
        assert result.returncode!=0 and message in text and 'READY ' not in text,(name,result.returncode,text)
        free_port();results[name]='PASS';print('PASS: '+name+' / explicit error / port released',flush=True)
    (out/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')


if __name__=='__main__': main()
