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
from app.core.student_master_contract import (ACTION_CONFLICT, ACTION_CREATE, ACTION_REUSE,
                                              ACTION_SKIP, CONFLICT_DUP_IN_FILE,
                                              CONFLICT_IDENTITY, CONFLICT_ORG, CONFLICT_VOIDED,
                                              ERR_STUDENT_NO_CONFLICT, ERR_VALIDATION,
                                              SOURCE_MANUAL, VALID_SOURCES,
                                              StudentCreateCommand, StudentCreateResult,
                                              StudentIdentityUpdateCommand, StudentResolution)
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
        class_id=cmd.class_id, actor=actor,
        require_complete_org=bool(getattr(cmd, "require_complete_org", False)))
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
            # 错误码单列，前端据此弹「确认恢复」而不是把它当成普通重复学号
            raise AppException(
                "VOIDED_PROFILE_EXISTS",
                f"学号 {no} 属于已作废档案（学号在校内永久唯一，不能另建新档）。"
                f"该生原姓名为「{voided.real_name or '—'}」，如确认是同一人，"
                "可勾选「恢复该作废档案」后重新提交；恢复将复用原档案并记入审计。",
                http_status=409)
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


def apply_approved_correction_in_session(db, *, tenant_id: int, student_id: int, field_key: str,
                                         new_value: str, expected_version: int,
                                         actor: dict | None = None, correction_id=None):
    """学籍信息更正审核通过后写主档（教务审核链路的唯一落库口）。

    用调用方的事务，**不自行 commit**：更正单状态与主档修改必须一起成功或一起回滚。
    此前教务侧审核通过是直接改 ORM 并 `version += 1`，绕过了统一服务的
    CAS 乐观锁与投影同步——那正是本次整改要消灭的非原子写法。

    阶段 C 待办（本方法刻意不做，避免扩大施工）：
    学号更正对登录账号（StudentAccountLink / User.login_name）、消息受众、
    首页缓存、家长授权 snapshot 的联动，依赖阶段 C 的账号链接表。
    """
    from app.models import StudentProfile

    field = str(field_key or "").strip().upper()
    plain = str(new_value or "").strip()
    if not plain:
        raise AppException(ERR_VALIDATION, "更正后的值不能为空")

    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(student_id), StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False))).first()
    if not s:
        raise not_found("学生主档不存在")

    current_version = int(s.version or 0)
    if expected_version is None or int(expected_version) != current_version:
        raise AppException("DATA_CONFLICT",
                           f"该学生档案已被他人修改（当前版本 {current_version}，"
                           f"本次基于 {expected_version}），请刷新后重新审核",
                           http_status=409)

    # 学号：租户内永久唯一，查重必须覆盖软删行，否则审核通过时会撞 uk_tenant_student_no
    if field == "STUDENT_NO":
        dup = db.scalar(select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no == plain,
            StudentProfile.id != s.id))
        if dup:
            raise AppException("DATA_CONFLICT",
                               f"学号 {plain} 已被占用（含已作废档案），无法更正",
                               http_status=409)

    # 原子 CAS：命中 0 行说明版本已被并发改走
    updated = db.query(StudentProfile).filter(
        StudentProfile.id == s.id,
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.version == current_version,
    ).update({StudentProfile.version: current_version + 1}, synchronize_session=False)
    if not updated:
        raise AppException("DATA_CONFLICT", "该学生档案已被他人修改，请刷新后重新审核",
                           http_status=409)

    before = {"studentNo": s.student_no, "realName": s.real_name,
              "gender": s.gender, "grade": s.grade}
    if field == "STUDENT_NO":
        s.student_no = plain
    elif field == "REAL_NAME":
        s.real_name = plain
    elif field == "GENDER":
        s.gender = plain
    elif field == "GRADE":
        s.grade = plain
    elif field == "ID_CARD":
        # 继续走现有强加密与 HMAC，不得退回明文或裸 SHA256
        s.id_card_encrypted = encrypt_sensitive(plain, "id_card")
        s.id_card_hash = hash_sensitive(plain, "id_card")
    else:
        raise AppException(ERR_VALIDATION, f"不支持的更正字段：{field_key}")
    s.version = current_version + 1

    from app.services.db_service import audit_insert_in_session
    audit_insert_in_session(
        db, "学籍信息更正生效", "student",
        {"correctionId": str(correction_id or ""), "fieldKey": field,
         "studentNo": s.student_no,
         # 证件号不入审计明文，其它字段记录前后值便于追溯
         "before": {k: v for k, v in before.items() if field != "ID_CARD" or k != "studentNo"},
         "operator": (actor or {}).get("realName") or "",
         "roleCode": (actor or {}).get("currentRoleCode") or ""},
        "SUCCESS",
        # 本方法已显式接收 tenant_id，审计就不该再回头依赖隐式请求上下文——
        # 否则后台任务/服务层直调时会因缺上下文而写不了审计。
        tenant_id=tenant_id, resource_id=str(s.id))

    _sync_projections(db, s)
    return s


