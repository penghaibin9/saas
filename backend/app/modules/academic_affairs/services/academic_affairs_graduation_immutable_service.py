"""Stage C3 shared graduation evaluator + immutable formal runs/decisions.

Preview and formal precheck both call :func:`evaluate_student`.  Preview is strictly
read-only; only the explicit formal precheck command appends ``GraduationEvaluationRun``.
The legacy ``AaGraduationAuditResult`` row remains the current work-queue projection so
existing pages stay compatible, but it is no longer the historical source of truth.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_graduation_service as graduation_service
# Import after the package truth guard is installed: this wraps that strict evaluator
# with evidence hashes without changing its PASS/FAIL/UNKNOWN semantics.
from . import academic_affairs_graduation_evidence_facade as _evidence_facade  # noqa: F401,E402

_EVALUATOR_VERSION = "STAGE_C3_V1"


def _json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _strict_overall(items: list[dict]) -> str:
    """Formal Stage C3 decision is PASS only when every required evidence item is PASS.

    The legacy work-queue projection historically treated selected UNKNOWN domains as
    non-blocking hints.  That is acceptable for a preview UI, but it is not acceptable
    for an immutable formal run that can later anchor a graduation decision.  Missing,
    unavailable, or ambiguous evidence must remain visible as SYSTEM_ABNORMAL until a
    human/process supplies a formal resolution; UNKNOWN must never silently become PASS.
    """
    if not items:
        return "SYSTEM_ABNORMAL"
    return "SYSTEM_PASSED" if all(str(item.get("result") or "").upper() == "PASS" for item in items) else "SYSTEM_ABNORMAL"


def _actor_id() -> int | None:
    _name, _role, raw = graduation_service._op()
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _program_id(items: list[dict]) -> int | None:
    for item in items:
        raw = item.get("programId")
        if raw not in (None, ""):
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
    return None


def evaluate_student(db, student, *, evaluated_at: datetime | None = None) -> dict:
    """Single read-only evaluator used by both preview and formal runs.

    It also captures the effective-dated academic identity used at the evaluation
    instant.  Missing/overlapping facts fail closed before a formal PASS can exist.
    """
    from .academic_affairs_student_fact_service import resolve_student_academic_fact

    at = evaluated_at or datetime.utcnow()
    fact = resolve_student_academic_fact(db, int(student.id), as_of=at, required=True)
    items = list(graduation_service._run_items(db, student))
    overall = _strict_overall(items)
    snapshot = {
        "evaluatorVersion": _EVALUATOR_VERSION,
        "evaluatedAt": at.isoformat(),
        "studentId": str(student.id),
        "academicFact": {
            "id": str(fact.id),
            "versionNo": int(fact.version_no),
            "validFrom": fact.valid_from.isoformat() if fact.valid_from else None,
            "studentStatus": fact.student_status,
            "collegeId": str(fact.college_id) if fact.college_id is not None else None,
            "majorId": str(fact.major_id) if fact.major_id is not None else None,
            "classId": str(fact.class_id) if fact.class_id is not None else None,
            "grade": fact.grade,
        },
        "programId": str(_program_id(items)) if _program_id(items) is not None else None,
        "evidenceHashes": [item.get("evidenceHash") for item in items if item.get("evidenceHash")],
    }
    return {
        "programId": _program_id(items),
        "inputSnapshot": snapshot,
        "inputHash": _hash(snapshot),
        "items": items,
        "overall": overall,
    }


def evaluate_preview(student_id, user) -> dict:
    """Read-only preview.  Never creates a GraduationEvaluationRun."""
    graduation_service._require_review_role(user)
    with graduation_service.session() as db:
        from app.models import StudentProfile

        student = db.get(StudentProfile, int(student_id))
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("学生不存在")
        evaluated = evaluate_student(db, student)
        return {
            "studentId": str(student.id),
            "overall": evaluated["overall"],
            "items": evaluated["items"],
            "inputHash": evaluated["inputHash"],
            "formalRunCreated": False,
        }


def precheck(batch_id, user) -> dict:
    """Formal precheck: append Run#N, then update only the compatibility projection."""
    graduation_service._require_review_role(user)
    with graduation_service.session() as db:
        from app.models import (
            AaGraduationAuditBatch,
            AaGraduationAuditResult,
            GraduationEvaluationRun,
            StudentProfile,
        )

        batch = db.get(AaGraduationAuditBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("预审批次不存在")
        rows = db.scalars(
            select(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == _tid(),
                AaGraduationAuditResult.batch_id == batch.id,
                AaGraduationAuditResult.status.in_(["WAIT_PRECHECK", "SYSTEM_PASSED", "SYSTEM_ABNORMAL"]),
                AaGraduationAuditResult.is_deleted.is_(False),
            ).order_by(AaGraduationAuditResult.id).with_for_update()
        ).all()
        passed = abnormal = 0
        run_ids: list[str] = []
        for result in rows:
            student = db.get(StudentProfile, int(result.student_id))
            if not student or student.is_deleted or student.tenant_id != _tid():
                raise AppException(
                    "DATA_CONFLICT",
                    f"毕业预审结果 {result.id} 对应学生主档不存在，禁止静默跳过正式评估",
                    http_status=409,
                )
            evaluated_at = datetime.utcnow()
            evaluated = evaluate_student(db, student, evaluated_at=evaluated_at)
            current_max = db.scalar(
                select(func.max(GraduationEvaluationRun.run_no)).where(
                    GraduationEvaluationRun.tenant_id == _tid(),
                    GraduationEvaluationRun.result_id == result.id,
                )
            ) or 0
            run_no = int(current_max) + 1
            run = GraduationEvaluationRun(
                tenant_id=_tid(),
                batch_id=batch.id,
                result_id=result.id,
                student_id=result.student_id,
                run_no=run_no,
                program_id=evaluated["programId"],
                input_snapshot_json=_json(evaluated["inputSnapshot"]),
                input_hash=evaluated["inputHash"],
                item_results_json=_json(evaluated["items"]),
                overall=evaluated["overall"],
                evaluator_version=_EVALUATOR_VERSION,
                created_at=evaluated_at,
                created_by=_actor_id(),
            )
            db.add(run)
            db.flush()
            run_ids.append(str(run.id))

            # Compatibility/current projection only.  Historical readers use the run.
            result.item_results_json = _json(evaluated["items"])
            result.overall = evaluated["overall"]
            result.status = evaluated["overall"]
            result.rerun_count = run_no
            if evaluated["overall"] == "SYSTEM_PASSED":
                passed += 1
            else:
                abnormal += 1

        batch.status = "PRECHECKED"
        graduation_service._audit(
            db,
            batch.id,
            "PRECHECK_IMMUTABLE",
            f"pass={passed},abnormal={abnormal},runs={','.join(run_ids)}",
        )
        db.commit()
        return {
            "batchId": str(batch_id),
            "passed": passed,
            "abnormal": abnormal,
            "evaluationRunIds": run_ids,
        }


def academic_final(result_id, user, conclusion, confirm=False) -> dict:
    """Final decision must reference the exact immutable evaluation run it used."""
    graduation_service._require_review_role(user)
    conclusion = (conclusion or "").upper()
    if conclusion not in graduation_service._CONCLUSION:
        raise AppException("BAD_REQUEST", "结论非法（GRADUATED/COMPLETED/DELAYED）")
    if not confirm:
        raise AppException("DATA_CONFLICT", "毕业结论涉及学籍终态，需二次确认(confirm=true)")

    _name, _role, operator_raw = graduation_service._op()
    with graduation_service.session() as db:
        from app.models import AaGraduationAuditResult, GraduationDecisionFact, GraduationEvaluationRun

        result = db.query(AaGraduationAuditResult).filter(
            AaGraduationAuditResult.id == int(result_id),
            AaGraduationAuditResult.tenant_id == _tid(),
            AaGraduationAuditResult.is_deleted.is_(False),
        ).with_for_update().first()
        if not result:
            raise not_found("预审结果不存在")
        if result.status != "ACADEMIC_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅学院初审通过的结果可终审")
        if result.overall == "SYSTEM_ABNORMAL" and conclusion in ("GRADUATED", "COMPLETED"):
            if not result.review_note or len(result.review_note.strip()) < 5:
                raise AppException("DATA_CONFLICT", "存在异常或未知关键项，学院初审必须填写不少于5字的人工核验说明")

        run = db.scalars(select(GraduationEvaluationRun).where(
            GraduationEvaluationRun.tenant_id == _tid(),
            GraduationEvaluationRun.result_id == result.id,
        ).order_by(GraduationEvaluationRun.run_no.desc()).limit(1)).first()
        if not run:
            raise AppException(
                "DATA_CONFLICT",
                "该毕业结论没有可引用的正式 GraduationEvaluationRun，禁止按可变投影直接终审",
                http_status=409,
            )
        if str(run.overall or "") != str(result.overall or ""):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "毕业预审投影已偏离最新正式评估 Run，请重新预审后再终审",
                http_status=409,
            )
        existing = db.scalars(select(GraduationDecisionFact).where(
            GraduationDecisionFact.tenant_id == _tid(),
            GraduationDecisionFact.result_id == result.id,
        )).first()
        if existing:
            raise AppException("IDEMPOTENCY_CONFLICT", "该毕业结果已形成正式决策事实")

        to_status = graduation_service._CONCLUSION[conclusion]
        changed = graduation_service.change_student_status(
            db,
            result.student_id,
            to_status,
            change_type="GRADUATE",
            reason=f"毕业预审终审：{conclusion};evaluationRunId={run.id}",
            operator=operator_raw,
            source_biz_id=result.id,
        )
        decision_at = datetime.utcnow()
        db.add(GraduationDecisionFact(
            tenant_id=_tid(),
            batch_id=result.batch_id,
            result_id=result.id,
            student_id=result.student_id,
            evaluation_run_id=run.id,
            conclusion=conclusion,
            decision_at=decision_at,
            decision_by=_actor_id(),
            review_note=result.review_note,
            created_at=decision_at,
            created_by=_actor_id(),
        ))
        result.conclusion = conclusion
        result.status = conclusion
        graduation_service._audit(
            db,
            result.id,
            "ACADEMIC_FINAL_IMMUTABLE",
            f"{conclusion}/{to_status};evaluationRunId={run.id}",
        )
        db.commit()
        db.refresh(result)
        payload = graduation_service._row(result)
        payload["evaluationRunId"] = str(run.id)

    graduation_service.audit_status_change(
        result.student_id,
        changed["fromStatus"],
        changed["toStatus"],
        "GRADUATE",
        operator_raw,
    )
    return payload


def install() -> None:
    graduation_service.evaluate_student = evaluate_student
    graduation_service.evaluate_preview = evaluate_preview
    graduation_service.precheck = precheck
    graduation_service.academic_final = academic_final
