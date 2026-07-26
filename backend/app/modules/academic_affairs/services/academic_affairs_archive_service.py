"""教务学期归档。

归档批次 → 语义完整性检查 → 学期封存 → 水印导出/下载审计。
完整性不再以“记录数 > 0”代替业务完成；整体 force 跳过全部门禁已停用。
现有表、导出格式和写保护继续复用，不建立第二套归档事实。
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_DOMAINS = [
    ("STUDENT_STATUS", "学籍"),
    ("REGISTRATION", "注册"),
    ("STATUS_CHANGE", "异动"),
    ("PROGRAM", "培养方案"),
    ("TEACHING_TASK", "教学任务"),
    ("SCHEDULE", "课表"),
    ("EXAM", "考务"),
    ("GRADE", "成绩"),
    ("GRADUATION", "毕业资格"),
]


def _bad(message):
    return AppException("VALIDATION_ERROR", message)


def _invalid(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type="AA_ARCHIVE", biz_id=biz_id, action=action,
        operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow(),
    ))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理教务归档")


# ═══════════ 学期写保护 ═══════════

def guard_term_writable(db, term_id) -> None:
    if not term_id:
        return
    from app.models import AaTerm
    try:
        tid = int(term_id)
    except (TypeError, ValueError):
        return
    term = db.get(AaTerm, tid)
    if term and term.tenant_id == _tid() and term.status == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该学期已归档封存，禁止修改", http_status=409)


def guard_term_writable_current(db) -> None:
    """无强 term_id 外键的旧写入口，按当前学期做最低限度封存保护。"""
    from app.models import AaTerm
    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    )).first()
    if term and term.status == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "当前学期已归档封存，禁止修改", http_status=409)


# ═══════════ 语义完整性规则 ═══════════

def _result(count: int, passed: bool, remark: str) -> dict:
    return {"recordCount": int(count or 0), "present": bool(passed), "remark": remark}


def _evaluate_student_status(db, college_ids=None):
    from app.models import StudentProfile
    query = db.query(StudentProfile).filter(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
    if college_ids:
        query = query.filter(StudentProfile.college_id.in_(college_ids))
    count = query.count()
    return _result(count, count > 0, "已存在学生主档" if count else "无学生主档，不能形成教务归档")


def _evaluate_registration(db, term_id):
    from app.models import AaRegistrationBatch, AaRegistrationException
    query = db.query(AaRegistrationBatch).filter(
        AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.is_deleted.is_(False))
    if term_id:
        query = query.filter(AaRegistrationBatch.term_id == term_id)
    rows = query.all()
    if not rows:
        return _result(0, False, "本学期没有注册批次")
    unfinished = [r for r in rows if str(r.status or "").upper() not in {"CLOSED", "ARCHIVED"}]
    batch_ids = [r.id for r in rows]
    open_exceptions = db.query(AaRegistrationException).filter(
        AaRegistrationException.tenant_id == _tid(),
        AaRegistrationException.batch_id.in_(batch_ids),
        AaRegistrationException.status == "OPEN",
        AaRegistrationException.is_deleted.is_(False),
    ).count() if batch_ids else 0
    passed = not unfinished and open_exceptions == 0
    remark = ("注册批次已关闭且无未处理异常" if passed else
              f"未关闭批次 {len(unfinished)} 个，未处理注册异常 {open_exceptions} 条")
    return _result(len(rows), passed, remark)


def _evaluate_status_change(db, term_code):
    """异动无记录不是缺失；只阻断本学期明确关联的在途异动。"""
    from app.models import AaStatusChange
    query = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False))
    if term_code:
        query = query.filter(AaStatusChange.term_code == term_code)
    rows = query.all()
    in_flight = [r for r in rows if str(r.status or "").upper() in {
        "DRAFT", "SUBMITTED", "IN_REVIEW", "APPROVED", "RETURNED",
    }]
    passed = not in_flight
    remark = ("无在途学籍异动" if passed else f"仍有 {len(in_flight)} 条学籍异动未生效/未关闭")
    if not rows and term_code:
        remark += "；历史异动缺少term_code的记录无法按学期精确核验，已登记为兼容欠账"
    return _result(len(rows), passed, remark)


def _evaluate_program(db):
    from app.models import AaProgram, AaProgramBinding
    programs = db.query(AaProgram).filter(
        AaProgram.tenant_id == _tid(), AaProgram.status == "ENABLED",
        AaProgram.is_deleted.is_(False)).all()
    if not programs:
        return _result(0, False, "没有已启用培养方案")
    ids = [p.id for p in programs]
    bindings = db.query(AaProgramBinding).filter(
        AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id.in_(ids),
        AaProgramBinding.status == "ACTIVE", AaProgramBinding.is_deleted.is_(False)).count()
    passed = bindings > 0
    return _result(len(programs), passed,
                   f"已启用方案 {len(programs)} 个、有效绑定 {bindings} 条" if passed else
                   "存在已启用方案，但没有任何有效专业年级/班级绑定")


def _evaluate_teaching_task(db, term_id, college_ids=None):
    from app.models import AaTeachingTaskBatch, AaTeachingTask
    query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False))
    if term_id:
        query = query.filter(AaTeachingTaskBatch.term_id == term_id)
    if college_ids:
        query = query.filter(AaTeachingTaskBatch.college_id.in_(college_ids))
    batches = query.all()
    if not batches:
        return _result(0, False, "本学期没有教学任务批次")
    unfinished_batches = [b for b in batches if str(b.status or "").upper() not in {"APPROVED", "ARCHIVED"}]
    batch_ids = [b.id for b in batches]
    unfinished_tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id.in_(batch_ids),
        AaTeachingTask.status.in_(["PENDING_ASSIGN", "ASSIGNED", "REJECTED_BY_TEACHER", "TEACHER_CONFIRMED"]),
        AaTeachingTask.is_deleted.is_(False),
    ).count()
    passed = not unfinished_batches and unfinished_tasks == 0
    remark = ("教学任务批次已审核完成" if passed else
              f"未完成批次 {len(unfinished_batches)} 个，未收口任务 {unfinished_tasks} 条")
    return _result(len(batches), passed, remark)


def _evaluate_schedule(db, term_id, college_ids=None):
    from app.models import AaScheduleBatch
    query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.is_deleted.is_(False))
    if term_id:
        query = query.filter(AaScheduleBatch.term_id == term_id)
    if college_ids:
        query = query.filter(AaScheduleBatch.college_id.in_(college_ids))
    rows = query.all()
    published = [r for r in rows if str(r.status or "").upper() == "PUBLISHED"]
    in_flight = [r for r in rows if str(r.status or "").upper() == "PRE_PUBLISHED"]
    passed = bool(published) and not in_flight
    remark = (f"已发布课表 {len(published)} 个" if passed else
              f"已发布课表 {len(published)} 个，仍有预发布批次 {len(in_flight)} 个")
    if not rows:
        remark = "本学期没有课表批次"
    return _result(len(rows), passed, remark)


def _evaluate_exam(db, term_id):
    from app.models import AaExamBatch
    query = db.query(AaExamBatch).filter(
        AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False))
    if term_id:
        query = query.filter(AaExamBatch.term_id == term_id)
    rows = query.all()
    if not rows:
        return _result(0, False, "本学期没有考务批次")
    unfinished = [r for r in rows if str(r.status or "").upper() not in {"FINISHED", "ARCHIVED"}]
    passed = not unfinished
    return _result(len(rows), passed,
                   "考务批次均已结束" if passed else f"仍有 {len(unfinished)} 个考务批次未结束")


def _evaluate_grade(db, term_code):
    from app.models import AaGradeTask, AaGradeRecheck
    query = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False))
    if term_code:
        query = query.filter(AaGradeTask.term_code == term_code)
    rows = query.all()
    if not rows:
        return _result(0, False, "本学期没有成绩任务")
    unfinished = [r for r in rows if str(r.status or "").upper() not in {"PUBLISHED", "ARCHIVED"}]
    task_ids = [r.id for r in rows]
    active_rechecks = 0
    if task_ids:
        # 复查表按 acad_grade_id 关联，不一定能反查task；现阶段至少阻断租户内所有在途复查，避免错误封存。
        active_rechecks = db.query(AaGradeRecheck).filter(
            AaGradeRecheck.tenant_id == _tid(),
            AaGradeRecheck.status.in_(["SUBMITTED", "TEACHER_REVIEW", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"]),
            AaGradeRecheck.is_deleted.is_(False),
        ).count()
    passed = not unfinished and active_rechecks == 0
    return _result(len(rows), passed,
                   "成绩任务均已发布且无在途复查" if passed else
                   f"未发布/未归档成绩任务 {len(unfinished)} 个，在途复查 {active_rechecks} 条")


def _evaluate_graduation(db):
    """非毕业学期没有毕业审核批次不阻断；一旦存在批次则必须收口。"""
    from app.models import AaGraduationAuditBatch
    rows = db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False)).all()
    if not rows:
        return _result(0, True, "当前无毕业审核批次（非阻断）")
    unfinished = [r for r in rows if str(r.status or "").upper() != "ARCHIVED"]
    passed = not unfinished
    return _result(len(rows), passed,
                   "毕业审核批次均已归档" if passed else f"仍有 {len(unfinished)} 个毕业审核批次未归档")


def _evaluate_domains(db, term_id, term_code, college_ids=None) -> dict[str, dict]:
    checks = {
        "STUDENT_STATUS": lambda: _evaluate_student_status(db, college_ids),
        "REGISTRATION": lambda: _evaluate_registration(db, term_id),
        "STATUS_CHANGE": lambda: _evaluate_status_change(db, term_code),
        "PROGRAM": lambda: _evaluate_program(db),
        "TEACHING_TASK": lambda: _evaluate_teaching_task(db, term_id, college_ids),
        "SCHEDULE": lambda: _evaluate_schedule(db, term_id, college_ids),
        "EXAM": lambda: _evaluate_exam(db, term_id),
        "GRADE": lambda: _evaluate_grade(db, term_code),
        "GRADUATION": lambda: _evaluate_graduation(db),
    }
    results = {}
    for code, _label in _DOMAINS:
        try:
            results[code] = checks[code]()
        except Exception as exc:  # 单域隔离，错误本身是阻断，不伪装缺记录或成功
            results[code] = _result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


# ═══════════ 批次 ═══════════

def _batch_dto(batch, items=None):
    data = {
        "batchId": str(batch.id), "batchName": batch.batch_name,
        "termId": str(batch.term_id) if batch.term_id else None,
        "termCode": batch.term_code, "status": batch.status,
        "missingCount": batch.missing_count, "checkedAt": _iso(batch.checked_at),
        "archivedAt": _iso(batch.archived_at),
    }
    if items is not None:
        data["items"] = items
    return data


def _get_batch(db, batch_id):
    from app.models import AaArchiveBatch
    batch = db.query(AaArchiveBatch).filter(
        AaArchiveBatch.id == batch_id, AaArchiveBatch.tenant_id == _tid(),
        AaArchiveBatch.is_deleted.is_(False)).first()
    if not batch:
        raise not_found("归档批次不存在")
    return batch


def create_batch(user, body):
    from app.models import AaArchiveBatch, AaTerm
    with session() as db:
        _require_school(_ctx(user, db))
        term_id = int(body.termId) if getattr(body, "termId", None) else None
        term_code = None
        if term_id:
            term = db.query(AaTerm).filter(AaTerm.id == term_id, AaTerm.tenant_id == _tid()).first()
            if not term:
                raise not_found("学期不存在")
            term_code = f"{term.year_code}-{term.term_no}"
            duplicate = db.query(AaArchiveBatch).filter(
                AaArchiveBatch.tenant_id == _tid(), AaArchiveBatch.term_id == term_id,
                AaArchiveBatch.is_deleted.is_(False)).first()
            if duplicate:
                raise _invalid("该学期已存在归档批次")
        batch = AaArchiveBatch(
            tenant_id=_tid(),
            batch_name=(getattr(body, "batchName", None) or f"{term_code or ''}教务归档").strip(),
            term_id=term_id, term_code=term_code, status="DRAFT",
        )
        db.add(batch)
        db.flush()
        _audit(db, batch.id, "ARCHIVE_BATCH_CREATE", batch.batch_name)
        db.commit()
        return _batch_dto(batch)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaArchiveBatch
    with session() as db:
        _ctx(user, db)
        query = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.tenant_id == _tid(), AaArchiveBatch.is_deleted.is_(False))
        if status:
            query = query.filter(AaArchiveBatch.status == status)
        rows = query.order_by(AaArchiveBatch.id.desc()).all()
        return [_batch_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def _items_dto(db, batch_id):
    from app.models import AaArchiveItem
    rows = db.query(AaArchiveItem).filter(
        AaArchiveItem.batch_id == batch_id, AaArchiveItem.tenant_id == _tid()
    ).order_by(AaArchiveItem.id).all()
    return [{
        "domain": row.domain, "domainLabel": row.domain_label,
        "recordCount": row.record_count, "present": row.present, "remark": row.remark,
    } for row in rows]


def get_batch(user, batch_id):
    with session() as db:
        _ctx(user, db)
        batch = _get_batch(db, batch_id)
        return _batch_dto(batch, items=_items_dto(db, batch.id))


def run_check(user, batch_id):
    """按业务状态执行语义完整性检查并持久化结果。"""
    from app.models import AaArchiveItem
    with session() as db:
        _require_school(_ctx(user, db))
        batch = _get_batch(db, batch_id)
        if batch.status in ("ARCHIVED", "CANCELLED"):
            raise _invalid("已归档/已取消批次不可再检查")
        results = _evaluate_domains(db, batch.term_id, batch.term_code)
        db.query(AaArchiveItem).filter(
            AaArchiveItem.batch_id == batch.id,
            AaArchiveItem.tenant_id == _tid(),
        ).delete(synchronize_session=False)
        missing = 0
        for code, label in _DOMAINS:
            result = results[code]
            if not result["present"]:
                missing += 1
            db.add(AaArchiveItem(
                tenant_id=_tid(), batch_id=batch.id, domain=code, domain_label=label,
                record_count=result["recordCount"], present=result["present"],
                remark=result["remark"],
            ))
        batch.missing_count = missing
        batch.checked_at = datetime.utcnow()
        batch.status = "READY" if missing == 0 else "MISSING_ITEMS"
        _audit(db, batch.id, "ARCHIVE_CHECK", f"语义完整性检查 阻断{missing}域")
        db.commit()
        return _batch_dto(batch, items=_items_dto(db, batch.id))


def confirm_archive(user, batch_id, force=False):
    """仅 READY 批次可归档；兼容参数 force 不再允许整体绕过门禁。"""
    from app.models import AaTerm
    with session() as db:
        _require_school(_ctx(user, db))
        batch = _get_batch(db, batch_id)
        if batch.status == "ARCHIVED":
            return _batch_dto(batch)
        if batch.status == "MISSING_ITEMS":
            raise _invalid(
                f"仍有 {batch.missing_count} 个业务域未满足归档规则。整体强制归档已停用，请逐项处理后重新检查")
        if batch.status != "READY":
            raise _invalid("仅语义完整性检查通过（READY）的批次可确认归档")
        batch.status = "ARCHIVED"
        batch.archived_at = datetime.utcnow()
        if batch.term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == batch.term_id, AaTerm.tenant_id == _tid()).first()
            if term:
                term.status = "ARCHIVED"
        _audit(db, batch.id, "ARCHIVE_CONFIRM", "语义检查通过，确认归档并封存学期")
        db.commit()
        return _batch_dto(batch)


def unfreeze(user, batch_id, reason):
    from app.models import AaTerm
    with session() as db:
        ctx = _ctx(user, db)
        _require_school(ctx)
        if _role() != "SCHOOL_ADMIN":
            raise no_data_scope("仅学校管理员可特批解冻归档")
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise _bad("解冻原因必填且不少于5字")
        batch = _get_batch(db, batch_id)
        if batch.status != "ARCHIVED":
            raise _invalid("仅已归档批次可解冻")
        batch.status = "DRAFT"
        batch.archived_at = None
        if batch.term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == batch.term_id, AaTerm.tenant_id == _tid()).first()
            if term:
                term.status = "PUBLISHED"
        _audit(db, batch.id, "ARCHIVE_UNFREEZE", f"特批解冻：{reason}")
        db.commit()
        return _batch_dto(batch)


def cancel_batch(user, batch_id):
    with session() as db:
        _require_school(_ctx(user, db))
        batch = _get_batch(db, batch_id)
        if batch.status == "ARCHIVED":
            raise _invalid("已归档批次不可取消，请走特批解冻")
        batch.status = "CANCELLED"
        _audit(db, batch.id, "ARCHIVE_CANCEL", "取消批次")
        db.commit()
        return _batch_dto(batch)


# ═══════════ 实时预检 ═══════════

def precheck(user, term_id=None):
    from app.models import AaTerm
    with session() as db:
        ctx = _ctx(user, db)
        if term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == int(term_id), AaTerm.tenant_id == _tid()).first()
            if not term:
                raise not_found("学期不存在")
        else:
            term = db.scalars(select(AaTerm).where(
                AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False))).first()
        term_id_value = term.id if term else None
        term_code_value = f"{term.year_code}-{term.term_no}" if term else None
        college_ids = ctx.college_ids if ctx.scope_type == "COLLEGE" else None
        evaluated = _evaluate_domains(db, term_id_value, term_code_value, college_ids)
        domains = []
        for code, label in _DOMAINS:
            result = evaluated[code]
            domains.append({
                "domain": code, "domainLabel": label,
                "recordCount": result["recordCount"],
                "status": "OK" if result["present"] else "MISSING",
                "note": result["remark"],
            })
        return {
            "termId": str(term_id_value) if term_id_value else None,
            "termCode": term_code_value,
            "scopeNote": ("教学任务、课表、学籍按本院范围检查；其他域仍为全校规则" if college_ids else None),
            "domains": domains,
        }


# 兼容旧调用：返回单域语义检查中的记录数量，不再用于归档是否通过的判定。
def _count_one_domain(db, code, term_id, term_code, college_ids=None):
    return _evaluate_domains(db, term_id, term_code, college_ids).get(code, {}).get("recordCount", 0)


def _count_domains(db, term_id, term_code):
    evaluated = _evaluate_domains(db, term_id, term_code)
    return {code: result["recordCount"] for code, result in evaluated.items()}


# ═══════════ 归档导出 ═══════════

_DOMAIN_COLS = {
    "STUDENT_STATUS": ("学籍档案", ["学号", "姓名", "学籍状态", "班级ID"]),
    "REGISTRATION": ("注册台账", ["批次名称", "注册类型", "状态", "学期ID"]),
    "STATUS_CHANGE": ("学籍异动流水", ["学生ID", "异动类型", "原状态", "新状态", "异动状态"]),
    "PROGRAM": ("培养方案", ["方案名称", "适用年级", "总学分", "状态"]),
    "TEACHING_TASK": ("教学任务批次", ["批次名称", "学院ID", "状态", "生成时间"]),
    "SCHEDULE": ("课表批次", ["批次名称", "学院ID", "状态", "发布时间"]),
    "EXAM": ("考务批次", ["批次名称", "考试类型", "状态", "发布时间"]),
    "GRADE": ("成绩任务", ["课程名称", "班级ID", "状态", "发布时间"]),
    "GRADUATION": ("毕业资格批次", ["批次名称", "毕业年级", "状态", "生成时间"]),
}


def _domain_rows(db, code, term_id, term_code):
    from app.models import (AaExamBatch, AaGradeTask, AaGraduationAuditBatch, AaProgram,
                            AaRegistrationBatch, AaScheduleBatch, AaStatusChange,
                            AaTeachingTaskBatch, StudentProfile)
    tenant = _tid()
    if code == "STUDENT_STATUS":
        rows = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == tenant, StudentProfile.is_deleted.is_(False)).all()
        return [[r.student_no, r.real_name, r.student_status, r.class_id] for r in rows]
    if code == "REGISTRATION":
        query = db.query(AaRegistrationBatch).filter(
            AaRegistrationBatch.tenant_id == tenant, AaRegistrationBatch.is_deleted.is_(False))
        rows = query.filter(AaRegistrationBatch.term_id == term_id).all() if term_id else query.all()
        return [[r.batch_name, r.register_type, r.status, r.term_id] for r in rows]
    if code == "STATUS_CHANGE":
        query = db.query(AaStatusChange).filter(
            AaStatusChange.tenant_id == tenant, AaStatusChange.is_deleted.is_(False))
        rows = query.filter(AaStatusChange.term_code == term_code).all() if term_code else query.all()
        return [[r.student_id, r.change_type, r.from_status, r.to_status, r.status] for r in rows]
    if code == "PROGRAM":
        rows = db.query(AaProgram).filter(
            AaProgram.tenant_id == tenant, AaProgram.is_deleted.is_(False)).all()
        return [[r.program_name, r.grade_year, r.total_credits, r.status] for r in rows]
    if code == "TEACHING_TASK":
        query = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == tenant, AaTeachingTaskBatch.is_deleted.is_(False))
        rows = query.filter(AaTeachingTaskBatch.term_id == term_id).all() if term_id else query.all()
        return [[r.batch_name, r.college_id, r.status, _iso(r.generate_at)] for r in rows]
    if code == "SCHEDULE":
        query = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.tenant_id == tenant, AaScheduleBatch.is_deleted.is_(False))
        rows = query.filter(AaScheduleBatch.term_id == term_id).all() if term_id else query.all()
        return [[r.batch_name, r.college_id, r.status, _iso(r.publish_at)] for r in rows]
    if code == "EXAM":
        query = db.query(AaExamBatch).filter(
            AaExamBatch.tenant_id == tenant, AaExamBatch.is_deleted.is_(False))
        rows = query.filter(AaExamBatch.term_id == term_id).all() if term_id else query.all()
        return [[r.batch_name, r.exam_type, r.status, _iso(r.published_at)] for r in rows]
    if code == "GRADE":
        query = db.query(AaGradeTask).filter(
            AaGradeTask.tenant_id == tenant, AaGradeTask.is_deleted.is_(False))
        rows = query.filter(AaGradeTask.term_code == term_code).all() if term_code else query.all()
        return [[r.course_name, r.class_id, r.status, _iso(r.publish_at)] for r in rows]
    if code == "GRADUATION":
        rows = db.query(AaGraduationAuditBatch).filter(
            AaGraduationAuditBatch.tenant_id == tenant,
            AaGraduationAuditBatch.is_deleted.is_(False)).all()
        return [[r.batch_name, r.grade_year, r.status, _iso(r.generate_at)] for r in rows]
    return []


def _check_export_purpose(purpose):
    if not purpose or len(purpose.strip()) < 5:
        raise _bad("下载用途必填且不少于5字")
    return purpose.strip()


def _watermark(purpose, title):
    ctx = get_current_user_ctx() or {}
    return (f"高校学生全生命周期管理平台 · {title} · "
            f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'} · "
            f"时间：{datetime.utcnow():%Y-%m-%d %H:%M} · 用途：{purpose} · "
            "含学生姓名/学号等敏感字段仅限内部使用")


def _record_export_task(db, row_count, purpose, file_bytes):
    from app.models import ExportTask
    task = ExportTask(
        tenant_id=_tid(), export_mode="ENCRYPTED_ARCHIVE",
        module_code="academic_affairs_archive", row_count=row_count,
        purpose=purpose, file_hash=hashlib.sha256(file_bytes).hexdigest(), status="SUCCESS",
    )
    db.add(task)
    db.flush()
    return task


def export_batch_item(user, batch_id, category, purpose) -> tuple[bytes, str]:
    from app.services.xlsx_util import build_ledger_xlsx
    purpose = _check_export_purpose(purpose)
    if category not in _DOMAIN_COLS:
        raise not_found(f"未知归档物料域：{category}")
    with session() as db:
        _ctx(user, db)
        batch = _get_batch(db, batch_id)
        if batch.status != "ARCHIVED":
            raise _invalid("批次未归档，暂不可下载归档物料")
        title, headers = _DOMAIN_COLS[category]
        rows = _domain_rows(db, category, batch.term_id, batch.term_code)
        content = build_ledger_xlsx(title, headers, rows, watermark=_watermark(purpose, title))
        _record_export_task(db, len(rows), purpose, content)
        _audit(db, batch.id, "ITEM_EXPORT_DOWNLOAD", f"域={category} 用途={purpose[:100]}")
        db.commit()
        return content, f"{category}_batch{batch.id}.xlsx"


def export_batch_all(user, batch_id, purpose) -> tuple[bytes, str]:
    from app.services.xlsx_util import build_ledger_xlsx
    purpose = _check_export_purpose(purpose)
    with session() as db:
        _ctx(user, db)
        batch = _get_batch(db, batch_id)
        if batch.status != "ARCHIVED":
            raise _invalid("批次未归档，暂不可下载归档物料")
        buffer = io.BytesIO()
        total_rows = 0
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for code, _label in _DOMAINS:
                title, headers = _DOMAIN_COLS[code]
                rows = _domain_rows(db, code, batch.term_id, batch.term_code)
                if not rows:
                    continue
                content = build_ledger_xlsx(title, headers, rows, watermark=_watermark(purpose, title))
                archive.writestr(f"{code}_{title}.xlsx", content)
                total_rows += len(rows)
        content = buffer.getvalue()
        _record_export_task(db, total_rows, purpose, content)
        _audit(db, batch.id, "BATCH_EXPORT_DOWNLOAD", f"打包下载 用途={purpose[:100]}")
        db.commit()
        return content, f"archive_batch{batch.id}.zip"


def list_download_log(user, batch_id):
    from app.models import AffairsAuditTrail
    with session() as db:
        _ctx(user, db)
        _get_batch(db, batch_id)
        rows = db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "AA_ARCHIVE",
            AffairsAuditTrail.biz_id == int(batch_id),
            AffairsAuditTrail.action.in_(["ITEM_EXPORT_DOWNLOAD", "BATCH_EXPORT_DOWNLOAD"]),
        ).order_by(AffairsAuditTrail.id.desc()).all()
        return [{
            "operator": row.operator, "roleName": row.role_name,
            "action": row.action, "detail": row.detail,
            "downloadAt": _iso(row.occurred_at),
        } for row in rows]
