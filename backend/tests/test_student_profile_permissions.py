"""学籍维护权限矩阵与受控恢复流程（甲方 2026-07-26 拍板口径）。

矩阵：
- SCHOOL_ADMIN    全校，可补录 / 维护 / 恢复（持 * 通配）
- ACADEMIC_ADMIN  全校，可补录 / 维护 / 恢复（学籍主责角色）
- COLLEGE_ADMIN   仅本学院，可补录 / 维护 / 恢复；不得跨学院
- COUNSELOR 等    不得建档 / 恢复 / 改核心学籍，只能查看与发起更正
"""
from __future__ import annotations

import pytest

TID = 1000000000000000001

CREATE = "student.profile.create"
UPDATE = "student.profile.update"
RESTORE = "student.profile.restore"
VIEW = "student.profile.view"


def _perms(role: str) -> set:
    from app.core.permissions import ROLE_PERMISSIONS
    return set(ROLE_PERMISSIONS.get(role, set()))


def _can(role: str, code: str) -> bool:
    """复用运行时的模式匹配（app.core.permissions._match），不另写一套判定。"""
    from app.core.permissions import _match
    return _match(code, _perms(role))


# ── 1. 权限矩阵 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ["SCHOOL_ADMIN", "ACADEMIC_ADMIN", "COLLEGE_ADMIN"])
@pytest.mark.parametrize("code", [CREATE, UPDATE, RESTORE, VIEW])
def test_maintainer_roles_have_all_profile_actions(role, code):
    assert _can(role, code), f"{role} 应具备 {code}"


@pytest.mark.parametrize("role", ["COUNSELOR", "PSYCHOLOGY_TEACHER", "FUNDING_TEACHER",
                                  "YOUTH_LEAGUE", "ACADEMIC_TEACHER"])
@pytest.mark.parametrize("code", [CREATE, RESTORE])
def test_non_maintainer_roles_cannot_create_or_restore(role, code):
    """辅导员等不得直接建档或恢复；他们走查看 / 发起更正 / 审批节点。"""
    assert not _can(role, code), f"{role} 不应具备 {code}"


@pytest.mark.parametrize("role", ["STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN"])
def test_student_affairs_not_granted_restore(role):
    """学工保留存量 manage 兼容既有功能，但恢复是高危动作，不授予。"""
    assert not _can(role, RESTORE), f"{role} 不应具备 {RESTORE}"


def test_restore_endpoint_does_not_accept_manage_fallback():
    """恢复端点只认 student.profile.restore，不接受宽泛的 manage 兜底。"""
    import inspect

    from app.api.v1 import student as student_api

    src = inspect.getsource(student_api)
    assert '_P_RESTORE = require_permission("student.profile.restore")' in src
    # 建档/更新允许 manage 并列（存量兼容），恢复不允许
    assert '_P_CREATE = require_any_permission("student.profile.create", "student.profile.manage")' in src


def test_restore_route_registered():
    from app.api.v1.student import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/students/restore" in paths


# ── 2. 恢复流程 ────────────────────────────────────────────────────────────

def _seed_org(db):
    from app.models.org import College, Major, SchoolClass

    col = College(tenant_id=TID, college_name="信息工程学院", status="ACTIVE")
    db.add(col); db.flush()
    maj = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(maj); db.flush()
    cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="软件2601",
                      grade="2026", status="ACTIVE", class_status="NORMAL")
    db.add(cls); db.flush()
    return cls


def _create(db, no="RS0001", name="恢复测试"):
    from app.core.student_master_contract import StudentCreateCommand
    from app.services import student_master_application_service as master

    cls = _seed_org(db)
    return master.create_student_in_session(
        db, tenant_id=TID, actor=None,
        cmd=StudentCreateCommand(student_no=no, real_name=name, class_id=cls.id,
                                 require_complete_org=True))


def test_restore_requires_reason_of_at_least_five_chars(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        _create(db)
        db.flush()
        with pytest.raises(AppException) as ei:
            master.restore_voided_student_in_session(
                db, tenant_id=TID, student_no="RS0001", reason="太短", actor=None)
        assert "不少于 5" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback(); db.close()


def test_restore_rejects_when_active_profile_exists(db_mode):
    """恢复前重新确认：期间已有有效同学号主档时必须拒绝，而不是撞唯一键。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        _create(db)
        db.flush()
        with pytest.raises(AppException) as ei:
            master.restore_voided_student_in_session(
                db, tenant_id=TID, student_no="RS0001",
                reason="该生仍在籍需要恢复", actor=None)
        assert "已有有效学生主档" in str(getattr(ei.value, "message", "") or ei.value)
    finally:
        db.rollback(); db.close()


def test_restore_reuses_original_id_and_records_states(db_mode):
    """恢复复用原 studentId，并返回作废前后状态供审计记录。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        created = _create(db)
        db.flush()
        sid = created.student_id

        s = db.get(StudentProfile, sid)
        s.is_deleted = True
        s.student_status = "RECYCLED"
        s.remark = "VOID:误作废"
        db.flush()

        out = master.restore_voided_student_in_session(
            db, tenant_id=TID, student_no="RS0001",
            reason="经教务处核实该生仍在籍，恢复原档案", actor=None)
        db.flush()

        assert out["studentId"] == sid, "必须复用原 studentId，不能新建第二份"
        assert out["before"]["isDeleted"] is True and out["after"]["isDeleted"] is False
        assert out["before"]["studentStatus"] == "RECYCLED"
        assert out["after"]["studentStatus"] == "NORMAL"

        again = db.get(StudentProfile, sid)
        assert again.is_deleted is False
        # 作废原因写在 remark（VOID:xxx），恢复后必须清掉，否则会被当成风险等级读
        assert not str(again.remark or "").startswith("VOID:")
    finally:
        db.rollback(); db.close()


def test_restore_does_not_touch_login_account(db_mode):
    """恢复学籍 ≠ 恢复登录：账号状态必须原样不动。"""
    import inspect

    from app.services import student_master_application_service as master

    src = inspect.getsource(master.restore_voided_student_in_session)
    assert "User" not in src, "恢复流程不得触碰登录账号"
    assert "不动登录账号" in src or "账号" in src


def test_restore_missing_profile_is_404(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        with pytest.raises(AppException):
            master.restore_voided_student_in_session(
                db, tenant_id=TID, student_no="NOSUCH999",
                reason="不存在的学号恢复测试", actor=None)
    finally:
        db.rollback(); db.close()


# ── 3. 补录不再复活 & 数据范围 ─────────────────────────────────────────────

def test_create_never_auto_restores():
    """allow_restore 默认 False，且补录不再传该开关。"""
    import inspect

    from app.core.student_master_contract import StudentCreateCommand
    from app.services import db_service

    assert StudentCreateCommand(student_no="x", real_name="y").allow_restore is False
    src = inspect.getsource(db_service.create_student)
    assert "allow_restore=False" in src
    assert "restoreVoided" not in src, "补录不应再有恢复开关"


def test_org_scope_guard_exists_for_existing_student():
    """学院管理员对既有学生的写操作必须过后端范围校验，不能只靠前端筛选。"""
    import inspect

    from app.services import db_service
    from app.services.student_org_validator import assert_student_org_scope

    src = inspect.getsource(assert_student_org_scope)
    assert "NO_DATA_SCOPE" in src and "allowed_class_ids" in src
    assert "assert_student_org_scope" in inspect.getsource(db_service.restore_student)
