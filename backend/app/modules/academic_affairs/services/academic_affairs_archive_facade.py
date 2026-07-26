"""教务归档兼容入口。

保留既有归档批次、导出、解冻和写保护实现，只接管语义完整性检查：
- 成绩复查使用真实字段 ``review_status``，并通过 ``AcademicGrade.term`` 限定到当前学期；
- 毕业审核批次当前没有 ``term_id``，仅使用创建/生成时间落在学期区间内的批次，禁止
  拿租户全部历史毕业批次阻断任意学期；无法可靠归属时明确登记兼容欠账，但不伪造缺失。

待毕业审核批次补齐强 ``term_id`` 后，应把本兼容入口合并回主 service。
"""
from __future__ import annotations

from datetime import datetime, time

from app.services.db_service import _tid, session

from . import academic_affairs_archive_service as _legacy

# 其余公开能力继续使用原实现，避免建立第二套归档事实。
guard_term_writable = _legacy.guard_term_writable
guard_term_writable_current = _legacy.guard_term_writable_current
create_batch = _legacy.create_batch
list_batches = _legacy.list_batches
get_batch = _legacy.get_batch
confirm_archive = _legacy.confirm_archive
unfreeze = _legacy.unfreeze
cancel_batch = _legacy.cancel_batch
export_batch_item = _legacy.export_batch_item
export_batch_all = _legacy.export_batch_all
list_download_log = _legacy.list_download_log

_ACTIVE_RECHECK_STATUSES = {
    "SUBMITTED", "TEACHER_REVIEW", "COLLEGE_REVIEW", "ACADEMIC_REVIEW",
}


def _day_start(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _day_end(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max)


def _evaluate_grade(db, term_code):
    """成绩任务必须发布，且本学期成绩不存在在途复查。"""
    from app.models import AaGradeRecheck, AaGradeTask, AcademicGrade

    query = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if term_code:
        query = query.filter(AaGradeTask.term_code == term_code)
    rows = query.all()
    if not rows:
        return _legacy._result(0, False, "本学期没有成绩任务")

    unfinished = [
        row for row in rows
        if str(row.status or "").upper() not in {"PUBLISHED", "ARCHIVED"}
    ]

    recheck_query = db.query(AaGradeRecheck).join(
        AcademicGrade,
        AcademicGrade.id == AaGradeRecheck.acad_grade_id,
    ).filter(
        AaGradeRecheck.tenant_id == _tid(),
        AaGradeRecheck.is_deleted.is_(False),
        AaGradeRecheck.review_status.in_(sorted(_ACTIVE_RECHECK_STATUSES)),
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.is_deleted.is_(False),
    )
    if term_code:
        recheck_query = recheck_query.filter(AcademicGrade.term == term_code)
    active_rechecks = recheck_query.count()

    passed = not unfinished and active_rechecks == 0
    remark = (
        "成绩任务均已发布且无本学期在途复查"
        if passed
        else f"未发布/未归档成绩任务 {len(unfinished)} 个，本学期在途复查 {active_rechecks} 条"
    )
    return _legacy._result(len(rows), passed, remark)


def _evaluate_graduation(db, term_id):
    """只检查能通过时间窗口可靠归属到本学期的毕业审核批次。

    当前 AaGraduationAuditBatch 没有 term_id。直接查询租户全量会让往年未归档批次阻断任意
    学期；按 grade_year 推算也不可靠，因为该字段保存入学年级而非毕业年份。
    """
    from app.models import AaGraduationAuditBatch, AaTerm

    if not term_id:
        return _legacy._result(
            0, True,
            "未指定学期；毕业审核批次暂无term_id，本次不跨学期阻断",
        )
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return _legacy._result(0, False, "学期不存在，无法核验毕业审核范围")

    start_at = _day_start(getattr(term, "start_date", None))
    end_at = _day_end(getattr(term, "end_date", None))
    if not start_at or not end_at:
        return _legacy._result(
            0, True,
            "学期起止日期不完整；毕业批次暂无term_id，已停止使用全校历史批次作阻断",
        )

    all_rows = db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False),
    ).all()
    rows = []
    for row in all_rows:
        occurred_at = getattr(row, "generate_at", None) or getattr(row, "created_at", None)
        if occurred_at and start_at <= occurred_at <= end_at:
            rows.append(row)

    if not rows:
        return _legacy._result(
            0, True,
            "本学期未发现可按时间归属的毕业审核批次（非毕业学期不阻断；待补term_id）",
        )
    unfinished = [row for row in rows if str(row.status or "").upper() != "ARCHIVED"]
    passed = not unfinished
    return _legacy._result(
        len(rows),
        passed,
        "本学期毕业审核批次均已归档"
        if passed
        else f"本学期仍有 {len(unfinished)} 个毕业审核批次未归档",
    )


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    checks = {
        "STUDENT_STATUS": lambda: _legacy._evaluate_student_status(db, college_ids),
        "REGISTRATION": lambda: _legacy._evaluate_registration(db, term_id),
        "STATUS_CHANGE": lambda: _legacy._evaluate_status_change(db, term_code),
        "PROGRAM": lambda: _legacy._evaluate_program(db),
        "TEACHING_TASK": lambda: _legacy._evaluate_teaching_task(db, term_id, college_ids),
        "SCHEDULE": lambda: _legacy._evaluate_schedule(db, term_id, college_ids),
        "EXAM": lambda: _legacy._evaluate_exam(db, term_id),
        "GRADE": lambda: _evaluate_grade(db, term_code),
        "GRADUATION": lambda: _evaluate_graduation(db, term_id),
    }
    results = {}
    for code, _label in _legacy._DOMAINS:
        try:
            results[code] = checks[code]()
        except Exception as exc:  # 单域错误必须成为阻断，不能伪装为无数据或成功
            results[code] = _legacy._result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


