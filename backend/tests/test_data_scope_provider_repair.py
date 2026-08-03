"""SYS-05 体检查出的两个数据范围缺口的修复验证（真库）。

缺口本身：
- ``GD_STUDENTS`` 的 provider 读的三个字段在 GraduationStudent 上都不存在 → 恒为拒绝，
  毕设导师在数据范围模拟器里永远看不到自己带的学生；
- ``DORM_BUILDING`` 根本没有 provider → 落到"未知数据范围默认拒绝"，宿管同理。

两者都是 fail-closed，不存在越权，但"该看见的人看不见"同样是错的。修复只做一件事：
让模拟器复述业务域自己的判定规则。因此测试必须同时验证**放行**与**拒绝**两个方向。
"""
import pytest

from app.core.context import set_tenant
from app.services import data_scope_service as scope

MAIN_TENANT_ID = 1000000000000000001
OTHER_TENANT_ID = 8901


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, MAIN_TENANT_ID) is None:
            db.add(Tenant(id=MAIN_TENANT_ID, tenant_code="demo",
                          school_name="范围修复测试学校", status="ACTIVE"))
            db.commit()
    set_tenant({"tenantId": str(MAIN_TENANT_ID)})
    try:
        yield MAIN_TENANT_ID
    finally:
        set_tenant(None)


