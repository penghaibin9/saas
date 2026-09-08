"""Closed execution/mount boundary for the standalone fresh-install profile.

Validate Docker's normalized JSON. This is a configuration gate, not a defense
against a host administrator editing the gate, nor proof that containers ran.
All diagnostics are fixed identifiers: never echo paths, commands or secrets.
"""
from __future__ import annotations

from pathlib import Path

PROJECT = 'school-lifecycle-security'
APPS = ('backend', 'scheduler', 'file-scan')
NETWORKS = {
    'mysql': {'data'}, 'redis': {'data'}, 'migrate': {'data'},
    'backend': {'edge', 'data', 'scan', 'egress'},
    'scheduler': {'data', 'egress'}, 'file-scan': {'data', 'scan', 'egress'},
    'clamav': {'scan', 'egress'}, 'nginx': {'edge'}, 'prepare-storage': set(),
}
VOLUMES = {'mysql_data', 'redis_data', 'uploads', 'exports', 'app_data', 'clamav_db'}
NAMED_MOUNTS = {
    'mysql': {('mysql_data', '/var/lib/mysql')},
    'redis': {('redis_data', '/data')}, 'clamav': {('clamav_db', '/var/lib/clamav')},
    'migrate': set(), 'nginx': set(),
}
for _name in (*APPS, 'prepare-storage'):
    NAMED_MOUNTS[_name] = {(v, '/app/backend/' + p) for v, p in
                           [('uploads', 'uploads'), ('exports', 'exports'), ('app_data', 'data')]}
BIND_MOUNTS = {
    'mysql': {'/docker-entrypoint-initdb.d/01-accounts.sh': 'deploy/docker/mysql-security-init/01-accounts.sh'},
    'nginx': {
        '/etc/nginx/nginx.conf': 'deploy/env/security/nginx.conf',
        '/etc/nginx/tls': 'deploy/env/security/tls',
        **{f'/etc/nginx/conf.d/{f}': 'deploy/nginx/' + f for f in
           ('security-http.conf', 'security-server.conf', 'security-headers.conf')},
        **{f'/usr/share/nginx/html/{k}': v for k, v in {
            'pc': 'frontend/dist', 'portal': 'student-portal/dist',
            'enterprise': 'enterprise-portal/dist', 'miniapp': 'miniapp/dist/build/h5',
        }.items()},
    },
}
COMMANDS = {
    'scheduler': ['sh', '-c', 'python scripts/security_profile_probe.py filesystem && python scripts/check_production_redis.py && exec python -m scripts.run_scheduled_jobs'],
    'file-scan': ['sh', '-c', 'python scripts/security_profile_probe.py filesystem && python scripts/check_production_file_scan.py && exec python -m app.workers.file_scan_worker'],
}
# These are absent in the supported profile; reject additions rather than try
# to classify every possible command, mount or namespace they might introduce.
OVERRIDES = ('volumes_from', 'configs', 'secrets', 'post_start', 'pre_start', 'pre_stop',
             'develop', 'profiles', 'deploy', 'extra_hosts', 'dns', 'dns_search',
             'external_links', 'links', 'group_add', 'device_cgroup_rules', 'gpus',
             'models', 'sysctls', 'storage_opt', 'runtime', 'pid', 'ipc', 'uts', 'userns_mode')
MYSQL_COMMAND = [
    '--character-set-server=utf8mb4', '--collation-server=utf8mb4_unicode_ci',
    '--innodb-buffer-pool-size=512M', '--max-connections=200', '--log-bin=mysql-bin',
    '--binlog-format=ROW', '--log-bin-trust-function-creators=1',
    '--binlog-expire-logs-seconds=604800', '--sync-binlog=1', '--innodb-flush-log-at-trx-commit=1',
]
MYSQL_HEALTH = ['CMD-SHELL', 'MYSQL_PWD="${MYSQL_PASSWORD}" mysql --protocol=TCP -h127.0.0.1 -u"${MYSQL_USER}" -Nse "SELECT 1"']


