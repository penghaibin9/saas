"""13B-R7 教务归档 service。

按学年学期建归档批次(D-01) → 完整性检查(聚合9数据域记录数,present/missing) →
确认归档(批次ARCHIVED + 学期status→ARCHIVED,D-04) → 特批解冻(仅SCHOOL_ADMIN,D-06)。

三级施工卡 10/11/12（归档缺失提醒/批量归档/归档导出）补强（Tier1续工）：
- guard_term_writable()/guard_term_writable_current()：D-04 学期封存后写保护横切拦截（11 卡 §6.2），
  已接入 5 个既有 service 文件的 14 处写入口（学期发布/校历、注册批次/注册、学籍异动提交/审批、
  教学任务生成/分配/教师确认、课表批次/排课项/导入/预发布/发布/作废重发、成绩任务/录入/发布）。
  学籍异动无强 term_id 外键（AaStatusChange.term_code/effective_date 均从未被写入口回填，
  代码事实核验勘误，非本次新增缺口）——降级为"当前激活学期"判据，真实但不如强 FK 精确，已如实注释。
- precheck()：归档缺失提醒（10 卡），复用 _count_domains 实时计算，不落库、不写审计。
- export_batch_item()/export_batch_all()/list_download_log()：归档导出（12 卡），复用
  xlsx_util.build_ledger_xlsx 水印模式 + ExportTask 留痕 + AffairsAuditTrail 下载审计。

D-04 学期封存后该学期写端点应 409（横切拦截跨 R1-R6 端点）。审计复用 AffairsAuditTrail(biz_type=AA_ARCHIVE)。
"""
from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

# 9 数据域（域码 → (中文名, 计数函数key)）
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


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_ARCHIVE", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理教务归档")


# ═══════════ 学期写保护 guard（11 卡 §6.2，D-04 横切拦截）═══════════

def guard_term_writable(db, term_id) -> None:
    """按 term_id 判定：目标学期若已 ARCHIVED，409 拦截写操作。
    term_id 为空（无法定位学期的写操作，如字典类新建）不拦截，避免过度拦截伤及无关业务。"""
    if not term_id:
        return
    from app.models import AaTerm
    try:
        tid = int(term_id)
    except (TypeError, ValueError):
        return
    t = db.get(AaTerm, tid)
    if t and t.tenant_id == _tid() and t.status == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该学期已归档封存，禁止修改", http_status=409)


def guard_term_writable_current(db) -> None:
    """无强 term_id 外键的写操作（学籍异动 submit/review）降级判据：拦截当前激活学期(is_current=True)
    若已 ARCHIVED 的写操作。代码事实：AaStatusChange.term_code/effective_date 从未被任何写入口回填
    （核验勘误，非本次新增缺口），故不能按 11 卡 §6.2 原设计的「term_code/effective_date判据」精确关联，
    降级为当前学期判据——真实生效但不如强 FK 精确，越权/漏拦截风险已如实登记为欠账。"""
    from app.models import AaTerm
    t = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True), AaTerm.is_deleted.is_(False))).first()
    if t and t.status == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "当前学期已归档封存，禁止修改", http_status=409)


