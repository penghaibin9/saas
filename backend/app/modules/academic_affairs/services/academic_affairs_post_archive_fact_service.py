"""Stage C3 domain commands consumed by an approved PostArchiveCorrectionCase.

This module is the *only* write-after-ARCHIVED exception for the first production
scope (GRADE / GRADUATION / SCHEDULE).  It never reopens the term and never overwrites the old
official fact:

* GRADE: ACTIVE AcademicGrade -> SUPERSEDED + new ACTIVE AcademicGrade, with the
  existing AaGradeCorrection/effective-policy evidence chain and aggregate projection
  refreshed in the same transaction.
* GRADUATION: new immutable GraduationEvaluationRun + GraduationDecisionFact#N+1 that
  supersedes the prior decision.  The archived result row remains an ARCHIVED
  projection; StudentAcademicFact is advanced only when the corrected final status
  actually changes.
* SCHEDULE: complete replacement AaScheduleBatch + AaScheduleItem facts are appended;
  the previous batch becomes SUPERSEDED and the scope head advances atomically.

The caller owns commit/rollback and Manifest V2+ creation, so domain fact + correction
case + manifest revision are atomic.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid


def _json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _target_id(value) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "归档后纠错 targetRef 必须是正式事实 ID") from exc
    if parsed <= 0:
        raise AppException("VALIDATION_ERROR", "归档后纠错 targetRef 必须是正整数正式事实 ID")
    return parsed


def _correction(case) -> dict:
    try:
        payload = json.loads(case.correction_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppException("DATA_CONFLICT", "归档后纠错内容 JSON 已损坏，拒绝应用", http_status=409) from exc
    if not isinstance(payload, dict) or not payload:
        raise AppException("DATA_CONFLICT", "归档后纠错内容为空，拒绝应用", http_status=409)
    return payload


def _term_code(db, batch) -> str | None:
    if str(getattr(batch, "term_code", None) or "").strip():
        return str(batch.term_code).strip()
    if not getattr(batch, "term_id", None):
        return None
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.id == int(batch.term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return None
    return f"{term.year_code}-{term.term_no}"


def _grade_snapshot(row) -> dict:
    return {
        "gradeId": str(row.id),
        "acadStudentId": str(row.acad_student_id),
        "courseId": str(row.course_id) if getattr(row, "course_id", None) is not None else None,
        "courseCode": getattr(row, "course_code", None),
        "courseVersion": getattr(row, "course_version", None),
        "attemptNo": getattr(row, "attempt_no", None),
        "gradeRecordId": str(row.grade_record_id) if getattr(row, "grade_record_id", None) is not None else None,
        "term": row.term,
        "score": row.score,
        "passStatus": row.pass_status,
        "recordStatus": row.record_status,
        "effectivePolicyCode": getattr(row, "effective_policy_code", None),
        "effectivePolicyVersion": getattr(row, "effective_policy_version", None),
        "attemptStrategy": getattr(row, "effective_attempt_strategy", None),
        "passLineSnapshot": getattr(row, "pass_line_snapshot", None),
        "gpaPoint": float(row.gpa_point) if getattr(row, "gpa_point", None) is not None else None,
        "gpaPolicyCode": getattr(row, "gpa_policy_code", None),
        "gpaPolicyVersion": getattr(row, "gpa_policy_version", None),
    }


def _copy_grade_payload(original) -> dict:
    excluded = {
        "id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by",
        "is_deleted", "version", "score", "pass_status", "record_status", "void_reason",
        "source", "source_biz_type", "source_biz_id", "active_record_key",
        "gpa_point", "gpa_policy_code", "gpa_policy_version",
    }
    payload = {}
    for column in original.__table__.columns:
        if column.name in excluded:
            continue
        payload[column.name] = getattr(original, column.name)
    return payload


def _pass_line(db, grade, correction: dict) -> int:
    raw = getattr(grade, "pass_line_snapshot", None)
    if raw is None and getattr(grade, "grade_task_id", None):
        from app.models import AaGradeTask

        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(grade.grade_task_id),
            AaGradeTask.tenant_id == _tid(),
            AaGradeTask.is_deleted.is_(False),
        ).first()
        raw = getattr(task, "pass_line", None) if task else None
    if raw is None:
        raw = correction.get("passLine")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppException(
            "DATA_CONFLICT",
            "原正式成绩缺少冻结及格线；纠错必须显式提供 passLine 后再二次审批",
            http_status=409,
        ) from exc
    if not 0 <= value <= 100:
        raise AppException("VALIDATION_ERROR", "passLine 必须在 0-100")
    return value


def _score(correction: dict) -> int:
    raw = correction.get("score")
    if raw is None:
        raise AppException("VALIDATION_ERROR", "GRADE 归档后纠错必须提供 score")
    try:
        numeric = float(raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "纠错 score 必须是 0-100 的整数") from exc
    if not numeric.is_integer() or not 0 <= numeric <= 100:
        raise AppException("VALIDATION_ERROR", "纠错 score 必须是 0-100 的整数")
    return int(numeric)


def _recalculate_same_gpa_policy(db, original, corrected, score: int) -> None:
    code = getattr(original, "gpa_policy_code", None)
    version = getattr(original, "gpa_policy_version", None)
    point = getattr(original, "gpa_point", None)
    if point is not None and (not code or version is None):
        raise AppException(
            "DATA_CONFLICT",
            "原成绩已有冻结绩点但缺少策略版本，无法安全重算归档后成绩",
            details={"gradeId": str(original.id)},
            http_status=409,
        )
    if not code or version is None:
        return
    from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy
    from .academic_affairs_gpa_policy_service import evaluate_policy

    policy = db.query(AaGpaPointPolicy).filter(
        AaGpaPointPolicy.tenant_id == _tid(),
        AaGpaPointPolicy.policy_code == str(code),
        AaGpaPointPolicy.policy_version == int(version),
        AaGpaPointPolicy.is_deleted.is_(False),
    ).first()
    if not policy:
        raise AppException(
            "DATA_CONFLICT",
            "原成绩冻结的绩点策略版本不存在，拒绝用当前策略重算历史成绩",
            details={"gradeId": str(original.id), "policyCode": str(code), "policyVersion": int(version)},
            http_status=409,
        )
    corrected.gpa_point = evaluate_policy(policy, score)
    corrected.gpa_policy_code = str(code)
    corrected.gpa_policy_version = int(version)


def _apply_grade(db, batch, case, actor: int) -> dict:
    from app.models import AaGradeCorrection, AaGradeRecord, AcademicGrade, AcademicStudent
    from . import academic_affairs_grade_service as grade_service
    from .academic_affairs_effective_grade_policy_service import freeze_effective_grade_policy

    target_id = _target_id(case.target_ref)
    original = db.query(AcademicGrade).filter(
        AcademicGrade.id == target_id,
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.is_deleted.is_(False),
    ).with_for_update().first()
    if not original:
        raise not_found("待纠错正式成绩不存在")
    if str(original.record_status or "").upper() != "ACTIVE":
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "待纠错成绩已不是当前 ACTIVE 正式事实，请基于最新成绩重新发起纠错",
            details={"gradeId": str(original.id), "recordStatus": original.record_status},
            http_status=409,
        )
    expected_term = _term_code(db, batch)
    if not expected_term or str(original.term or "").strip() != expected_term:
        raise AppException(
            "DATA_CONFLICT",
            "待纠错成绩不属于该归档批次学期，已拒绝跨学期纠错",
            details={"gradeId": str(original.id), "gradeTerm": original.term, "archiveTerm": expected_term},
            http_status=409,
        )

    correction = _correction(case)
    score = _score(correction)
    pass_line = _pass_line(db, original, correction)
    pass_status = "PASSED" if score >= pass_line else "FAILED"
    before = _grade_snapshot(original)
    if int(original.score) == score if original.score is not None else False:
        if str(original.pass_status or "").upper() == pass_status:
            raise AppException("DATA_CONFLICT", "归档后成绩纠错没有产生正式事实变化", http_status=409)

    corrected = AcademicGrade(
        tenant_id=_tid(),
        **_copy_grade_payload(original),
        score=score,
        pass_status=pass_status,
        record_status="ACTIVE",
        source="POST_ARCHIVE",
        source_biz_type="POST_ARCHIVE",
        source_biz_id=int(case.id),
        created_by=actor,
        updated_by=actor,
    )
    _recalculate_same_gpa_policy(db, original, corrected, score)

    original.record_status = "SUPERSEDED"
    original.void_reason = f"归档后纠错 case={case.id}"
    original.updated_by = actor
    db.flush()  # release active_record_key before the replacement claims it
    db.add(corrected)
    db.flush()
    original.void_reason = f"归档后纠错 superseded_by={corrected.id};case={case.id}"

    correction_fact = AaGradeCorrection(
        tenant_id=_tid(),
        source_type="POST_ARCHIVE",
        source_ref_id=int(case.id),
        original_grade_id=int(original.id),
        corrected_grade_id=int(corrected.id),
        before_score=original.score,
        after_score=score,
        pass_line=pass_line,
        rule_snapshot_json=_json({
            "archiveBatchId": str(batch.id),
            "correctionCaseId": str(case.id),
            "effectivePolicyCode": getattr(corrected, "effective_policy_code", None),
            "effectivePolicyVersion": getattr(corrected, "effective_policy_version", None),
            "attemptStrategy": getattr(corrected, "effective_attempt_strategy", None),
            "gpaPolicyCode": getattr(corrected, "gpa_policy_code", None),
            "gpaPolicyVersion": getattr(corrected, "gpa_policy_version", None),
        }),
        reason=case.reason,
        operator=str(actor),
        effective_at=datetime.utcnow(),
        status="ACTIVE",
        created_by=actor,
        updated_by=actor,
    )
    db.add(correction_fact)
    db.flush()
    freeze_effective_grade_policy(
        db,
        corrected,
        event_type="CHANGE",
        source_biz_type="POST_ARCHIVE",
        source_biz_id=int(case.id),
    )

    if getattr(original, "grade_record_id", None):
        record = db.query(AaGradeRecord).filter(
            AaGradeRecord.id == int(original.grade_record_id),
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record or (record.acad_grade_id and int(record.acad_grade_id) != int(original.id)):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "成绩录入投影已偏离待纠错正式成绩，拒绝覆盖",
                details={"gradeRecordId": str(original.grade_record_id), "gradeId": str(original.id)},
                http_status=409,
            )
        record.total_score = score
        record.pass_status = pass_status
        record.acad_grade_id = corrected.id
        if hasattr(record, "source"):
            record.source = "CHANGE"
        if hasattr(record, "change_reason"):
            record.change_reason = f"归档后纠错：{case.reason}"[:500]
        if hasattr(record, "change_at"):
            record.change_at = datetime.utcnow()
        if hasattr(record, "change_by"):
            record.change_by = actor
        if hasattr(record, "version_no"):
            record.version_no = int(record.version_no or 1) + 1
        record.updated_by = actor

    academic_student = db.query(AcademicStudent).filter(
        AcademicStudent.id == int(original.acad_student_id),
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.is_deleted.is_(False),
    ).with_for_update().first()
    if not academic_student:
        raise AppException("DATA_CONFLICT", "正式成绩对应学业台账不存在，拒绝产生半成功纠错", http_status=409)
    grade_service._refresh_aggregates(db, academic_student)
    db.flush()
    after = _grade_snapshot(corrected)
    return {
        "factType": "ACADEMIC_GRADE",
        "factId": int(corrected.id),
        "beforeHash": _hash(before),
        "afterHash": _hash(after),
        "snapshot": after,
        "lineage": {
            "originalGradeId": str(original.id),
            "correctedGradeId": str(corrected.id),
            "gradeCorrectionId": str(correction_fact.id),
        },
    }


def _term_bounds(db, batch):
    if not getattr(batch, "term_id", None):
        return None, None
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.id == int(batch.term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)
    ).first()
    if not term or not term.start_date or not term.end_date:
        return None, None
    start = term.start_date if isinstance(term.start_date, datetime) else datetime.combine(term.start_date, time.min)
    end = term.end_date if isinstance(term.end_date, datetime) else datetime.combine(term.end_date, time.max)
    return start, end


def _decision_snapshot(row) -> dict:
    return {
        "decisionId": str(row.id),
        "resultId": str(row.result_id),
        "studentId": str(row.student_id),
        "decisionNo": int(getattr(row, "decision_no", None) or 1),
        "evaluationRunId": str(row.evaluation_run_id),
        "conclusion": row.conclusion,
        "supersedesId": str(row.supersedes_id) if getattr(row, "supersedes_id", None) else None,
        "correctionCaseId": str(row.correction_case_id) if getattr(row, "correction_case_id", None) else None,
        "decisionAt": row.decision_at.isoformat() if row.decision_at else None,
    }


def _apply_graduation(db, batch, case, actor: int) -> dict:
    from app.models import (
        AaGraduationAuditBatch,
        AaGraduationAuditResult,
        GraduationDecisionFact,
        GraduationEvaluationRun,
        StudentProfile,
    )
    from . import academic_affairs_graduation_service as graduation
    from . import academic_affairs_graduation_immutable_service as immutable
    from .academic_affairs_student_fact_service import append_student_academic_fact

    previous = db.query(GraduationDecisionFact).filter(
        GraduationDecisionFact.id == _target_id(case.target_ref),
        GraduationDecisionFact.tenant_id == _tid(),
    ).with_for_update().first()
    if not previous:
        raise not_found("待纠错毕业决定不存在")
    latest = db.scalars(select(GraduationDecisionFact).where(
        GraduationDecisionFact.tenant_id == _tid(),
        GraduationDecisionFact.result_id == previous.result_id,
    ).order_by(GraduationDecisionFact.decision_no.desc(), GraduationDecisionFact.id.desc()).limit(1)).first()
    if not latest or int(latest.id) != int(previous.id):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "待纠错毕业决定已被后续正式决定替代，请基于最新决定重新发起纠错",
            http_status=409,
        )

    grad_batch = db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.id == int(previous.batch_id),
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False),
    ).first()
    start, end = _term_bounds(db, batch)
    occurred = (getattr(grad_batch, "generate_at", None) or getattr(grad_batch, "created_at", None)) if grad_batch else None
    if not grad_batch or not start or not end or not occurred or not (start <= occurred <= end):
        raise AppException(
            "DATA_CONFLICT",
            "待纠错毕业决定无法证明属于该归档学期，拒绝跨学期/无边界纠错",
            details={"graduationBatchId": str(previous.batch_id), "archiveBatchId": str(batch.id)},
            http_status=409,
        )

    result = db.query(AaGraduationAuditResult).filter(
        AaGraduationAuditResult.id == int(previous.result_id),
        AaGraduationAuditResult.tenant_id == _tid(),
        AaGraduationAuditResult.is_deleted.is_(False),
    ).with_for_update().first()
    student = db.query(StudentProfile).filter(
        StudentProfile.id == int(previous.student_id),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update().first()
    if not result or not student:
        raise AppException("DATA_CONFLICT", "毕业纠错缺少结果投影或学生主档，拒绝产生半成功事实", http_status=409)

    correction = _correction(case)
    conclusion = str(correction.get("conclusion") or "").strip().upper()
    if conclusion not in graduation._CONCLUSION:
        raise AppException("VALIDATION_ERROR", "GRADUATION 纠错 conclusion 仅支持 GRADUATED/COMPLETED/DELAYED")

    evaluated_at = datetime.utcnow()
    evaluated = immutable.evaluate_student(db, student, evaluated_at=evaluated_at)
    if conclusion in {"GRADUATED", "COMPLETED"} and evaluated["overall"] != "SYSTEM_PASSED":
        raise AppException(
            "DATA_CONFLICT",
            "当前正式毕业评估仍存在 FAIL/UNKNOWN，禁止通过归档后纠错强行给出毕业/结业结论",
            details={"overall": evaluated["overall"]},
            http_status=409,
        )
    previous_run = db.get(GraduationEvaluationRun, int(previous.evaluation_run_id))
    if previous_run and previous_run.input_hash == evaluated["inputHash"] and previous.conclusion == conclusion:
        raise AppException("DATA_CONFLICT", "毕业纠错的评估输入与结论均未变化，无需追加新决定", http_status=409)

    run_no = (db.scalar(select(func.max(GraduationEvaluationRun.run_no)).where(
        GraduationEvaluationRun.tenant_id == _tid(),
        GraduationEvaluationRun.result_id == result.id,
    )) or 0) + 1
    run = GraduationEvaluationRun(
        tenant_id=_tid(),
        batch_id=result.batch_id,
        result_id=result.id,
        student_id=result.student_id,
        run_no=int(run_no),
        program_id=evaluated["programId"],
        input_snapshot_json=_json(evaluated["inputSnapshot"]),
        input_hash=evaluated["inputHash"],
        item_results_json=_json(evaluated["items"]),
        overall=evaluated["overall"],
        evaluator_version=str(evaluated["inputSnapshot"].get("evaluatorVersion") or "STAGE_C3_V1"),
        created_at=evaluated_at,
        created_by=actor,
    )
    db.add(run)
    db.flush()

    decision = GraduationDecisionFact(
        tenant_id=_tid(),
        batch_id=previous.batch_id,
        result_id=previous.result_id,
        student_id=previous.student_id,
        decision_no=int(previous.decision_no or 1) + 1,
        evaluation_run_id=run.id,
        conclusion=conclusion,
        supersedes_id=previous.id,
        correction_case_id=case.id,
        decision_at=evaluated_at,
        decision_by=actor,
        review_note=f"归档后纠错：{case.reason}"[:500],
        created_at=evaluated_at,
        created_by=actor,
    )
    db.add(decision)
    db.flush()

    target_status = graduation._CONCLUSION[conclusion]
    if str(student.student_status or "") != target_status:
        append_student_academic_fact(
            db,
            int(student.id),
            student_status=target_status,
            source_type="POST_ARCHIVE_GRAD_CORRECTION",
            source_ref_id=int(case.id),
            created_by=actor,
        )
    result.item_results_json = _json(evaluated["items"])
    result.overall = evaluated["overall"]
    result.rerun_count = int(run_no)
    result.conclusion = conclusion
    # The operational row stays archived; correction is represented by immutable facts.
    result.status = "ARCHIVED"
    result.updated_by = actor
    db.flush()

    before = _decision_snapshot(previous)
    after = _decision_snapshot(decision)
    after["evaluationInputHash"] = run.input_hash
    after["evaluationOverall"] = run.overall
    return {
        "factType": "GRADUATION_DECISION",
        "factId": int(decision.id),
        "beforeHash": _hash(before),
        "afterHash": _hash(after),
        "snapshot": after,
        "lineage": {
            "previousDecisionId": str(previous.id),
            "correctedDecisionId": str(decision.id),
            "evaluationRunId": str(run.id),
        },
    }


def _schedule_item_payload(row) -> dict:
    excluded = {
        "id", "tenant_id", "batch_id", "created_at", "created_by", "updated_at",
        "updated_by", "is_deleted",
    }
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in excluded
    }


def _schedule_batch_snapshot(row, *, item_count: int) -> dict:
    return {
        "batchId": str(row.id),
        "termId": str(row.term_id),
        "batchName": row.batch_name,
        "collegeId": str(row.college_id) if row.college_id is not None else None,
        "status": row.status,
        "publishAt": row.publish_at.isoformat() if row.publish_at else None,
        "supersedesBatchId": (
            str(row.supersedes_batch_id) if row.supersedes_batch_id is not None else None
        ),
        "effectiveItemCount": int(item_count),
    }


def _apply_schedule(db, batch, case, actor: int) -> dict:
    """Append a complete published schedule version for an archived term.

    The correction payload intentionally carries only the governed mode, not thousands
    of client-supplied rows.  Existing effective items are copied as immutable evidence;
    missing sessions are placed into conflict-free teacher/class/classroom slots using
    the same task snapshots and room as the task's existing session.
    """
    from app.models import (
        AaScheduleBatch,
        AaScheduleItem,
        AaSchedulePublish,
        AaScheduleScopeHead,
        AaTeachingTask,
        AaTeachingTaskBatch,
    )

    source = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.id == _target_id(case.target_ref),
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.is_deleted.is_(False),
    ).with_for_update().first()
    if not source:
        raise not_found("待更正正式课表批次不存在")
    if int(source.term_id) != int(batch.term_id or 0):
        raise AppException("DATA_CONFLICT", "待更正课表不属于该归档学期", http_status=409)
    if source.status != "PUBLISHED":
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "待更正课表已不是当前 PUBLISHED 正式版本，请基于最新版本重新发起",
            http_status=409,
        )
    correction = _correction(case)
    if str(correction.get("mode") or "").upper() != "REPLACE_INCOMPLETE_PUBLISHED_BATCH":
        raise AppException(
            "VALIDATION_ERROR",
            "SCHEDULE 归档后更正仅支持 REPLACE_INCOMPLETE_PUBLISHED_BATCH 模式",
        )

    task_batch_ids = list(db.scalars(select(AaTeachingTaskBatch.id).where(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(source.term_id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all())
    tasks = list(db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids),
        AaTeachingTask.status == "READY",
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all()) if task_batch_ids else []
    if source.college_id is not None:
        # A college-scoped schedule is proved by the administrative class's major;
        # the correction currently refuses an ambiguous partial scope rather than
        # silently publishing school-wide facts.
        raise AppException(
            "DATA_CONFLICT",
            "归档后课表整批更正当前仅支持 SCHOOL 全校范围",
            http_status=409,
        )
    if not tasks:
        raise AppException("DATA_CONFLICT", "归档学期没有 READY 教学任务，无法重建课表", http_status=409)

    source_items = list(db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id == int(source.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).order_by(AaScheduleItem.id)).all())
    by_task: dict[int, list] = {}
    for item in source_items:
        if item.task_id is not None:
            by_task.setdefault(int(item.task_id), []).append(item)

    expected_total = sum(max(0, int(task.weekly_hours or 0)) for task in tasks)
    if expected_total <= 0:
        raise AppException("DATA_CONFLICT", "归档学期教学任务应排节次为 0，拒绝生成空课表", http_status=409)
    for task in tasks:
        expected = max(0, int(task.weekly_hours or 0))
        actual = len(by_task.get(int(task.id), []))
        if actual > expected:
            raise AppException(
                "DATA_CONFLICT",
                "原正式课表存在超排任务，必须先人工裁定，不能自动整批更正",
                details={"taskId": str(task.id), "expected": expected, "actual": actual},
                http_status=409,
            )
        if expected and actual == 0:
            raise AppException(
                "DATA_CONFLICT",
                "原正式课表存在完全未排任务，缺少教室锚点，必须先人工补排一节",
                details={"taskId": str(task.id)},
                http_status=409,
            )

    before = _schedule_batch_snapshot(source, item_count=len(source_items))
    now = datetime.utcnow()
    replacement = AaScheduleBatch(
        tenant_id=_tid(),
        term_id=int(source.term_id),
        batch_name=f"{source.batch_name} · 归档后更正 #{case.correction_no}"[:200],
        college_id=source.college_id,
        status="PUBLISHED",
        publish_at=now,
        supersedes_batch_id=int(source.id),
        created_by=actor,
        updated_by=actor,
    )
    db.add(replacement)
    db.flush()

    new_items: list[AaScheduleItem] = []
    used_teacher: set[tuple[str, int, int]] = set()
    used_class: set[tuple[int, int, int]] = set()
    used_room: set[tuple[int, int, int]] = set()
    for item in source_items:
        copied = AaScheduleItem(
            tenant_id=_tid(),
            batch_id=int(replacement.id),
            **_schedule_item_payload(item),
            created_by=actor,
            updated_by=actor,
        )
        new_items.append(copied)
        if item.teacher_key:
            used_teacher.add((str(item.teacher_key), int(item.weekday), int(item.slot_no)))
        if item.class_id is not None:
            used_class.add((int(item.class_id), int(item.weekday), int(item.slot_no)))
        if item.classroom_id is not None:
            used_room.add((int(item.classroom_id), int(item.weekday), int(item.slot_no)))

    for task in tasks:
        anchors = by_task.get(int(task.id), [])
        missing = max(0, int(task.weekly_hours or 0) - len(anchors))
        if not missing:
            continue
        anchor = anchors[0]
        for _ in range(missing):
            chosen = None
            for weekday in range(1, 6):
                for slot_no in range(1, 11):
                    teacher_key = str(task.teacher_key or "")
                    class_id = int(task.class_id) if task.class_id is not None else 0
                    room_id = int(anchor.classroom_id) if anchor.classroom_id is not None else 0
                    if teacher_key and (teacher_key, weekday, slot_no) in used_teacher:
                        continue
                    if class_id and (class_id, weekday, slot_no) in used_class:
                        continue
                    if room_id and (room_id, weekday, slot_no) in used_room:
                        continue
                    chosen = (weekday, slot_no)
                    break
                if chosen:
                    break
            if not chosen:
                raise AppException(
                    "DATA_CONFLICT",
                    "无法为漏排教学任务找到无教师/班级/教室冲突的时段",
                    details={"taskId": str(task.id)},
                    http_status=409,
                )
            weekday, slot_no = chosen
            payload = _schedule_item_payload(anchor)
            payload.update({
                "task_id": int(task.id),
                "course_id": int(task.course_id) if task.course_id is not None else None,
                "course_name": task.course_name,
                "class_id": int(task.class_id) if task.class_id is not None else None,
                "teacher_key": task.teacher_key,
                "teacher_name": task.teacher_name,
                "weekday": weekday,
                "slot_no": slot_no,
                "start_week": int(task.start_week or anchor.start_week or 1),
                "end_week": int(task.end_week or anchor.end_week or 18),
                "week_parity": "ALL",
                "status": "EFFECTIVE",
                "source": "AUTO",
                "change_id": None,
                "objection_status": None,
                "objection_reason": None,
            })
            new_items.append(AaScheduleItem(
                tenant_id=_tid(),
                batch_id=int(replacement.id),
                **payload,
                created_by=actor,
                updated_by=actor,
            ))
            if task.teacher_key:
                used_teacher.add((str(task.teacher_key), weekday, slot_no))
            if task.class_id is not None:
                used_class.add((int(task.class_id), weekday, slot_no))
            if anchor.classroom_id is not None:
                used_room.add((int(anchor.classroom_id), weekday, slot_no))

    if len(new_items) != expected_total:
        raise AppException(
            "DATA_CONFLICT",
            "课表更正生成节次与教学任务应排节次不一致",
            details={"expected": expected_total, "actual": len(new_items)},
            http_status=409,
        )
    db.add_all(new_items)
    db.flush()

    source.status = "SUPERSEDED"
    source.updated_by = actor
    scope_head = db.query(AaScheduleScopeHead).filter(
        AaScheduleScopeHead.tenant_id == _tid(),
        AaScheduleScopeHead.term_id == int(source.term_id),
        AaScheduleScopeHead.scope_type == "SCHOOL",
        AaScheduleScopeHead.scope_id == 0,
        AaScheduleScopeHead.is_deleted.is_(False),
    ).with_for_update().first()
    if scope_head is None:
        scope_head = AaScheduleScopeHead(
            tenant_id=_tid(),
            term_id=int(source.term_id),
            scope_type="SCHOOL",
            scope_id=0,
            active_batch_id=int(replacement.id),
            version=1,
            published_at=now,
            created_by=actor,
            updated_by=actor,
        )
        db.add(scope_head)
    else:
        if scope_head.active_batch_id not in (None, int(source.id)):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "正式课表范围头已指向其他版本，请重新发起归档后更正",
                http_status=409,
            )
        scope_head.active_batch_id = int(replacement.id)
        scope_head.version = int(scope_head.version or 0) + 1
        scope_head.published_at = now
        scope_head.updated_by = actor
    db.add(AaSchedulePublish(
        tenant_id=_tid(),
        batch_id=int(source.id),
        term_id=int(source.term_id),
        action="VOID_REISSUE",
        operator_name=str(actor),
        notified_count=0,
        note=f"归档后课表更正 case={case.id}；替代批次={replacement.id}"[:500],
        created_by=actor,
        updated_by=actor,
    ))
    db.add(AaSchedulePublish(
        tenant_id=_tid(),
        batch_id=int(replacement.id),
        term_id=int(source.term_id),
        action="PUBLISH",
        operator_name=str(actor),
        notified_count=0,
        note=f"归档后课表更正 case={case.id}；顶替批次={source.id}"[:500],
        created_by=actor,
        updated_by=actor,
    ))
    db.flush()
    after = _schedule_batch_snapshot(replacement, item_count=len(new_items))
    return {
        "factType": "AA_SCHEDULE_BATCH",
        "factId": int(replacement.id),
        "recordCount": len(new_items),
        "beforeHash": _hash(before),
        "afterHash": _hash(after),
        "snapshot": after,
        "lineage": {
            "previousScheduleBatchId": str(source.id),
            "replacementScheduleBatchId": str(replacement.id),
            "scopeHeadId": str(scope_head.id),
        },
    }


def apply_official_correction_fact(db, batch, case, actor: int) -> dict:
    kind = str(case.business_type or "").upper()
    if kind == "GRADE":
        return _apply_grade(db, batch, case, actor)
    if kind == "GRADUATION":
        return _apply_graduation(db, batch, case, actor)
    if kind == "SCHEDULE":
        return _apply_schedule(db, batch, case, actor)
    raise AppException("VALIDATION_ERROR", f"不支持的归档后正式纠错类型：{kind}")
