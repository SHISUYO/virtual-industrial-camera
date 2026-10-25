"""Scoped Fluent-inspired styling for the VIC 06 PySide6 dashboard."""

PANEL_STYLE = """
QMainWindow, QWidget#workspace, QWidget#mainArea { background: #edf4fb; color: #182f55; }
QFrame#sidebar { background: #eaf2fb; border-right: 1px solid #d3e2f3; }
QLabel#brand { color: #103472; font-size: 16px; font-weight: 700; padding: 7px 8px 12px 8px; }
QLabel#sideStatus { color: #158255; font-size: 10px; padding: 8px; }
QLabel#muted, QLabel#description { color: #71829d; font-size: 10px; }
QLabel#heading { color: #0d3277; font-size: 27px; font-weight: 700; }
QLabel#transportBadge { background: #dceeff; color: #1367cf; border-radius: 13px;
    padding: 7px 13px; font-size: 10px; font-weight: 700; }
QListWidget#navigation { background: transparent; border: 0; outline: 0;
    color: #24406c; font-size: 11px; }
QListWidget#navigation::item { border-radius: 8px; padding: 12px 13px; margin: 2px 0; }
QListWidget#navigation::item:hover { background: #dbeaff; }
QListWidget#navigation::item:selected { background: #d2e6ff; color: #075ec4;
    border-left: 3px solid #0871ef; font-weight: 700; }
QFrame#summaryCard, QFrame#contentCard, QFrame#previewCard,
QFrame#metricsCard, QFrame#logCard {
    background: #ffffff; border: 1px solid #dce7f3; border-radius: 11px;
}
QFrame#summaryItem { border-left: 1px solid #dfe7f1; }
QLabel#cameraSymbol { background: #dce9f6; color: #1c61a9;
    border-radius: 8px; font-size: 27px; }
QLabel#cameraName { color: #12377a; font-size: 17px; font-weight: 700; }
QLabel#cameraState { color: #7a8aa0; font-size: 10px; font-weight: 700; }
QLabel#cameraState[running="true"] { color: #079558; }
QLabel#gigeState { color: #567399; font-size: 10px; }
QLabel#metaCaption { color: #7687a3; font-size: 10px; }
QLabel#metaValue { color: #15356d; font-size: 11px; font-weight: 700; }
QLabel#sectionTitle { color: #183b76; font-size: 12px; font-weight: 700; }
QLabel#kpiValue { color: #123a80; font-size: 22px; font-weight: 700; }
QLabel#quickValue { color: #173b75; font-size: 11px; font-weight: 700; }
QFrame#kpiCard { background: #fbfdff; border: 1px solid #e0eaf6; border-radius: 9px; }
QFrame#quickCard { background: #f5f9fe; border: 1px solid #e0eaf6; border-radius: 9px; }
QScrollArea#contentScroll { background: transparent; border: 0; }
QTabWidget::pane { background: transparent; border: 0; }
QTabBar::tab { background: transparent; color: #637899; border: 0;
    border-bottom: 2px solid transparent; padding: 7px 16px; }
QTabBar::tab:selected { color: #086bd6; border-bottom: 2px solid #0871ef;
    font-weight: 700; }
QTabBar::tab:hover:!selected { background: #ebf3ff; color: #1f4f91; }
QLabel { color: #344c70; }
QLineEdit, QSpinBox, QComboBox {
    background: #ffffff; color: #1d3355; border: 1px solid #bccce1;
    border-radius: 6px; padding: 5px 8px; min-height: 21px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 2px solid #438cdb; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background: #edf1f6; color: #77869c;
}
QPushButton { background: #ffffff; color: #244775; border: 1px solid #c6d7eb;
    border-radius: 6px; padding: 6px 12px; min-height: 24px; font-weight: 600; }
QPushButton:hover:enabled { background: #eaf3ff; border-color: #79a9e5; }
QPushButton:pressed:enabled { background: #d6e8ff; }
QPushButton:focus { border: 2px solid #357bd0; }
QPushButton:disabled { background: #edf1f6; color: #8c9bb0; border-color: #dfe7f0; }
QPushButton#primaryAction { background: #0c70e8; color: #ffffff; border-color: #0c70e8; }
QPushButton#primaryAction:hover:enabled { background: #075ec8; border-color: #075ec8; }
QPushButton#primaryAction:disabled { background: #c9d9ed; color: #6e83a0; border-color: #c9d9ed; }
QPushButton#dangerAction { color: #37557d; }
QPushButton#sideButton { text-align: left; padding-left: 12px; }
QCheckBox { color: #344c70; spacing: 8px; }
QPlainTextEdit { background: #101d2d; color: #cfe2f8; border: 1px solid #233851;
    border-radius: 7px; padding: 7px; font-family: Consolas; font-size: 9px; }
QLabel#previewSurface { background: #152339; color: #dceafa; border-radius: 7px; }
QLabel#footer { background: #deedff; color: #255186;
    border-radius: 7px; padding: 8px 12px; }
"""
