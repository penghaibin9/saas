"""毕业设计中心 · 中期检查服务。

三档结论（通过/限期整改/不通过）+ 整改跟踪闭环（对齐老系统 docs/16"指导中检"页）。
通过 → 推进学生阶段 MIDTERM→FINAL_CHECK；限期整改 → 学生提交整改 → 教师复核 → 通过/退回再整改。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationMidterm, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

STATUS_LABEL = {"PENDING": "待检查", "CHECKED_PASS": "已通过", "RECTIFYING": "限期整改中",
                "RECTIFY_SUBMITTED": "整改待复核", "RECTIFIED_PASS": "整改已通过", "CHECKED_FAIL": "不通过"}
STATUS_TONE = {"PENDING": "default", "CHECKED_PASS": "success", "RECTIFYING": "warning",
               "RECTIFY_SUBMITTED": "warning", "RECTIFIED_PASS": "success", "CHECKED_FAIL": "danger"}
CONCLUSION_LABEL = {"PASS": "通过", "RECTIFY": "限期整改", "FAIL": "不通过"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="MIDTERM", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "midterm")


def _get_or_create(db, stu: GraduationStudent) -> GraduationMidterm:
    m = db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == stu.id,
        GraduationMidterm.is_deleted.is_(False))).first()
    if not m:
        m = GraduationMidterm(tenant_id=_tid(), gd_student_id=stu.id, batch_id=stu.batch_id, status="PENDING")
        db.add(m)
        db.flush()
    return m


def _row(m: GraduationMidterm, stu=None) -> dict:
    return {"id": str(m.id), "gdStudentId": str(m.gd_student_id),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "advisorName": stu.advisor_name if stu else "",
            "status": m.status, "statusLabel": STATUS_LABEL.get(m.status, m.status),
            "statusTone": STATUS_TONE.get(m.status, "default"),
            "conclusion": m.conclusion or "", "conclusionLabel": CONCLUSION_LABEL.get(m.conclusion or "", ""),
            "checkComment": m.check_comment or "", "checkBy": m.check_by or "", "checkedAt": _iso(m.checked_at),
            "rectifyDeadline": _iso(m.rectify_deadline), "rectifyContent": m.rectify_content or "",
            "rectifySubmittedAt": _iso(m.rectify_submitted_at), "rectifyAttempts": m.rectify_attempts,
            "reviewComment": m.review_comment or "", "reviewedBy": m.reviewed_by or "",
            "reviewedAt": _iso(m.reviewed_at), "updatedAt": _iso(m.updated_at)}


def midterm_stats(batch_id=None) -> dict:
    with session() as db:
        from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select

        scope = student_scope_select(db, _tid(), batch_id=batch_id)
        base = [GraduationMidterm.tenant_id == _tid(), GraduationMidterm.is_deleted.is_(False),
                GraduationMidterm.gd_student_id.in_(scope)]
        status_counts = {
            str(status or ""): int(count)
            for status, count in db.execute(
                select(GraduationMidterm.status, func.count(GraduationMidterm.id))
                .where(*base)
                .group_by(GraduationMidterm.status)
            ).all()
        }
        total = sum(status_counts.values())
        by_status = [{"status": status, "label": STATUS_LABEL[status],
                      "count": status_counts.get(status, 0)} for status in STATUS_LABEL]
        from app.modules.graduation.services.graduation_process_consistency import (
            _midterm_eligible_clause, _no_midterm_row,
        )
        not_started = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            # 待发起中期检查：开题已通过（或已处于中期阶段）但尚无检查记录的学生
            GraduationStudent.record_status == "ACTIVE", _midterm_eligible_clause(), _no_midterm_row(),
            GraduationStudent.id.in_(scope))) or 0)
        return {"total": total, "byStatus": by_status, "studentsAtMidtermStage": not_started,
                "batchId": str(batch_id) if batch_id else None}


from app.modules.graduation.services.graduation_process_consistency import (
    conduct_check,
    get_midterm,
    list_midterms,
    review_rectification,
    submit_rectification,
)
