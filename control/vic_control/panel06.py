import json,os,sys,time,zipfile
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QLockFile,QLocale
from PySide6.QtGui import QFont,QFontDatabase,QPalette,QColor,QImage,QPixmap,QPainter,QPen
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QLineEdit,QComboBox,QSpinBox,QPushButton,QCheckBox,QTabWidget,QPlainTextEdit,QFileDialog,QMessageBox,QListWidget,QScrollArea)
from .combo_style import style_combo
from .fluent_style import PANEL_STYLE
from .window import Work
from .engine06 import EngineClient,DEFAULTS,ROOT
from .gige06 import GigESourceService

BUILD='06-0.6.8'


def application_style(app):
    app.setStyle('Fusion');palette=QPalette()
    for role,color in [(QPalette.Window,'#eef2f6'),(QPalette.WindowText,'#1f2937'),(QPalette.Base,'#ffffff'),(QPalette.Text,'#1f2937'),(QPalette.Button,'#ffffff'),(QPalette.ButtonText,'#1f2937'),(QPalette.Highlight,'#1663d6'),(QPalette.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
    for role in [QPalette.Text,QPalette.ButtonText,QPalette.WindowText]:palette.setColor(QPalette.Disabled,role,QColor('#64748b'))
    palette.setColor(QPalette.Disabled,QPalette.Base,QColor('#e8edf4'))
    app.setPalette(palette);app.setFont(QFont('Microsoft YaHei UI',10))
    if app.platformName()=='offscreen':
        for name in ['msyh.ttc','consola.ttf']:QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))


def camera_glyph():
    pixmap=QPixmap(54,54);pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor('#245887'),2));painter.setBrush(QColor('#c6d8e9'))
    painter.drawRoundedRect(7,16,40,27,5,5);painter.drawRoundedRect(13,12,14,5,2,2)
    painter.setBrush(QColor('#eef6ff'));painter.drawEllipse(21,21,17,17)
    painter.setBrush(QColor('#4080bc'));painter.drawEllipse(26,26,7,7)
    painter.end();return pixmap


