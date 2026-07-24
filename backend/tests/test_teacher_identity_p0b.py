"""P0-B 教师身份归属回归：毕设/实习域「同名教师互相越权」封堵。

背景：毕设域对 GD_MENTOR/GD_REVIEWER/答辩秘书/答辩专家 全部用姓名字符串判定归属
（advisor_name / reviewer_name / group.secretary / members_json）；实习域教师范围把本人
realName 直接加入 advisorNames。学校里姓名会重复（开发库已存在同名账号），两名同名教师
会互相访问对方学生。

本用例锁住的性质：
  1. 租户内存在同名账号时，姓名不再作为归属依据（fail-closed），双方都访问不到；
  2. 工号（t_gd_mentor.teacher_no ↔ t_user.login_name，两侧租户内唯一）匹配仍可正常访问；
  3. 姓名唯一时兜底仍然可用（不误伤未绑工号的存量指导关系）；
  4. 实习教师范围不再把重名的 realName 放进 advisorNames。
"""
from __future__ import annotations

MAIN = 1000000000000000001


def _ctx_user(user_id, real_name, login_name, role):
    return {"userId": f"u_{user_id}", "realName": real_name, "loginName": login_name,
            "userType": "TEACHER", "tenantId": str(MAIN), "tid": "demo",
            "currentRoleCode": role, "activeContextId": "ctx"}


def _seed(_db_mode):
    """两个同名「张伟」账号 + 一个唯一名「李独一」账号；
    三名毕设学生：同名导师带的、唯一名导师带的、按工号挂导师台账的。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationMentor, GraduationStudent, User
    db = get_sessionmaker()()
    try:
        dup1 = User(tenant_id=MAIN, login_name="T9101", real_name="张伟",
                    password_hash="x", user_type="TEACHER", status="ACTIVE")
        dup2 = User(tenant_id=MAIN, login_name="T9102", real_name="张伟",
                    password_hash="x", user_type="TEACHER", status="ACTIVE")
        uniq = User(tenant_id=MAIN, login_name="T9103", real_name="李独一",
                    password_hash="x", user_type="TEACHER", status="ACTIVE")
        db.add_all([dup1, dup2, uniq])
        db.flush()

        mentor = GraduationMentor(tenant_id=MAIN, teacher_no="T9101", teacher_name="张伟",
                                  mentor_type="INTERNAL", qualification_status="APPROVED")
        db.add(mentor)
        db.flush()

        s_dup = GraduationStudent(tenant_id=MAIN, name="学生甲", student_no="P0B001",
                                  advisor_name="张伟")
        s_uniq = GraduationStudent(tenant_id=MAIN, name="学生乙", student_no="P0B002",
                                   advisor_name="李独一")
        s_no = GraduationStudent(tenant_id=MAIN, name="学生丙", student_no="P0B003",
                                 advisor_name="张伟", mentor_id=mentor.id)
        db.add_all([s_dup, s_uniq, s_no])
        db.commit()
        return {"dup": s_dup.id, "uniq": s_uniq.id, "byNo": s_no.id,
                "u_dup1": dup1.id, "u_dup2": dup2.id, "u_uniq": uniq.id}
    finally:
        db.close()


def _can_access(user_ctx, student_id):
    from app.core.context import set_current_user
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    from app.modules.graduation.services import graduation_scope_service as scope
    set_current_user(user_ctx)
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, student_id)
        return scope.can_access_student(db, stu)
    finally:
        db.close()
        set_current_user(None)


def test_duplicate_name_mentors_cannot_cross_access(db_mode):
    """两名同名「张伟」都不能靠姓名访问 advisor_name='张伟' 的学生（fail-closed）。"""
    ids = _seed(db_mode)
    a = _ctx_user(ids["u_dup1"], "张伟", "T9101", "GD_MENTOR")
    b = _ctx_user(ids["u_dup2"], "张伟", "T9102", "GD_MENTOR")
    assert _can_access(a, ids["dup"]) is False, "同名教师不应凭姓名访问"
    assert _can_access(b, ids["dup"]) is False, "同名教师不应凭姓名访问"


def test_teacher_no_match_still_grants_access(db_mode):
    """工号精确匹配（t_gd_mentor.teacher_no == login_name）仍可访问，即使姓名重复。"""
    ids = _seed(db_mode)
    owner = _ctx_user(ids["u_dup1"], "张伟", "T9101", "GD_MENTOR")
    other = _ctx_user(ids["u_dup2"], "张伟", "T9102", "GD_MENTOR")
    assert _can_access(owner, ids["byNo"]) is True, "工号匹配的导师应可访问本人学生"
    assert _can_access(other, ids["byNo"]) is False, "非本人工号不应访问"


def test_unique_name_fallback_still_works(db_mode):
    """姓名在租户内唯一时，姓名兜底仍可用——不误伤未绑工号的存量指导关系。"""
    ids = _seed(db_mode)
    u = _ctx_user(ids["u_uniq"], "李独一", "T9103", "GD_MENTOR")
    assert _can_access(u, ids["uniq"]) is True, "唯一姓名的存量指导关系应保持可访问"


def test_internship_scope_excludes_ambiguous_name(db_mode):
    """实习教师范围：重名的 realName 不得进入 advisorNames（否则同名导师互看带教学生）。"""
    from app.core.context import set_current_user, set_tenant
    from app.services.mobile_teacher_service import resolve_teacher_scope
    ids = _seed(db_mode)
    set_tenant({"tenantId": str(MAIN)})
    try:
        dup = _ctx_user(ids["u_dup1"], "张伟", "T9101", "INTERN_MENTOR")
        set_current_user(dup)
        assert "张伟" not in resolve_teacher_scope(dup)["advisorNames"], "重名不应进入导师姓名范围"

        uniq = _ctx_user(ids["u_uniq"], "李独一", "T9103", "INTERN_MENTOR")
        set_current_user(uniq)
        assert "李独一" in resolve_teacher_scope(uniq)["advisorNames"], "唯一姓名应保持兼容"
    finally:
        set_current_user(None)
        set_tenant(None)
