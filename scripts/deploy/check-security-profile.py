#!/usr/bin/env python3
"""Read-only preflight of effective Compose config. Never start services or print secrets.

Passing these checks is NOT release approval, certificate-chain trust, vulnerability
scanning, live scanner/worker acceptance, or a backup restore rehearsal.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import subprocess

DIGEST = re.compile(r'^[^\s]+@sha256:[a-f0-9]{64}$')
BANNED = {'MYSQL_ROOT_PASSWORD', 'MIGRATOR_PASSWORD', 'MIGRATION_PASSWORD', 'ROOT_PASSWORD',
          'DOCKER_HOST', 'DOCKER_API_VERSION', 'LD_PRELOAD', 'PYTHONPATH'}
APPS = ('backend', 'scheduler', 'file-scan')
IMAGE_KEYS = {'mysql': 'MYSQL_IMAGE', 'redis': 'REDIS_IMAGE', 'nginx': 'NGINX_IMAGE', 'clamav': 'CLAMAV_IMAGE'}
ARTIFACTS = {'pc': 'frontend/dist', 'portal': 'student-portal/dist',
             'enterprise': 'enterprise-portal/dist', 'miniapp': 'miniapp/dist/build/h5'}
EXPECTED_ENV = {'APP_ENV': 'production', 'DEPLOYMENT_MODE': 'production', 'DEBUG': 'false',
                'MOCK_LOGIN_ENABLED': 'false', 'DB_ENABLED': 'true', 'DB_DRIVER': 'mysql',
                'DB_USER': 'saas_runtime', 'DB_HOST': 'mysql', 'DATABASE_URL': '',
                'MULTI_INSTANCE': 'true', 'WEB_CONCURRENCY': '2', 'SCHEDULER_MODE': 'external',
                'TRUSTED_PROXY_IPS': '172.30.40.10/32', 'CLAMAV_ENABLED': 'true',
                'FILE_SCAN_REQUIRED': 'true', 'CLAMAV_HOST': 'clamav'}
WRITABLE = {'uploads': '/app/backend/uploads', 'exports': '/app/backend/exports', 'app_data': '/app/backend/data'}


def read_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in result or '\x00' in value:
            raise ValueError('INVALID_ENV_FORMAT')
        # This generator emits literal unquoted values only. Do not ambiguously
        # interpret dotenv interpolation, quotes, comments or backslash escapes.
        if any(char in value for char in '$\r\n\'"`\\'):
            raise ValueError('NON_LITERAL_ENV_VALUE')
        result[key] = value
    return result


def _no_new_privileges(service: dict) -> bool:
    return any(str(item).replace('=', ':') in {'no-new-privileges', 'no-new-privileges:true'}
               for item in service.get('security_opt', []))


def validate_rendered(config: dict, *, root: Path | None = None) -> list[str]:
    """Validate Docker's normalized JSON, not the unexpanded YAML anchors."""
    errors = []
    if not isinstance(config, dict) or not isinstance(config.get('services'), dict):
        return ['COMPOSE_SERVICE_STRUCTURE_INVALID']
    services = config['services']
    if any(not isinstance(service, dict) for service in services.values()):
        return ['COMPOSE_SERVICE_STRUCTURE_INVALID']
    required = set(APPS) | {'nginx', 'mysql', 'redis', 'migrate', 'prepare-storage', 'clamav'}
    if set(services) != required:
        errors.append('EXACT_SERVICE_SET_REQUIRED')
    mysql = services.get('mysql', {}).get('environment', {})
    root_secret, migrator_secret, runtime_secret = (mysql.get(key, '') for key in
                                                   ('MYSQL_ROOT_PASSWORD', 'MIGRATOR_PASSWORD', 'MYSQL_PASSWORD'))
    if (any(not re.fullmatch('[a-f0-9]{64}', str(value)) for value in (root_secret, migrator_secret, runtime_secret))
            or len({root_secret, migrator_secret, runtime_secret}) != 3):
        errors.append('DATABASE_CREDENTIAL_SEPARATION_REQUIRED')
    for name, service in services.items():
        if service.get('build') or not DIGEST.fullmatch(service.get('image', '')):
            errors.append(name + ':IMMUTABLE_IMAGE_REQUIRED')
        if (service.get('privileged') or service.get('pid') == 'host' or service.get('ipc') == 'host'
                or service.get('network_mode') == 'host' or service.get('devices') or service.get('use_api_socket')):
            errors.append(name + ':UNSAFE_HOST_ACCESS')
        if name != 'nginx' and service.get('ports'):
            errors.append(name + ':PORT_MUST_NOT_BE_PUBLISHED')
        for key, value in service.get('environment', {}).items():
            if name != 'mysql' and root_secret and root_secret in str(value):
                errors.append(name + ':ROOT_CREDENTIAL_LEAK')
            if name not in {'mysql', 'migrate'} and migrator_secret and migrator_secret in str(value):
                errors.append(name + ':MIGRATOR_CREDENTIAL_LEAK')
        for mount in service.get('volumes', []):
            if not isinstance(mount, dict):
                errors.append(name + ':NORMALIZED_MOUNT_REQUIRED')
                continue
            if mount.get('type') == 'bind':
                if (not mount.get('read_only') or mount.get('bind', {}).get('create_host_path') is not False
                        or mount.get('source') == '/' or 'docker.sock' in mount.get('source', '')):
                    errors.append(name + ':UNSAFE_BIND_MOUNT')
    for name in APPS:
        service = services.get(name, {})
        env = service.get('environment', {})
        if BANNED.intersection(env):
            errors.append(name + ':FORBIDDEN_ENV_KEY')
        for key, value in EXPECTED_ENV.items():
            if str(env.get(key)) != value:
                errors.append(name + ':ENV_DRIFT:' + key)
        if env.get('DB_PASSWORD') != runtime_secret:
            errors.append(name + ':WRONG_RUNTIME_CREDENTIAL')
        if (str(service.get('user')) != '10001:10001' or not service.get('read_only')
                or 'ALL' not in service.get('cap_drop', []) or service.get('cap_add')
                or not _no_new_privileges(service)):
            errors.append(name + ':PROCESS_PRIVILEGE_BOUNDARY')
        mounts = {(m.get('source'), m.get('target')) for m in service.get('volumes', []) if isinstance(m, dict)}
        if mounts != set(WRITABLE.items()):
            errors.append(name + ':EXACT_SHARED_STORAGE_REQUIRED')
        if (not service.get('pids_limit') or not service.get('mem_limit') or not service.get('cpus')
                or not any('noexec' in str(t) for t in service.get('tmpfs', []))):
            errors.append(name + ':RESOURCE_BOUNDARY_REQUIRED')
        if service.get('depends_on', {}).get('migrate', {}).get('condition') != 'service_completed_successfully':
            errors.append(name + ':MIGRATION_DEPENDENCY_REQUIRED')
        if name != 'backend' and 'backend' in service.get('depends_on', {}):
            errors.append(name + ':WORKER_WEB_READINESS_CYCLE')
    for name in ('backend', 'file-scan'):
        service = services.get(name, {})
        if service.get('depends_on', {}).get('clamav', {}).get('condition') != 'service_healthy':
            errors.append(name + ':SCANNER_READINESS_REQUIRED')
        if 'scripts/check_production_file_scan.py' not in str(service.get('command', [])):
            errors.append(name + ':SCAN_PREFLIGHT_REQUIRED')
    cmd = services.get('backend', {}).get('command', [])
    expected = ['sh', '-c', 'python scripts/security_profile_probe.py filesystem && python scripts/check_production_redis.py && python scripts/check_production_file_scan.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --no-proxy-headers']
    if cmd != expected:
        errors.append('SINGLE_PROXY_AUTHORITY_COMMAND_REQUIRED')
    app_image = services.get('backend', {}).get('image')
    if any(services.get(name, {}).get('image') != app_image for name in (*APPS, 'migrate', 'prepare-storage')):
        errors.append('SINGLE_APP_RELEASE_REQUIRED')
    migration = services.get('migrate', {})
    menv = migration.get('environment', {})
    if (menv.get('DB_USER') != 'saas_migrator' or menv.get('DB_PASSWORD') != migrator_secret
            or migration.get('command') != ['alembic', 'upgrade', 'head'] or BANNED.intersection(menv)
            or migration.get('volumes') or migration.get('secrets') or migration.get('env_file')):
        errors.append('MIGRATOR_BOUNDARY_REQUIRED')
    if (str(migration.get('user')) != '10001:10001' or not migration.get('read_only')
            or migration.get('cap_drop') != ['ALL'] or migration.get('cap_add')
            or not _no_new_privileges(migration) or set(migration.get('networks', {})) != {'data'}):
        errors.append('MIGRATOR_PROCESS_BOUNDARY_REQUIRED')
    prepare = services.get('prepare-storage', {})
    if (str(prepare.get('user')) != '0:0' or not prepare.get('read_only')
            or prepare.get('cap_drop') != ['ALL'] or not _no_new_privileges(prepare)
            or prepare.get('network_mode') != 'none' or prepare.get('environment') or prepare.get('secrets')
            or prepare.get('cap_add') != ['CHOWN']
            or prepare.get('command') != ['python', 'scripts/security_profile_probe.py', 'prepare-storage']):
        errors.append('STORAGE_PREPARATION_BOUNDARY_REQUIRED')
    if {(m.get('source'), m.get('target')) for m in prepare.get('volumes', []) if isinstance(m, dict)} != set(WRITABLE.items()):
        errors.append('STORAGE_PREPARATION_MOUNTS_REQUIRED')
    rediscmd = services.get('redis', {}).get('command', [])
    try:
        if rediscmd[rediscmd.index('--maxmemory-policy') + 1] != 'noeviction':
            raise ValueError()
    except (ValueError, IndexError):
        errors.append('REDIS_NOEVICTION_REQUIRED')
    for name in ('data', 'scan'):
        if config.get('networks', {}).get(name, {}).get('internal') is not True:
            errors.append(name + ':INTERNAL_NETWORK_REQUIRED')
    if set(services.get('mysql', {}).get('networks', {})) != {'data'}:
        errors.append('MYSQL_NETWORK_BOUNDARY_REQUIRED')
    if 'data' in services.get('clamav', {}).get('networks', {}):
        errors.append('SCANNER_MUST_NOT_JOIN_DATABASE_NETWORK')
    nginx = services.get('nginx', {})
    ports = nginx.get('ports', [])
    if (len(ports) != 2 or {(str(p.get('target')), str(p.get('published'))) for p in ports} != {('80', '80'), ('443', '443')}):
        errors.append('EDGE_PORTS_MUST_BE_80_443')
    mounts = {m.get('target') for m in nginx.get('volumes', []) if isinstance(m, dict)}
    if not {f'/usr/share/nginx/html/{name}' for name in ARTIFACTS}.issubset(mounts):
        errors.append('ALL_FOUR_STATIC_PORTALS_REQUIRED')
    allowed_mounts = {f'/usr/share/nginx/html/{name}' for name in ARTIFACTS} | {
        '/etc/nginx/nginx.conf', '/etc/nginx/tls', '/etc/nginx/conf.d/security-http.conf',
        '/etc/nginx/conf.d/security-server.conf', '/etc/nginx/conf.d/security-headers.conf'}
    if mounts != allowed_mounts or nginx.get('env_file') or nginx.get('environment') or nginx.get('secrets'):
        errors.append('EDGE_CONFIG_MOUNT_BOUNDARY_REQUIRED')
    if nginx.get('networks', {}).get('edge', {}).get('ipv4_address') != '172.30.40.10':
        errors.append('EDGE_PROXY_ADDRESS_DRIFT')
    spec = importlib.util.spec_from_file_location(
        'security_profile_boundary', Path(__file__).with_name('security_profile_boundary.py'))
    boundary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boundary)
    try:
        errors.extend(boundary.execution_errors(config))
        if root is not None:
            folder = root / 'deploy/env/security'
            errors.extend(boundary.release_input_errors(
                config, root, read_env(folder / 'compose.env'), read_env(folder / 'runtime.env')))
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        errors.append('EXECUTION_BOUNDARY_NOT_VALIDATED')
    return sorted(set(errors))


