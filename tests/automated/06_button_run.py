"""Real mouse gestures across a delayed native status poll, then Cognex SDK."""
import argparse,json,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vic_control.panel06 import Panel,application_style
from vic_control.engine06 import EngineClient,DEFAULTS

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--gige-backend',type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);application_style(app)
    client=EngineClient(out/'old-local',ROOT/'out/06/build/VICEngine.exe');client.start();panel=Panel(client);panel.show();panel.poll_timer.stop();report={'status':'FAIL','QuickBuild_manual':'NOT TESTED'}
    def wait(fn,seconds=15):
        deadline=time.monotonic()+seconds
        while True:
            app.processEvents()
            if fn():return
            if time.monotonic()>deadline:raise RuntimeError(panel.footer.text())
            time.sleep(.01)
    try:
        wait(lambda:not panel.jobs)
        if a.gige_backend:panel.bridge.backend=a.gige_backend.resolve()
        config=dict(DEFAULTS,source_kind='image',path=str(ROOT/'tests/evidence/06-source-fix/live-02/fixtures/red.png'),serial='SOURCE06')
        panel.load_settings(config);assert 'source_frame_floor' not in panel.state
        real_request=client.request
        def gesture(button):
            entered=threading.Event();release=threading.Event()
            def delayed(command,payload=None):
                if command==2:entered.set();release.wait(5)
                return real_request(command,payload)
            client.request=delayed
            try:
                assert button.isEnabled();QTest.mousePress(button,Qt.LeftButton);panel.poll();wait(entered.is_set)
                assert button.isEnabled(),'Background status disabled pressed button'
                QTest.mouseRelease(button,Qt.LeftButton);assert panel.pending_action is not None,'Click was not queued'
            finally:release.set();client.request=real_request
            wait(lambda:not panel.jobs and panel.pending_action is None)
        gesture(panel.gige);assert panel.bridge.alive(),panel.footer.text();report['old_engine_and_poll_mouse_publish']='PASS'
        old=real_request(2);assert old['config']['source_kind']=='pattern' and not old['acquiring'];report['old_local_engine_unchanged']='PASS'
        for mode in ['mono','rgb','software']:
            case=out/mode;case.mkdir()
            with (case/'sdk.txt').open('wb') as log:
                process=subprocess.Popen([str(ROOT/'out/06-fix/source-probe.exe'),mode,str(case),'10.203.0.2','SOURCE06'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                try:wait(lambda:process.poll() is not None,30)
                finally:
                    if process.poll() is None:process.kill();process.wait()
            text=(case/'sdk.txt').read_text(encoding='utf-8-sig');assert process.returncode==0,text
            frames=list(case.glob('frame-*.*'));assert len(frames)==3
            for frame in frames:
                header,pixels=frame.read_bytes().split(b'\n255\n',1)
                assert header==(b'P6' if mode=='rgb' else b'P5')+b'\n640 480'
                assert pixels==(bytes([255,0,0]) if mode=='rgb' else bytes([76]))*(640*480)
            result={key:('PASS' if marker in text else 'FAIL') for key,marker in [('discovered','PASS: discovered'),('xml','PASS: GenICam'),('opened_fifo','PASS: FIFO_CREATED'),('disconnect','TARGET_DISCONNECTED')]}
            assert all(value=='PASS' for value in result.values()),result
            result.update(valid_frames='PASS',frames=3,all_pixels_checked=True)
            if mode=='software':assert text.count('TRIGGER_SOFTWARE_EXECUTED')==3;result['software_trigger']='PASS'
            report[mode]=result
        gesture(panel.stop_gige);wait(lambda:not panel.bridge.alive());report['stop_button_during_poll']='PASS'
        panel.grab().save(str(out/'gui.png'));report['status']='PASS';print(json.dumps(report),flush=True)
    finally:
        if panel.bridge.alive():panel.bridge.stop();wait(lambda:not panel.bridge.alive())
        wait(lambda:not panel.jobs);panel.close()
        if client.alive():client.request(1);wait(lambda:not client.alive())
        (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
