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
    "student-affairs": ("studentNo", "", "", "学号"),
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
    from app.models import AffairsAuditTrail, StudentProfile
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
    if domain == "student-affairs":
        return _dry_run_student_affairs(rows, namespace=namespace, user=user)
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
    if batch["domain"] == "student-affairs":
        result = _confirm_student_affairs(batch["rows"])
        batch["status"] = "SUCCESS"
        return {"batchNo": batch_no, "status": "SUCCESS", **result}
    create = _svc(DOMAINS[batch["domain"]][1])
    inserted = 0
    for r in batch["rows"]:
        create({k: v for k, v in r.items() if v is not None})
        inserted += 1
    batch["status"] = "SUCCESS"
    return {"batchNo": batch_no, "status": "SUCCESS", "insertedRows": inserted}


_AFFAIRS_HISTORY_TYPES = {
    "DIFFICULT", "FUNDING", "DISCIPLINE", "DORM",
    "ORG_CADRE", "LEAGUE",
}


def _dry_run_student_affairs(rows, *, namespace=None, user=None):
    from app.models import StudentProfile
    if len(rows) > MAX_IMPORT_ROWS:
        raise AppException("VALIDATION_ERROR", f"单次导入不能超过 {MAX_IMPORT_ROWS} 行")
    db = get_sessionmaker()()
    try:
        students = {str(no): int(sid) for no, sid in db.execute(select(
            StudentProfile.student_no, StudentProfile.id
        ).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )).all()}
        imported = set(db.scalars(select(AffairsAuditTrail.detail).where(
            AffairsAuditTrail.tenant_id == _tid(),
            AffairsAuditTrail.biz_type.like("HISTORY_IMPORT_%"),
            AffairsAuditTrail.action == "IMPORT",
            AffairsAuditTrail.is_deleted.is_(False),
        )).all())
    finally:
        db.close()
    ok_rows, errors, seen = [], [], set()
    for index, raw in enumerate(rows, start=2):
        row = dict(raw or {})
        student_no = str(row.get("studentNo") or row.get("学号") or "").strip()
        biz_type = str(row.get("bizType") or row.get("业务类型") or "").strip().upper()
        natural_key = str(row.get("historyNo") or row.get("历史编号") or "").strip()
        if biz_type not in _AFFAIRS_HISTORY_TYPES:
            errors.append({"rowIndex": index, "field": "bizType", "rawValue": biz_type,
                           "message": f"业务类型须为 {sorted(_AFFAIRS_HISTORY_TYPES)}"})
            continue
        if student_no not in students:
            errors.append({"rowIndex": index, "field": "studentNo", "rawValue": student_no,
                           "message": "学号没有学籍主档"})
            continue
        if not natural_key:
            errors.append({"rowIndex": index, "field": "historyNo", "rawValue": "",
                           "message": "历史编号必填（用于导入幂等与对账）"})
            continue
        if f"historyNo={natural_key}" in imported:
            errors.append({"rowIndex": index, "field": "historyNo", "rawValue": natural_key,
                           "message": "该历史编号已成功导入"})
            continue
        dedup = (biz_type, natural_key)
        if dedup in seen:
            errors.append({"rowIndex": index, "field": "historyNo", "rawValue": natural_key,
                           "message": "文件内历史编号重复"})
            continue
        required = {
            "DIFFICULT": "batchId", "FUNDING": "batchId", "DORM": "bedId",
            "ORG_CADRE": "orgId",
        }.get(biz_type)
        if required and not row.get(required):
            errors.append({"rowIndex": index, "field": required, "rawValue": "",
                           "message": f"{biz_type} 历史迁移必须提供 {required}"})
            continue
        seen.add(dedup)
        row.update({"studentNo": student_no, "studentId": students[student_no],
                    "bizType": biz_type, "historyNo": natural_key})
        ok_rows.append(row)
    batch_no = f"IMP{uuid.uuid4().hex[:10]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    actor = user or get_current_user_ctx() or {}
    _MEM[batch_no] = {"domain": "student-affairs", "rows": ok_rows, "status": status,
                      "tenantId": _tid(), "createdBy": str(actor.get("userId") or ""),
                      "namespace": namespace or "STUDENT_AFFAIRS_HISTORY"}
    return {"batchNo": batch_no, "status": status, "totalRows": len(rows),
            "okRows": len(ok_rows), "errorRows": len(errors), "errors": errors[:50],
            "reconciliation": {"acceptedHistoryNos": [r["historyNo"] for r in ok_rows]}}


