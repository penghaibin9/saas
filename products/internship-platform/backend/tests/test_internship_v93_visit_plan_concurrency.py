"""巡访计划状态机并发回归（V93-04 / 总册 §13）。

`transition()` 原来是「读 status → 校验 → 改字段 → version+1 → commit」，中间没有行锁也没有
版本条件。两个教师同时对同一份 PUBLISHED 计划下不同结论（一个 START、一个 CANCEL）时，双方
都读到 PUBLISHED、都通过白名单校验，各自 commit——后写的覆盖先写的，version 虽然自增却从来
没有人比对过它。计划最终状态取决于谁的事务晚提交，而不是谁先做的决定。

`update_visit_plan()` 有同样的窗口：两个教师同时编辑，后保存的静默吃掉前一个人的修改。

真实 MySQL 并发（db_mode 夹具）：SQLite 没有真正的并发写语义，压出来的绿是假的。
"""
from __future__ import annotations

import threading
import uuid

import pytest

TID = 1000000000000000001


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "realName": "实习处",
                      "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
                      "activeContextId": "ctx"})


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db, status="PUBLISHED"):
    from app.models import InternshipVisitPlan

    plan = InternshipVisitPlan(
        tenant_id=TID, objective=f"V93巡访计划-{uuid.uuid4().hex[:6]}",
        plan_type="VISIT", method="ONSITE", status=status,
        owner_name="张老师", version=0)
    db.add(plan)
    db.flush()
    return plan.id


@pytest.fixture()
def plan_svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_visit_plan_service as svc

    return svc


def _plan_row(pid):
    from app.models import InternshipVisitPlan

    db = _session()
    try:
        return db.get(InternshipVisitPlan, pid)
    finally:
        db.close()


def test_serial_transition_still_works(plan_svc, db_mode):
    """先证明种子是真的：串行 PUBLISHED→IN_PROGRESS 必须成功并真的落库。

    没有这条，后面并发用例里「只有一个成功」可能只是因为迁移本来就跑不通。
    """
    db = _session()
    pid = _seed(db)
    db.commit()
    db.close()

    result = plan_svc.transition(pid, "START")
    assert result["status"] == "IN_PROGRESS"
    assert _plan_row(pid).status == "IN_PROGRESS"


def test_stale_expected_version_is_rejected(plan_svc, db_mode):
    """客户端拿着过期版本来操作，必须 409，而不是照着旧视图改。"""
    from app.core.exceptions import AppException

    db = _session()
    pid = _seed(db)
    db.commit()
    db.close()

    plan_svc.transition(pid, "START")  # version 0 -> 1
    with pytest.raises(AppException) as exc:
        plan_svc.transition(pid, "COMPLETE", {"expectedVersion": 0})
    assert exc.value.http_status == 409
    assert _plan_row(pid).status == "IN_PROGRESS", "被拒绝的请求不该改动状态"


def _race(pid, actions):
    """多个线程同毫秒对同一份计划下不同结论。"""
    from app.core.exceptions import AppException

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(len(actions))

    def _run(action):
        _ctx()
        from app.modules.internship.services import internship_visit_plan_service as svc
        # 两个教师都是在 version=0 时打开的页面：这才是「同一份视图上的两个决定」。
        # 只靠 barrier 抢时序无法稳定复现——先跑完的那个提交后，后跑的会读到新版本，
        # 两次先后保存都成功本来就是正确行为，压不出真正要防的冲突。
        body = {"expectedVersion": 0}
        if action == "CANCEL":
            body["reason"] = "企业临时闭园，本次巡访取消"
        try:
            barrier.wait(timeout=30)
            result = svc.transition(pid, action, body)
            with lock:
                ok.append((action, result["status"]))
        except AppException as exc:
            with lock:
                failed.append((action, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 其它异常必须记录，静默吞掉会把 500 伪装成通过
            with lock:
                failed.append((action, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(a,)) for a in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    return ok, failed


def test_concurrent_start_and_cancel_single_winner(plan_svc, db_mode):
    """两个教师同毫秒 START / CANCEL 同一份计划：只能有一个赢，另一个稳定 409。

    这是总册 §13 的核心不变量：状态机不允许 last-write-wins。
    """
    db = _session()
    pid = _seed(db)
    db.commit()
    db.close()

    ok, failed = _race(pid, ["START", "CANCEL"])

    assert len(ok) == 1, f"两个迁移都成功了，状态机出现双真值：成功={ok} 失败={failed}"
    assert len(failed) == 1, f"另一个请求没有被稳定拒绝：{failed}"
    assert failed[0][1] == 409, f"输家应稳定 409，实际 {failed[0]}"

    row = _plan_row(pid)
    winner_status = ok[0][1]
    assert row.status == winner_status, (
        f"落库状态 {row.status} 与赢家回执 {winner_status} 不一致——回执和事实分叉了")
    assert row.status in ("IN_PROGRESS", "CANCELLED")
    # CANCEL 赢了才该有取消原因；START 赢了却留着取消原因说明两次写混在了一起
    if row.status == "IN_PROGRESS":
        assert not (row.cancel_reason or "").strip(), "START 赢了却写进了取消原因"
    assert int(row.version or 0) == 1, f"version 应恰好自增一次，实际 {row.version}"


def test_concurrent_same_action_only_one_applies(plan_svc, db_mode):
    """两个教师同时点同一个 START：一个成功一个 409，不能双双成功。"""
    db = _session()
    pid = _seed(db)
    db.commit()
    db.close()

    ok, failed = _race(pid, ["START", "START"])

    assert len(ok) == 1, f"同一迁移被执行了两次：成功={ok} 失败={failed}"
    assert failed and failed[0][1] == 409, f"输家应稳定 409，实际 {failed}"
    assert int(_plan_row(pid).version or 0) == 1


def test_concurrent_update_does_not_silently_overwrite(plan_svc, db_mode):
    """两个教师在同一版本上编辑同一份计划：后保存的不能静默吃掉前一个人的修改。"""
    from app.core.exceptions import AppException

    db = _session()
    pid = _seed(db, status="DRAFT")
    db.commit()
    db.close()

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _run(title):
        _ctx()
        from app.modules.internship.services import internship_visit_plan_service as svc
        try:
            barrier.wait(timeout=30)
            result = svc.update_visit_plan(pid, {"objective": title, "expectedVersion": 0})
            with lock:
                ok.append((title, result))
        except AppException as exc:
            with lock:
                failed.append((title, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001
            with lock:
                failed.append((title, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(t,))
               for t in ("甲老师改的巡访目标", "乙老师改的巡访目标")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert len(ok) == 1, f"两次编辑都成功了，后写覆盖了先写：成功={ok} 失败={failed}"
    assert failed and failed[0][1] == 409, f"输家应稳定 409，实际 {failed}"
    assert int(_plan_row(pid).version or 0) == 1