def execution_errors(config: dict) -> list[str]:
    errors = []
    services = config['services']
    if config.get('name') != PROJECT:
        errors.append('FIXED_PROJECT_IDENTITY_REQUIRED')
    if services.get('mysql', {}).get('command') != MYSQL_COMMAND:
        errors.append('MYSQL_TRUSTED_MIGRATOR_BINLOG_CONTRACT_REQUIRED')
    for name in NETWORKS:
        service = services.get(name, {})
        if (service.get('entrypoint') is not None or service.get('working_dir') is not None
                or any(service.get(key) for key in OVERRIDES)):
            errors.append(name + ':EXECUTION_OVERRIDE_FORBIDDEN')
        if (set(service.get('networks', {})) != NETWORKS[name]
                or (name != 'prepare-storage' and service.get('network_mode') is not None)):
            errors.append(name + ':EXACT_NETWORK_ATTACHMENTS_REQUIRED')
        if any(str(option).replace('=', ':') not in {'no-new-privileges', 'no-new-privileges:true'}
               for option in service.get('security_opt', [])):
            errors.append(name + ':SECURITY_OPTION_OVERRIDE_FORBIDDEN')
        if name in COMMANDS and service.get('command') != COMMANDS[name]:
            errors.append(name + ':WORKER_COMMAND_DRIFT')
        if name in ('nginx', 'clamav') and service.get('command') is not None:
            errors.append(name + ':IMAGE_COMMAND_OVERRIDE_FORBIDDEN')
        # Do not let a pass-always check (or NONE) replace image readiness.
        health = service.get('healthcheck', {})
        if name in ('backend', 'clamav') and health:
            errors.append(name + ':IMAGE_HEALTHCHECK_OVERRIDE_FORBIDDEN')
        if name in ('mysql', 'redis'):
            expected = MYSQL_HEALTH if name == 'mysql' else ['CMD', 'redis-cli', 'ping']
            # Compose config serializes dollar signs as $$ even in JSON
            # (cmd/compose/config.go: escapeDollarSign). Match the exact known
            # command in model or serialized form; never broadly normalize shell.
            serialized = [str(part).replace('$', '$$') for part in expected]
            if health.get('disable') or health.get('test') not in (expected, serialized):
                errors.append(name + ':AUTHENTICATED_HEALTHCHECK_REQUIRED')
        if name in APPS:
            required = {'mysql': 'service_healthy', 'redis': 'service_healthy',
                        'migrate': 'service_completed_successfully',
                        'prepare-storage': 'service_completed_successfully'}
            if name != 'scheduler':
                required['clamav'] = 'service_healthy'
            dependencies = service.get('depends_on', {})
            if (set(dependencies) != set(required) or any(
                    dependencies.get(dep, {}).get('condition') != condition
                    or dependencies.get(dep, {}).get('required') is False
                    for dep, condition in required.items())):
                errors.append(name + ':STARTUP_DEPENDENCY_DRIFT')
        if name in (*APPS, 'migrate'):
            mounts = service.get('tmpfs', [])
            if (len(mounts) != 1 or not isinstance(mounts[0], str)
                    or mounts[0].split(':', 1)[0] != '/tmp'
                    or not {'rw', 'nosuid', 'nodev', 'noexec'}.issubset(set(mounts[0].partition(':')[2].split(',')))):
                errors.append(name + ':EXACT_TEMPORARY_STORAGE_REQUIRED')
        mounted = service.get('volumes', [])
        named = [m for m in mounted if isinstance(m, dict) and m.get('type') == 'volume']
        bound = [m for m in mounted if isinstance(m, dict) and m.get('type') == 'bind']
        wanted = NAMED_MOUNTS[name]
        if (len(named) != len(wanted) or {(m.get('source'), m.get('target')) for m in named} != wanted
                or any(m.get('read_only') or m.get('volume') for m in named)):
            errors.append(name + ':NAMED_VOLUME_BOUNDARY_DRIFT')
        binds = BIND_MOUNTS.get(name, {})
        if (len(bound) != len(binds) or {m.get('target') for m in bound} != set(binds)
                or len(named) + len(bound) != len(mounted)):
            errors.append(name + ':BIND_TARGET_BOUNDARY_DRIFT')
        if any(not m.get('read_only') or m.get('bind', {}).get('create_host_path') is not False
               or m.get('bind', {}).get('propagation') not in (None, 'rprivate') for m in bound):
            errors.append(name + ':BIND_OPTIONS_DRIFT')
    volumes = config.get('volumes', {})
    if set(volumes) != VOLUMES:
        errors.append('EXACT_OWNED_VOLUME_SET_REQUIRED')
    for name in VOLUMES:
        value = volumes.get(name) or {}
        if (set(value) - {'name', 'driver', 'external'} or value.get('external')
                or value.get('driver') not in (None, 'local')
                or value.get('name', PROJECT + '_' + name) != PROJECT + '_' + name):
            errors.append('OWNED_LOCAL_VOLUME_REQUIRED:' + name)
    networks = config.get('networks', {})
    if set(networks) != {'edge', 'data', 'scan', 'egress'}:
        errors.append('EXACT_NETWORK_SET_REQUIRED')
    for name in ('edge', 'data', 'scan', 'egress'):
        value = networks.get(name) or {}
        if (set(value) - {'name', 'driver', 'internal', 'ipam'}
                or value.get('driver') != 'bridge'
                or bool(value.get('internal')) != (name in {'data', 'scan'})
                or value.get('name', PROJECT + '_' + name) != PROJECT + '_' + name):
            errors.append('OWNED_BRIDGE_NETWORK_REQUIRED:' + name)
        ipam = value.get('ipam', {})
        if name == 'edge':
            if (set(ipam) - {'driver', 'config'} or ipam.get('driver', 'default') != 'default'
                    or ipam.get('config') != [{'subnet': '172.30.40.0/24'}]):
                errors.append('EDGE_NETWORK_SUBNET_DRIFT')
        elif ipam:
            errors.append('NETWORK_IPAM_OVERRIDE_FORBIDDEN:' + name)
    return sorted(set(errors))


