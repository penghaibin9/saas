"""过程指导/中期检查一致性收口。

中期 GET 只返回虚拟 PENDING，不因查看页面写库；首次检查才创建记录。
列表、统计与计划均支持批次范围；检查、整改、签到和取消使用行锁。
V9.2 U4：过程列表统一在 MySQL 侧完成 dataScope、关联、筛选、计数与分页，
禁止 Python 全量物化和逐行 student N+1。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationGuidance, GraduationGuidancePlan, GraduationMidterm, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _iso, _tid, session


def _student_filters(scope_select):
    return (
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.id.in_(scope_select),
    )


def _keyword_filter(keyword):
    value = str(keyword or "").strip()
    if not value:
        return None
    return or_(GraduationStudent.name.contains(value), GraduationStudent.student_no.contains(value))


def list_guidance(page, page_size, gd_student_id=None, keyword=None, batch_id=None):
    from app.modules.graduation.services import graduation_guidance_service as svc
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    with session() as db:
        scope_select = student_scope_select(db, _tid(), batch_id=batch_id)
        filters = [
            GraduationGuidance.tenant_id == _tid(),
            GraduationGuidance.is_deleted.is_(False),
            *_student_filters(scope_select),
        ]
        if gd_student_id:
            filters.append(GraduationGuidance.gd_student_id == int(gd_student_id))
        keyword_clause = _keyword_filter(keyword)
        if keyword_clause is not None:
            filters.append(keyword_clause)
        join_on = GraduationStudent.id == GraduationGuidance.gd_student_id
        total = int(db.scalar(
            select(func.count()).select_from(GraduationGuidance)
            .join(GraduationStudent, join_on).where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationGuidance, GraduationStudent)
            .join(GraduationStudent, join_on).where(*filters)
            .order_by(GraduationGuidance.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)
        ).all()
        return [svc._row(row, student) for row, student in rows], total


def list_plans(page, page_size, gd_student_id=None, batch_id=None):
    from app.modules.graduation.services import graduation_guidance_service as svc
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    with session() as db:
        scope_select = student_scope_select(db, _tid(), batch_id=batch_id)
        filters = [
            GraduationGuidancePlan.tenant_id == _tid(),
            GraduationGuidancePlan.is_deleted.is_(False),
            *_student_filters(scope_select),
        ]
        if gd_student_id:
            filters.append(GraduationGuidancePlan.gd_student_id == int(gd_student_id))
        join_on = GraduationStudent.id == GraduationGuidancePlan.gd_student_id
        total = int(db.scalar(
            select(func.count()).select_from(GraduationGuidancePlan)
            .join(GraduationStudent, join_on).where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationGuidancePlan, GraduationStudent)
            .join(GraduationStudent, join_on).where(*filters)
            .order_by(GraduationGuidancePlan.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)
        ).all()
        return [svc._plan_row(row, student) for row, student in rows], total


def list_midterms(page, page_size, keyword=None, status=None, batch_id=None):
    from app.modules.graduation.services import graduation_midterm_service as svc
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    with session() as db:
        scope_select = student_scope_select(db, _tid(), batch_id=batch_id)
        filters = [
            GraduationMidterm.tenant_id == _tid(),
            GraduationMidterm.is_deleted.is_(False),
            *_student_filters(scope_select),
        ]
        if status:
            filters.append(GraduationMidterm.status == status)
        keyword_clause = _keyword_filter(keyword)
        if keyword_clause is not None:
            filters.append(keyword_clause)
        join_on = GraduationStudent.id == GraduationMidterm.gd_student_id
        total = int(db.scalar(
            select(func.count()).select_from(GraduationMidterm)
            .join(GraduationStudent, join_on).where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationMidterm, GraduationStudent)
            .join(GraduationStudent, join_on).where(*filters)
            .order_by(GraduationMidterm.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)
        ).all()
        return [svc._row(row, student) for row, student in rows], total


def get_midterm(gd_student_id) -> dict:
    from app.modules.graduation.services import graduation_midterm_service as svc
    with session() as db:
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "midterm.view")
        row = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == student.id,
            GraduationMidterm.is_deleted.is_(False),
        )).first()
        if row:
            return {"exists": True, **svc._row(row, student)}
        return {
            "exists": False, "id": None, "gdStudentId": str(student.id),
            "studentName": student.name, "studentNo": student.student_no or "",
            "advisorName": student.advisor_name or "", "status": "PENDING",
            "statusLabel": svc.STATUS_LABEL["PENDING"], "statusTone": svc.STATUS_TONE["PENDING"],
            "conclusion": "", "conclusionLabel": "", "checkComment": "",
            "checkBy": "", "checkedAt": None, "rectifyDeadline": None,
            "rectifyContent": "", "rectifySubmittedAt": None, "rectifyAttempts": 0,
            "reviewComment": "", "reviewedBy": "", "reviewedAt": None, "updatedAt": None,
        }


def _locked_student_midterm(db, gd_student_id, action: str, *, create=False):
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(gd_student_id), GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
    ).with_for_update()).first()
    if not student:
        raise not_found("毕设学生不存在")
    assert_student_access(db, student, action)
    row = db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == student.id,
        GraduationMidterm.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row and create:
        row = GraduationMidterm(
            tenant_id=_tid(), gd_student_id=student.id, batch_id=student.batch_id, status="PENDING",
        )
        db.add(row)
        db.flush()
    return student, row


def conduct_check(gd_student_id, conclusion, comment=None, rectify_deadline=None):
    from app.modules.graduation.services import graduation_midterm_service as svc
    if conclusion not in ("PASS", "RECTIFY", "FAIL"):
        raise AppException("VALIDATION_ERROR", "conclusion 必须是 PASS/RECTIFY/FAIL")
    with session() as db:
        student, row = _locked_student_midterm(db, gd_student_id, "midterm.review", create=True)
        if student.stage not in ("MIDTERM", "FINAL_CHECK"):
            raise AppException("DATA_CONFLICT", "当前阶段不可发起中期检查")
        if row.status not in ("PENDING", "RECTIFIED_PASS", "CHECKED_FAIL"):
            raise AppException("DATA_CONFLICT", "该中期检查已被处理，请刷新")
        operator, _ = svc._op()
        row.conclusion = conclusion
        row.check_comment = (comment or "").strip()
        row.check_by = operator
        row.checked_at = datetime.now(timezone.utc)
        student.midterm_conclusion = svc.CONCLUSION_LABEL[conclusion]
        if conclusion == "PASS":
            row.status = "CHECKED_PASS"
            if student.stage == "MIDTERM": student.stage = "FINAL_CHECK"
        elif conclusion == "RECTIFY":
            row.status = "RECTIFYING"
            if rectify_deadline:
                try: row.rectify_deadline = datetime.fromisoformat(str(rectify_deadline)[:19])
                except ValueError: raise AppException("VALIDATION_ERROR", "整改截止时间格式不正确") from None
        else:
            row.status = "CHECKED_FAIL"
            student.risk_level = "HIGH"
        svc._audit(db, row.id, "中期检查-" + svc.CONCLUSION_LABEL[conclusion], (comment or "").strip())
        db.commit()
        return {"exists": True, **svc._row(row, student)}


def submit_rectification(gd_student_id, content):
    from app.modules.graduation.services import graduation_midterm_service as svc
    value = str(content or "").strip()
    if not value:
        raise AppException("VALIDATION_ERROR", "整改说明不能为空")
    with session() as db:
        student, row = _locked_student_midterm(db, gd_student_id, "midterm.rectify")
        if not row or row.status != "RECTIFYING":
            raise AppException("DATA_CONFLICT", "当前无需提交整改")
        row.rectify_content = value
        row.rectify_submitted_at = datetime.now(timezone.utc)
        row.status = "RECTIFY_SUBMITTED"
        svc._audit(db, row.id, "提交整改")
        db.commit()
        return {"exists": True, **svc._row(row, student)}


def review_rectification(gd_student_id, action, comment=None):
    from app.modules.graduation.services import graduation_midterm_service as svc
    if action not in ("PASS", "FAIL"):
        raise AppException("VALIDATION_ERROR", "action 必须是 PASS/FAIL")
    with session() as db:
        student, row = _locked_student_midterm(db, gd_student_id, "midterm.review")
        if not row or row.status != "RECTIFY_SUBMITTED":
            raise AppException("DATA_CONFLICT", "整改已被处理或尚未提交，请刷新")
        operator, _ = svc._op()
        row.review_comment = (comment or "").strip()
        row.reviewed_by = operator
        row.reviewed_at = datetime.now(timezone.utc)
        if action == "PASS":
            row.status = "RECTIFIED_PASS"
            row.conclusion = "PASS"
            student.midterm_conclusion = svc.CONCLUSION_LABEL["PASS"]
            if student.stage == "MIDTERM": student.stage = "FINAL_CHECK"
        else:
            row.status = "RECTIFYING"
            row.rectify_attempts = int(row.rectify_attempts or 0) + 1
            student.midterm_conclusion = svc.CONCLUSION_LABEL["RECTIFY"]
        svc._audit(db, row.id, "复核整改-" + ("通过" if action == "PASS" else "退回再整改"),
                   (comment or "").strip())
        db.commit()
        return {"exists": True, **svc._row(row, student)}


def checkin_plan(plan_id, body=None):
    from app.modules.graduation.services import graduation_guidance_service as svc
    body = body or {}
    with session() as db:
        plan = db.scalars(select(GraduationGuidancePlan).where(
            GraduationGuidancePlan.id == int(plan_id), GraduationGuidancePlan.tenant_id == _tid(),
            GraduationGuidancePlan.is_deleted.is_(False),
        ).with_for_update()).first()
        if not plan:
            raise not_found("指导计划不存在")
        student = db.get(GraduationStudent, plan.gd_student_id)
        assert_student_access(db, student, "guidance.checkin")
        if plan.status != "PLANNED":
            raise AppException("DATA_CONFLICT", "该计划已签到或已取消，请刷新")
        user = get_current_user_ctx() or {}
        role = str(user.get("currentRoleCode") or "").upper()
        user_type = str(user.get("userType") or "").upper()
        operator, _ = svc._op()
        method = str(body.get("method") or "MANUAL").upper()
        if method not in svc.METHOD_LABEL: method = "MANUAL"
        plan.status = "CHECKED_IN"
        plan.checked_in_at = datetime.now(timezone.utc)
        plan.checked_in_by = operator
        plan.checkin_role = "STUDENT" if user_type == "STUDENT" or role == "STUDENT" else (
            "MENTOR" if role in {"GD_MENTOR", "COUNSELOR"} else "STAFF")
        plan.checkin_note = str(body.get("note") or "").strip() or None
        plan.checkin_method = method
        svc._audit(db, plan.id, "指导计划签到", detail=f"{student.name}/{plan.checkin_role}/{operator}")
        db.commit()
        return svc._plan_row(plan, student)


def cancel_plan(plan_id, reason):
    from app.modules.graduation.services import graduation_guidance_service as svc
    value = str(reason or "").strip()
    if len(value) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因必填且不少于 5 字")
    with session() as db:
        plan = db.scalars(select(GraduationGuidancePlan).where(
            GraduationGuidancePlan.id == int(plan_id), GraduationGuidancePlan.tenant_id == _tid(),
            GraduationGuidancePlan.is_deleted.is_(False),
        ).with_for_update()).first()
        if not plan:
            raise not_found("指导计划不存在")
        student = db.get(GraduationStudent, plan.gd_student_id)
        assert_student_access(db, student, "guidance.update")
        if plan.status == "CHECKED_IN":
            raise AppException("DATA_CONFLICT", "已签到计划不可取消，请保留留痕")
        if plan.status == "CANCELLED":
            raise AppException("DATA_CONFLICT", "计划已取消")
        plan.status = "CANCELLED"
        plan.void_reason = value
        plan.is_deleted = True
        svc._audit(db, plan.id, "取消指导计划", value)
        db.commit()
        return {"id": str(plan.id), "cancelled": True}
