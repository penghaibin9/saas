"""毕业设计中心 · 中期检查服务。

三档结论（通过/限期整改/不通过）+ 整改跟踪闭环（对齐老系统 docs/16"指导中检"页）。
通过 → 推进学生阶段 MIDTERM→FINAL_CHECK；限期整改 → 学生提交整改 → 教师复核 → 通过/退回再整改。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime

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
                                occurred_at=datetime.utcnow()))


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


def list_midterms(page: int, page_size: int, keyword=None, status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationMidterm).where(GraduationMidterm.tenant_id == _tid(),
                                             GraduationMidterm.is_deleted.is_(False),
                                             GraduationMidterm.gd_student_id.in_(scope_ids or [-1]))
        if status:
            q = q.where(GraduationMidterm.status == status)
        rows = db.scalars(q.order_by(GraduationMidterm.id.desc())).all()
        items = []
        for m in rows:
            stu = db.get(GraduationStudent, m.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_row(m, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_midterm(gd_student_id) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        m = _get_or_create(db, stu)
        db.commit()
        return _row(m, stu)


def conduct_check(gd_student_id, conclusion: str, comment: str = None, rectify_deadline: str = None) -> dict:
    if conclusion not in ("PASS", "RECTIFY", "FAIL"):
        raise AppException("VALIDATION_ERROR", "conclusion 必须是 PASS/RECTIFY/FAIL")
    with session() as db:
        stu = _stu(db, gd_student_id)
        m = _get_or_create(db, stu)
        if m.status not in ("PENDING", "RECTIFIED_PASS", "CHECKED_FAIL"):
            raise AppException("DATA_CONFLICT", "当前状态不可重新发起中期检查")
        n, _ = _op()
        m.conclusion = conclusion
        m.check_comment = (comment or "").strip()
        m.check_by = n
        m.checked_at = datetime.utcnow()
        if conclusion == "PASS":
            m.status = "CHECKED_PASS"
            if stu.stage == "MIDTERM":
                stu.stage = "FINAL_CHECK"
        elif conclusion == "RECTIFY":
            m.status = "RECTIFYING"
            if rectify_deadline:
                try:
                    m.rectify_deadline = datetime.fromisoformat(str(rectify_deadline)[:19])
                except ValueError:
                    m.rectify_deadline = None
        else:
            m.status = "CHECKED_FAIL"
            stu.risk_level = "HIGH"
        _audit(db, m.id, "中期检查-" + CONCLUSION_LABEL[conclusion], (comment or "").strip())
        db.commit()
        return _row(m, stu)


def submit_rectification(gd_student_id, content: str) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        m = _get_or_create(db, stu)
        if m.status != "RECTIFYING":
            raise AppException("DATA_CONFLICT", "当前无需提交整改")
        m.rectify_content = content
        m.rectify_submitted_at = datetime.utcnow()
        m.status = "RECTIFY_SUBMITTED"
        _audit(db, m.id, "提交整改")
        db.commit()
        return _row(m, stu)


def review_rectification(gd_student_id, action: str, comment: str = None) -> dict:
    if action not in ("PASS", "FAIL"):
        raise AppException("VALIDATION_ERROR", "action 必须是 PASS/FAIL")
    with session() as db:
        stu = _stu(db, gd_student_id)
        m = _get_or_create(db, stu)
        if m.status != "RECTIFY_SUBMITTED":
            raise AppException("DATA_CONFLICT", "当前无待复核的整改")
        n, _ = _op()
        m.review_comment = (comment or "").strip()
        m.reviewed_by = n
        m.reviewed_at = datetime.utcnow()
        if action == "PASS":
            m.status = "RECTIFIED_PASS"
            if stu.stage == "MIDTERM":
                stu.stage = "FINAL_CHECK"
        else:
            m.status = "RECTIFYING"
            m.rectify_attempts += 1
        _audit(db, m.id, "复核整改-" + ("通过" if action == "PASS" else "退回再整改"), (comment or "").strip())
        db.commit()
        return _row(m, stu)


def midterm_stats() -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        base = [GraduationMidterm.tenant_id == _tid(), GraduationMidterm.is_deleted.is_(False),
                GraduationMidterm.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationMidterm).where(*base)) or 0)
        by_status = [{"status": s, "label": STATUS_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(GraduationMidterm).where(
                          *base, GraduationMidterm.status == s)) or 0)} for s in STATUS_LABEL]
        not_started = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.stage == "MIDTERM",
            GraduationStudent.id.in_(scope_ids or [-1]))) or 0)
        return {"total": total, "byStatus": by_status, "studentsAtMidtermStage": not_started}
