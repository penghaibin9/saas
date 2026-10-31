"""Teacher Miniapp V3 T6 internship execution-evidence adapter.

This module does not introduce a second internship authority. It composes the existing
InternshipRecord / InternshipVisit / RiskRecord / InternshipAuditTrail facts and the public
file-binding hook into one mobile command transaction. Shared Student V3 files remain untouched.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import aliased

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAuditTrail,
    InternshipRecord,
    InternshipVisit,
    InternshipVisitPlan,
    RiskRecord,
    StudentProfile,
)
from app.modules.internship.services import internship_service
from app.modules.internship.services import internship_visit_plan_service as visit_plan_service
from app.modules.internship.services import internship_teacher_activity_service as teacher_guard
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services.internship_batch_context import assert_record_batch, parse_required_batch_id, resolve_batch
from app.services.db_service import _as_id, _tid, session

_RISK_LEVEL_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
_ALLOWED_VISIT_TYPES = {"ONSITE", "ONLINE", "PHONE", "VIDEO", "OTHER"}
_PLAN_ACTIVE = {"PUBLISHED", "IN_PROGRESS"}
_SCOPE_SPLIT = re.compile(r"[,，、;；\n\r]+")
_PLAN_SCOPE_COMPOSITE = re.compile(
    r"^(?P<name>.+?)\s*[\(（]\s*(?P<student_no>[^()（）]+?)\s*[\)）]\s*$"
)


def _op_name(user: dict | None) -> str:
    return str((user or {}).get("realName") or "系统").strip() or "系统"


def _plan_scope_tokens(raw: str | None) -> set[str]:
    return {item.strip() for item in _SCOPE_SPLIT.split(str(raw or "")) if item.strip()}


def _plan_allows_student(plan: InternshipVisitPlan, student: StudentProfile) -> bool:
    tokens = _plan_scope_tokens(plan.student_scope)
    if not tokens:
        return False
    name = str(student.real_name or "").strip()
    student_no = str(student.student_no or "").strip()
    if name in tokens or student_no in tokens:
        return True
    # Historical plans may freeze a display token such as "张三(20230001)".  This token is an
    # authorization boundary, so parse and compare both fields exactly; substring guessing can
    # otherwise authorize 张三 / 20230001 from a different longer display token.
    for token in tokens:
        match = _PLAN_SCOPE_COMPOSITE.fullmatch(token)
        if not match:
            continue
        if (
            name
            and student_no
            and match.group("name").strip() == name
            and match.group("student_no").strip() == student_no
        ):
            return True
    return False


def _risk_level_max(current: str | None, requested: str) -> str:
    cur = str(current or "NONE").upper()
    req = str(requested or "NONE").upper()
    return req if _RISK_LEVEL_ORDER.get(req, 0) > _RISK_LEVEL_ORDER.get(cur, 0) else cur


def _plan_record_query(plan, user):
    tokens = _plan_scope_tokens(plan.student_scope)
    named_student, named_record = aliased(StudentProfile), aliased(InternshipRecord)
    name_count = select(func.count(func.distinct(named_student.id))).join(named_record, and_(
        named_record.student_id == named_student.id, named_record.tenant_id == _tid(),
        named_record.is_deleted.is_(False), named_record.batch_id == plan.batch_id,
    )).where(named_student.tenant_id == _tid(), named_student.is_deleted.is_(False),
             named_student.real_name == StudentProfile.real_name).correlate(StudentProfile).scalar_subquery()
    # 历史裸姓名只有在整个批次唯一时才能确定学生，不能按当前老师范围消除同名歧义。
    targets = [and_(StudentProfile.real_name.in_(tokens), name_count == 1),
               StudentProfile.student_no.in_(tokens)] if tokens else [false()]
    for token in tokens:
        match = _PLAN_SCOPE_COMPOSITE.fullmatch(token)
        if match:
            targets.append(and_(StudentProfile.real_name == match.group('name').strip(),
                                StudentProfile.student_no == match.group('student_no').strip()))
    query = select(InternshipRecord.id).join(StudentProfile, and_(
        StudentProfile.id == InternshipRecord.student_id, StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )).where(InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
             InternshipRecord.batch_id == plan.batch_id, or_(*targets))
    if plan.enterprise_id:
        query = query.where(InternshipRecord.enterprise_id == plan.enterprise_id)
    elif plan.enterprise_name:
        query = query.where(InternshipRecord.enterprise_name == plan.enterprise_name)
    return apply_internship_record_scope(query, user)


def list_visit_targets(user: dict, *, batch_id, page=1, page_size=20, plan_id=None,
                       student_page=1, student_page_size=20, internship_id=None, keyword='') -> dict[str, Any]:
    """当前批次、计划冻结对象及稳定导师范围；计划和学生分别在数据库分页。"""
    teacher_guard._teacher_identity(user)
    with session() as db:
        teacher_guard._assert_teacher_batch_scope(db, int(batch_id), user)
        query = select(InternshipVisitPlan).where(InternshipVisitPlan.tenant_id == _tid(),
            InternshipVisitPlan.is_deleted.is_(False), InternshipVisitPlan.batch_id == int(batch_id),
            InternshipVisitPlan.status.in_(_PLAN_ACTIVE))
        scope = internship_service._current_scope(user)
        query = query.where(visit_plan_service.plan_scope_clause(scope))
        if plan_id is not None:
            query = query.where(InternshipVisitPlan.id == int(plan_id))
        term = str(keyword or '').strip()
        if term:
            # 企业来自被授权的当前实习关系，不接受客户端伪造企业名称。
            match = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        plans = db.scalars(query.order_by(InternshipVisitPlan.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for plan in plans:
            records = _plan_record_query(plan, user)
            if term:
                records = records.where(InternshipRecord.enterprise_name.ilike(match, escape='\\'))
            if internship_id is not None:
                records = records.where(InternshipRecord.id == int(internship_id))
            visit_lookup = select(InternshipVisit.id).join(InternshipAuditTrail, and_(
                InternshipAuditTrail.target_id == InternshipVisit.id,
                InternshipAuditTrail.target_type == 'VISIT', InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.action == 'CREATE_MOBILE_EVIDENCE',
                InternshipAuditTrail.detail_json['planId'].as_string() == str(plan.id),
            )).where(InternshipVisit.tenant_id == _tid(), InternshipVisit.is_deleted.is_(False),
                     InternshipVisit.internship_id == InternshipRecord.id,
                     InternshipVisit.student_id == InternshipRecord.student_id)
            visited = visit_lookup.exists()
            student_total = db.scalar(select(func.count()).select_from(records.subquery())) or 0
            visited_total = db.scalar(select(func.count()).select_from(records.where(visited).subquery())) or 0
            rows = db.execute(select(InternshipRecord, StudentProfile, visited.label('visited'),
                visit_lookup.order_by(InternshipVisit.id.desc()).limit(1).scalar_subquery().label('visit_id'))
                .join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
                .where(InternshipRecord.id.in_(records)).order_by(InternshipRecord.id)
                .offset((student_page - 1) * student_page_size).limit(student_page_size)).all()
            plan_row = visit_plan_service._row(plan)
            plan_row.pop('studentScope', None)  # 只返回当前老师有权访问的精确学生。
            items.append({**plan_row, 'studentTotal': student_total,
                'visitedStudentCount': visited_total, 'studentPage': student_page,
                'studentHasMore': student_page * student_page_size < student_total,
                'students': [{'name': stu.real_name, 'studentNo': stu.student_no,
                    'internshipId': str(rec.id), 'batchId': str(rec.batch_id), 'planId': str(plan.id),
                    'expectedVersion': int(rec.version or 0), 'expectedPlanVersion': int(plan.version or 0),
                    'positionName': rec.position_name or '', 'enterpriseName': rec.enterprise_name or '',
                    'visited': bool(done), 'visitId': str(visit_id) if visit_id else '',
                    'resolvable': True} for rec, stu, done, visit_id in rows]})
    return {'hasData': bool(items), 'batchId': str(batch_id), 'plans': items, 'enterpriseKeyword': term,
            'page': page, 'pageSize': page_size, 'total': total, 'hasMore': page * page_size < total}


def remind_overdue_weekly_report(user: dict, report_id: Any) -> dict:
    """Scope first, then require real OVERDUE truth, then delegate canonical outbox command."""
    teacher_guard._teacher_identity(user)
    detail = internship_service.get_weekly_report_detail(report_id, user=user)
    if str((detail or {}).get("status") or "").upper() != "OVERDUE":
        raise AppException(
            "DATA_CONFLICT",
            "仅真实逾期未交周报可以催交，请刷新列表后重试",
            http_status=409,
        )
    return internship_service.remind_weekly_report(report_id, user=user)


def _validate_file_ids(user: dict, raw_file_ids: Any) -> str | None:
    file_ids = [str(item or "").strip() for item in (raw_file_ids or []) if str(item or "").strip()]
    if len(file_ids) > 1:
        raise AppException("VALIDATION_ERROR", "T8 公共多附件接管前，巡访执行证据最多上传 1 个附件")
    if not file_ids:
        return None
    fid = file_ids[0]
    from app.services.internship_file_transfer_service import authorized_file

    _, meta = authorized_file(fid, user, 'bind')
    if not meta:
        raise AppException("VALIDATION_ERROR", "附件不存在、无权访问或尚未完成安全扫描")
    if str(meta.get("bizType") or "").upper() != "TEMP_PRIVATE" or str(meta.get("bizId") or "").strip():
        raise AppException("FILE_ALREADY_BOUND", "巡访附件必须是本人本次上传且尚未绑定的临时文件")
    if not bool(meta.get("readyForBusiness", False)):
        raise AppException("FILE_NOT_READY", "附件仍在安全扫描，请稍后重试", http_status=409)
    return fid


def _validate_plan(db, plan_id: Any, rec: InternshipRecord, student: StudentProfile, user: dict,
                   expected_plan_version: int) -> InternshipVisitPlan:
    plan = db.scalar(select(InternshipVisitPlan).where(
        InternshipVisitPlan.id == _as_id(plan_id),
        InternshipVisitPlan.tenant_id == _tid(),
        InternshipVisitPlan.is_deleted.is_(False),
    ).with_for_update())
    if not plan:
        raise not_found("巡访计划不存在或已失效")
    if int(plan.version or 0) != expected_plan_version:
        raise AppException("DATA_CONFLICT", "巡访计划已发生变化，请先重读核对计划", http_status=409)
    if str(plan.status or "").upper() not in _PLAN_ACTIVE:
        raise AppException("DATA_CONFLICT", "巡访计划当前不可执行，请刷新计划后重试", http_status=409)
    scope = internship_service._current_scope(user)
    if not visit_plan_service._scope_ok(scope, plan, db):
        raise no_permission("该巡访计划不在你的执行范围内")
    if plan.batch_id and int(plan.batch_id) != int(rec.batch_id or 0):
        raise AppException("DATA_CONFLICT", "巡访计划与学生当前实习批次不一致", http_status=409)
    if plan.enterprise_id and int(plan.enterprise_id) != int(rec.enterprise_id or 0):
        raise AppException("DATA_CONFLICT", "巡访计划与学生当前实习企业不一致", http_status=409)
    if plan.enterprise_name and rec.enterprise_name:
        if str(plan.enterprise_name).strip() != str(rec.enterprise_name).strip() and not plan.enterprise_id:
            raise AppException("DATA_CONFLICT", "巡访计划企业与学生当前实习企业不一致", http_status=409)
    if not _plan_allows_student(plan, student) or db.scalar(
        _plan_record_query(plan, user).where(InternshipRecord.id == rec.id)
    ) is None:
        raise no_permission("该学生不在此巡访计划的冻结学生范围内")
    return plan


def _visit_report_text(body: dict) -> str:
    parts = [
        f"联系人：{str(body.get('contactPerson') or '').strip()}",
        f"工作状态：{str(body.get('workStatus') or '').strip()}",
        f"事实记录：{str(body.get('facts') or '').strip()}",
    ]
    if str(body.get("advice") or "").strip():
        parts.append(f"指导建议：{str(body.get('advice')).strip()}")
    if bool(body.get("needFollow")):
        parts.append("后续跟进：需要")
    return "\n".join(parts)


def create_visit_evidence(user: dict, internship_id: Any, body: dict) -> dict:
    """Create one execution evidence record and optional risk in one locked transaction."""
    teacher_guard._teacher_identity(user)
    b = dict(body or {})
    from app.modules.internship.services.internship_visit_service import normalize_visit_title, encrypt_visit_location
    title = normalize_visit_title(b.get('title'))
    encrypted_location = encrypt_visit_location(b.get('location'))
    visit_type = str(b.get("visitType") or "").upper().strip()
    if visit_type not in _ALLOWED_VISIT_TYPES:
        raise AppException("VALIDATION_ERROR", "巡访类型不合法")
    facts = str(b.get("facts") or "").strip()
    contact = str(b.get("contactPerson") or "").strip()
    work_status = str(b.get("workStatus") or "").strip()
    enterprise_feedback = str(b.get("enterpriseFeedback") or "").strip()
    if len(contact) < 2 or len(work_status) < 2 or len(enterprise_feedback) < 2 or len(facts) < 10:
        raise AppException("VALIDATION_ERROR", "联系人、工作状态、企业反馈必填，情况记录不少于 10 字")

    need_risk = bool(b.get("needRisk"))
    risk_level = str(b.get("riskLevel") or "").upper().strip()
    risk_reason = str(b.get("riskReason") or "").strip()
    if need_risk:
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            raise AppException("VALIDATION_ERROR", "转风险时风险等级须为低 / 中 / 高")
        if len(risk_reason) < 5:
            raise AppException("VALIDATION_ERROR", "转风险原因不少于 5 字")
    elif risk_level or risk_reason:
        raise AppException("VALIDATION_ERROR", "未勾选转风险时不得提交风险字段")

    expected = b.get("expectedVersion")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise AppException("VALIDATION_ERROR", "数据版本必须是非负整数")
    expected_plan = b.get("expectedPlanVersion")
    if isinstance(expected_plan, bool) or not isinstance(expected_plan, int) or expected_plan < 0:
        raise AppException("VALIDATION_ERROR", "巡访计划版本必须是非负整数")
    batch_id = parse_required_batch_id(b.get('batchId'))

    with session() as db:
        rec = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == _as_id(internship_id),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
        ).with_for_update())
        if not rec:
            raise not_found("实习记录不存在")
        assert_record_batch(rec, batch_id)
        current_version = int(rec.version or 0)
        if current_version != expected:
            raise AppException(
                "DATA_CONFLICT",
                "实习记录已发生变化，请刷新巡访计划后重试",
                details={"expectedVersion": expected, "currentVersion": current_version},
                http_status=409,
            )
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == rec.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ))
        if not student:
            raise not_found("学生主档不存在")
        scope = internship_service._current_scope(user)
        if not internship_service._rec_in_scope(scope, db, rec, student):
            raise no_permission("只能登记本人数据范围内学生的巡访执行证据")

        plan = _validate_plan(db, b.get("planId"), rec, student, user, expected_plan)
        resolve_batch(db, rec.batch_id, for_write=True)
        file_id = _validate_file_ids(user, b.get("fileIds"))
        issues = str(b.get("issues") or "").strip()
        advice = str(b.get("advice") or "").strip()
        need_follow = bool(b.get("needFollow"))
        has_rectify = bool(need_follow or issues or advice)

        visit = InternshipVisit(
            tenant_id=_tid(),
            internship_id=rec.id,
            student_id=rec.student_id,
            advisor_name=_op_name(user),
            enterprise_name=rec.enterprise_name or plan.enterprise_name or None,
            visit_title=title,
            location_encrypted=encrypted_location,
            visit_at=datetime.utcnow(),
            method=visit_type,
            enterprise_feedback=enterprise_feedback,
            student_feedback=work_status,
            safety_issue=issues or None,
            rectify_require=advice or ("需继续跟进" if need_follow else None),
            rectify_status="PENDING" if has_rectify else "NONE",
            monthly_report=_visit_report_text(b),
            file_id=file_id,
        )
        db.add(visit)
        db.flush()
        from app.modules.internship.services.internship_visit_service import bind_visit_file
        bind_visit_file(db, visit, rec, student, user)

        risk = None
        if need_risk:
            risk = RiskRecord(
                tenant_id=_tid(),
                internship_id=rec.id,
                risk_code="INT-R-VISIT",
                risk_title="巡访发现风险转办",
                risk_level=risk_level,
                source_module="visit",
                source_type="VISIT",
                source_id=visit.id,
                source_version=int(visit.version or 0),
                owner_name=rec.advisor_name or _op_name(user),
                deadline_at=datetime.utcnow() + timedelta(days=3),
                status="PENDING_HANDLE",
                last_follow_note=risk_reason[:500],
            )
            db.add(risk)
            db.flush()
            rec.risk_level = _risk_level_max(rec.risk_level, risk_level)
            db.add(InternshipAuditTrail(
                tenant_id=_tid(), target_id=risk.id, target_type="RISK", action="CREATE_FROM_VISIT",
                operator_name=_op_name(user),
                detail_json={"visitId": str(visit.id), "riskLevel": risk_level, "reason": risk_reason[:200]},
                occurred_at=datetime.utcnow(),
            ))

        rec.version = current_version + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=visit.id, target_type="VISIT", action="CREATE_MOBILE_EVIDENCE",
            operator_name=_op_name(user),
            detail_json={
                "planId": str(plan.id),
                "planVersion": int(plan.version or 0),
                "batchId": str(rec.batch_id),
                "method": visit_type,
                "needFollow": need_follow,
                "needRisk": need_risk,
                "hasFile": bool(file_id),
                "teacherLocationCaptured": bool(encrypted_location),
                "internshipVersionBefore": current_version,
                "internshipVersionAfter": rec.version,
            },
            occurred_at=datetime.utcnow(),
        ))
        if has_rectify:
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.push_visit_rectify_todo(db, visit, rec)
        db.commit()
        return {
            "visitId": str(visit.id),
            "expectedVersion": int(rec.version),
            "rectifyStatus": visit.rectify_status,
            "riskId": str(risk.id) if risk else None,
            "riskLevel": risk.risk_level if risk else None,
            "locationCaptured": bool(encrypted_location),
        }
