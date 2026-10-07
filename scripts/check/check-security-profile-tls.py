#!/usr/bin/env python3
"""Actual localhost Nginx TLS checks using generated config and repository headers.

Uses an ephemeral self-signed certificate and a loopback echo backend, NOT the
SaaS application or a production certificate. Starts no external/persistent services.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
from threading import Thread
import time

HOST = 'school.example.test'


class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        value = json.dumps({'xff': self.headers.get('X-Forwarded-For'),
                            'real': self.headers.get('X-Real-IP'),
                            'proto': self.headers.get('X-Forwarded-Proto'),
                            'forwarded': self.headers.get('Forwarded')}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(value)))
        self.end_headers()
        self.wfile.write(value)

    def log_message(self, *args):
        pass


def certificate(folder):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=30)).add_extension(x509.SubjectAlternativeName([
                x509.DNSName(HOST), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    (folder / 'fullchain.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / 'privkey.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (folder / 'privkey.pem').chmod(0o600)


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def verify(root: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location('tls_profile_generator', root / 'scripts/deploy/prepare-security-config.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    checks = []
    with tempfile.TemporaryDirectory(prefix='pr265-tls-') as directory:
        folder = Path(directory)
        folder.chmod(0o755)
        for name in ('pc', 'portal', 'enterprise', 'miniapp'):
            static = folder / 'html' / name
            static.mkdir(parents=True)
            (static / 'index.html').write_text('PORTAL:' + name, encoding='utf-8')
            (static / '.env').write_text('must-not-serve', encoding='utf-8')
            (static / 'backup.sql').write_text('must-not-serve', encoding='utf-8')
        certificate(folder)
        conf_dir = folder / 'conf'
        conf_dir.mkdir()
        for name in ('security-http.conf', 'security-server.conf', 'security-headers.conf'):
            source = (root / 'deploy/nginx' / name).read_text(encoding='utf-8')
            (conf_dir / name).write_text(source.replace('/etc/nginx/conf.d', str(conf_dir)), encoding='utf-8')
        echo = ThreadingHTTPServer(('127.0.0.1', 0), Echo)
        thread = Thread(target=echo.serve_forever, daemon=True)
        thread.start()
        http_port, https_port = port(), port()
        config = generator.nginx_config(HOST)
        is_root = getattr(os, 'geteuid', lambda: -1)() == 0
        user_line = 'user root;' if is_root else ''
        config = (config.replace('user nginx;', user_line).replace('worker_processes auto;', 'worker_processes 1;')
                  .replace('/etc/nginx/conf.d', str(conf_dir)).replace('/etc/nginx/tls', str(folder))
                  .replace('/usr/share/nginx/html', str(folder / 'html'))
                  .replace('/var/log/nginx/error.log', str(folder / 'error.log'))
                  .replace('/var/log/nginx/access.log', str(folder / 'access.log'))
                  .replace('/var/run/nginx.pid', str(folder / 'nginx.pid'))
                  .replace('backend:8000', f'127.0.0.1:{echo.server_port}')
                  .replace('listen 80', f'listen 127.0.0.1:{http_port}')
                  .replace('listen 443', f'listen 127.0.0.1:{https_port}'))
        path = folder / 'nginx.conf'
        path.write_text(config, encoding='utf-8')
        process = None
        try:
            syntax = subprocess.run(['nginx', '-t', '-p', str(folder), '-c', str(path)], capture_output=True, timeout=10)
            if syntax.returncode:
                raise RuntimeError('NGINX_CONFIG_INVALID')
            checks.append('nginx-syntax')
            process = subprocess.Popen(['nginx', '-p', str(folder), '-c', str(path), '-g', 'daemon off;'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for attempt in range(100):
                try:
                    with socket.create_connection(('127.0.0.1', https_port), timeout=0.1):
                        break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError('NGINX_START_FAILED')
                    time.sleep(0.05)
            context = ssl.create_default_context(cafile=str(folder / 'fullchain.pem'))
            def request(uri, *, tls=True, headers=None):
                conn = (http.client.HTTPSConnection('127.0.0.1', https_port, context=context, timeout=3)
                        if tls else http.client.HTTPConnection('127.0.0.1', http_port, timeout=3))
                try:
                    conn.request('GET', uri, headers={'Host': HOST, **(headers or {})})
                    response = conn.getresponse()
                    return response.status, dict(response.getheaders()), response.read().decode()
                finally:
                    conn.close()
            for uri, portal in (('/login', 'pc'), ('/portal/grades', 'portal'),
                                ('/enterprise/tasks', 'enterprise'), ('/miniapp/pages/login', 'miniapp')):
                status, headers, body = request(uri)
                assert status == 200 and body == 'PORTAL:' + portal, (uri, status)
                for key in ('Content-Security-Policy', 'X-Content-Type-Options', 'X-Frame-Options', 'Strict-Transport-Security'):
                    assert key in headers, (uri, key)
                assert headers.get('Cache-Control') == 'no-store', uri
                checks.append(portal + '-history-security-headers')
            status, headers, _ = request('/portal/login?x=1', tls=False)
            assert status == 308 and headers['Location'] == f'https://{HOST}/portal/login?x=1'
            checks.append('http-fixed-host-redirect')
            assert request('/api/v1/auth/login', tls=False)[0] == 426
            checks.append('plaintext-api-refused')
            for uri in ('/uploads/id.pdf', '/exports/grades.xlsx', '/.env', '/portal/.env', '/enterprise/backup.sql',
                        '/miniapp/.env', '/internal/metrics', '/health/ready', '/portal/assets/missing.js'):
                status, _, body = request(uri)
                assert status in (403, 404) and 'must-not-serve' not in body, (uri, status)
                checks.append('denied:' + uri)
            status, headers, body = request('/api/v1/proxy-check', headers={
                'X-Forwarded-For': '1.1.1.1, 192.168.1.1', 'X-Real-IP': '1.1.1.1',
                'X-Forwarded-Proto': 'http', 'Forwarded': 'for=1.1.1.1'})
            value = json.loads(body)
            assert status == 200 and value == {'xff': '127.0.0.1', 'real': '127.0.0.1', 'proto': 'https', 'forwarded': None}
            checks.append('edge-replaces-forged-proxy-headers')
            try:
                request('/', headers={'Host': 'attacker.example.test'})
            except http.client.RemoteDisconnected:
                checks.append('unknown-host-refused')
            else:
                raise AssertionError('UNKNOWN_HOST_NOT_REFUSED')
            for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
                context.minimum_version = context.maximum_version = version
                assert request('/login')[0] == 200
                checks.append(version.name)
            broken = folder / 'missing-cert.conf'
            broken.write_text(config.replace('fullchain.pem', 'absent-certificate.pem'), encoding='utf-8')
            result = subprocess.run(['nginx', '-t', '-p', str(folder), '-c', str(broken)], capture_output=True, timeout=10)
            assert result.returncode != 0
            checks.append('missing-certificate-refuses-start')
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            echo.shutdown()
            echo.server_close()
            thread.join(timeout=3)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        checks = verify(args.repo.resolve())
    except Exception as exc:
        print(json.dumps({'passed': False, 'errorType': type(exc).__name__, 'liveSaaS': False}))
        return 1
    print(json.dumps({'passed': True, 'checks': checks, 'count': len(checks),
                      'liveSaaS': False, 'productionCertificate': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
