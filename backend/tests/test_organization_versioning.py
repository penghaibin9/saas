"""SYS-04 组织变更版本与任职有效期（真库）。

对应必测 SYS04-T01～T04：
未来版本生效前不影响当前 / 移动节点展示影响 / 任职到期自动失效 / 跨租户节点不可引用。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import organization_version_service as svc

TENANT = 8801
OTHER_TENANT = 8802


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _mk_college(tenant_id: int, name: str) -> int:
    from app.models import College

    with _session() as db:
        row = College(tenant_id=tenant_id, college_name=name, status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _mk_major(tenant_id: int, college_id: int, name: str) -> int:
    from app.models import Major

    with _session() as db:
        row = Major(tenant_id=tenant_id, college_id=college_id, major_name=name, status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _mk_class(tenant_id: int, major_id: int, name: str, **kw) -> int:
    from app.models import SchoolClass

    with _session() as db:
        row = SchoolClass(tenant_id=tenant_id, major_id=major_id, class_name=name, status="ACTIVE", **kw)
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _mk_student(tenant_id: int, class_id: int, no: str) -> None:
    from app.models import StudentProfile

    with _session() as db:
        db.add(StudentProfile(tenant_id=tenant_id, student_no=no, real_name=f"学生{no}", class_id=class_id))
        db.commit()


def _college_name(tenant_id: int, college_id: int) -> str:
    from app.models import College

    with _session() as db:
        return db.get(College, college_id).college_name


def _major_parent(tenant_id: int, major_id: int) -> int:
    from app.models import Major

    with _session() as db:
        return int(db.get(Major, major_id).college_id)


def _advance(version_id: int, target: str, *, effective_at=None, reason: str = "测试") -> dict:
    current = svc.get_version(version_id, tenant_id=TENANT)
    return svc.transition_version(
        version_id, target, reason=reason, expected_version=int(current["version"]),
        effective_at=effective_at, tenant_id=TENANT,
    )


# ── SYS04-T01：未来版本生效前不影响当前 ─────────────────────────────────────
def test_t01_scheduled_version_does_not_touch_current_org(db_mode):
    college = _mk_college(TENANT, "信息工程学院")
    version = svc.create_version(version_name="学院更名", reason="行政调整", tenant_id=TENANT)
    vid = int(version["versionId"])

    svc.add_change(
        vid, change_type="RENAME", org_type="COLLEGE", org_node_id=college,
        payload={"name": "人工智能学院"}, tenant_id=TENANT,
    )
    _advance(vid, "VALIDATED")
    _advance(vid, "SCHEDULED", effective_at=datetime.utcnow() + timedelta(days=7))

    # 排期后当前组织必须原封不动
    assert _college_name(TENANT, college) == "信息工程学院"

    _advance(vid, "ACTIVATED")
    assert _college_name(TENANT, college) == "人工智能学院"


def test_t01_rollback_restores_previous_values(db_mode):
    college = _mk_college(TENANT, "机电学院")
    vid = int(svc.create_version(version_name="改名", reason="r", tenant_id=TENANT)["versionId"])
    svc.add_change(
        vid, change_type="RENAME", org_type="COLLEGE", org_node_id=college,
        payload={"name": "智能制造学院"}, tenant_id=TENANT,
    )
    _advance(vid, "VALIDATED")
    _advance(vid, "ACTIVATED")
    assert _college_name(TENANT, college) == "智能制造学院"

    _advance(vid, "ROLLED_BACK", reason="决策撤回")
    assert _college_name(TENANT, college) == "机电学院"


def test_t01_move_applies_only_on_activation(db_mode):
    c1 = _mk_college(TENANT, "甲学院")
    c2 = _mk_college(TENANT, "乙学院")
    major = _mk_major(TENANT, c1, "软件技术")

    vid = int(svc.create_version(version_name="专业调整", reason="r", tenant_id=TENANT)["versionId"])
    svc.add_change(
        vid, change_type="MOVE", org_type="MAJOR", org_node_id=major,
        payload={"parentId": c2}, tenant_id=TENANT,
    )
    _advance(vid, "VALIDATED")
    assert _major_parent(TENANT, major) == c1  # 校验完成也不该动

    _advance(vid, "ACTIVATED")
    assert _major_parent(TENANT, major) == c2


def test_t01_scheduled_activation_is_idempotent(db_mode):
    college = _mk_college(TENANT, "待改名学院")
    vid = int(svc.create_version(version_name="定时改名", reason="r", tenant_id=TENANT)["versionId"])
    svc.add_change(
        vid, change_type="RENAME", org_type="COLLEGE", org_node_id=college,
        payload={"name": "已改名学院"}, tenant_id=TENANT,
    )
    _advance(vid, "VALIDATED")
    _advance(vid, "SCHEDULED", effective_at=datetime.utcnow() + timedelta(hours=1))

    early = svc.activate_due_versions(now=datetime.utcnow())
    assert not any(i["versionId"] == str(vid) for i in early["activated"])
    assert _college_name(TENANT, college) == "待改名学院"

    later = datetime.utcnow() + timedelta(hours=2)
    first = svc.activate_due_versions(now=later)
    assert any(i["versionId"] == str(vid) for i in first["activated"])
    second = svc.activate_due_versions(now=later)
    assert not any(i["versionId"] == str(vid) for i in second["activated"])
    assert _college_name(TENANT, college) == "已改名学院"


def test_t01_illegal_version_transition_rejected(db_mode):
    vid = int(svc.create_version(version_name="空版本", reason="r", tenant_id=TENANT)["versionId"])
    # 空版本不能校验通过
    with pytest.raises(AppException):
        _advance(vid, "VALIDATED")

    college = _mk_college(TENANT, "某学院")
    svc.add_change(
        vid, change_type="DISABLE", org_type="COLLEGE", org_node_id=college, payload={}, tenant_id=TENANT
    )
    # DRAFT 不能直接激活
    with pytest.raises(AppException) as exc:
        _advance(vid, "ACTIVATED")
    assert exc.value.code == "STATE_TRANSITION_DENIED"


def test_t01_locked_version_rejects_new_changes(db_mode):
    college = _mk_college(TENANT, "锁定测试学院")
    vid = int(svc.create_version(version_name="锁定", reason="r", tenant_id=TENANT)["versionId"])
    svc.add_change(
        vid, change_type="DISABLE", org_type="COLLEGE", org_node_id=college, payload={}, tenant_id=TENANT
    )
    _advance(vid, "VALIDATED")
    with pytest.raises(AppException) as exc:
        svc.add_change(
            vid, change_type="RENAME", org_type="COLLEGE", org_node_id=college,
            payload={"name": "x"}, tenant_id=TENANT,
        )
    assert exc.value.code == "ORG_VERSION_LOCKED"


# ── SYS04-T02：移动节点展示影响 ─────────────────────────────────────────────
def test_t02_impact_counts_downstream_majors_classes_students(db_mode):
    college = _mk_college(TENANT, "影响面学院")
    major = _mk_major(TENANT, college, "影响面专业")
    klass = _mk_class(TENANT, major, "影响面班级")
    _mk_student(TENANT, klass, "T02001")
    _mk_student(TENANT, klass, "T02002")

    impact = svc.compute_impact("COLLEGE", college, tenant_id=TENANT)
    assert impact["affectedMajors"] == 1
    assert impact["affectedClasses"] == 1
    assert impact["affectedStudents"] == 2

    major_impact = svc.compute_impact("MAJOR", major, tenant_id=TENANT)
    assert major_impact["affectedClasses"] == 1
    assert major_impact["affectedStudents"] == 2


def test_t02_impact_snapshot_saved_on_validation(db_mode):
    college = _mk_college(TENANT, "快照学院")
    major = _mk_major(TENANT, college, "快照专业")
    klass = _mk_class(TENANT, major, "快照班级")
    _mk_student(TENANT, klass, "T02100")

    vid = int(svc.create_version(version_name="停用专业", reason="r", tenant_id=TENANT)["versionId"])
    svc.add_change(
        vid, change_type="DISABLE", org_type="MAJOR", org_node_id=major, payload={}, tenant_id=TENANT
    )
    validated = _advance(vid, "VALIDATED")
    items = validated["impact"]["items"]
    assert items and items[0]["affectedStudents"] == 1


def test_t02_impact_counts_active_assignments(db_mode):
    college = _mk_college(TENANT, "任职影响学院")
    svc.create_assignment(
        user_id=6001, org_type="COLLEGE", org_node_id=college, assignment_type="SECRETARY",
        reason="教学秘书", tenant_id=TENANT,
    )
    impact = svc.compute_impact("COLLEGE", college, tenant_id=TENANT)
    assert impact["affectedAssignments"] == 1


# ── SYS04-T03：任职到期自动失效 ─────────────────────────────────────────────
def test_t03_expired_assignment_stops_being_effective(db_mode):
    college = _mk_college(TENANT, "任职学院")
    major = _mk_major(TENANT, college, "任职专业")
    klass = _mk_class(TENANT, major, "任职班级")

    start = datetime.utcnow() - timedelta(days=2)
    end = datetime.utcnow() - timedelta(hours=1)  # 已过期
    svc.create_assignment(
        user_id=7001, org_type="CLASS", org_node_id=klass, assignment_type="COUNSELOR",
        effective_at=start, expires_at=end, reason="学期辅导员", tenant_id=TENANT,
    )

    # 定时任务还没跑，读取时校验就必须已经拦住
    effective = svc.effective_assignments(7001, tenant_id=TENANT)
    assert effective == []

    # 带 includeExpired 才看得到，且状态仍是 ACTIVE（未刷新）
    allrows = svc.list_assignments(user_id=7001, include_expired=True, tenant_id=TENANT)["items"]
    assert len(allrows) == 1
    assert allrows[0]["effectiveNow"] is False

    # 定时任务补刀，状态落库
    result = svc.expire_due_assignments()
    assert result["expired"] >= 1
    after = svc.list_assignments(user_id=7001, include_expired=True, tenant_id=TENANT)["items"]
    assert after[0]["status"] == "EXPIRED"


def test_t03_future_assignment_not_effective_yet(db_mode):
    college = _mk_college(TENANT, "未来任职学院")
    svc.create_assignment(
        user_id=7002, org_type="COLLEGE", org_node_id=college, assignment_type="LEADER",
        effective_at=datetime.utcnow() + timedelta(days=3), reason="下学期上任", tenant_id=TENANT,
    )
    assert svc.effective_assignments(7002, tenant_id=TENANT) == []
    later = svc.list_assignments(
        user_id=7002, at=datetime.utcnow() + timedelta(days=4), tenant_id=TENANT
    )["items"]
    assert len(later) == 1


def test_t03_only_one_primary_assignment_per_user(db_mode):
    c1 = _mk_college(TENANT, "主任职A")
    c2 = _mk_college(TENANT, "主任职B")
    svc.create_assignment(
        user_id=7003, org_type="COLLEGE", org_node_id=c1, assignment_type="LEADER",
        is_primary=True, tenant_id=TENANT,
    )
    svc.create_assignment(
        user_id=7003, org_type="COLLEGE", org_node_id=c2, assignment_type="LEADER",
        is_primary=True, tenant_id=TENANT,
    )
    primaries = [a for a in svc.effective_assignments(7003, tenant_id=TENANT) if a["isPrimary"]]
    assert len(primaries) == 1
    assert primaries[0]["orgNodeId"] == str(c2)


def test_t03_revoke_takes_effect_immediately(db_mode):
    college = _mk_college(TENANT, "撤销任职学院")
    created = svc.create_assignment(
        user_id=7004, org_type="COLLEGE", org_node_id=college, assignment_type="SECRETARY", tenant_id=TENANT
    )
    svc.revoke_assignment(
        int(created["assignmentId"]), reason="岗位调整", expected_version=int(created["version"]), tenant_id=TENANT
    )
    assert svc.effective_assignments(7004, tenant_id=TENANT) == []

    with pytest.raises(AppException) as exc:
        svc.revoke_assignment(int(created["assignmentId"]), reason="重复撤销", expected_version=0, tenant_id=TENANT)
    assert exc.value.code == "VERSION_CONFLICT"


# ── SYS04-T04：跨租户节点不可引用 ───────────────────────────────────────────
def test_t04_cannot_reference_other_tenant_org_node(db_mode):
    foreign_college = _mk_college(OTHER_TENANT, "别校学院")

    vid = int(svc.create_version(version_name="越权尝试", reason="r", tenant_id=TENANT)["versionId"])
    with pytest.raises(AppException):
        svc.add_change(
            vid, change_type="RENAME", org_type="COLLEGE", org_node_id=foreign_college,
            payload={"name": "改别人的"}, tenant_id=TENANT,
        )

    with pytest.raises(AppException):
        svc.create_assignment(
            user_id=7005, org_type="COLLEGE", org_node_id=foreign_college,
            assignment_type="LEADER", tenant_id=TENANT,
        )

    with pytest.raises(AppException):
        svc.compute_impact("COLLEGE", foreign_college, tenant_id=TENANT)


def test_t04_cannot_move_under_other_tenant_parent(db_mode):
    college = _mk_college(TENANT, "本校学院")
    major = _mk_major(TENANT, college, "本校专业")
    foreign_college = _mk_college(OTHER_TENANT, "别校学院2")

    vid = int(svc.create_version(version_name="跨租户移动", reason="r", tenant_id=TENANT)["versionId"])
    with pytest.raises(AppException):
        svc.add_change(
            vid, change_type="MOVE", org_type="MAJOR", org_node_id=major,
            payload={"parentId": foreign_college}, tenant_id=TENANT,
        )


def test_t04_assignments_are_tenant_isolated(db_mode):
    mine = _mk_college(TENANT, "我的学院")
    theirs = _mk_college(OTHER_TENANT, "他们的学院")
    svc.create_assignment(
        user_id=7006, org_type="COLLEGE", org_node_id=mine, assignment_type="LEADER", tenant_id=TENANT
    )
    svc.create_assignment(
        user_id=7006, org_type="COLLEGE", org_node_id=theirs, assignment_type="LEADER", tenant_id=OTHER_TENANT
    )
    mine_rows = svc.effective_assignments(7006, tenant_id=TENANT)
    theirs_rows = svc.effective_assignments(7006, tenant_id=OTHER_TENANT)
    assert len(mine_rows) == 1 and mine_rows[0]["orgNodeId"] == str(mine)
    assert len(theirs_rows) == 1 and theirs_rows[0]["orgNodeId"] == str(theirs)