def release_input_errors(config: dict, root: Path, compose: dict, runtime: dict) -> list[str]:
    """Tie the inspected local inputs to the actual resolved deployment inputs.

    Root must be the same resolved repository used to invoke Compose. A readonly
    mount with the right target is not enough if it reads a different host file.
    """
    errors = []
    root = root.resolve()
    services = config['services']
    for name, bindings in BIND_MOUNTS.items():
        for mount in services.get(name, {}).get('volumes', []):
            relative = bindings.get(mount.get('target'))
            if not relative:
                continue
            expected = root / relative
            actual = Path(mount.get('source', ''))
            if (not actual.is_absolute() or actual != expected or not expected.exists()
                    or actual.resolve() != expected.absolute()):
                errors.append(name + ':CHECKED_BIND_SOURCE_MISMATCH')
    for name in services:
        key = {'mysql': 'MYSQL_IMAGE', 'redis': 'REDIS_IMAGE', 'nginx': 'NGINX_IMAGE',
               'clamav': 'CLAMAV_IMAGE'}.get(name, 'APP_IMAGE')
        if services[name].get('image') != compose.get(key):
            errors.append('CHECKED_IMAGE_REFERENCE_MISMATCH')
    # Verify the secrets and policy supplied in runtime.env survive Compose
    # precedence unchanged. Explicit profile routing values are checked separately.
    for name in APPS:
        env = services.get(name, {}).get('environment', {})
        if any(env.get(key) != value for key, value in runtime.items()):
            errors.append(name + ':CHECKED_RUNTIME_ENV_MISMATCH')
        if env.get('DB_PASSWORD') != compose.get('DB_PASSWORD'):
            errors.append(name + ':CHECKED_DATABASE_CREDENTIAL_MISMATCH')
        url = 'redis://default:' + compose.get('REDIS_PASSWORD', '') + '@redis:6379/0'
        if env.get('REDIS_URL') != url:
            errors.append(name + ':CHECKED_REDIS_ENDPOINT_MISMATCH')
    mysql = services.get('mysql', {}).get('environment', {})
    for supplied, inspected in [('MYSQL_PASSWORD', 'DB_PASSWORD'), ('MYSQL_ROOT_PASSWORD', 'MYSQL_ROOT_PASSWORD'),
                                ('MIGRATOR_PASSWORD', 'MIGRATOR_PASSWORD')]:
        if mysql.get(supplied) != compose.get(inspected):
            errors.append('mysql:CHECKED_DATABASE_CREDENTIAL_MISMATCH')
    if services.get('migrate', {}).get('environment', {}).get('DB_PASSWORD') != compose.get('MIGRATOR_PASSWORD'):
        errors.append('migrate:CHECKED_DATABASE_CREDENTIAL_MISMATCH')
    redis = services.get('redis', {})
    password = compose.get('REDIS_PASSWORD', '')
    if (redis.get('environment', {}).get('REDISCLI_AUTH') != password or redis.get('command') != [
            'redis-server', '--appendonly', 'yes', '--appendfsync', 'everysec', '--maxmemory', '256mb',
            '--maxmemory-policy', 'noeviction', '--requirepass', password]):
        errors.append('redis:CHECKED_AUTH_STORAGE_COMMAND_MISMATCH')
    return sorted(set(errors))
