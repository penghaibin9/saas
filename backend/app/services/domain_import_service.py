"""6 大业务域通用导入（Dry-Run 校验 + 确认写入）。行级校验：主键字段必填 + 批内/库内查重。"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker


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
MAX_IMPORT_ROWS = 5000


def _import_service(mod_name):
    """定位服务模块：兼容旧 app.services.* 与目录收拢后的 app.modules.<中心>.services.*。

    仅改变“到哪里找模块”，不改导入校验/写入行为（目录收拢后的接线兼容）。
    """
    import importlib
    import pkgutil
    try:
        return importlib.import_module(f"app.services.{mod_name}")
    except ModuleNotFoundError:
        pass
    import app.modules as _modules
    for _sub in pkgutil.iter_modules(_modules.__path__):
        try:
            return importlib.import_module(f"app.modules.{_sub.name}.services.{mod_name}")
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"服务模块未找到：app.services.{mod_name} 或 app.modules.*.services.{mod_name}")


def _svc(path):
    mod_name, fn = path.split(".")
    return getattr(_import_service(mod_name), fn)


def _existing_keys(domain: str, list_path: str, key_field: str) -> set[str]:
    """只读取当前租户的查重键，避免为 Dry-Run 构造十万条完整列表字典。"""
    if not db_enabled():
        return {str(r.get(key_field) or "") for r in _svc(list_path)(1, MAX_IMPORT_ROWS)[0]}
    from app.models import AcademicStudent, CsServiceStudent, EmpStudent, OrientationStudent
    model, column = {
        "orientation": (OrientationStudent, OrientationStudent.admission_no),
        "campus-service": (CsServiceStudent, CsServiceStudent.student_no),
        "academic": (AcademicStudent, AcademicStudent.student_no),
        "employment": (EmpStudent, EmpStudent.student_no),
    }[domain]
    db = get_sessionmaker()()
    try:
        return {str(value) for value in db.scalars(select(column).where(
            model.tenant_id == _tid(), model.is_deleted.is_(False), column.is_not(None))).all()}
    finally:
        db.close()


def dry_run(domain: str, rows: list[dict]) -> dict:
    if domain not in DOMAINS:
        raise AppException("VALIDATION_ERROR", f"未知导入域：{domain}（支持 {'/'.join(DOMAINS)}）")
    if len(rows) > MAX_IMPORT_ROWS:
        raise AppException("VALIDATION_ERROR",
                           f"单次导入不能超过 {MAX_IMPORT_ROWS} 行，当前 {len(rows)} 行，请拆分后重试")
    key_field, _, list_path, key_label = DOMAINS[domain]
    existing = _existing_keys(domain, list_path, key_field)
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
