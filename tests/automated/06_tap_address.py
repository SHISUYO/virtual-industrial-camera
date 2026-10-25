"""Read-only TAP guard regression: absent address is not an absent NIC."""
import json,sys,time,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from vic_control.gige06 import select_tap,tap_inventory,GigESourceService
from vic_control.engine06 import DEFAULTS

def main():
    report={}
    nic={'name':'VIC-PoC-TAP','guid':'fixture','index':23,'status':'Disconnected','driver':'9.27.0.0','addresses':[]}
    cases=[('missing',[],'未找到'),('duplicate',[nic,nic],'多个'),('no_address',[nic],'已找到'),('apipa',[dict(nic,addresses=[{'IPAddress':'169.254.177.9','PrefixLength':16,'SkipAsSource':False}])],'169.254.177.9/16')]
    for name,items,message in cases:
        with patch('vic_control.gige06.tap_inventory',return_value=items),patch.object(GigESourceService,'start') as start:
            service=GigESourceService(ROOT/'out/06-tap-address/guard-data')
            try:service.publish(dict(DEFAULTS,name='VIC',serial='TAPTEST'))
            except RuntimeError as e:assert message in str(e),str(e)
            else:raise AssertionError(name)
            start.assert_not_called();report[name]='PASS'
    good={'IPAddress':'10.203.0.1','PrefixLength':24,'SkipAsSource':False}
    for label,changes in [('wrong_prefix',{'PrefixLength':16}),('skip',{'SkipAsSource':True}),('wrong_ip',{'IPAddress':'10.203.0.3'})]:
        try:select_tap([dict(nic,addresses=[dict(good,**changes)])])
        except RuntimeError as e:assert '地址配置不符' in str(e)
        else:raise AssertionError(label)
        report[label]='PASS'
    selected=select_tap([dict(nic,addresses=[good,{'IPAddress':'169.254.1.1','PrefixLength':16,'SkipAsSource':False}])])
    assert selected['index']==23 and selected['ip']=='10.203.0.1';report['identity_not_address_count']='PASS'
    current=select_tap(tap_inventory());assert current['guid'].upper()=='{FA1317AE-2D52-4DAA-A4EC-1D116C7C1504}'
    report['real_inventory']='PASS'
    out=ROOT/'tests/evidence/06-tap-address';out.mkdir(parents=True,exist_ok=True)
    from PySide6.QtWidgets import QApplication,QFileDialog
    from vic_control.panel06 import Panel,application_style
    from vic_control.engine06 import EngineClient
    app=QApplication([]);application_style(app)
    panel=Panel(EngineClient(ROOT/'out/06-tap-address/export-data'));target=out/'export-check.zip'
    def drain():
        deadline=time.monotonic()+20
        while panel.jobs:
            app.processEvents();time.sleep(.01)
            if time.monotonic()>deadline:raise RuntimeError('GUI export timed out')
    drain();panel.poll_timer.stop();panel.preview_timer.stop()
    with patch.object(QFileDialog,'getSaveFileName',return_value=(str(target),'ZIP')):panel.export_logs()
    drain()
    with zipfile.ZipFile(target) as z:
        exported=json.loads(z.read('tap-current.json'));assert exported['status']=='PASS'
        assert select_tap(exported['adapters'])['ip']=='10.203.0.1'
    report['export_current_adapter_without_backend_session']='PASS'
    panel.grab().save(str(out/'gui-06-0.6.4.png'));panel.close();app.processEvents()
    (out/'guards.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
