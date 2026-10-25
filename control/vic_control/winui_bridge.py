"""Small JSON-line adapter over the existing 06 Engine and GigE controllers.

The bridge uses the same per-user session records and validation as the PySide6
GUI. It does not configure Windows networking or implement camera protocols.
"""
import base64
import json
import os
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from .engine06 import DEFAULTS, EngineClient
from .gige06 import GigESourceService, tap_inventory


def tail(path, limit=32768):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - limit))
            return stream.read().decode('utf-8', errors='replace')
    except (OSError, TypeError):
        return ''


class Bridge:
    def __init__(self, data=None, backend=None):
        self.engine = EngineClient(data or os.environ.get('VIC09_TEST_DATA'), backend)
        self.camera = GigESourceService(self.engine.data / 'gigE')
        self.config = dict(DEFAULTS)
        try:
            self.config.update(json.loads((self.engine.data / 'settings.json').read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pass
        self.last_frame = 0

    def status(self):
        engine_alive = self.engine.alive()
        camera_alive = self.camera.alive()
        engine_state = self.engine.request(2) if engine_alive else None
        source = self.camera.record['settings']['source'] if camera_alive else None
        return {
            'engine_alive': engine_alive,
            'camera_alive': camera_alive,
            'engine': engine_state,
            'published': source,
            'camera_ip': self.camera.record['settings']['camera_ip'] if camera_alive else None,
            'packet_size': self.camera.record['settings']['packet_size'] if camera_alive else None,
            'adapter': self.camera.record['adapter'] if camera_alive else None,
            'config': self.config,
            'engine_log': tail(Path(self.engine.record['session']) / 'console.txt', 8192) if self.engine.record else '',
            'camera_log': tail(Path(self.camera.record['session']) / 'console.txt', 8192) if self.camera.record else '',
        }

    def set_config(self, update):
        if not isinstance(update, dict):
            raise ValueError('config must be an object')
        unknown = set(update) - set(DEFAULTS)
        if unknown:
            raise ValueError('unknown config fields: ' + ', '.join(sorted(unknown)))
        self.config.update(update)
        return self.config

    def frame(self, after=0):
        if not self.engine.alive():
            return None
        frame = self.engine.frame(after_id=max(int(after), self.last_frame))
        if not frame:
            return None
        self.last_frame = frame['frame_id']
        fmt = QImage.Format_RGB888 if frame['pixel_format'] == 0x02180014 else QImage.Format_Grayscale8
        stride = frame['width'] * (3 if fmt == QImage.Format_RGB888 else 1)
        image = QImage(frame['pixels'], frame['width'], frame['height'], stride, fmt).copy()
        image = image.scaled(900, 650, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer, 'JPG', 85):
            raise RuntimeError('preview JPEG encoding failed')
        return {'frame_id': frame['frame_id'], 'width': frame['width'], 'height': frame['height'],
                'jpeg': base64.b64encode(bytes(data)).decode('ascii')}

    def run(self, request):
        op = request.get('op')
        if op == 'status':
            return self.status()
        if op == 'set_config':
            return self.set_config(request.get('value'))
        if op == 'start_engine':
            return self.engine.start()
        if op == 'stop_engine':
            return self.engine.request(1)
        if op == 'apply':
            return self.engine.request(3, self.config)
        if op == 'begin':
            return self.engine.request(4)
        if op == 'end':
            return self.engine.request(5)
        if op == 'trigger':
            return self.engine.request(6)
        if op == 'runtime':
            return self.engine.request(7, request.get('value'))
        if op == 'probe':
            return self.engine.probe_source(self.config)
        if op == 'apply_and_preview':
            if not self.engine.alive():
                self.engine.start()
            state = self.engine.request(2)
            if int(state.get('max_width', 0)) < 6000 or not state.get('sequence_resume'):
                raise RuntimeError('请先正常关闭旧版本地 Engine，再使用当前版本。')
            self.engine.request(3, self.config)
            self.last_frame = 0
            return self.engine.request(4)
        if op == 'publish':
            return self.camera.publish(self.config)
        if op == 'stop_camera':
            return self.camera.stop()
        if op == 'frame':
            return self.frame((request.get('value') or {}).get('after', 0))
        if op == 'tap_inventory':
            return tap_inventory()
        if op == 'export':
            target = Path(request.get('value', '')).resolve()
            if target.suffix.lower() != '.zip':
                raise ValueError('诊断文件必须是 ZIP')
            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                try:
                    inventory = {'status': 'PASS', 'adapters': tap_inventory()}
                except Exception as exc:
                    inventory = {'status': 'FAIL', 'error': str(exc)}
                archive.writestr('tap-current.json', json.dumps(inventory, ensure_ascii=False, indent=2))
                for name in ('active.json', 'settings.json'):
                    path = self.engine.data / name
                    if path.is_file():
                        archive.write(path, name)
                if self.engine.record:
                    path = Path(self.engine.record['session']) / 'console.txt'
                    if path.is_file():
                        archive.write(path, 'console.txt')
                if self.camera.record:
                    folder = Path(self.camera.record['session'])
                    for path in folder.rglob('*'):
                        if path.is_file():
                            archive.write(path, 'gigE/' + str(path.relative_to(folder)))
            return str(target)
        raise ValueError('unsupported operation: ' + str(op))


def main():
    bridge = Bridge()
    for line in sys.stdin.buffer:
        request = None
        try:
            request = json.loads(line)
            response = {'id': request.get('id'), 'ok': True, 'result': bridge.run(request)}
        except Exception as exc:
            response = {'id': request.get('id') if isinstance(request, dict) else None,
                        'ok': False, 'error': str(exc)}
        sys.stdout.buffer.write((json.dumps(response, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8'))
        sys.stdout.buffer.flush()
    return 0