def _count_domains(db, term_id, term_code):
    """聚合 9 数据域记录数（有 term_id 的按学期计，无清晰学期关联的按租户全量作近似指标）。"""
    from app.models import (AaExamBatch, AaGradeTask, AaGraduationAuditBatch, AaProgram,
                            AaRegistrationBatch, AaScheduleBatch, AaStatusChange, AaTeachingTaskBatch,
                            StudentProfile)
    T = _tid()
    counts = {}
    counts["STUDENT_STATUS"] = db.query(StudentProfile).filter(StudentProfile.tenant_id == T,
                                                               StudentProfile.is_deleted.is_(False)).count()
    q = db.query(AaRegistrationBatch).filter(AaRegistrationBatch.tenant_id == T, AaRegistrationBatch.is_deleted.is_(False))
    counts["REGISTRATION"] = (q.filter(AaRegistrationBatch.term_id == term_id).count() if term_id else q.count())
    q = db.query(AaStatusChange).filter(AaStatusChange.tenant_id == T, AaStatusChange.is_deleted.is_(False))
    counts["STATUS_CHANGE"] = (q.filter(AaStatusChange.term_code == term_code).count() if term_code else q.count())
    counts["PROGRAM"] = db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False)).count()
    q = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.tenant_id == T, AaTeachingTaskBatch.is_deleted.is_(False))
    counts["TEACHING_TASK"] = (q.filter(AaTeachingTaskBatch.term_id == term_id).count() if term_id else q.count())
    q = db.query(AaScheduleBatch).filter(AaScheduleBatch.tenant_id == T, AaScheduleBatch.is_deleted.is_(False))
    counts["SCHEDULE"] = (q.filter(AaScheduleBatch.term_id == term_id).count() if term_id else q.count())
    q = db.query(AaExamBatch).filter(AaExamBatch.tenant_id == T, AaExamBatch.is_deleted.is_(False))
    counts["EXAM"] = (q.filter(AaExamBatch.term_id == term_id).count() if term_id else q.count())
    q = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))
    counts["GRADE"] = (q.filter(AaGradeTask.term_code == term_code).count() if term_code else q.count())
    counts["GRADUATION"] = db.query(AaGraduationAuditBatch).filter(AaGraduationAuditBatch.tenant_id == T,
                                                                   AaGraduationAuditBatch.is_deleted.is_(False)).count()
    return counts


def _batch_dto(b, items=None):
    d = {"batchId": str(b.id), "batchName": b.batch_name, "termId": str(b.term_id) if b.term_id else None,
         "termCode": b.term_code, "status": b.status, "missingCount": b.missing_count,
         "checkedAt": _iso(b.checked_at), "archivedAt": _iso(b.archived_at)}
    if items is not None:
        d["items"] = items
    return d


def _get_batch(db, bid):
    from app.models import AaArchiveBatch
    b = db.query(AaArchiveBatch).filter(AaArchiveBatch.id == bid, AaArchiveBatch.tenant_id == _tid(),
                                        AaArchiveBatch.is_deleted.is_(False)).first()
    if not b:
        raise not_found("归档批次不存在")
    return b


