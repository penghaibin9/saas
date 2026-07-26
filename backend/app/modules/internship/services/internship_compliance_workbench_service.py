"""岗位实习合规办理工作台统一查询。

同一批次、同一数据范围返回知情确认、安全教育、特殊备案、事故应急、豁免和
证据包台账。前端不得再为每个标签各写一套统计或自行拼接状态。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.permissions import is_super_admin
from app.models import (
    InternshipComplianceExemption, InternshipConsent, InternshipEmergencyPlan,
    InternshipEvidencePackage, InternshipIncident, InternshipRecord,
    InternshipSafetyCompletion, InternshipSafetyCourse, InternshipSpecialFiling,
    StudentProfile,
)
from app.services.db_service import _iso, _tid, session


def _role(user) -> str:
    return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or "").upper()


def _is_school_level(user) -> bool:
    return is_super_admin(user or {}) or _role(user) in {
        "SCHOOL_ADMIN", "INTERNSHIP_ADMIN", "INTERN_ADMIN",
    }


def _allowed_records(db, batch_id, user):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    batch = resolve_batch(db, batch_id)
    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id.desc())).all()
    scope = _current_scope(user)
    students = {}
    allowed = []
    for record in records:
        student = db.get(StudentProfile, record.student_id)
        if student and _rec_in_scope(scope, db, record, student):
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


def get_workbench(batch_id, user=None) -> dict:
    with session() as db:
        batch, records, students = _allowed_records(db, batch_id, user)
        record_map = {record.id: record for record in records}
        record_ids = list(record_map)
        student_ids = list(students)

        consent_rows = []
        if record_ids:
            rows = db.scalars(select(InternshipConsent).where(
                InternshipConsent.tenant_id == _tid(),
                InternshipConsent.internship_id.in_(record_ids),
                InternshipConsent.is_deleted.is_(False),
            ).order_by(InternshipConsent.id.desc())).all()
            for row in rows:
                record = record_map.get(row.internship_id)
                if not record:
                    continue
                consent_rows.append({
                    **_student_meta(record, students),
                    "id": str(row.id), "consentType": row.consent_type,
                    "status": row.status, "contentVersion": row.content_version or "",
                    "viewedAt": _iso(row.viewed_at), "confirmedAt": _iso(row.confirmed_at),
                    "participantName": row.participant_name or "",
                    "participantRelation": row.participant_relation or "",
                    "contactMasked": row.contact_masked or "",
                    "deliveryChannel": row.delivery_channel or "",
                    "deliveredAt": _iso(row.delivered_at),
                    "guardianTokenExpiresAt": _iso(row.guardian_token_expires_at),
                    "version": int(row.version or 0),
                })

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

        safety_rows = []
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
                safety_rows.append({
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

        filing_rows = []
        if record_ids:
            rows = db.scalars(select(InternshipSpecialFiling).where(
                InternshipSpecialFiling.tenant_id == _tid(),
                InternshipSpecialFiling.internship_id.in_(record_ids),
                InternshipSpecialFiling.is_deleted.is_(False),
            ).order_by(InternshipSpecialFiling.id.desc())).all()
            for row in rows:
                record = record_map.get(row.internship_id)
                if not record:
                    continue
                filing_rows.append({
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

        incident_rows = []
        incident_query = select(InternshipIncident).where(
            InternshipIncident.tenant_id == _tid(),
            InternshipIncident.batch_id == batch.id,
            InternshipIncident.is_deleted.is_(False),
        )
        rows = db.scalars(incident_query.order_by(InternshipIncident.id.desc())).all()
        for row in rows:
            record = record_map.get(row.internship_id) if row.internship_id else None
            if not record and not _is_school_level(user):
                continue
            meta = _student_meta(record, students) if record else {
                "internshipId": "", "studentId": str(row.student_id or ""),
                "studentNo": "-", "studentName": "批次/企业级事故",
                "classId": "", "advisorName": "", "recordStatus": "",
            }
            incident_rows.append({
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

        emergency_rows = []
        if _is_school_level(user) or _role(user) == "COLLEGE_ADMIN":
            rows = db.scalars(select(InternshipEmergencyPlan).where(
                InternshipEmergencyPlan.tenant_id == _tid(),
                InternshipEmergencyPlan.batch_id == batch.id,
                InternshipEmergencyPlan.is_deleted.is_(False),
            ).order_by(InternshipEmergencyPlan.id.desc())).all()
            emergency_rows = [{
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

        exemption_rows = []
        if record_ids:
            rows = db.scalars(select(InternshipComplianceExemption).where(
                InternshipComplianceExemption.tenant_id == _tid(),
                InternshipComplianceExemption.internship_id.in_(record_ids),
                InternshipComplianceExemption.is_deleted.is_(False),
            ).order_by(InternshipComplianceExemption.id.desc())).all()
            for row in rows:
                record = record_map.get(row.internship_id)
                if not record:
                    continue
                exemption_rows.append({
                    **_student_meta(record, students),
                    "id": str(row.id), "checkCode": row.check_code,
                    "reason": row.reason, "status": row.status,
                    "evidenceFileIds": row.evidence_file_ids or [],
                    "validFrom": _iso(row.valid_from), "validUntil": _iso(row.valid_until),
                    "requestedByName": row.requested_by_name or "",
                    "reviewedByName": row.reviewed_by_name or "",
                    "version": int(row.version or 0),
                })

        package_rows = []
        rows = db.scalars(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.batch_id == batch.id,
            InternshipEvidencePackage.is_deleted.is_(False),
        ).order_by(
            InternshipEvidencePackage.generated_at.desc(),
            InternshipEvidencePackage.id.desc(),
        )).all()
        for row in rows:
            if row.package_type in ("STUDENT", "ARCHIVE") and row.target_id not in record_ids:
                continue
            if row.package_type in ("BATCH", "ENTERPRISE") and not _is_school_level(user):
                continue
            package_rows.append({
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

        return {
            "batch": {
                "id": str(batch.id), "name": batch.batch_name,
                "status": batch.status, "studentCount": len(records),
            },
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "consents": consent_rows,
            "safetyCourses": courses,
            "safetyCompletions": safety_rows,
            "filings": filing_rows,
            "incidents": incident_rows,
            "emergencyPlans": emergency_rows,
            "exemptions": exemption_rows,
            "evidencePackages": package_rows,
            "counts": {
                "consentPending": sum(1 for row in consent_rows if row["status"] == "PENDING"),
                "safetyPending": sum(1 for row in safety_rows if row["status"] in ("PENDING_REVIEW", "IN_PROGRESS", "NOT_STARTED")),
                "filingPending": sum(1 for row in filing_rows if row["status"] in ("DRAFT", "PENDING_COLLEGE", "PENDING_SCHOOL")),
                "incidentOpen": sum(1 for row in incident_rows if row["status"] != "CLOSED"),
                "exemptionPending": sum(1 for row in exemption_rows if row["status"] == "PENDING_REVIEW"),
                "packageReady": sum(1 for row in package_rows if row["status"] in ("READY", "READY_WITH_MISSING")),
            },
        }
