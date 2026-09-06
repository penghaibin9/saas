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
    "dorm": ("bedNo", "", "", "床号"),
    "campus-service": ("studentNo", "campus_service_service.create_student",
                       "campus_service_service.list_students", "学号"),
    "academic": ("studentNo", "academic_service.create_student",
                 "academic_service.list_students", "学号"),
    "employment": ("studentNo", "employment_service.create_student",
                   "employment_service.list_students", "学号"),
    "student-affairs": ("studentNo", "", "", "学号"),
}

# 单一命名空间：batch_no 全局唯一（uuid 生成），peek_batch 在拿到 domain 之前就要能按
# batch_no 单独查到批次，故不像 migration_import_service 那样按域分命名空间。
_NAMESPACE = "DOMAIN_IMPORT"
# One ordinary intake can exceed ten thousand students.  Keep the import a single
# governed dry-run/confirm operation instead of forcing operators to split files.
MAX_IMPORT_ROWS = 20_000


def _orientation_authority_catalog() -> dict:
    """Load exact-code orientation authorities once for one Dry-Run.

    Codes are deliberately not collapsed to a single dict entry: duplicate
    master codes must surface as an error instead of silently selecting one.
    """
    from collections import defaultdict
    from app.models import College, Major, OrientationBatch, OrientationStudent, SchoolClass

    db = get_sessionmaker()()
    try:
        batches, colleges, majors, classes = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        for row in db.scalars(select(OrientationBatch).where(
                OrientationBatch.tenant_id == _tid(), OrientationBatch.is_deleted.is_(False))).all():
            batches[str(row.batch_no or "").strip()].append(row)
        for row in db.scalars(select(College).where(
                College.tenant_id == _tid(), College.is_deleted.is_(False))).all():
            if str(row.code or "").strip():
                colleges[str(row.code).strip()].append(row)
        for row in db.scalars(select(Major).where(
                Major.tenant_id == _tid(), Major.is_deleted.is_(False))).all():
            if str(row.code or "").strip():
                majors[(int(row.college_id), str(row.code).strip())].append(row)
        for row in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False))).all():
            if str(row.class_code or "").strip():
                classes[(int(row.major_id), str(row.class_code).strip())].append(row)
        source_keys = {(int(batch_id), str(source_id)) for batch_id, source_id in db.execute(select(
            OrientationStudent.batch_id, OrientationStudent.source_record_id
        ).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.source_type == "DOMAIN_IMPORT",
        )).all()}
        return {"batches": batches, "colleges": colleges, "majors": majors,
                "classes": classes, "sourceKeys": source_keys}
    finally:
        db.close()


def _one(catalog: dict, key, field: str, label: str):
    rows = catalog.get(key, [])
    if not rows:
        return None, {"field": field, "rawValue": key[-1] if isinstance(key, tuple) else key,
                      "message": f"{label}不存在或不属于本校"}
    if len(rows) > 1:
        return None, {"field": field, "rawValue": key[-1] if isinstance(key, tuple) else key,
                      "message": f"{label}在本校存在重复代码，禁止自动选择，请先修复组织主数据"}
    return rows[0], None


