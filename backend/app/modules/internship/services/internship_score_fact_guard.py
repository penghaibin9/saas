"""包 7 第二组：过程事实建议分、人工调整证据与来源快照。

正式核算不再接受客户端直接填写五项分数。系统从打卡、周报、月报/总结、
企业评价、指导与巡访事实生成建议分；人工调整只能以增减分表达，必须绑定
已扫描文件并由不同用户在发布时复核。每次核算写入 append-only 审计快照，
发布前重算事实 hash，来源变化则要求重新核算。
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.models import (
    InternshipAuditTrail,
    InternshipBatch,
    InternshipCheckin,
    InternshipFinalScore,
    InternshipGuidance,
    InternshipLeave,
    InternshipMakeup,
    InternshipProcessReport,
    InternshipRecord,
    InternshipVisit,
    StudentProfile,
    WeeklyReport,
)
from app.models.file import FileBinding, FileObject
from app.modules.internship.services import internship_score_archive_guard as _archive_guard
from app.modules.internship.services import internship_score_service as _score
from app.modules.internship.services.internship_compliance_authoritative_service import (
    evaluate_internship_compliance,
)
from app.modules.internship.services.internship_compliance_facts import material_quantity_facts
from app.modules.internship.services.internship_version import (
    extract_expected_version,
    versioned_update,
)
from app.services.db_service import _iso, _tid, session
from app.services.file_business_binding_service import bind_file_to_business

_INSTALLED = False
_SNAPSHOT_ACTION = "COMPUTE_FACT_SNAPSHOT"
_REVIEW_ACTION = "MANUAL_ADJUSTMENT_REVIEW"
_SCHEMA_VERSION = "INTERNSHIP_SCORE_FACT_V1"
_LEGACY_DIRECT_FIELDS = {
    "checkinScore", "weeklyScore", "monthlyScore", "enterpriseScore", "schoolScore",
}
_COMPONENT_KEYS = ("checkin", "weekly", "monthly", "enterprise", "school")
_COMPONENT_COLUMNS = {
    "checkin": "checkin_score",
    "weekly": "weekly_score",
    "monthly": "monthly_score",
    "enterprise": "enterprise_score",
    "school": "school_score",
}
_WEIGHT_COLUMNS = {
    "checkin": "w_checkin",
    "weekly": "w_weekly",
    "monthly": "w_monthly",
    "enterprise": "w_enterprise",
    "school": "w_school",
}
_LABELS = {
    "checkin": "打卡",
    "weekly": "周报",
    "monthly": "月报总结",
    "enterprise": "企业评价",
    "school": "学校评价",
}
_ADJUSTMENT_ALIASES = {
    "checkin": "checkin", "checkinScore": "checkin",
    "weekly": "weekly", "weeklyScore": "weekly",
    "monthly": "monthly", "monthlyScore": "monthly",
    "enterprise": "enterprise", "enterpriseScore": "enterprise",
    "school": "school", "schoolScore": "school",
}

_legacy_get_score = _score.get_score
_legacy_score_freeze = _archive_guard._score_freeze


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _date_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


def _ratio_score(expected: int, actual: int) -> int:
    expected = max(0, int(expected or 0))
    actual = max(0, int(actual or 0))
    if expected == 0:
        return 100
    return round(min(actual, expected) * 100 / expected)


def _row_ref(row, **extra) -> dict:
    payload = {
        "id": str(row.id),
        "version": int(getattr(row, "version", 0) or 0),
    }
    payload.update(extra)
    return payload


def _monthly_expected(record, batch) -> int:
    rules = dict(getattr(batch, "rules_config", None) or {})
    node = (
        rules.get("monthlyReport")
        or rules.get("processReport")
        or rules.get("monthly")
        or {}
    )
    for key in ("expectedCount", "requiredCount", "minCount"):
        if node.get(key) is not None:
            return max(0, int(node[key]))
    start = _date_value(record.intern_start_date) or _date_value(
        getattr(batch, "start_date", None)
    )
    end = _date_value(record.intern_end_date) or _date_value(
        getattr(batch, "end_date", None)
    )
    if not start or not end or start > end:
        return 0
    days = (end - start).days + 1
    return max(1, (days + 29) // 30)


def _fact_snapshot(db, record: InternshipRecord) -> dict:
    batch = db.get(InternshipBatch, record.batch_id) if record.batch_id else None
    quantity = material_quantity_facts(db, record, batch)

    checkins = list(db.scalars(select(InternshipCheckin).where(
        InternshipCheckin.tenant_id == _tid(),
        InternshipCheckin.internship_id == record.id,
        InternshipCheckin.result.in_(("NORMAL", "RECORDED")),
        InternshipCheckin.is_deleted.is_(False),
    ).order_by(InternshipCheckin.id)).all())
    makeups = list(db.scalars(select(InternshipMakeup).where(
        InternshipMakeup.tenant_id == _tid(),
        InternshipMakeup.internship_id == record.id,
        InternshipMakeup.status == "APPROVED",
        InternshipMakeup.is_deleted.is_(False),
    ).order_by(InternshipMakeup.id)).all())
    leaves = list(db.scalars(select(InternshipLeave).where(
        InternshipLeave.tenant_id == _tid(),
        InternshipLeave.internship_id == record.id,
        InternshipLeave.status.in_(("APPROVED", "RETURNED")),
        InternshipLeave.is_deleted.is_(False),
    ).order_by(InternshipLeave.id)).all())
    weekly = list(db.scalars(select(WeeklyReport).where(
        WeeklyReport.tenant_id == _tid(),
        WeeklyReport.internship_id == record.id,
        WeeklyReport.status == "APPROVED",
        WeeklyReport.is_deleted.is_(False),
    ).order_by(WeeklyReport.id)).all())
    monthly = list(db.scalars(select(InternshipProcessReport).where(
        InternshipProcessReport.tenant_id == _tid(),
        InternshipProcessReport.internship_id == record.id,
        InternshipProcessReport.report_type.in_(("MONTHLY", "SUMMARY")),
        InternshipProcessReport.status == "APPROVED",
        InternshipProcessReport.is_deleted.is_(False),
    ).order_by(InternshipProcessReport.id)).all())
    guidance = list(db.scalars(select(InternshipGuidance).where(
        InternshipGuidance.tenant_id == _tid(),
        InternshipGuidance.internship_id == record.id,
        InternshipGuidance.status == "NORMAL",
        InternshipGuidance.is_deleted.is_(False),
    ).order_by(InternshipGuidance.id)).all())
    visits = list(db.scalars(select(InternshipVisit).where(
        InternshipVisit.tenant_id == _tid(),
        InternshipVisit.internship_id == record.id,
        InternshipVisit.visit_at.is_not(None),
        InternshipVisit.is_deleted.is_(False),
    ).order_by(InternshipVisit.id)).all())
    enterprise_eval = _score._approved_enterprise_eval(db, record.id)
    config = _score._active_config(db, record.batch_id)

    monthly_expected = _monthly_expected(record, batch)
    monthly_actual = len(monthly)
    school_expected = (
        int(quantity["guidance"]["expected"])
        + int(quantity["visit"]["expected"])
    )
    school_actual = (
        min(int(quantity["guidance"]["actual"]), int(quantity["guidance"]["expected"]))
        + min(int(quantity["visit"]["actual"]), int(quantity["visit"]["expected"]))
    )
    suggested = {
        "checkin": _ratio_score(
            quantity["checkin"]["expected"], quantity["checkin"]["actual"]
        ),
        "weekly": _ratio_score(
            quantity["weekly"]["expected"], quantity["weekly"]["actual"]
        ),
        "monthly": _ratio_score(monthly_expected, monthly_actual),
        "enterprise": _score._enterprise_avg(enterprise_eval),
        "school": _ratio_score(school_expected, school_actual),
    }
    rules = dict(getattr(batch, "rules_config", None) or {})
    weights = {
        "checkin": config.checkin_weight if config else _score.DEFAULT_CFG["checkin_weight"],
        "weekly": config.weekly_weight if config else _score.DEFAULT_CFG["weekly_weight"],
        "monthly": config.monthly_weight if config else _score.DEFAULT_CFG["monthly_weight"],
        "enterprise": config.enterprise_weight if config else _score.DEFAULT_CFG["enterprise_weight"],
        "school": config.school_weight if config else _score.DEFAULT_CFG["school_weight"],
    }
    pass_line = config.pass_line if config else _score.DEFAULT_CFG["pass_line"]
    manifest = {
        "schemaVersion": _SCHEMA_VERSION,
        "internship": {
            "id": str(record.id),
            "version": int(record.version or 0),
            "status": record.status,
            "studentId": str(record.student_id),
            "batchId": str(record.batch_id or ""),
        },
        "batchRules": {
            "batchId": str(getattr(batch, "id", "") or ""),
            "rulesVersion": int(getattr(batch, "rules_version", 0) or 0),
            "rulesHash": _canonical_hash(rules),
        },
        "scoreConfig": {
            "id": str(config.id) if config else "",
            "version": int(config.version or 0) if config else 0,
            "weights": weights,
            "passLine": pass_line,
            "scope": "BATCH" if config and config.batch_id is not None else (
                "TENANT_DEFAULT" if config else "BUILTIN_DEFAULT"
            ),
        },
        "checkin": {
            "expected": int(quantity["checkin"]["expected"]),
            "actual": int(quantity["checkin"]["actual"]),
            "rows": [
                _row_ref(row, date=row.checkin_date, result=row.result)
                for row in checkins
            ],
            "approvedMakeups": [
                _row_ref(row, date=row.checkin_date, status=row.status)
                for row in makeups
            ],
            "approvedLeaves": [
                _row_ref(row, startDate=row.start_date, endDate=row.end_date)
                for row in leaves
            ],
        },
        "weekly": {
            "expected": int(quantity["weekly"]["expected"]),
            "actual": int(quantity["weekly"]["actual"]),
            "rows": [
                _row_ref(
                    row,
                    weekNumber=int(row.week_number),
                    reportVersion=int(row.report_version or 0),
                    status=row.status,
                )
                for row in weekly
            ],
        },
        "monthly": {
            "expected": monthly_expected,
            "actual": monthly_actual,
            "rows": [
                _row_ref(
                    row,
                    reportType=row.report_type,
                    periodKey=row.period_key,
                    status=row.status,
                )
                for row in monthly
            ],
        },
        "school": {
            "guidanceExpected": int(quantity["guidance"]["expected"]),
            "guidanceActual": int(quantity["guidance"]["actual"]),
            "visitExpected": int(quantity["visit"]["expected"]),
            "visitActual": int(quantity["visit"]["actual"]),
            "guidanceRows": [
                _row_ref(row, method=row.method, status=row.status)
                for row in guidance
            ],
            "visitRows": [
                _row_ref(row, method=row.method, visitAt=_iso(row.visit_at) or "")
                for row in visits
            ],
        },
        "enterprise": {
            "evaluationId": str(enterprise_eval.id) if enterprise_eval else "",
            "evaluationVersion": int(enterprise_eval.version or 0) if enterprise_eval else 0,
            "sourceFileId": (
                enterprise_eval.source_file_id or enterprise_eval.file_id
            ) if enterprise_eval else "",
            "componentScores": {
                "attendance": enterprise_eval.attendance_score,
                "skill": enterprise_eval.skill_score,
                "attitude": enterprise_eval.attitude_score,
                "collaboration": enterprise_eval.collaboration_score,
                "safety": enterprise_eval.safety_score,
            } if enterprise_eval else None,
        },
    }
    return {
        "suggestedScores": suggested,
        "manifest": manifest,
        "factSourceHash": _canonical_hash(manifest),
        "config": config,
        "weights": weights,
        "passLine": pass_line,
        "enterpriseEval": enterprise_eval,
        "quantityFacts": quantity,
    }


def _parse_adjustments(body: dict) -> dict:
    raw = body.get("manualAdjustments") or {}
    if not isinstance(raw, dict):
        raise AppException("VALIDATION_ERROR", "manualAdjustments 必须为对象")
    unknown = [key for key in raw if key not in _ADJUSTMENT_ALIASES]
    if unknown:
        raise AppException(
            "VALIDATION_ERROR", "人工调整包含未知分项",
            details={"unknownKeys": unknown},
        )
    result = {key: 0 for key in _COMPONENT_KEYS}
    for source_key, value in raw.items():
        target = _ADJUSTMENT_ALIASES[source_key]
        if value in (None, ""):
            continue
        try:
            delta = int(value)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "人工调整分必须为整数")
        result[target] += delta
    return result


def _evidence_ids(body: dict) -> list[str]:
    raw = (
        body.get("adjustmentEvidenceFileIds")
        or body.get("evidenceFileIds")
        or []
    )
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "人工调分依据文件必须为数组")
    result = []
    for value in raw:
        text = str(value or "").strip()
        if not text.isdigit():
            raise AppException("VALIDATION_ERROR", "人工调分依据文件 ID 无效")
        if text not in result:
            result.append(text)
    return result


def _bind_adjustment_evidence(
    db, *, score, record, student, user, file_ids: list[str],
) -> list[dict]:
    snapshots = []
    for file_id in file_ids:
        binding = bind_file_to_business(
            db,
            file_id=file_id,
            biz_type="INTERNSHIP_SCORE_ADJUSTMENT",
            biz_id=str(score.id),
            actor=user or {},
            subject_type="STUDENT",
            subject_id=str(student.id),
            relation_type="MANUAL_SCORE_ADJUSTMENT",
            module_code="INTERNSHIP",
            student_id=student.id,
            batch_id=str(record.batch_id or "") or None,
            college_id=getattr(student, "college_id", None),
            class_id=getattr(student, "class_id", None),
            scope={
                "internshipId": str(record.id),
                "scoreId": str(score.id),
                "studentId": str(student.id),
                "batchId": str(record.batch_id or ""),
                "businessType": "INTERNSHIP_SCORE_ADJUSTMENT",
            },
        )
        file_obj = db.get(FileObject, int(file_id))
        snapshots.append({
            "fileId": file_id,
            "fileVersion": int(file_obj.version or 0),
            "fileSha256": file_obj.sha256 or "",
            "scanStatus": file_obj.scan_status,
            "bindingId": str(binding.id),
            "bindingVersion": int(binding.version or 0),
            "bindingStatus": binding.status,
        })
    return snapshots


def _latest_snapshot(db, score_id):
    return db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "SCORE",
        InternshipAuditTrail.target_id == score_id,
        InternshipAuditTrail.action == _SNAPSHOT_ACTION,
    ).order_by(InternshipAuditTrail.id.desc())).first()


def _latest_review(db, score_id, snapshot_id=None):
    rows = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "SCORE",
        InternshipAuditTrail.target_id == score_id,
        InternshipAuditTrail.action == _REVIEW_ACTION,
    ).order_by(InternshipAuditTrail.id.desc())).all()
    if snapshot_id is None:
        return rows[0] if rows else None
    for row in rows:
        if str((row.detail_json or {}).get("computeSnapshotId") or "") == str(snapshot_id):
            return row
    return None


def _verify_evidence_snapshot(db, score, evidence_rows: list[dict]) -> None:
    for item in evidence_rows:
        binding = db.scalar(select(FileBinding).where(
            FileBinding.id == int(item["bindingId"]),
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == int(item["fileId"]),
            FileBinding.biz_type == "INTERNSHIP_SCORE_ADJUSTMENT",
            FileBinding.biz_id == str(score.id),
            FileBinding.relation_type == "MANUAL_SCORE_ADJUSTMENT",
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ))
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == int(item["fileId"]),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        if not binding or not file_obj:
            raise AppException(
                "DATA_CONFLICT", "人工调分依据文件绑定已失效，禁止发布",
                details={"fileId": item.get("fileId")},
            )
        if (
            str(file_obj.status or "").upper() not in {"AVAILABLE", "STORED"}
            or str(file_obj.scan_status or "NOT_REQUIRED").upper()
            not in {"CLEAN", "NOT_REQUIRED"}
            or str(file_obj.sha256 or "") != str(item.get("fileSha256") or "")
            or int(file_obj.version or 0) != int(item.get("fileVersion") or 0)
        ):
            raise AppException(
                "DATA_CONFLICT", "人工调分依据文件版本或安全状态已变化，禁止发布",
                details={"fileId": item.get("fileId")},
            )


def _compute(user, body) -> dict:
    from app.core.permissions import enforce_permission

    enforce_permission(user or {}, "internship.score.manage")
    data = body or {}
    internship_id = data.get("internshipId") or data.get("internId")
    if not internship_id:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    direct = [
        field for field in _LEGACY_DIRECT_FIELDS
        if data.get(field) not in (None, "")
    ]
    if direct:
        raise AppException(
            "VALIDATION_ERROR",
            "正式成绩不得直接提交分项分数；请使用系统建议分与 manualAdjustments",
            details={"rejectedFields": sorted(direct)},
        )
    adjustments = _parse_adjustments(data)
    has_adjustment = any(value != 0 for value in adjustments.values())
    reason = str(data.get("adjustmentReason") or data.get("reason") or "").strip()
    evidence_file_ids = _evidence_ids(data)
    if has_adjustment:
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "人工调分原因必填且不少于 5 字")
        if not evidence_file_ids:
            raise AppException("VALIDATION_ERROR", "人工调分必须绑定依据文件")
        if not _score._user_id(user):
            raise AppException("VALIDATION_ERROR", "人工调分缺少稳定操作人 userId")
    elif evidence_file_ids:
        raise AppException("VALIDATION_ERROR", "未发生人工调分时不得提交调分依据文件")

    with session() as db:
        record = _archive_guard._locked_record(db, internship_id)
        _archive_guard._require_assessing(record, "核算成绩")
        student = _archive_guard._student_and_scope(
            db, record, user, "只能核算本人指导或授权范围内学生成绩",
        )
        facts = _fact_snapshot(db, record)
        suggested = facts["suggestedScores"]
        final_scores = {}
        for key in _COMPONENT_KEYS:
            suggestion = suggested[key]
            delta = adjustments[key]
            if suggestion is None:
                if delta:
                    raise AppException(
                        "DATA_CONFLICT",
                        f"{_LABELS[key]}缺少权威来源，不得用人工调分补成正式事实",
                    )
                final_scores[key] = None
                continue
            value = int(suggestion) + int(delta)
            if not 0 <= value <= 100:
                raise AppException(
                    "VALIDATION_ERROR",
                    f"{_LABELS[key]}调整后须在 0-100 之间",
                    details={"suggested": suggestion, "adjustment": delta},
                )
            final_scores[key] = value

        missing = [
            _LABELS[key] for key in _COMPONENT_KEYS
            if final_scores[key] is None
        ]
        incomplete = bool(missing)
        total = None
        if not incomplete:
            total = round(sum(
                final_scores[key] * facts["weights"][key]
                for key in _COMPONENT_KEYS
            ) / 100, 1)

        score = _archive_guard._locked_score_for_record(
            db, record.id, required=False,
        )
        if score and score.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "成绩已发布，不能直接重算")
        if score and score.status == "ARCHIVED":
            raise AppException(
                "DATA_CONFLICT", "历史成绩归档记录必须先走档案更正流程，不能直接重算",
            )
        values = {
            **{
                _COMPONENT_COLUMNS[key]: final_scores[key]
                for key in _COMPONENT_KEYS
            },
            **{
                _WEIGHT_COLUMNS[key]: facts["weights"][key]
                for key in _COMPONENT_KEYS
            },
            "total_score": total,
            "score_config_id": facts["config"].id if facts["config"] else None,
            "score_config_version": int(facts["config"].version or 0)
            if facts["config"] else 0,
            "pass_line": facts["passLine"],
            "is_pass": bool(total is not None and total >= facts["passLine"]),
            "incomplete": incomplete,
            "incomplete_reason": ("缺：" + "、".join(missing)) if missing else None,
            "status": "PENDING_REVIEW",
        }
        if score is None:
            score = InternshipFinalScore(
                tenant_id=_tid(),
                internship_id=record.id,
                student_id=record.student_id,
                batch_id=record.batch_id,
            )
            db.add(score)
            for key, value in values.items():
                setattr(score, key, value)
            score.version = int(score.version or 0) + 1
            db.flush()
            new_version = int(score.version or 0)
        else:
            new_version = versioned_update(
                db,
                InternshipFinalScore,
                entity_id=score.id,
                tenant_id=_tid(),
                expected_version=extract_expected_version(data),
                expected_status=score.status,
                values=values,
            )
            db.flush()

        evidence = _bind_adjustment_evidence(
            db,
            score=score,
            record=record,
            student=student,
            user=user,
            file_ids=evidence_file_ids,
        ) if has_adjustment else []
        source_manifest = {
            "facts": facts["manifest"],
            "manualAdjustmentEvidence": evidence,
        }
        source_hash = _canonical_hash(source_manifest)
        snapshot_detail = {
            "schemaVersion": _SCHEMA_VERSION,
            "scoreId": str(score.id),
            "scoreVersion": int(new_version),
            "internshipId": str(record.id),
            "recordVersion": int(record.version or 0),
            "suggestedScores": suggested,
            "manualAdjustments": adjustments,
            "finalScores": final_scores,
            "weights": facts["weights"],
            "passLine": facts["passLine"],
            "total": total,
            "sourceManifest": source_manifest,
            "factSourceHash": facts["factSourceHash"],
            "sourceHash": source_hash,
            "adjustment": {
                "reason": reason if has_adjustment else "",
                "evidenceFileIds": evidence_file_ids,
                "actorUserId": _score._user_id(user),
                "actorName": _score._op_name(user),
                "actorRole": _score._role_code(user),
                "reviewStatus": "PENDING" if has_adjustment else "NOT_REQUIRED",
            },
        }
        snapshot = InternshipAuditTrail(
            tenant_id=_tid(),
            target_id=score.id,
            target_type="SCORE",
            action=_SNAPSHOT_ACTION,
            operator_name=_score._op_name(user),
            detail_json=snapshot_detail,
            occurred_at=datetime.utcnow(),
        )
        db.add(snapshot)
        _score._trail(db, score.id, "COMPUTE", {
            "total": total,
            "incomplete": incomplete,
            "missing": missing,
            "recordStatus": record.status,
            "scoreConfigId": str(facts["config"].id) if facts["config"] else "",
            "scoreConfigVersion": int(facts["config"].version or 0)
            if facts["config"] else 0,
            "factSourceHash": facts["factSourceHash"],
            "sourceHash": source_hash,
            "manualAdjustment": has_adjustment,
            "actorUserId": _score._user_id(user),
            "actorRole": _score._role_code(user),
        }, operator=_score._op_name(user))
        db.commit()
        return {
            "id": str(score.id),
            "internshipId": str(record.id),
            "total": total,
            "enterpriseScore": final_scores["enterprise"],
            "suggestedScores": suggested,
            "manualAdjustments": adjustments,
            "factSourceHash": facts["factSourceHash"],
            "sourceHash": source_hash,
            "adjustmentReviewStatus": "PENDING" if has_adjustment else "NOT_REQUIRED",
            "incomplete": incomplete,
            "incompleteReason": values["incomplete_reason"],
            "isPass": values["is_pass"],
            "status": "PENDING_REVIEW",
            "version": new_version,
        }


def _publish(user, score_id, expected_version=None) -> dict:
    from app.core.permissions import enforce_permission

    enforce_permission(user or {}, "internship.score.publish")
    _score._assert_reviewer(user, final=True)
    with session() as db:
        record, score = _archive_guard._locked_score(db, score_id)
        _archive_guard._student_and_scope(
            db, record, user, "只能发布本人数据范围内的成绩",
        )
        _archive_guard._require_assessing(record, "发布成绩")
        if score.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待复核成绩可发布")
        if score.incomplete:
            raise AppException(
                "DATA_CONFLICT", f"成绩缺项不可发布（{score.incomplete_reason}）",
            )
        snapshot = _latest_snapshot(db, score.id)
        if not snapshot:
            raise AppException(
                "DATA_CONFLICT", "成绩缺少正式过程事实快照，请重新核算",
            )
        detail = snapshot.detail_json or {}
        current_facts = _fact_snapshot(db, record)
        if current_facts["factSourceHash"] != detail.get("factSourceHash"):
            raise AppException(
                "DATA_CONFLICT",
                "成绩来源事实已变化，请重新核算后再发布",
                details={
                    "snapshotFactSourceHash": detail.get("factSourceHash"),
                    "currentFactSourceHash": current_facts["factSourceHash"],
                },
            )
        evidence = (
            (detail.get("sourceManifest") or {})
            .get("manualAdjustmentEvidence")
            or []
        )
        _verify_evidence_snapshot(db, score, evidence)
        adjustments = detail.get("manualAdjustments") or {}
        has_adjustment = any(int(value or 0) != 0 for value in adjustments.values())
        reviewer_id = _score._user_id(user)
        if has_adjustment:
            adjuster_id = str(
                (detail.get("adjustment") or {}).get("actorUserId") or ""
            )
            if not reviewer_id or not adjuster_id:
                raise AppException(
                    "DATA_CONFLICT", "人工调分缺少稳定调整人或复核人 userId",
                )
            if reviewer_id == adjuster_id:
                raise AppException(
                    "DATA_CONFLICT", "人工调分必须由不同用户复核，调整人不得自行发布",
                )
            review = InternshipAuditTrail(
                tenant_id=_tid(),
                target_id=score.id,
                target_type="SCORE",
                action=_REVIEW_ACTION,
                operator_name=_score._op_name(user),
                detail_json={
                    "computeSnapshotId": str(snapshot.id),
                    "decision": "APPROVED",
                    "sourceHash": detail.get("sourceHash"),
                    "adjusterUserId": adjuster_id,
                    "reviewerUserId": reviewer_id,
                    "reviewerRole": _score._role_code(user),
                },
                occurred_at=datetime.utcnow(),
            )
            db.add(review)

        evaluation = evaluate_internship_compliance(
            record.id, "ASSESS", user=user, db=db,
        )
        if not evaluation["passed"]:
            raise AppException(
                "DATA_CONFLICT",
                "实习考核合规检查未通过，禁止发布成绩",
                details={
                    "blockers": evaluation["blockers"],
                    "ruleVersion": evaluation["ruleVersion"],
                    "quantityFacts": evaluation.get("quantityFacts"),
                },
            )
        new_version = versioned_update(
            db,
            InternshipFinalScore,
            entity_id=score.id,
            tenant_id=_tid(),
            expected_version=extract_expected_version(
                {"expectedVersion": expected_version}
            ),
            expected_status="PENDING_REVIEW",
            values={
                "status": "PUBLISHED",
                "reviewed_by_name": _score._op_name(user),
                "reviewed_at": datetime.utcnow(),
                "published_by_name": _score._op_name(user),
                "published_at": datetime.utcnow(),
            },
        )
        _score._trail(db, score.id, "PUBLISH", {
            "total": score.total_score,
            "isPass": score.is_pass,
            "ruleVersion": evaluation["ruleVersion"],
            "quantityFacts": evaluation.get("quantityFacts"),
            "computeSnapshotId": str(snapshot.id),
            "factSourceHash": detail.get("factSourceHash"),
            "sourceHash": detail.get("sourceHash"),
            "manualAdjustmentReviewed": has_adjustment,
            "actorUserId": reviewer_id,
            "actorRole": _score._role_code(user),
        }, operator=_score._op_name(user))
        db.commit()
        return {
            "id": str(score.id),
            "status": "PUBLISHED",
            "statusLabel": _score.STATUS_LABEL["PUBLISHED"],
            "version": new_version,
            "sourceHash": detail.get("sourceHash"),
            "adjustmentReviewStatus": "APPROVED" if has_adjustment else "NOT_REQUIRED",
        }


def _get_score(score_id, user=None) -> dict:
    result = _legacy_get_score(score_id, user=user)
    with session() as db:
        snapshot = _latest_snapshot(db, int(score_id))
        if not snapshot:
            result.update({
                "suggestedScores": {},
                "manualAdjustments": {},
                "sourceManifest": {},
                "factSourceHash": "",
                "sourceHash": "",
                "adjustmentReviewStatus": "LEGACY_MISSING",
            })
            return result
        detail = snapshot.detail_json or {}
        review = _latest_review(db, int(score_id), snapshot.id)
        adjustment = detail.get("adjustment") or {}
        result.update({
            "suggestedScores": detail.get("suggestedScores") or {},
            "manualAdjustments": detail.get("manualAdjustments") or {},
            "sourceManifest": detail.get("sourceManifest") or {},
            "factSourceHash": detail.get("factSourceHash") or "",
            "sourceHash": detail.get("sourceHash") or "",
            "adjustmentReason": adjustment.get("reason") or "",
            "adjustmentEvidenceFileIds": adjustment.get("evidenceFileIds") or [],
            "adjustmentReviewStatus": (
                "APPROVED" if review
                else adjustment.get("reviewStatus") or "NOT_REQUIRED"
            ),
            "adjustedByUserId": adjustment.get("actorUserId") or "",
            "reviewedByUserId": (
                (review.detail_json or {}).get("reviewerUserId") if review else ""
            ),
        })
        return result


def _score_freeze(db, score) -> tuple[dict, str]:
    payload, _legacy_hash = _legacy_score_freeze(db, score)
    snapshot = _latest_snapshot(db, score.id)
    if not snapshot:
        payload["sourceSnapshotStatus"] = "LEGACY_MISSING"
        return payload, _canonical_hash(payload)
    detail = snapshot.detail_json or {}
    review = _latest_review(db, score.id, snapshot.id)
    payload.update({
        "schemaVersion": "INTERNSHIP_FINAL_SCORE_FREEZE_V2",
        "sourceSnapshotStatus": "FROZEN",
        "computeSnapshotId": str(snapshot.id),
        "suggestedScores": detail.get("suggestedScores") or {},
        "manualAdjustments": detail.get("manualAdjustments") or {},
        "sourceManifest": detail.get("sourceManifest") or {},
        "factSourceHash": detail.get("factSourceHash") or "",
        "sourceHash": detail.get("sourceHash") or "",
        "manualAdjustmentReview": (
            review.detail_json if review else {
                "decision": (detail.get("adjustment") or {}).get("reviewStatus")
                or "NOT_REQUIRED"
            }
        ),
    })
    return payload, _canonical_hash(payload)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _score.compute = _compute
    _score.publish = _publish
    _score.get_score = _get_score
    _archive_guard._score_freeze = _score_freeze
    _INSTALLED = True