def restore_voided_student_in_session(db, *, tenant_id: int, student_no: str, reason: str,
                                      actor: dict | None = None) -> dict:
    """受控恢复已作废学生主档。

    与「再补录一次」的本质区别：恢复复用原 studentId 与全部历史业务关联
    （成绩、实习、毕设、审批、消息都挂在原 ID 上），因此必须是独立动作、
    独立权限、必须填原因、必须留审计，而不是建档流程里的一个开关。

    不做的事：**不动登录账号**。账号是否启用、是否强制改密由账号管理单独处理——
    恢复学籍与恢复登录能力是两件事，混在一起会让「恢复档案」顺手打开一个
    本该保持停用的账号。
    """
    from app.models import StudentProfile

    no = str(student_no or "").strip()
    why = str(reason or "").strip()
    if not no:
        raise AppException(ERR_VALIDATION, "请提供要恢复的学号")
    if len(why) < 5:
        raise AppException(ERR_VALIDATION, "恢复原因必填且不少于 5 个字")

    # 恢复前重新确认：期间可能已有人用同学号建了新档，这时必须拒绝而不是撞唯一键
    active = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(False))).first()
    if active is not None:
        raise AppException(
            ERR_STUDENT_NO_CONFLICT,
            f"学号 {no} 当前已有有效学生主档（{active.real_name or '—'}），无需也不能恢复",
            http_status=409)

    voided = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no,
        StudentProfile.is_deleted.is_(True))).first()
    if voided is None:
        raise not_found(f"未找到学号 {no} 的已作废主档")

    before = {"studentStatus": voided.student_status, "currentStage": voided.current_stage,
              "isDeleted": True, "remark": voided.remark}

    voided.is_deleted = False
    voided.student_status = "NORMAL"
    voided.status = "ACTIVE"
    # 作废时把原因写进了 remark（VOID:xxx），恢复后清掉，避免它被当成风险等级读
    if str(voided.remark or "").startswith("VOID:"):
        voided.remark = None
    voided.version = int(voided.version or 0) + 1

    after = {"studentStatus": voided.student_status, "currentStage": voided.current_stage,
             "isDeleted": False, "remark": voided.remark}

    db.add(StudentStageEvent(
        tenant_id=tenant_id, student_id=voided.id, from_stage="RECYCLED",
        to_stage=voided.current_stage, reason=f"受控恢复作废主档：{why}",
        source_module=SOURCE_MANUAL))
    _sync_projections(db, voided)
    return {"studentId": voided.id, "studentNo": no, "before": before, "after": after,
            "realName": voided.real_name}


def resolve_student_for_import(db, *, tenant_id: int, cmd: StudentCreateCommand,
                               seen_nos: set | None = None,
                               seen_id_cards: set | None = None) -> StudentResolution:
    """判定一行导入数据该新建、复用、跳过还是阻断。

    两个正式入口（教务学籍导入 / 系统管理学生导入）共用本函数，规则不得各写一份。
    预检与落库都调它——预检只是提前展示，落库时必须重新判定，期间数据可能已变。

    查询范围限本租户：跨租户既不匹配也不回报存在性，避免用学号探测其它学校数据。
    """
    from app.models import StudentProfile

    no = cmd.normalized_no()
    name = cmd.normalized_name()
    id_card = (cmd.id_card or "").strip() or None
    id_hash = hash_sensitive(id_card, "id_card") if id_card else None

    # 文件内重复：同一批里同学号/同身份证只能出现一次
    if seen_nos is not None and no in seen_nos:
        return StudentResolution(action=ACTION_CONFLICT, student_no=no,
                                 reason_code=CONFLICT_DUP_IN_FILE,
                                 message=f"文件内学号 {no} 重复出现，请先去重再导入")
    if id_hash and seen_id_cards is not None and id_hash in seen_id_cards:
        return StudentResolution(action=ACTION_CONFLICT, student_no=no,
                                 reason_code=CONFLICT_DUP_IN_FILE,
                                 message=f"文件内身份证重复（学号 {no}），同一人不能导入两次")

    same_no = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no)).first()

    # 身份证撞到别的学号 → 同一人两个学号，必须人工核验
    if id_hash:
        other = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.id_card_hash == id_hash,
            StudentProfile.student_no != no)).first()
        if other is not None:
            return StudentResolution(
                action=ACTION_CONFLICT, student_no=no, student_id=other.id,
                reason_code=CONFLICT_IDENTITY,
                message=(f"该身份证已登记在学号 {other.student_no} 名下，"
                         f"与本次学号 {no} 不一致，请走身份核验确认是否同一人"))

    if same_no is None:
        return StudentResolution(action=ACTION_CREATE, student_no=no)

    # 学号属于已作废档案：不允许批量导入顺手复活
    if same_no.is_deleted:
        return StudentResolution(
            action=ACTION_CONFLICT, student_no=no, student_id=same_no.id,
            reason_code=CONFLICT_VOIDED,
            message=(f"学号 {no} 属于已作废档案（学号租户内永久唯一，不可另建新档）；"
                     "如确需恢复该生学籍，请走主档恢复流程，不要用批量导入"))

    # 姓名不一致 → 疑似不同人共用学号
    if name and (same_no.real_name or "").strip() and name != (same_no.real_name or "").strip():
        return StudentResolution(
            action=ACTION_CONFLICT, student_no=no, student_id=same_no.id,
            reason_code=CONFLICT_IDENTITY,
            message=(f"学号 {no} 在库中的姓名为「{same_no.real_name}」，与本次「{name}」不一致，"
                     "请走身份核验；确需改名请用「学籍信息更正」"))

    # 双方都有身份证时必须一致
    if id_hash and same_no.id_card_hash and id_hash != same_no.id_card_hash:
        return StudentResolution(
            action=ACTION_CONFLICT, student_no=no, student_id=same_no.id,
            reason_code=CONFLICT_IDENTITY,
            message=f"学号 {no} 的证件号与库中记录不一致，请走身份核验")

    # 组织：已有完整值与本次不同 → 阻断（改院系班必须走学籍异动）；已有为空 → 可补齐
    fillable: dict = {}
    org_fields = (("college_id", cmd.college_id, "学院"), ("major_id", cmd.major_id, "专业"),
                  ("class_id", cmd.class_id, "班级"))
    for col, incoming, label in org_fields:
        if not incoming:
            continue
        cur = getattr(same_no, col, None)
        if cur and int(cur) != int(incoming):
            return StudentResolution(
                action=ACTION_CONFLICT, student_no=no, student_id=same_no.id,
                reason_code=CONFLICT_ORG,
                message=(f"学号 {no} 已归属其它{label}，导入不得覆盖；"
                         "调整院系班请走「教务中心 › 学籍异动」"))
        if not cur:
            fillable[col] = int(incoming)

    # 非组织类的空字段也允许补齐（不覆盖已有值）
    for col, incoming in (("gender", cmd.gender), ("grade", cmd.grade)):
        if incoming and not getattr(same_no, col, None):
            fillable[col] = incoming
    if id_hash and not same_no.id_card_hash:
        fillable["id_card"] = cmd.id_card

    if fillable:
        return StudentResolution(action=ACTION_REUSE, student_id=same_no.id, student_no=no,
                                 fillable=fillable,
                                 message=f"复用已有主档并补齐 {len(fillable)} 项空缺信息")
    return StudentResolution(action=ACTION_SKIP, student_id=same_no.id, student_no=no,
                             message="主档已存在且信息一致，本次跳过")


