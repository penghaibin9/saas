"""学生主档 ↔ 登录账号稳定绑定（学生主档统一整改 阶段 C）。

核心价值验证：**学号更正后，该生仍能登录到自己的档案、仍能收到班级消息**——
这正是绑定表要解决的问题（此前靠 login_name == student_no 隐式关联，改号即断）。
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

TID = 1000000000000000001


def _load_migration():
    """直接加载迁移模块，测回填 SQL 本身，而不是在测试里复制一份。"""
    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / \
        "student_c1_account_link.py"
    spec = importlib.util.spec_from_file_location("mig_c1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_student_and_account(db, no="LK0001", name="绑定测试"):
    from app.models import StudentProfile, User
    from app.core.security import hash_password

    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                       current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(s)
    u = User(tenant_id=TID, login_name=no, real_name=name,
             password_hash=hash_password("Test@123456"), user_type="STUDENT", status="ACTIVE")
    db.add(u)
    db.flush()
    return s, u


# ── 1. 回填 ────────────────────────────────────────────────────────────────

def test_backfill_creates_links_from_legacy_convention(db_mode):
    """回填按历史约定 login_name == student_no 建立 ACTIVE 绑定。"""
    from app.db.session import get_sessionmaker
    from app.models.student_account_link import LINK_ACTIVE, StudentAccountLink
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db)
        db.commit()
        _load_migration()._backfill(db.connection())
        db.commit()

        row = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == TID,
            StudentAccountLink.student_id == s.id)).first()
        assert row is not None, "回填应为历史学生建立绑定"
        assert int(row.user_id) == int(u.id)
        assert row.link_status == LINK_ACTIVE and row.source == "BACKFILL"
    finally:
        db.close()


def test_backfill_is_idempotent(db_mode):
    """重复执行迁移不得产生第二条绑定（否则撞唯一键）。"""
    from app.db.session import get_sessionmaker
    from app.models.student_account_link import StudentAccountLink
    from sqlalchemy import func, select

    db = get_sessionmaker()()
    try:
        _mk_student_and_account(db, no="LK0002")
        db.commit()
        mig = _load_migration()
        mig._backfill(db.connection())
        db.commit()
        mig._backfill(db.connection())
        db.commit()

        cnt = db.scalar(select(func.count()).select_from(StudentAccountLink).where(
            StudentAccountLink.tenant_id == TID))
        assert cnt == 1, f"回填不幂等，产生了 {cnt} 条绑定"
    finally:
        db.close()


def test_backfill_skips_non_student_accounts(db_mode):
    """工号与学号撞号的教师账号不得被回填成学生绑定。"""
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, User
    from app.models.student_account_link import StudentAccountLink
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no="LK9999", real_name="撞号学生",
                           current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.add(User(tenant_id=TID, login_name="LK9999", real_name="撞号教师",
                    password_hash=hash_password("Test@123456"),
                    user_type="TEACHER", status="ACTIVE"))
        db.commit()
        _load_migration()._backfill(db.connection())
        db.commit()

        rows = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == TID)).all()
        assert not rows, "教师账号不应被回填为学生绑定"
    finally:
        db.close()


# ── 2. 绑定服务 ────────────────────────────────────────────────────────────

def test_bind_is_idempotent_and_rejects_double_binding(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.services import student_account_link_service as link_svc

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db, no="LK0003")
        r1 = link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        r2 = link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        assert r1.id == r2.id, "重复绑定同一对应关系应幂等"

        s2, u2 = _mk_student_and_account(db, no="LK0004")
        with pytest.raises(AppException):
            # 账号已绑给别人 → 拒绝，换绑必须先显式解绑
            link_svc.bind_in_session(db, tenant_id=TID, student_id=s2.id, user_id=u.id)
    finally:
        db.rollback()
        db.close()


def test_lookup_both_directions(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import student_account_link_service as link_svc

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db, no="LK0005")
        link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        db.flush()
        assert link_svc.get_student_id_by_user(db, tenant_id=TID, user_id=u.id) == s.id
        assert link_svc.get_user_id_by_student(db, tenant_id=TID, student_id=s.id) == u.id
        # 未绑定的学生返回 None，供调用方计入 ACCOUNT_UNLINKED
        assert link_svc.get_user_id_by_student(db, tenant_id=TID, student_id=999999) is None
    finally:
        db.rollback()
        db.close()


# ── 3. 学号更正后身份不断（本阶段的核心价值）──────────────────────────────

def test_identity_survives_student_no_correction(db_mode):
    """改学号后：经绑定仍解析到同一学生；靠学号的老办法则会失效。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_account_link_service as link_svc
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db, no="LK1000", name="改号学生")
        link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        db.commit()
        sid, ver = s.id, int(s.version or 0)

        master.apply_approved_correction_in_session(
            db, tenant_id=TID, student_id=sid, field_key="STUDENT_NO",
            new_value="LK2000", expected_version=ver, actor=None, correction_id=99)
        db.commit()

        # 学号已变，登录名还是旧的
        assert db.get(StudentProfile, sid).student_no == "LK2000"
        assert u.login_name == "LK1000"

        # 经绑定仍能解析到同一学生
        assert link_svc.get_student_id_by_user(db, tenant_id=TID, user_id=u.id) == sid

        # 而旧办法（login_name == student_no）此时已经找不到人——正是本阶段要消灭的
        stale = db.scalars(select_stale(StudentProfile, u.login_name)).first()
        assert stale is None, "旧的学号关联方式在改号后必然失效"
    finally:
        db.close()


