import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'control'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from vic_control.panel06 import Panel,application_style
from vic_control.engine06 import EngineClient
p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--ready',type=Path,required=True);a=p.parse_args()
app=QApplication([]);application_style(app);client=EngineClient(a.data);client.start(seconds=90);client.request(4);panel=Panel(client);panel.show()
QTimer.singleShot(500,lambda:a.ready.write_text('READY'))
raise SystemExit(app.exec())
