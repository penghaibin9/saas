"""首次创建并发下的错误码合同（V93-08 / 总册 §9）。

周报、过程报告、安全课程完成三张表都已经带了 DB 唯一约束——这是好底子，防住了重复行。
但三个 service 都是「SELECT 查重 → 没有就 INSERT」，谁也没有接住 `IntegrityError`。
并发或网络重试时，输家撞上唯一约束，异常会一路冒到接口层变成 **500**。

总册 §9 的硬规则：输家只允许拿到「同一份幂等结果」或 **409**，绝不能是 500。
这不是洁癖——学生端看到 500 会以为系统坏了继续重试，而 409 才能让客户端知道
「已经交过了」。安全教育完成尤其要紧，它是合规链上的前置。

真实 MySQL（db_mode 夹具）：SQLite 不会以同样方式触发唯一约束竞争。
"""
from __future__ import annotations

import threading
import uuid

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
    """一个 RUNNING 批次 + 一条在岗记录，让学生写操作能真正走到落库那一步。"""
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="V93首创批次",
                            batch_no=f"IXF-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()
    student_no = f"IXF{uuid.uuid4().hex[:8]}"
    profile = StudentProfile(tenant_id=TID, student_no=student_no, real_name="首创甲",
                             grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    record = InternshipRecord(tenant_id=TID, student_id=profile.id, batch_id=batch.id,
                             status="ONBOARD")
    db.add(record)
    db.flush()
    return {"batch": batch.id, "internship": record.id, "studentNo": student_no}


@pytest.fixture()
def report_svc(db_mode):
    from app.modules.internship.services import (
        internship_student_report_context_service as svc)

    return svc


def _weekly_body(ids, week=1):
    return {
        "batchId": str(ids["batch"]),
        "internshipId": str(ids["internship"]),
        "weekNo": week,
        # submit_weekly 强制要求 expectedVersion；首次创建时当前版本为 0。
        # 两个并发请求都会带 0，这正是「两台设备同时提交同一周」的真实形态。
        "expectedVersion": 0,
        "workContent": "本周在岗完成装配线巡检与记录，累计四十小时。",
        "harvestContent": "熟悉了工位安全规程与异常上报流程，能独立处理常见告警。",
        "planContent": "下周计划跟随师傅学习设备保养。",
    }


def test_serial_weekly_submit_works(report_svc, db_mode):
    """先证明种子是真的：串行提交一次必须成功落库。

    没有这条，后面「并发只有一条」可能只是因为提交本来就跑不通。
    """
    from app.models import WeeklyReport

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _ctx(ids["studentNo"])
    report_svc.submit_weekly(
        {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"},
        _weekly_body(ids))

    db = _session()
    try:
        rows = db.query(WeeklyReport).filter(
            WeeklyReport.tenant_id == TID,
            WeeklyReport.internship_id == ids["internship"],
            WeeklyReport.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_concurrent_weekly_submit_never_returns_500(report_svc, db_mode):
    """同一周并发提交两次：只能落一条，且输家不许是 500。

    这是总册 §9 的错误码合同。唯一约束已经防住了重复行，本用例盯的是**输家看到什么**——
    未接住的 IntegrityError 会变成 500，学生端会当成系统故障继续重试。
    """
    from app.core.exceptions import AppException
    from app.models import WeeklyReport

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}
    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _run(seq):
        _ctx(ids["studentNo"])
        from app.modules.internship.services import (
            internship_student_report_context_service as svc)
        try:
            barrier.wait(timeout=30)
            svc.submit_weekly(user, _weekly_body(ids))
            with lock:
                ok.append(seq)
        except AppException as exc:
            with lock:
                failed.append((seq, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 未接住的异常正是本用例要抓的东西
            with lock:
                failed.append((seq, 500, repr(exc)[:160]))

    threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    db = _session()
    try:
        rows = db.query(WeeklyReport).filter(
            WeeklyReport.tenant_id == TID,
            WeeklyReport.internship_id == ids["internship"],
            WeeklyReport.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, f"同一周落了 {len(rows)} 条周报：成功={ok} 失败={failed}"
    for seq, status, detail in failed:
        assert status != 500, (
            f"并发输家拿到了 500 而不是业务冲突，学生端会当成系统故障：seq={seq} {detail}")
        assert status == 409, f"输家应稳定 409，实际 {status} {detail}"


def test_concurrent_self_eval_creates_exactly_one_row(db_mode):
    """自评首次创建并发：一条实习记录只能有一条自评。

    `InternshipStudentEval` 上没有任何唯一约束，service 是「SELECT ... FOR UPDATE → 没有就
    INSERT」。对**尚不存在的行**加 FOR UPDATE 到底挡不挡得住并发插入，取决于 InnoDB 在当前
    隔离级别下会不会对索引区间加间隙锁——这必须实测，不能靠推断。

    如果本用例红：说明没有 DB 约束兜底，需要补 UNIQUE(tenant_id, internship_id)。
    如果本用例绿：说明间隙锁确实挡住了，那就把这条留作回归锁，防止以后有人改动取数方式
    （比如把 FOR UPDATE 去掉、或换成先查后插的无锁读）时悄悄退化。
    """
    from app.core.exceptions import AppException
    from app.models import InternshipStudentEval

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    user = {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"}
    body = {
        "batchId": str(ids["batch"]),
        "internshipId": str(ids["internship"]),
        "selfSummary": "实习期间完成岗位轮训，掌握基本操作规程，无违规记录，收获良好。",
    }
    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _run(seq):
        _ctx(ids["studentNo"])
        from app.modules.internship.services import internship_student_eval_service as svc
        try:
            barrier.wait(timeout=30)
            svc.student_submit(user, dict(body))
            with lock:
                ok.append(seq)
        except AppException as exc:
            with lock:
                failed.append((seq, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001
            with lock:
                failed.append((seq, 500, repr(exc)[:160]))

    threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    db = _session()
    try:
        rows = db.query(InternshipStudentEval).filter(
            InternshipStudentEval.tenant_id == TID,
            InternshipStudentEval.internship_id == ids["internship"],
            InternshipStudentEval.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, (
        f"一条实习记录落了 {len(rows)} 条自评：成功={ok} 失败={failed}")
    for seq, status, detail in failed:
        assert status != 500, f"并发输家拿到 500：seq={seq} {detail}"
