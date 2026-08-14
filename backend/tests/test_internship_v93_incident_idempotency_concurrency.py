"""实习事故上报幂等键并发回归（V93-03 / 总册 §10）。

`report_incident()` 用应用层「先 SELECT 查重、查不到再 INSERT」保证幂等，而
`InternshipIncident.idempotency_key` 原来只有普通索引，没有唯一约束。两个请求可以双双
穿过查重窗口各自 INSERT，而且事故不是普通业务行：severity 为 HIGH/CRITICAL 时还会派生
RiskRecord，每次上报都写审计。一次穿透同时造出重复事故、重复风险、重复审计三条假事实。

本项目其它幂等写入方早就带同款约束（uk_aa_status_change_idem / uk_campaign_tenant_idem /
uk_affairs_job_idem），岗位实习事故是唯一漏网的。

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


def _seed(db):
    """一条进行中的实习记录，供 HIGH 事故派生 RiskRecord 用。

    必须真的能派生风险：如果种子缺 internship_id，HIGH 分支根本不会走到，
    「没有重复风险」就成了因为压根没建过风险，证明不了任何东西。
    """
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="V93事故并发批次",
                            batch_no=f"IXB-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()
    profile = StudentProfile(tenant_id=TID, student_no=f"IX{uuid.uuid4().hex[:6]}",
                             real_name="事故甲", grade="2024",
                             student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    record = InternshipRecord(tenant_id=TID, student_id=profile.id, batch_id=batch.id,
                              status="ONBOARD")
    db.add(record)
    db.flush()
    return {"internship": record.id, "batch": batch.id, "student": profile.id}


@pytest.fixture()
def incident_svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_incident_service as svc

    return svc


def _body(ids, key, severity="HIGH"):
    return {
        "idempotencyKey": key,
        "internshipId": str(ids["internship"]),
        "summary": "学生在岗操作机床时左手被夹伤，已送医",
        "incidentType": "INJURY",
        "severity": severity,
    }


def _count_incidents(key):
    from app.models import InternshipIncident

    db = _session()
    try:
        return db.query(InternshipIncident).filter(
            InternshipIncident.tenant_id == TID,
            InternshipIncident.idempotency_key == key,
            InternshipIncident.is_deleted.is_(False)).all()
    finally:
        db.close()


def _count_risks(internship_id):
    from app.models import RiskRecord

    db = _session()
    try:
        return db.query(RiskRecord).filter(
            RiskRecord.tenant_id == TID,
            RiskRecord.internship_id == internship_id,
            RiskRecord.risk_code == "INT-INCIDENT",
            RiskRecord.is_deleted.is_(False)).all()
    finally:
        db.close()


def test_serial_retry_is_idempotent(incident_svc, db_mode):
    """先证明种子是真的：串行重复上报只落一条事故、一条风险，第二次是幂等回执。

    没有这条，后面并发用例里「只有一条」可能只是因为上报本来就失败了。
    """
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    key = f"IXK-{uuid.uuid4().hex[:12]}"
    first = incident_svc.report_incident(_body(ids, key))
    assert first.get("riskId"), "HIGH 事故没有派生风险，种子无效"

    second = incident_svc.report_incident(_body(ids, key))
    assert second.get("idempotent") is True
    assert second["id"] == first["id"]

    assert len(_count_incidents(key)) == 1
    assert len(_count_risks(ids["internship"])) == 1


def _race(ids, key, workers=2):
    """N 个线程同毫秒用同一幂等键上报同一起事故。"""
    from app.core.exceptions import AppException

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(workers)

    def _run(seq):
        _ctx()
        from app.modules.internship.services import internship_incident_service as svc
        try:
            barrier.wait(timeout=30)
            result = svc.report_incident(_body(ids, key))
            with lock:
                ok.append((seq, result))
        except AppException as exc:
            with lock:
                failed.append((seq, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 其它异常必须记录：静默吞掉会把 500 伪装成通过
            with lock:
                failed.append((seq, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    return ok, failed


def test_concurrent_same_key_creates_exactly_one_incident(incident_svc, db_mode):
    """两台手机同毫秒重复提交同一起事故：数据库里只能有一条事故、一条风险。

    这是总册 §9 的硬不变量——输家只能拿到同一份幂等结果或 409，绝不能是 500 IntegrityError，
    也绝不能造出第二条事故事实。
    """
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    key = f"IXK-{uuid.uuid4().hex[:12]}"
    ok, failed = _race(ids, key)

    # 输家不允许以 500 / 未处理异常的形式出现
    for seq, status, code in failed:
        assert status == 409, f"并发输家返回了非 409 的失败：seq={seq} status={status} code={code}"

    incidents = _count_incidents(key)
    assert len(incidents) == 1, (
        f"同一幂等键造出了 {len(incidents)} 条事故事实：成功={ok} 失败={failed}")

    risks = _count_risks(ids["internship"])
    assert len(risks) == 1, f"派生风险重复了 {len(risks)} 条：成功={ok} 失败={failed}"

    # 所有拿到成功回执的调用必须指向同一条事故，不能各说各话
    returned_ids = {result["id"] for _seq, result in ok}
    assert len(returned_ids) <= 1, f"并发调用返回了不同的事故 id：{returned_ids}"
    if ok:
        assert str(incidents[0].id) == next(iter(returned_ids))


def test_concurrent_burst_same_key_still_single_truth(incident_svc, db_mode):
    """网络重试风暴：5 个并发同键请求仍然只允许一条事故事实。"""
    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    key = f"IXK-{uuid.uuid4().hex[:12]}"
    ok, failed = _race(ids, key, workers=5)

    for seq, status, code in failed:
        assert status == 409, f"并发输家返回了非 409 的失败：seq={seq} status={status} code={code}"

    incidents = _count_incidents(key)
    assert len(incidents) == 1, (
        f"重试风暴造出了 {len(incidents)} 条事故事实：成功={ok} 失败={failed}")
    assert len(_count_risks(ids["internship"])) == 1