def _confirm_student_affairs(rows):
    """Write the whole history batch in one transaction; any row failure rolls all rows back."""
    from datetime import datetime
    from app.models import (AffairsAuditTrail, AffairsLeagueDev, AffairsLeagueDevStage,
                            AffairsOrgPosition, AidApply, DisciplineCase, DormBed,
                            FundingApplication)

    db = get_sessionmaker()()
    inserted, ids = 0, []
    try:
        for row in rows:
            raw_actor = str((get_current_user_ctx() or {}).get("userId") or "").removeprefix("db-")
            common = {"tenant_id": _tid(), "created_by": int(raw_actor) if raw_actor.isdigit() else None}
            kind, sid = row["bizType"], int(row["studentId"])
            if kind == "DIFFICULT":
                obj = AidApply(**common, batch_id=int(row["batchId"]), student_id=sid,
                               apply_level=row.get("level"), final_level=row.get("level"),
                               statement=row.get("remark"), status=row.get("status") or "APPROVED")
            elif kind == "FUNDING":
                obj = FundingApplication(**common, batch_id=int(row["batchId"]), student_id=sid,
                                         project_type=row.get("projectType"),
                                         amount=row.get("amount"), statement=row.get("remark"),
                                         status=row.get("status") or "GRANTED")
            elif kind == "DISCIPLINE":
                obj = DisciplineCase(**common, student_id=sid, disc_type=row.get("discType") or "WARNING",
                                     reason=row.get("reason"), doc_no=row.get("docNo"),
                                     status=row.get("status") or "EFFECTIVE")
            elif kind == "DORM":
                obj = db.get(DormBed, int(row["bedId"]))
                if not obj or obj.tenant_id != _tid() or obj.is_deleted or (obj.student_id and obj.student_id != sid):
                    raise AppException("DATA_CONFLICT", f"床位 {row['bedId']} 不存在或已占用")
                obj.student_id, obj.status, obj.occupied_at = sid, "OCCUPIED", datetime.utcnow()
            elif kind == "ORG_CADRE":
                obj = AffairsOrgPosition(**common, org_id=int(row["orgId"]), student_id=sid,
                                         position=str(row.get("position") or "成员"),
                                         term_code=row.get("termCode"),
                                         status=row.get("status") or "ACTIVE")
            else:
                obj = AffairsLeagueDev(**common, student_id=sid, dev_type=row.get("devType") or "PARTY",
                                       current_stage=row.get("stage") or "APPLICANT",
                                       branch_name=row.get("branchName"),
                                       status=row.get("status") or "ONGOING")
            if kind != "DORM":
                db.add(obj)
            db.flush()
            if kind == "LEAGUE":
                db.add(AffairsLeagueDevStage(
                    tenant_id=_tid(), dev_id=obj.id, to_stage=obj.current_stage,
                    operator="历史迁移", remark=f"historyNo={row['historyNo']}"))
            db.add(AffairsAuditTrail(
                tenant_id=_tid(), biz_type=f"HISTORY_IMPORT_{kind}", biz_id=obj.id,
                action="IMPORT", operator=str((get_current_user_ctx() or {}).get("realName") or "未记录"),
                detail=f"historyNo={row['historyNo']}", occurred_at=datetime.utcnow()))
            ids.append({"historyNo": row["historyNo"], "bizType": kind, "recordId": str(obj.id)})
            inserted += 1
        db.commit()
        return {"insertedRows": inserted, "reconciliation": {"records": ids}}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
