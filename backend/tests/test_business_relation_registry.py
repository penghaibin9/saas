"""SYS-05 业务关系中心（真库）。

对应必测 SYS05-T01～T03：
每种关系有 owner/resolver/test / 缺失统计与业务权威表一致 / 关系过期后访问范围失效。
"""
import pytest

from app.core.exceptions import AppException
from app.services import business_relation_registry as registry

MAIN_TENANT_ID = 1000000000000000001


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _make_class(counselor_id=None, head_teacher_id=None, status="ACTIVE",
                tenant_id: int = MAIN_TENANT_ID) -> int:
    from uuid import uuid4

    from app.models.org import College, Major, SchoolClass

    with _session() as db:
        col = College(tenant_id=tenant_id, college_name=f"学院-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(col)
        db.flush()
        maj = Major(tenant_id=tenant_id, college_id=col.id, major_name=f"专业-{uuid4().hex[:6]}",
                    status="ACTIVE")
        db.add(maj)
        db.flush()
        cls = SchoolClass(tenant_id=tenant_id, major_id=maj.id,
                          class_name=f"班级-{uuid4().hex[:6]}", grade="2026",
                          status=status, class_status="NORMAL",
                          counselor_id=counselor_id, head_teacher_id=head_teacher_id)
        db.add(cls)
        db.commit()
        return int(cls.id)


def _make_teacher(login_name: str, *, status: str = "ACTIVE",
                  tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.core.security import hash_password
    from app.models import Tenant, User

    with _session() as db:
        if db.get(Tenant, int(tenant_id)) is None:
            code = "demo" if int(tenant_id) == MAIN_TENANT_ID else f"rel-{tenant_id}"
            db.add(Tenant(id=int(tenant_id), tenant_code=code, school_name="关系测试学校",
                          status="ACTIVE"))
            db.flush()
        row = User(tenant_id=tenant_id, login_name=login_name, real_name="关系测试教师",
                   password_hash=hash_password("Init123456"), user_type="TEACHER", status=status)
        db.add(row)
        db.commit()
        return int(row.id)


# ── SYS05-T01：每种关系都要有 owner / resolver / test，且登记必须与真实代码对得上 ──
def test_t01_every_relation_declares_owner_resolver_and_test(db_mode):
    rows = registry.validate_registry()
    assert len(rows) >= 5, "至少覆盖辅导员班级/导师学生/实习指导/任课教学班/宿管楼栋"
    for row in rows:
        assert row["ownerModule"], f"{row['relationType']} 缺 ownerModule"
        assert row["sourceModel"], f"{row['relationType']} 缺 sourceModel"
        assert row["test"], f"{row['relationType']} 缺 test"
        codes = {c["code"] for c in row["checks"]}
        # 登记的模型/字段/测试必须真实存在——这三类是硬错误
        assert registry.CHECK_MODEL_MISSING not in codes, row
        assert registry.CHECK_FIELD_MISSING not in codes, row
        assert registry.CHECK_TEST_MISSING not in codes, row


def test_t01b_registry_surfaces_known_broken_resolvers(db_mode):
    """登记不是走过场：它必须能自己指出哪几条关系当前是坏的。

    这两条是本卡体检出来的真实缺口，都不在 SYS-05 的施工白名单内，故只登记不改：
    - GD_STUDENTS 的 resolver 读的 mentor_user_id/mentor_no/teacher_no 在
      GraduationStudent 上全都不存在 → 该数据范围恒为拒绝；
    - DORM_BUILDING 既没有 resolver，关系键还是文本。
    """
    rows = {r["relationType"]: r for r in registry.validate_registry()}

    gd_codes = {c["code"] for c in rows["GD_MENTOR_STUDENT"]["checks"]}
    assert registry.CHECK_RESOLVER_FIELD_MISSING in gd_codes

    from app.models.graduation import GraduationStudent

    for field in ("mentor_user_id", "mentor_no", "teacher_no"):
        assert not hasattr(GraduationStudent, field), f"{field} 已补上，请同步更新注册表与本断言"

    dorm_codes = {c["code"] for c in rows["DORM_MANAGER_BUILDING"]["checks"]}
    assert registry.CHECK_RESOLVER_MISSING in dorm_codes
    assert registry.CHECK_UNSTABLE_KEY in dorm_codes


def test_t01c_no_relation_data_is_copied(db_mode):
    """系统管理不得为业务关系建通用副本表：注册表只声明业务表位置。"""
    from app.db.base import metadata

    assert "t_business_relation" not in metadata.tables
    assert "t_business_relation_item" not in metadata.tables
    for item in registry.load_registry():
        assert item["sourceModel"].startswith("app.models."), item


# ── SYS05-T02：缺失统计必须与业务权威表一致 ─────────────────────────────────
def test_t02_missing_count_matches_authority_table(db_mode):
    from sqlalchemy import func, select

    from app.models.org import SchoolClass

    teacher_id = _make_teacher("rel_counselor_01")
    _make_class(counselor_id=teacher_id)
    _make_class(counselor_id=None)
    _make_class(counselor_id=None)

    report = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=MAIN_TENANT_ID)

    with _session() as db:
        authoritative_missing = int(db.scalar(
            select(func.count()).select_from(SchoolClass).where(
                SchoolClass.tenant_id == MAIN_TENANT_ID,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.status == "ACTIVE",
                SchoolClass.counselor_id.is_(None))) or 0)

    assert report["counts"][registry.ISSUE_MISSING_SUBJECT] == authoritative_missing
    assert authoritative_missing >= 2


def test_t02b_dangling_subject_detected(db_mode):
    disabled = _make_teacher("rel_counselor_off", status="DISABLED")
    _make_class(counselor_id=disabled)
    report = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=MAIN_TENANT_ID)
    assert report["counts"][registry.ISSUE_DANGLING_SUBJECT] >= 1


