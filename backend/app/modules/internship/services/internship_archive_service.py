"""岗位实习归档中心。

归档列表、归档动作和批次/企业汇总全部使用同一权威合规评估器；归档包仅从
冻结快照生成，旧实时数据打包路径已移除。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    InternshipAgreement, InternshipArchive, InternshipAuditTrail,
    InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
    InternshipGuidance, InternshipRecord, InternshipStudentEval,
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


def _scoped_records(db, user, batch_id=None, enterprise=None):
    scope, in_scope = _scope_ctx(user)
    records = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False))).all()
    result = []
    for record in records:
        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):
            continue
        if batch_id and str(record.batch_id) != str(batch_id):
            continue
        if enterprise and (record.enterprise_name or "") != enterprise:
            continue
        result.append((record, student))
    return result


def list_by_student(page, page_size, keyword=None, batch_id=None,
                    only_incomplete=False, user=None):
    with session() as db:
        from app.modules.internship.services.internship_batch_context import resolve_batch
        from app.modules.internship.services.internship_scope import apply_internship_record_scope
        batch = resolve_batch(db, batch_id)
        if not only_incomplete:
            query = select(InternshipRecord, StudentProfile).join(
                StudentProfile, StudentProfile.id == InternshipRecord.student_id
            ).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False),
                StudentProfile.is_deleted.is_(False))
            query = apply_internship_record_scope(query, user)
            if keyword:
                query = query.where(StudentProfile.real_name.like(f"%{keyword.strip()}%"))
            total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
            pairs = db.execute(query.order_by(InternshipRecord.id.desc()).offset(
                (max(1, page) - 1) * page_size).limit(page_size)).all()
            return [_row(db, record, student, user) for record, student in pairs], total

        items = []
        for record, student in _scoped_records(db, user, batch_id=batch.id):
            if keyword and keyword.strip() not in (student.real_name or ""):
                continue
            item = _row(db, record, student, user)
            if item["archivePassed"]:
                continue
            items.append(item)
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


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
        return result


def archive_student(user, internship_id, force=False, expected_version=None,
                    force_reason="", evidence_file_ids=None,
                    record_expected_version=None) -> dict:
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

    with session() as db:
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
        db.commit()
        return {
            "id": str(record.id), "completeness": completeness,
            "missing": missing, "archived": True,
            "version": archive_version,
            "recordVersion": new_record_version,
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


def revoke_archive(user, internship_id, reason="", expected_version=None,
                   record_expected_version=None) -> dict:
    from app.core.permissions import is_super_admin
    role = str((user or {}).get("currentRoleCode") or
               (user or {}).get("userType") or "").upper()
    if role != "SCHOOL_ADMIN" and not is_super_admin(user or {}):
        raise no_permission("仅学校管理员可撤销归档")
    import re
    if len(re.findall(r"[\u4e00-\u9fff]", (reason or "").strip())) < 10:
        raise AppException("VALIDATION_ERROR", "撤销归档原因必填且不少于10个汉字")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
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
        new_archive_version = versioned_update(
            db, InternshipArchive, entity_id=archive.id, tenant_id=_tid(),
            expected_version=archive_version, expected_status="ARCHIVED",
            values={
                "status": "REVOKED", "revoked_by_name": _op_name(user),
                "revoked_at": datetime.utcnow(), "revoke_reason": reason.strip(),
                "package_invalidated_at": datetime.utcnow()
                if archive.package_file_id else None,
            })
        record.status = restore_status
        record.version = record_version + 1
        from app.models import InternshipEvidencePackage
        packages = db.scalars(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE",
            InternshipEvidencePackage.target_id == record.id,
            InternshipEvidencePackage.status.in_(("READY", "READY_WITH_MISSING")),
            InternshipEvidencePackage.is_deleted.is_(False)).with_for_update()).all()
        for package in packages:
            package.status = "INVALIDATED"
            package.invalidated_at = datetime.utcnow()
            package.invalidated_by_name = _op_name(user)
            package.invalidation_reason = reason.strip()
        _trail(db, record.id, "REVOKE", {
            "reason": reason.strip(), "invalidatedPackageCount": len(packages),
        }, operator=_op_name(user))
        db.commit()
        return {
            "id": str(record.id), "archived": False,
            "version": new_archive_version,
            "recordVersion": record.version,
            "recordStatus": restore_status,
            "packageInvalidated": bool(archive.package_file_id),
            "invalidatedPackageCount": len(packages),
        }


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


def _aggregate(pairs, db, user, group_key):
    groups = {}
    for record, _student in pairs:
        key = group_key(record) or "未分组"
        group = groups.setdefault(key, {
            "group": key, "total": 0, "archived": 0,
            "complete": 0, "sum": 0,
        })
        group["total"] += 1
        evaluation = _evaluation(db, record, user)
        completeness = round(float(evaluation["completeness"]["ratio"]) * 100)
        group["sum"] += completeness
        if evaluation["passed"]:
            group["complete"] += 1
        archive = _archive_row(db, record.id)
        if archive and archive.status == "ARCHIVED":
            group["archived"] += 1
    result = []
    for group in groups.values():
        group["avgCompleteness"] = round(group["sum"] / group["total"]) if group["total"] else 0
        group["archiveRate"] = round(
            group["archived"] / group["total"] * 100, 1) if group["total"] else 0
        del group["sum"]
        result.append(group)
    return sorted(result, key=lambda item: item["group"])


def by_batch(user=None, batch_id=None):
    from app.models import InternshipBatch
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        pairs = _scoped_records(db, user, batch_id=batch.id)
        names = {
            row.id: row.batch_name
            for row in db.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == _tid())).all()
        }
        return _aggregate(
            pairs, db, user,
            lambda record: names.get(record.batch_id, f"批次{record.batch_id}")
            if record.batch_id else "未分批")


def by_enterprise(user=None, batch_id=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    with session() as db:
        batch = resolve_batch(db, batch_id)
        pairs = _scoped_records(db, user, batch_id=batch.id)
        return _aggregate(
            pairs, db, user,
            lambda record: record.enterprise_name or "未分配企业")


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
