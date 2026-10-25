"""Reuse G03's real Aravis consumers against the newly built socket adapter."""
import argparse,json,subprocess
from pathlib import Path
from g03_aravis_run import ROOT,run_case

p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.mkdir(parents=True);fixtures=out/'fixtures';report={'status':'FAIL','cases':{}}
try:
    subprocess.run([str(ROOT/'out/g05/build/g03_core.exe'),'--fixtures',str(fixtures)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    cases=[('regression',[],True),('pattern',[],False),('png',['--image',str(fixtures/'red.png')],False),('jpg',['--image',str(fixtures/'red.jpg')],False),('bmp',['--image',str(fixtures/'red.bmp')],False),('sequence',['--sequence',str(fixtures/'sequence')],False),('video',['--video',str(fixtures/'colors.avi')],False)]
    for kind,options,regression in cases:
        report['cases'][kind]=run_case(a.ip,out/kind,kind,options,regression,server_exe=ROOT/'out/g05/build/VICGigE.exe',build_id='G04-0.4.0')
    report['status']='PASS';report['checked_frames']=sum(x['checked_frames'] for x in report['cases'].values())
    print(json.dumps(report),flush=True)
finally:(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