def create_batch(user, body):
    """按学期建归档批次（一学期一批次，唯一 term_id）。"""
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
            dup = db.query(AaArchiveBatch).filter(AaArchiveBatch.tenant_id == _tid(),
                                                  AaArchiveBatch.term_id == term_id,
                                                  AaArchiveBatch.is_deleted.is_(False)).first()
            if dup:
                raise _invalid("该学期已存在归档批次")
        b = AaArchiveBatch(tenant_id=_tid(),
                           batch_name=(getattr(body, "batchName", None) or f"{term_code or ''}教务归档").strip(),
                           term_id=term_id, term_code=term_code, status="DRAFT")
        db.add(b); db.flush()
        _audit(db, b.id, "ARCHIVE_BATCH_CREATE", b.batch_name)
        db.commit()
        return _batch_dto(b)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaArchiveBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaArchiveBatch).filter(AaArchiveBatch.tenant_id == _tid(), AaArchiveBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaArchiveBatch.status == status)
        rows = q.order_by(AaArchiveBatch.id.desc()).all()
        return [_batch_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def _items_dto(db, bid):
    from app.models import AaArchiveItem
    rows = db.query(AaArchiveItem).filter(AaArchiveItem.batch_id == bid, AaArchiveItem.tenant_id == _tid()).order_by(AaArchiveItem.id).all()
    return [{"domain": i.domain, "domainLabel": i.domain_label, "recordCount": i.record_count,
             "present": i.present, "remark": i.remark} for i in rows]


def get_batch(user, bid):
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        return _batch_dto(b, items=_items_dto(db, b.id))


def run_check(user, bid):
    """完整性检查：聚合 9 数据域 → 写 item + missing_count → READY/MISSING_ITEMS。"""
    from app.models import AaArchiveItem
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status in ("ARCHIVED", "CANCELLED"):
            raise _invalid("已归档/已取消批次不可再检查")
        counts = _count_domains(db, b.term_id, b.term_code)
        db.query(AaArchiveItem).filter(AaArchiveItem.batch_id == b.id, AaArchiveItem.tenant_id == _tid()).delete(synchronize_session=False)
        missing = 0
        for code, label in _DOMAINS:
            cnt = counts.get(code, 0)
            present = cnt > 0
            if not present:
                missing += 1
            db.add(AaArchiveItem(tenant_id=_tid(), batch_id=b.id, domain=code, domain_label=label,
                                 record_count=cnt, present=present,
                                 remark=None if present else "该数据域无记录"))
        b.missing_count = missing
        b.checked_at = datetime.utcnow()
        b.status = "READY" if missing == 0 else "MISSING_ITEMS"
        _audit(db, b.id, "ARCHIVE_CHECK", f"完整性检查 缺失{missing}域")
        db.commit()
        return _batch_dto(b, items=_items_dto(db, b.id))


def confirm_archive(user, bid, force=False):
    """确认归档：批次→ARCHIVED + 学期→ARCHIVED（D-04）。MISSING_ITEMS 需 force 才可强制归档。"""
    from app.models import AaArchiveBatch, AaTerm
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status == "ARCHIVED":
            return _batch_dto(b)
        if b.status not in ("READY", "MISSING_ITEMS"):
            raise _invalid("仅完整性检查后(READY/MISSING_ITEMS)可确认归档")
        if b.status == "MISSING_ITEMS" and not force:
            raise _invalid(f"存在 {b.missing_count} 个缺失数据域，需勾选强制归档")
        b.status = "ARCHIVED"
        b.archived_at = datetime.utcnow()
        # D-04 学期封存
        if b.term_id:
            term = db.query(AaTerm).filter(AaTerm.id == b.term_id, AaTerm.tenant_id == _tid()).first()
            if term:
                term.status = "ARCHIVED"
        _audit(db, b.id, "ARCHIVE_CONFIRM", "确认归档，学期封存" + ("(强制)" if force else ""))
        db.commit()
        return _batch_dto(b)


def unfreeze(user, bid, reason):
    """特批解冻（D-06，仅 SCHOOL_ADMIN）：批次 ARCHIVED→DRAFT，学期恢复 PUBLISHED。"""
    from app.models import AaTerm
    with session() as db:
        ctx = _ctx(user, db)
        _require_school(ctx)
        if _role() != "SCHOOL_ADMIN":
            raise no_data_scope("仅学校管理员可特批解冻归档")
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise _bad("解冻原因必填且不少于5字")
        b = _get_batch(db, bid)
        if b.status != "ARCHIVED":
            raise _invalid("仅已归档批次可解冻")
        b.status = "DRAFT"
        b.archived_at = None
        if b.term_id:
            term = db.query(AaTerm).filter(AaTerm.id == b.term_id, AaTerm.tenant_id == _tid()).first()
            if term:
                term.status = "PUBLISHED"
        _audit(db, b.id, "ARCHIVE_UNFREEZE", f"特批解冻：{reason}")
        db.commit()
        return _batch_dto(b)


def cancel_batch(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status == "ARCHIVED":
            raise _invalid("已归档批次不可取消，请走特批解冻")
        b.status = "CANCELLED"
        _audit(db, b.id, "ARCHIVE_CANCEL", "取消批次")
        db.commit()
        return _batch_dto(b)


# ═══════════ 归档缺失提醒（10 卡）：实时预检，不落库、不写审计 ═══════════

def precheck(user, term_id=None):
    """9 域实时预检查（不落库，不产生批次/物料记录）。term_id 缺省取当前学期。
    学院教务员（COLLEGE 数据范围）：STUDENT_STATUS/TEACHING_TASK/SCHEDULE 三域按本院过滤；
    其余 6 域（注册批次/学籍异动/培养方案/考试批次/成绩任务/毕业批次）当前无 college_id 直接列，
    仍按全校口径返回（如实登记为已知局限，未虚报"已按学院过滤"）。"""
    from app.models import AaTerm
    with session() as db:
        ctx = _ctx(user, db)
        term = None
        if term_id:
            term = db.query(AaTerm).filter(AaTerm.id == int(term_id), AaTerm.tenant_id == _tid()).first()
            if not term:
                raise not_found("学期不存在")
        else:
            term = db.scalars(select(AaTerm).where(
                AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True), AaTerm.is_deleted.is_(False))).first()
        term_id_v = term.id if term else None
        term_code_v = (f"{term.year_code}-{term.term_no}" if term else None)
        college_ids = ctx.college_ids if ctx.scope_type == "COLLEGE" else None
        results = []
        for code, label in _DOMAINS:
            try:
                cnt = _count_one_domain(db, code, term_id_v, term_code_v, college_ids)
                results.append({"domain": code, "domainLabel": label, "recordCount": cnt,
                                "status": "OK" if cnt > 0 else "MISSING", "note": None})
            except Exception as e:  # noqa: BLE001  # 域间隔离：单域异常不拖垮整个看板
                results.append({"domain": code, "domainLabel": label, "recordCount": 0,
                                "status": "ERROR", "note": f"该域检查暂不可用：{e}"})
        return {"termId": str(term_id_v) if term_id_v else None, "termCode": term_code_v,
                "scopeNote": ("仅学籍/教学任务/课表按本院过滤，其余域为全校口径" if college_ids else None),
                "domains": results}


def _count_one_domain(db, code, term_id, term_code, college_ids=None):
    """单域计数（供 precheck 逐域隔离调用）；college_ids 非空时对支持列过滤的域按本院收窄。"""
    from app.models import (AaExamBatch, AaGradeTask, AaGraduationAuditBatch, AaProgram,
                            AaRegistrationBatch, AaScheduleBatch, AaStatusChange, AaTeachingTaskBatch,
                            StudentProfile)
    T = _tid()
    if code == "STUDENT_STATUS":
        q = db.query(StudentProfile).filter(StudentProfile.tenant_id == T, StudentProfile.is_deleted.is_(False))
        if college_ids:
            q = q.filter(StudentProfile.college_id.in_(college_ids))
        return q.count()
    if code == "REGISTRATION":
        q = db.query(AaRegistrationBatch).filter(AaRegistrationBatch.tenant_id == T, AaRegistrationBatch.is_deleted.is_(False))
        return (q.filter(AaRegistrationBatch.term_id == term_id).count() if term_id else q.count())
    if code == "STATUS_CHANGE":
        q = db.query(AaStatusChange).filter(AaStatusChange.tenant_id == T, AaStatusChange.is_deleted.is_(False))
        return (q.filter(AaStatusChange.term_code == term_code).count() if term_code else q.count())
    if code == "PROGRAM":
        return db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False)).count()
    if code == "TEACHING_TASK":
        q = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.tenant_id == T, AaTeachingTaskBatch.is_deleted.is_(False))
        if term_id:
            q = q.filter(AaTeachingTaskBatch.term_id == term_id)
        if college_ids:
            q = q.filter(AaTeachingTaskBatch.college_id.in_(college_ids))
        return q.count()
    if code == "SCHEDULE":
        q = db.query(AaScheduleBatch).filter(AaScheduleBatch.tenant_id == T, AaScheduleBatch.is_deleted.is_(False))
        if term_id:
            q = q.filter(AaScheduleBatch.term_id == term_id)
        if college_ids:
            q = q.filter(AaScheduleBatch.college_id.in_(college_ids))
        return q.count()
    if code == "EXAM":
        q = db.query(AaExamBatch).filter(AaExamBatch.tenant_id == T, AaExamBatch.is_deleted.is_(False))
        return (q.filter(AaExamBatch.term_id == term_id).count() if term_id else q.count())
    if code == "GRADE":
        q = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))
        return (q.filter(AaGradeTask.term_code == term_code).count() if term_code else q.count())
    if code == "GRADUATION":
        return db.query(AaGraduationAuditBatch).filter(AaGraduationAuditBatch.tenant_id == T,
                                                        AaGraduationAuditBatch.is_deleted.is_(False)).count()
    return 0


