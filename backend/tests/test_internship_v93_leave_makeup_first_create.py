"""请假与补卡的首次创建并发（V93-09 / 总册 §9、§11）。

这两条是学生端最高频的写操作，而且是这批实体里唯一**既没有 DB 唯一约束、也没有
`SELECT ... FOR UPDATE`** 的：`apply()` 用一条普通查询看有没有 PENDING，没有就 INSERT。
两个请求在同一瞬间都查到「没有」，于是各建一条——学生双击或网络重试就能造出两条待审批
请假，教师队列里出现两条同一个人的申请，批了一条另一条还挂着。

对照组：变更申请、知情同意、特殊备案、学生自评都带了 FOR UPDATE，周报等三张表还有 DB
唯一约束（见 `test_internship_v93_first_create_no_500.py` 的实测结论）。请假和补卡是漏的。

不变量（总册 §9）：同一学生同一时刻只能有一条活动申请；输家只允许拿到同一份幂等结果
或 409，不能是 500，更不能双双成功。

真实 MySQL（db_mode 夹具）：SQLite 不会以同样方式暴露这个窗口。
"""
from __future__ import annotations

import threading
import uuid
from datetime import date, timedelta

import pytest

TID = 1000000000000000001


def _ctx(student_no=None):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": "1", "tenantId": str(TID), "realName": "学生甲",
               "userType": "STUDENT", "currentRoleCode": "STUDENT",
               "activeContextId": "ctx"}
    if student_no:
        payload["studentNo"] = student_no
    set_current_user(payload)


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db):
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="V93请假批次",
                            batch_no=f"IXL-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()
    student_no = f"IXL{uuid.uuid4().hex[:8]}"
    profile = StudentProfile(tenant_id=TID, student_no=student_no, real_name="请假甲",
                             grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    record = InternshipRecord(tenant_id=TID, student_id=profile.id, batch_id=batch.id,
                             status="ONBOARD")
    db.add(record)
    db.flush()
    return {"batch": batch.id, "internship": record.id,
            "student": profile.id, "studentNo": student_no}


def _leave_body(ids):
    start = date.today() + timedelta(days=3)
    return {
        "batchId": str(ids["batch"]),
        "internshipId": str(ids["internship"]),
        "leaveType": "PERSONAL",
        "startDate": start.isoformat(),
        "endDate": start.isoformat(),
        "reason": "家中有事需请假一天，已与企业师傅口头报备。",
    }


def _run_concurrent(fn, count=2):
    """两个线程在同一时刻发起同一个请求，收集成功与失败。"""
    from app.core.exceptions import AppException

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(count)

    def _worker(seq):
        try:
            barrier.wait(timeout=30)
            fn(seq)
            with lock:
                ok.append(seq)
        except AppException as exc:
            with lock:
                failed.append((seq, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 未接住的异常正是要抓的
            with lock:
                failed.append((seq, 500, repr(exc)[:160]))

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    return ok, failed


@pytest.fixture()
def leave_svc(db_mode):
    from app.modules.internship.services import internship_leave_service as svc

    return svc


def test_serial_leave_apply_works(leave_svc, db_mode):
    """先证明种子是真的：串行申请一次必须落库。

    没有这条，「并发只落一条」可能只是因为申请本来就走不通。
    """
    from app.models import InternshipLeave

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _ctx(ids["studentNo"])
    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}
    leave_svc.apply(user, _leave_body(ids))

    db = _session()
    try:
        rows = db.query(InternshipLeave).filter(
            InternshipLeave.tenant_id == TID,
            InternshipLeave.internship_id == ids["internship"],
            InternshipLeave.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_second_leave_blocked_while_one_pending(leave_svc, db_mode):
    """串行情况下的既有规则：已有待审批时再申请必须被挡。

    这条本来就该是绿的，用来锚定「同时只能有一条活动申请」确实是产品意图，
    而不是我在并发用例里自己发明的不变量。
    """
    from app.core.exceptions import AppException
    from app.models import InternshipLeave

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _ctx(ids["studentNo"])
    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}
    leave_svc.apply(user, _leave_body(ids))
    with pytest.raises(AppException) as exc:
        leave_svc.apply(user, _leave_body(ids))
    assert exc.value.http_status == 409

    db = _session()
    try:
        rows = db.query(InternshipLeave).filter(
            InternshipLeave.tenant_id == TID,
            InternshipLeave.internship_id == ids["internship"],
            InternshipLeave.status == "PENDING",
            InternshipLeave.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_concurrent_leave_apply_creates_only_one_pending(leave_svc, db_mode):
    """学生双击/重试：同一时刻两次申请，只能留下一条待审批。

    `apply()` 用无锁 SELECT 查 PENDING 再 INSERT，两个请求可以同时查到「没有」。
    落两条的后果是教师队列里出现同一个人的两条申请，批了一条另一条还挂着。
    """
    from app.models import InternshipLeave

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}

    def _apply(_seq):
        _ctx(ids["studentNo"])
        from app.modules.internship.services import internship_leave_service as svc
        svc.apply(user, _leave_body(ids))

    ok, failed = _run_concurrent(_apply)

    db = _session()
    try:
        rows = db.query(InternshipLeave).filter(
            InternshipLeave.tenant_id == TID,
            InternshipLeave.internship_id == ids["internship"],
            InternshipLeave.status == "PENDING",
            InternshipLeave.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, (
        f"并发申请落了 {len(rows)} 条待审批请假，教师队列会出现重复申请："
        f"成功={ok} 失败={failed}")
    for seq, status, detail in failed:
        assert status != 500, f"并发输家拿到 500：seq={seq} {detail}"
        assert status == 409, f"输家应稳定 409，实际 {status} {detail}"


def test_concurrent_makeup_apply_creates_only_one(db_mode):
    """补卡同型：同一天并发申请两次，只能留下一条活动申请。

    补卡与请假是这批实体里仅有的两个既无 DB 唯一约束、也无 FOR UPDATE 的写入口。
    """
    from app.models import InternshipMakeup

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}
    target_day = (date.today() - timedelta(days=1)).isoformat()

    def _apply(_seq):
        _ctx(ids["studentNo"])
        from app.modules.internship.services import internship_makeup_service as svc
        # apply() 收关键字参数而不是 body 字典；MISSING 类型不强制凭证（只有
        # OUT_OF_RANGE 才要），所以这条能真正走到落库那一步。
        svc.apply(user, checkin_date=target_day,
                  reason="当日在客户现场作业，手机无信号未能打卡。",
                  makeup_type="MISSING",
                  internship_id=str(ids["internship"]))

    ok, failed = _run_concurrent(_apply)

    db = _session()
    try:
        rows = db.query(InternshipMakeup).filter(
            InternshipMakeup.tenant_id == TID,
            InternshipMakeup.internship_id == ids["internship"],
            InternshipMakeup.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) <= 1, (
        f"同一天并发补卡落了 {len(rows)} 条：成功={ok} 失败={failed}")
    for seq, status, detail in failed:
        assert status != 500, f"并发输家拿到 500：seq={seq} {detail}"
