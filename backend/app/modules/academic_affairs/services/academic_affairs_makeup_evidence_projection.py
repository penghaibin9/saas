"""PC-C05 evidence projected only from already-authorized application rows.

No course-name joins, audit-detail parsing, file URLs, or inferred historical
roster versions. Missing lineage remains explicit and cannot authorize a write.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json

from sqlalchemy import func, select

from app.core.permissions import has_permission
from app.models import (
    AaCourse, AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion,
    AcademicGrade, AcademicStudent,
)
from app.models.academic_affairs_effective_grade import AaGradeCorrection
from app.services.db_service import _tid

from . import academic_affairs_exemption_evidence_service as evidence
from . import academic_affairs_makeup_core_service as core


def _visible(model):
    return model.tenant_id == _tid(), model.is_deleted.is_(False)


def _id(value):
    return str(value) if value else None


def _iso(value):
    return value.isoformat() if value else None


def _rows(db, model, ids, *, lock=False):
    ids = {int(value) for value in ids if value}
    if not ids:
        return {}
    query = select(model).where(model.id.in_(ids), *_visible(model)).order_by(model.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return {int(row.id): row for row in db.scalars(query).all()}


def grade_dto(grade):
    if grade is None:
        return None
    return {
        "gradeId": str(grade.id), "gradeRowVersion": int(grade.version or 0), "score": grade.score,
        "passStatus": grade.pass_status, "recordStatus": grade.record_status,
        "courseId": _id(grade.course_id), "courseCode": grade.course_code, "courseVersion": grade.course_version,
        "attemptNo": grade.attempt_no, "source": grade.source,
        "sourceBizType": grade.source_biz_type, "sourceBizId": _id(grade.source_biz_id),
        "effectivePolicyCode": grade.effective_policy_code, "effectivePolicyVersion": grade.effective_policy_version,
        "effectiveAttemptStrategy": grade.effective_attempt_strategy,
        "passLineSnapshot": grade.pass_line_snapshot, "gradeTaskId": _id(grade.grade_task_id),
        "gradeRecordId": _id(grade.grade_record_id), "rosterVersionId": _id(grade.roster_version_id),
    }


def grade_evidence_hash(grade):
    if grade is None:
        return None
    payload = json.dumps(grade_dto(grade), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grade_chains(db, root_ids, *, lock=False):
    """Batch-expand explicit correction edges; ambiguity/cycles fail closed."""
    roots = {int(value) for value in root_ids if value}
    grades, edges = {}, defaultdict(list)
    frontier = roots
    for _ in range(64):
        frontier = frontier - grades.keys()
        if not frontier:
            break
        loaded = _rows(db, AcademicGrade, frontier, lock=lock)
        grades.update(loaded)
        edge_query = select(AaGradeCorrection).where(
            AaGradeCorrection.original_grade_id.in_(frontier), *_visible(AaGradeCorrection),
        ).order_by(AaGradeCorrection.id)
        if lock:
            edge_query = edge_query.with_for_update().execution_options(populate_existing=True)
        corrections = db.scalars(edge_query).all()
        for correction in corrections:
            edges[int(correction.original_grade_id)].append(correction)
        frontier = {int(c.corrected_grade_id) for c in corrections if c.corrected_grade_id}
    results = {}
    for root in roots:
        original = grades.get(root)
        current, seen = original, set()
        state = "CHAIN_INVALID"
        while current and current.id not in seen:
            seen.add(current.id)
            links = edges.get(current.id, [])
            if current.record_status == "ACTIVE":
                if not links:
                    state = "RESOLVED"
                break
            if current.record_status != "SUPERSEDED" or len(links) != 1 or links[0].status != "ACTIVE":
                break
            next_grade = grades.get(links[0].corrected_grade_id)
            if (not next_grade or next_grade.acad_student_id != original.acad_student_id
                    or next_grade.course_id != original.course_id
                    or next_grade.course_code != original.course_code
                    or next_grade.course_version != original.course_version
                    or next_grade.attempt_no != original.attempt_no):
                break
            current = next_grade
        results[root] = (original, current if state == "RESOLVED" else None, state)
    return results


def retake_sources(db, rows, user):
    from . import academic_affairs_makeup_service as public

    ctx = core._ctx(user, db)
    school_review = ctx.scope_type == "TENANT_ALL" and has_permission(user, "academicAffairs.retake.review")
    chains = grade_chains(db, [row.origin_grade_id for row in rows])
    students = _rows(db, AcademicStudent, [row.acad_student_id for row in rows])
    active_by_student = defaultdict(list)
    if students:
        for grade in db.scalars(select(AcademicGrade).where(
            AcademicGrade.acad_student_id.in_(students), AcademicGrade.record_status == "ACTIVE", *_visible(AcademicGrade),
        )).all():
            active_by_student[grade.acad_student_id].append(grade)
    effective_failed = {
        sid: {int(g.id) for g in public._effective_failed_rows(items)}
        for sid, items in active_by_student.items()
    }
    versions = _rows(db, AaTeachingClassRosterVersion, [row.enrollment_roster_version_id for row in rows])
    classes = _rows(db, AaTeachingClass, [version.teaching_class_id for version in versions.values()])
    members = set(db.execute(select(AaTeachingClassMember.roster_version_id, AaTeachingClassMember.student_id).where(
        AaTeachingClassMember.roster_version_id.in_(versions), *_visible(AaTeachingClassMember),
    )).all()) if versions else set()
    results = {}
    for row in rows:
        original, current, state = chains.get(row.origin_grade_id, (None, None, "SOURCE_GRADE_UNRESOLVED"))
        student = students.get(row.acad_student_id)
        if (original and (not student or student.student_id != row.student_id
                          or original.acad_student_id != row.acad_student_id
                          or not row.course_id or original.course_id != row.course_id)):
            original, current, state = None, None, "CHAIN_INVALID"
        blockers = []
        if state != "RESOLVED":
            blockers.append("来源正式成绩尚无可靠回链，禁止按课程名或审计文本猜配")
        elif (current.id not in effective_failed.get(row.acad_student_id, set())
              or not all((current.course_id, current.course_code, current.course_version, current.attempt_no))):
            state = "NOT_EFFECTIVE_FAILED"
            blockers.append("来源后继成绩已不是具有完整课程身份的当前有效挂科结果")
        actions = []
        if school_review:
            if row.status in {core._RT_SUBMITTED, core._RT_REVIEW}:
                actions = (["APPROVE"] if state == "RESOLVED" else []) + ["REJECT"]
            elif row.status == core._RT_APPROVED and state == "RESOLVED":
                actions = ["ENROLL"]
        version = versions.get(row.enrollment_roster_version_id)
        classroom = classes.get(version.teaching_class_id) if version else None
        enrolled = bool(version and classroom and classroom.teaching_task_id == row.teaching_task_ref
                        and (version.id, row.student_id) in members)
        results[row.id] = {
            "applicationVersion": int(row.version or 0), "appliedAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
            "courseId": _id(row.course_id), "teachingTaskId": _id(row.teaching_task_ref),
            "workflowInstanceId": _id(row.workflow_instance_id),
            "originGrade": grade_dto(original), "currentGrade": grade_dto(current),
            "sourceGradeState": state, "sourceGradeBlockers": blockers, "allowedActions": actions,
            "sourceEvidenceHash": grade_evidence_hash(current) if state == "RESOLVED" else None,
            "enrollment": {
                "teachingTaskId": _id(row.teaching_task_ref), "teachingClassId": _id(classroom.id) if enrolled else None,
                "rosterVersionId": _id(version.id) if enrolled else None,
                "rosterVersionNo": version.version_no if enrolled else None,
                "rosterCoverage": "FROZEN_AT_ENROLLMENT" if enrolled else "UNRESOLVED",
            },
        }
    return results


def _material_projection(db, row):
    from app.models.file import FileBinding

    checked = evidence.verify_manifest(db, row, kind="EXEMPTION")
    frozen = checked["entries"]
    if not frozen:
        return {"evidenceManifestHash": row.evidence_manifest_hash,
                "evidenceCount": None if checked["problems"] else 0,
                "evidenceFiles": [], "evidenceState": "INVALID" if checked["problems"] else "MISSING",
                "evidenceProblems": checked["problems"] or ["没有可读取的申请时冻结材料清单"]}
    if any(not isinstance(item, dict) or not str(item.get("fileId", "")).isdigit()
           or not str(item.get("bindingId", "")).isdigit()
           or int(item["fileId"]) <= 0 or int(item["bindingId"]) <= 0 for item in frozen):
        return {"evidenceManifestHash": row.evidence_manifest_hash, "evidenceCount": None,
                "evidenceFiles": [], "evidenceState": "INVALID", "evidenceProblems": ["冻结材料清单结构损坏"]}
    bindings = _rows(db, FileBinding, [item["bindingId"] for item in frozen])
    files = []
    for item in frozen:
        binding = bindings.get(int(item["bindingId"]))
        same_binding = bool(binding and str(binding.biz_type).upper() == "AA_EXEMPTION"
                            and str(binding.biz_id) == str(row.id) and str(binding.file_id) == str(item["fileId"]))
        files.append({
            "frozenBindingId": str(item["bindingId"]), "fileId": str(item["fileId"]),
            "fileName": item.get("fileName"), "frozenFileObjectVersion": item.get("fileVersion"),
            "sha256": item.get("sha256"), "boundAt": item.get("boundAt"),
            "fileVersionId": None, "fileVersionNo": None, "versionCoverage": "FILE_OBJECT_SNAPSHOT_ONLY",
            "bindingStatus": binding.status if same_binding else None,
            "isCurrent": bool(binding.is_current) if same_binding else None,
            "bindingVersionNo": binding.version_no if same_binding else None,
        })
    problems = list(checked["problems"])
    return {"evidenceManifestHash": row.evidence_manifest_hash, "evidenceCount": len(frozen),
            "evidenceFiles": files, "evidenceState": "INVALID" if problems else "VALID", "evidenceProblems": problems}


def exemption_sources(db, rows, *, archive=False):
    from app.models import AffairsAuditTrail

    if not rows:
        return {}
    courses = _rows(db, AaCourse, [row.course_id for row in rows])
    result_by_apply = defaultdict(list)
    for grade in db.scalars(select(AcademicGrade).where(
        AcademicGrade.source_biz_type == "EXEMPTION", AcademicGrade.source_biz_id.in_([row.id for row in rows]),
        *_visible(AcademicGrade),
    )).all():
        result_by_apply[grade.source_biz_id].append(grade)
    chains = grade_chains(db, [grade.id for grades in result_by_apply.values() for grade in grades])
    students = _rows(db, AcademicStudent, [grade.acad_student_id for grades in result_by_apply.values() for grade in grades])
    operations = {}
    if archive:
        ranked = select(AffairsAuditTrail.id, func.row_number().over(
            partition_by=AffairsAuditTrail.biz_id,
            order_by=(AffairsAuditTrail.occurred_at.desc(), AffairsAuditTrail.id.desc()),
        ).label("rn")).where(
            AffairsAuditTrail.biz_type == "AA_EXEMPTION", AffairsAuditTrail.action == "EXEMPTION_ARCHIVE",
            AffairsAuditTrail.biz_id.in_([row.id for row in rows]), AffairsAuditTrail.tenant_id == _tid(),
        ).subquery()
        for operation in db.scalars(select(AffairsAuditTrail).join(ranked, ranked.c.id == AffairsAuditTrail.id).where(ranked.c.rn == 1)).all():
            operations[int(operation.biz_id)] = {"action": operation.action, "operator": operation.operator,
                                                "role": operation.role_name, "occurredAt": _iso(operation.occurred_at)}
    results = {}
    for row in rows:
        course = courses.get(row.course_id)
        origins = result_by_apply.get(row.id, [])
        original, current, state = None, None, "SOURCE_GRADE_UNRESOLVED" if row.status == "APPROVED" else "NOT_GENERATED"
        if len(origins) == 1:
            original, current, state = chains[origins[0].id]
            student = students.get(original.acad_student_id)
            if not student or student.student_id != row.student_id or original.course_id != row.course_id:
                original, current, state = None, None, "CHAIN_INVALID"
        elif origins:
            state = "CHAIN_INVALID"
        dto = {
            "exemptionVersion": int(row.version or 0), "appliedAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
            "course": {"id": _id(row.course_id), "code": course.course_code if course else None,
                       "version": course.version if course else None, "name": row.course_name},
            "resultGrade": grade_dto(original), "currentGrade": grade_dto(current), "resultGradeState": state,
            **_material_projection(db, row),
        }
        if archive:
            dto["archiveOperation"] = operations.get(row.id)
        results[row.id] = dto
    return results
