"""毕业设计 · 第1批：列表/统计/导出批次口径一致；非法 batchId→422。

覆盖：开题统计不再 NameError；两批次互不混合；开题/成果/题目列表与统计一致；
综合统计只统计指定批次；答辩列表与导出一致；非法 batchId 返回 422。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_BATCH = "/api/v1/graduation/batches"
PROP = "/api/v1/graduation/proposals"
FINAL = "/api/v1/graduation/finals"
DG = "/api/v1/graduation/defense-groups"
STATS = "/api/v1/graduation/gd-stats"
DASH = "/api/v1/graduation/dashboard"
STU = "/api/v1/students"
MAIN = 1000000000000000001


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(client, h, no=None):
    body = {
        "batchName": _uniq("批次"),
        "batchNo": no or _uniq("GD-B1"),
        "gradeYear": "2026届",
        "plannedCount": 50,
    }
    r = client.post(GD_BATCH, headers=h, json=body).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _student(client, h, no=None, name=None):
    sno = no or _uniq("S")
    r = client.post(STU, headers=h, json={
        "studentNo": sno, "realName": name or f"学生{sno[-4:]}",
    }).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _record(client, h, sid, batch_id):
    r = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": batch_id}).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _insert_proposal(gid, status="PENDING_REVIEW"):
    from app.db.session import get_sessionmaker
    from app.models import GraduationProposal, GraduationStudent
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        assert stu is not None
        p = GraduationProposal(
            tenant_id=stu.tenant_id, gd_student_id=stu.id, version="v1",
            is_resubmit=False, submit_at=datetime.now(timezone.utc),
            background="背景", plan="方案", outcome="成果",
            attachments_json=[], status=status,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return str(p.id)
    finally:
        db.close()


def _insert_final(gid, status="PENDING_REVIEW", plagiarism_rate=None):
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationStudent
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        assert stu is not None
        f = GraduationFinal(
            tenant_id=stu.tenant_id, gd_student_id=stu.id, version="v1",
            submit_at=datetime.now(timezone.utc),
            final_type="初稿", attachments_json=[], status=status,
            plagiarism_rate=plagiarism_rate,
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        return str(f.id)
    finally:
        db.close()


def _status_count(stats, status):
    return next((x["count"] for x in stats.get("byStatus", []) if x["status"] == status), 0)


def test_illegal_batch_id_returns_422(client, auth_headers, db_mode):
    """非法 batchId 不得落入 service 导致 500；须为校验失败（HTTP 422 或业务码 422001）。"""
    h = auth_headers

    def _assert_validation(r, path):
        assert r.status_code != 500, (path, r.text)
        body = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
        ok = (
            r.status_code == 422
            or body.get("code") == 422001
            or body.get("bizCode") == "VALIDATION_ERROR"
        )
        assert ok, (path, r.status_code, body)

    for path in (
        f"{PROP}/stats",
        f"{FINAL}/stats",
        f"{GD_TOPIC}/stats",
        f"{GD_TOPIC}/category-stats",
        f"{STATS}/overview",
        f"{STATS}/college-comparison",
        DASH,
    ):
        _assert_validation(client.get(path, headers=h, params={"batchId": "abc"}), path)
    _assert_validation(
        client.post(f"{DG}/export", headers=h, params={"batchId": "abc"}),
        f"{DG}/export",
    )


def test_proposal_stats_no_error_and_matches_list(client, auth_headers, db_mode):
    """开题统计接口可用；列表页签数量与统计一致；两批次互不混合。"""
    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    g1 = _record(client, h, _student(client, h, name="开题批次甲"), b1)
    g2 = _record(client, h, _student(client, h, name="开题批次乙"), b2)
    _insert_proposal(g1, "PENDING_REVIEW")
    _insert_proposal(g2, "APPROVED")

    # 统计不再因未定义 batch_id 报错
    st1 = client.get(f"{PROP}/stats", headers=h, params={"batchId": b1}).json()
    assert st1["code"] == 0, st1
    assert st1["data"]["batchId"] == str(b1)
    assert _status_count(st1["data"], "PENDING_REVIEW") >= 1
    assert _status_count(st1["data"], "APPROVED") == 0

    st2 = client.get(f"{PROP}/stats", headers=h, params={"batchId": b2}).json()
    assert st2["code"] == 0
    assert _status_count(st2["data"], "APPROVED") >= 1
    assert _status_count(st2["data"], "PENDING_REVIEW") == 0

    lst1 = client.get(PROP, headers=h, params={"batchId": b1, "status": "PENDING_REVIEW"}).json()
    assert lst1["code"] == 0
    assert lst1["data"]["total"] == _status_count(st1["data"], "PENDING_REVIEW")


def test_final_stats_matches_list_and_batch_isolated(client, auth_headers, db_mode):
    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    g1 = _record(client, h, _student(client, h, name="成果批次甲"), b1)
    g2 = _record(client, h, _student(client, h, name="成果批次乙"), b2)
    _insert_final(g1, "PENDING_REVIEW", plagiarism_rate="35%")
    _insert_final(g2, "APPROVED", plagiarism_rate="10%")

    st1 = client.get(f"{FINAL}/stats", headers=h, params={"batchId": b1}).json()
    assert st1["code"] == 0, st1
    assert st1["data"]["plagiarismOver"] >= 1
    assert _status_count(st1["data"], "PENDING_REVIEW") >= 1
    assert _status_count(st1["data"], "APPROVED") == 0

    lst1 = client.get(FINAL, headers=h, params={"batchId": b1, "status": "PENDING_REVIEW"}).json()
    assert lst1["data"]["total"] == _status_count(st1["data"], "PENDING_REVIEW")

    st2 = client.get(f"{FINAL}/stats", headers=h, params={"batchId": b2}).json()
    assert _status_count(st2["data"], "APPROVED") >= 1
    assert st2["data"]["plagiarismOver"] == 0


def test_topic_stats_matches_list(client, auth_headers, db_mode):
    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    for i, bid in enumerate((b1, b1, b2)):
        r = client.post(GD_TOPIC, headers=h, json={
            "title": _uniq(f"题{i}"), "sourceType": "TEACHER", "advisorName": "王老师",
            "batchId": bid, "capacity": 1, "category": "软件" if i < 2 else "硬件",
        }).json()
        assert r["code"] == 0, r

    lst = client.get(GD_TOPIC, headers=h, params={"batchId": b1, "pageSize": 100}).json()
    st = client.get(f"{GD_TOPIC}/stats", headers=h, params={"batchId": b1}).json()
    assert lst["code"] == 0 and st["code"] == 0
    # 列表可能含已归档过滤差异；未归档口径与 stats.total 对齐
    assert st["data"]["total"] == lst["data"]["total"]
    assert st["data"]["batchId"] == str(b1)

    cat = client.get(f"{GD_TOPIC}/category-stats", headers=h, params={"batchId": b1}).json()
    assert cat["code"] == 0
    assert sum(x["count"] for x in cat["data"]) == st["data"]["total"]


def test_overview_and_college_only_current_batch(client, auth_headers, db_mode):
    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    _record(client, h, _student(client, h, name="总览甲1"), b1)
    _record(client, h, _student(client, h, name="总览甲2"), b1)
    _record(client, h, _student(client, h, name="总览乙"), b2)

    ov1 = client.get(f"{STATS}/overview", headers=h, params={"batchId": b1}).json()
    ov2 = client.get(f"{STATS}/overview", headers=h, params={"batchId": b2}).json()
    assert ov1["code"] == 0 and ov2["code"] == 0
    assert ov1["data"]["batchId"] == str(b1)
    assert ov1["data"]["studentTotal"] == 2
    assert ov2["data"]["studentTotal"] == 1

    col = client.get(f"{STATS}/college-comparison", headers=h, params={"batchId": b1}).json()
    assert col["code"] == 0
    assert sum(x["total"] for x in col["data"]) == 2


def test_defense_list_export_same_batch(client, auth_headers, db_mode):
    """答辩列表与导出同批次口径（直接挂学生到组，绕过阶段门禁）。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationDefenseGroup, GraduationStudent

    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    g1 = _record(client, h, _student(client, h, name="答辩甲"), b1)
    g2 = _record(client, h, _student(client, h, name="答辩乙"), b2)

    d1 = client.post(DG, headers=h, json={
        "groupName": _uniq("一组"), "batchId": b1, "chair": "组长A", "members": ["评委1"], "secretary": "秘书A",
    }).json()
    assert d1["code"] == 0, d1
    d2 = client.post(DG, headers=h, json={
        "groupName": _uniq("二组"), "batchId": b2, "chair": "组长B", "members": ["评委2"], "secretary": "秘书B",
    }).json()
    assert d2["code"] == 0, d2
    id1, id2 = d1["data"]["id"], d2["data"]["id"]

    db = get_sessionmaker()()
    try:
        for gid, dgid in ((g1, id1), (g2, id2)):
            stu = db.get(GraduationStudent, int(gid))
            grp = db.get(GraduationDefenseGroup, int(dgid))
            stu.stage = "FINAL_CHECK"
            stu.defense_group_id = grp.id
            stu.defense_group = grp.group_name
            grp.student_count = 1
        db.commit()
    finally:
        db.close()

    lst = client.get(DG, headers=h, params={"batchId": b1, "pageSize": 100}).json()
    assert lst["code"] == 0
    ids = {x["id"] for x in lst["data"]["items"]}
    assert id1 in ids
    assert id2 not in ids

    exp = client.post(f"{DG}/export", headers=h, params={"batchId": b1}).json()
    assert exp["code"] == 0, exp
    assert exp["data"]["rowCount"] == lst["data"]["total"]
    assert exp["data"].get("batchId") == str(b1)


def test_dashboard_batch_scoped_counts(client, auth_headers, db_mode):
    h = auth_headers
    b1 = _batch(client, h)
    b2 = _batch(client, h)
    g1 = _record(client, h, _student(client, h, name="看板甲"), b1)
    g2 = _record(client, h, _student(client, h, name="看板乙"), b2)
    _insert_proposal(g1, "PENDING_REVIEW")
    _insert_proposal(g2, "PENDING_REVIEW")

    d1 = client.get(DASH, headers=h, params={"batchId": b1}).json()
    assert d1["code"] == 0, d1
    assert d1["data"]["batchId"] == str(b1)
    prop_stat = next(s for s in d1["data"]["stats"] if s["label"] == "开题待审阅")
    stu_stat = next(s for s in d1["data"]["stats"] if s["label"] == "毕设学生")
    assert int(stu_stat["value"]) == 1
    assert int(prop_stat["value"]) == 1
    t2 = next(t for t in d1["data"]["todos"] if t["id"] == "t1")
    assert t2["count"] == 1