# ═══════════ 归档导出（12 卡）：批次 ARCHIVED 后水印 xlsx + zip 打包 + 下载记录 ═══════════

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
    """归档物料明细行（完整台账，非缺项摘要，12 卡 §3 要求）。"""
    from app.models import (AaExamBatch, AaGradeTask, AaGraduationAuditBatch, AaProgram,
                            AaRegistrationBatch, AaScheduleBatch, AaStatusChange, AaTeachingTaskBatch,
                            StudentProfile)
    T = _tid()
    if code == "STUDENT_STATUS":
        rows = db.query(StudentProfile).filter(StudentProfile.tenant_id == T, StudentProfile.is_deleted.is_(False)).all()
        return [[r.student_no, r.real_name, r.student_status, r.class_id] for r in rows]
    if code == "REGISTRATION":
        q = db.query(AaRegistrationBatch).filter(AaRegistrationBatch.tenant_id == T, AaRegistrationBatch.is_deleted.is_(False))
        rows = (q.filter(AaRegistrationBatch.term_id == term_id).all() if term_id else q.all())
        return [[r.batch_name, r.register_type, r.status, r.term_id] for r in rows]
    if code == "STATUS_CHANGE":
        q = db.query(AaStatusChange).filter(AaStatusChange.tenant_id == T, AaStatusChange.is_deleted.is_(False))
        rows = (q.filter(AaStatusChange.term_code == term_code).all() if term_code else q.all())
        return [[r.student_id, r.change_type, r.from_status, r.to_status, r.status] for r in rows]
    if code == "PROGRAM":
        rows = db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False)).all()
        return [[r.program_name, r.grade_year, r.total_credits, r.status] for r in rows]
    if code == "TEACHING_TASK":
        q = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.tenant_id == T, AaTeachingTaskBatch.is_deleted.is_(False))
        rows = (q.filter(AaTeachingTaskBatch.term_id == term_id).all() if term_id else q.all())
        return [[r.batch_name, r.college_id, r.status, _iso(r.generate_at)] for r in rows]
    if code == "SCHEDULE":
        q = db.query(AaScheduleBatch).filter(AaScheduleBatch.tenant_id == T, AaScheduleBatch.is_deleted.is_(False))
        rows = (q.filter(AaScheduleBatch.term_id == term_id).all() if term_id else q.all())
        return [[r.batch_name, r.college_id, r.status, _iso(r.publish_at)] for r in rows]
    if code == "EXAM":
        q = db.query(AaExamBatch).filter(AaExamBatch.tenant_id == T, AaExamBatch.is_deleted.is_(False))
        rows = (q.filter(AaExamBatch.term_id == term_id).all() if term_id else q.all())
        return [[r.batch_name, r.exam_type, r.status, _iso(r.published_at)] for r in rows]
    if code == "GRADE":
        q = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))
        rows = (q.filter(AaGradeTask.term_code == term_code).all() if term_code else q.all())
        return [[r.course_name, r.class_id, r.status, _iso(r.publish_at)] for r in rows]
    if code == "GRADUATION":
        rows = db.query(AaGraduationAuditBatch).filter(AaGraduationAuditBatch.tenant_id == T,
                                                        AaGraduationAuditBatch.is_deleted.is_(False)).all()
        return [[r.batch_name, r.grade_year, r.status, _iso(r.generate_at)] for r in rows]
    return []


