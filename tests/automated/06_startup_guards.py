"""Bounded startup waiting with delayed READY, early exit and retained ownership."""
import json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'control'))
from vic_control.gige06 import GigESourceService,STARTUP_TIMEOUT

def main():
    result={}
    with tempfile.TemporaryDirectory() as d:
        service=GigESourceService(Path(d));session=Path(d)/'sessions/test';session.mkdir(parents=True)
        service.record={'session':str(session)};clock=[0.0]
        def sleep(delay):clock[0]+=delay
        with patch('vic_control.gige06.time.monotonic',side_effect=lambda:clock[0]),patch('vic_control.gige06.time.sleep',side_effect=sleep),patch.object(service,'alive',return_value=True),patch.object(service,'observed',side_effect=lambda:{'ready':clock[0]>=9,'last_lines':''}),patch.object(service,'stop') as stop:
            service.wait_ready();assert clock[0]>=9;stop.assert_not_called()
            assert json.loads((session/'startup.json').read_text())['state']=='READY'
        result['ready_after_old_8s_limit']='PASS'
        clock[0]=0
        with patch('vic_control.gige06.time.monotonic',side_effect=lambda:clock[0]),patch('vic_control.gige06.time.sleep',side_effect=sleep),patch.object(service,'alive',return_value=True),patch.object(service,'observed',return_value={'ready':False}),patch.object(service,'stop') as stop:
            try:service.wait_ready(timeout=.2)
            except RuntimeError as e:assert '未自动停止' in str(e)
            else:raise AssertionError('No bounded timeout')
            stop.assert_not_called();assert service.record is not None
            assert json.loads((session/'startup.json').read_text())['state']=='TIMEOUT'
        result['timeout_retains_record_without_automatic_stop']='PASS'
        with patch.object(service,'alive',return_value=False),patch.object(service,'observed',return_value={'ready':True,'last_lines':'FAIL: invalid source'}):
            try:service.wait_ready()
            except RuntimeError as e:assert 'invalid source' in str(e)
            else:raise AssertionError('Dead process accepted as READY')
        result['early_exit_including_stale_ready_is_failure']='PASS'
        (session/'console.txt').write_text('READY build=06-GIGE-0.6.5\n'+'x'*150000+'\nMETRICS acquiring=0\n',encoding='utf-8')
        assert service.observed()['ready'];result['ready_retained_after_log_tail_rollover']='PASS'
    assert STARTUP_TIMEOUT==120
    out=ROOT/'tests/evidence/06-startup';out.mkdir(exist_ok=True,parents=True)
    (out/'guards.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
