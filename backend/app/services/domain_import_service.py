"""6 大业务域通用导入（Dry-Run 校验 + 确认写入）。行级校验：主键字段必填 + 批内/库内查重。"""
from __future__ import annotations

import uuid

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found


def _tid() -> int:
    try:
        return int(current_tenant_id() or 1000000000000000001)
    except (TypeError, ValueError):
        return 1000000000000000001


# 域 → (key字段前端名, create 服务路径, list 服务路径, 展示名)
DOMAINS = {
    "orientation": ("admissionNo", "orientation_service.create_student",
                    "orientation_service.list_students", "录取编号"),
    "campus-service": ("studentNo", "campus_service_service.create_student",
                       "campus_service_service.list_students", "学号"),
    "academic": ("studentNo", "academic_service.create_student",
                 "academic_service.list_students", "学号"),
    "employment": ("studentNo", "employment_service.create_student",
                   "employment_service.list_students", "学号"),
}

_MEM: dict[str, dict] = {}


def _svc(path):
    import importlib
    mod_name, fn = path.split(".")
    return getattr(importlib.import_module(f"app.services.{mod_name}"), fn)


def dry_run(domain: str, rows: list[dict]) -> dict:
    if domain not in DOMAINS:
        raise AppException("VALIDATION_ERROR", f"未知导入域：{domain}（支持 {'/'.join(DOMAINS)}）")
    key_field, _, list_path, key_label = DOMAINS[domain]
    existing = {str(r.get(key_field) or "") for r in _svc(list_path)(1, 100000)[0]}
    ok_rows, errors, seen = [], [], set()
    for i, row in enumerate(rows, start=2):
        name = str(row.get("name") or row.get("姓名") or "").strip()
        key = str(row.get(key_field) or row.get(key_label) or "").strip()
        if not name or not key:
            errors.append({"rowIndex": i, "field": "name" if not name else key_field,
                           "rawValue": name or key, "message": f"姓名/{key_label} 必填"})
            continue
        if key in seen:
            errors.append({"rowIndex": i, "field": key_field, "rawValue": key,
                           "message": f"{key_label} {key} 在文件内重复"})
            continue
        if key in existing:
            errors.append({"rowIndex": i, "field": key_field, "rawValue": key,
                           "message": f"{key_label} {key} 已存在"})
            continue
        seen.add(key)
        ok_rows.append({"name": name, key_field: key, "className": row.get("className") or row.get("班级")})
    batch_no = f"IMP{uuid.uuid4().hex[:10]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    # 绑定当前租户，防止跨租户凭 batchNo 猜测/泄露确认写入他人数据（与 import_export_service 口径一致）
    _MEM[batch_no] = {"domain": domain, "rows": ok_rows, "status": status, "tenantId": _tid()}
    return {"batchNo": batch_no, "status": status, "totalRows": len(rows),
            "okRows": len(ok_rows), "errorRows": len(errors), "errors": errors[:50]}


def confirm(batch_no: str) -> dict:
    batch = _MEM.get(batch_no)
    if not batch or batch.get("tenantId") != _tid():
        raise not_found("导入批次不存在或已过期，请重新校验")
    if batch["status"] != "DRY_RUN_PASSED":
        raise AppException("VALIDATION_ERROR", "该批次未通过 Dry-Run 校验，禁止确认导入")
    create = _svc(DOMAINS[batch["domain"]][1])
    inserted = 0
    for r in batch["rows"]:
        create({k: v for k, v in r.items() if v is not None})
        inserted += 1
    batch["status"] = "SUCCESS"
    return {"batchNo": batch_no, "status": "SUCCESS", "insertedRows": inserted}