def run_check(user, batch_id):
    """按本兼容入口的语义规则执行检查并持久化。"""
    from app.models import AaArchiveItem

    with session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, batch_id)
        if batch.status in {"ARCHIVED", "CANCELLED"}:
            raise _legacy._invalid("已归档/已取消批次不可再检查")

        results = _evaluate_domains(db, batch.term_id, batch.term_code)
        db.query(AaArchiveItem).filter(
            AaArchiveItem.batch_id == batch.id,
            AaArchiveItem.tenant_id == _tid(),
        ).delete(synchronize_session=False)

        missing = 0
        for code, label in _legacy._DOMAINS:
            result = results[code]
            if not result["present"]:
                missing += 1
            db.add(AaArchiveItem(
                tenant_id=_tid(),
                batch_id=batch.id,
                domain=code,
                domain_label=label,
                record_count=result["recordCount"],
                present=result["present"],
                remark=result["remark"],
            ))

        batch.missing_count = missing
        batch.checked_at = datetime.utcnow()
        batch.status = "READY" if missing == 0 else "MISSING_ITEMS"
        _legacy._audit(db, batch.id, "ARCHIVE_CHECK", f"语义完整性检查 阻断{missing}域")
        db.commit()
        return _legacy._batch_dto(batch, items=_legacy._items_dto(db, batch.id))


def precheck(user, term_id=None):
    """实时预检；失败域与无数据严格区分。"""
    from app.models import AaTerm

    with session() as db:
        ctx = _legacy._ctx(user, db)
        if term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == int(term_id),
                AaTerm.tenant_id == _tid(),
                AaTerm.is_deleted.is_(False),
            ).first()
            if not term:
                raise _legacy.not_found("学期不存在")
        else:
            term = db.query(AaTerm).filter(
                AaTerm.tenant_id == _tid(),
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            ).first()

        term_id_value = term.id if term else None
        term_code_value = f"{term.year_code}-{term.term_no}" if term else None
        college_ids = ctx.college_ids if ctx.scope_type == "COLLEGE" else None
        evaluated = _evaluate_domains(db, term_id_value, term_code_value, college_ids)
        domains = []
        for code, label in _legacy._DOMAINS:
            result = evaluated[code]
            domains.append({
                "domain": code,
                "domainLabel": label,
                "recordCount": result["recordCount"],
                "status": "OK" if result["present"] else "MISSING",
                "note": result["remark"],
            })
        return {
            "termId": str(term_id_value) if term_id_value else None,
            "termCode": term_code_value,
            "scopeNote": (
                "教学任务、课表、学籍按本院范围检查；其他域仍按其业务归属规则"
                if college_ids else None
            ),
            "domains": domains,
        }
