"""Real C++ CameraCore / IPC / shared frames and Qt actions, no GenTL mocks."""
import argparse,json,os,subprocess,sys,time,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from vic_control.engine06 import EngineClient,DEFAULTS
from vic_control.panel06 import Panel,application_style


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--backend',type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    fixtures=out/'fixtures';subprocess.run([str(ROOT/'out/06/build/g03_core.exe'),'--fixtures',str(fixtures)],check=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);application_style(app);client=EngineClient(out/'data',backend=a.backend)
    panel=Panel(client);panel.show();report={'status':'FAIL','cases':{},'Harvester':'BLOCKED: no GenTL Producer or pre-existing Harvester test suite','Consumer_live_update':'BLOCKED: no GenTL Producer'};child=None
    def pump(predicate,seconds=15):
        end=time.monotonic()+seconds
        while True:
            app.processEvents()
            if predicate():return
            time.sleep(.01)
            if time.monotonic()>end:raise RuntimeError('Timed out: '+panel.footer.text())
    def idle():pump(lambda:not panel.jobs)
    def click(button):
        parent=button.parentWidget()
        if panel.tabs.indexOf(parent)>=0:
            panel.tabs.setCurrentWidget(parent);panel.content_scroll.ensureWidgetVisible(button)
        idle();pump(button.isEnabled);QTest.mouseClick(button,Qt.LeftButton);idle()
    def config(c):
        idle();panel.load_settings(c);click(panel.apply);assert panel.footer.text()=='配置已应用',panel.footer.text();assert 'error' not in client.request(2) or not client.request(2)['error']
    def frame_after(fid=0):
        value={}
        def got():
            f=client.frame()
            if f and f['frame_id']>fid:value.update(f);return True
            return False
        pump(got);return value
    def stop_acquisition():click(panel.end);pump(lambda:not panel.state.get('acquiring'));idle()
    try:
        assert [panel.tabs.tabText(i) for i in range(panel.tabs.count())]==['概览','设备管理','图像源','采集控制','实时预览','故障注入','日志与状态']
        assert panel.nav.count()==panel.tabs.count() and panel.nav.currentRow()==0
        assert '未发布' in panel.summary_state.text() and panel.kpi_values['consumer'].text()=='未提供'
        panel.nav.setCurrentRow(2);assert panel.tabs.currentIndex()==2
        panel.tabs.setCurrentIndex(0);assert panel.nav.currentRow()==0
        report['cases']['dashboard_navigation_and_truthful_status']='PASS'
        click(panel.start_engine);pump(client.alive);idle();report['cases']['engine_start']='PASS'
        c=dict(DEFAULTS,width=64,height=48,pixel_format=0x02180014,fps_milli=30000,name='Panel Test',model='VIC-06',serial='TEST06')
        config(c);click(panel.begin);pump(lambda:panel.image is not None);f=frame_after();seed=f['frame_id']
        expected=bytes(v&255 for y in range(48) for x in range(64) for v in (x+seed,y+seed,x+y+seed));assert f['pixels']==expected;assert not panel.state['consumer_connected']
        assert not panel.fields['name'].isEnabled();report['cases']['actual_cpp_pattern_preview_identity']='PASS'
        pump(lambda:int(panel.state.get('frame_id','0'))>0)
        panel.tabs.setCurrentIndex(0);app.processEvents()
        assert panel.kpi_values['frame'].text()==str(panel.state['frame_id'])
        assert panel.kpi_values['consumer'].text()=='未提供'
        report['cases']['dashboard_live_engine_metrics']='PASS'
        for i in range(panel.tabs.count()):panel.tabs.setCurrentIndex(i);app.processEvents();panel.grab().save(str(out/f'page-{i}.png'))
        panel.grab().save(str(out/'preview-pattern.png'))
        refused=False
        try:client.request(3,dict(c,name='must-refuse'))
        except RuntimeError:refused=True
        assert refused and client.request(2)['config']['name']=='Panel Test';report['cases']['live_immutable_guard']='PASS'
        panel.fps.setValue(12);panel.delay.setValue(150);panel.drop.setValue(100);click(panel.runtime)
        before=int(client.request(2)['simulated_dropped']);pump(lambda:int(client.request(2)['simulated_dropped'])>before)
        state=client.request(2);assert state['config']['fps_milli']==12000 and state['config']['delay_us']==150000
        panel.drop.setValue(0);click(panel.runtime);before=frame_after()['frame_id'];frame_after(before);report['cases']['live_fps_delay_drop_recover']='PASS'
        stop_acquisition();before=frame_after()['frame_id'];QTest.qWait(150);assert frame_after()['frame_id']==before
        for kind,path in [('image',fixtures/'red.png'),('image',fixtures/'red.jpg'),('image',fixtures/'red.bmp'),('sequence',fixtures/'sequence'),('video',fixtures/'colors.avi')]:
            c.update(source_kind=kind,path=str(path),trigger_mode=0,drop_percent=0,fps_milli=30000,delay_us=0)
            config(c);click(panel.begin);f=frame_after(before);before=f['frame_id'];seen=set()
            until=time.monotonic()+2
            while time.monotonic()<until:
                f=frame_after(before);before=f['frame_id'];center=(24*64+32)*3;color=tuple(f['pixels'][center:center+3]);seen.add(color)
                if kind=='image' or len(seen)>=2:break
            if kind=='image':assert all(abs(v-(255 if i%3==0 else 0))<=1 for i,v in enumerate(f['pixels']))
            else:assert (255,0,0) in seen and (0,255,0) in seen,seen
            if kind=='sequence':
                expected=bytes(v for y in range(48) for x in range(64) for v in ((255,0,0) if color==(255,0,0) and 8<=y<40 else (0,255,0) if color==(0,255,0) and 20<=x<44 else (0,0,0)))
                assert f['pixels']==expected,'Aspect-preserving padding/pixels differ'
            if kind=='video':assert f['pixels']==bytes(color)*(64*48)
            report['cases'][kind+'_'+path.name]='PASS';stop_acquisition()
        c.update(source_kind='image',path=str(fixtures/'red.png'),pixel_format=0x01080001,width=63,height=47,fit=0)
        config(c);click(panel.begin);f=frame_after(before);assert len(f['pixels'])==63*47 and f['pixels']==bytes([76])*(63*47)
        pump(lambda:panel.image is not None and panel.image.width()==63);report['cases']['mono8_all_pixels_odd_stride']='PASS';stop_acquisition()
        # A corrupt or absent source fails atomically, preserving the old config.
        bad=fixtures/'bad.png';bad.write_bytes(b'not an image');(fixtures/'empty').mkdir()
        for kind,path in [('image',bad),('image',fixtures/'missing.png'),('sequence',fixtures/'empty'),('video',fixtures/'bad.avi')]:
            state=client.request(2);candidate=dict(c,source_kind=kind,path=str(path));failed=False
            panel.load_settings(candidate);click(panel.apply)
            assert panel.footer.text().startswith('错误：'),panel.footer.text();assert client.request(2)['config']==state['config']
            report['cases']['reject_'+kind+'_'+path.name]='PASS'
        c.update(source_kind='pattern',path='',trigger_mode=1,delay_us=120000)
        config(c);click(panel.begin);before=int(client.request(2)['frame_id']);QTest.qWait(160);assert int(client.request(2)['frame_id'])==before
        start=time.monotonic();click(panel.fire);f=frame_after(before);assert time.monotonic()-start>=.10;assert f['frame_id']==before+1
        click(panel.fire);stop_acquisition();before=int(client.request(2)['frame_id']);QTest.qWait(150);assert int(client.request(2)['frame_id'])==before
        report['cases']['trigger_delay_stop_cancel']='PASS'
        # Persisted settings survive Engine shutdown/restart.
        state=client.request(2);click(panel.stop_engine);pump(lambda:not client.alive());click(panel.start_engine);assert client.request(2)['config']==state['config'];report['cases']['persistent_restart']='PASS'
        export=out/'diagnostics.zip'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(export),'ZIP')):click(panel.export)
        with zipfile.ZipFile(export) as z:assert {'active.json','settings.json','console.txt'}<=set(z.namelist());assert z.testzip() is None
        report['cases']['diagnostics']='PASS'
        c['trigger_mode']=0;config(c);click(panel.begin);frame_after()
        import signal
        os.kill(client.record['identity']['pid'],signal.SIGTERM)
        pump(lambda:not client.alive());pump(panel.start_engine.isEnabled);click(panel.start_engine);click(panel.begin);pump(lambda:panel.last_frame>0)
        report['cases']['engine_crash_detect_restart']='PASS';click(panel.stop_engine);pump(lambda:not client.alive())
        # Abrupt GUI PROCESS death, not just closing a widget.
        worker_data=out/'worker-data';ready=out/'worker-ready.txt'
        child=subprocess.Popen([sys.executable,str(ROOT/'tests/automated/06_gui_worker.py'),'--data',str(worker_data),'--ready',str(ready)],creationflags=subprocess.CREATE_NO_WINDOW)
        pump(ready.exists);remote=EngineClient(worker_data);assert remote.alive();before=int(remote.request(2)['frame_id']);child.kill();child.wait(10)
        pump(lambda:int(remote.request(2)['frame_id'])>before);report['cases']['unexpected_gui_process_exit_engine_continues']='PASS'
        idle();panel.close();panel=Panel(remote);client=remote;panel.show();pump(lambda:panel.state.get('acquiring'));pump(lambda:panel.image is not None);report['cases']['gui_reopen_attach_preview']='PASS'
        click(panel.stop_engine);pump(lambda:not remote.alive());report['cases']['attached_shutdown']='PASS'
        report['status']='PASS';print(json.dumps(report,ensure_ascii=False),flush=True)
    finally:
        if child and child.poll() is None:child.kill();child.wait(10)
        for data in [out/'data',out/'worker-data']:
            try:
                existing=EngineClient(data)
                if existing.alive():existing.request(1);pump(lambda:not existing.alive())
                existing.close_preview()
            except Exception as e:report.setdefault('cleanup_errors',[]).append(str(e))
        idle();panel.close();app.processEvents();(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