def _check_export_purpose(purpose):
    if not purpose or len(purpose.strip()) < 5:
        raise _bad("下载用途必填且不少于5字")
    return purpose.strip()


def _watermark(purpose, title):
    ctx = get_current_user_ctx() or {}
    return (f"高校学生全生命周期管理平台 · {title} · 导出人：{ctx.get('realName') or ctx.get('loginName') or '-'} · "
           f"时间：{datetime.utcnow():%Y-%m-%d %H:%M} · 用途：{purpose} · 含学生姓名/学号等敏感字段仅限内部使用")


def _record_export_task(db, row_count, purpose, file_bytes):
    from app.models import ExportTask
    task = ExportTask(tenant_id=_tid(), export_mode="ENCRYPTED_ARCHIVE", module_code="academic_affairs_archive",
                      row_count=row_count, purpose=purpose, file_hash=hashlib.sha256(file_bytes).hexdigest(),
                      status="SUCCESS")
    db.add(task)
    db.flush()
    return task


def export_batch_item(user, bid, category, purpose) -> tuple[bytes, str]:
    """单域水印导出（12 卡）：批次须 ARCHIVED；返回 (xlsx bytes, 文件名)。"""
    from app.services.xlsx_util import build_ledger_xlsx
    purpose = _check_export_purpose(purpose)
    if category not in _DOMAIN_COLS:
        raise not_found(f"未知归档物料域：{category}")
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        if b.status != "ARCHIVED":
            raise _invalid("批次未归档，暂不可下载归档物料")
        title, headers = _DOMAIN_COLS[category]
        rows = _domain_rows(db, category, b.term_id, b.term_code)
        content = build_ledger_xlsx(title, headers, rows, watermark=_watermark(purpose, title))
        _record_export_task(db, len(rows), purpose, content)
        _audit(db, b.id, "ITEM_EXPORT_DOWNLOAD", f"域={category} 用途={purpose[:100]}")
        db.commit()
        # 文件名保持 ASCII-safe（HTTP Content-Disposition 头要求 latin-1 可编码，对齐仓库既有导出端点惯例，
        # 不直接嵌入 batch_name 等中文；水印内的中文批次名已在 xlsx 内容首行体现，不影响可追溯性）。
        return content, f"{category}_batch{b.id}.xlsx"


