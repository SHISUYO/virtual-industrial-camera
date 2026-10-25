"""GUI source selection -> TAP -> REAL Cognex SDK -> whole-image verification."""
import argparse,json,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from vic_control.panel06 import Panel,application_style
from vic_control.engine06 import EngineClient,DEFAULTS

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--backend',type=Path);p.add_argument('--gige-backend',type=Path);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    fixtures=out/'fixtures';subprocess.run([str(ROOT/'out/06-fix/build/g03_core.exe'),'--fixtures',str(fixtures)],check=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);application_style(app);panel=Panel(EngineClient(out/'local',a.backend));panel.auto_size.setChecked(False);panel.show();report={'status':'FAIL','cases':{},'QuickBuild_manual':'NOT TESTED'}
    if a.gige_backend:panel.bridge.backend=a.gige_backend.resolve()
    def wait(test,timeout=20):
        until=time.monotonic()+timeout
        while True:
            app.processEvents()
            if test():return
            if time.monotonic()>until:raise RuntimeError('Timed out: '+panel.footer.text())
            time.sleep(.01)
    def click(button):
        parent=button.parentWidget()
        if panel.tabs.indexOf(parent)>=0:panel.tabs.setCurrentWidget(parent)
        wait(lambda:not panel.jobs and button.isEnabled());QTest.mouseClick(button,Qt.LeftButton);wait(lambda:not panel.jobs)
    def stop_gige():
        if panel.bridge.alive():click(panel.stop_gige);wait(lambda:not panel.bridge.alive())
    def apply_config(config):panel.load_settings(config);click(panel.apply);assert panel.footer.text()=='配置已应用',panel.footer.text()
    def expected(w,h,kind,color,rgb):
        # Independent geometry for fixture dimensions and CameraCore's fit padding.
        iw,ih=(64,32) if kind=='sequence' and color=='red' else (32,64) if kind=='sequence' else (64,48)
        scale=min(w/iw,h/ih);rw=max(1,int(iw*scale));rh=max(1,int(ih*scale));left=(w-rw)//2;top=(h-rh)//2
        pixel=bytes((255,0,0) if color=='red' else (0,255,0)) if rgb else bytes([76 if color=='red' else 150])
        zero=bytes(len(pixel));row=zero*left+pixel*rw+zero*(w-left-rw)
        return zero*(w*top)+row*rh+zero*(w*(h-top-rh))
    try:
        click(panel.start_engine)
        c=dict(DEFAULTS,width=642,height=480,pixel_format=0x02180014,serial='SOURCE06')
        apply_config(c);click(panel.begin);wait(lambda:panel.image is not None);click(panel.end)
        # Reproduce wrong dropdown kind (Video) + picked JPG/PNG, then verify auto type.
        panel.source.setCurrentIndex(panel.source.findData('video'))
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(fixtures/'red.png'),'')):click(panel.browse)
        assert panel.source.currentData()=='image';click(panel.apply)
        assert panel.image is None;QTest.qWait(200);app.processEvents();assert panel.image is None,'Previous pattern survived apply'
        assert int(panel.state['source_frame_floor'])>0;report['cases']['old_frame_invalidated_auto_file_kind']='PASS'
        click(panel.source_apply);wait(lambda:panel.image is not None);assert panel.image.pixelColor(200,200).red()==255;click(panel.end)
        report['cases']['one_click_apply_preview']='PASS'
        cases=[('png_mono','image','red.png','mono',642),('png_rgb','image','red.png','rgb',642),('jpg_mono','image','red.jpg','mono',640),('bmp_rgb','image','red.bmp','rgb',640),('video_mono','video','colors.avi','continuous',640),('video_rgb','video','colors.avi','rgb-continuous',640),('sequence_rgb','sequence','sequence','rgb-continuous',640),('software','image','red.png','software',640)]
        for name,kind,source,mode,width in cases:
            c.update(source_kind=kind,path=str(fixtures/source),width=width,pixel_format=0x02180014 if mode.startswith('rgb') else 0x01080001,trigger_mode=int(mode.endswith('software')),delay_us=100000 if mode.endswith('software') else 0)
            apply_config(c);click(panel.gige);wait(lambda:panel.bridge.alive() and 'READY build=06-GIGE-0.6.3' in (Path(panel.bridge.record['session'])/'console.txt').read_text(encoding='utf-8'))
            assert not panel.source.isEnabled();case=out/name;case.mkdir();log=(case/'sdk.txt').open('wb')
            probe=subprocess.Popen([str(ROOT/'out/06-fix/source-probe.exe'),mode,str(case),'10.203.0.2',c['serial']],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:wait(lambda:probe.poll() is not None,30)
            finally:
                if probe.poll() is None:probe.kill();probe.wait()
                log.close()
            text=(case/'sdk.txt').read_text(encoding='utf-8-sig');result={'discovered':'PASS' if 'PASS: discovered' in text else 'FAIL','opened_fifo':'PASS' if 'PASS: FIFO_CREATED' in text else 'FAIL','xml':'PASS' if 'PASS: GenICam' in text else 'FAIL','sdk_exit':probe.returncode,'valid_frames':'NOT TESTED'}
            report['cases'][name]=result;assert probe.returncode==0,text
            colors=set();count=0
            for path in sorted(case.glob('frame-*.*')):
                header,pixels=path.read_bytes().split(b'\n255\n',1);magic,shape=header.split(b'\n');w,h=map(int,shape.split());rgb=magic==b'P6';assert (w,h)==(width,480)
                red=expected(w,h,kind,'red',rgb);green=expected(w,h,kind,'green',rgb)
                if pixels==red:colors.add('red')
                elif kind!='image' and pixels==green:colors.add('green')
                else:raise AssertionError('Whole-frame source pixels differ: '+str(path))
                count+=1
            assert count==3
            if kind!='image':assert colors=={'red','green'},colors
            segment=(Path(panel.bridge.record['session'])/'console.txt').read_text(encoding='utf-8');assert 'STREAM_CONFIG acquiring=1' in segment
            result.update(acquisition_started='PASS',valid_frames='PASS',all_pixels_checked=True,frames=count,colors=sorted(colors),disconnect='PASS' if 'TARGET_DISCONNECTED' in text else 'FAIL')
            assert result['disconnect']=='PASS'
            if mode.endswith('software'):assert text.count('TRIGGER_SOFTWARE_EXECUTED')==3;result['software_trigger']='PASS'
            if name=='software':
                again=case/'reconnect';again.mkdir()
                with (again/'sdk.txt').open('wb') as log:
                    probe=subprocess.Popen([str(ROOT/'out/06-fix/source-probe.exe'),mode,str(again),'10.203.0.2',c['serial']],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        wait(lambda:probe.poll() is not None,30)
                    finally:
                        if probe.poll() is None:probe.kill();probe.wait()
                assert probe.returncode==0
                frames=list(again.glob('frame-*.pgm'));assert len(frames)==3
                for frame in frames:assert frame.read_bytes().split(b'\n255\n',1)[1]==expected(width,480,kind,'red',False)
                result['reconnect_valid_pixels']='PASS'
            if name=='png_rgb':
                target=case/'diagnostics.zip'
                with patch.object(QFileDialog,'getSaveFileName',return_value=(str(target),'')):click(panel.export)
                import zipfile
                with zipfile.ZipFile(target) as z:assert {'gigE/source.json','gigE/console.txt','gigE/device-boundary.pcap'}<=set(z.namelist());assert z.testzip() is None
                report['cases']['source_diagnostic_export']='PASS'
            (case/'result.json').write_text(json.dumps(result,indent=2));stop_gige();result['stop']='PASS'
            print(name,json.dumps(result),flush=True)
        report['status']='PASS';panel.grab().save(str(out/'final-gui.png'));print(json.dumps(report),flush=True)
    finally:
        stop_gige()
        wait(lambda:not panel.jobs)
        if panel.client.alive():panel.client.request(1);wait(lambda:not panel.client.alive())
        panel.close();app.processEvents();(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
