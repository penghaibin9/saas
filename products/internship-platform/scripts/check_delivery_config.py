"""Read-only candidate configuration gate, using only the Python standard library."""
from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit

KEYS = {'ENTERPRISE_PORTAL_BASE_URL', 'COMPOSE_PROFILES', 'ATTENDANCE_TENANT_ID', 'ATTENDANCE_BATCH_ID'}


def read_config(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.strip().partition('=')
        key = key.strip().removeprefix('export ')
        if not separator or key not in KEYS:
            continue
        if key in values:
            raise ValueError(f'{key} 重复配置，请保留唯一值')
        value = value.strip()
        if value.startswith(('"', "'")):
            end = value.find(value[0], 1)
            if end < 0 or value[end + 1:].strip() and not value[end + 1:].strip().startswith('#'):
                raise ValueError(f'{key} 引号或行尾格式不正确')
            value = value[1:end]
        else:
            value = value.split(' #', 1)[0].strip()
        values[key] = value
    return values


def public_enterprise_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        host = (url.hostname or '').encode('idna').decode('ascii').lower()
        if (url.scheme != 'https' or not host or url.username is not None or url.password is not None
                or url.query or url.fragment or url.path.rstrip('/') != '/enterprise'
                or url.port is not None and not 1 <= url.port <= 65535):
            return False
        try:
            address = ipaddress.ip_address(host)
            return address.is_global and not address.is_multicast
        except ValueError:
            if (host in {'localhost', 'example.com', 'example.org', 'example.net'}
                    or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid', '.example', '.example.com', '.example.org', '.example.net'))):
                return False
            return bool(re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', host))
    except (ValueError, UnicodeError):
        return False


def validate_config(values: dict[str, str]) -> list[str]:
    errors = []
    if not public_enterprise_url(values.get('ENTERPRISE_PORTAL_BASE_URL', '')):
        errors.append('ENTERPRISE_PORTAL_BASE_URL 须为无账号信息、查询或片段的 HTTPS 公网地址，路径须为 /enterprise')
    if 'attendance' not in {profile.strip() for profile in values.get('COMPOSE_PROFILES', '').split(',')}:
        errors.append('COMPOSE_PROFILES 必须显式包含 attendance 考勤配置档')
    for key in ('ATTENDANCE_TENANT_ID', 'ATTENDANCE_BATCH_ID'):
        value = values.get(key, '')
        if not re.fullmatch(r'[1-9][0-9]{0,18}', value) or int(value) > 9223372036854775807:
            errors.append(f'{key} 必须是已核验的学校或批次正整数编号')
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='检查指定候选交付环境文件，不连接数据库或公网')
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        errors = validate_config(read_config(args.env_file))
    except (OSError, UnicodeError, ValueError) as exc:
        errors = [str(exc) if isinstance(exc, ValueError) and not isinstance(exc, UnicodeError) else '环境文件无法读取']
    if errors:
        for error in errors:
            print(f'配置未通过：{error}')
        return 2
    print('候选配置合同通过；尚未验证域名、证书、实际学校批次、调度运行或业务交付。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
