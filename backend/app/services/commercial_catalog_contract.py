"""M1 deterministic catalogue/order draft contracts, not an entitlement writer.

The caller must resolve catalogue revisions and approved feature/policy scopes
from server-owned storage. These functions do not publish SKUs, create paid
orders, migrate customers, grant permissions or validate business approvals.
Compiled JSON is detached and immutable; persistence/authorization stay with
the existing control-plane services when the M1 integration gate is complete.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re
from typing import Callable, Iterable, Mapping

MODULE_FEATURES = {
    "internship": "internship", "graduationDesign": "graduation",
    "studentAffairs": "studentAffairs", "academicAffairs": "academicAffairs",
}
MAX_AMOUNT = Decimal('9999999999.99')  # Existing t_order NUMERIC(12, 2).
MONEY = re.compile(r'(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z')
CODE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


class ContractError(ValueError):
    """Invalid draft; adapters translate this to the existing API error envelope."""


def integer(value: object, field: str, *, minimum: int = 0, maximum: int = 2**31 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(f'{field}: expected integer {minimum}..{maximum}')
    return value


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,18}', value) or int(value) > 2**63 - 1:
        raise ContractError(f'{field}: expected positive BIGINT string')
    return value


def code(value: object, field: str) -> str:
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise ContractError(f'{field}: invalid code')
    return value


def money(value: object, field: str) -> Decimal:
    # Reject floats, exponential notation and silent rounding at the boundary.
    if isinstance(value, Decimal):
        if not value.is_finite() or value < 0 or value > MAX_AMOUNT:
            raise ContractError(f'{field}: amount out of range')
        text = format(value, 'f')
    elif isinstance(value, str):
        text = value
    else:
        raise ContractError(f'{field}: use a decimal string, never float')
    if not MONEY.fullmatch(text):
        raise ContractError(f'{field}: expected nonnegative amount with at most two decimals')
    try:
        with localcontext() as context:
            context.prec = 40
            return Decimal(text).quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ContractError(f'{field}: invalid decimal') from exc


def instant(value: object, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40 or 'T' not in value:
        raise ContractError(f'{field}: expected ISO timestamp with timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('timezone missing')
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ContractError(f'{field}: invalid timezone-aware instant') from exc


def canonical(data: object) -> str:
    try:
        text = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if len(text.encode('utf-8')) > 262144:
            raise ContractError('snapshot exceeds the 256 KiB draft limit')
        return text
    except (ValueError, TypeError) as exc:
        raise ContractError('snapshot must contain finite JSON values') from exc


@dataclass(frozen=True)
class Snapshot:
    """Value object only. A hash proves content consistency, not publication/identity."""
    canonical_json: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json.encode('utf-8')).hexdigest()

    def as_dict(self) -> dict:
        return json.loads(self.canonical_json)


def _fields(data: object, allowed: set[str], required: set[str], field: str) -> dict:
    if not isinstance(data, dict) or set(data) - allowed or required - set(data):
        raise ContractError(f'{field}: missing or unexpected fields')
    return data


def compile_sku(
    payload: dict, *, known_features: Iterable[str],
    approved_features: Mapping[str, Iterable[str]],
    resolve_component: Callable[[str, int], Snapshot] | None = None,
) -> Snapshot:
    """Validate a draft using an externally reviewed capability scope.

    The approval mapping is mandatory and must never originate in request JSON.
    Bundles bind exact immutable component hashes, not current catalogue prices.
    """
    fields = {'skuCode', 'revision', 'name', 'productType', 'moduleKey', 'features',
              'quotas', 'components', 'pricePolicy', 'lifecyclePolicyVersion'}
    data = _fields(payload, fields, fields - {'moduleKey', 'features', 'quotas', 'components'}, 'sku')
    sku_code = code(data['skuCode'], 'skuCode')
    revision = integer(data['revision'], 'revision', minimum=1)
    name = data['name']
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ContractError('name: required, at most 100 characters')
    kind = data['productType']
    if not isinstance(kind, str) or kind not in {'MODULE', 'BUNDLE', 'ADDON'}:
        raise ContractError('productType: invalid value')
    known = frozenset(known_features)
    if any(not isinstance(k, str) or not k for k in known) or not set(MODULE_FEATURES.values()) <= known:
        raise ContractError('known_features: incomplete server feature catalogue')
    features = {key: False for key in sorted(known)}
    components = []
    module = data.get('moduleKey')
    if kind == 'BUNDLE':
        if module is not None or data.get('features') or data.get('quotas'):
            raise ContractError('bundle rights and quotas must come from component snapshots')
        refs = data.get('components')
        if not isinstance(refs, list) or not 1 <= len(refs) <= 20 or resolve_component is None:
            raise ContractError('bundle requires 1..20 resolved components')
        seen = set()
        for ref in refs:
            _fields(ref, {'skuCode', 'revision', 'contentHash'}, {'skuCode', 'revision', 'contentHash'}, 'component')
            component_key = (code(ref['skuCode'], 'component.skuCode'), integer(ref['revision'], 'component.revision', minimum=1))
            if component_key in seen or component_key[0] == sku_code:
                raise ContractError('duplicate or self-referencing component')
            seen.add(component_key)
            snapshot = resolve_component(*component_key)
            if not isinstance(snapshot, Snapshot) or snapshot.content_hash != ref['contentHash']:
                raise ContractError('component content fingerprint mismatch')
            child = snapshot.as_dict()
            if (child.get('skuCode'), child.get('revision')) != component_key or child.get('productType') not in {'MODULE', 'ADDON'}:
                raise ContractError('component identity mismatch or nested bundle unsupported')
            if set(child.get('features', {})) != known or any(type(v) is not bool for v in child['features'].values()):
                raise ContractError('component feature catalogue drift')
            components.append({'contentHash': snapshot.content_hash, 'snapshot': child})
            features = {key: value or child['features'][key] for key, value in features.items()}
    else:
        if not isinstance(module, str) or module not in MODULE_FEATURES or data.get('components'):
            raise ContractError('moduleKey must be canonical; non-bundles cannot have components')
        scope = frozenset(approved_features.get(module, ()))
        if not scope or not scope <= known:
            raise ContractError('reviewed capability scope is missing or contains unknown features')
        supplied = data.get('features', {})
        if not isinstance(supplied, dict) or not set(supplied) <= known or any(type(v) is not bool for v in supplied.values()):
            raise ContractError('features: unknown key or non-boolean value')
        enabled = {key for key, value in supplied.items() if value}
        if not enabled or not enabled <= scope:
            raise ContractError('features exceed the reviewed scope')
        core = set(MODULE_FEATURES.values())
        if kind == 'MODULE' and (enabled & core != {MODULE_FEATURES[module]} or enabled & {'employment', 'apiAccess'}):
            raise ContractError('module SKU cannot grant another centre or implicit paid add-ons')
        if kind == 'ADDON' and enabled & core:
            raise ContractError('add-on cannot grant a base centre')
        features.update(supplied)
    quotas = data.get('quotas', {})
    if not isinstance(quotas, dict) or len(quotas) > 30:
        raise ContractError('quotas: invalid mapping')
    clean_quotas = {}
    for key, rule in quotas.items():
        code(key, 'quota key')
        _fields(rule, {'limit', 'unit', 'aggregation'}, {'limit', 'unit', 'aggregation'}, 'quota')
        if not isinstance(rule['aggregation'], str) or rule['aggregation'] not in {'MAX', 'SUM', 'REPLACE'}:
            raise ContractError('quota aggregation must be explicit')
        clean_quotas[key] = {'limit': integer(rule['limit'], 'quota.limit', maximum=2**53 - 1),
                             'unit': code(rule['unit'], 'quota.unit'), 'aggregation': rule['aggregation']}
    policy = _fields(data['pricePolicy'], {'unitPrice', 'currency', 'taxTreatment'}, {'unitPrice', 'currency', 'taxTreatment'}, 'pricePolicy')
    if not isinstance(policy['currency'], str) or not re.fullmatch(r'[A-Z]{3}', policy['currency']):
        raise ContractError('currency: expected explicit ISO-style three-letter code')
    if not isinstance(policy['taxTreatment'], str) or policy['taxTreatment'] not in {'INCLUSIVE', 'EXCLUSIVE', 'EXEMPT', 'UNSPECIFIED'}:
        raise ContractError('taxTreatment: invalid value')
    price = {'unitPrice': format(money(policy['unitPrice'], 'unitPrice'), '.2f'),
             'currency': policy['currency'], 'taxTreatment': policy['taxTreatment']}
    return Snapshot(canonical({'skuCode': sku_code, 'revision': revision, 'name': name.strip(),
        'productType': kind, 'moduleKey': module, 'features': features, 'quotas': clean_quotas,
        'components': components, 'pricePolicy': price,
        'lifecyclePolicyVersion': code(data['lifecyclePolicyVersion'], 'lifecyclePolicyVersion')}))


def compile_order_draft(payload: dict, *, resolve_sku: Callable[[str, int], Snapshot]) -> Snapshot:
    """Read-only preflight. Never marks an order paid or gives a school rights.

    Persistence must enforce tenant authorization, actual publication, policy
    approval and idempotency in one transaction. They are NOT proven here.
    """
    fields = {'tenantId', 'currency', 'totalAmount', 'items'}
    data = _fields(payload, fields, fields, 'order')
    tenant_id = identifier(data['tenantId'], 'tenantId')
    if not isinstance(data['currency'], str) or not re.fullmatch(r'[A-Z]{3}', data['currency']):
        raise ContractError('currency: invalid code')
    if not isinstance(data['items'], list) or not 1 <= len(data['items']) <= 100:
        raise ContractError('items: expected 1..100 lines')
    total = money(data['totalAmount'], 'totalAmount')
    lines = []
    running = Decimal('0.00')
    seen = set()
    for source in data['items']:
        keys = {'lineNo', 'skuCode', 'skuRevision', 'skuContentHash', 'quantity',
                'unitPrice', 'discountAmount', 'netAmount', 'startAt', 'endAt', 'requestedGeneration'}
        line = _fields(source, keys, keys, 'order item')
        number = integer(line['lineNo'], 'lineNo', minimum=1, maximum=100)
        if number in seen:
            raise ContractError('duplicate lineNo')
        seen.add(number)
        selected = (code(line['skuCode'], 'skuCode'), integer(line['skuRevision'], 'skuRevision', minimum=1))
        snapshot = resolve_sku(*selected)
        if not isinstance(snapshot, Snapshot) or snapshot.content_hash != line['skuContentHash']:
            raise ContractError('SKU fingerprint mismatch; reload the catalogue')
        sku = snapshot.as_dict()
        if (sku.get('skuCode'), sku.get('revision')) != selected or sku.get('pricePolicy', {}).get('currency') != data['currency']:
            raise ContractError('SKU identity or currency mismatch')
        if sku.get('productType') not in {'MODULE', 'ADDON'}:
            raise ContractError('bundle orders require reviewed component price allocation first')
        quantity = integer(line['quantity'], 'quantity', minimum=1, maximum=1000000)
        unit_price = money(line['unitPrice'], 'unitPrice')
        discount = money(line['discountAmount'], 'discountAmount')
        net = money(line['netAmount'], 'netAmount')
        with localcontext() as context:
            context.prec = 40
            gross = unit_price * quantity
            calculated_net = gross - discount
        if gross > MAX_AMOUNT or discount > gross or calculated_net != net:
            raise ContractError('line amount does not reconcile')
        start, end = instant(line['startAt'], 'startAt'), instant(line['endAt'], 'endAt')
        if start >= end:
            raise ContractError('service interval must be nonempty [startAt,endAt)')
        with localcontext() as context:
            context.prec = 40
            running += net
        if running > MAX_AMOUNT:
            raise ContractError('order amount exceeds existing header capacity')
        lines.append({'lineNo': number, 'skuCode': selected[0], 'skuRevision': selected[1],
            'moduleKey': sku['moduleKey'], 'skuContentHash': snapshot.content_hash,
            'requestedGeneration': integer(line['requestedGeneration'], 'requestedGeneration', minimum=1),
            'quantity': quantity, 'unitPrice': format(unit_price, '.2f'),
            'discountAmount': format(discount, '.2f'), 'netAmount': format(net, '.2f'),
            'currency': data['currency'], 'startAt': start.isoformat().replace('+00:00', 'Z'),
            'endAt': end.isoformat().replace('+00:00', 'Z'), 'skuSnapshot': sku})
    if running != total:
        raise ContractError('order header total differs from line totals')
    return Snapshot(canonical({'tenantId': tenant_id, 'currency': data['currency'],
        'totalAmount': format(total, '.2f'), 'items': sorted(lines, key=lambda item: item['lineNo']),
        'validationOnly': True, 'paymentRecorded': False, 'rightsMaterialized': False}))
