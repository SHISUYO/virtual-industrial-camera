import codecs,ipaddress,json,re,sys,time
from pathlib import Path
from PySide6.QtCore import QThread,Signal,QTimer,Qt,QLockFile
from PySide6.QtGui import QFont,QFontDatabase,QPalette,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QComboBox,QSpinBox,QLineEdit,QCheckBox,QPlainTextEdit,QTabWidget,QGroupBox,QFileDialog,QMessageBox)
from . import VERSION
from .combo_style import style_combo
from .service import Service,enumerate_adapters,atomic_json

class Work(QThread):
    result=Signal(object);error=Signal(str)
    def __init__(self,fn,parent):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.result.emit(self.fn())
        except Exception as e:self.error.emit(str(e))

class Window(QMainWindow):
    def __init__(self,service=None):
        super().__init__();self.service=service or Service();self.jobs=[];self.adapter_items=[];self.offset=0;self.partial='';self.seen_ready=False;self.last_alive=None
        # The Qt offscreen platform on Windows does not enumerate system fonts.
        # Explicitly loading an installed font also makes render checks meaningful.
        if QApplication.platformName()=='offscreen':
            import os
            for name in ['msyh.ttc','consola.ttf']:
                QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
        QApplication.setStyle('Fusion')
        palette=QPalette()
        for role,color in [(QPalette.Window,'#eef2f6'),(QPalette.WindowText,'#1f2937'),(QPalette.Base,'#ffffff'),(QPalette.AlternateBase,'#f1f5f9'),(QPalette.Text,'#1f2937'),(QPalette.Button,'#ffffff'),(QPalette.ButtonText,'#1f2937'),(QPalette.Highlight,'#1663d6'),(QPalette.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
        QApplication.setPalette(palette)
        self.decoder=codecs.getincrementaldecoder('utf-8')('replace');self.setWindowTitle('VIC Control · '+VERSION);self.resize(1100,800)
        self.setFont(QFont('Microsoft YaHei UI',10))
        self.setStyleSheet('QMainWindow{background:#eef2f6} QGroupBox{background:white;border:1px solid #d8e0eb;border-radius:8px;margin-top:16px;padding:16px} QGroupBox::title{left:14px;color:#334155} QPushButton{padding:8px 18px;border:1px solid #b7c5d8;border-radius:5px;background:white} QPushButton#primary{background:#1663d6;color:white;border:0} QPushButton:disabled,QPushButton#primary:disabled{color:#8a95a6;background:#e8edf4} QLineEdit,QSpinBox,QComboBox{padding:6px;background:white;border:1px solid #bccadb;border-radius:4px} QPlainTextEdit{background:#101c2d;color:#d1e0f4;border-radius:5px;font-family:Consolas;font-size:10pt} QLabel#title{font-size:23px;font-weight:700;color:#15253d}')
        content=QWidget();self.setCentralWidget(content);layout=QVBoxLayout(content);layout.setContentsMargins(24,16,24,18)
        title=QLabel('VIC Control');title.setObjectName('title');layout.addWidget(title)
        self.state=QLabel('检查相机服务…');layout.addWidget(self.state)
        setup=QGroupBox('相机与连接');grid=QGridLayout(setup);layout.addWidget(setup)
        self.mode=QComboBox();self.mode.addItems(['GigE Vision · TAP','GenTL（项目尚未实现）']);self.mode.currentIndexChanged.connect(self.update_controls)
        self.nic=QComboBox();self.refresh=QPushButton('刷新网卡');self.refresh.clicked.connect(self.refresh_adapters)
        for combo in (self.mode,self.nic):style_combo(combo)
        self.camera=QLineEdit('10.203.0.2');self.packet=QSpinBox();self.packet.setRange(220,1500);self.packet.setSingleStep(4);self.packet.setValue(1400)
        self.delay=QSpinBox();self.delay.setRange(0,5000);self.delay.setSuffix(' ms')
        self.drop=QSpinBox();self.drop.setRange(0,100);self.drop.setSuffix(' %')
        self.seed=QSpinBox();self.seed.setRange(1,2147483647);self.seed.setValue(1)
        self.capture=QCheckBox('记录 TAP 抓包（最高 256 MiB）')
        items=[('传输模式',self.mode),('专用网卡 / 宿主 IPv4',self.nic),('虚拟相机 IPv4',self.camera),('启动默认 Packet Size',self.packet),('启动触发延迟',self.delay),('GVSP Payload 模拟丢包率',self.drop),('故障随机种子',self.seed)]
        for row,(label,widget) in enumerate(items):grid.addWidget(QLabel(label),row//2,(row%2)*2);grid.addWidget(widget,row//2,(row%2)*2+1)
        grid.addWidget(self.refresh,3,2);grid.addWidget(self.capture,3,3)
        hint=QLabel('参数在启动时应用；Consumer 可修改 Packet Size 和触发延迟，下方显示实际生效值。');hint.setWordWrap(True);grid.addWidget(hint,4,0,1,4)
        buttons=QHBoxLayout();self.start=QPushButton('启动 GigE 服务');self.start.setObjectName('primary');self.stop=QPushButton('停止服务');self.export=QPushButton('导出诊断日志');self.folder=QPushButton('打开日志目录')
        for b in [self.start,self.stop,self.export,self.folder]:buttons.addWidget(b)
        buttons.addStretch();layout.addLayout(buttons)
        self.start.clicked.connect(self.start_service);self.stop.clicked.connect(self.stop_service);self.export.clicked.connect(self.export_logs);self.folder.clicked.connect(self.open_folder)
        stats=QGroupBox('实时状态');sg=QGridLayout(stats);layout.addWidget(stats);self.values={}
        labels=[('controller','控制连接'),('acquiring','采集状态'),('generated_fps','实际产生 FPS'),('submitted_fps','完整帧提交 FPS'),('generated','产生帧数'),('submitted_frames','完整提交帧数'),('submitted_packets','提交包数'),('simulated_drop_packets','模拟丢弃包数'),('packet_size','生效 Packet Size'),('trigger_delay_us','生效触发延迟 (µs)')]
        for i,(key,label) in enumerate(labels):
            value=QLabel('—');value.setStyleSheet('font-size:17px;font-weight:600;color:#174a87');self.values[key]=value;sg.addWidget(QLabel(label),i//5*2,i%5);sg.addWidget(value,i//5*2+1,i%5)
        note=QLabel('提交成功不等于接收端有效图像；网络实际丢包和 Consumer 有效帧以接收端或抓包验证为准。');note.setWordWrap(True);sg.addWidget(note,4,0,1,5)
        self.tabs=QTabWidget();self.logs={}
        for key,label in [('all','服务日志'),('gvcp','GVCP 连接 / 控制'),('gvsp','GVSP 取流 / 统计')]:
            view=QPlainTextEdit();view.setReadOnly(True);view.document().setMaximumBlockCount(2000);self.logs[key]=view;self.tabs.addTab(view,label)
        layout.addWidget(self.tabs,1)
        self.footer=QLabel('先启动服务，再在 VisionPro 选择 VIC。关闭本界面后相机继续运行，再次打开可管理同一服务。');self.footer.setWordWrap(True);layout.addWidget(self.footer)
        try:
            settings=json.loads((self.service.data/'settings.json').read_text(encoding='utf-8'))
            self.camera.setText(settings.get('camera_ip','10.203.0.2'));self.packet.setValue(settings.get('packet_size',1400));self.delay.setValue(settings.get('delay_ms',0));self.drop.setValue(settings.get('drop_percent',0));self.seed.setValue(settings.get('seed',1));self.capture.setChecked(settings.get('capture',False))
        except (OSError,ValueError):pass
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(500);self.poll();self.refresh_adapters()
    def background(self,fn,callback):
        job=Work(fn,self);self.jobs.append(job);job.result.connect(callback);job.error.connect(self.error)
        job.finished.connect(lambda:self.jobs.remove(job));job.start()
    def refresh_adapters(self):
        self.refresh.setEnabled(False);self.nic.clear();self.nic.addItem('读取已部署的 TAP 网卡…')
        def ready(items):
            self.adapter_items=items;self.nic.clear()
            for x in items:self.nic.addItem(f"{x['name']} · {x['ip']}/24 · {x['status']}",x)
            if not items:self.nic.addItem('未找到专用 VIC-PoC-TAP /24 地址')
            self.update_controls()
        self.background(enumerate_adapters,ready)
    def update_controls(self):
        alive=self.service.alive();gig=self.mode.currentIndex()==0
        for widget in [self.mode,self.nic,self.camera,self.packet,self.delay,self.drop,self.seed,self.capture]:widget.setEnabled(not alive)
        self.refresh.setEnabled(not alive);self.start.setEnabled(not alive and gig and bool(self.nic.currentData()));self.stop.setEnabled(alive)
        self.export.setEnabled(self.service.record is not None);self.folder.setEnabled(self.service.record is not None)
        if not gig and not alive:self.state.setText('GenTL 模式：未实现，无可用 CTI；本阶段没有伪造 Producer。')
    def settings(self):
        adapter=self.nic.currentData()
        if not adapter:raise RuntimeError('未找到已部署的专用 TAP 网卡，请使用现有部署记录核查；本界面不会安装或改网卡。')
        camera=ipaddress.IPv4Address(self.camera.text().strip());host=ipaddress.IPv4Address(adapter['ip'])
        network=ipaddress.IPv4Network(str(host)+'/24',strict=False)
        if camera==host or camera not in network or camera in (network.network_address,network.broadcast_address):raise RuntimeError('相机 IP 须为同一 /24 内与宿主不同的有效地址。')
        if adapter['skip']:raise RuntimeError('宿主地址 SkipAsSource=true；请先核查部署配置，本界面不修改它。')
        if self.packet.value()%4:raise RuntimeError('Packet Size 必须是 4 的倍数。')
        return {'camera_ip':str(camera),'packet_size':self.packet.value(),'delay_ms':self.delay.value(),'drop_percent':self.drop.value(),'seed':self.seed.value(),'capture':self.capture.isChecked(),'seconds':28800}
    def start_service(self):
        try:
            self.service.start(self.settings(),self.nic.currentData());self.offset=0;self.partial='';self.decoder.reset();self.seen_ready=False
            for view in self.logs.values():view.clear()
            self.last_alive=None;self.update_controls()
        except Exception as e:self.error(str(e))
    def stop_service(self):
        self.stop.setEnabled(False)
        self.background(self.service.stop,lambda _:self.state.setText('停止请求已接收，等待已提交 I/O 归还…'))
    def poll(self):
        record=self.service.record
        if record:
            try:
                with (Path(record['session'])/'console.txt').open('rb') as f:
                    f.seek(self.offset);chunk=f.read(512*1024);self.offset+=len(chunk)
                self.partial+=self.decoder.decode(chunk);lines=self.partial.split('\n');self.partial=lines.pop()
                for line in lines:
                    line=line.rstrip('\r');self.logs['all'].appendPlainText(line)
                    if 'GVCP ' in line:self.logs['gvcp'].appendPlainText(line)
                    if any(x in line for x in ['STREAM_CONFIG','METRICS','IO_PROFILE','CAPTURE_DISABLED']):self.logs['gvsp'].appendPlainText(line)
                    if 'READY build=G05-0.5.0' in line:self.seen_ready=True
                    if 'METRICS ' in line:
                        fields=dict(re.findall(r'(\w+)=([^ ]+)',line))
                        for key,value in self.values.items():
                            text=fields.get(key,'—')
                            if key=='controller':text='未连接' if text=='0' else str(ipaddress.IPv4Address(int(text)))
                            elif key=='acquiring':text='正在采集' if text=='1' else '空闲'
                            elif key.endswith('_fps'):text=f'{float(text):.2f}'
                            value.setText(text)
            except (OSError,ValueError):pass
        alive=self.service.alive()
        if alive:self.state.setText(('服务运行中' if self.seen_ready else '服务启动中…')+' · '+str(record['settings']['camera_ip'])+' · '+record['adapter']['name'])
        elif self.mode.currentIndex()==0:self.state.setText('服务已停止' if record else '服务未启动 · 请选择已部署的 TAP 网卡')
        if alive!=self.last_alive:self.last_alive=alive;self.update_controls()
    def export_logs(self):
        target,_=QFileDialog.getSaveFileName(self,'导出诊断日志',str(Path.home()/('VIC-diagnostics-'+time.strftime('%Y%m%d_%H%M%S')+'.zip')),'ZIP (*.zip)')
        if target:self.background(lambda:self.service.export(target),lambda path:self.footer.setText('诊断日志已导出：'+path))
    def open_folder(self):
        import os
        if self.service.record:os.startfile(self.service.record['session'])
    def error(self,text):self.footer.setText('错误：'+text);self.refresh.setEnabled(True);self.update_controls()
    def closeEvent(self,event):
        # GUI never terminates an active camera or an external Consumer.
        if any(job.isRunning() for job in self.jobs):event.ignore();self.footer.setText('正在完成后台操作，请稍后关闭。');return
        self.timer.stop();event.accept()

def main():
    app=QApplication(sys.argv);app.setApplicationName('VIC Control');service=Service();lock=QLockFile(str(service.data/'gui.lock'));lock.setStaleLockTime(10000)
    if not lock.tryLock(0):QMessageBox.information(None,'VIC Control','控制界面已经打开。');return 1
    window=Window(service);window.show()
    if '--self-check' in sys.argv:
        target=Path(sys.argv[sys.argv.index('--self-check')+1]);deadline=time.monotonic()+25
        def check():
            if window.jobs and time.monotonic()<deadline:return
            target.parent.mkdir(parents=True,exist_ok=True);window.grab().save(str(target));window.close();app.quit()
        smoke=QTimer();smoke.timeout.connect(check);smoke.start(100)
    code=app.exec();lock.unlock();return code
