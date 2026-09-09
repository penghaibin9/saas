#!/usr/bin/env python3
"""Generate NEW EMPTY installation config. No network/DB/Docker action or key rotation."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets

_HOST = re.compile(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\Z")
PASSWORD_KEYS = ("DB_PASSWORD", "MYSQL_ROOT_PASSWORD", "MIGRATOR_PASSWORD", "REDIS_PASSWORD")
IMAGE_KEYS = ("APP_IMAGE", "PYTHON_BASE_IMAGE", "MYSQL_IMAGE", "REDIS_IMAGE", "NGINX_IMAGE", "CLAMAV_IMAGE")


def nginx_config(host: str) -> str:
    if not _HOST.fullmatch(host):
        raise ValueError("Use one DNS hostname without scheme/path/port/wildcard")
    return r'''user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;
events { worker_connections 4096; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    server_tokens off;
    log_format safe '$remote_addr [$time_local] "$request_method $uri $server_protocol" $status $body_bytes_sent';
    access_log /var/log/nginx/access.log safe;
    include /etc/nginx/conf.d/security-http.conf;
    sendfile on;
    keepalive_timeout 30;
    upstream backend_api { server backend:8000; keepalive 64; }
    server { listen 80 default_server; server_name _; return 444; }
    server {
        listen 80;
        server_name __HOST__;
        # Never encourage API clients to send credentials over plaintext HTTP.
        location /api/ { return 426; }
        location / { return 308 https://__HOST__$request_uri; }
    }
    server {
        listen 443 ssl default_server;
        server_name __HOST__;
        if ($host != "__HOST__") { return 444; }
        ssl_certificate /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_session_cache shared:TLS:10m;
        ssl_session_tickets off;
        include /etc/nginx/conf.d/security-server.conf;
        # Extend only after real certificate-renewal acceptance, not before.
        add_header Strict-Transport-Security "max-age=86400" always;
        location /api/ {
            proxy_pass http://backend_api;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host __HOST__;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-Host "";
            proxy_set_header Forwarded "";
            proxy_connect_timeout 5s;
            proxy_read_timeout 60s;
        }
        location = /health { return 404; }
        location /health/ { return 404; }
        location /internal/ { return 404; }
        location = /portal { return 308 /portal/; }
        location = /enterprise { return 308 /enterprise/; }
        location = /miniapp { return 308 /miniapp/; }
        # Security deny regexes were included first: no ^~ bypass here.
        location /portal/ { root /usr/share/nginx/html; try_files $uri $uri/ /portal/index.html; }
        location /enterprise/ { root /usr/share/nginx/html; try_files $uri $uri/ /enterprise/index.html; }
        location /miniapp/ { root /usr/share/nginx/html; try_files $uri $uri/ /miniapp/index.html; }
        location / { root /usr/share/nginx/html/pc; try_files $uri $uri/ /index.html; }
        # HTML updates must not leave a stale login bundle in a browser cache.
        location ~ ^/(portal|enterprise|miniapp)/.*\.html$ {
            root /usr/share/nginx/html;
            try_files $uri =404;
            include /etc/nginx/conf.d/security-headers.conf;
            add_header Strict-Transport-Security "max-age=86400" always;
            add_header Cache-Control "no-store" always;
        }
        location ~ \.html$ {
            root /usr/share/nginx/html/pc;
            try_files $uri =404;
            include /etc/nginx/conf.d/security-headers.conf;
            add_header Strict-Transport-Security "max-age=86400" always;
            add_header Cache-Control "no-store" always;
        }
        location ~* ^/(portal|enterprise|miniapp)/.*\.(js|mjs|css|map|png|jpg|svg|ico|woff2?)$ {
            root /usr/share/nginx/html;
            try_files $uri =404;
        }
        location ~* \.(js|mjs|css|map|png|jpg|svg|ico|woff2?)$ {
            root /usr/share/nginx/html/pc;
            try_files $uri =404;
        }
    }
}
'''.replace('__HOST__', host.lower())


def _private_write(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def prepare(directory: Path, host: str, *, new_empty_install: bool) -> list[str]:
    config = nginx_config(host)
    if not new_empty_install:
        raise ValueError("Fresh keys require a NEW EMPTY installation acknowledgement")
    # Directory and any existing file are never overwritten, even on partial failure.
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    (directory / 'tls').mkdir(mode=0o700)
    compose = {key: secrets.token_hex(32) for key in PASSWORD_KEYS}
    compose.update({key: 'REQUIRED_REVIEWED_DIGEST' for key in IMAGE_KEYS})
    compose['PUBLIC_HOST'] = host.lower()
    runtime = {
        'APP_ENV': 'production', 'DEPLOYMENT_MODE': 'production',
        'DEBUG': 'false', 'MOCK_LOGIN_ENABLED': 'false', 'DB_ENABLED': 'true',
        'JWT_SECRET': secrets.token_hex(32), 'JWT_ALG': 'HS256',
        'JWT_EXPIRES_IN': '7200', 'REFRESH_TOKEN_EXPIRE_DAYS': '7',
        'INTERNAL_OPS_TOKEN': secrets.token_hex(32),
        'FIELD_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'SENSITIVE_SEARCH_HMAC_KEY': secrets.token_hex(32),
        'CORS_ORIGINS': 'https://' + host.lower(), 'AUDIT_ENABLED': 'true',
        'GUARDIAN_PORTAL_BASE_URL': 'https://' + host.lower(),
        'CLAMAV_ENABLED': 'true', 'FILE_SCAN_REQUIRED': 'true',
        'CLAMAV_HOST': 'clamav', 'CLAMAV_PORT': '3310',
    }
    _private_write(directory / 'compose.env', '# Interpolation ONLY. NEVER use as application env_file.\n' +
                   ''.join(f'{key}={value}\n' for key, value in compose.items()))
    _private_write(directory / 'runtime.env', '# Application settings ONLY; no root or migration credential.\n' +
                   ''.join(f'{key}={value}\n' for key, value in runtime.items()))
    _private_write(directory / 'nginx.conf', config)
    _private_write(directory / '.gitignore', '*\n!.gitignore\n')
    return ['compose.env', 'runtime.env', 'nginx.conf', 'tls/', '.gitignore']


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--output-dir', type=Path, default=Path('deploy/env/security'))
    parser.add_argument('--new-empty-install', action='store_true')
    args = parser.parse_args(argv)
    try:
        names = prepare(args.output_dir, args.host, new_empty_install=args.new_empty_install)
    except (OSError, ValueError) as exc:
        print(json.dumps({'generated': False, 'errorType': type(exc).__name__, 'overwritten': False}))
        return 1
    print(json.dumps({'generated': True, 'files': names, 'deployed': False,
                      'releaseApproved': False, 'required': ['reviewed image digests', 'real TLS', 'acceptance']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
