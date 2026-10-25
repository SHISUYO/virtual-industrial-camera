"""Actual Qt widgets/rendering only; never starts a camera or edits networking.

Windows Settings theme/DPI switches remain manual. This exercises application
color-scheme changes and QT_SCALE_FACTOR in isolated processes.
"""
import argparse,json,os,sys,time
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QPalette,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QStyleOptionViewItem,QStyle
from vic_control.service import Service
from vic_control.window import Window


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    out=args.out.resolve();out.mkdir(parents=True);app=QApplication([]);report={'status':'FAIL','platform':app.platformName(),'scale_environment':os.environ.get('QT_SCALE_FACTOR','1'),'cases':[]}
    with TemporaryDirectory() as temp:
        # Only the read-only NIC inventory is replaced. Both real QComboBoxes,
        # models, selection/delegate/style and all rendering remain real.
        with patch('vic_control.window.enumerate_adapters',return_value=[]):window=Window(Service(Path(temp)))
        window.show()
        def settle():app.processEvents();QTest.qWait(60);app.processEvents()
        def screenshot(widget,name):
            image=widget.grab().toImage();image.save(str(out/(name+'.png')));return image
        def colors(image):return Counter(image.pixelColor(x,y).name() for y in range(image.height()) for x in range(image.width()))
        def require_text(image,background,foreground):
            counts=colors(image)
            assert counts[background]>20,(background,counts.most_common(5))
            # Fully covered interior glyph pixels, not just the antialias halo.
            assert counts[foreground]>3,(foreground,counts.most_common(5))
        try:
            settle()
            while window.jobs:settle()
            combo=window.mode;original=[combo.itemText(i) for i in range(combo.count())];assert len(original)==2 and all(original)
            assert combo.itemDelegate().metaObject().className()=='QStyledItemDelegate'
            assert window.nic.itemDelegate().metaObject().className()=='QStyledItemDelegate'
            report['data_before']=original;report['delegate']=combo.itemDelegate().metaObject().className();report['device_pixel_ratio']=combo.devicePixelRatioF()
            light=QPalette(app.palette());dark=QPalette(light)
            for role,color in [(QPalette.Window,'#202020'),(QPalette.Base,'#202020'),(QPalette.Button,'#303030'),(QPalette.Text,'#ffffff'),(QPalette.ButtonText,'#ffffff'),(QPalette.WindowText,'#ffffff'),(QPalette.Highlight,'#ffffff'),(QPalette.HighlightedText,'#ffffff')]:dark.setColor(role,QColor(color))
            # Includes deliberately identical incoming highlight/foreground colors;
            # local QSS must restore contrast without deleting selection.
            for scheme,palette in [('light',light),('dark',dark),('light-restored',light)]:
                app.styleHints().setColorScheme(Qt.ColorScheme.Dark if scheme=='dark' else Qt.ColorScheme.Light)
                app.setPalette(palette);settle()
                for row in (0,1):
                    combo.setCurrentIndex(row);settle();assert combo.currentText()==original[row]
                    require_text(screenshot(combo,f'{scheme}-{row}-closed'),'#ffffff','#1f2937')
                    combo.showPopup();settle();view=combo.view();index=combo.model().index(row,0);rect=view.visualRect(index)
                    assert view.currentIndex().row()==row
                    image=screenshot(view,f'{scheme}-{row}-popup')
                    ratio=image.devicePixelRatio();selected=image.copy(round(rect.x()*ratio),round(rect.y()*ratio),round(rect.width()*ratio),round(rect.height()*ratio))
                    require_text(selected,'#1663d6','#ffffff')
                    # Hover another row and verify its glyphs remain visible.
                    other=1-row;QTest.mouseMove(view.viewport(),view.visualRect(combo.model().index(other,0)).center());settle()
                    image=screenshot(view,f'{scheme}-{row}-hover');hover_rect=view.visualRect(combo.model().index(other,0));ratio=image.devicePixelRatio()
                    hovered=image.copy(round(hover_rect.x()*ratio),round(hover_rect.y()*ratio),round(hover_rect.width()*ratio),round(hover_rect.height()*ratio))
                    if colors(hovered)['#1663d6']>20:require_text(hovered,'#1663d6','#ffffff')
                    else:require_text(hovered,'#dbeafe','#1f2937')
                    # Keyboard updates selection and the collapsed currentText.
                    QTest.keyClick(view,Qt.Key_Down if row==0 else Qt.Key_Up);settle()
                    assert view.currentIndex().row()==other
                    QTest.keyClick(view,Qt.Key_Return);settle();assert combo.currentIndex()==other and combo.currentText()==original[other]
                    require_text(screenshot(combo,f'{scheme}-{row}-keyboard-closed'),'#ffffff','#1f2937')
                    combo.showPopup();settle();QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualRect(combo.model().index(row,0)).center());settle()
                    assert combo.currentIndex()==row and combo.currentText()==original[row] and not view.isVisible()
                    report['cases'].append({'scheme':scheme,'row':row,'index_text':'PASS','expanded_selected_text':'PASS','collapsed_text':'PASS','keyboard':'PASS','hover':'PASS','mouse_selection':'PASS'})
                # Disabled MODEL item and a disabled entire COMBO are separate.
                item=combo.model().item(1);item.setEnabled(False);combo.setCurrentIndex(0);combo.showPopup();settle()
                view=combo.view();rect=view.visualRect(combo.model().index(1,0));image=screenshot(view,scheme+'-disabled-item');ratio=image.devicePixelRatio()
                disabled=image.copy(round(rect.x()*ratio),round(rect.y()*ratio),round(rect.width()*ratio),round(rect.height()*ratio))
                require_text(disabled,'#f1f5f9','#64748b')
                QTest.keyClick(view,Qt.Key_Down);settle();assert view.currentIndex().row()==0
                combo.hidePopup();item.setEnabled(True);combo.setCurrentIndex(1);combo.setEnabled(False);settle()
                require_text(screenshot(combo,scheme+'-disabled-combo'),'#e8edf4','#64748b')
                combo.setEnabled(True);settle();assert combo.currentText()==original[1]
                report[scheme+'_disabled']='PASS'
            assert [combo.itemText(i) for i in range(combo.count())]==original
            report['status']='PASS';report['system_theme_switch']='NOT TESTED: application override only';report['system_dpi_switch']='NOT TESTED: QT_SCALE_FACTOR only'
        finally:
            combo.hidePopup()
            while window.jobs:settle()
            window.close();app.processEvents();(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
