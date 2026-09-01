"""O3 canonical student pre-arrival self service.

All writes resolve the logged-in StudentProfile first and then require an explicit
OrientationStudent.student_id link.  Names and admission numbers are display facts,
never authorization keys.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.field_crypto import encrypt_field, hash_sensitive, mask_phone_encrypted
from app.core.optimistic_lock import require_expected_version
from app.models import (
    FileObject,
    OrientationArrivalPlan,
    OrientationBatch,
    OrientationMaterial,
    OrientationStudent,
    StudentContact,
)
from app.models.file import FileAsset, FileBinding, FileVersion
from app.services.db_service import _iso, _tid, session
from app.services.orientation_flow_service import set_student_step_status

ARRIVAL_MODES = {"TRAIN", "AIR", "COACH", "SELF_DRIVE", "CITY_TRANSIT", "OTHER"}
MATERIAL_TYPES = {"ID_CARD", "ADMISSION_LETTER", "PHOTO", "ARCHIVE"}


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_datetime(value: Any, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise AppException("VALIDATION_ERROR", f"{field} 必填")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field} 格式不正确") from exc


def _phone(value: Any, field: str) -> str:
    raw = _text(value, 20)
    if not raw or not raw.isdigit() or not 6 <= len(raw) <= 20:
        raise AppException("VALIDATION_ERROR", f"{field}格式不正确")
    return raw


def _own_context(db, user: dict, *, lock: bool = False):
    from app.services.mobile_student_service import resolve_student

    profile = resolve_student(db, user or {})
    if not profile:
        raise AppException("NO_PERMISSION", "当前账号未绑定稳定学生身份，请联系学校处理")
    stmt = (
        select(OrientationStudent, OrientationBatch)
        .join(
            OrientationBatch,
            (OrientationBatch.id == OrientationStudent.batch_id)
            & (OrientationBatch.tenant_id == OrientationStudent.tenant_id),
        )
        .where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.student_id == int(profile.id),
            OrientationStudent.identity_status == "LINKED",
            OrientationStudent.record_status == "ACTIVE",
            OrientationStudent.is_deleted.is_(False),
            OrientationBatch.status == "ACTIVE",
            OrientationBatch.is_deleted.is_(False),
        )
        .order_by(OrientationStudent.id.desc())
    )
    if lock:
        stmt = stmt.with_for_update()
    rows = db.execute(stmt).all()
    if not rows:
        raise AppException("DATA_NOT_FOUND", "未找到已绑定且开放的本人迎新记录，请联系学校处理")
    if len(rows) > 1:
        raise AppException("DATA_CONFLICT", "本人同时存在多个开放迎新批次，请联系学校处理")
    orientation, batch = rows[0]
    if orientation.report_status in {"CHECKED_IN", "COLLEGE_CONFIRMED"}:
        raise AppException("DATA_CONFLICT", "已完成现场报到，预报到信息不可继续修改")
    now = datetime.utcnow()
    if batch.start_date and now < batch.start_date:
        raise AppException("DATA_CONFLICT", "预报到尚未开放")
    if batch.end_date and now > batch.end_date:
        raise AppException("DATA_CONFLICT", "预报到已结束")
    return profile, orientation, batch


def _contact(db, student_id: int, contact_type: str):
    return db.scalars(
        select(StudentContact)
        .where(
            StudentContact.tenant_id == _tid(),
            StudentContact.student_id == student_id,
            StudentContact.contact_type == contact_type,
            StudentContact.is_deleted.is_(False),
        )
        .order_by(StudentContact.is_primary.desc(), StudentContact.id.desc())
    ).first()


def _upsert_contact(db, *, student_id: int, contact_type: str, value: str,
                    contact_name: str | None = None) -> StudentContact:
    row = db.scalars(
        select(StudentContact)
        .where(
            StudentContact.tenant_id == _tid(),
            StudentContact.student_id == student_id,
            StudentContact.contact_type == contact_type,
            StudentContact.is_deleted.is_(False),
        )
        .order_by(StudentContact.is_primary.desc(), StudentContact.id.desc())
        .with_for_update()
    ).first()
    if row is None:
        row = StudentContact(
            tenant_id=_tid(), student_id=student_id, contact_type=contact_type,
            verified_status="UNVERIFIED", is_primary=True,
        )
        db.add(row)
    row.contact_value_encrypted = encrypt_field(value)
    row.contact_value_hash = hash_sensitive(value, "phone")
    row.contact_name = contact_name
    row.is_primary = True
    row.version = int(row.version or 0) + 1
    return row


def _arrival_payload(row: OrientationArrivalPlan | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id), "version": int(row.version or 0),
        "arrivalMode": row.arrival_mode,
        "plannedArrivalAt": _iso(row.planned_arrival_at),
        "stationName": row.station_name or "", "transportNo": row.transport_no or "",
        "pickupRequired": bool(row.pickup_required),
        "companionCount": int(row.companion_count or 0), "status": row.status,
        "submittedAt": _iso(row.submitted_at),
    }


def _material_payload(db, row: OrientationMaterial) -> dict:
    binding = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == "ORIENTATION_MATERIAL",
        FileBinding.biz_id == str(row.id),
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id.desc())).first()
    return {
        "id": str(row.id), "materialType": row.material_type,
        "fileId": str(binding.file_id) if binding else "",
        "fileName": row.file_name or "", "submissionNo": int(row.submission_no or 1),
        "isCurrent": bool(row.is_current), "status": row.status,
        "returnReason": row.return_reason or "", "submitTime": _iso(row.submit_time),
        "reviewTime": _iso(row.review_time), "assetId": str(row.asset_id or ""),
        "fileVersionId": str(row.file_version_id or ""),
    }


def snapshot(user: dict) -> dict:
    with session() as db:
        profile, orientation, batch = _own_context(db, user)
        phone = _contact(db, profile.id, "PHONE")
        emergency = _contact(db, profile.id, "EMERGENCY_PHONE")
        arrival = db.scalars(select(OrientationArrivalPlan).where(
            OrientationArrivalPlan.tenant_id == _tid(),
            OrientationArrivalPlan.ori_student_id == orientation.id,
            OrientationArrivalPlan.student_id == profile.id,
            OrientationArrivalPlan.is_deleted.is_(False),
        )).first()
        materials = list(db.scalars(select(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.ori_student_id == orientation.id,
            OrientationMaterial.student_id == profile.id,
            OrientationMaterial.is_deleted.is_(False),
        ).order_by(OrientationMaterial.material_type, OrientationMaterial.submission_no.desc())).all())
        return {
            "orientationStudentId": str(orientation.id), "studentId": str(profile.id),
            "batch": {
                "id": str(batch.id), "name": batch.batch_name,
                "reportStartAt": _iso(batch.report_start_date),
                "reportEndAt": _iso(batch.report_end_date),
            },
            "information": {
                "origin": orientation.origin or "",
                "phoneMasked": mask_phone_encrypted(
                    phone.contact_value_encrypted if phone else orientation.phone_encrypted
                ),
                "emergencyContactName": emergency.contact_name or "" if emergency else "",
                "emergencyPhoneMasked": mask_phone_encrypted(
                    emergency.contact_value_encrypted if emergency else None
                ),
                "complete": bool(phone and emergency and orientation.origin),
            },
            "arrivalPlan": _arrival_payload(arrival),
            "materials": [_material_payload(db, row) for row in materials],
            "materialTypes": sorted(MATERIAL_TYPES),
        }


def submit_information(user: dict, body: dict) -> dict:
    if (body or {}).get("confirmed") is not True:
        raise AppException("VALIDATION_ERROR", "请确认所填信息真实有效")
    phone = _phone((body or {}).get("phone"), "联系电话")
    emergency_phone = _phone((body or {}).get("emergencyPhone"), "紧急联系人电话")
    emergency_name = _text((body or {}).get("emergencyContactName"), 100)
    origin = _text((body or {}).get("origin"), 100)
    if not emergency_name or not origin:
        raise AppException("VALIDATION_ERROR", "生源地、紧急联系人姓名均必填")
    with session() as db:
        profile, orientation, _batch = _own_context(db, user, lock=True)
        _upsert_contact(db, student_id=profile.id, contact_type="PHONE", value=phone)
        _upsert_contact(
            db, student_id=profile.id, contact_type="EMERGENCY_PHONE",
            value=emergency_phone, contact_name=emergency_name,
        )
        orientation.phone_encrypted = encrypt_field(phone)  # 兼容教师端只读投影
        orientation.origin = origin
        set_student_step_status(
            db, orientation, "INFO", "DONE", status_source="PROCESS_FACT",
            source_biz_id=f"student:{profile.id}:orientation-info",
        )
        if orientation.blocked_step == "INFO":
            orientation.blocked_step = None
            orientation.blocked_reason = None
        if orientation.report_status == "NOT_REPORTED":
            orientation.report_status = "PREPARED"
        orientation.version = int(orientation.version or 0) + 1
        from app.services.orientation_service import _audit
        _audit(db, "PROGRESS", orientation.id, "学生提交预报到信息", "稳定学生主档联系方式已更新")
        db.commit()
        return {"id": str(orientation.id), "reportStatus": orientation.report_status}


def submit_arrival_plan(user: dict, body: dict) -> dict:
    mode = _text((body or {}).get("arrivalMode"), 30).upper()
    if mode not in ARRIVAL_MODES:
        raise AppException("VALIDATION_ERROR", "请选择有效到校方式")
    arrival_at = _parse_datetime((body or {}).get("plannedArrivalAt"), "计划到校时间")
    station = _text((body or {}).get("stationName"), 200)
    transport_no = _text((body or {}).get("transportNo"), 100)
    pickup = bool((body or {}).get("pickupRequired", False))
    try:
        companions = int((body or {}).get("companionCount", 0))
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "随行人数须为整数") from exc
    if not 0 <= companions <= 20:
        raise AppException("VALIDATION_ERROR", "随行人数须在 0 到 20 之间")
    if pickup and not station:
        raise AppException("VALIDATION_ERROR", "申请接站时须填写到达站点")
    if pickup and mode == "SELF_DRIVE":
        raise AppException("VALIDATION_ERROR", "自驾到校不可申请学校接站")
    expected = require_expected_version((body or {}).get("expectedVersion"))
    with session() as db:
        profile, orientation, batch = _own_context(db, user, lock=True)
        if batch.report_start_date and arrival_at < batch.report_start_date:
            raise AppException("VALIDATION_ERROR", "计划到校时间早于批次报到开始时间")
        if batch.report_end_date and arrival_at > batch.report_end_date:
            raise AppException("VALIDATION_ERROR", "计划到校时间晚于批次报到结束时间")
        row = db.scalars(select(OrientationArrivalPlan).where(
            OrientationArrivalPlan.tenant_id == _tid(),
            OrientationArrivalPlan.ori_student_id == orientation.id,
            OrientationArrivalPlan.is_deleted.is_(False),
        ).with_for_update()).first()
        current = int(row.version or 0) if row else 0
        if expected != current:
            raise AppException("APPROVAL_VERSION_CONFLICT", "到校计划已变化，请刷新后重试")
        now = datetime.utcnow()
        if row is None:
            row = OrientationArrivalPlan(
                tenant_id=_tid(), ori_student_id=orientation.id, student_id=profile.id,
                arrival_mode=mode, planned_arrival_at=arrival_at, status="SUBMITTED",
                submitted_at=now, version=1,
            )
            db.add(row)
        else:
            row.arrival_mode = mode
            row.planned_arrival_at = arrival_at
            row.status = "SUBMITTED"
            row.submitted_at = now
            row.version = current + 1
        row.station_name = station or None
        row.transport_no = transport_no or None
        row.pickup_required = pickup
        row.companion_count = companions
        orientation.version = int(orientation.version or 0) + 1
        db.flush()
        from app.services.orientation_service import _audit
        _audit(db, "ARRIVAL", row.id, "学生提交到校计划", f"{mode} / {_iso(arrival_at)}")
        db.commit()
        return _arrival_payload(row)


def _create_file_version(db, *, profile, orientation, material: OrientationMaterial,
                         file_obj: FileObject, user: dict) -> tuple[FileAsset, FileVersion]:
    code = f"ORIENTATION:{_tid()}:{profile.id}:{material.material_type}"
    asset = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if asset is None:
        asset = FileAsset(
            tenant_id=_tid(), asset_code=code,
            title=f"{profile.real_name}·迎新{material.material_type}",
            category_code=material.material_type, owner_type="ORIENTATION_STUDENT",
            owner_id=str(profile.id), lifecycle_status="ACTIVE", version_count=0,
            sensitivity_level="SENSITIVE",
        )
        db.add(asset)
        db.flush()
    duplicate = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == asset.id,
        FileVersion.file_object_id == file_obj.id, FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if duplicate:
        raise AppException("DATA_CONFLICT", "该文件已提交过，请上传修改后的新文件")
    current_versions = list(db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == asset.id,
        FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
    ).with_for_update()).all())
    now = datetime.utcnow()
    for old in current_versions:
        old.is_current = False
        if old.status not in {"APPROVED", "ARCHIVED"}:
            old.status = "INVALIDATED"
            old.invalidated_at = now
            old.invalid_reason = "迎新材料受控重交新版本"
    old_bindings = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.asset_id == asset.id,
        FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False),
    ).with_for_update()).all())
    for old in old_bindings:
        old.is_current = False
        old.status = "SUPERSEDED"
        old.invalidated_at = now
    next_no = int(db.scalar(select(func.max(FileVersion.version_no)).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == asset.id,
    )) or 0) + 1
    version = FileVersion(
        tenant_id=_tid(), asset_id=asset.id, file_object_id=file_obj.id,
        version_no=next_no, source_channel="ORIENTATION_SELF_SERVICE",
        uploader_user_id=str(user.get("userId") or "") or None,
        uploader_name_snapshot=profile.real_name, status="SUBMITTED",
        is_current=True, submitted_at=now,
    )
    db.add(version)
    db.flush()
    asset.current_version_id = version.id
    asset.version_count = next_no
    asset.version = int(asset.version or 0) + 1
    return asset, version


def submit_material(user: dict, body: dict) -> dict:
    material_type = _text((body or {}).get("materialType"), 50).upper()
    if material_type not in MATERIAL_TYPES:
        raise AppException("VALIDATION_ERROR", "材料类型不在预报到开放范围内")
    file_id = _text((body or {}).get("fileId"), 30)
    client_id = _text((body or {}).get("clientSubmissionId"), 100)
    if not file_id.isdigit() or len(client_id) < 8:
        raise AppException("VALIDATION_ERROR", "fileId 与 clientSubmissionId 必填")
    with session() as db:
        profile, orientation, _batch = _own_context(db, user, lock=True)
        prior = db.scalars(select(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.client_submission_id == client_id,
            OrientationMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if prior:
            if prior.student_id == profile.id and prior.material_type == material_type:
                prior_version = db.get(FileVersion, prior.file_version_id) if prior.file_version_id else None
                if prior_version and int(prior_version.file_object_id) == int(file_id):
                    return _material_payload(db, prior)
                raise AppException(
                    "IDEMPOTENCY_CONFLICT",
                    "clientSubmissionId 的 fileId 与首次提交不一致",
                )
            raise AppException("IDEMPOTENCY_CONFLICT", "clientSubmissionId 已用于其他材料")
        current = db.scalars(select(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.ori_student_id == orientation.id,
            OrientationMaterial.student_id == profile.id,
            OrientationMaterial.material_type == material_type,
            OrientationMaterial.is_current.is_(True),
            OrientationMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if current and current.status in {"UPLOADED", "APPROVED"}:
            raise AppException("DATA_CONFLICT", "该材料正在审核或已通过，不可重复提交")
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise AppException("DATA_NOT_FOUND", "文件不存在或不在当前数据范围内")
        next_submission = int(current.submission_no or 0) + 1 if current else 1
        if current:
            current.is_current = False
            current.version = int(current.version or 0) + 1
        row = OrientationMaterial(
            tenant_id=_tid(), ori_student_id=orientation.id, student_id=profile.id,
            material_type=material_type, file_name=file_obj.file_name,
            submission_no=next_submission, is_current=True,
            supersedes_material_id=current.id if current else None,
            source_type="STUDENT_SELF_SERVICE", client_submission_id=client_id,
            submit_time=datetime.utcnow(), status="UPLOADED",
        )
        db.add(row)
        db.flush()
        from app.services.file_business_binding_service import bind_file_to_business
        binding = bind_file_to_business(
            db, file_id=file_id, biz_type="ORIENTATION_MATERIAL", biz_id=row.id,
            actor=user or {}, subject_type="STUDENT", subject_id=profile.id,
            relation_type="MATERIAL_SUBMISSION", module_code="ORIENTATION",
            student_id=profile.id, batch_id=str(orientation.batch_id),
            college_id=profile.college_id, class_id=profile.class_id,
            scope={
                "orientationStudentId": str(orientation.id), "studentId": str(profile.id),
                "materialType": material_type, "submissionNo": next_submission,
            },
        )
        asset, version = _create_file_version(
            db, profile=profile, orientation=orientation, material=row,
            file_obj=file_obj, user=user or {},
        )
        binding.asset_id = asset.id
        binding.version_id = version.id
        binding.version_no = version.version_no
        row.asset_id = asset.id
        row.file_version_id = version.id
        orientation.material_status = "UPLOADED"
        set_student_step_status(
            db, orientation, "MATERIAL", "IN_PROGRESS", status_source="PROCESS_FACT",
            source_biz_id=f"orientation-material:{row.id}",
        )
        orientation.version = int(orientation.version or 0) + 1
        from app.services.orientation_service import _audit
        _audit(db, "MATERIAL", row.id, "学生提交迎新材料", f"{material_type} 第 {next_submission} 版")
        db.commit()
        return _material_payload(db, row)
