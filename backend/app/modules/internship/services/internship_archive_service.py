"""岗位实习归档中心。

归档列表、归档动作和批次/企业汇总全部使用同一权威合规评估器；归档包仅从
冻结快照生成，旧实时数据打包路径已移除。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from urllib.parse import quote

from sqlalchemy import and_, case, func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAgreement, InternshipArchive, InternshipAuditTrail,
    InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
    InternshipEvidencePackage, InternshipGuidance, InternshipRecord, InternshipStudentEval,
    RiskRecord, StudentProfile, WeeklyReport,
)
from app.modules.internship.services.internship_compliance_authoritative_service import (
    evaluate_internship_compliance,
)
from app.modules.internship.services.internship_version import (
    extract_expected_version,
    versioned_update,
)
from app.services.db_service import _as_id, _iso, _tid, session

MATERIALS = [
    ("agreement", "三方协议"), ("checkin", "打卡记录"), ("weekly", "周报"),
    ("enterpriseEval", "企业评价"), ("studentEval", "学生自评"),
    ("score", "实习成绩"), ("guidance", "指导记录"),
]

_FIX_PATHS = {
    "eligibility": ("完成实习资格审核", "/admin/internship/participants?stage=qualification"),
    "enterpriseAccess": ("补齐企业准入", "/admin/internship/enterprises"),
    "studentConsent": ("补学生知情确认", "/admin/internship/compliance?panel=consent"),
    "guardianConsent": ("补监护人确认", "/admin/internship/compliance?panel=consent"),
    "safetyEducation": ("完成岗前安全教育", "/admin/internship/compliance?panel=safety"),
    "insurance": ("补录并核验保险", "/admin/internship/insurances"),
    "agreement": ("完成三方协议", "/admin/internship/agreements"),
    "specialFiling": ("完成特殊实习备案", "/admin/internship/compliance?panel=special"),
    "workRights": ("修正岗位劳动权益", "/admin/internship/positions"),
    "emergency": ("补齐企业应急预案", "/admin/internship/compliance?panel=emergency"),
    "advisor": ("分配校内指导教师", "/admin/internship/participants?stage=advisor"),
    "weekly": ("补交或审核周报", "/admin/internship/process-reports"),
    "checkin": ("处理打卡缺口", "/admin/internship/attendance"),
    "guidance": ("补录指导记录", "/admin/internship/guidance"),
    "visit": ("补录巡访记录", "/admin/internship/visits"),
    "openIncident": ("关闭未结事故", "/admin/internship/risks?panel=incident"),
    "openHighRisk": ("处置开放高风险", "/admin/internship/risks"),
    "enterpriseEval": ("完成企业评价", "/admin/internship/evaluations?stage=enterprise"),
    "studentEval": ("完成学生自评", "/admin/internship/evaluations?stage=student"),
    "score": ("发布正式实习成绩", "/admin/internship/scores?stage=publish"),
}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, target_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=target_id, target_type="ARCHIVE",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _exists(db, model, rec_id, *conditions):
    return bool(db.scalar(select(func.count()).select_from(model).where(
        model.tenant_id == _tid(), model.is_deleted.is_(False),
        model.internship_id == rec_id, *conditions)) or 0)


def _materials(db, rec_id) -> dict:
    """兼容旧页面展示；是否可归档不以本布尔清单为权威。"""
    return {
        "agreement": _exists(
            db, InternshipAgreement, rec_id,
            InternshipAgreement.status.in_(("EFFECTIVE", "ARCHIVED"))),
        "checkin": _exists(db, InternshipCheckin, rec_id),
        "weekly": _exists(db, WeeklyReport, rec_id),
        "enterpriseEval": _exists(
            db, InternshipEnterpriseEval, rec_id,
            InternshipEnterpriseEval.school_review_status == "APPROVED"),
        "studentEval": _exists(
            db, InternshipStudentEval, rec_id,
            InternshipStudentEval.school_review_status == "APPROVED"),
        "score": _exists(
            db, InternshipFinalScore, rec_id,
            InternshipFinalScore.status == "PUBLISHED"),
        "guidance": _exists(
            db, InternshipGuidance, rec_id,
            InternshipGuidance.status == "NORMAL"),
    }


def _archive_row(db, rec_id):
    return db.scalars(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == rec_id,
        InternshipArchive.is_deleted.is_(False))).first()


def _evaluation(db, record, user=None):
    return evaluate_internship_compliance(
        record.id, "ARCHIVE", user=user, db=db)


def _row(db, record, student, user=None):
    materials = _materials(db, record.id)
    evaluation = _evaluation(db, record, user)
    completeness = round(float(evaluation["completeness"]["ratio"]) * 100)
    missing = [item["label"] for item in evaluation["blockers"]]
    archive = _archive_row(db, record.id)
    return {
        "id": str(record.id),
        "studentName": student.real_name if student else "-",
        "studentNo": student.student_no if student else "-",
        "advisorName": record.advisor_name or "",
        "enterpriseName": record.enterprise_name or "",
        "recordStatus": record.status,
        "completeness": completeness,
        "missing": missing,
        "materials": materials,
        "quantityFacts": evaluation.get("quantityFacts"),
        "archivePassed": bool(evaluation["passed"]),
        "ruleVersion": evaluation["ruleVersion"],
        "blockers": evaluation["blockers"],
        "warnings": evaluation["warnings"],
        "archived": bool(archive and archive.status == "ARCHIVED"),
        "archivedAt": _iso(archive.archived_at) if archive else "",
        "packageReady": bool(archive and archive.package_file_id),
        "version": int(archive.version or 0) if archive else None,
        "recordVersion": int(record.version or 0),
    }


def _ledger_row(record, student, archive):
    """20K 台账投影只读已提交事实；当前合规在单生预检/详情中按需计算。"""
    snapshot_known = archive is not None
    archived = bool(archive and archive.status == "ARCHIVED")
    missing = [
        item for item in str(getattr(archive, "missing_items", "") or "").split("、")
        if item
    ]
    completeness = int(archive.completeness or 0) if snapshot_known else None
    return {
        "id": str(record.id),
        "studentName": student.real_name if student else "-",
        "studentNo": student.student_no if student else "-",
        "advisorName": record.advisor_name or "",
        "enterpriseName": record.enterprise_name or "",
        "recordStatus": record.status,
        "completeness": completeness,
        "missing": missing,
        "readinessKnown": snapshot_known,
        "readinessSource": "ARCHIVE_SNAPSHOT" if snapshot_known else "PREFLIGHT_REQUIRED",
        "archivePassed": bool(snapshot_known and not missing and completeness == 100),
        "archived": archived,
        "archivedAt": _iso(archive.archived_at) if archive else "",
        "packageReady": bool(archive and archive.package_file_id),
        "version": int(archive.version or 0) if archive else None,
        "recordVersion": int(record.version or 0),
    }


def _missing_actions(blockers, internship_id) -> list[dict]:
    actions = []
    for blocker in blockers or []:
        action_label, path = _FIX_PATHS.get(
            blocker.get("code"),
            ("回到合规工作台补齐", "/admin/internship/compliance"),
        )
        joiner = "&" if "?" in path else "?"
        actions.append({
            "code": blocker.get("code"),
            "label": blocker.get("label"),
            "reason": blocker.get("reason"),
            "status": blocker.get("status"),
            "actionLabel": action_label,
            "path": f"{path}{joiner}id={internship_id}",
        })
    return actions


def list_by_student(page, page_size, keyword=None, batch_id=None,
                    only_incomplete=False, only_pending=False, user=None):
    with session() as db:
        from app.modules.internship.services.internship_batch_context import resolve_batch
        from app.modules.internship.services.internship_scope import apply_internship_record_scope
        batch = resolve_batch(db, batch_id)
        archive_join = and_(
            InternshipArchive.tenant_id == _tid(),
            InternshipArchive.internship_id == InternshipRecord.id,
            InternshipArchive.is_deleted.is_(False),
        )
        query = select(InternshipRecord, StudentProfile, InternshipArchive).join(
            StudentProfile, StudentProfile.id == InternshipRecord.student_id,
        ).outerjoin(
            InternshipArchive, archive_join,
        ).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.is_deleted.is_(False),
        )
        query = apply_internship_record_scope(query, user)
        if keyword:
            value = f"%{keyword.strip()}%"
            query = query.where(or_(
                StudentProfile.real_name.like(value),
                StudentProfile.student_no.like(value),
            ))
        if only_pending or only_incomplete:
            query = query.where(or_(
                InternshipArchive.id.is_(None),
                InternshipArchive.status != "ARCHIVED",
                InternshipArchive.completeness < 100,
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        if int(page_size or 0) <= 0:
            return [], total
        rows = db.execute(query.order_by(InternshipRecord.id.desc()).offset(
            (max(1, int(page)) - 1) * int(page_size),
        ).limit(int(page_size))).all()
        return [_ledger_row(record, student, archive) for record, student, archive in rows], total


def get_archive(internship_id, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        record = db.get(InternshipRecord, _as_id(internship_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习记录不存在")
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            raise no_permission("该学生不在你的数据范围内")
        result = _row(db, record, student, user)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "ARCHIVE",
            InternshipAuditTrail.target_id == record.id,
        ).order_by(InternshipAuditTrail.id)).all()
        result["auditTrail"] = [{
            "action": item.action, "operator": item.operator_name or "",
            "detail": item.detail_json or {}, "occurredAt": _iso(item.occurred_at),
        } for item in trail]
        result["materialLabels"] = [{
            "key": key, "label": label, "present": result["materials"].get(key),
        } for key, label in MATERIALS]
        result["missingActions"] = _missing_actions(result["blockers"], record.id)
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE",
            InternshipEvidencePackage.target_id == record.id,
            InternshipEvidencePackage.status == "READY",
            InternshipEvidencePackage.is_deleted.is_(False),
        ).order_by(InternshipEvidencePackage.package_version.desc()))
        result["latestPackage"] = None
        if package and package.package_file_id:
            from app.models.file import FileObject

            file_row = db.scalar(select(FileObject).where(
                FileObject.id == int(package.package_file_id),
                FileObject.tenant_id == _tid(),
                FileObject.is_deleted.is_(False),
            ))
            result["latestPackage"] = {
                "packageId": str(package.id),
                "packageVersion": int(package.package_version or 0),
                "fileId": str(package.package_file_id),
                "fileName": getattr(file_row, "file_name", "") or "实习归档.zip",
                "sizeBytes": package.package_size_bytes,
                "sha256": package.package_sha256,
                "fileCount": int(package.file_count or 0),
                "rowCount": int(package.row_count or 0),
                "status": package.status,
                "restoreCheckAvailable": True,
            }
        return result


def archive_student_in_session(db, user, internship_id, force=False,
                               expected_version=None, force_reason="",
                               evidence_file_ids=None,
                               record_expected_version=None) -> dict:
    """在调用方事务中完成业务归档；调用方负责 commit/rollback。"""
    scope, in_scope = _scope_ctx(user)
    if force:
        import re
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

    record = db.get(InternshipRecord, _as_id(internship_id))
    if not record or record.is_deleted or record.tenant_id != _tid():
        raise not_found("实习记录不存在")
    student = db.get(StudentProfile, record.student_id)
    if not in_scope(scope, db, record, student):
        raise no_permission("只能归档本人数据范围内的学生")

    materials = _materials(db, record.id)
    evaluation = _evaluation(db, record, user)
    completeness = round(float(evaluation["completeness"]["ratio"]) * 100)
    missing = [item["label"] for item in evaluation["blockers"]]
    if not evaluation["passed"] and not force:
        raise AppException(
            "DATA_CONFLICT", "归档合规检查未通过",
            details={
                "blockers": evaluation["blockers"],
                "ruleVersion": evaluation["ruleVersion"],
                "quantityFacts": evaluation.get("quantityFacts"),
            })
    bypassed = [{
        "code": item["code"], "label": item["label"],
        "status": item["status"], "reason": item["reason"],
    } for item in evaluation["blockers"]]
    force_meta = {
        "force_bypassed_items": bypassed if force else None,
        "force_rule_version": evaluation["ruleVersion"] if force else None,
        "force_approved_role": str((user or {}).get("currentRoleCode") or "") if force else None,
        "force_approved_by": _op_name(user) if force else None,
    }
    archive = _archive_row(db, record.id)
    previous_status = record.status
    if archive is None:
        record_version = extract_expected_version({"expectedVersion": expected_version})
        new_record_version = versioned_update(
            db, InternshipRecord, entity_id=record.id, tenant_id=_tid(),
            expected_version=record_version, expected_status=record.status,
            values={"status": "ARCHIVED"})
        archive = InternshipArchive(
            tenant_id=_tid(), internship_id=record.id,
            student_id=record.student_id, batch_id=record.batch_id,
            previous_record_status=previous_status,
            completeness=completeness,
            missing_items="、".join(missing) or None,
            status="ARCHIVED",
            archived_by_name=_op_name(user),
            archived_at=datetime.utcnow(),
            force_reason=(force_reason or "").strip() or None,
            force_evidence_file_ids=evidence_file_ids or None,
        )
        for key, value in force_meta.items():
            setattr(archive, key, value)
        archive.version = int(archive.version or 0) + 1
        db.add(archive)
        archive_version = int(archive.version or 0)
    else:
        record_version = extract_expected_version(
            {"expectedVersion": record_expected_version})
        new_record_version = versioned_update(
            db, InternshipRecord, entity_id=record.id, tenant_id=_tid(),
            expected_version=record_version, expected_status=record.status,
            values={"status": "ARCHIVED"})
        archive_version = versioned_update(
            db, InternshipArchive, entity_id=archive.id, tenant_id=_tid(),
            expected_version=extract_expected_version(
                {"expectedVersion": expected_version}),
            expected_status=archive.status,
            values={
                "completeness": completeness,
                "missing_items": "、".join(missing) or None,
                "status": "ARCHIVED",
                "archived_by_name": _op_name(user),
                "archived_at": datetime.utcnow(),
                "previous_record_status": previous_status,
                "force_reason": (force_reason or "").strip() or None,
                "force_evidence_file_ids": evidence_file_ids or None,
            })
        for key, value in force_meta.items():
            setattr(archive, key, value)

    db.flush()
    from app.modules.internship.services.internship_evidence_package_service import (
        capture_archive_snapshot,
    )
    snapshot = capture_archive_snapshot(db, record, evaluation, user)
    snapshot["legacyMaterialFlags"] = materials
    snapshot["missingItems"] = missing
    snapshot["forced"] = bool(force)
    snapshot["forceReason"] = (force_reason or "").strip() or None
    snapshot["forceEvidenceFileIds"] = evidence_file_ids or []
    snapshot["exemptedItems"] = [
        item for item in evaluation["items"] if item["status"] == "EXEMPTED"
    ]
    archive.material_snapshot = snapshot
    archive.snapshot_version = int(archive.snapshot_version or 0) + 1
    _trail(db, record.id, "ARCHIVE", {
        "completeness": completeness, "missing": missing,
        "force": bool(force), "ruleVersion": evaluation["ruleVersion"],
        "blockers": bypassed,
        "forceReason": (force_reason or "").strip(),
        "evidenceFileIds": evidence_file_ids or [],
    }, operator=_op_name(user))
    return {
        "id": str(record.id), "completeness": completeness,
        "missing": missing, "archived": True,
        "version": archive_version,
        "recordVersion": new_record_version,
    }


def archive_student(user, internship_id, force=False, expected_version=None,
                    force_reason="", evidence_file_ids=None,
                    record_expected_version=None) -> dict:
    with session() as db:
        result = archive_student_in_session(
            db, user, internship_id, force=force,
            expected_version=expected_version, force_reason=force_reason,
            evidence_file_ids=evidence_file_ids,
            record_expected_version=record_expected_version,
        )
        db.commit()
        return result


def preflight_archive(internship_id, user=None) -> dict:
    """同步现有材料版本并返回可确认的服务端归档预检回执。"""
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        record = db.get(InternshipRecord, _as_id(internship_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习记录不存在")
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            raise no_permission("该学生不在你的数据范围内")

        from app.modules.internship.services import internship_material_center_facade as material_facade
        from app.modules.internship.services import internship_material_center_service as material_core

        synced = material_facade.sync_record_materials(db, record, user=user)
        detail = _row(db, record, student, user)
        rows = material_core._current_rows(db, record)
        items = [material_core._item(*row) for row in rows]
        unsafe = [item for item in items if not item["readyForBusiness"]]
        missing_actions = _missing_actions(detail["blockers"], record.id)
        token_payload = {
            "internshipId": str(record.id),
            "recordVersion": int(record.version or 0),
            "archiveVersion": detail.get("version"),
            "ruleVersion": detail["ruleVersion"],
            "blockerCodes": [item.get("code") for item in detail["blockers"]],
            "fileVersions": [{
                "versionId": item["versionId"],
                "sha256": item["sha256"],
                "scanStatus": item["scanStatus"],
            } for item in items],
        }
        preflight_token = hashlib.sha256(json.dumps(
            token_payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        can_archive = bool(detail["archivePassed"] and not unsafe)
        _trail(db, record.id, "ARCHIVE_PREFLIGHT", {
            "preflightToken": preflight_token,
            "canArchive": can_archive,
            "blockerCount": len(detail["blockers"]),
            "fileVersionCount": len(items),
            "unsafeFileCount": len(unsafe),
        }, operator=_op_name(user))
        db.commit()
        return {
            **detail,
            "missingActions": missing_actions,
            "fileVersionSafety": {
                "status": "BLOCKED" if unsafe else "READY",
                "total": len(items),
                "ready": len(items) - len(unsafe),
                "unsafe": len(unsafe),
                "unsafeItems": [{
                    "versionId": item["versionId"],
                    "fileName": item["fileName"],
                    "statusText": item["statusText"],
                    "scanStatus": item["scanStatus"],
                } for item in unsafe],
                "systemSnapshotOnCommit": True,
            },
            "canArchive": can_archive,
            "requiresForce": bool(not detail["archivePassed"]),
            "preflightReceipt": {
                "action": "ARCHIVE_PREFLIGHT",
                "objectId": str(record.id),
                "recordVersion": int(record.version or 0),
                "archiveVersion": detail.get("version"),
                "preflightToken": preflight_token,
                "ruleVersion": detail["ruleVersion"],
                "status": "PASSED" if can_archive else "BLOCKED",
            },
            "syncedMaterialCount": len(synced.get("items") or []),
        }


def employment_transition_context(internship_id, user=None) -> dict:
    """仅以已归档且仍为 PUBLISHED 的冻结成绩衔接就业台账。"""
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        record = db.get(InternshipRecord, _as_id(internship_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习记录不存在")
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            raise no_permission("该学生不在你的数据范围内")
        archive = _archive_row(db, record.id)
        if not archive or archive.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅已归档实习结果可衔接就业")
        score = db.scalar(select(InternshipFinalScore).where(
            InternshipFinalScore.tenant_id == _tid(),
            InternshipFinalScore.internship_id == record.id,
            InternshipFinalScore.status == "PUBLISHED",
            InternshipFinalScore.is_deleted.is_(False),
        ).order_by(InternshipFinalScore.id.desc()))
        if not score:
            raise AppException("DATA_CONFLICT", "缺少仍有效的已发布正式成绩，禁止衔接就业")
        from app.modules.internship.services import internship_score_archive_guard as score_guard

        frozen = (archive.material_snapshot or {}).get("finalScoreFreeze") or {}
        frozen_hash = (archive.material_snapshot or {}).get("finalScoreFreezeHash") or ""
        current_freeze, current_hash = score_guard._score_freeze(db, score)
        if (
            str(frozen.get("scoreId") or "") != str(score.id)
            or int(frozen.get("scoreVersion") or -1) != int(score.version or 0)
            or str(frozen_hash) != str(current_hash)
            or frozen != current_freeze
        ):
            raise AppException("DATA_CONFLICT", "归档成绩冻结证据与当前正式结果不一致")

        from app.models.employment import EmpStudent
        from app.modules.employment.services import employment_runtime_service as employment_runtime

        employment = db.scalar(select(EmpStudent).where(
            EmpStudent.tenant_id == _tid(),
            EmpStudent.student_id == record.student_id,
            EmpStudent.record_status == "ACTIVE",
            EmpStudent.is_deleted.is_(False),
        ).order_by(EmpStudent.id.desc()))
        employment_id = ""
        if employment:
            # 就业域仍使用自己的数据范围；不能因为实习可见就泄露就业详情对象 ID。
            employment_runtime._assert_emp_id(db, employment.id, user)
            employment_id = str(employment.id)
        keyword = getattr(student, "student_no", "") or getattr(student, "real_name", "") or ""
        path = (
            f"/admin/employment/students/{employment_id}?source=internship&internshipId={record.id}"
            if employment_id else
            f"/admin/employment/students?source=internship&internshipId={record.id}&keyword={quote(keyword)}"
        )
        return {
            "internshipId": str(record.id),
            "studentId": str(record.student_id),
            "studentNo": getattr(student, "student_no", "") or "",
            "studentName": getattr(student, "real_name", "") or "",
            "archiveId": str(archive.id),
            "archiveVersion": int(archive.version or 0),
            "finalScoreId": str(score.id),
            "finalScoreVersion": int(score.version or 0),
            "finalScoreStatus": score.status,
            "totalScore": score.total_score,
            "isPass": bool(score.is_pass),
            "finalScoreFreezeHash": current_hash,
            "employmentRecordId": employment_id,
            "employmentRecordExists": bool(employment_id),
            "employmentPath": path,
            "resultAuthority": "PUBLISHED_FINAL_SCORE_FROZEN_IN_ARCHIVE",
        }


def build_package(user, internship_id) -> dict:
    """仅从不可变归档快照生成版本化归档包。"""
    from sqlalchemy.exc import IntegrityError
    from app.models import InternshipEvidencePackage
    from app.services import file_service
    from app.modules.internship.services.internship_evidence_package_service import (
        archive_zip_from_snapshot,
    )

    scope, in_scope = _scope_ctx(user)
    with session() as db:
        record = db.get(InternshipRecord, _as_id(internship_id))
        if not record or record.is_deleted or record.tenant_id != _tid():
            raise not_found("实习记录不存在")
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            raise no_permission("该学生不在你的数据范围内")
        archive = _archive_row(db, record.id)
        if not archive or archive.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅已归档学生可生成归档包")
        snapshot = archive.material_snapshot or {}
        if snapshot.get("snapshotSchemaVersion") != "INTERNSHIP_ARCHIVE_SNAPSHOT_V2":
            raise AppException("DATA_CONFLICT", "历史归档缺少完整冻结快照，不能冒充完整归档包")
        latest = int(db.scalar(select(func.max(
            InternshipEvidencePackage.package_version)).where(
                InternshipEvidencePackage.tenant_id == _tid(),
                InternshipEvidencePackage.package_type == "ARCHIVE",
                InternshipEvidencePackage.target_id == record.id)) or 0)
        package = InternshipEvidencePackage(
            tenant_id=_tid(), package_type="ARCHIVE", batch_id=record.batch_id,
            target_id=record.id, package_version=latest + 1, status="FAILED",
            generated_by_name=_op_name(user), generated_at=datetime.utcnow(),
            row_count=1, source_module="system")
        db.add(package)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppException("DATA_CONFLICT", "归档包正在生成，请稍后重试") from exc
        base_manifest = {
            "packageId": str(package.id), "packageType": "ARCHIVE",
            "packageVersion": package.package_version,
            "tenantId": str(_tid()), "batchId": str(record.batch_id or ""),
            "targetId": str(record.id),
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "generatedByUserId": str((user or {}).get("userId") or ""),
            "generatedByName": _op_name(user),
        }
        zip_bytes, manifest = archive_zip_from_snapshot(
            snapshot, user, db, base_manifest)
        safe_name = (student.real_name if student else "学生").replace("/", "_")
        meta = file_service.store_bytes(
            zip_bytes, f"实习归档_{safe_name}_v{package.package_version}.zip",
            biz_type="ARCHIVE_PACKAGE", biz_id=f"ARCHIVE:{record.id}",
            mime_type="application/zip", user=user, visibility="BIZ_SCOPED",
            security_level="SENSITIVE")
        manifest["packageSha256"] = meta["sha256"]
        manifest["totalSizeBytes"] = meta["sizeBytes"]
        package.package_file_id = meta["fileId"]
        package.package_sha256 = meta["sha256"]
        package.package_size_bytes = meta["sizeBytes"]
        package.manifest_json = manifest
        package.included_items = manifest["includedItems"]
        package.missing_items = manifest["missingItems"]
        package.rule_version = snapshot.get("ruleVersion")
        package.metric_version = "archive-snapshot-v2"
        package.status = manifest["packageStatus"]
        package.file_count = len(manifest["includedItems"])
        archive.package_file_id = meta["fileId"]
        _trail(db, record.id, "PACKAGE", {
            "fileId": meta["fileId"], "fileName": meta["fileName"],
            "packageVersion": package.package_version,
            "status": package.status, "sha256": meta["sha256"],
        }, operator=_op_name(user))
        db.commit()
        return {
            "fileId": meta["fileId"], "fileName": meta["fileName"],
            "sizeBytes": meta["sizeBytes"], "sha256": meta["sha256"],
            "packageVersion": package.package_version,
            "status": package.status,
            "packageReady": package.status == "READY",
            "missingItems": manifest["missingItems"],
        }


def revoke_archive_in_session(db, user, internship_id, reason="",
                              expected_version=None,
                              record_expected_version=None) -> dict:
    """在调用方事务中撤销业务归档并失效归档包。"""
    from app.modules.internship.services.internship_audit_service import (
        assert_high_risk_write_available,
    )

    assert_high_risk_write_available(db)
    from app.core.permissions import is_super_admin
    role = str((user or {}).get("currentRoleCode") or
               (user or {}).get("userType") or "").upper()
    if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
        raise no_permission("仅学校管理员可撤销归档")
    import re
    if len(re.findall(r"[\u4e00-\u9fff]", (reason or "").strip())) < 10:
        raise AppException("VALIDATION_ERROR", "撤销归档原因必填且不少于10个汉字")
    scope, in_scope = _scope_ctx(user)
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(internship_id),
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False)).with_for_update())
    if not record:
        raise not_found("实习记录不存在")
    student = db.get(StudentProfile, record.student_id)
    if not in_scope(scope, db, record, student):
        raise no_permission("只能撤销本人数据范围内的归档")
    archive = _archive_row(db, record.id)
    if not archive or archive.status != "ARCHIVED":
        raise AppException("DATA_CONFLICT", "该学生未归档")
    archive_version = extract_expected_version(
        {"expectedVersion": expected_version})
    record_version = extract_expected_version(
        {"expectedVersion": record_expected_version})
    if int(record.version or 0) != record_version:
        raise AppException("DATA_CONFLICT", "实习学生记录已被其他用户修改，请刷新后重试")
    restore_status = archive.previous_record_status or "ASSESSING"
    if restore_status == "ARCHIVED":
        restore_status = "ASSESSING"
    had_package = bool(archive.package_file_id)
    new_archive_version = versioned_update(
        db, InternshipArchive, entity_id=archive.id, tenant_id=_tid(),
        expected_version=archive_version, expected_status="ARCHIVED",
        values={
            "status": "REVOKED", "revoked_by_name": _op_name(user),
            "revoked_at": datetime.utcnow(), "revoke_reason": reason.strip(),
            "package_invalidated_at": datetime.utcnow() if had_package else None,
            "package_file_id": None,
        })
    record.status = restore_status
    record.version = record_version + 1
    from app.models import InternshipEvidencePackage
    packages = db.scalars(select(InternshipEvidencePackage).where(
        InternshipEvidencePackage.tenant_id == _tid(),
        or_(
            (
                (InternshipEvidencePackage.package_type == "ARCHIVE")
                & (InternshipEvidencePackage.target_id == record.id)
            ),
            (
                (InternshipEvidencePackage.package_type == "ARCHIVE_BATCH")
                & (InternshipEvidencePackage.batch_id == record.batch_id)
            ),
        ),
        InternshipEvidencePackage.status.in_(("READY", "READY_WITH_MISSING")),
        InternshipEvidencePackage.is_deleted.is_(False)).with_for_update()).all()
    invalidated_packages = []
    for package in packages:
        if package.package_type == "ARCHIVE_BATCH" and not any(
            str(item.get("internshipId") or "") == str(record.id)
            for item in (package.included_items or [])
        ):
            continue
        package.status = "INVALIDATED"
        package.invalidated_at = datetime.utcnow()
        package.invalidated_by_name = _op_name(user)
        package.invalidation_reason = reason.strip()
        invalidated_packages.append(package)
    _trail(db, record.id, "REVOKE", {
        "reason": reason.strip(), "invalidatedPackageCount": len(invalidated_packages),
    }, operator=_op_name(user))
    return {
        "id": str(record.id), "archived": False,
        "version": new_archive_version,
        "recordVersion": record.version,
        "recordStatus": restore_status,
        "packageInvalidated": had_package,
        "invalidatedPackageCount": len(invalidated_packages),
    }


def revoke_archive(user, internship_id, reason="", expected_version=None,
                   record_expected_version=None) -> dict:
    with session() as db:
        result = revoke_archive_in_session(
            db, user, internship_id, reason=reason,
            expected_version=expected_version,
            record_expected_version=record_expected_version,
        )
        db.commit()
        return result


def resolve_archive_package_download(package_id, user=None):
    from app.models import InternshipEvidencePackage
    from app.services import file_service
    with session() as db:
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.id == _as_id(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE",
            InternshipEvidencePackage.is_deleted.is_(False)))
        if not package or package.status == "INVALIDATED" or not package.package_file_id:
            raise not_found("归档包不存在或不可下载")
        from app.modules.internship.services.internship_scope import (
            assert_internship_record_scope,
        )
        assert_internship_record_scope(db, package.target_id, user, "下载归档包")
        resolved = file_service.resolve_download(package.package_file_id, user=user)
        if not resolved:
            raise not_found("归档包不存在或不可下载")
        _trail(db, package.target_id, "PACKAGE_DOWNLOAD", {
            "packageId": str(package.id),
            "packageVersion": package.package_version,
            "sha256": package.package_sha256,
        }, operator=_op_name(user))
        db.commit()
        return resolved


def _aggregate_committed_archive(db, user, batch_id, group_expr) -> list[dict]:
    """聚合只读已提交归档快照，查询数不随学生人数增长。"""
    from app.modules.internship.services.internship_scope import (
        apply_internship_record_scope,
    )

    archive_join = and_(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == InternshipRecord.id,
        InternshipArchive.is_deleted.is_(False),
    )
    scoped = select(
        InternshipRecord.id.label("internship_id"),
        group_expr.label("group_name"),
        InternshipArchive.status.label("archive_status"),
        InternshipArchive.completeness.label("completeness"),
    ).outerjoin(
        InternshipArchive, archive_join,
    ).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch_id,
        InternshipRecord.is_deleted.is_(False),
    )
    scoped = apply_internship_record_scope(scoped, user).subquery()
    archived_case = case((scoped.c.archive_status == "ARCHIVED", 1), else_=0)
    complete_case = case((
        (scoped.c.archive_status == "ARCHIVED") & (scoped.c.completeness >= 100), 1,
    ), else_=0)
    rows = db.execute(select(
        scoped.c.group_name,
        func.count().label("total"),
        func.sum(archived_case).label("archived"),
        func.sum(complete_case).label("complete"),
        func.avg(func.coalesce(scoped.c.completeness, 0)).label("avg_completeness"),
    ).group_by(scoped.c.group_name).order_by(scoped.c.group_name)).all()
    return [{
        "group": group_name or "未分组",
        "total": int(total or 0),
        "complete": int(complete or 0),
        "avgCompleteness": round(float(avg_completeness or 0)),
        "archived": int(archived or 0),
        "archiveRate": round(int(archived or 0) / int(total or 1) * 100, 1),
        "metricSource": "COMMITTED_ARCHIVE_SNAPSHOT",
    } for group_name, total, archived, complete, avg_completeness in rows]


def by_batch(user=None, batch_id=None):
    from sqlalchemy import literal
    from app.modules.internship.services.internship_batch_context import resolve_batch

    with session() as db:
        batch = resolve_batch(db, batch_id)
        return _aggregate_committed_archive(
            db, user, batch.id, literal(batch.batch_name or "未命名批次"),
        )


def by_enterprise(user=None, batch_id=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch

    with session() as db:
        batch = resolve_batch(db, batch_id)
        group_expr = case((
            or_(
                InternshipRecord.enterprise_name.is_(None),
                InternshipRecord.enterprise_name == "",
            ),
            "未分配企业",
        ), else_=InternshipRecord.enterprise_name)
        return _aggregate_committed_archive(db, user, batch.id, group_expr)


def export_archives(keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_by_student, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "指导教师", "实习企业", "记录状态", "完整度(%)", "是否已归档", "归档时间"]
    rows = [[item["studentNo"], item["studentName"], item["advisorName"], item["enterpriseName"],
             item["recordStatus"], item["completeness"], "是" if item["archived"] else "否",
             item["archivedAt"]] for item in items]
    watermark = (f"岗位实习中心·归档台账 · 导出人：{_op_name(user)} · "
                 f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("归档台账", headers, rows, watermark=watermark)
    return xlsx_util.pack_xlsx_result(content, "归档台账.xlsx", len(items))
