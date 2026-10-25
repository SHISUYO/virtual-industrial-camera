"""Independent Python/stdlib GVCP wire client. Hex transcript != packet capture.

Wire constants verified from Aravis 0.8.36 official upstream headers; see
docs/G01_PROTOCOL_SOURCES.md. Does not import the C++ implementation.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


class Client:
    def __init__(self, ip, trace):
        self.ip, self.trace, self.request_id = ip, trace, 100
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ip, 0))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(1)

    def record(self, direction, data, endpoint):
        self.trace.write(json.dumps(dict(time_ns=time.time_ns(), direction=direction,
                                       endpoint=endpoint, hex=data.hex())) + '\n')
        self.trace.flush()

    def exchange(self, command, payload=b'', status=0, destination=None, flags=1,
                 raw=None, silent=False):
        self.request_id = self.request_id % 65535 + 1
        packet = raw if raw is not None else struct.pack('!BBHHH', 0x42, flags, command,
                                                        len(payload), self.request_id) + payload
        target = (destination or self.ip, 3956)
        self.record('TX', packet, target)
        self.sock.sendto(packet, target)
        if silent:
            old = self.sock.gettimeout()
            self.sock.settimeout(.12)
            try:
                data, source = self.sock.recvfrom(2048)
                self.record('RX', data, source)
                raise AssertionError('Unexpected response to silent request')
            except socket.timeout:
                return b''
            finally:
                self.sock.settimeout(old)
        data, source = self.sock.recvfrom(2048)
        self.record('RX', data, source)
        assert source == (self.ip, 3956), source
        assert len(data) >= 8
        actual, ack, count, rid = struct.unpack('!HHHH', data[:8])
        expected_id = struct.unpack('!H', packet[6:8])[0]
        assert (actual, ack, rid) == (status, command + 1, expected_id), (actual, ack, rid, status)
        assert len(data) == 8 + count
        return data[8:]

    def read(self, *addresses, status=0):
        data = self.exchange(0x80, struct.pack('!' + 'I' * len(addresses), *addresses), status)
        return list(struct.unpack('!' + 'I' * (len(data) // 4), data))

    def write(self, address, value, status=0, **kwargs):
        data = self.exchange(0x82, struct.pack('!II', address, value), status, **kwargs)
        if not status and not kwargs.get('silent'):
            assert data == b'\0\0\0\1', data

    def memory(self, address, count, status=0):
        data = self.exchange(0x84, struct.pack('!IHH', address, 0, count), status)
        if status:
            return data
        assert data[:4] == struct.pack('!I', address)
        assert len(data) == count + 4
        return data[4:]


def exercise(ip, out, prefix, trace):
    a, b = Client(ip, trace), Client(ip, trace)
    results = []

    def passed(name):
        print('PASS:', name, flush=True)
        results.append(name)

    try:
        discovery = a.exchange(2)
        assert len(discovery) == 248
        assert discovery[0x48:0x68].split(b'\0')[0] == b'VIC Project'
        assert discovery[0x68:0x88].split(b'\0')[0] == b'VIC-1000-GE'
        assert discovery[0xd8:0xe8].split(b'\0')[0] == b'VICGE000001'
        assert discovery[0x24:0x28] == socket.inet_aton(ip)
        passed('unicast discovery and stable identity')
        assert a.exchange(2, destination='255.255.255.255', flags=0x11) == discovery
        broadcast = str(ipaddress.ip_interface(f'{ip}/{prefix}').network.broadcast_address)
        assert a.exchange(2, destination=broadcast) == discovery
        passed('global and subnet broadcast discovery, selected source IP')
        assert a.read(0x600, 0x900, 0x904) == [1, 0, 0]
        url = a.memory(0x200, 512).split(b'\0')[0].decode('ascii')
        scheme, address, size = url.split(';')
        assert scheme == 'Local:VIC_G01.xml'
        address, size = int(address, 16), int(size, 16)
        xml = bytearray()
        for offset in range(0, (size + 3) & ~3, 512):
            count = min(512, ((size + 3) & ~3) - offset)
            xml.extend(a.memory(address + offset, count))
        xml = bytes(xml[:size])
        (out / 'downloaded.xml').write_bytes(xml)
        tree = ET.fromstring(xml)
        assert tree.attrib['ModelName'] == 'VIC_1000_GE'  # XML ID restrictions; register identity unchanged.
        assert 'AcquisitionStart' not in xml.decode()
        passed('chunked XML memory read; no image stream advertised')
        a.write(0xa00, 2)
        assert a.read(0xa00) == [2]
        a.write(0x938, 300)
        assert a.read(0x938) == [300]
        b.write(0xa00, 2, status=0x8006)
        b.write(0x938, 999, status=0x8006)
        assert b.read(0x938) == [300]  # Shared read in control mode.
        passed('register write/read, single controller, observer access')
        for _ in range(3):
            time.sleep(.12)
            assert a.read(0xa00) == [2]
        b.write(0xa00, 2, status=0x8006)
        time.sleep(.42)
        b.write(0xa00, 1)
        a.read(0xa00, status=0x8006)
        a.memory(0x200, 4, status=0x8006)
        passed('heartbeat refresh/expiry takeover, exclusive read protection')
        b.write(0xa00, 0)
        a.write(0xa00, 2)
        a.write(0x938, 3000)
        a.read(1, status=0x8005)
        a.read(0xfffffffc, status=0x8003)
        a.memory(0xfffffffc, 8, status=0x8003)
        a.memory(0x1000, 4, status=0x8003)
        a.memory(0x200, 0, status=0x8002)
        a.memory(0x200, 516, status=0x8002)
        a.memory(0x201, 4, status=0x8005)
        a.memory(0x200, 3, status=0x8005)
        a.write(0x48, 0, status=0x8004)
        a.write(0x938, 99, status=0x8002)
        a.write(0xa00, 3, status=0x8002)
        a.exchange(0x82, struct.pack('!IIII', 0x938, 200, 0x48, 0), status=0x8004)
        assert a.read(0x938) == [3000]
        a.exchange(0x86, b'\0' * 8, status=0x8001)  # WriteMem unsupported, no capability bit.
        a.exchange(0x80, b'', status=0x8002)
        a.exchange(0x80, b'\0', status=0x8002)
        a.exchange(0x84, struct.pack('!IHH', 0x200, 1, 4), status=0x8002)
        a.exchange(0x80, struct.pack('!I', 0), flags=0x11, status=0x8002)
        a.exchange(0x80, raw=struct.pack('!BBHHH', 0x42, 1, 0x80, 4, 77), status=0x800e)
        a.exchange(0x80, raw=struct.pack('!BBHHH', 0x42, 1, 0x80, 0, 78) + b'\0', status=0x800e)
        a.exchange(0x80, b'\0' * 516, status=0x800e)
        passed('alignment/length/overflow/ROM/reserved flags/unsupported operation; no partial write')
        for n in range(8):
            a.exchange(0x80, raw=b'\x42' * n, silent=True)
        a.exchange(0x80, raw=b'\0' * 12, silent=True)
        if ip != '127.0.0.1':
            outside = Client('127.0.0.1', trace)
            try:
                outside.exchange(2, silent=True)
            finally:
                outside.sock.close()
            passed('nonselected loopback interface rejected')
        a.write(0x938, 2000, flags=0, silent=True)
        assert a.read(0x938) == [2000]
        a.write(0xa00, 0)
        b.write(0xa00, 2)
        b.write(0xa00, 0)
        passed('short/wrong-key silence, no-ACK execution, release/reopen')
        return results, discovery
    finally:
        a.sock.close()
        b.sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', required=True)
    parser.add_argument('--prefix', type=int, required=True)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    process = None
    with (args.out / 'server-console.txt').open('w', encoding='utf-8') as console, \
            (args.out / 'wire-transcript.jsonl').open('w', encoding='utf-8') as trace:
        try:
            if args.exe:
                # Never accept READY left by a previous test invocation.
                (args.out / 'server.txt').write_text('', encoding='utf-8')
                process = subprocess.Popen([str(args.exe.resolve()), '--bind', args.ip,
                    '--config', str(ROOT / 'assets/g01-camera.ini'), '--duration-ms', '12000',
                    '--log', str((args.out / 'server.txt').resolve()),
                    '--dump-xml', str((args.out / 'served.xml').resolve())], cwd=ROOT,
                    stdout=console, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Server exited before READY')
                    path = args.out / 'server.txt'
                    if path.exists() and 'READY ' in path.read_text(encoding='utf-8'):
                        break
                    time.sleep(.02)
                else:
                    raise TimeoutError('No server READY')
            results, first = exercise(args.ip, args.out, args.prefix, trace)
            sys.path.insert(0, str(ROOT / 'out/g01/python-tools'))
            from lxml import etree
            schema_path = Path('C:/Program Files/Cognex/Common/genicam/xml/GenApi/GenApiSchema_Version_1_1.xsd')
            etree.XMLSchema(etree.parse(str(schema_path))).assertValid(etree.parse(str(args.out / 'downloaded.xml')))
            print('PASS: installed GenApi 1.1 XSD validation', flush=True)
            if args.exe:
                assert (args.out / 'served.xml').read_bytes() == (args.out / 'downloaded.xml').read_bytes()
                assert process.wait(timeout=15) == 0
                # Rebind same port and verify identity remains identical after restart.
                (args.out / 'restart-server.txt').write_text('', encoding='utf-8')
                process = subprocess.Popen([str(args.exe.resolve()), '--bind', args.ip,
                    '--config', str(ROOT / 'assets/g01-camera.ini'), '--duration-ms', '1800',
                    '--log', str((args.out / 'restart-server.txt').resolve())],
                    cwd=ROOT, stdout=console, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                deadline = time.monotonic() + 4
                while 'READY ' not in (args.out / 'restart-server.txt').read_text(encoding='utf-8'):
                    assert time.monotonic() < deadline and process.poll() is None
                    time.sleep(.02)
                probe = Client(args.ip, trace)
                try:
                    assert probe.exchange(2) == first
                finally:
                    probe.sock.close()
                assert process.wait(timeout=4) == 0
                print('PASS: timed graceful stop, port rebind and persistent identity', flush=True)
                invalid = args.out / 'invalid-identity.ini'
                invalid.write_text('vendor=VIC Project\nmodel=VIC-1000-GE\nserial=' + 'X' * 16 + '\nuser_name=VIC\n', encoding='ascii')
                cases = [[], ['--bind', '0.0.0.0'], ['--bind', '203.0.113.42'],
                         ['--bind', args.ip, '--config', str(invalid.resolve())],
                         ['--bind', args.ip, '--duration-ms', '0'], ['--unknown', 'x']]
                with (args.out / 'invalid-startup.txt').open('w', encoding='utf-8') as failures:
                    for options in cases:
                        r = subprocess.run([str(args.exe.resolve())] + options, cwd=ROOT,
                            capture_output=True, timeout=4, creationflags=subprocess.CREATE_NO_WINDOW)
                        failures.write(repr(options) + '\n' + r.stderr.decode('utf-8', errors='replace'))
                        assert r.returncode == 1 and b'FATAL' in r.stderr
                print('PASS: unsafe/missing bind, nonlocal IP, overlong identity and invalid CLI rejected', flush=True)
            (args.out / 'result.json').write_text(json.dumps(dict(status='PASS', checks=results,
                schema='PASS', restart='PASS' if args.exe else 'NOT TESTED'), indent=2), encoding='utf-8')
        except Exception as error:
            (args.out / 'result.json').write_text(json.dumps(dict(status='FAIL', error=repr(error))), encoding='utf-8')
            raise
        finally:
            if process and process.poll() is None:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
