"""Offline deployment-policy tests. No app import, network or database access.

Run with --noconftest for isolated policy tests; normal repository pytest also
collects this module. Docker's real rendering/build and local TLS are separate gates.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load('security_generator_tests', 'scripts/deploy/prepare-security-config.py')
check = load('security_check_tests', 'scripts/deploy/check-security-profile.py')
probe = load('security_probe_tests', 'backend/scripts/security_profile_probe.py')


def create_cert(folder, host='school.example.test', days=30):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
            .sign(key, hashes.SHA256()))
    (folder / 'fullchain.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / 'privkey.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for file in folder.iterdir():
        file.chmod(0o600)


def ready_files(root):
    folder = root / 'deploy/env/security'
    generator.prepare(folder, 'school.example.test', new_empty_install=True)
    text = (folder / 'compose.env').read_text()
    for index, key in enumerate(generator.IMAGE_KEYS):
        text = text.replace(f'{key}=REQUIRED_REVIEWED_DIGEST', f'{key}=fixture/{key.lower()}@sha256:{index + 1:064x}')
    (folder / 'compose.env').write_text(text)
    for relative in check.ARTIFACTS.values():
        path = root / relative / 'index.html'
        path.parent.mkdir(parents=True)
        path.write_text('test-only static entry')
    create_cert(folder / 'tls')
    return folder


def rendered(root):
    """Explicit approximation fixture only, NOT evidence of Docker rendering."""
    folder = ready_files(root)
    env = check.read_env(folder / 'compose.env')
    runtime = check.read_env(folder / 'runtime.env')
    source = (ROOT / 'deploy/docker/docker-compose.security.yml').read_text()
    def substitute(match):
        value = match.group(1)
        key = re.split(r':[-?]', value, maxsplit=1)[0]
        return env.get(key, value.partition(':-')[2])
    source = re.sub(r'(?<!\$)\$\{([^}]+)\}', substitute, source).replace('$$', '$')
    config = copy.deepcopy(yaml.safe_load(source))
    for service in config['services'].values():
        service['environment'] = dict(service.get('environment', {}))
        if service.pop('env_file', None):
            service['environment'] = {**runtime, **service['environment']}
        normalized = []
        for mount in service.get('volumes', []):
            if isinstance(mount, str):
                a, b = mount.split(':', 1)
                normalized.append({'type': 'volume', 'source': a, 'target': b})
            else:
                normalized.append(copy.deepcopy(mount))
        service['volumes'] = normalized
        if isinstance(service.get('networks'), list):
            service['networks'] = {name: {} for name in service['networks']}
    config['services']['nginx']['ports'] = [{'target': 80, 'published': '80'}, {'target': 443, 'published': '443'}]
    return config


def test_generator_separates_all_secrets_and_refuses_rotation(tmp_path):
    folder = tmp_path / 'new'
    generator.prepare(folder, 'School.example.test', new_empty_install=True)
    compose = check.read_env(folder / 'compose.env')
    runtime = check.read_env(folder / 'runtime.env')
    assert len({compose[key] for key in generator.PASSWORD_KEYS}) == 4
    assert not set(generator.PASSWORD_KEYS).intersection(runtime)
    assert runtime['CORS_ORIGINS'] == 'https://school.example.test'
    before = (folder / 'runtime.env').read_bytes()
    with pytest.raises(FileExistsError):
        generator.prepare(folder, 'school.example.test', new_empty_install=True)
    assert (folder / 'runtime.env').read_bytes() == before
    assert folder.stat().st_mode & 0o777 == 0o700
    assert all((folder / name).stat().st_mode & 0o777 == 0o600 for name in ('compose.env', 'runtime.env', 'nginx.conf'))


def test_new_install_must_be_explicit(tmp_path):
    with pytest.raises(ValueError):
        generator.prepare(tmp_path / 'new', 'school.example.test', new_empty_install=False)
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('host', ['localhost', '*.school.test', 'https://school.test', 'school.test/path',
                                  'school.test:443', 'a;return 200;', 'school.test\n', '-school.test'])
def test_untrusted_hostname_cannot_inject_nginx(host):
    with pytest.raises(ValueError):
        generator.nginx_config(host)


@pytest.mark.parametrize('value', ['A=one\nA=two', 'INVALID', 'A=${OTHER}', "A='quoted'", 'A="quoted"'])
def test_environment_parser_refuses_ambiguity(tmp_path, value):
    path = tmp_path / 'sample.env'
    path.write_text(value)
    with pytest.raises(ValueError):
        check.read_env(path)


def test_effective_candidate_has_required_boundaries(tmp_path):
    assert check.validate_rendered(rendered(tmp_path)) == []


@pytest.mark.parametrize('mutation,expected', [
    ('root', 'backend:PROCESS_PRIVILEGE_BOUNDARY'),
    ('writable-code', 'backend:PROCESS_PRIVILEGE_BOUNDARY'),
    ('cap', 'backend:PROCESS_PRIVILEGE_BOUNDARY'),
    ('privileged', 'backend:UNSAFE_HOST_ACCESS'),
    ('root-leak', 'backend:ROOT_CREDENTIAL_LEAK'),
    ('migrator-leak', 'scheduler:MIGRATOR_CREDENTIAL_LEAK'),
    ('public-db', 'mysql:PORT_MUST_NOT_BE_PUBLISHED'),
    ('public-redis', 'redis:PORT_MUST_NOT_BE_PUBLISHED'),
    ('public-scanner', 'clamav:PORT_MUST_NOT_BE_PUBLISHED'),
    ('proxy', 'SINGLE_PROXY_AUTHORITY_COMMAND_REQUIRED'),
    ('trust', 'backend:ENV_DRIFT:TRUSTED_PROXY_IPS'),
    ('mock', 'backend:ENV_DRIFT:MOCK_LOGIN_ENABLED'),
    ('scan-off', 'backend:ENV_DRIFT:FILE_SCAN_REQUIRED'),
    ('eviction', 'REDIS_NOEVICTION_REQUIRED'),
    ('tag', 'mysql:IMMUTABLE_IMAGE_REQUIRED'),
    ('missing-portal', 'ALL_FOUR_STATIC_PORTALS_REQUIRED'),
    ('network', 'data:INTERNAL_NETWORK_REQUIRED'),
    ('scanner-data', 'SCANNER_MUST_NOT_JOIN_DATABASE_NETWORK'),
    ('worker-cycle', 'scheduler:WORKER_WEB_READINESS_CYCLE'),
    ('scan-ready', 'file-scan:SCANNER_READINESS_REQUIRED'),
    ('shared-data', 'scheduler:EXACT_SHARED_STORAGE_REQUIRED'),
    ('host-socket', 'backend:UNSAFE_BIND_MOUNT'),
])
def test_weakened_candidate_is_rejected(tmp_path, mutation, expected):
    config = rendered(tmp_path)
    services = config['services']
    backend = services['backend']
    if mutation == 'root': backend['user'] = '0:0'
    if mutation == 'writable-code': backend['read_only'] = False
    if mutation == 'cap': backend['cap_add'] = ['SYS_ADMIN']
    if mutation == 'privileged': backend['privileged'] = True
    if mutation == 'root-leak': backend['environment']['DISGUISED'] = services['mysql']['environment']['MYSQL_ROOT_PASSWORD']
    if mutation == 'migrator-leak': services['scheduler']['environment']['DISGUISED'] = services['mysql']['environment']['MIGRATOR_PASSWORD']
    if mutation.startswith('public-'):
        key = {'public-db': 'mysql', 'public-redis': 'redis', 'public-scanner': 'clamav'}[mutation]
        services[key]['ports'] = [{'target': 1234, 'published': '1234'}]
    if mutation == 'proxy': backend['command'] = ['sh', '-c', 'echo --no-proxy-headers; uvicorn app.main:app']
    if mutation == 'trust': backend['environment']['TRUSTED_PROXY_IPS'] = '0.0.0.0/0'
    if mutation == 'mock': backend['environment']['MOCK_LOGIN_ENABLED'] = 'true'
    if mutation == 'scan-off': backend['environment']['FILE_SCAN_REQUIRED'] = 'false'
    if mutation == 'eviction': services['redis']['command'] = ['redis-server', '--maxmemory-policy', 'allkeys-lru']
    if mutation == 'tag': services['mysql']['image'] = 'mysql:latest'
    if mutation == 'missing-portal': services['nginx']['volumes'] = [m for m in services['nginx']['volumes'] if m['target'] != '/usr/share/nginx/html/portal']
    if mutation == 'network': config['networks']['data']['internal'] = False
    if mutation == 'scanner-data': services['clamav']['networks']['data'] = {}
    if mutation == 'worker-cycle': services['scheduler']['depends_on']['backend'] = {'condition': 'service_healthy'}
    if mutation == 'scan-ready': services['file-scan']['depends_on']['clamav'] = {'condition': 'service_started'}
    if mutation == 'shared-data': services['scheduler']['volumes'] = []
    if mutation == 'host-socket': backend['volumes'].append({'type': 'bind', 'source': '/var/run/docker.sock', 'target': '/docker.sock'})
    assert expected in check.validate_rendered(config)


def test_local_preflight_missing_files_never_runs_docker(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check.subprocess, 'run', lambda *a, **k: pytest.fail('missing config must stop before render'))
    assert check.main(['--repo', str(tmp_path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result['preflightPassed'] and not result['releaseApproved']


def test_local_certificate_pair_and_host_are_checked(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith('COMPOSE_'):
            monkeypatch.delenv(key)
    folder = ready_files(tmp_path)
    assert check.local_errors(tmp_path) == []
    assert check.certificate_errors(folder / 'tls', 'wrong.example.test') == ['TLS_EXACT_HOST_SAN_REQUIRED']
    create_cert(folder / 'tls', days=1)
    assert 'TLS_VALIDITY_WINDOW_REQUIRED' in check.local_errors(tmp_path)


def test_bad_certificate_pair_is_not_treated_as_ready(tmp_path):
    folder = ready_files(tmp_path)
    (folder / 'tls/privkey.pem').write_text('not a private key')
    assert 'TLS_PEM_OR_KEY_PAIR_INVALID' in check.local_errors(tmp_path)


def test_preflight_suppresses_compose_rendered_secrets(tmp_path, monkeypatch, capsys):
    ready_files(tmp_path)
    def render(*a, **kw):
        return SimpleNamespace(returncode=1, stdout='SECRET-DO-NOT-PRINT', stderr='SECRET-DO-NOT-PRINT')
    monkeypatch.setattr(check.subprocess, 'run', render)
    assert check.main(['--repo', str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert 'SECRET-DO-NOT-PRINT' not in output.out + output.err
    assert 'COMPOSE_RENDER_FAILED_OUTPUT_SUPPRESSED' in output.out


def test_shadowing_environment_refuses_approval(tmp_path, monkeypatch):
    ready_files(tmp_path)
    monkeypatch.setenv('MYSQL_ROOT_PASSWORD', 'wrong-local-secret')
    assert 'AMBIENT_COMPOSE_VALUE_SHADOWING' in check.local_errors(tmp_path)


def test_static_artifacts_and_permissions_are_not_optional(tmp_path):
    folder = ready_files(tmp_path)
    (tmp_path / 'student-portal/dist/index.html').unlink()
    (folder / 'runtime.env').chmod(0o644)
    errors = check.local_errors(tmp_path)
    assert 'STATIC_ARTIFACT_MISSING:portal' in errors
    assert 'PRIVATE_FILE_MODE_REQUIRED:runtime.env' in errors


def test_symlink_config_is_not_followed(tmp_path):
    folder = ready_files(tmp_path)
    (folder / 'runtime.env').rename(folder / 'old.env')
    (folder / 'runtime.env').symlink_to(folder / 'old.env')
    assert 'MISSING_OR_UNSAFE:runtime.env' in check.local_errors(tmp_path)


def test_sql_init_is_syntax_valid_and_schema_scoped():
    path = ROOT / 'deploy/docker/mysql-security-init/01-accounts.sh'
    subprocess.run(['bash', '-n', str(path)], check=True, capture_output=True)
    source = path.read_text()
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE' in source
    assert 'GRANT ALL PRIVILEGES ON *.*' not in source
    assert 'set -x' not in source
    assert "CREATE USER 'saas_migrator'" in source


def test_security_image_preserves_repository_paths_and_excludes_secrets():
    image = (ROOT / 'backend/Dockerfile.security').read_text()
    ignore = (ROOT / 'backend/Dockerfile.security.dockerignore').read_text()
    assert 'WORKDIR /app/backend' in image and 'COPY shared /app/shared' in image
    assert 'USER 10001:10001' in image and 'security_profile_probe.py' in image
    assert 'COPY . ' not in image and '**/.env' in ignore
    assert '!backend/tests' not in ignore and 'MYSQL_ROOT_PASSWORD' not in image


def test_image_probe_refuses_root(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.os, 'geteuid', lambda: 0)
    with pytest.raises(RuntimeError, match='NONROOT_UID_REQUIRED'):
        probe.image_contract(tmp_path)


def test_storage_preparation_never_recursively_changes_existing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.os, 'geteuid', lambda: 0)
    for relative in probe.WRITABLE:
        (tmp_path / relative).mkdir(parents=True)
    data = tmp_path / probe.WRITABLE[0] / 'existing.txt'
    data.write_text('business-data')
    monkeypatch.setattr(probe.os, 'chown', lambda *a, **k: pytest.fail('must not alter existing data'))
    with pytest.raises(RuntimeError, match='NONEMPTY_VOLUME'):
        probe.prepare_storage(tmp_path)
    assert data.read_text() == 'business-data'


@pytest.mark.parametrize('change,error', [
    ('mixed-release', 'SINGLE_APP_RELEASE_REQUIRED'),
    ('root-migration', 'MIGRATOR_PROCESS_BOUNDARY_REQUIRED'),
    ('networked-prepare', 'STORAGE_PREPARATION_BOUNDARY_REQUIRED'),
    ('prepare-extra-volume', 'STORAGE_PREPARATION_MOUNTS_REQUIRED'),
    ('edge-app-env', 'EDGE_CONFIG_MOUNT_BOUNDARY_REQUIRED'),
])
def test_additional_operator_boundaries_are_not_silent(tmp_path, change, error):
    config = rendered(tmp_path)
    services = config['services']
    if change == 'mixed-release': services['scheduler']['image'] = 'other/release@sha256:' + 'a' * 64
    if change == 'root-migration': services['migrate']['user'] = '0:0'
    if change == 'networked-prepare': services['prepare-storage']['network_mode'] = 'host'
    if change == 'prepare-extra-volume': services['prepare-storage']['volumes'].append({'type': 'volume', 'source': 'mysql_data', 'target': '/database'})
    if change == 'edge-app-env': services['nginx']['environment']['JWT_SECRET'] = 'unexpected-app-secret'
    assert error in check.validate_rendered(config)


@pytest.mark.parametrize('bad', [None, [], {'services': []}, {'services': {'backend': None}}])
def test_malformed_render_is_rejected(bad):
    assert check.validate_rendered(bad) == ['COMPOSE_SERVICE_STRUCTURE_INVALID']


def test_ops_probe_refuses_redirect_and_disables_environment_proxy(monkeypatch):
    monkeypatch.setenv('INTERNAL_OPS_TOKEN', 'ephemeral-test-ops-token')
    seen = []
    def build(*handlers):
        seen.extend(handlers)
        return SimpleNamespace(open=lambda *a, **k: (_ for _ in ()).throw(OSError('not-a-live-backend')))
    monkeypatch.setattr(probe, 'build_opener', build)
    assert probe.main(['ready']) == 1
    assert seen[0].proxies == {}
    assert seen[1].redirect_request(None, None, 302, '', {}, 'https://other.example') is None


def test_container_acceptance_requires_disposable_ci_acknowledgement(monkeypatch):
    module = load('security_container_test', 'scripts/check/check-security-profile-containers.py')
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(SystemExit) as exc:
        module.main(['--disposable-ci-only'])
    assert exc.value.code == 2
