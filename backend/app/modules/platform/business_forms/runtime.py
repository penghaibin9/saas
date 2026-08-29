"""Server-side dual evaluation and submission-value authorization."""
from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Callable

from app.core.exceptions import AppException

from .condition_dsl import evaluate_condition
from .schema_validator import BusinessFormSchemaValidator
from .schemas import BusinessFormVersionDTO, FormClient, FormFieldType


class BusinessFormRuntimeValidator:
    def __init__(
        self,
        *,
        student_authorizer: Callable[[Any, dict, dict], bool] | None = None,
        file_authorizer: Callable[[Any, dict, dict], bool] | None = None,
    ):
        self._student_authorizer = student_authorizer
        self._file_authorizer = file_authorizer
        self._schema_validator = BusinessFormSchemaValidator()

    @staticmethod
    def _invalid(field: str, message: str, code: str = "FORM_VALUE_INVALID") -> None:
        raise AppException(code, message, details={"field": field}, http_status=400)

    def _validate_value(self, field, value: Any) -> None:
        if field.type in {FormFieldType.TEXT, FormFieldType.TEXTAREA}:
            if not isinstance(value, str):
                self._invalid(field.code, "字段必须是字符串")
            if field.max_length is not None and len(value) > field.max_length:
                self._invalid(field.code, "字段长度超过限制")
        elif field.type == FormFieldType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                self._invalid(field.code, "字段必须是数字")
            if not math.isfinite(float(value)):
                self._invalid(field.code, "字段必须是有限数字")
            if field.min_value is not None and value < field.min_value:
                self._invalid(field.code, "字段小于最小值")
            if field.max_value is not None and value > field.max_value:
                self._invalid(field.code, "字段大于最大值")
        elif field.type == FormFieldType.SELECT:
            allowed = {str(option.value) for option in field.options}
            candidates = value if field.multiple else [value]
            if field.multiple and not isinstance(value, list):
                self._invalid(field.code, "多选字段必须是数组")
            if any(str(candidate) not in allowed for candidate in candidates):
                self._invalid(field.code, "选项值不在发布版本白名单内")
        elif field.type in {FormFieldType.DATE, FormFieldType.DATETIME}:
            if not isinstance(value, str):
                self._invalid(field.code, "日期字段必须是 ISO 字符串")
            try:
                (date.fromisoformat(value) if field.type == FormFieldType.DATE else datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                self._invalid(field.code, "日期格式无效")
        elif field.type == FormFieldType.FILE:
            values = value if field.multiple else [value]
            if field.multiple and not isinstance(value, list):
                self._invalid(field.code, "多文件字段必须是数组")
            valid_file_id = lambda item: (
                isinstance(item, str) and bool(item.strip())
            ) or (
                isinstance(item, int) and not isinstance(item, bool) and item > 0
            )
            if not values or any(not valid_file_id(item) for item in values):
                self._invalid(field.code, "文件字段必须提交 File Center ID")
        elif field.type == FormFieldType.STUDENT_PICKER:
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                self._invalid(field.code, "学生选择字段必须提交学生 ID")

    def validate_submission(
        self,
        *,
        version: BusinessFormVersionDTO,
        submitted_values: dict[str, Any],
        client: FormClient | str,
        schema_hash: str,
        version_id: int,
        context: dict,
        user: dict,
        authoritative_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._schema_validator.validate(version)
        if int(version_id) != int(version.version_id):
            raise AppException("FORM_VERSION_STALE", "表单版本已更新，请刷新后重试", http_status=409)
        if schema_hash != version.schema_hash:
            raise AppException("FORM_SCHEMA_HASH_MISMATCH", "表单 Schema 哈希不匹配", http_status=409)
        try:
            normalized_client = FormClient(client)
        except (TypeError, ValueError) as exc:
            raise AppException(
                "FORM_CLIENT_UNSUPPORTED",
                "当前端不支持此表单，请前往 PC 办理",
                http_status=409,
            ) from exc
        if normalized_client not in version.supported_clients:
            raise AppException("FORM_CLIENT_UNSUPPORTED", "当前端不支持此表单，请前往 PC 办理", http_status=409)
        if not isinstance(submitted_values, dict):
            raise AppException("FORM_VALUE_INVALID", "表单 values 必须是对象")
        by_code = {field.code: field for field in version.fields}
        unknown = sorted(set(submitted_values) - set(by_code))
        if unknown:
            raise AppException("FORM_FIELD_INJECTION", "提交包含未发布字段", details={"fields": unknown}, http_status=400)
        if authoritative_values is not None and not isinstance(authoritative_values, dict):
            raise AppException("FORM_ADAPTER_INVALID", "业务表单初始数据必须是对象", http_status=500)
        # Client conditions are evaluated against initialData plus the current
        # draft.  Rebuild that same view from a freshly authorized data-adapter
        # read so readonly/server-owned facts cannot disappear at submit time.
        # Submitted values win only for condition evaluation; an attempted
        # readonly submission is still rejected below before any command runs.
        condition_values = {
            key: value
            for key, value in (authoritative_values or {}).items()
            if key in by_code
        }
        condition_values.update(submitted_values)
        sanitized: dict[str, Any] = {}
        for field in version.fields:
            visible = field.visible_when is None or evaluate_condition(field.visible_when, condition_values)
            readonly = field.readonly or (
                field.readonly_when is not None and evaluate_condition(field.readonly_when, condition_values)
            )
            required = visible and (
                field.required or (
                    field.required_when is not None and evaluate_condition(field.required_when, condition_values)
                )
            )
            present = field.code in submitted_values
            value = submitted_values.get(field.code)
            if present and not visible:
                self._invalid(field.code, "禁止提交隐藏字段", "FORM_HIDDEN_FIELD_INJECTION")
            if present and readonly:
                self._invalid(field.code, "禁止提交只读字段", "FORM_READONLY_FIELD_INJECTION")
            if required and (not present or value is None or value == "" or value == []):
                self._invalid(field.code, "必填字段缺失", "FORM_REQUIRED")
            if not present or value is None:
                continue
            self._validate_value(field, value)
            if field.type == FormFieldType.STUDENT_PICKER:
                if self._student_authorizer is None:
                    raise AppException("FORM_AUTHORIZER_MISSING", "学生选择授权器未配置", http_status=500)
                if not self._student_authorizer(value, context, user):
                    raise AppException("NO_DATA_SCOPE", "无权选择该学生", http_status=403)
            if field.type == FormFieldType.FILE:
                if self._file_authorizer is None:
                    raise AppException("FORM_AUTHORIZER_MISSING", "文件授权器未配置", http_status=500)
                file_ids = value if field.multiple else [value]
                if any(not self._file_authorizer(file_id, context, user) for file_id in file_ids):
                    raise AppException("NO_PERMISSION", "文件不存在或无权访问", http_status=403)
            sanitized[field.code] = value
        return sanitized