class Panel(QMainWindow):
    def __init__(self,client=None):
        super().__init__();self.client=client or EngineClient();self.jobs=[];self.pending_action=None;self.probe_failed=None;self.state={};self.image=None;self.last_frame=0;self.offset=0;self.gige_offset=0;self.gige_session=None;self.bridge=GigESourceService(self.client.data/'gigE')
        self.setWindowTitle('VIC Control · '+BUILD);self.resize(1500,920);self.setMinimumSize(1100,740)
        widget=QWidget();widget.setObjectName('workspace');self.setCentralWidget(widget)
        shell=QHBoxLayout(widget);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(210);side=QVBoxLayout(sidebar);side.setContentsMargins(14,24,14,18);side.setSpacing(14)
        brand=QLabel('VIC Control');brand.setObjectName('brand');side.addWidget(brand)
        self.nav=QListWidget();self.nav.setObjectName('navigation');self.nav.setFocusPolicy(Qt.NoFocus);side.addWidget(self.nav,1)
        self.side_status=QLabel('●  本地 Engine 未运行');self.side_status.setObjectName('sideStatus');self.side_status.setWordWrap(True);self.status=self.side_status;side.addWidget(self.side_status)
        version=QLabel('Version '+BUILD);version.setObjectName('muted');side.addWidget(version)
        shell.addWidget(sidebar)
        main=QWidget();main.setObjectName('mainArea');layout=QVBoxLayout(main);layout.setContentsMargins(20,18,20,14);layout.setSpacing(11);shell.addWidget(main,1)
        header=QHBoxLayout();layout.addLayout(header)
        titles=QVBoxLayout();titles.setSpacing(1);heading=QLabel('VIC Control');heading.setObjectName('heading');titles.addWidget(heading)
        subtitle=QLabel('虚拟工业相机控制与图像采集');subtitle.setObjectName('description');titles.addWidget(subtitle);header.addLayout(titles)
        transport=QLabel('GigE Vision / TAP-Windows6');transport.setObjectName('transportBadge');header.addWidget(transport,0,Qt.AlignVCenter);header.addStretch(1)
        summary=QFrame();summary.setObjectName('summaryCard');summary_layout=QVBoxLayout(summary);summary_layout.setContentsMargins(16,12,16,12);summary_layout.setSpacing(8)
        summary_top=QHBoxLayout();summary_layout.addLayout(summary_top)
        camera_symbol=QLabel();camera_symbol.setObjectName('cameraSymbol');camera_symbol.setFixedSize(54,54);camera_symbol.setAlignment(Qt.AlignCenter);camera_symbol.setPixmap(camera_glyph());summary_top.addWidget(camera_symbol)
        identity=QVBoxLayout();identity.setSpacing(1);self.summary_name=QLabel('VIC-1000');self.summary_name.setObjectName('cameraName');identity.addWidget(self.summary_name)
        self.summary_state=QLabel('●  未发布');self.summary_state.setObjectName('cameraState');identity.addWidget(self.summary_state);summary_top.addLayout(identity)
        summary_top.addStretch(1)
        self.start_engine=QPushButton('启动本地预览 Engine');self.stop_engine=QPushButton('关闭本地 Engine');self.reconnect=QPushButton('重新连接');self.gige=QPushButton('启动 VisionPro 相机');self.stop_gige=QPushButton('停止 VisionPro 相机')
        self.gige.setObjectName('primaryAction');self.stop_gige.setObjectName('dangerAction')
        for button in [self.gige,self.stop_gige]:summary_top.addWidget(button)
        for index,button in enumerate([self.start_engine,self.stop_engine,self.reconnect],2):
            button.setObjectName('sideButton');side.insertWidget(index,button)
        self.start_engine.clicked.connect(lambda:self.job(self.client.start,self.started));self.stop_engine.clicked.connect(lambda:self.call(1));self.reconnect.clicked.connect(self.attach);self.gige.clicked.connect(self.publish_gige);self.stop_gige.clicked.connect(lambda:self.job(self.bridge.stop,lambda _:self.footer.setText('正在停止 GigE 相机，请在 VisionPro 断开后更换来源。')))
        self.gige_state=QLabel('GigE 相机未启动；启动本地 Engine 不会使 VisionPro 发现设备。')
        self.gige_state.setObjectName('gigeState');self.gige_state.setWordWrap(True);summary_layout.addWidget(self.gige_state)
        summary_meta=QHBoxLayout();summary_meta.setSpacing(0);summary_layout.addLayout(summary_meta)
        self.summary_values={}
        for title,key in [('传输模式','transport'),('相机 IP','ip'),('网络适配器','adapter'),('像素格式','pixel'),('分辨率','size'),('目标帧率','fps')]:
            cell=QFrame();cell.setObjectName('summaryItem');stack=QVBoxLayout(cell);stack.setContentsMargins(12,4,12,3);stack.setSpacing(2)
            caption=QLabel(title);caption.setObjectName('metaCaption');stack.addWidget(caption)
            value=QLabel('—');value.setObjectName('metaValue');value.setWordWrap(True);stack.addWidget(value);self.summary_values[key]=value;summary_meta.addWidget(cell,1)
        layout.addWidget(summary)
        body=QHBoxLayout();body.setSpacing(11);layout.addLayout(body,1)
        content=QFrame();content.setObjectName('contentCard');content_layout=QVBoxLayout(content);content_layout.setContentsMargins(12,10,12,10)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();content_layout.addWidget(self.tabs)
        scroll=QScrollArea();self.content_scroll=scroll;scroll.setObjectName('contentScroll');scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setWidget(content);body.addWidget(scroll,3)
        overview=QWidget();overview_layout=QVBoxLayout(overview);overview_layout.setContentsMargins(4,4,4,4);overview_layout.setSpacing(10)
        overview_title=QLabel('运行状态');overview_title.setObjectName('sectionTitle');overview_layout.addWidget(overview_title)
        kpi_grid=QGridLayout();kpi_grid.setSpacing(8);overview_layout.addLayout(kpi_grid)
        self.kpi_values={}
        for i,(key,title) in enumerate([('fps','本地平均 FPS'),('frame','本地 FrameID'),('generated','本地产生帧'),('dropped','模拟丢帧'),('previewed','预览写入帧'),('consumer','VisionPro 连接')]):
            card=QFrame();card.setObjectName('kpiCard');stack=QVBoxLayout(card);stack.setContentsMargins(13,11,13,11)
            caption=QLabel(title);caption.setObjectName('metaCaption');stack.addWidget(caption)
            value=QLabel('—');value.setObjectName('kpiValue');stack.addWidget(value);self.kpi_values[key]=value;kpi_grid.addWidget(card,i//3,i%3)
        guide=QLabel('以上帧数与帧率只来自本地预览 Engine；当前版本不提供 VisionPro 消费端收包统计。')
        guide.setObjectName('muted');guide.setWordWrap(True);overview_layout.addWidget(guide)
        quick=QFrame();quick.setObjectName('quickCard');quick_layout=QVBoxLayout(quick);quick_layout.setContentsMargins(15,13,15,13)
        quick_title=QLabel('采集参数概览');quick_title.setObjectName('sectionTitle');quick_layout.addWidget(quick_title)
        quick_grid=QGridLayout();quick_grid.setSpacing(8);quick_layout.addLayout(quick_grid);self.quick_values={}
        for index,(key,title) in enumerate([('source','图像源'),('packet','GVSP Packet Size'),('trigger','采集模式'),('delay','触发延迟')]):
            label=QLabel(title);label.setObjectName('metaCaption');value=QLabel('—');value.setObjectName('quickValue');value.setWordWrap(True)
            row=index//2;column=(index%2)*2;quick_grid.addWidget(label,row,column);quick_grid.addWidget(value,row,column+1);self.quick_values[key]=value
        quick_buttons=QHBoxLayout();quick_layout.addLayout(quick_buttons)
        for label,action in [('编辑图像源',2),('编辑采集控制',3)]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,index=action:self.tabs.setCurrentIndex(index));quick_buttons.addWidget(button)
        quick_buttons.addStretch(1);overview_layout.addWidget(quick);overview_layout.addStretch(1)
        self.tabs.addTab(overview,'概览');self.nav.addItem('概览')
        self.fields={};self.immutable=[]
        device=self.page('设备管理');self.line(device,'name','设备名称',31);self.line(device,'model','型号',31);self.line(device,'serial','序列号',15)
        hint=QLabel('GigE身份要求ASCII：名称/序列号最多15字符、型号最多31字符。旧名称过长时请修改；停止相机并在VisionPro断开后更换身份。');hint.setWordWrap(True);device.addRow(hint)
        source=self.page('图像源');self.source=QComboBox();style_combo(self.source)
        for label,key in [('测试图','pattern'),('单张图片','image'),('图片文件夹','sequence'),('视频','video')]:self.source.addItem(label,key)
        source.addRow('来源',self.source);self.immutable.append(self.source)
        self.path=QLineEdit();self.browse=QPushButton('选择文件 / 文件夹');source.addRow('路径',self.path);source.addRow(self.browse);self.immutable.extend([self.path,self.browse])
        self.source.currentIndexChanged.connect(lambda _:self.path.clear() if self.source.currentData()=='pattern' else None)
        self.fit=QCheckBox('保持比例并补黑边');self.fit.setChecked(True);source.addRow(self.fit);self.immutable.append(self.fit);self.browse.clicked.connect(self.choose_source)
        self.source_apply=QPushButton('应用并预览此来源');source.addRow(self.source_apply);self.source_apply.clicked.connect(self.apply_and_preview)
        self.source_note=QLabel('选择文件后请应用；修改来源时会清除旧预览，避免显示上一来源的画面。');self.source_note.setWordWrap(True);source.addRow(self.source_note)
        self.auto_size=QCheckBox('选文件时自动设置宽高（序列按文件名排序取首张）');self.auto_size.setChecked(True);source.addRow(self.auto_size)
        self.detect_size=QPushButton('读取当前来源分辨率');source.addRow(self.detect_size);self.detect_size.clicked.connect(self.detect_source_size);self.immutable.extend([self.auto_size,self.detect_size])
        acquire=self.page('采集控制');self.spin(acquire,'width','宽度',1,6000);self.spin(acquire,'height','高度',1,6000)
        acquire.addRow(QLabel('输出范围1–6000；大图建议降低FPS。选文件时可自动读取原始尺寸。'))
        self.pixel=QComboBox();style_combo(self.pixel);self.pixel.addItem('Mono8',0x01080001);self.pixel.addItem('RGB8',0x02180014);acquire.addRow('像素格式',self.pixel);self.immutable.append(self.pixel)
        self.fps=QSpinBox();self.fps.setRange(1,60);acquire.addRow('目标 FPS',self.fps)
        self.trigger=QComboBox();style_combo(self.trigger);self.trigger.addItems(['连续','软件触发']);acquire.addRow('采集模式',self.trigger);self.immutable.append(self.trigger)
        self.apply=QPushButton('应用配置（停止采集时）');self.begin=QPushButton('开始预览采集');self.end=QPushButton('停止采集');self.fire=QPushButton('软件触发')
        for button in [self.apply,self.begin,self.end,self.fire]:acquire.addRow(button)
        self.apply.clicked.connect(self.apply_config);self.begin.clicked.connect(lambda:self.call(4));self.end.clicked.connect(lambda:self.call(5));self.fire.clicked.connect(lambda:self.call(6))
        preview=self.page('实时预览');hint=QLabel('右侧图像来自 Engine 共享内存，GUI 最多每100ms读取最新帧。预览跳过不等于模拟丢帧，也不等于 Consumer 丢帧。');hint.setWordWrap(True);preview.addRow(hint)
        self.actual=QLabel('等待实际配置');self.actual.setWordWrap(True);preview.addRow(self.actual)
        fault=self.page('故障注入');self.delay=QSpinBox();self.delay.setRange(0,5000);self.delay.setSuffix(' ms');fault.addRow('触发延迟',self.delay)
        self.drop=QSpinBox();self.drop.setRange(0,100);self.drop.setSuffix(' %');fault.addRow('生成后模拟丢帧率',self.drop)
        self.seed=QSpinBox();self.seed.setRange(1,2147483647);fault.addRow('随机种子',self.seed)
        self.runtime=QPushButton('在线应用 FPS / 延迟 / 丢帧参数');fault.addRow(self.runtime);self.runtime.clicked.connect(lambda:self.call(7,self.runtime_settings()))
        logpage=self.page('日志与状态');log_hint=QLabel('下方日志区持续显示本地 Engine 与 GigE 后台原始输出；可导出诊断 ZIP。GVCP/GVSP 尚未单独分类。');log_hint.setWordWrap(True);logpage.addRow(log_hint)
        right=QVBoxLayout();right.setSpacing(12);body.addLayout(right,2)
        preview_card=QFrame();preview_card.setObjectName('previewCard');preview_layout=QVBoxLayout(preview_card);preview_layout.setContentsMargins(14,12,14,14)
        preview_title=QLabel('实时预览');preview_title.setObjectName('sectionTitle');preview_layout.addWidget(preview_title)
        self.preview=QLabel('等待 Engine 图像');self.preview.setObjectName('previewSurface');self.preview.setAlignment(Qt.AlignCenter);self.preview.setMinimumSize(310,250);preview_layout.addWidget(self.preview,1)
        right.addWidget(preview_card,1)
        metrics_card=QFrame();metrics_card.setObjectName('metricsCard');metrics_layout=QVBoxLayout(metrics_card);metrics_layout.setContentsMargins(14,12,14,12)
        metrics_title=QLabel('采集状态');metrics_title.setObjectName('sectionTitle');metrics_layout.addWidget(metrics_title)
        self.metrics=QLabel('本地预览状态：Engine 未运行\nVisionPro 取图结果请在 VisionPro 中查看。');self.metrics.setWordWrap(True);metrics_layout.addWidget(self.metrics)
        right.addWidget(metrics_card)
        log_card=QFrame();log_card.setObjectName('logCard');log_layout=QVBoxLayout(log_card);log_layout.setContentsMargins(12,9,12,9);log_layout.setSpacing(4)
        log_header=QHBoxLayout();log_layout.addLayout(log_header);log_title=QLabel('运行日志');log_title.setObjectName('sectionTitle');log_header.addWidget(log_title);log_header.addStretch(1)
        self.export=QPushButton('导出诊断日志');log_header.addWidget(self.export);self.export.clicked.connect(self.export_logs)
        self.log_tabs=QTabWidget();self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.document().setMaximumBlockCount(2000);self.gige_logs=QPlainTextEdit();self.gige_logs.setReadOnly(True);self.gige_logs.document().setMaximumBlockCount(2000)
        self.log_tabs.addTab(self.logs,'本地 Engine');self.log_tabs.addTab(self.gige_logs,'GigE 后台');self.log_tabs.setMinimumHeight(118);log_layout.addWidget(self.log_tabs)
        layout.addWidget(log_card,0)
        self.footer=QLabel('修改配置后先应用，再开始预览采集；关闭界面后 Engine 继续运行，重开可接管。')
        self.footer.setObjectName('footer');self.footer.setWordWrap(True);layout.addWidget(self.footer)
        self.nav.currentRowChanged.connect(self.tabs.setCurrentIndex);self.tabs.currentChanged.connect(self.nav.setCurrentRow)
        self.tabs.currentChanged.connect(lambda index:scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if index==0 else Qt.ScrollBarAsNeeded))
        self.nav.setCurrentRow(0);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(PANEL_STYLE)
        settings=dict(DEFAULTS)
        try:settings.update(json.loads((self.client.data/'settings.json').read_text(encoding='utf-8')))
        except (OSError,ValueError):pass
        self.load_settings(settings);self.poll_timer=QTimer(self);self.poll_timer.timeout.connect(self.poll);self.poll_timer.start(500)
        self.preview_timer=QTimer(self);self.preview_timer.timeout.connect(self.paint_preview);self.preview_timer.start(100);self.update_controls();self.poll()
    def page(self,title):
        page=QWidget();form=QFormLayout(page);form.setContentsMargins(12,18,12,10);form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft);self.tabs.addTab(page,title);self.nav.addItem(title);return form
    def line(self,form,key,label,length):
        field=QLineEdit();field.setMaxLength(length);self.fields[key]=field;self.immutable.append(field);form.addRow(label,field)
    def spin(self,form,key,label,lo,hi):
        field=QSpinBox();field.setRange(lo,hi);field.setLocale(QLocale.c());field.setGroupSeparatorShown(False);field.setKeyboardTracking(False);field.setMinimumWidth(130);self.fields[key]=field;self.immutable.append(field);form.addRow(label,field)
    def load_settings(self,c):
        for k,w in self.fields.items():w.setText(str(c[k])) if isinstance(w,QLineEdit) else w.setValue(c[k])
        self.source.setCurrentIndex(max(0,self.source.findData(c['source_kind'])));self.path.setText(c['path']);self.fit.setChecked(bool(c['fit']));self.pixel.setCurrentIndex(max(0,self.pixel.findData(c['pixel_format'])));self.fps.setValue(c['fps_milli']//1000);self.trigger.setCurrentIndex(c['trigger_mode']);self.delay.setValue(c['delay_us']//1000);self.drop.setValue(c['drop_percent']);self.seed.setValue(c['seed'])
        self.refresh_dashboard()
    def refresh_dashboard(self):
        published=self.bridge.alive();local=self.client.alive()
        try:config=self.bridge.record['settings']['source'] if published else self.state.get('config') if local and self.state else None
        except (KeyError,TypeError):config=None
        if not config:
            config={'model':self.fields['model'].text(),'width':self.fields['width'].value(),'height':self.fields['height'].value(),'pixel_format':self.pixel.currentData(),'fps_milli':self.fps.value()*1000}
        self.summary_name.setText(str(config.get('model') or 'VIC 相机'))
        self.summary_state.setText('●  GigE 已发布' if published else '●  GigE 未发布')
        if self.summary_state.property('running')!=published:
            self.summary_state.setProperty('running',published);self.summary_state.style().unpolish(self.summary_state);self.summary_state.style().polish(self.summary_state)
        values={'transport':'GigE Vision','ip':'10.203.0.2' if published else '—','adapter':'VIC-PoC-TAP' if published else '待发布',
                'pixel':'RGB8' if config.get('pixel_format')==0x02180014 else 'Mono8',
                'size':f"{config.get('width','—')} × {config.get('height','—')}",
                'fps':f"{config.get('fps_milli',0)/1000:g} FPS"}
        for key,value in values.items():self.summary_values[key].setText(value)
        self.quick_values['source'].setText(str(config.get('source_kind') or self.source.currentData()))
        self.quick_values['packet'].setText(str(self.bridge.record['settings']['packet_size'])+' B' if published else '1400 B（发布时）')
        self.quick_values['trigger'].setText('软件触发' if config.get('trigger_mode',self.trigger.currentIndex()) else '连续')
        self.quick_values['delay'].setText(str(config.get('delay_us',self.delay.value()*1000)//1000)+' ms')
        state=self.state if local else {}
        self.kpi_values['fps'].setText(f"{state.get('average_fps',0):.2f}" if state else '—')
        for key,field in [('frame','frame_id'),('generated','generated'),('dropped','simulated_dropped'),('previewed','previewed')]:
            self.kpi_values[key].setText(str(state[field]) if field in state else '—')
        self.kpi_values['consumer'].setText('未提供')
        if not local:self.side_status.setText('●  本地 Engine 未运行')
    def runtime_settings(self):return {'fps_milli':self.fps.value()*1000,'delay_us':self.delay.value()*1000,'drop_percent':self.drop.value(),'seed':self.seed.value()}
    def settings(self):
        for key in ('width','height'):self.fields[key].interpretText()
        if self.auto_size.isChecked() and self.probe_failed==(self.source.currentData(),self.path.text()):
            raise ValueError('自动分辨率读取失败；请选择有效来源，或关闭自动检测后手动设置输出尺寸。')
        if self.source.currentData()=='pattern' and self.path.text().strip():
            suffix=Path(self.path.text()).suffix.lower()
            if suffix in ('.png','.jpg','.jpeg','.bmp'):self.source.setCurrentIndex(self.source.findData('image'))
            else:raise ValueError('当前选择测试图但填有文件路径，请选择图片、图片文件夹或视频。')
        c={k:(w.text() if isinstance(w,QLineEdit) else w.value()) for k,w in self.fields.items()};c.update(self.runtime_settings());c.update(source_kind=self.source.currentData(),path=self.path.text(),fit=int(self.fit.isChecked()),pixel_format=self.pixel.currentData(),trigger_mode=self.trigger.currentIndex());return c
    def job(self,fn,callback=None,background=False):
        if self.jobs:
            if not background and all(w.background for w in self.jobs) and self.pending_action is None:
                self.pending_action=(fn,callback);self.update_controls()
            return
        work=Work(fn,self);work.background=background;self.jobs.append(work);work.result.connect(callback or self.received);work.error.connect(self.error)
        def done():
            self.jobs.remove(work)
            if self.pending_action is not None:
                action=self.pending_action;self.pending_action=None;self.job(*action)
            self.update_controls()
        work.finished.connect(done);self.update_controls();work.start()
    def call(self,command,payload=None,background=False):
        def complete(state):
            self.received(state)
            if command==3:self.clear_old_preview()
            if command!=2 and not state.get('error'):
                self.footer.setText({1:'Engine 正在关闭',3:'配置已应用',4:'采集已开始',5:'采集已停止',6:'软件触发请求已接受',7:'运行参数已应用'}.get(command,'操作已完成'))
        self.job(lambda:self.client.request(command,payload),complete,background=background)
    def apply_config(self):
        try:self.call(3,self.settings())
        except Exception as e:self.error(str(e))
    def started(self,state):self.offset=0;self.last_frame=0;self.received(state);self.footer.setText('Engine 已启动，应用配置后开始预览采集。')
    def received(self,state):
        if not isinstance(state,dict):return
        if 'acquiring' not in state:self.state={};self.client.close_preview();self.update_controls();return
        self.state=state;c=state['config'];self.status.setText('Engine '+('采集中' if state['acquiring'] else '空闲')+' · '+c['name'])
        if int(state.get('max_width',0))<6000 or not state.get('sequence_resume'):
            self.image=None;self.preview.clear();self.preview.setText('旧版本地Engine：仅预览需关闭后重新启动\n不影响顶部启动VisionPro相机')
        if self.image and self.last_frame<=int(state.get('source_frame_floor',0)):
            self.image=None;self.preview.clear();self.preview.setText('当前来源尚无新采集帧')
        self.actual.setText(f"本地生效：{c['width']}×{c['height']} · {'RGB8' if c['pixel_format']==0x02180014 else 'Mono8'} · {c['fps_milli']/1000:g} FPS · {c['source_kind']}\n来源：{c['path'] or '测试图'}\nGenTL未实现；VisionPro走顶部GigE入口。")
        self.metrics.setText(f"FrameID {state['frame_id']}\n产生 {state['generated']} · 预览写入 {state['previewed']}\n模拟丢帧 {state['simulated_dropped']} · 预览写入跳过 {state['preview_skipped']}\n平均生成 FPS {state['average_fps']:.2f}\nGenTL交付：未实现；GigE取图请查看VisionPro")
        if state.get('error'):self.error(state['error'])
        self.refresh_dashboard();self.update_controls()
    def update_controls(self):
        alive=self.client.alive();busy=self.pending_action is not None or any(not w.background for w in self.jobs);acquiring=alive and bool(self.state.get('acquiring'));published=self.bridge.alive();modern=int(self.state.get('max_width',0))>=6000 and bool(self.state.get('sequence_resume'))
        self.start_engine.setEnabled(not alive and not busy);self.stop_engine.setEnabled(alive and not busy);self.reconnect.setEnabled(not busy)
        for w in self.immutable:w.setEnabled(not acquiring and not busy and not published)
        self.apply.setEnabled(alive and not acquiring and not busy and not published);self.source_apply.setEnabled(not acquiring and not busy and not published);self.begin.setEnabled(alive and not acquiring and not busy);self.end.setEnabled(acquiring and not busy);self.fire.setEnabled(acquiring and bool(self.state.get('config',{}).get('trigger_mode')) and not busy);self.runtime.setEnabled(alive and not busy and not published)
        for w in [self.fps,self.delay,self.drop,self.seed]:w.setEnabled(not published and not busy)
        self.gige.setEnabled(not published and not busy);self.stop_gige.setEnabled(published and not busy)
        if alive and not modern:
            for w in [self.apply,self.source_apply,self.begin]:w.setEnabled(False)
    def poll(self):
        if self.bridge.alive():
            c=self.bridge.record['settings']['source'];full=c['path'] or '测试图'
            self.gige_state.setText('当前发布：'+c['source_kind']+' · '+Path(full).name+'；本地预览独立运行。')
            self.gige_state.setToolTip(full)
        else:self.gige_state.setText('GigE 相机未运行；更换来源前请先在 VisionPro 断开。')
        if self.bridge.record:
            session=self.bridge.record.get('session')
            if session!=self.gige_session:
                self.gige_session=session;self.gige_offset=0;self.gige_logs.clear()
            try:
                with (Path(session)/'console.txt').open('rb') as f:f.seek(self.gige_offset);chunk=f.read(65536);self.gige_offset+=len(chunk)
                if chunk:self.gige_logs.appendPlainText(chunk.decode('utf-8',errors='replace'))
            except (OSError,TypeError):pass
        self.refresh_dashboard()
        if not self.client.alive():self.status.setText('●  本地 Engine 未运行');self.update_controls();return
        if not self.jobs:self.call(2,background=True)
        if self.client.record:
            try:
                with (Path(self.client.record['session'])/'console.txt').open('rb') as f:f.seek(self.offset);chunk=f.read(65536);self.offset+=len(chunk)
                if chunk:self.logs.appendPlainText(chunk.decode('utf-8',errors='replace'))
            except OSError:pass
    def paint_preview(self):
        try:
            if int(self.state.get('max_width',0))<6000 or not self.state.get('sequence_resume'):return
            frame=self.client.frame(after_id=max(self.last_frame,int(self.state.get('source_frame_floor',0))))
            if frame and frame['frame_id']>int(self.state.get('source_frame_floor',0)) and frame['frame_id']!=self.last_frame:
                self.last_frame=frame['frame_id'];fmt=QImage.Format_RGB888 if frame['pixel_format']==0x02180014 else QImage.Format_Grayscale8
                self.image=QImage(frame['pixels'],frame['width'],frame['height'],frame['width']*(3 if fmt==QImage.Format_RGB888 else 1),fmt).copy();self.show_image()
        except Exception as e:self.error(str(e));self.client.close_preview()
    def show_image(self):
        if self.image:self.preview.setPixmap(QPixmap.fromImage(self.image).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def resizeEvent(self,event):super().resizeEvent(event);self.show_image()
    def attach(self):
        self.client.close_preview();self.client=EngineClient(self.client.data,self.client.backend);self.last_frame=0;self.offset=0;self.state={};self.poll()
    def choose_source(self):
        kind=self.source.currentData()
        if kind=='sequence':path=QFileDialog.getExistingDirectory(self,'选择图片文件夹')
        else:path,_=QFileDialog.getOpenFileName(self,'选择图像源','','图像或视频 (*.png *.jpg *.jpeg *.bmp *.avi *.mp4 *.mkv *.mov *.wmv);;所有文件 (*.*)')
        if path:
            inferred='sequence' if kind=='sequence' else ('image' if Path(path).suffix.lower() in ('.png','.jpg','.jpeg','.bmp') else 'video')
            self.source.setCurrentIndex(self.source.findData(inferred));self.path.setText(path);self.source_note.setText('待应用：'+inferred+' · '+path+'。点击“应用并预览此来源”或“启动 VisionPro 相机”。')
            if self.auto_size.isChecked():self.detect_source_size()
    def detect_source_size(self):
        self.probe_failed=None
        try:config=self.settings()
        except Exception as e:self.error(str(e));return
        if config['source_kind']=='pattern':self.footer.setText('测试图无文件原始尺寸，可手动设置宽高。');return
        self.probe_failed=(config['source_kind'],config['path'])
        def complete(dimensions):
            if (self.source.currentData(),self.path.text())!=(config['source_kind'],config['path']):return
            self.probe_failed=None
            self.fields['width'].setValue(dimensions['width']);self.fields['height'].setValue(dimensions['height']);self.footer.setText(f"已读取来源：{dimensions['width']}×{dimensions['height']}；应用配置或启动VisionPro相机后生效。")
        self.job(lambda:self.client.probe_source(config),complete)
    def clear_old_preview(self):
        frame=self.client.frame();self.last_frame=int(self.state.get('source_frame_floor',frame['frame_id'] if frame else 0));self.image=None;self.preview.clear();self.preview.setText('新来源已应用，等待新采集帧');self.source_note.setText('生效：'+self.state.get('config',{}).get('source_kind','')+' · '+self.state.get('config',{}).get('path',''))
    def apply_and_preview(self):
        try:config=self.settings()
        except Exception as e:self.error(str(e));return
        def run():
            if not self.client.alive():self.client.start()
            state=self.client.request(2)
            if int(state.get('max_width',0))<6000 or not state.get('sequence_resume'):raise RuntimeError('请关闭旧版本地Engine后重新启动06-0.6.5。')
            self.client.request(3,config);return self.client.request(4)
        self.job(run,lambda s:(self.received(s),self.clear_old_preview(),self.footer.setText('当前来源已应用并开始本地预览。')))
    def publish_gige(self):
        try:config=self.settings()
        except Exception as e:self.error(str(e));return
        self.footer.setText('正在初始化 VisionPro 相机；图片文件夹需逐张校验，最多等待120秒，请稍候。')
        def run():
            return self.bridge.publish(config)
        self.job(run,lambda _:self.footer.setText('GigE相机已启动：10.203.0.2，请在VisionPro重新发现。发布的是当前表单来源；参数更换前需停止GigE并断开Consumer。'))
    def open_gige(self):
        executable=(Path(sys.executable).parent/'G05/VICControl.exe') if getattr(sys,'frozen',False) else ROOT/'out/g05/Release-combobox/VICControl/VICControl.exe'
        if executable.is_file():
            import subprocess
            subprocess.Popen([str(executable)],creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:self.error('未找到保留的 G05：'+str(executable))
    def export_logs(self):
        target,_=QFileDialog.getSaveFileName(self,'导出 Engine 诊断日志','VIC06-diagnostics.zip','ZIP (*.zip)')
        if not target:return
        def export():
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                from .gige06 import tap_inventory
                try:inventory={'status':'PASS','adapters':tap_inventory()}
                except Exception as e:inventory={'status':'FAIL','error':str(e)}
                z.writestr('tap-current.json',json.dumps(inventory,ensure_ascii=False,indent=2))
                for name in ['active.json','settings.json']:
                    p=self.client.data/name
                    if p.is_file():z.write(p,name)
                if self.client.record:
                    p=Path(self.client.record['session'])/'console.txt'
                    if p.is_file():z.write(p,'console.txt')
                if self.bridge.record:
                    folder=Path(self.bridge.record['session'])
                    for p in folder.rglob('*'):
                        if p.is_file():z.write(p,'gigE/'+str(p.relative_to(folder)))
            return target
        self.job(export,lambda p:self.footer.setText('诊断日志已导出：'+p))
    def error(self,text):self.footer.setText('错误：'+text);self.logs.appendPlainText('ERROR '+text)
    def closeEvent(self,event):
        if self.jobs:event.ignore();self.footer.setText('正在完成 Engine 请求，请稍后关闭。');return
        self.poll_timer.stop();self.preview_timer.stop();self.client.close_preview();event.accept()


def main():
    app=QApplication(sys.argv);application_style(app);client=EngineClient();lock=QLockFile(str(client.data/'gui.lock'))
    if not lock.tryLock(0):QMessageBox.information(None,'VIC Control','06控制界面已经打开。');return 1
    panel=Panel(client);panel.show()
    if '--self-check' in sys.argv:
        path=Path(sys.argv[sys.argv.index('--self-check')+1])
        def done():
            if panel.jobs:return QTimer.singleShot(100,done)
            path.parent.mkdir(parents=True,exist_ok=True);panel.grab().save(str(path));panel.close();app.quit()
        QTimer.singleShot(800,done)
    code=app.exec();lock.unlock();return code
