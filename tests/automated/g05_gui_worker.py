"""Separate GUI PROCESS used to verify that closing it leaves acquisition alive."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vic_control.service import Service
from vic_control.window import Window

p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--close-file',type=Path,required=True);a=p.parse_args()
class Bounded(Service):
    def start(self,settings,adapter):settings['seconds']=60;return super().start(settings,adapter)
app=QApplication([]);window=Window(Bounded(a.data));window.delay.setValue(1000);window.show();started=False
def tick():
    global started
    if not started and window.start.isEnabled():QTest.mouseClick(window.start,Qt.LeftButton);started=True
    if window.seen_ready:(a.data/'gui-ready.txt').write_text('READY',encoding='utf-8')
    if a.close_file.exists():window.close()
timer=QTimer();timer.timeout.connect(tick);timer.start(20);QTimer.singleShot(45000,window.close)
raise SystemExit(app.exec())