def select_stale(model, login_name):
    from sqlalchemy import select
    return select(model).where(model.tenant_id == TID, model.student_no == login_name,
                               model.is_deleted.is_(False))


# ── 4. 生命周期联动 ────────────────────────────────────────────────────────

def test_void_suspends_link_without_touching_account(db_mode):
    """作废学籍 → 绑定 SUSPENDED；账号状态必须原样不动。"""
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.models.student_account_link import LINK_SUSPENDED, StudentAccountLink
    from app.services import student_account_link_service as link_svc
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db, no="LK3000")
        link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        db.flush()

        link_svc.suspend_by_student_in_session(db, tenant_id=TID, student_id=s.id,
                                               remark="学籍作废：测试")
        db.flush()

        row = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.student_id == s.id)).first()
        assert row.link_status == LINK_SUSPENDED
        assert db.get(User, u.id).status == "ACTIVE", "作废学籍不得顺手停用登录账号"
        # 暂停后按账号查不到学生（该生不应再被当作在校生处理）
        assert link_svc.get_student_id_by_user(db, tenant_id=TID, user_id=u.id) is None
    finally:
        db.rollback()
        db.close()


def test_restore_reactivates_link(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.student_account_link import LINK_ACTIVE, StudentAccountLink
    from app.services import student_account_link_service as link_svc
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        s, u = _mk_student_and_account(db, no="LK4000")
        link_svc.bind_in_session(db, tenant_id=TID, student_id=s.id, user_id=u.id)
        db.flush()
        link_svc.suspend_by_student_in_session(db, tenant_id=TID, student_id=s.id)
        db.flush()
        assert link_svc.reactivate_by_student_in_session(db, tenant_id=TID, student_id=s.id) == 1
        db.flush()

        row = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.student_id == s.id)).first()
        assert row.link_status == LINK_ACTIVE
        assert link_svc.get_student_id_by_user(db, tenant_id=TID, user_id=u.id) == s.id
    finally:
        db.rollback()
        db.close()


# ── 5. 消息受众 ────────────────────────────────────────────────────────────

