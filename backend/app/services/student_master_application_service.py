"""学生主档统一应用服务（学生主档统一整改 阶段 B）。

`StudentProfile` 的**唯一**写入口。四条来源链（手工建档 / 公共导入 / 统一身份导入 /
教务学籍导入）此前各自 `StudentProfile(...)`，导致组织不校验、敏感字段口径不一、
学号唯一规则各写一遍。本服务把这些收敛成一处。

事务口径：
- `*_in_session(db, ...)` 只写不 commit，供批量导入在一个大事务里逐行复用，
  任一行失败由外层整体回滚；
- 不带 `_in_session` 的方法自开事务，供单条 API 使用；
- 主档变更、StudentStageEvent、投影刷新在**同一事务**内完成
  （投影用 sync_student_projections_in_session，不得 commit 后再同步）。

学号语义（沿用既有产品裁决，不得放宽）：
租户内学号永久唯一（含软删行，uk_tenant_student_no 全表唯一）；
作废后同号只能「复活」原主档 PK，禁止新建第二档，保证历史关联不断档。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.core.field_crypto import encrypt_field, encrypt_sensitive, hash_sensitive
from app.core.student_lifecycle import ADMITTED
from app.core.student_master_contract import (ERR_STUDENT_NO_CONFLICT, ERR_VALIDATION,
                                              SOURCE_MANUAL, VALID_SOURCES,
                                              StudentCreateCommand, StudentCreateResult,
                                              StudentIdentityUpdateCommand)
from app.models import StudentContact, StudentProfile, StudentStageEvent
from app.services.student_org_validator import validate_student_org_path


def _source_of(cmd) -> str:
    src = getattr(cmd, "source", None) or SOURCE_MANUAL
    return src if src in VALID_SOURCES else SOURCE_MANUAL


def _upsert_phone_in_session(db, *, tenant_id: int, student_id: int, phone: str | None) -> None:
    """手机号写入 StudentContact（密文列），不落到主档表。"""
    if not phone:
        return
    enc = encrypt_field(phone)
    row = db.scalars(select(StudentContact).where(
        StudentContact.tenant_id == tenant_id, StudentContact.student_id == student_id,
        StudentContact.contact_type == "PHONE")).first()
    if row:
        row.contact_value_encrypted = enc
    else:
        db.add(StudentContact(tenant_id=tenant_id, student_id=student_id, contact_type="PHONE",
                              contact_value_encrypted=enc, is_primary=True,
                              verified_status="UNVERIFIED"))


def create_student_in_session(db, *, tenant_id: int, cmd: StudentCreateCommand,
                              actor: dict | None = None) -> StudentCreateResult:
    """事务内建档。批量导入逐行调用本函数，由调用方统一 commit。"""
    no = cmd.normalized_no()
    name = cmd.normalized_name()
    if not no or not name:
        raise AppException(ERR_VALIDATION, "学号与姓名必填")

    org = validate_student_org_path(
        db, tenant_id=tenant_id, college_id=cmd.college_id, major_id=cmd.major_id,
        class_id=cmd.class_id, actor=actor)
    source = _source_of(cmd)
    stage = cmd.current_stage or ADMITTED

    active = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(False))).first()
    if active:
        raise AppException(ERR_STUDENT_NO_CONFLICT, "学号已存在（租户内唯一，不可复用为新档）")

    voided = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(True))).first()

    if voided is not None:
        if not cmd.allow_restore:
            raise AppException(ERR_STUDENT_NO_CONFLICT,
                               f"学号 {no} 属于已作废档案，请改用主档恢复流程")
        s = voided
        s.is_deleted = False
        s.real_name = name
        s.gender = cmd.gender
        s.grade = cmd.grade
        s.college_id = org.college_id
        s.major_id = org.major_id
        s.class_id = org.class_id
        s.student_status = cmd.student_status or "NORMAL"
        s.status = "ACTIVE"
        s.current_stage = stage
        s.remark = cmd.remark
        if cmd.enroll_date is not None:
            s.enroll_date = cmd.enroll_date
        if cmd.id_card:
            s.id_card_encrypted = encrypt_sensitive(cmd.id_card, "id_card")
            s.id_card_hash = hash_sensitive(cmd.id_card, "id_card")
        s.version = int(s.version or 0) + 1
        db.add(StudentStageEvent(tenant_id=tenant_id, student_id=s.id, from_stage="RECYCLED",
                                 to_stage=stage, reason="作废学号复活（复用原主档，非新建）",
                                 source_module=source))
        _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)
        _sync_projections(db, s)
        return StudentCreateResult(student_id=s.id, student_no=no, restored=True)

    s = StudentProfile(
        tenant_id=tenant_id, student_no=no, real_name=name,
        gender=cmd.gender, grade=cmd.grade,
        college_id=org.college_id, major_id=org.major_id, class_id=org.class_id,
        current_stage=stage, student_status=cmd.student_status or "NORMAL", status="ACTIVE",
        remark=cmd.remark,
        id_card_encrypted=encrypt_sensitive(cmd.id_card, "id_card") if cmd.id_card else None,
        id_card_hash=hash_sensitive(cmd.id_card, "id_card") if cmd.id_card else None)
    if cmd.enroll_date is not None:
        s.enroll_date = cmd.enroll_date
    db.add(s)
    try:
        db.flush()
    except IntegrityError as e:
        # 并发下同一学号可能刚被另一个事务插入；唯一键是最后防线
        raise AppException(ERR_STUDENT_NO_CONFLICT, "学号已存在（租户内唯一）") from e
    _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)
    db.add(StudentStageEvent(tenant_id=tenant_id, student_id=s.id, from_stage=None,
                             to_stage=stage, reason="建档", source_module=source))
    return StudentCreateResult(student_id=s.id, student_no=no, restored=False)


def update_identity_in_session(db, *, tenant_id: int, student_id: int,
                               cmd: StudentIdentityUpdateCommand,
                               actor: dict | None = None) -> StudentProfile:
    """事务内更正身份字段，带原子乐观锁。

    组织归属不在此处改——学院/专业/班级调整必须走学籍异动（唯一入口
    change_student_status），否则会绕过审批留痕。
    """
    _ = actor
    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id), StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False))).first()
    if not s:
        raise not_found("学生主档不存在")

    expected = cmd.expected_version
    if expected is None:
        raise AppException(ERR_VALIDATION, "缺少 expectedVersion，无法安全更新（并发保护）")
    current_version = int(s.version or 0)
    if int(expected) != current_version:
        raise AppException("DATA_CONFLICT",
                           "该学生档案已被他人修改（当前版本 "
                           f"{current_version}，你提交的是 {expected}），请刷新后重试",
                           http_status=409)

    # 原子 CAS：条件更新命中 0 行说明版本已被并发改走，绝不能用「先读后写」代替
    updated = db.query(StudentProfile).filter(
        StudentProfile.id == s.id,
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.version == current_version,
    ).update({StudentProfile.version: current_version + 1}, synchronize_session=False)
    if not updated:
        raise AppException("DATA_CONFLICT", "该学生档案已被他人修改，请刷新后重试", http_status=409)

    if cmd.real_name is not None:
        s.real_name = str(cmd.real_name).strip()
    if cmd.gender is not None:
        s.gender = cmd.gender
    if cmd.grade is not None:
        s.grade = cmd.grade
    if cmd.remark is not None:
        s.remark = cmd.remark
    _upsert_phone_in_session(db, tenant_id=tenant_id, student_id=s.id, phone=cmd.phone)

    # CAS 已在库里把 version 递增；同步 ORM 实例，避免随后 flush 时又写回旧值
    s.version = current_version + 1
    _sync_projections(db, s)
    return s


def _sync_projections(db, s) -> None:
    """同事务刷新在校服务/毕设投影：失败与主档一起回滚，不产生假失败。"""
    from app.services.student_projection_sync import sync_student_projections_in_session
    sync_student_projections_in_session(db, s)
