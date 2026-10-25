"""Migration/source picker guards; only starts a private old local Engine."""
import argparse,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtWidgets import QApplication,QFileDialog
from vic_control.panel06 import Panel,application_style
from vic_control.engine06 import EngineClient,DEFAULTS

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--old-backend',type=Path,default=ROOT/'out/06/build/VICEngine.exe');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True)
    app=QApplication([]);application_style(app)
    client=EngineClient(out/'private-old-engine',a.old_backend);report={}
    try:
        state=client.start();assert not state.get('sequence_resume')
        panel=Panel(client);panel.auto_size.setChecked(False);panel.received(state)
        deadline=time.monotonic()+5
        while panel.jobs and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
        panel.update_controls()
        assert not panel.apply.isEnabled() and not panel.source_apply.isEnabled() and panel.gige.isEnabled() and panel.stop_engine.isEnabled()
        panel.paint_preview();assert panel.image is None;report['old_engine_explicit_upgrade_guard']='PASS'
        panel.source.setCurrentIndex(panel.source.findData('image'))
        with patch.object(QFileDialog,'getOpenFileName',return_value=('C:/fixture/video.avi','')):panel.choose_source()
        assert panel.source.currentData()=='video';report['auto_video_file_kind']='PASS'
        with patch.object(QFileDialog,'getOpenFileName',return_value=('C:/fixture/photo.jpg','')):panel.choose_source()
        assert panel.source.currentData()=='image';report['auto_jpg_file_kind']='PASS'
        panel.source.setCurrentIndex(panel.source.findData('pattern'));assert not panel.path.text();report['test_pattern_clears_old_path']='PASS'
        config=dict(DEFAULTS,name='Virtual Camera 01')
        try:panel.bridge.publish(config)
        except ValueError as e:assert 'name' in str(e)
        else:raise AssertionError('Overlong GigE name accepted')
        assert not panel.bridge.record;report['identity_rejected_before_TAP_start']='PASS'
        panel.close();report['status']='PASS';print(json.dumps(report),flush=True)
    finally:
        if client.alive():client.request(1)
        deadline=time.monotonic()+5
        while client.alive() and time.monotonic()<deadline:app.processEvents();time.sleep(.02)
        assert not client.alive();(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