def test_audience_join_prefers_link_and_falls_back(db_mode):
    """受众 SQL：有绑定按绑定，无绑定退回学号；教师账号不得被兜底命中。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, User
    from app.services.message_audience_service import _link_join, _user_join
    from app.services import student_account_link_service as link_svc
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        # A：已绑定，且登录名与学号**不同**（模拟改过号）
        from app.core.security import hash_password
        a = StudentProfile(tenant_id=TID, student_no="AUD_NEW_A", real_name="已绑定A",
                           current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add(a)
        ua = User(tenant_id=TID, login_name="AUD_OLD_A", real_name="已绑定A",
                  password_hash=hash_password("Test@123456"), user_type="STUDENT", status="ACTIVE")
        db.add(ua)
        db.flush()
        link_svc.bind_in_session(db, tenant_id=TID, student_id=a.id, user_id=ua.id)
        # B：未绑定，靠学号兜底
        b, ub = _mk_student_and_account(db, no="AUD_B", name="未绑定B")
        db.flush()

        rows = db.execute(
            select(StudentProfile.id, User.id)
            .select_from(StudentProfile)
            .outerjoin(*_link_join())
            .outerjoin(*_user_join())
            .where(StudentProfile.tenant_id == TID,
                   StudentProfile.id.in_([a.id, b.id]))
        ).all()
        got = {int(sid): (int(uid) if uid else None) for sid, uid in rows}
        assert got[a.id] == ua.id, "已绑定学生必须经绑定命中账号（即使登录名与学号不同）"
        assert got[b.id] == ub.id, "未绑定学生应由迁移期兜底按学号命中"
    finally:
        db.rollback()
        db.close()


# ── 6. 部署安全网：忘跑迁移也不能出事 ──────────────────────────────────────

def test_read_paths_degrade_when_link_table_missing():
    """绑定表查询失败时必须降级为「查不到」，不能把登录整条链路带崩。

    真实场景：代码已升级、迁移尚未执行。测试库总是全新建表，撞不到这个场景，
    因此这里显式模拟查询异常。
    """
    from app.services import student_account_link_service as link_svc

    class BoomDB:
        def scalars(self, *a, **k):
            raise RuntimeError("Table 't_student_account_link' doesn't exist")
        def scalar(self, *a, **k):
            raise RuntimeError("Table 't_student_account_link' doesn't exist")

    db = BoomDB()
    # 不抛异常，返回 None → 调用方走历史兜底
    assert link_svc.get_student_id_by_user(db, tenant_id=TID, user_id=1) is None
    assert link_svc.get_user_id_by_student(db, tenant_id=TID, student_id=1) is None
    assert link_svc.active_user_ids_for_students(db, tenant_id=TID, student_ids=[1, 2]) == {}


def test_audience_joins_switch_by_table_readiness():
    """绑定表未建时，受众查询必须整体退回学号 JOIN，绝不引用不存在的表。"""
    from sqlalchemy import select
    from sqlalchemy.dialects import mysql

    from app.models import StudentProfile, User
    import app.services.message_audience_service as mas

    def render(q):
        return str(q.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))

    class FakeDB:
        def get_bind(self):
            raise RuntimeError("no bind")

    original = mas._LINK_TABLE_READY
    try:
        mas._LINK_TABLE_READY = False
        sql = render(mas.apply_student_account_joins(
            select(User.id).select_from(StudentProfile), FakeDB()))
        assert "t_student_account_link" not in sql, "表缺失时不得 JOIN 不存在的表"
        assert "login_name" in sql, "应退回学号匹配"

        mas._LINK_TABLE_READY = True
        sql2 = render(mas.apply_student_account_joins(
            select(User.id).select_from(StudentProfile), FakeDB(),
            active_only=True, inner_user=True))
        assert "t_student_account_link" in sql2 and "INNER JOIN t_user" in sql2
    finally:
        mas._LINK_TABLE_READY = original


def test_startup_warns_about_pending_migration(db_mode, caplog):
    """缺表时启动检查必须给出可直接照做的提示，而不是沉默。

    需 db_mode：检查仅在数据库模式下执行（未启用 DB 时无表可查，直接返回）。
    """
    import logging

    import app.main as m

    original = m._REQUIRED_TABLES
    try:
        m._REQUIRED_TABLES = {"t_definitely_missing_xyz": "自检用"}
        with caplog.at_level(logging.WARNING, logger="app.startup"):
            m._check_pending_migrations()
        text = caplog.text
        assert "PENDING_MIGRATION" in text
        assert "alembic upgrade head" in text, "提示必须包含可直接执行的命令"
    finally:
        m._REQUIRED_TABLES = original