def test_t02c_inactive_object_is_not_counted_as_missing(db_mode):
    _make_class(counselor_id=None, status="ARCHIVED")
    report = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=MAIN_TENANT_ID)
    assert report["counts"][registry.ISSUE_INACTIVE_OBJECT] >= 1
    assert report["counts"][registry.ISSUE_MISSING_SUBJECT] == 0


def test_t02d_tenant_isolation(db_mode):
    other = 8805
    teacher_id = _make_teacher("rel_other_counselor", tenant_id=other)
    _make_class(counselor_id=teacher_id, tenant_id=other)
    _make_class(counselor_id=None, tenant_id=other)

    mine = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=MAIN_TENANT_ID)
    theirs = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=other)
    assert mine["total"] == 0
    assert theirs["total"] == 2


# ── SYS05-T03：关系解除后访问范围立即失效 ───────────────────────────────────
def test_t03_scope_dies_when_relation_is_removed(db_mode):
    from app.core.context import set_tenant
    from app.services import data_scope_service as scope

    teacher_id = _make_teacher("rel_scope_counselor")
    class_id = _make_class(counselor_id=teacher_id)
    user = {"userId": f"db-{teacher_id}", "loginName": "rel_scope_counselor",
            "tenantId": str(MAIN_TENANT_ID), "currentRoleCode": "COUNSELOR",
            "dataScope": "COUNSELOR_CLASSES"}

    set_tenant({"tenantId": str(MAIN_TENANT_ID)})
    try:
        allowed = scope.simulate_access(user, resource_type="STUDENT",
                                        resource={"classId": str(class_id)})
        assert allowed["allowed"] is True, allowed

        # 解除关系（换人）——不改任何权限配置，只动业务表
        from app.models.org import SchoolClass

        with _session() as db:
            db.get(SchoolClass, class_id).counselor_id = None
            db.commit()

        after = scope.simulate_access(user, resource_type="STUDENT",
                                      resource={"classId": str(class_id)})
        assert after["allowed"] is False, "关系解除后必须立刻失去范围"

        report = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=MAIN_TENANT_ID)
        assert report["counts"][registry.ISSUE_MISSING_SUBJECT] >= 1
    finally:
        set_tenant(None)


# ── 接口层 ───────────────────────────────────────────────────────────────────
def test_http_endpoints(client, auth_headers, db_mode):
    types = client.get("/api/v1/system/business-relations/types", headers=auth_headers).json()
    assert types["code"] == 0
    assert types["data"]["total"] >= 5
    row = next(r for r in types["data"]["list"] if r["relationType"] == "COUNSELOR_CLASS")
    assert row["ownerModule"] == "studentAffairs"

    issues = client.get("/api/v1/system/business-relations/issues", headers=auth_headers).json()
    assert issues["code"] == 0
    assert {r["relationType"] for r in issues["data"]["list"]} >= {"COUNSELOR_CLASS"}

    checked = client.post("/api/v1/system/business-relations/COUNSELOR_CLASS/validate",
                          headers=auth_headers).json()
    assert checked["code"] == 0
    assert checked["data"]["registry"]["relationType"] == "COUNSELOR_CLASS"

    unknown = client.post("/api/v1/system/business-relations/NOT_A_TYPE/validate",
                          headers=auth_headers)
    assert unknown.status_code == 400


def test_unknown_relation_type_rejected(db_mode):
    with pytest.raises(AppException):
        registry.inspect_relation("NOT_A_TYPE", tenant_id=MAIN_TENANT_ID)