def apply_resolution_in_session(db, *, tenant_id: int, cmd: StudentCreateCommand,
                                resolution: StudentResolution,
                                actor: dict | None = None) -> StudentCreateResult:
    """按判定结果落库：新建走统一建档；复用则只补空字段并留痕；跳过不写。"""
    from app.models import StudentProfile

    if resolution.action == ACTION_CREATE:
        return create_student_in_session(db, tenant_id=tenant_id, cmd=cmd, actor=actor)

    if resolution.action == ACTION_SKIP:
        return StudentCreateResult(student_id=int(resolution.student_id or 0),
                                   student_no=resolution.student_no, restored=False)

    if resolution.action != ACTION_REUSE:
        raise AppException(ERR_VALIDATION, resolution.message or "该行存在冲突，无法导入")

    s = db.scalars(select(StudentProfile).where(
        StudentProfile.id == int(resolution.student_id),
        StudentProfile.tenant_id == tenant_id)).first()
    if not s:
        raise not_found("学生主档不存在")

    # 组织补齐后仍要过一次完整性/父子校验，避免只补一半造出不自洽的组织
    merged = {
        "college_id": resolution.fillable.get("college_id", s.college_id),
        "major_id": resolution.fillable.get("major_id", s.major_id),
        "class_id": resolution.fillable.get("class_id", s.class_id),
    }
    org = validate_student_org_path(
        db, tenant_id=tenant_id, college_id=merged["college_id"], major_id=merged["major_id"],
        class_id=merged["class_id"], actor=actor,
        require_complete_org=bool(getattr(cmd, "require_complete_org", False)))

    before = {k: getattr(s, k, None) for k in ("college_id", "major_id", "class_id", "gender", "grade")}
    s.college_id, s.major_id, s.class_id = org.college_id, org.major_id, org.class_id
    for col in ("gender", "grade"):
        if col in resolution.fillable:
            setattr(s, col, resolution.fillable[col])
    if "id_card" in resolution.fillable and resolution.fillable["id_card"]:
        s.id_card_encrypted = encrypt_sensitive(resolution.fillable["id_card"], "id_card")
        s.id_card_hash = hash_sensitive(resolution.fillable["id_card"], "id_card")
    s.version = int(s.version or 0) + 1

    after = {k: getattr(s, k, None) for k in ("college_id", "major_id", "class_id", "gender", "grade")}
    changed = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
    if changed:
        # 补齐必须留痕：记录字段前后值与来源，便于事后追溯是哪次导入改的
        db.add(StudentStageEvent(
            tenant_id=tenant_id, student_id=s.id, from_stage=s.current_stage,
            to_stage=s.current_stage,
            reason=f"导入补齐主档空缺字段：{changed}",
            source_module=_source_of(cmd)))
    _sync_projections(db, s)
    return StudentCreateResult(student_id=s.id, student_no=s.student_no, restored=False)


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
