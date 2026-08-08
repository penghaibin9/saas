"""正式成绩修读次数唯一分配回归（P0-N02）。

`MAX(attempt_no) + 1` 没有互斥：两个事务同时读到 MAX=0 就各自返回 1。正常发布、成绩认定、
免修、补考、清考、重修全都会写正式成绩，任意两条路径并发，就能给同一个学生同一门课造出两条
attempt_no 相同且都 PASSED 的正式事实——(source_biz_type, source_biz_id) 唯一键拦不住，
因为两条来源本来就不同。

这里用真实 MySQL 起并发线程直接压 `next_study_attempt_no`：只有真锁得住，两个线程才拿不到
同一个号。SQLite 没有行锁，压出来的绿是假的，所以本文件只在 MySQL 下有意义（db_mode 夹具）。
"""
from __future__ import annotations

import threading

import pytest

TID = 1000000000000000001


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "realName": "教务处",
                      "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx"})


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _student(db, student_no="GI2401"):
    from app.models import AcademicStudent, StudentProfile

    profile = StudentProfile(tenant_id=TID, student_no=student_no, real_name="身份甲",
                             grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    acad = AcademicStudent(tenant_id=TID, student_id=profile.id, student_no=student_no,
                           name="身份甲", class_name="软件2401")
    db.add(acad)
    db.flush()
    return acad


def _grade(db, acad_student_id, *, course_code="GI_MATH", attempt_no=1, source="PUBLISH"):
    from app.models import AcademicGrade

    row = AcademicGrade(
        tenant_id=TID, acad_student_id=acad_student_id, course_name="高等数学",
        course_id=1, course_code=course_code, course_version=1, attempt_no=attempt_no,
        credit_value=4, score=80, pass_status="PASSED", source=source, record_status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture()
def identity(db_mode):
    _ctx()
    from app.modules.academic_affairs.services import academic_affairs_grade_identity_service as svc

    return svc


def test_first_allocation_starts_at_one(identity, db_mode):
    db = _session()
    acad = _student(db)
    db.commit()
    assert identity.next_study_attempt_no(db, acad.id, "GI_MATH") == 1
    db.commit()
    db.close()


def test_allocation_continues_from_existing_history(identity, db_mode):
    """存量成绩已经修读到第 2 次，新头必须从 3 开始，不能重号也不能跳号。"""
    db = _session()
    acad = _student(db)
    _grade(db, acad.id, attempt_no=1)
    _grade(db, acad.id, attempt_no=2)
    db.commit()

    assert identity.next_study_attempt_no(db, acad.id, "GI_MATH") == 3
    db.commit()
    # 头已建立，第二次继续递增
    assert identity.next_study_attempt_no(db, acad.id, "GI_MATH") == 4
    db.commit()
    db.close()


def test_different_courses_and_students_have_independent_counters(identity, db_mode):
    db = _session()
    a = _student(db, "GI2401")
    b = _student(db, "GI2402")
    db.commit()
    assert identity.next_study_attempt_no(db, a.id, "GI_MATH") == 1
    assert identity.next_study_attempt_no(db, a.id, "GI_ENG") == 1
    assert identity.next_study_attempt_no(db, b.id, "GI_MATH") == 1
    db.commit()
    db.close()


def test_head_is_unique_per_student_and_course(identity, db_mode):
    from sqlalchemy.exc import IntegrityError

    from app.models import AaGradeIdentityHead

    db = _session()
    acad = _student(db)
    db.commit()
    identity.lock_grade_identity(db, acad.id, "GI_MATH")
    db.commit()

    db.add(AaGradeIdentityHead(tenant_id=TID, acad_student_id=acad.id, course_code="GI_MATH"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_missing_course_code_is_rejected(identity, db_mode):
    """没有稳定课程代码就无法定位计数器，必须 fail-closed 而不是静默用空串建一行。"""
    from app.core.exceptions import AppException

    db = _session()
    acad = _student(db)
    db.commit()
    with pytest.raises(AppException):
        identity.lock_grade_identity(db, acad.id, "")
    db.rollback()
    db.close()


def test_concurrent_allocation_never_hands_out_the_same_attempt_no(identity, db_mode):
    """真实 MySQL 并发：8 个线程抢同一个 (学生, 课程) 的修读次数，必须拿到 8 个互不相同的号。

    这正是原 MAX+1 实现失守的地方——没有锁时它们会大量拿到同一个 1。
    """
    db = _session()
    acad = _student(db)
    acad_id = acad.id
    db.commit()
    db.close()

    workers = 8
    results = []
    errors = []
    lock = threading.Lock()
    barrier = threading.Barrier(workers)

    def _allocate():
        _ctx()
        session = _session()
        try:
            barrier.wait(timeout=30)
            value = identity.next_study_attempt_no(session, acad_id, "GI_MATH")
            session.commit()
            with lock:
                results.append(value)
        except Exception as exc:  # noqa: BLE001  失败也要记录，静默吞掉会让并发问题看起来"通过"
            session.rollback()
            with lock:
                errors.append(repr(exc))
        finally:
            session.close()

    threads = [threading.Thread(target=_allocate) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert not errors, f"并发分配出现异常：{errors}"
    assert len(results) == workers, f"只有 {len(results)} 个线程完成：{results}"
    assert len(set(results)) == workers, f"修读次数重号：{sorted(results)}"
    assert sorted(results) == list(range(1, workers + 1)), f"序号不连续：{sorted(results)}"

    # 头上的计数器与实际分配一致
    from app.models import AaGradeIdentityHead
    db = _session()
    head = db.query(AaGradeIdentityHead).filter(
        AaGradeIdentityHead.tenant_id == TID,
        AaGradeIdentityHead.acad_student_id == acad_id,
        AaGradeIdentityHead.course_code == "GI_MATH").one()
    assert int(head.current_attempt_no) == workers
    db.close()


def test_duplicate_head_insert_does_not_discard_caller_business_data(identity, db_mode):
    """建头撞唯一键时，只能回滚建头那一小段，调用方已写的业务数据必须留下。

    `begin_nested()` 之后的 flush 会把 session 里所有 pending 对象一起写进这个 savepoint，
    回滚时会连调用方刚写的成绩行一起撤掉——业务数据丢在一个本该只影响计数器的地方。
    这里不用并发碰运气：先在另一个会话里把头建好，调用方这一侧就必然走重复键分支。
    """
    from app.models import AcademicGrade, AaGradeIdentityHead

    other = _session()
    acad = _student(other)
    acad_id = acad.id
    other.commit()
    # 另一个会话抢先建头并提交，制造出确定的重复键路径
    other.add(AaGradeIdentityHead(tenant_id=TID, acad_student_id=acad_id,
                                  course_code="GI_DUP", current_attempt_no=3))
    other.commit()
    other.close()

    db = _session()
    grade = _grade(db, acad_id, course_code="GI_DUP", attempt_no=None)
    grade.score = 66
    # 走到这里必然撞唯一键；分配仍要成功，并接着已有计数器 3 往下发
    value = identity.next_study_attempt_no(db, acad_id, "GI_DUP")
    assert value == 4
    grade.attempt_no = value
    db.commit()
    db.close()

    db = _session()
    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == TID,
        AcademicGrade.acad_student_id == acad_id,
        AcademicGrade.course_code == "GI_DUP").all()
    assert len(rows) == 1, f"业务成绩行被 savepoint 回滚带走了，剩 {len(rows)} 条"
    assert int(rows[0].score) == 66 and int(rows[0].attempt_no) == 4
    head = db.query(AaGradeIdentityHead).filter(
        AaGradeIdentityHead.tenant_id == TID,
        AaGradeIdentityHead.acad_student_id == acad_id,
        AaGradeIdentityHead.course_code == "GI_DUP").one()
    assert int(head.current_attempt_no) == 4
    db.close()


def test_all_formal_grade_writers_go_through_the_locked_allocator():
    """所有正式成绩来源必须共用同一个加锁分配器，不能有人自己算 MAX+1 绕过去。"""
    import inspect

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_grade_identity_service as svc

    source = inspect.getsource(svc.next_study_attempt_no)
    assert "lock_grade_identity" in source

    from pathlib import Path
    services = Path(__file__).resolve().parents[1] / "app/modules/academic_affairs/services"
    offenders = []
    for path in services.glob("*.py"):
        if path.name == "academic_affairs_grade_identity_service.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "func.max(AcademicGrade.attempt_no)" in text:
            offenders.append(path.name)
    assert not offenders, f"这些模块绕过了统一分配器自己算 MAX(attempt_no)：{offenders}"


def test_model_and_migration_declare_the_same_head_invariant():
    from pathlib import Path

    from app.models import AaGradeIdentityHead

    names = {c.name for c in AaGradeIdentityHead.__table__.constraints if c.name}
    assert "uk_aa_grade_identity_head" in names

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260807_aa_grade_identity_head.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "20260807_aa_grade_head"' in migration
    assert 'down_revision = "20260807_aa_exempt_ev"' in migration
    assert "uk_aa_grade_identity_head" in migration
    # 存量必须按现有成绩的 MAX 回填，否则老数据会被重号
    assert "MAX(attempt_no)" in migration
