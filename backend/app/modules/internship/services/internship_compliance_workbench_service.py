"""岗位实习合规办理工作台统一查询。

同一批次、同一数据范围返回知情确认、安全教育、特殊备案、事故应急、豁免和
证据包台账。前端不得再为每个标签各写一套统计或自行拼接状态。

U11（V9.3 首屏拆分）：`get_workbench()` 一次性把全部分组的完整列表拉出来，
首屏「待处理数量」是遍历这些已加载列表现算的——批次学生一多，首屏就跟着变慢。
拆成三层，counts 统一走 SQL COUNT，不再依赖任何一组已加载的列表：

- `get_workbench_summary()`：批次元信息 + 6 项统计数字，首屏只用这个。
- `get_workbench_group()`：按 Tab 单独加载一组明细，点开哪个 Tab 才请求哪组。
- `get_workbench()`：保留的一次性全量接口（旧调用方兜底），内部复用同一套
  `_counts()` / 分组取数函数，与前两者口径强制一致，不再各写一份。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from app.core.permissions import is_super_admin
from app.core.exceptions import AppException
from app.models import (
    InternshipAuditTrail, InternshipComplianceExemption, InternshipConsent,
    InternshipEmergencyPlan, InternshipEvidencePackage, InternshipIncident,
    InternshipRecord, InternshipSafetyCompletion, InternshipSafetyCourse,
    InternshipSpecialFiling,
)
from app.services.db_service import _iso, _tid, session

# 每个 Tab 对应的分组 key，供路由校验与前端约定。
GROUPS = ("consents", "safety", "filings", "incidents", "exemptions", "evidence")


def _role(user) -> str:
    return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or "").upper()


def _is_school_level(user) -> bool:
    return is_super_admin(user or {}) or _role(user) in {
        "SCHOOL_ADMIN", "INTERNSHIP_ADMIN", "INTERN_ADMIN",
    }


def _allowed_records(db, batch_id, user):
    """批次内当前用户可见的实习记录 + 学生主档映射。

    U11：这里原本逐行 `db.get(StudentProfile)`，并在 `_rec_in_scope` 里再逐行推导
    班级/学院名——随批次人数线性放大的 N+1。把 8 组明细列表拆掉之后，它会变成首屏
    唯一的瓶颈，等于优化白做。改用既有的批量预加载路径（看板早因同样原因迁移过，
    见 `_bulk_context` 的 docstring 与看板等价性回归），判定口径完全一致：
    `_rec_in_scope_pre` 与 `_rec_in_scope` 走同一个 `scope_match_row`，只是班级/学院名
    来自预载映射而不是逐行查库。

    两个 import 必须留在函数体内、按属性取用：`internship_advisor_identity_guard`
    会在装载时 monkeypatch 这两个函数（把导师授权硬化成只认 advisor_user_id），
    模块顶层 from-import 会把补丁前的旧实现固化下来，等于绕开该安全加固。
    """
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services import internship_service as domain_service
    batch = resolve_batch(db, batch_id)
    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id.desc())).all()
    scope = domain_service._current_scope(user)
    _rec_map, stu_map, class_name_map, college_name_map, stu_college_name_map = (
        domain_service._bulk_context(db, records, id_attr="id"))
    students = {}
    allowed = []
    for record in records:
        # 查不到学生主档的孤儿记录一律不放行，与改造前一致。
        student = stu_map.get(record.student_id)
        if student and domain_service._rec_in_scope_pre(
                scope, record, student, class_name_map, college_name_map,
                stu_college_name_map):
            allowed.append(record)
            students[record.student_id] = student
    return batch, allowed, students


def _student_meta(record, students):
    student = students.get(record.student_id)
    return {
        "internshipId": str(record.id),
        "studentId": str(record.student_id),
        "studentNo": student.student_no if student else "-",
        "studentName": student.real_name if student else "-",
        "classId": str(student.class_id or "") if student else "",
        "advisorName": record.advisor_name or "",
        "recordStatus": record.status,
    }


def _delivery_audit_map(db, consent_ids) -> dict[int, dict]:
    """最近一次监护人送达结果；只返回状态和非敏感原因。"""
    if not consent_ids:
        return {}
    rows = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "INTERNSHIP_CONSENT",
        InternshipAuditTrail.target_id.in_(consent_ids),
        InternshipAuditTrail.action.like("GUARDIAN_DELIVERY_%"),
    ).order_by(
        InternshipAuditTrail.occurred_at.desc(),
        InternshipAuditTrail.id.desc(),
    )).all()
    latest = {}
    for audit in rows:
        target_id = int(audit.target_id)
        if target_id in latest:
            continue
        detail = audit.detail_json if isinstance(audit.detail_json, dict) else {}
        latest[target_id] = {
            "status": str(detail.get("status") or audit.action.rsplit("_", 1)[-1] or "").upper(),
            "reason": str(detail.get("reason") or "")[:200],
        }
    return latest


# ═══ 分组明细：每组独立取数，供全量接口与按需加载接口共用 ═══

def _group_consents(db, record_map, students, record_ids) -> list[dict]:
    if not record_ids:
        return []
    rows = db.scalars(select(InternshipConsent).where(
        InternshipConsent.tenant_id == _tid(),
        InternshipConsent.internship_id.in_(record_ids),
        InternshipConsent.is_deleted.is_(False),
    ).order_by(InternshipConsent.id.desc())).all()
    delivery_map = _delivery_audit_map(db, [row.id for row in rows])
    out = []
    for row in rows:
        record = record_map.get(row.internship_id)
        if not record:
            continue
        delivery = delivery_map.get(int(row.id), {})
        derived_status = (
            "SENT" if row.delivery_channel == "SMS" and row.delivered_at
            else str(row.delivery_channel or "").removeprefix("SMS_")
        )
        out.append({
            **_student_meta(record, students),
            "id": str(row.id), "consentType": row.consent_type,
            "status": row.status, "contentVersion": row.content_version or "",
            "viewedAt": _iso(row.viewed_at), "confirmedAt": _iso(row.confirmed_at),
            "participantName": row.participant_name or "",
            "participantRelation": row.participant_relation or "",
            "contactMasked": row.contact_masked or "",
            "deliveryChannel": row.delivery_channel or "",
            "deliveryStatus": delivery.get("status") or derived_status or "NOT_SENT",
            "deliveryReason": delivery.get("reason") or "",
            "deliveredAt": _iso(row.delivered_at),
            "guardianTokenExpiresAt": _iso(row.guardian_token_expires_at),
            "version": int(row.version or 0),
        })
    return out


def _group_safety(db, batch, record_map, students, record_ids) -> tuple[list[dict], list[dict]]:
    course_rows = db.scalars(select(InternshipSafetyCourse).where(
        InternshipSafetyCourse.tenant_id == _tid(),
        InternshipSafetyCourse.batch_id == batch.id,
        InternshipSafetyCourse.is_deleted.is_(False),
    ).order_by(InternshipSafetyCourse.id.desc())).all()
    courses = [{
        "id": str(row.id), "title": row.title,
        "courseVersion": row.course_version, "status": row.status,
        "requiredMinutes": int(row.required_minutes or 0),
        "passingScore": int(row.passing_score or 0),
        "maxAttempts": int(row.max_attempts or 0),
        "requireCommitment": bool(row.require_commitment),
        "effectiveAt": _iso(row.effective_at),
        "version": int(row.version or 0),
    } for row in course_rows]
    course_map = {row.id: row for row in course_rows}

    completions = []
    if record_ids:
        rows = db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == _tid(),
            InternshipSafetyCompletion.internship_id.in_(record_ids),
            InternshipSafetyCompletion.is_deleted.is_(False),
        ).order_by(InternshipSafetyCompletion.id.desc())).all()
        for row in rows:
            record = record_map.get(row.internship_id)
            course = course_map.get(row.course_id)
            if not record:
                continue
            completions.append({
                **_student_meta(record, students),
                "id": str(row.id), "courseId": str(row.course_id),
                "courseTitle": course.title if course else "课程已变更",
                "courseVersion": row.course_version,
                "currentCourseVersion": course.course_version if course else "",
                "status": row.status, "studiedMinutes": int(row.studied_minutes or 0),
                "attemptCount": int(row.attempt_count or 0),
                "score": row.score, "commitmentConfirmed": bool(row.commitment_confirmed),
                "submittedAt": _iso(row.submitted_at),
                "reviewedByName": row.reviewed_by_name or "",
                "reviewedAt": _iso(row.reviewed_at),
                "version": int(row.version or 0),
            })
    return courses, completions


def _group_filings(db, record_map, students, record_ids) -> list[dict]:
    if not record_ids:
        return []
    rows = db.scalars(select(InternshipSpecialFiling).where(
        InternshipSpecialFiling.tenant_id == _tid(),
        InternshipSpecialFiling.internship_id.in_(record_ids),
        InternshipSpecialFiling.is_deleted.is_(False),
    ).order_by(InternshipSpecialFiling.id.desc())).all()
    out = []
    for row in rows:
        record = record_map.get(row.internship_id)
        if not record:
            continue
        out.append({
            **_student_meta(record, students),
            "id": str(row.id), "filingType": row.filing_type,
            "status": row.status, "triggerReason": row.trigger_reason or "",
            "destinationRegion": row.destination_region or "",
            "guardianConsentRequired": bool(row.guardian_consent_required),
            "collegeReviewBy": row.college_review_by or "",
            "collegeComment": row.college_comment or "",
            "schoolReviewBy": row.school_review_by or "",
            "schoolComment": row.school_comment or "",
            "fileIds": row.file_ids or [], "validUntil": _iso(row.valid_until),
            "version": int(row.version or 0),
        })
    return out


def _group_incidents(db, batch, record_map, students, user) -> list[dict]:
    rows = db.scalars(select(InternshipIncident).where(
        InternshipIncident.tenant_id == _tid(),
        InternshipIncident.batch_id == batch.id,
        InternshipIncident.is_deleted.is_(False),
    ).order_by(InternshipIncident.id.desc())).all()
    out = []
    school_level = _is_school_level(user)
    for row in rows:
        record = record_map.get(row.internship_id) if row.internship_id else None
        if not record and not school_level:
            continue
        meta = _student_meta(record, students) if record else {
            "internshipId": "", "studentId": str(row.student_id or ""),
            "studentNo": "-", "studentName": "批次/企业级事故",
            "classId": "", "advisorName": "", "recordStatus": "",
        }
        out.append({
            **meta, "id": str(row.id), "incidentNo": row.incident_no,
            "incidentType": row.incident_type, "severity": row.severity,
            "status": row.status, "occurredAt": _iso(row.occurred_at),
            "location": row.location or "", "summary": row.summary or "",
            "reportedByName": row.reported_by_name or "",
            "investigationConclusion": row.investigation_conclusion or "",
            "responsibilityConclusion": row.responsibility_conclusion or "",
            "rectificationPlan": row.rectification_plan or "",
            "fileIds": row.file_ids or [], "version": int(row.version or 0),
        })
    return out


def _group_emergency_plans(db, batch, user) -> list[dict]:
    if not (_is_school_level(user) or _role(user) == "COLLEGE_ADMIN"):
        return []
    rows = db.scalars(select(InternshipEmergencyPlan).where(
        InternshipEmergencyPlan.tenant_id == _tid(),
        InternshipEmergencyPlan.batch_id == batch.id,
        InternshipEmergencyPlan.is_deleted.is_(False),
    ).order_by(InternshipEmergencyPlan.id.desc())).all()
    return [{
        "id": str(row.id), "companyId": str(row.company_id or ""),
        "planName": row.plan_name, "responsiblePerson": row.responsible_person or "",
        "emergencyContact": row.emergency_contact or "",
        "backupContact": row.backup_contact or "",
        "hospitalOrSupport": row.hospital_or_support or "",
        "status": row.status, "validFrom": _iso(row.valid_from),
        "validUntil": _iso(row.valid_until), "fileIds": row.file_ids or [],
        "reviewedByName": row.reviewed_by_name or "",
        "version": int(row.version or 0),
    } for row in rows]


def _group_exemptions(db, record_map, students, record_ids) -> list[dict]:
    if not record_ids:
        return []
    rows = db.scalars(select(InternshipComplianceExemption).where(
        InternshipComplianceExemption.tenant_id == _tid(),
        InternshipComplianceExemption.internship_id.in_(record_ids),
        InternshipComplianceExemption.is_deleted.is_(False),
    ).order_by(InternshipComplianceExemption.id.desc())).all()
    out = []
    for row in rows:
        record = record_map.get(row.internship_id)
        if not record:
            continue
        out.append({
            **_student_meta(record, students),
            "id": str(row.id), "checkCode": row.check_code,
            "reason": row.reason, "status": row.status,
            "evidenceFileIds": row.evidence_file_ids or [],
            "validFrom": _iso(row.valid_from), "validUntil": _iso(row.valid_until),
            "requestedByName": row.requested_by_name or "",
            "reviewedByName": row.reviewed_by_name or "",
            "version": int(row.version or 0),
        })
    return out


def _group_evidence_packages(db, batch, record_ids, user) -> list[dict]:
    rows = db.scalars(select(InternshipEvidencePackage).where(
        InternshipEvidencePackage.tenant_id == _tid(),
        InternshipEvidencePackage.batch_id == batch.id,
        InternshipEvidencePackage.is_deleted.is_(False),
    ).order_by(
        InternshipEvidencePackage.generated_at.desc(),
        InternshipEvidencePackage.id.desc(),
    )).all()
    out = []
    record_id_set = set(record_ids)
    school_level = _is_school_level(user)
    for row in rows:
        if row.package_type in ("STUDENT", "ARCHIVE") and row.target_id not in record_id_set:
            continue
        if row.package_type in ("BATCH", "ENTERPRISE") and not school_level:
            continue
        out.append({
            "id": str(row.id), "packageType": row.package_type,
            "targetId": str(row.target_id), "packageVersion": int(row.package_version or 0),
            "status": row.status, "fileCount": int(row.file_count or 0),
            "rowCount": int(row.row_count or 0),
            "missingCount": len(row.missing_items or []),
            "packageSha256": row.package_sha256 or "",
            "packageSizeBytes": int(row.package_size_bytes or 0),
            "generatedByName": row.generated_by_name or "",
            "generatedAt": _iso(row.generated_at),
            "invalidatedAt": _iso(row.invalidated_at),
        })
    return out


# ═══ 统计：全部走 SQL COUNT，不依赖任何一组已加载的列表 ═══

def _counts(db, batch, record_ids, user) -> dict:
    tid = _tid()
    rid_filter = record_ids or [0]
    school_level = _is_school_level(user)

    def _count(model, *conds) -> int:
        return db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tid, model.is_deleted.is_(False), *conds)) or 0

    consent_pending = _count(
        InternshipConsent, InternshipConsent.internship_id.in_(rid_filter),
        InternshipConsent.status == "PENDING")

    safety_pending = _count(
        InternshipSafetyCompletion, InternshipSafetyCompletion.internship_id.in_(rid_filter),
        InternshipSafetyCompletion.status.in_(["PENDING_REVIEW", "IN_PROGRESS", "NOT_STARTED"]))

    filing_pending = _count(
        InternshipSpecialFiling, InternshipSpecialFiling.internship_id.in_(rid_filter),
        InternshipSpecialFiling.status.in_(["DRAFT", "PENDING_COLLEGE", "PENDING_SCHOOL"]))

    # 事故：非校级角色只能看见「关联记录在本人数据范围内」的事故；批次/企业级事故
    # （internship_id 为空）只对校级角色可见——与 _group_incidents 的可见性判断保持一致。
    incident_conds = [InternshipIncident.batch_id == batch.id, InternshipIncident.status != "CLOSED"]
    if not school_level:
        incident_conds.append(InternshipIncident.internship_id.in_(rid_filter))
    incident_open = _count(InternshipIncident, *incident_conds)

    exemption_pending = _count(
        InternshipComplianceExemption, InternshipComplianceExemption.internship_id.in_(rid_filter),
        InternshipComplianceExemption.status == "PENDING_REVIEW")

    # 证据包：学生/归档级需 target_id 落在本人数据范围；批次/企业级只对校级角色可见——
    # 与 _group_evidence_packages 的可见性判断保持一致。
    student_cond = and_(
        InternshipEvidencePackage.package_type.in_(["STUDENT", "ARCHIVE"]),
        InternshipEvidencePackage.target_id.in_(rid_filter))
    if school_level:
        visibility_cond = or_(student_cond, InternshipEvidencePackage.package_type.in_(["BATCH", "ENTERPRISE"]))
    else:
        visibility_cond = student_cond
    package_ready = _count(
        InternshipEvidencePackage, InternshipEvidencePackage.batch_id == batch.id,
        InternshipEvidencePackage.status.in_(["READY", "READY_WITH_MISSING"]), visibility_cond)

    return {
        "consentPending": consent_pending,
        "safetyPending": safety_pending,
        "filingPending": filing_pending,
        "incidentOpen": incident_open,
        "exemptionPending": exemption_pending,
        "packageReady": package_ready,
    }


def _batch_meta(batch, record_count) -> dict:
    return {
        "id": str(batch.id), "name": batch.batch_name,
        "status": batch.status, "studentCount": record_count,
    }


def get_workbench_summary(batch_id, user=None) -> dict:
    """首屏：批次信息 + 6 项统计数字。不加载任何一组的完整明细列表。"""
    with session() as db:
        batch, records, _students = _allowed_records(db, batch_id, user)
        record_ids = [r.id for r in records]
        return {
            "batch": _batch_meta(batch, len(records)),
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "counts": _counts(db, batch, record_ids, user),
        }


def get_workbench_group(batch_id, group: str, user=None) -> dict:
    """按 Tab 懒加载单个分组的明细列表。"""
    if group not in GROUPS:
        raise AppException("VALIDATION_ERROR", f"未知的合规工作台分组：{group}")
    with session() as db:
        batch, records, students = _allowed_records(db, batch_id, user)
        record_map = {record.id: record for record in records}
        record_ids = list(record_map)

        if group == "consents":
            return {"consents": _group_consents(db, record_map, students, record_ids)}
        if group == "safety":
            courses, completions = _group_safety(db, batch, record_map, students, record_ids)
            return {"safetyCourses": courses, "safetyCompletions": completions}
        if group == "filings":
            return {"filings": _group_filings(db, record_map, students, record_ids)}
        if group == "incidents":
            return {
                "incidents": _group_incidents(db, batch, record_map, students, user),
                "emergencyPlans": _group_emergency_plans(db, batch, user),
            }
        if group == "exemptions":
            return {"exemptions": _group_exemptions(db, record_map, students, record_ids)}
        return {"evidencePackages": _group_evidence_packages(db, batch, record_ids, user)}


def get_workbench(batch_id, user=None) -> dict:
    """旧的一次性全量接口，仍保留给未迁移的调用方；内部与 summary/group 共用同一套取数
    和统计函数，口径强制一致，不会出现"页面一个数、导出/旧接口另一个数"。"""
    with session() as db:
        batch, records, students = _allowed_records(db, batch_id, user)
        record_map = {record.id: record for record in records}
        record_ids = list(record_map)

        consent_rows = _group_consents(db, record_map, students, record_ids)
        courses, safety_rows = _group_safety(db, batch, record_map, students, record_ids)
        filing_rows = _group_filings(db, record_map, students, record_ids)
        incident_rows = _group_incidents(db, batch, record_map, students, user)
        emergency_rows = _group_emergency_plans(db, batch, user)
        exemption_rows = _group_exemptions(db, record_map, students, record_ids)
        package_rows = _group_evidence_packages(db, batch, record_ids, user)

        return {
            "batch": _batch_meta(batch, len(records)),
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "consents": consent_rows,
            "safetyCourses": courses,
            "safetyCompletions": safety_rows,
            "filings": filing_rows,
            "incidents": incident_rows,
            "emergencyPlans": emergency_rows,
            "exemptions": exemption_rows,
            "evidencePackages": package_rows,
            "counts": _counts(db, batch, record_ids, user),
        }
