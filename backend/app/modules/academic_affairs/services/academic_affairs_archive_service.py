"""13B-R7 教务归档 service。

按学年学期建归档批次(D-01) → 完整性检查(聚合9数据域记录数,present/missing) →
确认归档(批次ARCHIVED + 学期status→ARCHIVED,D-04) → 特批解冻(仅SCHOOL_ADMIN,D-06)。

D-04 学期封存后该学期写端点应 409（横切拦截跨 R1-R6 端点，工程量大，本期落"学期状态置 ARCHIVED"，
全域写保护横切登记为欠账）。审计复用 AffairsAuditTrail(biz_type=AA_ARCHIVE)。
"""
from __future__ import annotations

from datetime import datetime

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
