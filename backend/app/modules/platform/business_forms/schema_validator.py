"""Publish-time validation and deterministic hashing for business form schemas."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from app.core.exceptions import AppException

from .condition_dsl import GROUP_OPERATORS, LEAF_OPERATORS
from .schemas import BusinessFormVersionDTO, FormFieldType

MAX_FIELDS = 80
MAX_OPTIONS_PER_SELECT = 200
MAX_CONDITION_DEPTH = 8
MAX_CONDITION_NODES = 200
MAX_SCHEMA_STRING = 4000

RESERVED_KEYS = {
    "__proto__", "prototype", "constructor", "tenantId", "createdBy",
    "updatedBy", "permission", "role",
}
FORBIDDEN_SCHEMA_KEYS = {
    "script", "style", "html", "rawHtml", "component", "remoteComponent",
    "remoteOptionsUrl", "callbackUrl", "uploadUrl", "eventHandler",
}
FORBIDDEN_VALUE_MARKERS = (
    "javascript:", "data:text/html", "<script", "eval(", "function(", "function ",
)
FIELD_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")


def _fail(message: str, details=None) -> None:
    raise AppException("FORM_SCHEMA_INVALID", message, details=details, http_status=400)


def _scan_untrusted(value: Any, path: str = "schema") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text in RESERVED_KEYS or key_text in FORBIDDEN_SCHEMA_KEYS or key_text.lower().startswith("on"):
                _fail("表单 Schema 包含保留或危险键", {"path": f"{path}.{key_text}"})
            _scan_untrusted(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_untrusted(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > MAX_SCHEMA_STRING:
            _fail("表单 Schema 字符串超过预算", {"path": path, "maxLength": MAX_SCHEMA_STRING})
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_VALUE_MARKERS):
            _fail("表单 Schema 包含危险内容", {"path": path})
    elif isinstance(value, float) and not math.isfinite(value):
        _fail("表单 Schema 只允许有限数字", {"path": path})


def _validate_condition(
    node: dict, *, field_codes: set[str], depth: int, counter: list[int], path: str,
) -> None:
    if depth > MAX_CONDITION_DEPTH:
        _fail("表单条件深度超过预算", {"path": path, "maxDepth": MAX_CONDITION_DEPTH})
    if not isinstance(node, dict):
        _fail("表单条件必须为对象", {"path": path})
    counter[0] += 1
    if counter[0] > MAX_CONDITION_NODES:
        _fail("表单条件节点超过预算", {"maxNodes": MAX_CONDITION_NODES})
    op = str(node.get("op") or "").lower()
    if op in GROUP_OPERATORS:
        if set(node) != {"op", "conditions"}:
            _fail("组合条件仅允许 op/conditions", {"path": path})
        children = node.get("conditions")
        if not isinstance(children, list) or not children:
            _fail("组合条件必须包含非空 conditions", {"path": path})
        for index, child in enumerate(children):
            _validate_condition(
                child, field_codes=field_codes, depth=depth + 1,
                counter=counter, path=f"{path}.conditions[{index}]",
            )
        return
    if op not in LEAF_OPERATORS or set(node) != {"op", "field", "value"}:
        _fail("叶子条件仅允许受支持的 op/field/value", {"path": path})
    if str(node.get("field") or "") not in field_codes:
        _fail("表单条件引用未知字段", {"path": path, "field": node.get("field")})
    if op in {"in", "not_in"} and not isinstance(node.get("value"), list):
        _fail("in/not_in 的 value 必须是数组", {"path": path})


def schema_payload(version: BusinessFormVersionDTO) -> dict[str, Any]:
    return {
        "formCode": version.form_code,
        "schemaVersion": version.schema_version,
        "supportedClients": sorted(value.value for value in version.supported_clients),
        "policyRefs": [ref.model_dump(mode="json") for ref in version.policy_refs],
        "domainDataAdapter": version.domain_data_adapter,
        "domainCommandAdapter": version.domain_command_adapter,
        "fields": [field.model_dump(mode="json", by_alias=True) for field in version.fields],
        "conditions": version.conditions,
    }


def compute_schema_hash(version: BusinessFormVersionDTO) -> str:
    try:
        encoded = json.dumps(
            schema_payload(version),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AppException(
            "FORM_SCHEMA_INVALID",
            "表单 Schema 必须是标准 JSON 且数字必须有限",
            http_status=400,
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


class BusinessFormSchemaValidator:
    def validate(self, version: BusinessFormVersionDTO, *, verify_hash: bool = True) -> BusinessFormVersionDTO:
        raw = schema_payload(version)
        _scan_untrusted(raw)
        if not version.fields:
            _fail("表单至少需要一个字段")
        if len(version.fields) > MAX_FIELDS:
            _fail("表单字段数超过预算", {"maxFields": MAX_FIELDS})
        if not version.supported_clients:
            _fail("表单必须声明至少一个支持端")
        field_codes = [field.code for field in version.fields]
        if len(field_codes) != len(set(field_codes)):
            _fail("表单字段 code 不能重复")
        # One budget applies to the complete schema.  Resetting the counter for
        # every field would allow MAX_FIELDS * MAX_CONDITION_NODES nodes.
        condition_counter = [0]
        for index, field in enumerate(version.fields):
            if not FIELD_CODE.fullmatch(field.code) or field.code in RESERVED_KEYS:
                _fail("表单字段 code 非法或为保留字", {"field": field.code})
            if not str(field.label or "").strip():
                _fail("表单字段 label 不能为空", {"field": field.code})
            if field.type == FormFieldType.SELECT:
                if not field.options:
                    _fail("select 字段必须声明 options", {"field": field.code})
                if len(field.options) > MAX_OPTIONS_PER_SELECT:
                    _fail("select 选项数超过预算", {"field": field.code, "maxOptions": MAX_OPTIONS_PER_SELECT})
                option_values = [option.value for option in field.options]
                if len(option_values) != len(set(map(str, option_values))):
                    _fail("select 选项值不能重复", {"field": field.code})
                if any(not str(option.label or "").strip() for option in field.options):
                    _fail("select 选项 label 不能为空", {"field": field.code})
            elif field.options:
                _fail("只有 select 字段可声明 options", {"field": field.code})
            if field.multiple and field.type not in {FormFieldType.SELECT, FormFieldType.FILE}:
                _fail("只有 select/file 字段可声明 multiple", {"field": field.code})
            if field.max_length is not None:
                if field.type not in {FormFieldType.TEXT, FormFieldType.TEXTAREA}:
                    _fail("只有文本字段可声明 maxLength", {"field": field.code})
                if field.max_length <= 0 or field.max_length > MAX_SCHEMA_STRING:
                    _fail(
                        "文本字段 maxLength 超出预算",
                        {"field": field.code, "maxLength": MAX_SCHEMA_STRING},
                    )
            if field.min_value is not None or field.max_value is not None:
                if field.type != FormFieldType.NUMBER:
                    _fail("只有 number 字段可声明 min/max", {"field": field.code})
                bounds = [value for value in (field.min_value, field.max_value) if value is not None]
                if any(not math.isfinite(float(value)) for value in bounds):
                    _fail("number 字段 min/max 必须是有限数字", {"field": field.code})
                if (
                    field.min_value is not None
                    and field.max_value is not None
                    and field.min_value > field.max_value
                ):
                    _fail("number 字段 min 不能大于 max", {"field": field.code})
            for condition_name, condition in (
                ("visibleWhen", field.visible_when),
                ("requiredWhen", field.required_when),
                ("readonlyWhen", field.readonly_when),
            ):
                if condition is not None:
                    _validate_condition(
                        condition, field_codes=set(field_codes), depth=1, counter=condition_counter,
                        path=f"fields[{index}].{condition_name}",
                    )
        for index, condition in enumerate(version.conditions):
            _validate_condition(
                condition, field_codes=set(field_codes), depth=1,
                counter=condition_counter, path=f"conditions[{index}]",
            )
        expected = compute_schema_hash(version)
        if verify_hash and version.schema_hash != expected:
            raise AppException("FORM_SCHEMA_HASH_MISMATCH", "表单 Schema 哈希不匹配", http_status=409)
        return version
