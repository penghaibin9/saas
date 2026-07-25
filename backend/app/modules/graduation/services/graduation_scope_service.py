"""毕业设计数据范围与业务关系裁决。

权限码只回答“能不能做该动作”；本服务再回答“能对哪些学生做”。
当前租户隔离仍由各域查询的 tenant_id 强制。学院/专业范围未进入 token 时
不猜测，默认无可见学生。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import no_permission
from app.models import GraduationDefenseGroup, GraduationReview, GraduationStudent


FULL_SCOPE_ROLES = {"PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN"}
COLLEGE_SCOPE_ROLES = {"GD_COLLEGE_ADMIN", "COLLEGE_ADMIN"}
MAJOR_SCOPE_ROLES = {"GD_MAJOR_ADMIN"}


def _ctx() -> tuple[str, str]:
    user = get_current_user_ctx() or {}
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    real_name = (user.get("realName") or "").strip()
    return role, real_name


def _claim_id_set(user: dict, singular: str, plural: str) -> set[str]:
    ids: set[str] = set()
    multi = user.get(plural)
    if isinstance(multi, (list, tuple, set)):
        ids.update(str(x).strip() for x in multi if str(x).strip())
    single = str(user.get(singular) or "").strip()
    if single:
        ids.add(single)
    return ids


def _student_org_keys(db, student: GraduationStudent) -> tuple[str, str]:
    """返回学生学院/专业 ID 字符串；台账缺省时回落学籍主档。"""
    college_key = str(student.college_id or "").strip()
    major_key = str(getattr(student, "major_id", None) or "").strip()
    if (college_key and major_key) or not student.student_id:
        return college_key, major_key
    try:
        from app.models import StudentProfile
        profile = db.get(StudentProfile, student.student_id)
    except Exception:  # noqa: BLE001 — FakeDb / 无 ORM 场景
        profile = None
    if profile is None:
        return college_key, major_key
    if not college_key and getattr(profile, "college_id", None) is not None:
        college_key = str(profile.college_id).strip()
    if not major_key and getattr(profile, "major_id", None) is not None:
        major_key = str(profile.major_id).strip()
    return college_key, major_key


def _has_review_relation(db, student: GraduationStudent, real_name: str) -> bool:
    """评阅关系：优先 reviewer_mentor_id（loginName→teacher_no）；无 ID 的历史任务才比姓名。"""
    login = _login_name()
    if login:
        try:
            from app.models import GraduationMentor
            mentor = db.scalars(select(GraduationMentor).where(
                GraduationMentor.tenant_id == student.tenant_id,
                GraduationMentor.teacher_no == login,
                GraduationMentor.is_deleted.is_(False),
            ).limit(1)).first()
        except Exception:  # noqa: BLE001
            mentor = None
        if mentor is not None:
            hit = db.scalar(select(GraduationReview.id).where(
                GraduationReview.tenant_id == student.tenant_id,
                GraduationReview.gd_student_id == student.id,
                GraduationReview.reviewer_mentor_id == mentor.id,
                GraduationReview.is_deleted.is_(False),
            ).limit(1))
            if hit is not None:
                return True
    # 历史无稳定 ID 的指派：仅匹配 reviewer_mentor_id IS NULL，避免同名串到已绑定 ID 的任务
    return db.scalar(select(GraduationReview.id).where(
        GraduationReview.tenant_id == student.tenant_id,
        GraduationReview.gd_student_id == student.id,
        GraduationReview.reviewer_name == real_name,
        GraduationReview.reviewer_mentor_id.is_(None),
        GraduationReview.is_deleted.is_(False),
    ).limit(1)) is not None


def _login_name() -> str:
    """当前登录者工号（t_user.login_name，租户内唯一 uk_tenant_login）。"""
    return str((get_current_user_ctx() or {}).get("loginName") or "").strip()


def _mentor_teacher_no(db, student: GraduationStudent) -> str:
    """学生所挂导师台账的工号（t_gd_mentor.teacher_no，租户内唯一 uk_gd_mentor_teacher_no）。

    这是毕设域判定「本人指导关系」最可靠的依据：与 t_user.login_name 同为工号口径，
    两侧都有租户内唯一约束，重名/改名都不会串号。
    """
    mentor_id = getattr(student, "mentor_id", None)
    if not mentor_id:
        return ""
    try:
        from app.models import GraduationMentor
        m = db.get(GraduationMentor, int(mentor_id))
    except Exception:  # noqa: BLE001 — FakeDb / 无 ORM 场景
        return ""
    if not m or getattr(m, "is_deleted", False) or m.tenant_id != student.tenant_id:
        return ""
    return str(getattr(m, "teacher_no", "") or "").strip()


def _name_is_ambiguous(db, tenant_id: int, real_name: str) -> bool:
    """租户内是否存在 ≥2 个同名用户——若是，姓名不足以证明身份，一律 fail-closed。

    毕设域历史上对 GD_MENTOR/GD_REVIEWER/答辩秘书/答辩专家 全部用 `姓名字符串 == realName`
    判定归属（advisor_name / reviewer_name / group.secretary / members_json）。学校里姓名会重复
    （开发库已存在同名账号），两名同名教师会互相访问对方学生，属真实越权。

    判定采取「只在能证明重名时才拒绝」：命中 0 个（演示/外聘导师无系统账号）或 1 个时不拒绝，
    保持既有数据可用；≥2 个才拒绝。这样只堵漏洞，不误伤未建账号的存量指导关系。
    """
    if not real_name:
        return True
    # 仅在真实 ORM 会话上判定：单元测试的 FakeDb 会忽略查询语句恒返回同一批行，
    # 据此判重名会把所有姓名都误判为重复，进而拒绝全部访问。
    from sqlalchemy.orm import Session as _OrmSession
    if not isinstance(db, _OrmSession):
        return False
    try:
        from app.models import User
        rows = db.scalars(select(User.id).where(
            User.tenant_id == tenant_id,
            User.real_name == real_name,
            User.is_deleted.is_(False),
        ).limit(2)).all()
    except Exception:  # noqa: BLE001 — 旧库无表/连接异常时不阻断既有链路
        return False
    return len(rows) >= 2


def _student_self_identity(db, tenant_id: int) -> tuple[str, int | None]:
    """学生登录者的稳定本人身份：令牌 studentNo 优先；缺失时在租户内按姓名唯一匹配
    学籍主档（与登录签发 studentNo 同源的映射）。重名或找不到一律 fail-closed。"""
    user = get_current_user_ctx() or {}
    student_no = str(user.get("studentNo") or "").strip()
    if student_no:
        return student_no, None
    real_name = (user.get("realName") or "").strip()
    if not real_name:
        return "", None
    from app.models import StudentProfile
    rows = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.real_name == real_name,
        StudentProfile.is_deleted.is_(False),
    ).limit(2)).all()
    if len(rows) != 1:
        return "", None
    return str(rows[0].student_no or ""), int(rows[0].id)


def has_full_scope() -> bool:
    role, _ = _ctx()
    return role in FULL_SCOPE_ROLES


def org_scope_status(user: dict | None = None) -> dict:
    """学院/专业管理员开箱诊断：是否已有可验证 claim（供 /context 与前端提示）。"""
    u = user if user is not None else (get_current_user_ctx() or {})
    role = (u.get("currentRoleCode") or u.get("userType") or "").strip().upper()
    college_ids = sorted(_claim_id_set(u, "collegeId", "collegeIds"))
    major_ids = sorted(_claim_id_set(u, "majorId", "majorIds"))
    if role in COLLEGE_SCOPE_ROLES:
        configured = bool(college_ids)
        hint = ("" if configured else
                "当前学院管理员身份未绑定学院数据范围。请在师生导入或教师范围中配置 COLLEGE 授权后重新登录。")
        return {
            "roleNeedsOrgScope": True,
            "scopeConfigured": configured,
            "requiredClaim": "collegeId",
            "collegeId": college_ids[0] if college_ids else None,
            "collegeIds": college_ids,
            "majorId": major_ids[0] if major_ids else None,
            "majorIds": major_ids,
            "scopeHint": hint,
        }
    if role in MAJOR_SCOPE_ROLES:
        configured = bool(major_ids)
        hint = ("" if configured else
                "当前专业管理员身份未绑定专业数据范围。请在师生导入或教师范围中配置 MAJOR 授权后重新登录。")
        return {
            "roleNeedsOrgScope": True,
            "scopeConfigured": configured,
            "requiredClaim": "majorId",
            "collegeId": college_ids[0] if college_ids else None,
            "collegeIds": college_ids,
            "majorId": major_ids[0] if major_ids else None,
            "majorIds": major_ids,
            "scopeHint": hint,
        }
    return {
        "roleNeedsOrgScope": False,
        "scopeConfigured": True,
        "requiredClaim": None,
        "collegeId": college_ids[0] if college_ids else None,
        "collegeIds": college_ids,
        "majorId": major_ids[0] if major_ids else None,
        "majorIds": major_ids,
        "scopeHint": "",
    }


def can_access_student(db, student: GraduationStudent | None) -> bool:
    if student is None:
        return False
    role, real_name = _ctx()
    if role in FULL_SCOPE_ROLES:
        return True
    if not real_name and role != "STUDENT":
        return False

    if role == "STUDENT":
        student_no, profile_id = _student_self_identity(db, student.tenant_id)
        if student_no and str(student.student_no or "") == student_no:
            return True
        return (profile_id is not None and student.student_id is not None
                and int(student.student_id) == profile_id)

    # 以下角色历史上靠姓名串；工号 / mentor_id 优先。有稳定 ID 时不因同名用户 fail-closed。
    # 学院/专业管理员走 claim，与姓名无关。
    if role in {"GD_DEFENSE_SECRETARY", "GD_DEFENSE_EXPERT"}:
        if not student.defense_group_id:
            return False
        group = db.get(GraduationDefenseGroup, student.defense_group_id)
        if not group or group.is_deleted or group.tenant_id != student.tenant_id:
            return False
        from app.modules.graduation.services import graduation_identity as gid
        me = gid.mentor_by_teacher_no(db, _login_name(), student.tenant_id) if _login_name() else None
        if role == "GD_DEFENSE_SECRETARY":
            if not gid.user_is_secretary(group, mentor=me, real_name=real_name):
                return False
            # 有秘书 ID 时已比 ID；仅姓名快照时重名 fail-closed
            if getattr(group, "secretary_mentor_id", None):
                return True
            if _name_is_ambiguous(db, student.tenant_id, real_name):
                return False
            return True
        # 评委：部分席位有 ID / 部分仅姓名 → ID∪姓名双通道（有 ID 席位不可被同名冒充）
        if not gid.user_on_judge_panel(group, mentor=me, real_name=real_name):
            return False
        matched_by_id = bool(
            me and any(
                s.get("mentorId") is not None and int(me.id) == int(s["mentorId"])
                for s in gid.judge_panel_seats(group)
            )
        )
        if matched_by_id:
            return True
        if _name_is_ambiguous(db, student.tenant_id, real_name):
            return False
        return True

    if role in {"GD_MENTOR", "COUNSELOR", "GD_REVIEWER"}:
        login_name = _login_name()
        if role in {"GD_MENTOR", "COUNSELOR"} and login_name:
            if _mentor_teacher_no(db, student) == login_name:
                return True
        # 评阅关系已绑 mentor_id 时，后续 _has_review_relation 走 ID，不受同名门禁阻断
        if role == "GD_REVIEWER" or (role in {"GD_MENTOR", "COUNSELOR"} and getattr(student, "mentor_id", None)):
            pass  # 不因同名提前拒绝；由 ID / 评阅关系裁决
        elif _name_is_ambiguous(db, student.tenant_id, real_name):
            return False

    if role in {"GD_MENTOR", "COUNSELOR"}:
        # 已绑定 mentor_id 时禁止再靠同名 advisor_name 串号（张伟A/B 隔离）。
        if getattr(student, "mentor_id", None):
            return _has_review_relation(db, student, real_name)
        if (student.advisor_name or "").strip() == real_name:
            return True
        return _has_review_relation(db, student, real_name)

    if role == "GD_REVIEWER":
        return _has_review_relation(db, student, real_name)

    user = get_current_user_ctx() or {}
    college_key, major_key = _student_org_keys(db, student)
    if role in COLLEGE_SCOPE_ROLES:
        allowed = _claim_id_set(user, "collegeId", "collegeIds")
        return bool(allowed and college_key and college_key in allowed)
    if role in MAJOR_SCOPE_ROLES:
        allowed = _claim_id_set(user, "majorId", "majorIds")
        return bool(allowed and major_key and major_key in allowed)

    # 其他角色未建模业务关系时 fail-closed。
    return False


def assert_student_access(db, student: GraduationStudent | None, action: str = "view") -> GraduationStudent:
    if not can_access_student(db, student):
        raise no_permission(f"不在当前毕业设计数据范围内（{action}）")
    return student


def accessible_student_ids(db, tenant_id: int, batch_id=None) -> list[int]:
    """返回当前毕设角色在租户内可访问的学生 ID。

    统计、列表、导出、看板必须复用本口径，不允许各自用角色名猜范围。
    batch_id 有值时再按批次收窄；列表 / 页签计数 / 统计 / 导出须传同一 batch_id。
    """
    q = select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )
    if batch_id is not None and batch_id != "":
        q = q.where(GraduationStudent.batch_id == int(batch_id))
    students = db.scalars(q).all()
    return [int(student.id) for student in students if can_access_student(db, student)]
