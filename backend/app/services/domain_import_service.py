"""域白名单通用导入（Dry-Run 校验 + 确认写入）。domain 必须由路由层白名单裁决后传入。"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.import_export_auth import assert_import_batch_owner
from app.db.session import db_enabled, get_sessionmaker


def _tid() -> int:
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    if db_enabled() and not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝域导入写入")
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝域导入写入")
    return tid


# 阶段 D：这些域的导入不得再凭 Excel 里的姓名+学号造学生，必须逐行确认学籍档案已存在。
# 迎新不在其中——录取候选人本来就还没有学籍，那是它的正常业务语义。
_REQUIRE_MASTER_PROFILE = {"campus-service", "academic", "employment"}

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


def _master_student_nos(domain: str) -> set[str] | None:
    """本租户已建档学号集合；不需要校验主档的域（迎新）返回 None。

    Dry-Run 阶段就把「查无此学籍」判成错行，用户在预检结果里一次看全，
    而不是确认导入时才一行行报 410。
    """
    if domain not in _REQUIRE_MASTER_PROFILE or not db_enabled():
        return None
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        return {str(v) for v in db.scalars(select(StudentProfile.student_no).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.student_no.is_not(None))).all()}
    finally:
        db.close()


def dry_run(domain: str, rows: list[dict], *, namespace: str | None = None, user: dict | None = None) -> dict:
    if domain not in DOMAINS:
        raise AppException("VALIDATION_ERROR", f"未知导入域：{domain}（支持 {'/'.join(DOMAINS)}）")
    if not _tid():
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝导入")
    if len(rows) > MAX_IMPORT_ROWS:
        raise AppException("VALIDATION_ERROR",
                           f"单次导入不能超过 {MAX_IMPORT_ROWS} 行，当前 {len(rows)} 行，请拆分后重试")
    key_field, _, list_path, key_label = DOMAINS[domain]
    existing = _existing_keys(domain, list_path, key_field)
    known_master = _master_student_nos(domain)
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
        if known_master is not None and key not in known_master:
            # 阶段 D 止血：没有学籍档案就不给建业务台账，否则又多一个"只在这个域里存在的学生"
            errors.append({"rowIndex": i, "field": key_field, "rawValue": key,
                           "message": f"{key_label} {key} 没有学籍档案，本域不能凭表格建学生。"
                                      "请先在「教务中心 → 学籍导入/补录」或「系统管理 → 学生导入与账号开通」建档"})
            continue
        seen.add(key)
        ok_rows.append({"name": name, key_field: key, "className": row.get("className") or row.get("班级")})
    batch_no = f"IMP{uuid.uuid4().hex[:10]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    actor = user or get_current_user_ctx() or {}
    created_by = str(actor.get("userId") or "")
    _MEM[batch_no] = {
        "domain": domain, "rows": ok_rows, "status": status, "tenantId": _tid(),
        "createdBy": created_by, "namespace": namespace or domain.upper(),
    }
    return {"batchNo": batch_no, "status": status, "totalRows": len(rows),
            "okRows": len(ok_rows), "errorRows": len(errors), "errors": errors[:50]}


def peek_batch(batch_no: str) -> dict | None:
    batch = _MEM.get(batch_no)
    if not batch or batch.get("tenantId") != _tid():
        return None
    return {"domain": batch.get("domain"), "status": batch.get("status"),
            "createdBy": batch.get("createdBy")}


def assert_confirm_allowed(user: dict, batch_no: str, auth) -> None:
    batch = _MEM.get(batch_no)
    if not batch or batch.get("tenantId") != _tid():
        raise not_found("导入批次不存在或已过期，请重新校验")
    assert_import_batch_owner(user, batch.get("createdBy"), auth.import_perm)


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
