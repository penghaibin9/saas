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


def _ctx() -> tuple[str, str]:
    user = get_current_user_ctx() or {}
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    real_name = (user.get("realName") or "").strip()
    return role, real_name


def _has_review_relation(db, student: GraduationStudent, real_name: str) -> bool:
    return db.scalar(select(GraduationReview.id).where(
        GraduationReview.tenant_id == student.tenant_id,
        GraduationReview.gd_student_id == student.id,
        GraduationReview.reviewer_name == real_name,
        GraduationReview.is_deleted.is_(False),
    ).limit(1)) is not None


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

    if role == "GD_MENTOR":
        if (student.advisor_name or "").strip() == real_name:
            return True
        # 教师移动端单令牌承载多重业务身份：被指派为评阅人时，凭真实评阅指派关系访问
        return _has_review_relation(db, student, real_name)

    if role == "GD_REVIEWER":
        return _has_review_relation(db, student, real_name)

    if role in {"GD_DEFENSE_SECRETARY", "GD_DEFENSE_EXPERT"}:
        if not student.defense_group_id:
            return False
        group = db.get(GraduationDefenseGroup, student.defense_group_id)
        if not group or group.is_deleted or group.tenant_id != student.tenant_id:
            return False
        if role == "GD_DEFENSE_SECRETARY":
            return (group.secretary or "").strip() == real_name
        panel = {(group.chair or "").strip(), *((x or "").strip() for x in (group.members_json or []))}
        return real_name in panel

    # 学院/专业负责人需要可验证的 collegeId/majorId 上下文；当前缺失时 fail-closed。
    return False


def assert_student_access(db, student: GraduationStudent | None, action: str = "view") -> GraduationStudent:
    if not can_access_student(db, student):
        raise no_permission(f"不在当前毕业设计数据范围内（{action}）")
    return student


def accessible_student_ids(db, tenant_id: int) -> list[int]:
    """返回当前毕设角色在租户内可访问的学生 ID。

    统计、列表、导出必须复用本口径，不允许各自用角色名猜范围。
    """
    students = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )).all()
    return [int(student.id) for student in students if can_access_student(db, student)]
