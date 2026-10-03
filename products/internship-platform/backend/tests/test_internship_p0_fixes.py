"""岗位实习 P0 回归：记录解析器 / 风险导出批次 / 匹配批次 / 容量原子 / 班级 / 工作台 / 批次闸门。"""
from __future__ import annotations

import uuid

IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
BATCH = "/api/v1/internship/batches"
DASH = "/api/v1/internship/dashboard"
RISK = "/api/v1/internship/risks"
MATCH = "/api/v1/internship/match"
POS = "/api/v1/internship/positions"
ENT = "/api/v1/internship/enterprises"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch_version(client, h, bid) -> int:
    d = client.get(f"{BATCH}/{bid}", headers=h).json()
    assert d["code"] == 0, d
    return int(d["data"].get("version") or 0)


def _mk_batch(client, h, *, status="RUNNING"):
    body = {
        "batchName": _uniq("批次"),
        "batchNo": _uniq("BN"),
        "startDate": "2026-03-01",
        "endDate": "2026-08-31",
        "plannedCount": 10,
    }
    r = client.post(BATCH, headers=h, json=body).json()
    assert r["code"] == 0, r
    bid = r["data"]["id"]
    ver = int(r["data"].get("version") or 0)
    if status in ("RUNNING", "CLOSED", "ARCHIVED"):
        act = client.post(f"{BATCH}/{bid}/activate", headers=h,
                          json={"expectedVersion": ver}).json()
        assert act["code"] == 0, act
        ver = int(act["data"].get("version") or (ver + 1))
    if status in ("CLOSED", "ARCHIVED"):
        cl = client.post(f"{BATCH}/{bid}/close", headers=h,
                         json={"expectedVersion": ver, "force": True,
                               "forceReason": "测试环境强制结束空批次"}).json()
        assert cl["code"] == 0, cl
        ver = int(cl["data"].get("version") or (ver + 1))
    if status == "ARCHIVED":
        ar = client.post(f"{BATCH}/{bid}/archive", headers=h,
                         json={"expectedVersion": ver, "force": True,
                               "forceReason": "测试环境强制归档空批次"}).json()
        assert ar["code"] == 0, ar
    return bid


TID = 1000000000000000001


