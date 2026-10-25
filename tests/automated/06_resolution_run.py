"""6000-pixel editing, native source dimensions, full shared frames and Cognex."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QColor,QPainter
from PySide6.QtTest import QTest
from vic_control.panel06 import Panel,application_style
from vic_control.engine06 import EngineClient,DEFAULTS,CAPACITY

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);parser.add_argument('--sdk',action='store_true');parser.add_argument('--backend',type=Path);parser.add_argument('--gige-backend',type=Path);a=parser.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    fixtures=ROOT/'out/06-resolution/fixtures';fixtures.mkdir(exist_ok=True)
    subprocess.run([str(ROOT/'out/06-resolution/build/g03_core.exe'),'--fixtures',str(fixtures)],check=True)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);application_style(app)
    for name,w,h in [('industrial.png',5472,3648),('square.png',6000,6000),('square.bmp',6000,6000),('oversize.png',6001,8)]:
        image=QImage(w,h,QImage.Format_RGB888);paint=QPainter(image)
        for x,y,c in [(0,0,'red'),(w//2,0,'green'),(0,h//2,'blue'),(w//2,h//2,'white')]:
            # Qt's named green is #008000; use exact full-scale channels.
            color={'red':QColor(255,0,0),'green':QColor(0,255,0),'blue':QColor(0,0,255),'white':QColor(255,255,255)}[c]
            paint.fillRect(x,y,w//2 if x==0 else w-w//2,h//2 if y==0 else h-h//2,color)
        paint.end();assert image.save(str(fixtures/name))
    image=None
    panel=Panel(EngineClient(out/'data',a.backend));panel.show();report={'status':'FAIL','QuickBuild_manual':'NOT TESTED','cases':{}}
    if a.gige_backend:panel.bridge.backend=a.gige_backend.resolve()
    def wait(fn,seconds=30):
        deadline=time.monotonic()+seconds
        while True:
            app.processEvents()
            if fn():return
            if time.monotonic()>deadline:raise RuntimeError('Timeout: '+panel.footer.text())
            time.sleep(.01)
    def click(button):
        parent=button.parentWidget()
        if panel.tabs.indexOf(parent)>=0:panel.tabs.setCurrentWidget(parent)
        wait(lambda:not panel.jobs and button.isEnabled());QTest.mouseClick(button,Qt.LeftButton);wait(lambda:not panel.jobs)
    def choose(kind,path):
        panel.source.setCurrentIndex(panel.source.findData(kind))
        method='getExistingDirectory' if kind=='sequence' else 'getOpenFileName'
        answer=str(path) if kind=='sequence' else (str(path),'')
        with patch.object(QFileDialog,method,return_value=answer):click(panel.browse)
    def stop_remote():
        if panel.bridge.alive():click(panel.stop_gige);wait(lambda:not panel.bridge.alive())
    def expected(w,h,rgb):
        colors=[bytes(c) for c in [(255,0,0),(0,255,0),(0,0,255),(255,255,255)]] if rgb else [bytes([v]) for v in (76,150,29,255)]
        top=colors[0]*(w//2)+colors[1]*(w-w//2);bottom=colors[2]*(w//2)+colors[3]*(w-w//2)
        return top*(h//2)+bottom*(h-h//2)
    try:
        # Actual key events and focus commit, not setValue substitution.
        panel.tabs.setCurrentIndex(2)
        QTest.qWait(100);app.processEvents()
        for key in ('width','height'):
            widget=panel.fields[key]
            for value in (1000,1920,3648,5472,6000):
                widget.setFocus();app.processEvents();QTest.keyClick(widget,Qt.Key_A,Qt.ControlModifier);QTest.keyClicks(widget,str(value));QTest.keyClick(widget,Qt.Key_Tab);app.processEvents();assert widget.value()==value,(key,value,widget.text())
            widget.stepDown();assert widget.value()==5999;widget.stepUp();assert widget.value()==6000
        report['cases']['keyboard_four_digits_and_arrows']='PASS'
        for kind,file,shape in [('image','industrial.png',(5472,3648)),('image','square.bmp',(6000,6000)),('sequence','sequence',(64,32)),('video','colors.avi',(64,48))]:
            choose(kind,fixtures/file);actual=(panel.fields['width'].value(),panel.fields['height'].value());assert actual==shape,(file,actual)
            report['cases']['auto_'+file]='PASS'
        before=(panel.fields['width'].value(),panel.fields['height'].value());choose('image',fixtures/'oversize.png')
        assert '6001' in panel.footer.text() and (panel.fields['width'].value(),panel.fields['height'].value())==before
        choose('image',fixtures/'missing.png');assert panel.footer.text().startswith('错误：')
        assert (panel.fields['width'].value(),panel.fields['height'].value())==before;report['cases']['invalid_or_oversize_auto_keeps_dimensions']='PASS'
        try:panel.settings()
        except ValueError:pass
        else:raise AssertionError('Failed auto dimensions allowed silent publication')
        panel.auto_size.setChecked(False);choose('image',fixtures/'industrial.png');assert (panel.fields['width'].value(),panel.fields['height'].value())==before
        click(panel.detect_size);assert panel.fields['width'].value()==5472;report['cases']['manual_mode_and_explicit_probe']='PASS'
        click(panel.start_engine);config=dict(DEFAULTS,source_kind='image',path=str(fixtures/'square.png'),width=6000,height=6000,pixel_format=0x02180014,fps_milli=1000,trigger_mode=1,serial='DIM06')
        panel.load_settings(config);click(panel.apply);assert panel.footer.text()=='配置已应用';click(panel.begin);click(panel.fire)
        captured={}
        def frame_ready():
            frame=panel.client.frame()
            if frame and frame['frame_id']>int(panel.state['source_frame_floor']):captured.update(frame);return True
            return False
        wait(frame_ready);assert captured['width']==6000 and captured['height']==6000 and len(captured['pixels'])==108000000
        assert captured['pixels']==expected(6000,6000,True);assert panel.client.frame(after_id=captured['frame_id']) is None
        captured.clear();wait(lambda:panel.image is not None);assert panel.image.size().width()==6000
        click(panel.end);report['cases']['shared_6000_rgb_all_pixels']='PASS';assert CAPACITY==108000040
        for key in ('width','height'):
            bad=dict(config);bad[key]=6001
            try:panel.client.request(3,bad)
            except RuntimeError:pass
            else:raise AssertionError('Accepted >6000')
        report['cases']['native_rejects_6001']='PASS'
        if a.sdk:
            for name,file,w,h,mode in [('industrial_rgb','industrial.png',5472,3648,'rgb'),('max_mono','square.png',6000,6000,'mono'),('max_rgb_software','square.png',6000,6000,'rgb-software')]:
                config.update(path=str(fixtures/file),width=w,height=h,pixel_format=0x01080001 if mode=='mono' else 0x02180014,trigger_mode=int(mode.endswith('software')))
                panel.load_settings(config);click(panel.gige);assert panel.bridge.alive(),panel.footer.text();case=out/name;case.mkdir()
                with (case/'sdk.txt').open('wb') as log:
                    process=subprocess.Popen([str(ROOT/'out/06-resolution/source-probe.exe'),mode,str(case),'10.203.0.2','DIM06'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                    try:wait(lambda:process.poll() is not None,120)
                    finally:
                        if process.poll() is None:process.kill();process.wait()
                text=(case/'sdk.txt').read_text(encoding='utf-8-sig');result={'sdk_exit':process.returncode,'valid_frames':'NOT TESTED'};report['cases'][name]=result
                assert process.returncode==0,text
                frames=list(case.glob('frame-*.*'));assert len(frames)==3;hashes=[]
                for frame in frames:
                    raw=frame.read_bytes();header,pixels=raw.split(b'\n255\n',1);rgb=mode.startswith('rgb');assert header==(b'P6' if rgb else b'P5')+f'\n{w} {h}'.encode()
                    assert pixels==expected(w,h,rgb),str(frame)
                    hashes.append({'path':str(frame.relative_to(out)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
                result.update(discovered='PASS' if 'PASS: discovered' in text else 'FAIL',opened_fifo='PASS' if 'PASS: FIFO_CREATED' in text else 'FAIL',xml='PASS' if 'PASS: GenICam' in text else 'FAIL',acquisition_started='PASS',valid_frames='PASS',frames=3,all_pixels_checked=True,raw_frames=hashes,disconnect='PASS' if 'TARGET_DISCONNECTED' in text else 'FAIL')
                if mode.endswith('software'):assert text.count('TRIGGER_SOFTWARE_EXECUTED')==3;result['software_trigger']='PASS'
                stop_remote();result['stop']='PASS';print(name,json.dumps(result),flush=True)
        report['status']='PASS';panel.grab().save(str(out/'gui.png'));print(json.dumps(report),flush=True)
    finally:
        # Prevent a new background query racing the deliberate Engine shutdown.
        panel.poll_timer.stop();panel.preview_timer.stop()
        stop_remote();wait(lambda:not panel.jobs)
        if panel.client.alive():panel.client.request(1);wait(lambda:not panel.client.alive())
        panel.close();(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
