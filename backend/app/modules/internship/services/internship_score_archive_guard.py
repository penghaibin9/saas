"""包 7 第一组：实习成绩与总档案统一状态、锁与冻结边界。

本模块替换历史成绩写命令，避免继续产生独立 ``score=ARCHIVED`` 正式事实。
所有竞争写操作统一按 ``InternshipRecord -> InternshipFinalScore ->
InternshipArchive`` 加锁：

* 只有 ASSESSING 实习记录可核算、发布成绩；
* 发布前在同一事务重跑权威 ASSESS 合规；
* 总档案归档冻结仍为 PUBLISHED 的最终成绩快照与 hash；
* 总档案 ARCHIVED 后禁止直接撤回成绩；
* 历史独立成绩归档入口永久 fail-closed。

第二组“事实建议分 / 人工调整分 / 调整证据”另行迁移，不在本文件冒充完成。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipArchive,
    InternshipFinalScore,
    InternshipRecord,
    StudentProfile,
)
from app.modules.internship.services import internship_archive_service as _archive
from app.modules.internship.services import internship_score_service as _score
from app.modules.internship.services.internship_compliance_authoritative_service import (
    evaluate_internship_compliance,
)
from app.modules.internship.services.internship_version import (
    extract_expected_version,
    versioned_update,
)
from app.services.db_service import _as_id, _iso, _tid, session

_INSTALLED = False


def _locked_record(db, internship_id) -> InternshipRecord:
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(internship_id),
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False),
    ).with_for_update())
    if not record:
        raise not_found("实习记录不存在")
    return record


def _score_identity(db, score_id) -> int:
    internship_id = db.scalar(select(InternshipFinalScore.internship_id).where(
        InternshipFinalScore.id == _as_id(score_id),
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.is_deleted.is_(False),
    ))
    if internship_id is None:
        raise not_found("成绩不存在")
    return int(internship_id)


def _locked_score_for_record(db, internship_id, *, required=True):
    row = db.scalar(select(InternshipFinalScore).where(
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.internship_id == _as_id(internship_id),
        InternshipFinalScore.is_deleted.is_(False),
    ).order_by(InternshipFinalScore.id.desc()).with_for_update())
    if required and not row:
        raise AppException("DATA_CONFLICT", "缺少可冻结的正式实习成绩")
    return row


def _locked_score(db, score_id):
    internship_id = _score_identity(db, score_id)
    record = _locked_record(db, internship_id)
    score = db.scalar(select(InternshipFinalScore).where(
        InternshipFinalScore.id == _as_id(score_id),
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.internship_id == record.id,
        InternshipFinalScore.is_deleted.is_(False),
    ).with_for_update())
    if not score:
        raise not_found("成绩不存在")
    return record, score


def _locked_archive(db, internship_id):
    return db.scalar(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == _as_id(internship_id),
        InternshipArchive.is_deleted.is_(False),
    ).order_by(InternshipArchive.id.desc()).with_for_update())


def _student_and_scope(db, record, user, denied_message):
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    scope, in_scope = _score._scope_ctx(user)
    if not in_scope(scope, db, record, student):
        raise no_permission(denied_message)
    return student


def _require_assessing(record, action: str) -> None:
    if str(record.status or "").upper() != "ASSESSING":
        raise AppException(
            "DATA_CONFLICT",
            f"仅处于考核阶段（ASSESSING）的实习记录可{action}",
            details={"internshipId": str(record.id), "currentStatus": record.status},
        )


def _compute(user, body) -> dict:
    """保留既有五项合同，但把阶段校验放进同一锁事务。"""
    from app.core.permissions import enforce_permission

    enforce_permission(user or {}, "internship.score.manage")
    b = body or {}
    internship_id = b.get("internshipId") or b.get("internId")
    if not internship_id:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    if b.get("enterpriseScore") not in (None, ""):
        raise AppException("VALIDATION_ERROR", "企业评价分不得手工填写，只能读取已审核企业评价")
    components = {
        "checkin_score": _score._score_or_none(b.get("checkinScore")),
        "weekly_score": _score._score_or_none(b.get("weeklyScore")),
        "monthly_score": _score._score_or_none(b.get("monthlyScore")),
        "school_score": _score._score_or_none(b.get("schoolScore")),
    }
    with session() as db:
        record = _locked_record(db, internship_id)
        _require_assessing(record, "核算成绩")
        _student_and_scope(db, record, user, "只能核算本人指导或授权范围内学生成绩")
        enterprise_eval = _score._approved_enterprise_eval(db, record.id)
        components["enterprise_score"] = _score._enterprise_avg(enterprise_eval)
        config = _score._active_config(db, record.batch_id)
        weights = {
            "w_checkin": config.checkin_weight if config else _score.DEFAULT_CFG["checkin_weight"],
            "w_weekly": config.weekly_weight if config else _score.DEFAULT_CFG["weekly_weight"],
            "w_monthly": config.monthly_weight if config else _score.DEFAULT_CFG["monthly_weight"],
            "w_enterprise": config.enterprise_weight if config else _score.DEFAULT_CFG["enterprise_weight"],
            "w_school": config.school_weight if config else _score.DEFAULT_CFG["school_weight"],
        }
        pass_line = config.pass_line if config else _score.DEFAULT_CFG["pass_line"]
        missing = [
            label for _json_key, column, _weight, label in _score.COMPONENTS
            if components[column] is None
        ]
        incomplete = bool(missing)
        total = None
        if not incomplete:
            total = round((
                components["checkin_score"] * weights["w_checkin"]
                + components["weekly_score"] * weights["w_weekly"]
                + components["monthly_score"] * weights["w_monthly"]
                + components["enterprise_score"] * weights["w_enterprise"]
                + components["school_score"] * weights["w_school"]
            ) / 100, 1)
        score = _locked_score_for_record(db, record.id, required=False)
        if score and score.status == "PUBLISHED":
            raise AppException("DATA_CONFLICT", "成绩已发布，不能直接重算")
        if score and score.status == "ARCHIVED":
            raise AppException(
                "DATA_CONFLICT",
                "历史成绩归档记录必须先走档案更正流程，不能直接重算",
            )
        values = {
            **components,
            **weights,
            "total_score": total,
            "score_config_id": config.id if config else None,
            "score_config_version": int(config.version or 0) if config else 0,
            "pass_line": pass_line,
            "is_pass": bool(total is not None and total >= pass_line),
            "incomplete": incomplete,
            "incomplete_reason": ("缺：" + "、".join(missing)) if missing else None,
            "status": "PENDING_REVIEW",
        }
        if score is None:
            score = InternshipFinalScore(
                tenant_id=_tid(), internship_id=record.id,
                student_id=record.student_id, batch_id=record.batch_id,
            )
            db.add(score)
            for key, value in values.items():
                setattr(score, key, value)
            score.version = int(score.version or 0) + 1
            db.flush()
            new_version = int(score.version or 0)
        else:
            new_version = versioned_update(
                db, InternshipFinalScore, entity_id=score.id, tenant_id=_tid(),
                expected_version=extract_expected_version(b),
                expected_status=score.status, values=values,
            )
        _score._trail(db, score.id, "COMPUTE", {
            "total": total,
            "incomplete": incomplete,
            "missing": missing,
            "recordStatus": record.status,
            "scoreConfigId": str(config.id) if config else "",
            "scoreConfigVersion": int(config.version or 0) if config else 0,
            "enterpriseEvalId": str(enterprise_eval.id) if enterprise_eval else "",
            "enterpriseEvidenceFileId": (
                enterprise_eval.source_file_id or enterprise_eval.file_id
            ) if enterprise_eval else "",
            "actorUserId": _score._user_id(user),
            "actorRole": _score._role_code(user),
        }, operator=_score._op_name(user))
        db.commit()
        return {
            "id": str(score.id),
            "internshipId": str(record.id),
            "total": total,
            "enterpriseScore": components["enterprise_score"],
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
        record, score = _locked_score(db, score_id)
        _student_and_scope(db, record, user, "只能发布本人数据范围内的成绩")
        _require_assessing(record, "发布成绩")
        if score.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待复核成绩可发布")
        if score.incomplete:
            raise AppException("DATA_CONFLICT", f"成绩缺项不可发布（{score.incomplete_reason}）")
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
            db, InternshipFinalScore,
            entity_id=score.id, tenant_id=_tid(),
            expected_version=extract_expected_version(
                {"expectedVersion": expected_version}),
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
            "actorUserId": _score._user_id(user),
            "actorRole": _score._role_code(user),
        }, operator=_score._op_name(user))
        db.commit()
        return {
            "id": str(score.id),
            "status": "PUBLISHED",
            "statusLabel": _score.STATUS_LABEL["PUBLISHED"],
            "version": new_version,
        }


def _withdraw(user, score_id, reason="", expected_version=None) -> dict:
    from app.core.permissions import enforce_permission

    enforce_permission(user or {}, "internship.score.publish")
    _score._assert_reviewer(user, final=True)
    normalized_reason = (reason or "").strip()
    if len(normalized_reason) < 5:
        raise AppException("VALIDATION_ERROR", "撤回原因必填且不少于 5 字")
    with session() as db:
        record, score = _locked_score(db, score_id)
        _student_and_scope(db, record, user, "只能撤回本人数据范围内的成绩")
        archive = _locked_archive(db, record.id)
        if archive and archive.status == "ARCHIVED":
            raise AppException(
                "DATA_CONFLICT",
                "实习总档案已归档，成绩已被冻结；请先发起档案更正/撤销归档",
                details={
                    "internshipId": str(record.id),
                    "archiveId": str(archive.id),
                    "archiveVersion": int(archive.version or 0),
                },
            )
        if score.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布成绩可撤回")
        new_version = versioned_update(
            db, InternshipFinalScore,
            entity_id=score.id, tenant_id=_tid(),
            expected_version=extract_expected_version(
                {"expectedVersion": expected_version}),
            expected_status="PUBLISHED",
            values={"status": "WITHDRAWN"},
        )
        _score._trail(db, score.id, "WITHDRAW", {
            "reason": normalized_reason,
            "actorUserId": _score._user_id(user),
            "actorRole": _score._role_code(user),
        }, operator=_score._op_name(user))
        db.commit()
        return {"id": str(score.id), "status": "WITHDRAWN", "version": new_version}


def _reject_independent_score_archive(user, score_id, expected_version=None) -> dict:
    raise AppException(
        "DATA_CONFLICT",
        "实习成绩不再单独归档；请使用学生实习总档案归档，系统会冻结 PUBLISHED 成绩快照",
        details={"scoreId": str(score_id)},
    )


def _score_freeze(db, score) -> tuple[dict, str]:
    enterprise_eval = _score._approved_enterprise_eval(db, score.internship_id)
    payload = {
        "schemaVersion": "INTERNSHIP_FINAL_SCORE_FREEZE_V1",
        "scoreId": str(score.id),
        "scoreVersion": int(score.version or 0),
        "status": score.status,
        "checkinScore": score.checkin_score,
        "weeklyScore": score.weekly_score,
        "monthlyScore": score.monthly_score,
        "enterpriseScore": score.enterprise_score,
        "schoolScore": score.school_score,
        "totalScore": score.total_score,
        "passLine": score.pass_line,
        "isPass": bool(score.is_pass),
        "scoreConfigId": str(score.score_config_id) if score.score_config_id else "",
        "scoreConfigVersion": int(score.score_config_version or 0),
        "publishedAt": _iso(score.published_at) or "",
        "enterpriseEvalId": str(enterprise_eval.id) if enterprise_eval else "",
        "enterpriseEvidenceFileId": (
            enterprise_eval.source_file_id or enterprise_eval.file_id
        ) if enterprise_eval else "",
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return payload, hashlib.sha256(canonical).hexdigest()


def _archive_student(user, internship_id, force=False, expected_version=None,
                     force_reason="", evidence_file_ids=None,
                     record_expected_version=None) -> dict:
    scope, in_scope = _archive._scope_ctx(user)
    if force:
        from app.core.permissions import enforce_permission, is_super_admin

        enforce_permission(user or {}, "internship.archive.force")
        role = str((user or {}).get("currentRoleCode") or
                   (user or {}).get("userType") or "").upper()
        if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
            raise no_permission("仅学校管理员可执行强制归档")
        if len(re.findall(r"[\u4e00-\u9fff]", (force_reason or "").strip())) < 10:
            raise AppException("VALIDATION_ERROR", "强制归档原因必填且不少于10个汉字")
        if not evidence_file_ids:
            raise AppException("VALIDATION_ERROR", "强制归档必须提供依据文件")

    with session() as db:
        record = _locked_record(db, internship_id)
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == record.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ))
        if not in_scope(scope, db, record, student):
            raise no_permission("只能归档本人数据范围内的学生")
        score = _locked_score_for_record(db, record.id)
        archive = _locked_archive(db, record.id)
        if score.status != "PUBLISHED":
            raise AppException(
                "DATA_CONFLICT",
                "实习总档案只能冻结当前已发布（PUBLISHED）的正式成绩",
                details={
                    "scoreId": str(score.id),
                    "scoreStatus": score.status,
                },
            )

        materials = _archive._materials(db, record.id)
        evaluation = evaluate_internship_compliance(
            record.id, "ARCHIVE", user=user, db=db,
        )
        completeness = round(float(evaluation["completeness"]["ratio"]) * 100)
        missing = [item["label"] for item in evaluation["blockers"]]
        if not evaluation["passed"] and not force:
            raise AppException(
                "DATA_CONFLICT", "归档合规检查未通过",
                details={
                    "blockers": evaluation["blockers"],
                    "ruleVersion": evaluation["ruleVersion"],
                    "quantityFacts": evaluation.get("quantityFacts"),
                },
            )
        bypassed = [{
            "code": item["code"],
            "label": item["label"],
            "status": item["status"],
            "reason": item["reason"],
        } for item in evaluation["blockers"]]
        force_meta = {
            "force_bypassed_items": bypassed if force else None,
            "force_rule_version": evaluation["ruleVersion"] if force else None,
            "force_approved_role": str((user or {}).get("currentRoleCode") or "") if force else None,
            "force_approved_by": _archive._op_name(user) if force else None,
        }
        previous_status = record.status
        if archive is None:
            new_record_version = versioned_update(
                db, InternshipRecord,
                entity_id=record.id, tenant_id=_tid(),
                expected_version=extract_expected_version(
                    {"expectedVersion": expected_version}),
                expected_status=record.status,
                values={"status": "ARCHIVED"},
            )
            archive = InternshipArchive(
                tenant_id=_tid(), internship_id=record.id,
                student_id=record.student_id, batch_id=record.batch_id,
                previous_record_status=previous_status,
                completeness=completeness,
                missing_items="、".join(missing) or None,
                status="ARCHIVED",
                archived_by_name=_archive._op_name(user),
                archived_at=datetime.utcnow(),
                force_reason=(force_reason or "").strip() or None,
                force_evidence_file_ids=evidence_file_ids or None,
            )
            for key, value in force_meta.items():
                setattr(archive, key, value)
            archive.version = int(archive.version or 0) + 1
            db.add(archive)
            db.flush()
            archive_version = int(archive.version or 0)
        else:
            new_record_version = versioned_update(
                db, InternshipRecord,
                entity_id=record.id, tenant_id=_tid(),
                expected_version=extract_expected_version(
                    {"expectedVersion": record_expected_version}),
                expected_status=record.status,
                values={"status": "ARCHIVED"},
            )
            archive_version = versioned_update(
                db, InternshipArchive,
                entity_id=archive.id, tenant_id=_tid(),
                expected_version=extract_expected_version(
                    {"expectedVersion": expected_version}),
                expected_status=archive.status,
                values={
                    "completeness": completeness,
                    "missing_items": "、".join(missing) or None,
                    "status": "ARCHIVED",
                    "archived_by_name": _archive._op_name(user),
                    "archived_at": datetime.utcnow(),
                    "previous_record_status": previous_status,
                    "force_reason": (force_reason or "").strip() or None,
                    "force_evidence_file_ids": evidence_file_ids or None,
                },
            )
            for key, value in force_meta.items():
                setattr(archive, key, value)

        db.flush()
        from app.modules.internship.services.internship_evidence_package_service import (
            capture_archive_snapshot,
        )

        score_snapshot, score_hash = _score_freeze(db, score)
        snapshot = capture_archive_snapshot(db, record, evaluation, user)
        snapshot["legacyMaterialFlags"] = materials
        snapshot["missingItems"] = missing
        snapshot["forced"] = bool(force)
        snapshot["forceReason"] = (force_reason or "").strip() or None
        snapshot["forceEvidenceFileIds"] = evidence_file_ids or []
        snapshot["exemptedItems"] = [
            item for item in evaluation["items"] if item["status"] == "EXEMPTED"
        ]
        snapshot["finalScoreFreeze"] = score_snapshot
        snapshot["finalScoreFreezeHash"] = score_hash
        archive.material_snapshot = snapshot
        archive.snapshot_version = int(archive.snapshot_version or 0) + 1
        _archive._trail(db, record.id, "ARCHIVE", {
            "completeness": completeness,
            "missing": missing,
            "force": bool(force),
            "ruleVersion": evaluation["ruleVersion"],
            "blockers": bypassed,
            "forceReason": (force_reason or "").strip(),
            "evidenceFileIds": evidence_file_ids or [],
            "finalScoreId": str(score.id),
            "finalScoreVersion": int(score.version or 0),
            "finalScoreFreezeHash": score_hash,
        }, operator=_archive._op_name(user))
        db.commit()
        return {
            "id": str(record.id),
            "completeness": completeness,
            "missing": missing,
            "archived": True,
            "version": archive_version,
            "recordVersion": new_record_version,
            "finalScoreId": str(score.id),
            "finalScoreVersion": int(score.version or 0),
            "finalScoreFreezeHash": score_hash,
        }


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _score.compute = _compute
    _score.publish = _publish
    _score.withdraw = _withdraw
    _score.archive = _reject_independent_score_archive
    _archive.archive_student = _archive_student
    _INSTALLED = True
