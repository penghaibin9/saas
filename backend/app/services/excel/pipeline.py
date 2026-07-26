"""公共 Excel 底座 · 核心管道（V1.1）。

统一封装：模板生成 → 读文件 → 字段映射 → 校验（必填/类型/长度/格式/文件内重复/库内重复/业务规则）
→ 错误行收集 → 错误行 Excel → 统一预校验结构 → 确认导入 → 台账导出。

底层 xlsx 读写复用 app.services.xlsx_util（不重复造）；业务模块只提供 ImportSpec/ExportSpec。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.context import get_current_user_ctx
from app.core.permissions import enforce_permission
from app.services import xlsx_util

from .spec import ExportSpec, ImportSpec
from .validators import TYPE_VALIDATORS, check_max_length, check_required


def _enforce_spec_permission(spec: ImportSpec) -> None:
    """Import specifications are security boundaries, not documentation."""
    if spec.permission_key:
        enforce_permission(get_current_user_ctx() or {}, spec.permission_key)


def _canonical_rows_digest(rows: list) -> str:
    raw = json.dumps(rows or [], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _batch_scope(rows: list, explicit: str | None = None) -> str:
    values = {str(explicit)} if explicit else set()
    for row in rows or []:
        for key in ("batchId", "batchNo"):
            if row.get(key) not in (None, ""):
                values.add(str(row[key]).strip())
    return ",".join(sorted(value for value in values if value))


def _preview_token(spec: ImportSpec, rows: list, evidence: dict | None = None) -> str:
    user = get_current_user_ctx() or {}
    evidence = evidence or {}
    payload = {
        "module": spec.module_key,
        "biz": spec.biz_type,
        "tenant": str(user.get("tenantId") or ""),
        "user": str(user.get("userId") or ""),
        "rows": _canonical_rows_digest(rows),
        "fileName": str(evidence.get("fileName") or "manual-input"),
        "fileSha256": str(evidence.get("fileSha256") or _canonical_rows_digest(rows)),
        "batchScope": _batch_scope(rows, evidence.get("batchScope")),
        "dataScope": {
            "scope": user.get("dataScope"),
            "collegeId": user.get("collegeId"),
            "majorId": user.get("majorId"),
        },
        "expected": len(rows),
        "exp": int(time.time()) + 15 * 60,
    }
    payload["dryRunSha256"] = hashlib.sha256(json.dumps(
        {
            "module": payload["module"], "biz": payload["biz"], "rows": payload["rows"],
            "batchScope": payload["batchScope"], "expected": payload["expected"],
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _verify_preview_token(spec: ImportSpec, rows: list, token: str | None) -> dict:
    if spec.module_key != "graduationDesign":
        return {}
    if not token or "." not in token:
        raise AppException("VALIDATION_ERROR", "确认导入前必须重新完成预校验")
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = base64.urlsafe_b64encode(hmac.new(
            settings.jwt_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256,
        ).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4),
        ).decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise AppException("VALIDATION_ERROR", "预校验凭证无效，请重新校验") from None

    user = get_current_user_ctx() or {}
    expected = {
        "module": spec.module_key,
        "biz": spec.biz_type,
        "tenant": str(user.get("tenantId") or ""),
        "user": str(user.get("userId") or ""),
        "rows": _canonical_rows_digest(rows),
        "expected": len(rows),
        "dataScope": {
            "scope": user.get("dataScope"),
            "collegeId": user.get("collegeId"),
            "majorId": user.get("majorId"),
        },
    }
    if int(payload.get("exp") or 0) < int(time.time()) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise AppException("DATA_CONFLICT", "预校验凭证已过期或导入数据/操作者发生变化，请重新校验")


# ═══════════ 模板 ═══════════

    payload["previewToken"] = token
    return payload


def build_template(spec: ImportSpec) -> bytes:
    """按 ImportSpec 生成 .xlsx 模板（表头 + 必填标记 + 示例行 + 填写说明页）。"""
    _enforce_spec_permission(spec)
    samples = [[c.example for c in spec.columns]] if any(c.example != "" for c in spec.columns) else None
    return xlsx_util.build_template_xlsx(
        spec.headers,
        samples=samples,
        required=spec.required_titles,
        notes=spec.notes or _auto_notes(spec),
    )


def _auto_notes(spec: ImportSpec) -> list:
    """无自定义说明时，按列 help_text/type 自动生成填写说明。"""
    notes = ["1. 仅导入「导入模板」页；带 * 为必填列，请勿修改表头。"]
    for c in spec.columns:
        if c.help_text:
            notes.append(f"· {c.title}：{c.help_text}")
    return notes


def read_upload(spec: ImportSpec, file_bytes: bytes) -> list:
    """上传 .xlsx → list[dict]（按表头映射为字段 key）。"""
    _enforce_spec_permission(spec)
    return xlsx_util.read_xlsx(file_bytes, spec.header_map)


# ═══════════ 预校验（统一结构）═══════════

def _validate_cell(col, value: str) -> str | None:
    """单元格：必填 → 长度 → 类型内置 → enum → 自定义。返回首个错误。"""
    if col.required:
        msg = check_required(value, col)
        if msg:
            return msg
    if value == "":
        return None  # 非必填空值放行（不再跑格式校验）
    for fn in ([check_max_length] + TYPE_VALIDATORS.get(col.type, []) + list(col.validators)):
        msg = fn(value, col)
        if msg:
            return msg
    return None


def pre_validate(spec: ImportSpec, rows: list, evidence: dict | None = None) -> dict:
    """统一预校验结构（不写库）。

    返回：
      moduleKey/bizType/templateVersion,
      total/validRows/invalidRows/passed,
      rows: 原始行（供错误行重建与确认导入），
      errors: [{rowNo, field, title, rawValue, message}]  （rowNo 为数据行 1-based）
    """
    _enforce_spec_permission(spec)
    rows = rows or []
    errors: list = []
    seen: dict = {tuple(c.key for c in spec.unique_columns): set()} if spec.unique_columns else {}
    invalid_rows: set = set()

    for i, raw in enumerate(rows):
        row_no = i + 1
        row = {c.key: str(raw.get(c.key, "") or "").strip() for c in spec.columns}
        row_bad = False
        # 1) 逐列：必填/长度/类型/格式/enum/自定义
        for c in spec.columns:
            msg = _validate_cell(c, row.get(c.key, ""))
            if msg:
                errors.append({"rowNo": row_no, "field": c.key, "title": c.title,
                               "rawValue": row.get(c.key, ""), "message": msg})
                row_bad = True
        # 2) 文件内重复（多列联合唯一键）
        if spec.unique_columns and not row_bad:
            keyset = tuple(c.key for c in spec.unique_columns)
            val = tuple(row.get(k, "") for k in keyset)
            if all(v != "" for v in val):
                if val in seen[keyset]:
                    label = "+".join(c.title for c in spec.unique_columns)
                    errors.append({"rowNo": row_no, "field": keyset[0], "title": label,
                                   "rawValue": "/".join(val), "message": f"{label} 在文件内重复"})
                    row_bad = True
                else:
                    seen[keyset].add(val)
        # 3) 业务规则扩展点
        if spec.business_validate and not row_bad:
            msg = spec.business_validate(row, row_no)
            if msg:
                errors.append({"rowNo": row_no, "field": "_business", "title": "业务规则",
                               "rawValue": "", "message": msg})
                row_bad = True
        if row_bad:
            invalid_rows.add(row_no)

    # 4) 库内重复扩展点（整批一次）
    if spec.duplicate_check:
        dup = spec.duplicate_check(rows) or {}
        for row_no, msg in dup.items():
            errors.append({"rowNo": int(row_no), "field": "_duplicate", "title": "库内重复",
                           "rawValue": "", "message": msg})
            invalid_rows.add(int(row_no))

    total = len(rows)
    invalid = len(invalid_rows)
    result = {
        "moduleKey": spec.module_key, "bizType": spec.biz_type,
        "templateVersion": spec.template_version,
        "total": total, "validRows": total - invalid, "invalidRows": invalid,
        "passed": invalid == 0 and total > 0,
        "rows": rows,
        "errors": errors[: spec.max_preview_errors],
    }
    if spec.module_key == "graduationDesign" and result["passed"]:
        result["previewToken"] = _preview_token(spec, rows, evidence)
    return result


def build_error_rows(spec: ImportSpec, rows: list, errors: list) -> dict:
    """错误行 Excel（仅出错行 + 错误字段 + 错误原因），返回 pack 后的下载体。"""
    content = xlsx_util.build_error_rows_xlsx(spec.headers, rows, errors, spec.row_values)
    return xlsx_util.pack_xlsx_result(content, f"{spec.template_name}-导入错误行.xlsx", len(errors or []))


# ═══════════ 确认导入（统一模式）═══════════

def confirm_import(spec: ImportSpec, rows: list, preview_token: str | None = None) -> dict:
    """确认导入：重新预校验（必须全通过）→ transform → persist_rows。

    与前端「先预校验后确认」两步对齐；即使前端跳步，这里也强制再校验，杜绝脏数据落库。
    """
    _enforce_spec_permission(spec)
    evidence = _verify_preview_token(spec, rows, preview_token)
    pre = pre_validate(spec, rows)
    if not pre["passed"]:
        raise AppException("DATA_CONFLICT",
                           f"存在 {pre['invalidRows']} 行未通过预校验，禁止确认导入")
    if not spec.persist_rows:
        raise AppException("VALIDATION_ERROR", f"{spec.module_key}.{spec.biz_type} 未配置 persist_rows 落库逻辑")
    payload = [spec.transform_row(r) for r in rows] if spec.transform_row else list(rows)
    from . import job_service
    evidence_token = job_service.set_import_evidence({
        **evidence,
        "templateVersion": spec.template_version,
    }) if spec.module_key == "graduationDesign" else None
    try:
        result = spec.persist_rows(payload) or {}
    finally:
        if evidence_token is not None:
            job_service.reset_import_evidence(evidence_token)
    created = int(result.get("created", len(payload)))
    return {"moduleKey": spec.module_key, "bizType": spec.biz_type,
            "total": len(rows), "created": created, **result}


# ═══════════ 台账导出 ═══════════

def build_export(spec: ExportSpec, items: list, *, operator_name: str = "", tenant_label: str = "") -> dict:
    """按 ExportSpec 生成台账 .xlsx（首行水印 + 表头 + 逐列脱敏数据），返回 pack 下载体。"""
    data_rows = [spec.to_row(it) for it in (items or [])]
    wm = (f"{spec.sheet_title} · 导出人：{operator_name or '-'} · "
          f"{datetime.now():%Y-%m-%d %H:%M}")
    content = xlsx_util.build_ledger_xlsx(spec.sheet_title, spec.headers, data_rows, watermark=wm)
    name = spec.file_name or f"{spec.sheet_title}.xlsx"
    return xlsx_util.pack_xlsx_result(content, name, len(items or []), tenant_label=tenant_label)