def _prepare_orientation_row(raw: dict, catalog: dict) -> tuple[dict | None, dict | None]:
    batch_no = str(raw.get("batchNo") or raw.get("迎新批次编号") or "").strip()
    college_code = str(raw.get("collegeCode") or raw.get("学院代码") or "").strip()
    major_code = str(raw.get("majorCode") or raw.get("专业代码") or "").strip()
    class_code = str(raw.get("classCode") or raw.get("班级代码") or "").strip()
    for field, value, label in (
        ("batchNo", batch_no, "迎新批次编号"), ("collegeCode", college_code, "学院代码"),
        ("majorCode", major_code, "专业代码"), ("classCode", class_code, "班级代码"),
    ):
        if not value:
            return None, {"field": field, "rawValue": "", "message": f"{label}必填"}

    batch, error = _one(catalog["batches"], batch_no, "batchNo", "迎新批次")
    if error:
        return None, error
    if batch.status == "CLOSED":
        return None, {"field": "batchNo", "rawValue": batch_no, "message": "已结束迎新批次不可再导入名单"}
    college, error = _one(catalog["colleges"], college_code, "collegeCode", "学院代码")
    if error:
        return None, error
    major, error = _one(catalog["majors"], (int(college.id), major_code), "majorCode", "该学院下的专业代码")
    if error:
        return None, error
    school_class, error = _one(catalog["classes"], (int(major.id), class_code), "classCode", "该专业下的班级代码")
    if error:
        return None, error

    admission_no = str(raw.get("admissionNo") or raw.get("录取编号") or "").strip()
    candidate_no = str(raw.get("candidateNo") or raw.get("候选人编号") or "").strip()
    source_record_id = candidate_no or admission_no
    source_key = (int(batch.id), source_record_id)
    if source_key in catalog["sourceKeys"]:
        return None, {"field": "candidateNo", "rawValue": source_record_id,
                      "message": "该批次来源记录已成功导入"}
    return {
        "name": str(raw.get("name") or raw.get("姓名") or "").strip(),
        "admissionNo": admission_no,
        "studentNo": str(raw.get("studentNo") or raw.get("学号") or "").strip(),
        "batchId": int(batch.id),
        "collegeId": int(college.id), "collegeName": college.college_name,
        "majorId": int(major.id), "majorName": major.major_name,
        "classId": int(school_class.id), "className": school_class.class_name,
        "gender": raw.get("gender") or raw.get("性别"),
        "idCard": raw.get("idCard") or raw.get("身份证号"),
        "phone": raw.get("phone") or raw.get("手机号"),
        "grade": raw.get("grade") or raw.get("年级"),
        "origin": raw.get("origin") or raw.get("生源地"),
        "admissionType": raw.get("admissionType") or raw.get("录取类型"),
        "sourceType": "DOMAIN_IMPORT", "sourceRecordId": source_record_id,
    }, None


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
    if domain == "dorm":
        from app.services import dorm_resource_import_service
        return dorm_resource_import_service.dry_run(
            _tid(), rows, namespace=_NAMESPACE, user=user,
        )
    key_field, _, list_path, key_label = DOMAINS[domain]
    existing = _existing_keys(domain, list_path, key_field)
    known_master = _master_student_nos(domain)
    orientation_catalog = _orientation_authority_catalog() if domain == "orientation" else None
    ok_rows, errors, seen, seen_sources = [], [], set(), set()
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
        if domain == "orientation":
            normalized, error = _prepare_orientation_row(row, orientation_catalog)
            if error:
                errors.append({"rowIndex": i, **error})
                continue
            source_key = (normalized["batchId"], normalized["sourceRecordId"])
            if source_key in seen_sources:
                errors.append({"rowIndex": i, "field": "candidateNo",
                               "rawValue": normalized["sourceRecordId"],
                               "message": "批次内来源编号在文件中重复"})
                continue
            seen_sources.add(source_key)
            seen.add(key)
            ok_rows.append(normalized)
        else:
            seen.add(key)
            ok_rows.append({"name": name, key_field: key, "className": row.get("className") or row.get("班级")})
    batch_no = f"IMP{uuid.uuid4().hex[:10]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    actor = user or get_current_user_ctx() or {}
    created_by = str(actor.get("userId") or "")
    from app.services import shared_import_batch_service as shared_batches
    # 持久化到共享 MySQL 批次表（跨进程/跨实例可见，服务重启不丢）：C29 止血——
    # 之前用进程内 _MEM 存批次，worker A 校验、worker B 确认时若落在不同实例/重启后即
    # 查无此批次；也没有 claim 租约，重复点确认会重复写。
    shared_batches.create(_tid(), _NAMESPACE, batch_no, status,
                          {"domain": domain, "rows": ok_rows}, errors=errors,
                          operator_key=created_by)
    return {"batchNo": batch_no, "status": status, "totalRows": len(rows),
            "okRows": len(ok_rows), "errorRows": len(errors), "errors": errors[:50],
            "errorWorkbookUrl": (
                f"/api/v1/import/domain/orientation/batches/{batch_no}/errors.xlsx"
                if domain == "orientation" and errors else None
            )}


def peek_batch(batch_no: str) -> dict | None:
    from app.services import shared_import_batch_service as shared_batches
    try:
        row = shared_batches.get(_tid(), _NAMESPACE, batch_no)
    except AppException:
        return None
    payload = row.get("payload") or {}
    return {"domain": payload.get("domain"), "status": row.get("status"),
            "createdBy": row.get("operatorKey")}


def assert_confirm_allowed(user: dict, batch_no: str, auth) -> None:
    meta = peek_batch(batch_no)
    if not meta:
        raise not_found("导入批次不存在或已过期，请重新校验")
    assert_import_batch_owner(user, meta.get("createdBy"), auth.import_perm)


def _confirm_master_domain_rows(domain: str, rows: list[dict]) -> int:
    """一批行在同一个事务/同一个会话内写入：任一行失败整批 rollback，不留半成品台账。"""
    from app.services import db_service
    create = _svc(DOMAINS[domain][1])
    db = db_service.session()
    try:
        inserted = 0
        for r in rows:
            create({k: v for k, v in r.items() if v is not None}, db=db)
            inserted += 1
        db.commit()
        return inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def confirm(batch_no: str) -> dict:
    from app.services import shared_import_batch_service as shared_batches
    payload, claim_token, already_done = shared_batches.claim(
        _tid(), _NAMESPACE, batch_no, required_status="DRY_RUN_PASSED")
    if already_done:
        return payload
    domain = payload.get("domain")
    rows = payload.get("rows") or []
    try:
        if domain == "student-affairs":
            result = _confirm_student_affairs(rows)
            public_result = {"batchNo": batch_no, "status": "SUCCESS", **result}
        elif domain == "dorm":
            from app.services import dorm_resource_import_service
            result = dorm_resource_import_service.confirm(
                _tid(), rows, batch_no=batch_no, claim_token=claim_token,
            )
            public_result = {"batchNo": batch_no, "status": "SUCCESS", **result}
        else:
            inserted = _confirm_master_domain_rows(domain, rows)
            public_result = {"batchNo": batch_no, "status": "SUCCESS", "insertedRows": inserted}
    except Exception as exc:
        shared_batches.fail(_tid(), _NAMESPACE, batch_no, claim_token, str(exc), retryable=True)
        raise
    shared_batches.finish(_tid(), _NAMESPACE, batch_no, claim_token, public_result)
    return public_result


_AFFAIRS_HISTORY_TYPES = {
    "DIFFICULT", "FUNDING", "DISCIPLINE", "DORM",
    "ORG_CADRE", "LEAGUE",
}


def _dry_run_student_affairs(rows, *, namespace=None, user=None):
    from app.models import AffairsAuditTrail, StudentProfile
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
    from app.services import shared_import_batch_service as shared_batches
    shared_batches.create(_tid(), _NAMESPACE, batch_no, status,
                          {"domain": "student-affairs", "rows": ok_rows}, errors=errors,
                          operator_key=str(actor.get("userId") or ""))
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
