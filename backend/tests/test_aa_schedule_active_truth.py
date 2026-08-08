"""课表唯一正式版本回归（P0-D05）。

要守住的两条不变式：

1. 一个(学期,范围)在任一时刻只有一份正式课表。此前同学期可以并存多个 PUBLISHED 批次，
   「学生现在的正式课表是哪一份」没有答案；换版必须显式顶替，而不是再造一份 PUBLISHED。
2. 教师、教室、班级是全校共享资源。学院 A 和学院 B 各自发布、两边批次内部都合法，
   同一个老师/同一间教室仍会被排在同一时段——批次级门禁看不见这种冲突。

本文件直接对 Service 和真实 MySQL 断言，不经 HTTP：发布接口还挂着教学任务完整性等一串
前置门禁，混在一起测会让"到底是哪条规则拦下的"变得说不清。
MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

import pytest

TID = 1000000000000000001


def _tenant_ctx():
    """_tid() 从租户上下文取值、审计从用户上下文取值；直连 Service 测试要自己铺好两者。"""
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "u_1", "tenantId": str(TID), "realName": "教务处",
        "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx",
    })


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _batch(db, term_id=1, *, college_id=None, name="课表批次", status="PRE_PUBLISHED"):
    from app.models import AaScheduleBatch

    row = AaScheduleBatch(tenant_id=TID, term_id=term_id, batch_name=name,
                          college_id=college_id, status=status)
    db.add(row)
    db.flush()
    return row


def _item(db, batch, *, weekday=1, slot_no=1, teacher_key="T1", classroom_id=None,
          class_id=None, start_week=1, end_week=18, week_parity="ALL", course_name="高等数学"):
    from app.models import AaScheduleItem

    row = AaScheduleItem(
        tenant_id=TID, batch_id=batch.id, weekday=weekday, slot_no=slot_no,
        teacher_key=teacher_key, teacher_name=teacher_key, classroom_id=classroom_id,
        classroom_text=f"教室{classroom_id}" if classroom_id else None,
        class_id=class_id, class_name=f"班{class_id}" if class_id else None,
        start_week=start_week, end_week=end_week, week_parity=week_parity,
        course_name=course_name, status="EFFECTIVE",
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def truth(db_mode):
    _tenant_ctx()
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as svc

    return svc


def test_scope_head_is_unique_per_term_and_scope(truth, db_mode):
    """同一(学期,范围)只能有一行范围头；全校范围用 scope_id=0 而不是 NULL。"""
    from sqlalchemy.exc import IntegrityError

    from app.models import AaScheduleScopeHead

    db = _session()
    head = truth.lock_scope_head(db, 1, "SCHOOL", 0)
    assert head.scope_id == 0 and head.version == 0
    db.commit()

    # 再取一次必须是同一行，不是新建
    again = truth.lock_scope_head(db, 1, "SCHOOL", 0)
    assert int(again.id) == int(head.id)
    db.commit()

    # 绕过服务直插同键 → 唯一约束必须拦下
    db.add(AaScheduleScopeHead(tenant_id=TID, term_id=1, scope_type="SCHOOL", scope_id=0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_promote_to_active_supersedes_previous_official_schedule(truth, db_mode):
    """换版后旧批次必须变 SUPERSEDED，且范围头只指向新批次——不留两份 PUBLISHED。"""
    from app.models import AaScheduleBatch

    db = _session()
    first = _batch(db, name="第一版", status="PUBLISHED")
    head = truth.lock_scope_head(db, 1, "SCHOOL", 0)
    truth.promote_to_active(db, first, head)
    db.commit()
    assert truth.active_batch_id(db, 1, "SCHOOL", 0) == int(first.id)

    second = _batch(db, name="第二版", status="PRE_PUBLISHED")
    head = truth.lock_scope_head(db, 1, "SCHOOL", 0)
    result = truth.promote_to_active(db, second, head)
    second.status = "PUBLISHED"
    db.commit()

    assert result["supersededBatchId"] == str(first.id)
    assert result["headVersion"] == 2
    assert truth.active_batch_id(db, 1, "SCHOOL", 0) == int(second.id)
    assert db.get(AaScheduleBatch, int(first.id)).status == "SUPERSEDED"
    assert db.get(AaScheduleBatch, int(second.id)).supersedes_batch_id == int(first.id)
    # 同学期同范围只剩一份 PUBLISHED
    published = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == TID, AaScheduleBatch.term_id == 1,
        AaScheduleBatch.status == "PUBLISHED").all()
    assert [int(row.id) for row in published] == [int(second.id)]
    db.close()


def test_teacher_conflict_across_colleges_is_detected(truth, db_mode):
    """两个学院各自排张老师周一第1节：各自批次内部都合法，全校层面是同一个人分身。"""
    db = _session()
    published = _batch(db, college_id=11, name="软件学院课表", status="PUBLISHED")
    _item(db, published, teacher_key="T_ZHANG", class_id=101)
    db.commit()

    candidate = _batch(db, college_id=22, name="机电学院课表", status="PRE_PUBLISHED")
    _item(db, candidate, teacher_key="T_ZHANG", class_id=202)
    db.commit()

    result = truth.validate_school_wide_conflicts(db, candidate)
    assert result["problems"], "跨学院共享教师冲突必须被检出"
    assert any("TEACHER_SCHEDULE_CONFLICT" in text for text in result["problems"])
    db.close()


def test_classroom_conflict_across_colleges_is_detected(truth, db_mode):
    db = _session()
    published = _batch(db, college_id=11, status="PUBLISHED")
    _item(db, published, teacher_key="T_A", classroom_id=301, class_id=101)
    db.commit()

    candidate = _batch(db, college_id=22, status="PRE_PUBLISHED")
    _item(db, candidate, teacher_key="T_B", classroom_id=301, class_id=202)
    db.commit()

    problems = truth.validate_school_wide_conflicts(db, candidate)["problems"]
    assert any("CLASSROOM_SCHEDULE_CONFLICT" in text for text in problems)
    db.close()


def test_class_conflict_across_batches_is_detected(truth, db_mode):
    """同一个班同一时段被两份课表各排一门课 → 学生分身。"""
    db = _session()
    published = _batch(db, status="PUBLISHED")
    _item(db, published, teacher_key="T_A", class_id=505)
    db.commit()

    candidate = _batch(db, status="PRE_PUBLISHED")
    _item(db, candidate, teacher_key="T_B", class_id=505)
    db.commit()

    problems = truth.validate_school_wide_conflicts(db, candidate)["problems"]
    assert any("CLASS_SCHEDULE_CONFLICT" in text for text in problems)
    db.close()


def test_non_overlapping_weeks_and_parity_do_not_conflict(truth, db_mode):
    """门禁不能一刀切：周次不相交、单双周错开都是正常排课，必须放行。"""
    db = _session()
    published = _batch(db, status="PUBLISHED")
    _item(db, published, teacher_key="T_A", start_week=1, end_week=8)
    _item(db, published, teacher_key="T_B", slot_no=3, week_parity="ODD")
    db.commit()

    candidate = _batch(db, status="PRE_PUBLISHED")
    _item(db, candidate, teacher_key="T_A", start_week=9, end_week=18)   # 周次不相交
    _item(db, candidate, teacher_key="T_B", slot_no=3, week_parity="EVEN")  # 单双周错开
    db.commit()

    assert truth.validate_school_wide_conflicts(db, candidate)["problems"] == []
    db.close()


def test_superseded_batch_is_not_counted_as_live_resource(truth, db_mode):
    """被顶替的历史课表不再占用资源；否则换版后旧版会把新版自己挡死。"""
    db = _session()
    old = _batch(db, status="PUBLISHED")
    _item(db, old, teacher_key="T_A", class_id=101)
    db.commit()

    replacement = _batch(db, status="PRE_PUBLISHED")
    _item(db, replacement, teacher_key="T_A", class_id=101)
    db.commit()
    # 顶替前：与旧版冲突
    assert truth.validate_school_wide_conflicts(db, replacement)["problems"]

    head = truth.lock_scope_head(db, 1, "SCHOOL", 0)
    head.active_batch_id = int(old.id)
    truth.promote_to_active(db, replacement, head)
    db.commit()
    # 顶替后：旧版已 SUPERSEDED，不再参与竞争
    assert truth.validate_school_wide_conflicts(db, replacement)["problems"] == []
    db.close()


def test_require_no_school_wide_conflict_raises_409(truth, db_mode):
    from app.core.exceptions import AppException

    db = _session()
    published = _batch(db, status="PUBLISHED")
    _item(db, published, teacher_key="T_A", class_id=101)
    db.commit()
    candidate = _batch(db, status="PRE_PUBLISHED")
    _item(db, candidate, teacher_key="T_A", class_id=202)
    db.commit()

    with pytest.raises(AppException) as exc:
        truth.require_no_school_wide_conflict(db, candidate)
    assert exc.value.http_status == 409
    db.close()


def test_publish_wires_scope_head_and_school_wide_gate():
    """发布必须按「锁范围头 → 全校冲突 → CAS 换版」的顺序接线，且不能绕回旧实现。"""
    import inspect

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as final

    assert final.publish.__module__.endswith("academic_affairs_schedule_final_service")
    source = inspect.getsource(final.publish)
    lock_at = source.index("lock_scope_head")
    gate_at = source.index("require_no_school_wide_conflict")
    promote_at = source.index("promote_to_active")
    assert lock_at < gate_at < promote_at, "锁必须早于校验，校验必须早于换版"


def test_scope_head_model_and_migration_declare_the_same_invariant():
    """模型和迁移必须都声明唯一约束；两边分裂会让约束只在其中一处成立。"""
    from pathlib import Path

    from app.models import AaScheduleBatch, AaScheduleScopeHead

    names = {c.name for c in AaScheduleScopeHead.__table__.constraints if c.name}
    assert "uk_aa_schedule_scope_head" in names
    assert "supersedes_batch_id" in AaScheduleBatch.__mapper__.attrs.keys()

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260807_aa_schedule_scope_head.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "20260807_aa_sched_head"' in migration
    assert 'down_revision = "20260806_discipline_pkg11"' in migration
    assert "uk_aa_schedule_scope_head" in migration
    assert "supersedes_batch_id" in migration
    # 存量回填：每个范围只留最新一份 PUBLISHED，其余标 SUPERSEDED
    assert "SUPERSEDED" in migration