def _make_user(login_name: str, *, tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.core.security import hash_password
    from app.models import User

    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name="范围测试教师",
                   password_hash=hash_password("Init123456"), user_type="TEACHER",
                   status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_mentor(teacher_no: str, *, tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.models import GraduationMentor

    with _session() as db:
        row = GraduationMentor(tenant_id=tenant_id, teacher_no=teacher_no,
                               teacher_name="毕设导师", qualification_status="QUALIFIED")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_gd_student(mentor_id: int | None, *, name: str,
                     tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.models import GraduationStudent

    with _session() as db:
        row = GraduationStudent(tenant_id=tenant_id, name=name, mentor_id=mentor_id,
                                stage="TOPIC_SELECTING", record_status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _mentor_user(login_name: str):
    return {"userId": "db-999", "loginName": login_name, "tenantId": str(MAIN_TENANT_ID),
            "currentRoleCode": "GD_MENTOR", "dataScope": "GD_STUDENTS"}


# ── 毕设导师范围 ─────────────────────────────────────────────────────────────
def test_gd_mentor_sees_own_students(tenant_ctx):
    mentor_id = _make_mentor("gd_mentor_01")
    mine = _make_gd_student(mentor_id, name="我带的学生")

    result = scope.simulate_access(_mentor_user("gd_mentor_01"),
                                   resource_type="STUDENT", resource={"studentId": str(mine)})
    assert result["allowed"] is True, result
    assert result["scope"] == "GD_STUDENTS"


def test_gd_mentor_cannot_see_other_mentors_students(tenant_ctx):
    mine_mentor = _make_mentor("gd_mentor_02")
    other_mentor = _make_mentor("gd_mentor_03")
    _make_gd_student(mine_mentor, name="我带的学生")
    theirs = _make_gd_student(other_mentor, name="别人带的学生")
    orphan = _make_gd_student(None, name="没有导师的学生")

    user = _mentor_user("gd_mentor_02")
    assert scope.simulate_access(user, resource_type="STUDENT",
                                 resource={"studentId": str(theirs)})["allowed"] is False
    assert scope.simulate_access(user, resource_type="STUDENT",
                                 resource={"studentId": str(orphan)})["allowed"] is False


def test_gd_scope_is_tenant_isolated(tenant_ctx):
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, OTHER_TENANT_ID) is None:
            db.add(Tenant(id=OTHER_TENANT_ID, tenant_code="scope-other",
                          school_name="他校", status="ACTIVE"))
            db.commit()
    # 他校有一个同工号导师带着他校学生
    foreign_mentor = _make_mentor("gd_mentor_04", tenant_id=OTHER_TENANT_ID)
    foreign_student = _make_gd_student(foreign_mentor, name="他校学生",
                                       tenant_id=OTHER_TENANT_ID)

    user = _mentor_user("gd_mentor_04")  # 本校上下文
    assert scope.simulate_access(user, resource_type="STUDENT",
                                 resource={"studentId": str(foreign_student)})["allowed"] is False


def test_non_mentor_login_gets_nothing(tenant_ctx):
    mentor_id = _make_mentor("gd_mentor_05")
    student = _make_gd_student(mentor_id, name="学生")
    stranger = _mentor_user("not_a_mentor_login")
    assert scope.simulate_access(stranger, resource_type="STUDENT",
                                 resource={"studentId": str(student)})["allowed"] is False


def test_gd_scope_survives_beyond_500_rows(tenant_ctx):
    """改造前只扫前 500 行，学生一多就随机漏判。这里把目标放在第 600 名之后。"""
    from app.models import GraduationStudent

    mentor_id = _make_mentor("gd_mentor_06")
    with _session() as db:
        db.add_all([GraduationStudent(tenant_id=MAIN_TENANT_ID, name=f"填充{i}",
                                      mentor_id=None, stage="TOPIC_SELECTING",
                                      record_status="ACTIVE") for i in range(600)])
        db.commit()
    target = _make_gd_student(mentor_id, name="第601个才是我的")

    assert scope.simulate_access(_mentor_user("gd_mentor_06"), resource_type="STUDENT",
                                 resource={"studentId": str(target)})["allowed"] is True


# ── 宿管楼栋范围 ─────────────────────────────────────────────────────────────
def _make_building(manager_key: str | None, *, name: str) -> int:
    from app.models import DormBuilding

    with _session() as db:
        row = DormBuilding(tenant_id=MAIN_TENANT_ID, building_name=name,
                           manager_teacher_key=manager_key, status="ENABLED")
        db.add(row)
        db.commit()
        return int(row.id)


def _dorm_user(user_id: int, login_name: str):
    return {"userId": f"db-{user_id}", "loginName": login_name,
            "tenantId": str(MAIN_TENANT_ID), "currentRoleCode": "DORM_MANAGER",
            "dataScope": "DORM_BUILDING"}


def test_dorm_manager_sees_own_building_only(tenant_ctx):
    uid = _make_user("dorm_keeper_01")
    mine = _make_building("dorm_keeper_01", name="1号楼")
    theirs = _make_building("dorm_keeper_02", name="2号楼")
    unassigned = _make_building(None, name="3号楼")

    user = _dorm_user(uid, "dorm_keeper_01")
    assert scope.simulate_access(user, resource_type="DORM",
                                 resource={"buildingId": str(mine)})["allowed"] is True
    assert scope.simulate_access(user, resource_type="DORM",
                                 resource={"buildingId": str(theirs)})["allowed"] is False
    assert scope.simulate_access(user, resource_type="DORM",
                                 resource={"buildingId": str(unassigned)})["allowed"] is False


def test_dorm_scope_is_no_longer_unknown(tenant_ctx):
    """回归锁：DORM_BUILDING 不能再落到"未知数据范围默认拒绝"。"""
    uid = _make_user("dorm_keeper_03")
    mine = _make_building("dorm_keeper_03", name="4号楼")
    result = scope.simulate_access(_dorm_user(uid, "dorm_keeper_03"),
                                   resource_type="DORM", resource={"buildingId": str(mine)})
    assert "未知数据范围" not in result["reason"], result
    assert result["scope"] == "DORM_BUILDING"


def test_dorm_without_building_id_is_denied(tenant_ctx):
    uid = _make_user("dorm_keeper_04")
    _make_building("dorm_keeper_04", name="5号楼")
    assert scope.simulate_access(_dorm_user(uid, "dorm_keeper_04"),
                                 resource_type="DORM", resource={})["allowed"] is False
