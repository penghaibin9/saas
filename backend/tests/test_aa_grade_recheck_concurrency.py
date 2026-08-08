"""成绩复查审批并发回归（P0-N01）。

`review()` 原来第一条业务读取是无锁的 `db.get(AaGradeRecheck, ...)`，两个教务员并发时可以
双双读到 SUBMITTED：一个 REJECT、一个 ADJUST，两边各自 commit。结果是「驳回成功」的回执和
被改掉的正式成绩同时成立——审批结论和正式成绩形成两个互相矛盾的真值。

ADJUST 分支后面确实锁了 AcademicGrade，但那时决策早已分叉，锁晚了。

真实 MySQL 并发（db_mode 夹具）：SQLite 没有行锁，压出来的绿是假的。
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


def _seed(db):
    """一条 SUBMITTED 复查申请 + 它指向的正式成绩。

    成绩必须带齐发布任务快照和冻结的有效成绩策略：ADJUST 分支会逐项校验这些前置，缺一项就
    在真正的并发点之前先被 409 挡下——那样两个请求"一成功一失败"是假象，证明不了锁生效。
    """
    from app.models import (AaEffectiveGradePolicy, AaGradeRecheck, AaGradeTask, AaTerm,
                            AcademicGrade, AcademicStudent, StudentProfile)

    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED",
                  is_current=True)
    db.add(term)
    db.flush()
    db.add(AaEffectiveGradePolicy(
        tenant_id=TID, policy_code="RC_POLICY", policy_version=1,
        attempt_strategy="LATEST_ATTEMPT", effective_from_term_id=term.id,
        active_scope_key=str(term.id), status="ACTIVE",
    ))
    db.flush()
    profile = StudentProfile(tenant_id=TID, student_no="RC2401", real_name="复查甲",
                             grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    acad = AcademicStudent(tenant_id=TID, student_id=profile.id, student_no="RC2401",
                           name="复查甲", class_name="软件2401")
    db.add(acad)
    db.flush()
    task = AaGradeTask(tenant_id=TID, term_id=term.id, course_id=1, pass_line=60,
                       status="PUBLISHED")
    db.add(task)
    db.flush()
    grade = AcademicGrade(
        tenant_id=TID, acad_student_id=acad.id, course_name="高等数学",
        course_id=1, course_code="RC_MATH", course_version=1, attempt_no=1,
        grade_task_id=task.id, pass_line_snapshot=60,
        effective_policy_code="RC_POLICY", effective_policy_version=1,
        effective_attempt_strategy="LATEST_ATTEMPT",
        credit_value=4, score=60, pass_status="PASSED", source="PUBLISH", record_status="ACTIVE",
    )
    db.add(grade)
    db.flush()
    recheck = AaGradeRecheck(
        tenant_id=TID, student_id=profile.id, student_no="RC2401", student_name="复查甲",
        acad_grade_id=grade.id, course_name="高等数学", original_score=60,
        reason="卷面分与登记分不一致", status="SUBMITTED",
    )
    db.add(recheck)
    db.flush()
    return {"recheck": recheck.id, "grade": grade.id, "student": profile.id}


@pytest.fixture()
def recheck_svc(db_mode):
    _ctx()
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as svc

    return svc


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_second_review_after_first_gets_409(recheck_svc, db_mode):
    """串行下第二次审批必须 409，而不是把已处理的申请再处理一遍。"""
    from app.core.exceptions import AppException

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"userId": "1", "currentRoleCode": "ACADEMIC_ADMIN"}
    first = recheck_svc.review(user, ids["recheck"], "REJECT", note="卷面复核无误，不予调整")
    assert first["status"] == "REJECTED"

    with pytest.raises(AppException) as exc:
        recheck_svc.review(user, ids["recheck"], "ADJUST", new_score=75)
    assert exc.value.http_status == 409
    assert exc.value.code == "APPROVAL_VERSION_CONFLICT"

    # 正式成绩必须一个字节没动
    from app.models import AcademicGrade
    db = _session()
    grade = db.get(AcademicGrade, ids["grade"])
    assert int(grade.score) == 60 and grade.record_status == "ACTIVE"
    db.close()


def test_adjust_actually_succeeds_serially(recheck_svc, db_mode):
    """先证明种子是真的：单独走 ADJUST 必须成功并真的换出新版本正式成绩。

    没有这条，后面并发用例里"一个失败"可能只是因为 ADJUST 本来就跑不通，锁生效与否根本没被验证。
    """
    from app.models import AcademicGrade

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"userId": "1", "currentRoleCode": "ACADEMIC_ADMIN"}
    result = recheck_svc.review(user, ids["recheck"], "ADJUST", note="卷面复核后调整", new_score=75)
    assert result["status"] == "ADJUSTED"

    db = _session()
    old = db.get(AcademicGrade, ids["grade"])
    assert old.record_status == "SUPERSEDED", "原成绩没有退位"
    active = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == TID, AcademicGrade.course_code == "RC_MATH",
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False)).all()
    assert len(active) == 1 and int(active[0].score) == 75
    assert active[0].source == "RECHECK" and int(active[0].source_biz_id) == int(ids["recheck"])
    db.close()


def _race(ids, actions):
    """两个线程同时对同一条复查申请下不同结论，返回 (成功列表, 失败列表)。"""
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as svc

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(len(actions))
    user = {"userId": "1", "currentRoleCode": "ACADEMIC_ADMIN"}

    def _run(action, score):
        _ctx()
        try:
            barrier.wait(timeout=30)
            result = svc.review(user, ids["recheck"], action, note="复核结论说明足够长", new_score=score)
            with lock:
                ok.append((action, result["status"]))
        except AppException as exc:
            with lock:
                failed.append((action, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001  其它异常也要记录，静默吞掉会让并发问题看起来通过
            with lock:
                failed.append((action, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(a, s)) for a, s in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    return ok, failed


def _assert_single_truth(ids, ok, failed):
    from app.models import AaGradeRecheck, AcademicGrade

    assert len(ok) == 1, f"两个审批都成功了，结论出现双真值：成功={ok} 失败={failed}"
    assert len(failed) == 1, f"另一个请求没有被稳定拒绝：{failed}"
    status, code = failed[0][1], failed[0][2]
    assert status == 409, f"另一个请求应稳定 409，实际 {failed[0]}"
    assert code == "APPROVAL_VERSION_CONFLICT", f"错误码不对：{failed[0]}"

    db = _session()
    row = db.get(AaGradeRecheck, ids["recheck"])
    assert row.status != "SUBMITTED", "申请仍停在 SUBMITTED，说明成功的那次没落库"
    # 该学生该课程只能有一条 ACTIVE 正式成绩
    active = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == TID,
        AcademicGrade.course_code == "RC_MATH",
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False)).all()
    assert len(active) == 1, f"出现 {len(active)} 条 ACTIVE 正式成绩"

    # 审批结论与正式成绩必须自洽：驳回/维持就不能改分，调整就必须改分
    grade = active[0]
    if row.status in ("REJECTED", "UPHELD"):
        assert int(grade.score) == 60, (
            f"申请结论是 {row.status}，正式成绩却被改成 {grade.score}——回执与成绩自相矛盾")
    else:
        assert row.status == "ADJUSTED", f"未预期的终态 {row.status}"
    db.close()


def test_concurrent_reject_vs_adjust_yields_one_truth(recheck_svc, db_mode):
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()
    ok, failed = _race(ids, [("REJECT", None), ("ADJUST", 75)])
    _assert_single_truth(ids, ok, failed)


def test_concurrent_uphold_vs_adjust_yields_one_truth(recheck_svc, db_mode):
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()
    ok, failed = _race(ids, [("UPHOLD", None), ("ADJUST", 80)])
    _assert_single_truth(ids, ok, failed)


def test_concurrent_two_adjusts_yield_one_truth(recheck_svc, db_mode):
    """两个都要改分：只能有一个生效，不能出现 75 和 80 各写一次。"""
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()
    ok, failed = _race(ids, [("ADJUST", 75), ("ADJUST", 80)])
    _assert_single_truth(ids, ok, failed)


def test_review_locks_the_application_row_before_reading_status():
    """申请行必须先加锁再判状态；退回无锁 db.get 就等于这条守卫没生效。"""
    import inspect

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as svc

    source = inspect.getsource(svc.review)
    head = source.split('act =')[0]
    assert "with_for_update()" in head, "申请行读取没有加锁"
    assert "db.get(AaGradeRecheck" not in head, "仍在用无锁 db.get 读取申请行"
    # 锁顺序：申请 → 成绩，不得反向
    assert source.index("AaGradeRecheck.id ==") < source.index("AcademicGrade.id ==")