def certificate_errors(folder: Path, host: str) -> list[str]:
    try:
        from cryptography import x509
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(folder / 'fullchain.pem', folder / 'privkey.pem')
        cert = x509.load_pem_x509_certificate((folder / 'fullchain.pem').read_bytes())
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
        # Explicit DNS SAN avoids wildcard / CN-only ambiguity in this profile.
        if host not in {name.lower() for name in names}:
            return ['TLS_EXACT_HOST_SAN_REQUIRED']
        now = datetime.now(timezone.utc)
        if cert.not_valid_before_utc > now or cert.not_valid_after_utc < now + timedelta(days=14):
            return ['TLS_VALIDITY_WINDOW_REQUIRED']
    except Exception:
        return ['TLS_PEM_OR_KEY_PAIR_INVALID']
    return []


def local_errors(root: Path) -> list[str]:
    folder = root / 'deploy/env/security'
    errors = []
    for relative in ('compose.env', 'runtime.env', 'nginx.conf', 'tls/fullchain.pem', 'tls/privkey.pem'):
        path = folder / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            errors.append('MISSING_OR_UNSAFE:' + relative)
        elif os.name == 'posix' and path.stat().st_mode & 0o077:
            errors.append('PRIVATE_FILE_MODE_REQUIRED:' + relative)
    if os.name == 'posix':
        for path in (folder, folder / 'tls'):
            if path.is_symlink() or (path.is_dir() and path.stat().st_mode & 0o077):
                errors.append('PRIVATE_DIRECTORY_REQUIRED')
    for name, relative in ARTIFACTS.items():
        if not (root / relative / 'index.html').is_file():
            errors.append('STATIC_ARTIFACT_MISSING:' + name)
    if errors:
        return sorted(set(errors))
    try:
        runtime = read_env(folder / 'runtime.env')
        compose = read_env(folder / 'compose.env')
        if BANNED.intersection(runtime):
            errors.append('RUNTIME_ENV_CONTAINS_FORBIDDEN_KEYS')
        for key in (*IMAGE_KEYS.values(), 'APP_IMAGE', 'PYTHON_BASE_IMAGE'):
            if not DIGEST.fullmatch(compose.get(key, '')):
                errors.append('DIGEST_REQUIRED:' + key)
        credentials = [compose.get(key, '') for key in ('DB_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'MIGRATOR_PASSWORD', 'REDIS_PASSWORD')]
        credentials += [runtime.get(key, '') for key in ('JWT_SECRET', 'INTERNAL_OPS_TOKEN', 'SENSITIVE_SEARCH_HMAC_KEY')]
        if not all(re.fullmatch('[a-f0-9]{64}', value) for value in credentials) or len(set(credentials)) != 7:
            errors.append('DISTINCT_STRONG_CREDENTIALS_REQUIRED')
        if len(base64.b64decode(runtime.get('FIELD_ENCRYPTION_KEY', ''), altchars=b'-_', validate=True)) != 32:
            errors.append('FERNET_KEY_REQUIRED')
        host = compose.get('PUBLIC_HOST', '')
        if runtime.get('CORS_ORIGINS') != 'https://' + host:
            errors.append('EXACT_HTTPS_ORIGIN_REQUIRED')
        generator_path = Path(__file__).with_name('prepare-security-config.py')
        spec = importlib.util.spec_from_file_location('security_profile_generator', generator_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if (folder / 'nginx.conf').read_text(encoding='utf-8') != module.nginx_config(host):
            errors.append('NGINX_GENERATED_CONTRACT_DRIFT')
        errors.extend(certificate_errors(folder / 'tls', host))
        # Reject shell shadowing instead of checking one config and deploying another.
        if any(key in os.environ and os.environ[key] != value for key, value in compose.items()):
            errors.append('AMBIENT_COMPOSE_VALUE_SHADOWING')
        if any(key.startswith('COMPOSE_') for key in os.environ):
            errors.append('AMBIENT_COMPOSE_CONTROL_OVERRIDE')
    except (OSError, ValueError, TypeError):
        errors.append('LOCAL_CONFIG_INVALID_VALUES_SUPPRESSED')
    return sorted(set(errors))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args(argv)
    root = args.repo.resolve()
    errors = local_errors(root)
    if not errors:
        try:
            result = subprocess.run(['docker', 'compose', '--env-file', str(root / 'deploy/env/security/compose.env'),
                                     '-f', str(root / 'deploy/docker/docker-compose.security.yml'), 'config', '--format', 'json'],
                                    cwd=root, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode:
                errors.append('COMPOSE_RENDER_FAILED_OUTPUT_SUPPRESSED')
            else:
                errors.extend(validate_rendered(json.loads(result.stdout), root=root))
        except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.TimeoutExpired):
            errors.append('COMPOSE_NOT_VALIDATED')
    print(json.dumps({'preflightPassed': not errors, 'errors': sorted(set(errors)),
                      'releaseApproved': False, 'liveApplicationAcceptance': 'NOT_RUN',
                      'imageVulnerabilityScan': 'NOT_RUN', 'tlsPublicTrustAndRenewal': 'NOT_RUN',
                      'backupRestore': 'NOT_RUN'}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
