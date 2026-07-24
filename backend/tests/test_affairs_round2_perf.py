"""第二轮学工：风险列表/统计性能实测（真实 MySQL，报告实测毫秒，不伪造达标）。

默认插入 PERF_N=10000 条；可用环境变量 AFFAIRS_R2_PERF_N 覆盖（如 100000）。
门槛参考：列表 P95≤800ms、统计随列表一并返回。默认 1 万仅记录实测；
当 AFFAIRS_R2_PERF_N>=100000 时，P95 超过 800ms 必须失败。
"""
from __future__ import annotations

import os
import statistics
import time

import pytest

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
PERF_N = int(os.environ.get("AFFAIRS_R2_PERF_N", "10000"))
ROUNDS = 5


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_perf(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, SchoolClass, StudentProfile

    db = get_sessionmaker()()
    try:
        cls = SchoolClass(
            tenant_id=TID, major_id=1, class_name="性能压测班", grade="2025", status="ACTIVE"
        )
        db.add(cls)
        db.flush()
        # 复用少量学生，降低学生表膨胀；风险 UK 靠 source_ref_id
        students = [
            StudentProfile(
                tenant_id=TID,
                student_no=f"PERF{i:04d}",
                real_name=f"压测{i:04d}",
                class_id=cls.id,
                current_stage="ORIENTATION",
                student_status="NORMAL",
                status="ACTIVE",
            )
            for i in range(1, 51)
        ]
        db.add_all(students)
        db.flush()
        sids = [s.id for s in students]
        batch = []
        for i in range(1, PERF_N + 1):
            batch.append(
                AffairsRiskRecord(
                    tenant_id=TID,
                    student_id=sids[(i - 1) % len(sids)],
                    source="MANUAL",
                    source_ref_id=8_000_000 + i,
                    risk_level="HIGH" if i % 20 == 0 else "MEDIUM",
                    title=f"压测风险{i}",
                    detail="性能压测明细不少于五字",
                    status="NEW" if i % 7 else "CLOSED",
                )
            )
            if len(batch) >= 2000:
                db.add_all(batch)
                db.flush()
                batch.clear()
        if batch:
            db.add_all(batch)
        db.commit()
    finally:
        db.close()
    return PERF_N


@pytest.mark.slow
def test_risk_list_perf_report(client, db_mode, capsys):
    n = _seed_perf(db_mode)
    hdr = _hdr(client, "school_admin01")
    # warmup
    warm = client.get(f"{BASE}/risk/records", headers=hdr, params={"page": 1, "pageSize": 50})
    assert warm.status_code == 200
    assert warm.json()["data"]["total"] >= n

    list_ms = []
    for _ in range(ROUNDS):
        t0 = time.perf_counter()
        r = client.get(f"{BASE}/risk/records", headers=hdr, params={"page": 1, "pageSize": 50})
        list_ms.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["total"] >= n
        assert "stats" in body and body["stats"]["total"] == body["total"]

    p95 = sorted(list_ms)[max(0, int(len(list_ms) * 0.95) - 1)]
    mean = statistics.mean(list_ms)
    hard_target = n >= 100_000
    print(
        f"\n[R2-PERF] n={n} rounds={ROUNDS} list_ms={['%.1f' % x for x in list_ms]} "
        f"mean={mean:.1f}ms p95≈{p95:.1f}ms target_p95=800ms "
        f"{'HARD_PASS' if hard_target and p95 <= 800 else ('HARD_FAIL' if hard_target else ('PASS_HINT' if p95 <= 800 else 'BELOW_TARGET_REPORTED'))}"
    )
    if hard_target:
        assert p95 <= 800, f"10万级风险列表 P95 超标: {p95:.1f}ms n={n}"
    else:
        assert p95 < 10_000, f"风险列表异常缓慢 p95={p95:.1f}ms n={n}"
