"""Exercise the native UI's real Engine bridge without changing a user camera session."""
import base64
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'control'))
from vic_control.winui_bridge import Bridge


def main():
    backend = ROOT / 'out/06-sequence/build/VICEngine.exe'
    assert backend.is_file(), backend
    with tempfile.TemporaryDirectory(prefix='vic09-', dir=ROOT / 'out') as folder:
        bridge = Bridge(folder, backend)
        config = bridge.run({'op': 'set_config', 'value': {
            'name': 'VIC Test', 'model': 'VIC-1000', 'serial': 'VIC09TEST',
            'source_kind': 'pattern', 'path': '', 'width': 640, 'height': 480,
            'pixel_format': 0x01080001, 'trigger_mode': 0, 'fps_milli': 30000,
        }})
        assert config['source_kind'] == 'pattern'
        assert bridge.run({'op': 'status'})['engine_alive'] is False
        try:
            bridge.run({'op': 'start_engine'})
            bridge.run({'op': 'apply'})
            bridge.run({'op': 'begin'})
            frame = None
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and frame is None:
                frame = bridge.run({'op': 'frame', 'value': {'after': 0}})
                if frame is None:
                    time.sleep(.05)
            assert frame is not None, 'no shared Engine frame'
            assert (frame['width'], frame['height']) == (640, 480)
            assert base64.b64decode(frame['jpeg'])[:3] == b'\xff\xd8\xff'
            assert bridge.run({'op': 'frame', 'value': {'after': 2**63}}) is None
            bridge.run({'op': 'end'})
            status = bridge.run({'op': 'status'})
            assert status['engine']['acquiring'] == 0
            print(json.dumps({'result': 'PASS', 'frame_id': frame['frame_id'], 'size': '640x480'}))
        finally:
            if bridge.engine.alive():
                bridge.run({'op': 'stop_engine'})
            bridge.engine.close_preview()
            deadline = time.monotonic() + 5
            while bridge.engine.alive() and time.monotonic() < deadline:
                time.sleep(.05)


if __name__ == '__main__':
    main()