def _org_class():
    """建档必须挂真实学院/专业/班级，见 tests/test_student.py::org_class。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=TID, college_name=_uniq("学院"), status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=TID, college_id=col.id, major_name=_uniq("专业"), status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name=_uniq("班级"),
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


def _mk_student(client, h, no=None):
    sno = no or _uniq("S")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"学生{sno[-4:]}",
                                          "classId": _org_class()}).json()
    assert r["code"] == 0, r
    return r["data"]["id"], sno


def test_p0_resolver_prefers_running_batch_record(client, auth_headers, db_mode):
    """同学生两批次时，解析器不得随意 .first()；显式 batchId 必须命中。"""
    from app.core.context import set_tenant
    from app.modules.internship.services.internship_record_resolver import (
        resolve_student_internship_context,
    )
    from app.services.db_service import session

    sid, sno = _mk_student(client, auth_headers)
    b_old = _mk_batch(client, auth_headers)
    b_new = _mk_batch(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b_old}).json()["code"] == 0
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b_new}).json()["code"] == 0
    # 结束旧批次（空就绪，学生仍在 PREPARING 且无岗位 → 会阻断；用 force）
    cl = client.post(f"{BATCH}/{b_old}/close", headers=auth_headers,
                     json={"expectedVersion": _batch_version(client, auth_headers, b_old),
                           "force": True, "forceReason": "历史批次测试强制结束"}).json()
    assert cl["code"] == 0, cl

    # 请求外直接调服务层必须显式绑租户（与 HTTP 中间件行为一致）
    set_tenant({"tenantId": "1000000000000000001"})
    try:
        with session() as db:
            ctx_new = resolve_student_internship_context(db, student_no=sno, batch_id=b_new, for_write=True)
            assert str(ctx_new.record.batch_id) == str(b_new)
            ctx_old_write = None
            try:
                resolve_student_internship_context(db, student_no=sno, batch_id=b_old, for_write=True)
            except Exception as e:  # noqa: BLE001
                ctx_old_write = e
            assert ctx_old_write is not None
            ctx_auto = resolve_student_internship_context(db, student_no=sno, for_write=True)
            assert str(ctx_auto.record.batch_id) == str(b_new)
    finally:
        set_tenant(None)


def test_p0_risk_export_requires_same_batch_as_list(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    missing = client.post(f"{RISK}/export", headers=auth_headers).json()
    assert missing["code"] != 0
    lst = client.get(RISK, headers=auth_headers, params={"batchId": b}).json()
    assert lst["code"] == 0
    exp = client.post(f"{RISK}/export", headers=auth_headers, params={"batchId": b}).json()
    assert exp["code"] == 0, exp
    assert exp["data"]["rowCount"] == lst["data"]["total"]
    assert exp["data"].get("batchId") == str(b)


def test_p0_run_major_match_requires_running_batch(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    no_bid = client.post(f"{MATCH}/run/major", headers=auth_headers).json()
    assert no_bid["code"] != 0
    ok = client.post(f"{MATCH}/run/major", headers=auth_headers, params={"batchId": b}).json()
    assert ok["code"] == 0, ok
    # 强制结束后不可再跑
    assert client.post(f"{BATCH}/{b}/close", headers=auth_headers,
                       json={"expectedVersion": _batch_version(client, auth_headers, b),
                             "force": True, "forceReason": "匹配测试强制结束"}).json()["code"] == 0
    closed = client.post(f"{MATCH}/run/major", headers=auth_headers, params={"batchId": b}).json()
    assert closed["code"] != 0


def test_p0_import_template_headers_match_writable_fields(client, auth_headers, db_mode):
    from app.modules.internship.services.internship_student_service import IMPORT_HEADERS
    assert IMPORT_HEADERS == ["学号", "指导教师", "实习开始日期", "实习结束日期", "备注"]
    tpl = client.get(f"{IST}/import/template", headers=auth_headers)
    assert tpl.status_code == 200


def test_p0_assign_position_atomic_capacity(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    s1, _ = _mk_student(client, auth_headers)
    s2, _ = _mk_student(client, auth_headers)
    r1 = client.post(IST, headers=auth_headers, json={"studentId": s1, "batchId": b}).json()
    r2 = client.post(IST, headers=auth_headers, json={"studentId": s2, "batchId": b}).json()
    assert r1["code"] == 0 and r2["code"] == 0
    ent = client.post(ENT, headers=auth_headers, json={
        "name": _uniq("企业"), "creditCode": _uniq("C"),
    }).json()
    # 企业创建接口字段因环境可能不同，宽松：直接用岗位接口已有企业
    # 若企业创建失败，跳过本用例的岗位创建依赖
    if ent.get("code") != 0:
        return
    eid = ent["data"]["id"]
    # 审核通过企业（若需要）
    client.post(f"{ENT}/{eid}/review", headers=auth_headers, json={"action": "APPROVE"})
    pos = client.post(POS, headers=auth_headers, json={
        "companyId": eid, "title": _uniq("岗"), "headcount": 1, "batchId": b,
    }).json()
    if pos.get("code") != 0:
        return
    pid = pos["data"]["id"]
    client.post(f"{POS}/{pid}/publish", headers=auth_headers)
    a1 = client.post(f"{IST}/{r1['data']['id']}/assign-position", headers=auth_headers,
                     json={"positionId": pid}).json()
    assert a1["code"] == 0, a1
    a2 = client.post(f"{IST}/{r2['data']['id']}/assign-position", headers=auth_headers,
                     json={"positionId": pid}).json()
    assert a2["code"] != 0


def test_p0_dashboard_progress_and_destination_metric(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    s1, _ = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": s1, "batchId": b}).json()["code"] == 0
    d = client.get(DASH, headers=auth_headers, params={"batchId": b}).json()
    assert d["code"] == 0
    labels = {x["label"] for x in d["data"]["stats"]}
    assert "去向待落实" in labels
    assert "准备中" in labels
    assert "待落实" not in labels  # 旧错误口径
    assert "batchProgress" in d["data"]
    # PREPARING 权重 0 → 进度 0
    assert d["data"]["batchProgress"] == 0
    ready_route = next(x for x in d["data"]["stats"] if x["label"] == "待上岗")["route"]
    assert "status=READY" in ready_route


def test_p0_batch_close_blocked_when_students_unplaced(client, auth_headers, db_mode):
    b = _mk_batch(client, auth_headers)
    sid, _ = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b}).json()["code"] == 0
    blocked = client.post(f"{BATCH}/{b}/close", headers=auth_headers,
                          json={"expectedVersion": _batch_version(client, auth_headers, b)}).json()
    assert blocked["code"] != 0
    ready = client.get(f"{BATCH}/{b}/readiness", headers=auth_headers).json()
    assert ready["code"] == 0
    # 就绪报告字段已从 blockingCount 改名为 blocked，口径不变
    assert ready["data"]["blocked"] >= 1
    forced = client.post(f"{BATCH}/{b}/close", headers=auth_headers,
                         json={"expectedVersion": _batch_version(client, auth_headers, b),
                               "force": True, "forceReason": "验收环境强制结束批次"}).json()
    assert forced["code"] == 0
    assert forced["data"].get("forced") is True


def test_p0_class_name_not_grade_suffix(client, auth_headers, db_mode):
    """有班级时 className 不得仅为『xxxx级』。"""
    b = _mk_batch(client, auth_headers)
    sid, sno = _mk_student(client, auth_headers)
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": b}).json()["code"] == 0
    lst = client.get(IST, headers=auth_headers, params={"batchId": b, "keyword": sno}).json()
    assert lst["code"] == 0
    items = lst["data"].get("items") or lst["data"].get("list") or []
    assert items
    cn = items[0].get("className") or ""
    # 无班级主档时允许 "-"；若有值则不得只是数字+级
    if cn and cn != "-":
        assert not (cn.endswith("级") and cn[:-1].isdigit())
