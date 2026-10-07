"""Idempotent audit redaction without corrupting business identity fields."""
from __future__ import annotations
import hashlib

_SENSITIVE_PARTS = ('phone', 'mobile', 'idcard', 'id_card', 'token', 'contact',
                    'password', 'passwd', 'secret', 'credential', 'authorization', 'email')
_IP_KEYS = {'ip', 'client_ip', 'clientip', 'ip_address', 'ipaddress', 'remote_addr'}


def sanitize_audit_payload(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            name = str(key).lower()
            sensitive = name in _IP_KEYS or any(part in name for part in _SENSITIVE_PARTS)
            if sensitive and item:
                result[key] = item if isinstance(item, str) and item.startswith('sha256:') else (
                    'sha256:' + hashlib.sha256(str(item).encode('utf-8')).hexdigest()[:16])
            else:
                result[key] = sanitize_audit_payload(item)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize_audit_payload(item) for item in value]
    return value
