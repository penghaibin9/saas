"""主档乐观锁的**真实并发**行为（不用 inspect 静态断言代替）。

两个独立 session 读到同一 version 后同时改同一学生：先提交者成功，
后提交者必须因 expectedVersion 不一致返回 409 DATA_CONFLICT，
且库里只保留先提交那一份数据。

MySQL 默认 REPEATABLE READ：后一个 session 在自己的事务快照里仍看到旧 version，
因此前置比较会通过，真正拦住它的是 `WHERE version = ?` 的条件更新（CAS）命中 0 行——
这正是本用例要覆盖的路径。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

TID = 1000000000000000001


def _seed_student(no="CC0001", name="并发原始"):
    """建一个带完整组织的学生，返回 (student_id, version)。"""
    from app.core.student_master_contract import StudentCreateCommand
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.models.org import College, Major, SchoolClass
    from app.services import student_master_application_service as master

    db = get_sessionmaker()()
    try:
        col = College(tenant_id=TID, college_name="并发测试学院", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=TID, college_id=col.id, major_name="并发测试专业", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name="并发2601",
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        res = master.create_student_in_session(
            db, tenant_id=TID, actor=None,
            cmd=StudentCreateCommand(student_no=no, real_name=name, class_id=cls.id,
                                     require_complete_org=True))
        db.commit()
        row = db.get(StudentProfile, res.student_id)
        return res.student_id, int(row.version or 0)
    finally:
        db.close()


def test_concurrent_update_second_writer_gets_409(db_mode):
    """两个 session 基于同一 version 更新姓名：第二个必须 409，且不得覆盖第一个。"""
    from app.core.student_master_contract import StudentIdentityUpdateCommand
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    sid, v0 = _seed_student()

    db_a = get_sessionmaker()()
    db_b = get_sessionmaker()()
    try:
        # 两个事务都先读到同一份数据，建立各自的快照
        a_row = db_a.get(StudentProfile, sid)
        b_row = db_b.get(StudentProfile, sid)
        assert int(a_row.version or 0) == v0 and int(b_row.version or 0) == v0

        # A 先改并提交
        master.update_identity_in_session(
            db_a, tenant_id=TID, student_id=sid,
            cmd=StudentIdentityUpdateCommand(expected_version=v0, real_name="甲先提交"),
            actor=None)
        db_a.commit()

        # B 拿着同一个旧 version 再改 → 必须被拒
        with pytest.raises(AppException) as ei:
            master.update_identity_in_session(
                db_b, tenant_id=TID, student_id=sid,
                cmd=StudentIdentityUpdateCommand(expected_version=v0, real_name="乙后提交"),
                actor=None)
            db_b.commit()
        err = ei.value
        assert getattr(err, "code", "") == "DATA_CONFLICT"
        assert getattr(err, "http_status", None) == 409
        db_b.rollback()
    finally:
        db_a.close()
        db_b.close()

    # 最终库里只有 A 的数据，版本只递增一次
    db_c = get_sessionmaker()()
    try:
        final = db_c.get(StudentProfile, sid)
        assert final.real_name == "甲先提交", "后提交者不得覆盖先提交者"
        assert int(final.version or 0) == v0 + 1, "版本只应递增一次"
    finally:
        db_c.close()


def test_stale_version_rejected_even_without_concurrent_session(db_mode):
    """顺序两次更新：第二次沿用第一次之前的 version 同样必须 409。"""
    from app.core.student_master_contract import StudentIdentityUpdateCommand
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    sid, v0 = _seed_student(no="CC0002", name="顺序原始")

    db = get_sessionmaker()()
    try:
        master.update_identity_in_session(
            db, tenant_id=TID, student_id=sid,
            cmd=StudentIdentityUpdateCommand(expected_version=v0, real_name="第一次"),
            actor=None)
        db.commit()
    finally:
        db.close()

    db2 = get_sessionmaker()()
    try:
        with pytest.raises(AppException) as ei:
            master.update_identity_in_session(
                db2, tenant_id=TID, student_id=sid,
                cmd=StudentIdentityUpdateCommand(expected_version=v0, real_name="用旧版本再改"),
                actor=None)
        assert getattr(ei.value, "http_status", None) == 409
        db2.rollback()
    finally:
        db2.close()

    db3 = get_sessionmaker()()
    try:
        assert db3.get(StudentProfile, sid).real_name == "第一次"
    finally:
        db3.close()


def test_correction_approval_uses_cas_and_rejects_stale_version(db_mode):
    """学籍更正走统一服务：拿过期 version 审核通过必须 409，主档不被改。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    sid, v0 = _seed_student(no="CC0003", name="更正原始")

    db = get_sessionmaker()()
    try:
        # 先制造一次版本推进（模拟期间被别人改过）
        master.apply_approved_correction_in_session(
            db, tenant_id=TID, student_id=sid, field_key="REAL_NAME",
            new_value="更正一次", expected_version=v0, actor=None, correction_id=1)
        db.commit()
    finally:
        db.close()

    db2 = get_sessionmaker()()
    try:
        with pytest.raises(AppException) as ei:
            master.apply_approved_correction_in_session(
                db2, tenant_id=TID, student_id=sid, field_key="REAL_NAME",
                new_value="拿旧版本再更正", expected_version=v0, actor=None, correction_id=2)
        assert getattr(ei.value, "http_status", None) == 409
        db2.rollback()
    finally:
        db2.close()

    db3 = get_sessionmaker()()
    try:
        assert db3.get(StudentProfile, sid).real_name == "更正一次"
    finally:
        db3.close()


def test_correction_student_no_uniqueness_covers_soft_deleted(db_mode):
    """学号更正的查重必须覆盖软删行，否则审核通过会撞唯一键。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import student_master_application_service as master

    sid_a, v_a = _seed_student(no="CC0100", name="占号者")
    # 把 A 作废，其学号仍然占用（租户内永久唯一）
    db = get_sessionmaker()()
    try:
        row = db.get(StudentProfile, sid_a)
        row.is_deleted = True
        db.commit()
    finally:
        db.close()

    sid_b, v_b = _seed_student(no="CC0200", name="待更正者")

    db2 = get_sessionmaker()()
    try:
        with pytest.raises(AppException) as ei:
            master.apply_approved_correction_in_session(
                db2, tenant_id=TID, student_id=sid_b, field_key="STUDENT_NO",
                new_value="CC0100", expected_version=v_b, actor=None, correction_id=3)
        msg = str(getattr(ei.value, "message", "") or ei.value)
        assert "已被占用" in msg and getattr(ei.value, "http_status", None) == 409
        db2.rollback()
    finally:
        db2.close()
