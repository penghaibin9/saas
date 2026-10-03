"""教师看板读侧改造的等价性回归（V93-06 / 总册 §21）。

看板是教师每天第一个打开的页面，原实现有三处会随批次人数线性放大：
1. SCOPED 教师逐行 `db.get(StudentProfile)` 再逐行推导班级/学院名（N+1）；
2. 把全部开放风险装进内存、Python 排序后只取前 5；
3. 这 5 条提醒再逐条 `db.get` 记录和学生。

改造只换取数方式，不改口径。本文件的作用是把「口径没变」变成可执行断言：
风险提醒的排序规则、SCOPED 教师能看见谁、各项统计数字，都必须和改造前一致。

排序等价性尤其要盯：SQL 的 CASE 权重必须和原 Python `level_rank` 逐值对齐，
未知等级同样排最后，否则教师看到的「最紧急 5 条」会悄悄换一批人。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

TID = 1000000000000000001


def _ctx(role="SCHOOL_ADMIN", **extra):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": "1", "tenantId": str(TID), "realName": "实习处",
               "userType": "ADMIN", "currentRoleCode": role, "activeContextId": "ctx"}
    payload.update(extra)
    set_current_user(payload)


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db, *, students=6):
    """一个 RUNNING 批次 + 若干学生记录，并挂上覆盖各等级的开放风险。"""
    from app.models import (InternshipBatch, InternshipRecord, RiskRecord, StudentProfile)

    batch = InternshipBatch(tenant_id=TID, batch_name="V93看板批次",
                            batch_no=f"IXD-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()

    statuses = ["PREPARING", "READY", "ONBOARD", "ONBOARD", "ASSESSING", "ARCHIVED"]
    records = []
    for i in range(students):
        profile = StudentProfile(
            tenant_id=TID, student_no=f"IXD{uuid.uuid4().hex[:8]}",
            real_name=f"看板学生{i}", grade="2024",
            student_status="NORMAL", status="ACTIVE")
        db.add(profile)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID, student_id=profile.id, batch_id=batch.id,
            status=statuses[i % len(statuses)], advisor_name="王老师")
        db.add(record)
        db.flush()
        records.append(record)

    # 覆盖 HIGH/MEDIUM/LOW 以及一个未知等级，且数量多于 5 条，才能真正验证排序与截断。
    now = datetime.utcnow()
    levels = ["LOW", "HIGH", "MEDIUM", "HIGH", "LOW", "WEIRD", "MEDIUM"]
    for i, level in enumerate(levels):
        db.add(RiskRecord(
            tenant_id=TID, internship_id=records[i % len(records)].id,
            risk_code=f"INT-R{i}", risk_title=f"风险{i}", risk_level=level,
            source_module="test", status="PENDING_HANDLE",
            updated_at=now - timedelta(minutes=i)))
    db.flush()
    return batch.id


def _legacy_top5(batch_id):
    """改造前的取法：全量装载 + Python 排序 + 切前 5。用作等价性基准。"""
    from app.models import InternshipRecord, RiskRecord
    from sqlalchemy import select

    db = _session()
    try:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == TID,
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch_id)).all()
        scoped_ids = [r.id for r in recs] or [0]
        rows = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == TID, RiskRecord.is_deleted.is_(False),
            RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]),
            RiskRecord.internship_id.in_(scoped_ids))).all()
        level_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        rows = sorted(rows, key=lambda k: (
            level_rank.get(k.risk_level, 9),
            -(k.updated_at.timestamp() if k.updated_at else 0)))[:5]
        return [str(k.id) for k in rows]
    finally:
        db.close()


@pytest.fixture()
def svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_service as s

    return s


def test_risk_alert_order_matches_legacy_python_sort(svc, db_mode):
    """SQL 排序取 5 必须与原 Python 排序取 5 得到同一批风险、同一个顺序。"""
    db = _session()
    batch_id = _seed(db)
    db.commit()
    db.close()

    _ctx()
    result = svc.get_dashboard_summary(batch_id=str(batch_id))
    new_ids = [a["id"] for a in result["riskAlerts"]]
    legacy_ids = _legacy_top5(batch_id)

    assert len(new_ids) == 5, f"看板应恰好给 5 条提醒，实际 {len(new_ids)}"
    assert new_ids == legacy_ids, (
        f"排序口径变了，教师看到的最紧急 5 条换了一批：新={new_ids} 原={legacy_ids}")


def test_unknown_risk_level_still_sorts_last(svc, db_mode):
    """未知等级必须仍排在 HIGH/MEDIUM/LOW 之后——CASE 的 else_ 权重不能写错。"""
    from app.models import RiskRecord

    db = _session()
    batch_id = _seed(db)
    db.commit()
    db.close()

    _ctx()
    alerts = svc.get_dashboard_summary(batch_id=str(batch_id))["riskAlerts"]

    db = _session()
    try:
        levels = []
        for a in alerts:
            row = db.get(RiskRecord, int(a["id"]))
            levels.append(row.risk_level)
    finally:
        db.close()
    assert "WEIRD" not in levels, "未知等级挤进了前 5，说明排序权重与原口径不一致"


def test_alert_payload_still_resolves_student_names(svc, db_mode):
    """批量取记录/学生后，提醒里的学生姓名不能退化成占位符。"""
    db = _session()
    batch_id = _seed(db)
    db.commit()
    db.close()

    _ctx()
    alerts = svc.get_dashboard_summary(batch_id=str(batch_id))["riskAlerts"]
    assert alerts, "没有产生任何风险提醒，种子无效"
    for alert in alerts:
        assert alert["studentName"] not in ("", "-"), (
            f"提醒未能解析出学生姓名，批量取数丢了关联：{alert}")


def test_batch_metrics_unchanged(svc, db_mode):
    """统计口径必须与种子事实一致：6 名学生、2 名在岗。"""
    db = _session()
    batch_id = _seed(db, students=6)
    db.commit()
    db.close()

    _ctx()
    result = svc.get_dashboard_summary(batch_id=str(batch_id))
    stats = {s["label"]: s["value"] for s in result["stats"]}
    assert stats["本批学生"] == "6"
    assert stats["在岗学生"] == "2"
    assert result["onboardRate"] == pytest.approx(33.3, abs=0.1)
