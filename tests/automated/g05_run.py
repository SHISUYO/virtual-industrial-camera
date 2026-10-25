"""Real TAP + PySide6 actions + native installed Cognex SDK; no network edits."""
import argparse,json,os,subprocess,sys,time,zipfile,threading
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'));sys.path.insert(0,str(ROOT/'tests/automated'))
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from vic_control.service import Service,command
from vic_control.window import Window
from g01_client import Client

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--backend',type=Path);parser.add_argument('--capture',action='store_true');a=parser.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);service=Service(out/'app-data',backend=a.backend);window=Window(service);window.show();report={};child=None
    def pump(predicate,seconds=15):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents();time.sleep(.01)
            if time.monotonic()>deadline:raise RuntimeError('Timed out: '+window.footer.text())
        app.processEvents()
    def stop():
        if service.alive():QTest.mouseClick(window.stop,Qt.LeftButton);pump(lambda:not service.alive());pump(lambda:not window.jobs);pump(lambda:window.start.isEnabled())
    def start(drop=0):
        window.drop.setValue(drop);window.seen_ready=False;QTest.mouseClick(window.start,Qt.LeftButton);pump(lambda:window.seen_ready and service.alive())
        command(service.record,2);return Path(service.record['session'])
    def sdk(session,name,only=None):
        target=out/name;cmd=[sys.executable,'-u',str(ROOT/'tests/automated/tap_visionpro_run.py'),'--camera-ip','10.203.0.2','--host-ip','10.203.0.1','--server-log',str(session/'console.txt'),'--out',str(target)]
        if only:cmd+=['--only',only]
        with (out/(name+'-runner.txt')).open('wb') as log:
            process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:pump(lambda:process.poll() is not None,80)
            except Exception:process.kill();process.wait();raise
        return process.returncode,json.loads((target/'result.json').read_text())
    try:
        pump(lambda:window.start.isEnabled());window.packet.setValue(1200);window.delay.setValue(120);window.capture.setChecked(a.capture)
        session=start();report['named_pipe_ping']='PASS'
        with (out/'initial-registers.jsonl').open('w') as trace:
            client=Client('10.203.0.1',trace);client.ip='10.203.0.2'
            try:assert client.read(0xd04,0x2001c)==[1200,120000]
            finally:client.sock.close()
        report['startup_packet_size_trigger_delay']='PASS'
        code,result=sdk(session,'healthy');assert code==0,result;report['healthy_sdk']=result
        pump(lambda:window.values['submitted_frames'].text() not in ('—','0'))
        assert window.values['simulated_drop_packets'].text()=='0';report['live_metrics']='PASS'
        window.grab().save(str(out/'gui-healthy.png'))
        stop();report['stop']='PASS';session=start(100)
        code,result=sdk(session,'drop100','mono');assert code==1 and result['cases']['mono']['discovered']=='PASS' and result['cases']['mono']['opened_fifo']=='PASS' and result['cases']['mono']['valid_frames']=='FAIL',result
        pump(lambda:window.values['simulated_drop_packets'].text() not in ('—','0'));report['fault_injection']={'status':'PASS','actual_expected_sdk_failure':result}
        window.grab().save(str(out/'gui-fault.png'));stop();session=start(0)
        code,result=sdk(session,'recovered');assert code==0,result;report['recovery_sdk']=result
        target=out/'diagnostics.zip'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(target),'ZIP')):QTest.mouseClick(window.export,Qt.LeftButton)
        pump(lambda:not window.jobs);assert target.is_file()
        with zipfile.ZipFile(target) as z:assert {'session.json','console.txt','camera.txt','settings.json'}<=set(z.namelist());assert z.testzip() is None
        report['diagnostic_export']='PASS';stop()
        # Real GUI process owns/starts the next backend, then exits while a native
        # Consumer is waiting on a one-second camera trigger delay.
        data=out/'detached-data';close_file=out/'close-gui.request'
        child=subprocess.Popen([sys.executable,str(ROOT/'tests/automated/g05_gui_worker.py'),'--data',str(data),'--close-file',str(close_file)],creationflags=subprocess.CREATE_NO_WINDOW)
        pump(lambda:(data/'gui-ready.txt').exists(),20);detached=Service(data);assert detached.alive()
        pixels=out/'gui-close-sdk';pixels.mkdir();log=(out/'gui-close-sdk.txt').open('wb')
        consumer=subprocess.Popen([str(ROOT/'out/g04/g04-visionpro-probe.exe'),'software',str(pixels),'10.203.0.2'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        triggered=threading.Event()
        def reader():
            for line in consumer.stdout:
                log.write(line);log.flush()
                if b'TRIGGER_SOFTWARE_EXECUTED' in line:triggered.set()
        thread=threading.Thread(target=reader);thread.start()
        pump(triggered.is_set,15);close_file.write_text('close',encoding='utf-8');pump(lambda:child.poll() is not None,10);assert child.returncode==0 and detached.alive()
        pump(lambda:consumer.poll() is not None,20);thread.join(5);log.close();assert consumer.returncode==0 and (out/'gui-close-sdk.txt').read_text(encoding='utf-8-sig').count('VALID_FRAME=')==3
        report['gui_process_exit_during_acquisition']='PASS'
        window.close();pump(lambda:not window.jobs);window=Window(Service(data));window.show();service=window.service
        pump(lambda:window.stop.isEnabled());assert service.alive();report['reopen_attach']='PASS';stop();report['attached_stop']='PASS'
        # GenTL is a truthful blocked mode; cannot launch a fake CTI.
        window.mode.setCurrentIndex(1);app.processEvents();assert not window.start.isEnabled() and '未实现' in window.state.text();report['gentl_ui_guard']='PASS';report['gentl_consumer_regression']='BLOCKED: no GenTL implementation exists in baseline'
        report['status']='PASS';print(json.dumps(report,ensure_ascii=False),flush=True)
    except Exception as e:
        report['status']='FAIL';report['error']=str(e);print(json.dumps(report,ensure_ascii=False),flush=True);raise
    finally:
        if child and child.poll() is None:close_file=out/'close-gui.request';close_file.write_text('close');child.wait(timeout=15)
        for directory in [out/'app-data',out/'detached-data']:
            try:
                existing=Service(directory)
                if existing.alive():existing.stop();pump(lambda:not existing.alive(),10)
            except Exception as e:report.setdefault('cleanup_errors',[]).append(str(e))
        pump(lambda:not window.jobs,10);window.close();app.processEvents();(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
