"""学生主档统一应用服务。

Stage C1 起，StudentProfile 的 student_status / college_id / major_id / class_id / grade
只是 StudentAcademicFact 的当前投影：已有学生的这些字段禁止在本服务里直接赋值。
新建学生由 StudentProfile after_insert 在同事务生成 version-1 fact；后续 academic
identity 变化全部调用 append_student_academic_fact。姓名、性别、电话、证件号等非学籍
身份字段继续使用本服务原有 CAS 与加密规则。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.core.field_crypto import encrypt_field, encrypt_sensitive, hash_sensitive
from app.core.student_lifecycle import ADMITTED
from app.core.student_master_contract import (
    ACTION_CONFLICT,
    ACTION_CREATE,
    ACTION_REUSE,
    ACTION_SKIP,
    CONFLICT_DUP_IN_FILE,
    CONFLICT_IDENTITY,
    CONFLICT_ORG,
    CONFLICT_VOIDED,
    ERR_STUDENT_NO_CONFLICT,
    ERR_VALIDATION,
    SOURCE_MANUAL,
    VALID_SOURCES,
    StudentCreateCommand,
    StudentCreateResult,
    StudentIdentityUpdateCommand,
    StudentResolution,
)
from app.models import StudentContact, StudentProfile, StudentStageEvent
from app.services.student_org_validator import validate_student_org_path


def _source_of(cmd) -> str:
    src = getattr(cmd, "source", None) or SOURCE_MANUAL
    return src if src in VALID_SOURCES else SOURCE_MANUAL


def _upsert_phone_in_session(db, *, tenant_id: int, student_id: int, phone: str | None) -> None:
    if not phone:
        return
    enc = encrypt_field(phone)
    row = db.scalars(select(StudentContact).where(
        StudentContact.tenant_id == tenant_id,
        StudentContact.student_id == student_id,
        StudentContact.contact_type == "PHONE",
    )).first()
    if row:
        row.contact_value_encrypted = enc
    else:
        db.add(StudentContact(
            tenant_id=tenant_id,
            student_id=student_id,
            contact_type="PHONE",
            contact_value_encrypted=enc,
            is_primary=True,
            verified_status="UNVERIFIED",
        ))


def _append_academic_identity_in_session(
    db,
    *,
    student: StudentProfile,
    source_type: str,
    source_ref_id=None,
    student_status=None,
    college_id=None,
    major_id=None,
    class_id=None,
    grade=None,
):
    """Call the Stage C1 canonical fact command with unchanged fields omitted."""
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
    )

    kwargs = {
        "source_type": source_type,
        "source_ref_id": int(source_ref_id) if source_ref_id is not None else None,
        "expected_student_version": int(student.version or 0),
    }
    if student_status is not None:
        kwargs["student_status"] = student_status
    if college_id is not None:
        kwargs["college_id"] = college_id
    if major_id is not None:
        kwargs["major_id"] = major_id
    if class_id is not None:
        kwargs["class_id"] = class_id
    if grade is not None:
        kwargs["grade"] = grade
    _fact, projected = append_student_academic_fact(db, int(student.id), **kwargs)
    return projected


def _ensure_restore_baseline_in_session(db, student: StudentProfile) -> None:
    """Legacy voided rows were excluded from C1 active-profile backfill.

    If a voided historical profile has no fact at all, create an explicitly INFERRED
    baseline from its current RECYCLED projection before restoring it. Existing facts
    are never rewritten or silently reconciled here.
    """
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        create_baseline_student_academic_fact,
        resolve_student_academic_fact,
    )

    if resolve_student_academic_fact(db, int(student.id), required=False) is not None:
        return
    create_baseline_student_academic_fact(
        db,
        student,
        valid_from=student.updated_at or student.created_at or datetime.utcnow(),
        source_type="VOIDED_RESTORE_BASELINE",
        source_quality="INFERRED",
    )


def create_student_in_session(
    db,
    *,
    tenant_id: int,
    cmd: StudentCreateCommand,
    actor: dict | None = None,
) -> StudentCreateResult:
    """事务内建档；新建 Profile 自动生成 EXACT v1 AcademicFact。"""
    no = cmd.normalized_no()
    name = cmd.normalized_name()
    if not no or not name:
        raise AppException(ERR_VALIDATION, "学号与姓名必填")

    org = validate_student_org_path(
        db,
        tenant_id=tenant_id,
        college_id=cmd.college_id,
        major_id=cmd.major_id,
        class_id=cmd.class_id,
        actor=actor,
        require_complete_org=bool(getattr(cmd, "require_complete_org", False)),
    )
    source = _source_of(cmd)
    stage = cmd.current_stage or ADMITTED

    active = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if active:
        raise AppException(ERR_STUDENT_NO_CONFLICT, "学号已存在（租户内唯一，不可复用为新档）")

    voided = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(True),
    )).first()
    if voided is not None:
        if not cmd.allow_restore:
            raise AppException(
                "VOIDED_PROFILE_EXISTS",
                f"学号 {no} 属于已作废档案（学号在校内永久唯一，不能另建新档）。"
                f"该生原姓名为「{voided.real_name or '—'}」，如确认是同一人，请走受控恢复流程。",
                http_status=409,
            )
        _ensure_restore_baseline_in_session(db, voided)
        # 先只恢复逻辑可见性，保持 academic projection 原值供 canonical command 做 drift 校验。
        voided.is_deleted = False
        db.flush()
        target_status = cmd.student_status or "NORMAL"
        academic_changed = (
            (voided.student_status or "NORMAL") != target_status
            or voided.grade != cmd.grade
            or voided.college_id != org.college_id
            or voided.major_id != org.major_id
            or voided.class_id != org.class_id
        )
        s = voided
        if academic_changed:
            s = _append_academic_identity_in_session(
                db,
                student=voided,
                source_type="PROFILE_RESTORE",
                student_status=target_status,
                college_id=org.college_id,
                major_id=org.major_id,
                class_id=org.class_id,
                grade=cmd.grade,
            )
        s.real_name = name
        s.gender = cmd.gender
        s.status = "ACTIVE"
        s.current_stage = stage
        s.remark = cmd.remark
        if cmd.enroll_date is not None:
            s.enroll_date = cmd.enroll_date
        if cmd.id_card:
            s.id_card_encrypted = encrypt_sensitive(cmd.id_card, "id_card")
            s.id_card_hash = hash_sensitive(cmd.id_card, "id_card")
        db.add(StudentStageEvent(
            tenant_id=tenant_id,
            student_id=s.id,
            from_stage="RECYCLED",
            to_stage=stage,
            reason="作废学号复活（复用原主档，非新建）",
            source_module=source,
        ))
        _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)
        _sync_projections(db, s)
        return StudentCreateResult(student_id=s.id, student_no=no, restored=True)

    s = StudentProfile(
        tenant_id=tenant_id,
        student_no=no,
        real_name=name,
        gender=cmd.gender,
        grade=cmd.grade,
        college_id=org.college_id,
        major_id=org.major_id,
        class_id=org.class_id,
        current_stage=stage,
        student_status=cmd.student_status or "NORMAL",
        status="ACTIVE",
        remark=cmd.remark,
        id_card_encrypted=encrypt_sensitive(cmd.id_card, "id_card") if cmd.id_card else None,
        id_card_hash=hash_sensitive(cmd.id_card, "id_card") if cmd.id_card else None,
    )
    if cmd.enroll_date is not None:
        s.enroll_date = cmd.enroll_date
    db.add(s)
    try:
        db.flush()
    except IntegrityError as exc:
        raise AppException(ERR_STUDENT_NO_CONFLICT, "学号已存在（租户内唯一）") from exc
    _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)
    db.add(StudentStageEvent(
        tenant_id=tenant_id,
        student_id=s.id,
        from_stage=None,
        to_stage=stage,
        reason="建档",
        source_module=source,
    ))
    return StudentCreateResult(student_id=s.id, student_no=no, restored=False)


def apply_approved_correction_in_session(
    db,
    *,
    tenant_id: int,
    student_id: int,
    field_key: str,
    new_value: str,
    expected_version: int,
    actor: dict | None = None,
    correction_id=None,
):
    """审核通过后的学籍信息更正；GRADE 走 AcademicFact，其它字段走原 CAS。"""
    field = str(field_key or "").strip().upper()
    plain = str(new_value or "").strip()
    if not plain:
        raise AppException(ERR_VALIDATION, "更正后的值不能为空")

    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if not s:
        raise not_found("学生主档不存在")
    current_version = int(s.version or 0)
    if expected_version is None or int(expected_version) != current_version:
        raise AppException(
            "DATA_CONFLICT",
            f"该学生档案已被他人修改（当前版本 {current_version}，本次基于 {expected_version}），请刷新后重新审核",
            http_status=409,
        )

    if field == "STUDENT_NO":
        dup = db.scalar(select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no == plain,
            StudentProfile.id != s.id,
        ))
        if dup:
            raise AppException("DATA_CONFLICT", f"学号 {plain} 已被占用（含已作废档案），无法更正", http_status=409)

    before = {
        "studentNo": s.student_no,
        "realName": s.real_name,
        "gender": s.gender,
        "grade": s.grade,
    }

    if field == "GRADE":
        if s.grade == plain:
            raise AppException("DATA_CONFLICT", "年级没有发生变化，无需更正", http_status=409)
        s = _append_academic_identity_in_session(
            db,
            student=s,
            source_type="PROFILE_CORRECTION",
            source_ref_id=correction_id,
            grade=plain,
        )
    else:
        updated = db.query(StudentProfile).filter(
            StudentProfile.id == s.id,
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.version == current_version,
        ).update({StudentProfile.version: current_version + 1}, synchronize_session=False)
        if not updated:
            raise AppException("DATA_CONFLICT", "该学生档案已被他人修改，请刷新后重新审核", http_status=409)
        if field == "STUDENT_NO":
            s.student_no = plain
        elif field == "REAL_NAME":
            s.real_name = plain
        elif field == "GENDER":
            s.gender = plain
        elif field == "ID_CARD":
            s.id_card_encrypted = encrypt_sensitive(plain, "id_card")
            s.id_card_hash = hash_sensitive(plain, "id_card")
        else:
            raise AppException(ERR_VALIDATION, f"不支持的更正字段：{field_key}")
        s.version = current_version + 1

    from app.services.db_service import audit_insert_in_session
    audit_insert_in_session(
        db,
        "学籍信息更正生效",
        "student",
        {
            "correctionId": str(correction_id or ""),
            "fieldKey": field,
            "studentNo": s.student_no,
            "before": before,
            "operator": (actor or {}).get("realName") or "",
            "roleCode": (actor or {}).get("currentRoleCode") or "",
        },
        "SUCCESS",
        tenant_id=tenant_id,
        resource_id=str(s.id),
    )
    _sync_projections(db, s)
    return s


def restore_voided_student_in_session(
    db,
    *,
    tenant_id: int,
    student_no: str,
    reason: str,
    actor: dict | None = None,
) -> dict:
    """受控恢复作废主档；RECYCLED→NORMAL 必须追加 AcademicFact。"""
    no = str(student_no or "").strip()
    why = str(reason or "").strip()
    if not no:
        raise AppException(ERR_VALIDATION, "请提供要恢复的学号")
    if len(why) < 5:
        raise AppException(ERR_VALIDATION, "恢复原因必填且不少于 5 个字")

    active = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if active is not None:
        raise AppException(
            ERR_STUDENT_NO_CONFLICT,
            f"学号 {no} 当前已有有效学生主档（{active.real_name or '—'}），无需也不能恢复",
            http_status=409,
        )
    voided = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(True),
    )).first()
    if voided is None:
        raise not_found(f"未找到学号 {no} 的已作废主档")

    before = {
        "studentStatus": voided.student_status,
        "currentStage": voided.current_stage,
        "isDeleted": True,
        "remark": voided.remark,
    }
    _ensure_restore_baseline_in_session(db, voided)
    voided.is_deleted = False
    db.flush()
    s = voided
    if (voided.student_status or "NORMAL") != "NORMAL":
        s = _append_academic_identity_in_session(
            db,
            student=voided,
            source_type="PROFILE_RESTORE",
            student_status="NORMAL",
        )
    s.status = "ACTIVE"
    if str(s.remark or "").startswith("VOID:"):
        s.remark = None

    after = {
        "studentStatus": s.student_status,
        "currentStage": s.current_stage,
        "isDeleted": False,
        "remark": s.remark,
    }
    db.add(StudentStageEvent(
        tenant_id=tenant_id,
        student_id=s.id,
        from_stage="RECYCLED",
        to_stage=s.current_stage,
        reason=f"受控恢复作废主档：{why}",
        source_module=SOURCE_MANUAL,
    ))
    _sync_projections(db, s)
    return {
        "studentId": s.id,
        "studentNo": no,
        "before": before,
        "after": after,
        "realName": s.real_name,
    }


def resolve_student_for_import(
    db,
    *,
    tenant_id: int,
    cmd: StudentCreateCommand,
    seen_nos: set | None = None,
    seen_id_cards: set | None = None,
) -> StudentResolution:
    """判定一行导入数据该新建、复用、跳过还是阻断。"""
    no = cmd.normalized_no()
    name = cmd.normalized_name()
    id_card = (cmd.id_card or "").strip() or None
    id_hash = hash_sensitive(id_card, "id_card") if id_card else None

    if seen_nos is not None and no in seen_nos:
        return StudentResolution(
            action=ACTION_CONFLICT,
            student_no=no,
            reason_code=CONFLICT_DUP_IN_FILE,
            message=f"文件内学号 {no} 重复出现，请先去重再导入",
        )
    if id_hash and seen_id_cards is not None and id_hash in seen_id_cards:
        return StudentResolution(
            action=ACTION_CONFLICT,
            student_no=no,
            reason_code=CONFLICT_DUP_IN_FILE,
            message=f"文件内身份证重复（学号 {no}），同一人不能导入两次",
        )

    same_no = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.student_no == no,
    )).first()
    if id_hash:
        other = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.id_card_hash == id_hash,
            StudentProfile.student_no != no,
        )).first()
        if other is not None:
            return StudentResolution(
                action=ACTION_CONFLICT,
                student_no=no,
                student_id=other.id,
                reason_code=CONFLICT_IDENTITY,
                message=f"该身份证已登记在学号 {other.student_no} 名下，与本次学号 {no} 不一致，请走身份核验",
            )
    if same_no is None:
        return StudentResolution(action=ACTION_CREATE, student_no=no)
    if same_no.is_deleted:
        return StudentResolution(
            action=ACTION_CONFLICT,
            student_no=no,
            student_id=same_no.id,
            reason_code=CONFLICT_VOIDED,
            message=f"学号 {no} 属于已作废档案；如确需恢复请走主档恢复流程，不要用批量导入",
        )
    if name and (same_no.real_name or "").strip() and name != (same_no.real_name or "").strip():
        return StudentResolution(
            action=ACTION_CONFLICT,
            student_no=no,
            student_id=same_no.id,
            reason_code=CONFLICT_IDENTITY,
            message=f"学号 {no} 在库中的姓名为「{same_no.real_name}」，与本次「{name}」不一致，请走身份核验",
        )
    if id_hash and same_no.id_card_hash and id_hash != same_no.id_card_hash:
        return StudentResolution(
            action=ACTION_CONFLICT,
            student_no=no,
            student_id=same_no.id,
            reason_code=CONFLICT_IDENTITY,
            message=f"学号 {no} 的证件号与库中记录不一致，请走身份核验",
        )

    fillable: dict = {}
    for col, incoming, label in (
        ("college_id", cmd.college_id, "学院"),
        ("major_id", cmd.major_id, "专业"),
        ("class_id", cmd.class_id, "班级"),
    ):
        if not incoming:
            continue
        cur = getattr(same_no, col, None)
        if cur and int(cur) != int(incoming):
            return StudentResolution(
                action=ACTION_CONFLICT,
                student_no=no,
                student_id=same_no.id,
                reason_code=CONFLICT_ORG,
                message=f"学号 {no} 已归属其它{label}，导入不得覆盖；调整院系班请走学籍异动",
            )
        if not cur:
            fillable[col] = int(incoming)
    for col, incoming in (("gender", cmd.gender), ("grade", cmd.grade)):
        if incoming and not getattr(same_no, col, None):
            fillable[col] = incoming
    if id_hash and not same_no.id_card_hash:
        fillable["id_card"] = cmd.id_card

    if fillable:
        return StudentResolution(
            action=ACTION_REUSE,
            student_id=same_no.id,
            student_no=no,
            fillable=fillable,
            message=f"复用已有主档并补齐 {len(fillable)} 项空缺信息",
        )
    return StudentResolution(
        action=ACTION_SKIP,
        student_id=same_no.id,
        student_no=no,
        message="主档已存在且信息一致，本次跳过",
    )


def apply_resolution_in_session(
    db,
    *,
    tenant_id: int,
    cmd: StudentCreateCommand,
    resolution: StudentResolution,
    actor: dict | None = None,
) -> StudentCreateResult:
    """导入复用：academic 空字段补齐也必须追加事实，不可直接改 Profile。"""
    if resolution.action == ACTION_CREATE:
        return create_student_in_session(db, tenant_id=tenant_id, cmd=cmd, actor=actor)
    if resolution.action == ACTION_SKIP:
        return StudentCreateResult(
            student_id=int(resolution.student_id or 0),
            student_no=resolution.student_no,
            restored=False,
        )
    if resolution.action != ACTION_REUSE:
        raise AppException(ERR_VALIDATION, resolution.message or "该行存在冲突，无法导入")

    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(resolution.student_id),
        StudentProfile.tenant_id == tenant_id,
    )).first()
    if not s:
        raise not_found("学生主档不存在")

    merged = {
        "college_id": resolution.fillable.get("college_id", s.college_id),
        "major_id": resolution.fillable.get("major_id", s.major_id),
        "class_id": resolution.fillable.get("class_id", s.class_id),
    }
    org = validate_student_org_path(
        db,
        tenant_id=tenant_id,
        college_id=merged["college_id"],
        major_id=merged["major_id"],
        class_id=merged["class_id"],
        actor=actor,
        require_complete_org=bool(getattr(cmd, "require_complete_org", False)),
    )
    before = {
        key: getattr(s, key, None)
        for key in ("college_id", "major_id", "class_id", "gender", "grade")
    }

    target_grade = resolution.fillable.get("grade", s.grade)
    academic_changed = (
        s.college_id != org.college_id
        or s.major_id != org.major_id
        or s.class_id != org.class_id
        or s.grade != target_grade
    )
    if academic_changed:
        kwargs = {}
        if s.college_id != org.college_id:
            kwargs["college_id"] = org.college_id
        if s.major_id != org.major_id:
            kwargs["major_id"] = org.major_id
        if s.class_id != org.class_id:
            kwargs["class_id"] = org.class_id
        if s.grade != target_grade:
            kwargs["grade"] = target_grade
        s = _append_academic_identity_in_session(
            db,
            student=s,
            source_type="IMPORT_PROFILE_FILL",
            **kwargs,
        )
        current_version = int(s.version or 0)
    else:
        current_version = int(s.version or 0)

    nonacademic_changed = False
    if "gender" in resolution.fillable and s.gender != resolution.fillable["gender"]:
        s.gender = resolution.fillable["gender"]
        nonacademic_changed = True
    if "id_card" in resolution.fillable and resolution.fillable["id_card"]:
        s.id_card_encrypted = encrypt_sensitive(resolution.fillable["id_card"], "id_card")
        s.id_card_hash = hash_sensitive(resolution.fillable["id_card"], "id_card")
        nonacademic_changed = True

    # If only non-academic fields changed, preserve the original one-command/one-version CAS.
    if nonacademic_changed and not academic_changed:
        loaded = int(s.version or 0)
        updated = db.query(StudentProfile).filter(
            StudentProfile.id == s.id,
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.version == loaded,
        ).update({StudentProfile.version: loaded + 1}, synchronize_session=False)
        if not updated:
            raise AppException("DATA_CONFLICT", "学生主档已被并发修改，请重新导入", http_status=409)
        s.version = loaded + 1

    after = {
        key: getattr(s, key, None)
        for key in ("college_id", "major_id", "class_id", "gender", "grade")
    }
    changed = {key: [before[key], after[key]] for key in before if before[key] != after[key]}
    if changed:
        db.add(StudentStageEvent(
            tenant_id=tenant_id,
            student_id=s.id,
            from_stage=s.current_stage,
            to_stage=s.current_stage,
            reason=f"导入补齐主档空缺字段：{changed}",
            source_module=_source_of(cmd),
        ))
    _sync_projections(db, s)
    return StudentCreateResult(student_id=s.id, student_no=s.student_no, restored=False)


def update_identity_in_session(
    db,
    *,
    tenant_id: int,
    student_id: int,
    cmd: StudentIdentityUpdateCommand,
    actor: dict | None = None,
) -> StudentProfile:
    """主档身份更正；grade 属 AcademicFact，其他可编辑字段仍用原 CAS。"""
    _ = actor
    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )).first()
    if not s:
        raise not_found("学生主档不存在")

    expected = cmd.expected_version
    if expected is None:
        raise AppException(ERR_VALIDATION, "缺少 expectedVersion，无法安全更新（并发保护）")
    current_version = int(s.version or 0)
    if int(expected) != current_version:
        raise AppException(
            "DATA_CONFLICT",
            f"该学生档案已被他人修改（当前版本 {current_version}，你提交的是 {expected}），请刷新后重试",
            http_status=409,
        )

    grade_changed = cmd.grade is not None and cmd.grade != s.grade
    if grade_changed:
        s = _append_academic_identity_in_session(
            db,
            student=s,
            source_type="PROFILE_IDENTITY_UPDATE",
            grade=cmd.grade,
        )
    else:
        updated = db.query(StudentProfile).filter(
            StudentProfile.id == s.id,
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.version == current_version,
        ).update({StudentProfile.version: current_version + 1}, synchronize_session=False)
        if not updated:
            raise AppException("DATA_CONFLICT", "该学生档案已被他人修改，请刷新后重试", http_status=409)
        s.version = current_version + 1

    if cmd.real_name is not None:
        s.real_name = str(cmd.real_name).strip()
    if cmd.gender is not None:
        s.gender = cmd.gender
    if cmd.remark is not None:
        s.remark = cmd.remark
    _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)

    _sync_projections(db, s)
    return s


def _sync_projections(db, s) -> None:
    from app.services.student_projection_sync import sync_student_projections_in_session

    sync_student_projections_in_session(db, s)