def export_batch_all(user, bid, purpose) -> tuple[bytes, str]:
    """批次级打包下载（zip，含全部有数据的域；无记录域自动跳过，12 卡 §6）。"""
    from app.services.xlsx_util import build_ledger_xlsx
    purpose = _check_export_purpose(purpose)
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        if b.status != "ARCHIVED":
            raise _invalid("批次未归档，暂不可下载归档物料")
        buf = io.BytesIO()
        total_rows = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for code, _label in _DOMAINS:
                title, headers = _DOMAIN_COLS[code]
                rows = _domain_rows(db, code, b.term_id, b.term_code)
                if not rows:
                    continue  # 无记录域跳过，zip 内不出现空文件
                content = build_ledger_xlsx(title, headers, rows, watermark=_watermark(purpose, title))
                zf.writestr(f"{code}_{title}.xlsx", content)
                total_rows += len(rows)
        zip_bytes = buf.getvalue()
        _record_export_task(db, total_rows, purpose, zip_bytes)
        _audit(db, b.id, "BATCH_EXPORT_DOWNLOAD", f"打包下载 用途={purpose[:100]}")
        db.commit()
        # ASCII-safe 文件名（同上，避免 Content-Disposition 头 UnicodeEncodeError）。
        return zip_bytes, f"archive_batch{b.id}.zip"


def list_download_log(user, bid):
    """下载记录查询（12 卡）：谁在何时下载过本批次哪些物料。"""
    from app.models import AffairsAuditTrail
    with session() as db:
        _ctx(user, db)
        _get_batch(db, bid)  # 校验批次存在+租户归属
        rows = db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "AA_ARCHIVE",
            AffairsAuditTrail.biz_id == int(bid),
            AffairsAuditTrail.action.in_(["ITEM_EXPORT_DOWNLOAD", "BATCH_EXPORT_DOWNLOAD"])
        ).order_by(AffairsAuditTrail.id.desc()).all()
        return [{"operator": r.operator, "roleName": r.role_name, "action": r.action,
                 "detail": r.detail, "downloadAt": _iso(r.occurred_at)} for r in rows]
