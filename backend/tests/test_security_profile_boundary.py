"""Release boundary regressions; fixtures are not live Docker evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
# Reuse the existing, explicitly labeled approximation fixture and certificate
# builder. Do not copy production service YAML or weaken the original tests.
_spec = importlib.util.spec_from_file_location(
    'security_profile_test_helpers', Path(__file__).with_name('test_security_deployment_profile.py'))
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
rendered = _helpers.rendered
check = _helpers.check


# A normalized fixture is explicitly NOT Docker output. The container workflow
# applies these same validators to real `docker compose config --format json`.
def checked_rendered(root):
    import shutil
    config = rendered(root)
    for relative in ('deploy/docker/docker-compose.security.yml',
                     'deploy/docker/mysql-security-init/01-accounts.sh',
                     'deploy/nginx/security-http.conf', 'deploy/nginx/security-server.conf',
                     'deploy/nginx/security-headers.conf'):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    for service in config['services'].values():
        for mount in service.get('volumes', []):
            if mount['type'] == 'bind':
                mount['source'] = str((root / 'deploy/docker' / mount['source']).resolve())
    for key, value in config['volumes'].items():
        config['volumes'][key] = dict(value or {}, name='school-lifecycle-security_' + key)
    for key, value in config['networks'].items():
        value['name'] = 'school-lifecycle-security_' + key
    return config


def test_resolved_inputs_and_execution_contract_have_positive_case(tmp_path):
    config = checked_rendered(tmp_path)
    assert check.validate_rendered(config, root=tmp_path) == []


@pytest.mark.parametrize('service', ['backend', 'scheduler', 'file-scan', 'migrate', 'prepare-storage', 'clamav', 'nginx'])
@pytest.mark.parametrize('value', [['sh', '-c', 'true'], []])
def test_entrypoint_cannot_bypass_checked_command(tmp_path, service, value):
    config = rendered(tmp_path)
    config['services'][service]['entrypoint'] = value
    assert service + ':EXECUTION_OVERRIDE_FORBIDDEN' in check.validate_rendered(config)


@pytest.mark.parametrize('key,value', [
    ('volumes_from', ['container:other']), ('configs', ['other']), ('secrets', ['other']),
    ('profiles', ['optional']), ('deploy', {'replicas': 0}), ('working_dir', '/tmp'),
    ('post_start', [{'command': 'true'}]), ('extra_hosts', ['mysql:127.0.0.1']),
    ('pid', 'service:mysql'), ('userns_mode', 'host'),
])
def test_unreviewed_execution_extensions_fail_closed(tmp_path, key, value):
    config = rendered(tmp_path)
    config['services']['backend'][key] = value
    assert 'backend:EXECUTION_OVERRIDE_FORBIDDEN' in check.validate_rendered(config)


@pytest.mark.parametrize('service', ['backend', 'clamav'])
@pytest.mark.parametrize('value', [{'disable': True}, {'test': ['CMD', 'true']}, {'test': ['NONE']}])
def test_image_health_cannot_be_disabled_or_forged(tmp_path, service, value):
    config = rendered(tmp_path)
    config['services'][service]['healthcheck'] = value
    assert service + ':IMAGE_HEALTHCHECK_OVERRIDE_FORBIDDEN' in check.validate_rendered(config)


@pytest.mark.parametrize('service', ['mysql', 'redis'])
def test_infrastructure_health_still_requires_real_command(tmp_path, service):
    config = rendered(tmp_path)
    config['services'][service]['healthcheck']['test'] = ['CMD', 'true']
    assert service + ':AUTHENTICATED_HEALTHCHECK_REQUIRED' in check.validate_rendered(config)


@pytest.mark.parametrize('service', ['scheduler', 'file-scan'])
def test_worker_cannot_just_echo_a_preflight_filename(tmp_path, service):
    config = rendered(tmp_path)
    config['services'][service]['command'] = ['echo', 'scripts/check_production_file_scan.py']
    assert service + ':WORKER_COMMAND_DRIFT' in check.validate_rendered(config)


@pytest.mark.parametrize('value', [
    {'driver': 'local', 'driver_opts': {'type': 'none', 'o': 'bind', 'device': '/'}},
    {'external': True}, {'name': 'other-project_existing-data'}, {'driver': 'nfs'},
])
def test_named_volume_cannot_disguise_host_or_existing_data_mount(tmp_path, value):
    config = rendered(tmp_path)
    config['volumes']['uploads'] = value
    assert 'OWNED_LOCAL_VOLUME_REQUIRED:uploads' in check.validate_rendered(config)


@pytest.mark.parametrize('service', ['redis', 'clamav', 'nginx', 'scheduler'])
def test_extra_network_cannot_join_a_trusted_plane(tmp_path, service):
    config = rendered(tmp_path)
    extra = 'edge' if service != 'nginx' else 'data'
    config['services'][service]['networks'][extra] = {}
    assert service + ':EXACT_NETWORK_ATTACHMENTS_REQUIRED' in check.validate_rendered(config)


@pytest.mark.parametrize('value', [{'external': True}, {'driver_opts': {'type': 'other'}}, {'name': 'other-network'}])
def test_network_identity_cannot_reuse_an_external_plane(tmp_path, value):
    config = rendered(tmp_path)
    config['networks']['data'].update(value)
    assert 'OWNED_BRIDGE_NETWORK_REQUIRED:data' in check.validate_rendered(config)


@pytest.mark.parametrize('change', ['omit', 'optional', 'started'])
def test_storage_preparation_cannot_be_omitted_or_downgraded(tmp_path, change):
    config = rendered(tmp_path)
    dependencies = config['services']['backend']['depends_on']
    if change == 'omit': dependencies.pop('prepare-storage')
    if change == 'optional': dependencies['prepare-storage']['required'] = False
    if change == 'started': dependencies['prepare-storage']['condition'] = 'service_started'
    assert 'backend:STARTUP_DEPENDENCY_DRIFT' in check.validate_rendered(config)


def test_extra_tmpfs_cannot_mask_application_code(tmp_path):
    config = rendered(tmp_path)
    config['services']['backend']['tmpfs'].append('/app/backend/app:rw,mode=777')
    assert 'backend:EXACT_TEMPORARY_STORAGE_REQUIRED' in check.validate_rendered(config)


def test_named_volume_subpath_cannot_change_checked_storage(tmp_path):
    config = rendered(tmp_path)
    config['services']['backend']['volumes'][0]['volume'] = {'subpath': 'different'}
    assert 'backend:NAMED_VOLUME_BOUNDARY_DRIFT' in check.validate_rendered(config)


@pytest.mark.parametrize('service,target', [
    ('nginx', '/etc/nginx/nginx.conf'), ('nginx', '/etc/nginx/tls'),
    ('nginx', '/usr/share/nginx/html/portal'), ('mysql', '/docker-entrypoint-initdb.d/01-accounts.sh'),
])
def test_correct_mount_target_does_not_prove_correct_host_source(tmp_path, service, target):
    config = checked_rendered(tmp_path)
    mount = next(m for m in config['services'][service]['volumes'] if m['target'] == target)
    mount['source'] = '/another-private-directory/not-the-checked-input'
    assert service + ':CHECKED_BIND_SOURCE_MISMATCH' in check.validate_rendered(config, root=tmp_path)


def test_symlink_ancestor_cannot_replace_checked_nginx_fragments(tmp_path):
    config = checked_rendered(tmp_path)
    original = tmp_path / 'deploy/nginx'
    original.rename(tmp_path / 'other-nginx')
    original.symlink_to(tmp_path / 'other-nginx', target_is_directory=True)
    assert 'nginx:CHECKED_BIND_SOURCE_MISMATCH' in check.validate_rendered(config, root=tmp_path)


@pytest.mark.parametrize('field', ['JWT_SECRET', 'INTERNAL_OPS_TOKEN', 'FIELD_ENCRYPTION_KEY', 'CORS_ORIGINS'])
def test_compose_cannot_shadow_inspected_runtime_secrets_or_origin(tmp_path, field):
    config = checked_rendered(tmp_path)
    config['services']['backend']['environment'][field] = 'different-value-not-to-be-printed'
    assert 'backend:CHECKED_RUNTIME_ENV_MISMATCH' in check.validate_rendered(config, root=tmp_path)


def test_consistent_database_password_replacement_is_still_not_the_inspected_password(tmp_path):
    config = checked_rendered(tmp_path)
    config['services']['mysql']['environment']['MYSQL_PASSWORD'] = 'f' * 64
    for service in ('backend', 'scheduler', 'file-scan'):
        config['services'][service]['environment']['DB_PASSWORD'] = 'f' * 64
    errors = check.validate_rendered(config, root=tmp_path)
    assert 'mysql:CHECKED_DATABASE_CREDENTIAL_MISMATCH' in errors
    assert 'backend:CHECKED_DATABASE_CREDENTIAL_MISMATCH' in errors


def test_well_formed_different_image_digest_does_not_match_reviewed_input(tmp_path):
    config = checked_rendered(tmp_path)
    config['services']['mysql']['image'] = 'fixture/other@sha256:' + 'f' * 64
    assert 'CHECKED_IMAGE_REFERENCE_MISMATCH' in check.validate_rendered(config, root=tmp_path)


def test_redis_destination_and_server_command_are_both_bound(tmp_path):
    config = checked_rendered(tmp_path)
    config['services']['backend']['environment']['REDIS_URL'] = 'redis://other-server/0'
    config['services']['redis']['command'].extend(['--maxmemory-policy', 'allkeys-lru'])
    errors = check.validate_rendered(config, root=tmp_path)
    assert 'backend:CHECKED_REDIS_ENDPOINT_MISMATCH' in errors
    assert 'redis:CHECKED_AUTH_STORAGE_COMMAND_MISMATCH' in errors


@pytest.mark.parametrize('changed', [False, True])
def test_cli_binds_local_checks_to_actual_render_and_suppresses_values(tmp_path, monkeypatch, capsys, changed):
    config = checked_rendered(tmp_path)
    if changed:
        config['services']['nginx']['volumes'][0]['source'] = '/private-sensitive-path'
        config['services']['backend']['environment']['JWT_SECRET'] = 'private-secret-do-not-print'
    def render(command, **kwargs):
        assert str(tmp_path / 'deploy/docker/docker-compose.security.yml') in command
        assert '--format' in command and 'json' in command
        return SimpleNamespace(returncode=0, stdout=json.dumps(config), stderr='private-stderr')
    monkeypatch.setattr(check.subprocess, 'run', render)
    assert check.main(['--repo', str(tmp_path)]) == int(changed)
    output = capsys.readouterr()
    receipt = json.loads(output.out)
    assert receipt['preflightPassed'] is (not changed) and receipt['releaseApproved'] is False
    assert not any(value in output.out + output.err for value in
                   ('private-sensitive-path', 'private-secret-do-not-print', 'private-stderr'))


@pytest.mark.parametrize('suffix,denied', [('', False), ('; true', True), (' || true', True)])
def test_compose_json_dollar_escaping_is_not_an_arbitrary_shell_allowance(tmp_path, suffix, denied):
    config = rendered(tmp_path)
    health = config['services']['mysql']['healthcheck']
    health['test'][1] = health['test'][1].replace('$', '$$') + suffix
    errors = check.validate_rendered(config)
    assert ('mysql:AUTHENTICATED_HEALTHCHECK_REQUIRED' in errors) is denied


@pytest.mark.parametrize('mutation', ['missing-trust', 'disabled-binlog', 'statement-binlog', 'reduced-durability'])
def test_mysql_migration_prerequisite_never_disables_recovery_or_grants_global_access(tmp_path, mutation):
    config = rendered(tmp_path)
    command = config['services']['mysql']['command']
    before, after = {
        'missing-trust': ('--log-bin-trust-function-creators=1', '--log-bin-trust-function-creators=0'),
        'disabled-binlog': ('--log-bin=mysql-bin', '--skip-log-bin'),
        'statement-binlog': ('--binlog-format=ROW', '--binlog-format=STATEMENT'),
        'reduced-durability': ('--sync-binlog=1', '--sync-binlog=0'),
    }[mutation]
    command[command.index(before)] = after
    assert 'MYSQL_TRUSTED_MIGRATOR_BINLOG_CONTRACT_REQUIRED' in check.validate_rendered(config)


@pytest.mark.parametrize('service', ['mysql', 'nginx'])
@pytest.mark.parametrize('form', ['empty-options', 'missing-options'])
def test_missing_serialized_flag_needs_explicit_checked_source(tmp_path, service, form):
    config = checked_rendered(tmp_path)
    mount = next(m for m in config['services'][service]['volumes'] if m['type'] == 'bind')
    if form == 'empty-options':
        mount['bind'].pop('create_host_path')
    else:
        mount.pop('bind')
    assert check.validate_rendered(config, root=tmp_path) == []
    # No mutation of the observed Docker model and no rootless default-allow.
    assert 'create_host_path' not in mount.get('bind', {})
    assert service + ':UNSAFE_BIND_MOUNT' in check.validate_rendered(config)


@pytest.mark.parametrize('source_flag', [True, None, 'false', 'omitted'])
def test_missing_serialized_flag_does_not_rescue_unsafe_raw_source(tmp_path, source_flag):
    import yaml
    config = checked_rendered(tmp_path)
    mount = next(m for m in config['services']['mysql']['volumes'] if m['type'] == 'bind')
    mount['bind'].pop('create_host_path')
    path = tmp_path / 'deploy/docker/docker-compose.security.yml'
    raw = yaml.safe_load(path.read_text())
    declared = next(m for m in raw['services']['mysql']['volumes'] if isinstance(m, dict))
    if source_flag == 'omitted':
        declared['bind'].pop('create_host_path')
    else:
        declared['bind']['create_host_path'] = source_flag
    path.write_text(yaml.safe_dump(raw))
    assert 'mysql:EXPLICIT_SOURCE_BIND_SAFETY_REQUIRED' in check.validate_rendered(config, root=tmp_path)


@pytest.mark.parametrize('effective', [True, None, 'false', 1])
def test_explicit_source_cannot_override_unsafe_effective_flag(tmp_path, effective):
    config = checked_rendered(tmp_path)
    mount = next(m for m in config['services']['mysql']['volumes'] if m['type'] == 'bind')
    mount['bind']['create_host_path'] = effective
    assert 'mysql:UNSAFE_BIND_MOUNT' in check.validate_rendered(config, root=tmp_path)


def test_missing_flag_and_changed_host_source_are_not_repaired(tmp_path):
    config = checked_rendered(tmp_path)
    mount = config['services']['nginx']['volumes'][0]
    mount['bind'].pop('create_host_path')
    mount['source'] = '/different-source'
    errors = check.validate_rendered(config, root=tmp_path)
    assert 'nginx:UNSAFE_BIND_MOUNT' in errors
    assert 'nginx:CHECKED_BIND_SOURCE_MISMATCH' in errors
