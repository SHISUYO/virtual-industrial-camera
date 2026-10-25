"""Read-only external Aravis consumer regression for G01; no acquisition."""
import argparse
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ip', required=True)
    args = p.parse_args()
    out = ROOT / 'tests/evidence/G01/aravis'
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(ROOT / 'out/g00/msys64/ucrt64/bin') + os.pathsep + env['PATH']
    tool = ROOT / 'out/g00/build/src/arv-tool-0.8.exe'
    with (out / 'server-console.txt').open('w', encoding='utf-8') as console:
        ready_log = out / 'server.txt'
        ready_log.write_text('', encoding='utf-8')
        server = subprocess.Popen([str(ROOT / 'out/g01/build/VICGigE.exe'), '--bind', args.ip,
            '--config', str(ROOT / 'assets/g01-camera.ini'), '--duration-ms', '15000',
            '--log', str(ready_log)], stdout=console, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, cwd=ROOT)
        try:
            deadline = time.monotonic() + 4
            while 'READY ' not in ready_log.read_text(encoding='utf-8'):
                assert time.monotonic() < deadline and server.poll() is None
                time.sleep(.02)
            def run(name, options):
                r = subprocess.run([str(tool)] + options, env=env, capture_output=True,
                                   timeout=7, creationflags=subprocess.CREATE_NO_WINDOW)
                (out / name).write_bytes(r.stdout + r.stderr)
                assert r.returncode == 0, r.stderr
                return r.stdout.decode('utf-8', errors='replace')
            found = run('discovery.txt', [])
            assert 'VICGE000001' in found and args.ip in found, found
            print('PASS: external Aravis discovery', flush=True)
            values = run('nodes.txt', ['-a', args.ip, 'control', 'DeviceVendorName',
                'DeviceModelName', 'DeviceSerialNumber', 'DeviceUserID', 'GevHeartbeatTimeout'])
            for expected in ['DeviceVendorName = VIC Project', 'DeviceModelName = VIC-1000-GE',
                             'DeviceSerialNumber = VICGE000001', 'GevHeartbeatTimeout = 3000']:
                assert expected in values, values
            print('PASS: external Aravis device open, GenApi XML parsing and node reads', flush=True)
            assert server.wait(timeout=17) == 0
        finally:
            if server.poll() is None:
                try:
                    server.wait(timeout=17)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    main()
