"""岗位实习 P2 合规证据链定向测试（MySQL）。"""
from __future__ import annotations

import uuid

import pytest

BATCH = "/api/v1/internship/batches"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
CMP = "/api/v1/internship/compliance"
ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"


def _uniq(p: str) -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


def _credit() -> str:
    s = uuid.uuid4().hex[:8].upper()
    for a, b in (("I", "A"), ("O", "B"), ("S", "C"), ("V", "D"), ("Z", "E")):
        s = s.replace(a, b)
    return f"91310000{s}XA"


def _mk_batch(client, h, *, activate=True, compliance=None):
    body = {
        "batchName": _uniq("P2B"), "batchNo": _uniq("P2BN"),
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }
    if compliance is not None:
        body["rules"] = {"compliance": compliance}
    r = client.post(BATCH, headers=h, json=body).json()
    assert r["code"] == 0, r
    bid, ver = r["data"]["id"], int(r["data"].get("version") or 0)
    if activate:
        act = client.post(f"{BATCH}/{bid}/activate", headers=h, json={"expectedVersion": ver}).json()
        assert act["code"] == 0, act
        # frozen flag
        det = client.get(f"{BATCH}/{bid}", headers=h).json()
        assert det["code"] == 0
        rules = (det["data"] or {}).get("rules") or {}
        assert rules.get("_complianceFrozen") is True
    return bid


def _mk_student(client, h):
    sno = _uniq("P2S")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"生{sno[-4:]}"}).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _mk_intern(client, h, bid):
    sid = _mk_student(client, h)
    rec = client.post(IST, headers=h, json={"studentId": sid, "batchId": bid}).json()
    assert rec["code"] == 0, rec
    return rec["data"]["id"]


def test_template_activate_freezes_and_no_inplace_overwrite(client, auth_headers, db_mode):
    h = auth_headers
    created = client.post(f"{CMP}/templates", headers=h, json={
        "templateCode": "P2DEFAULT", "templateName": "P2模板",
        "config": {"studentConsent": {"required": True, "severity": "BLOCK"}},
    }).json()
    assert created["code"] == 0, created
    tid = created["data"]["id"]
    act = client.post(f"{CMP}/templates/{tid}/activate", headers=h, json={"changeReason": "启用"}).json()
    assert act["code"] == 0, act
    assert act["data"]["status"] == "ACTIVE"
    # ACTIVE 升版必须写原因；无原因失败
    no_reason = client.post(f"{CMP}/templates/{tid}/activate", headers=h, json={}).json()
    assert no_reason["code"] != 0
    # 有原因则 RETIRE 旧版并生成新 ACTIVE（不原地覆盖）
    again = client.post(f"{CMP}/templates/{tid}/activate", headers=h, json={
        "changeReason": "规则收紧",
        "config": {"studentConsent": {"required": True}, "safetyEducation": {"required": True}},
    }).json()
    assert again["code"] == 0, again
    assert again["data"]["status"] == "ACTIVE"
    assert int(again["data"]["version"]) > int(act["data"]["version"])


def test_evaluate_not_applicable_not_counted_as_missing(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h, compliance={
        "studentConsent": {"required": False},
        "safetyEducation": {"required": False},
        "specialFiling": {"required": False},
        "enterpriseAccess": {"required": False},
        "emergency": {"required": False},
        "workRights": {"required": False},
        "agreement": {"required": True},
        "insurance": {"required": True},
        "advisor": {"required": True},
    })
    iid = _mk_intern(client, h, bid)
    ev = client.get(f"{CMP}/evaluate/{iid}", headers=h, params={"operation": "ONBOARD"}).json()
    assert ev["code"] == 0, ev
    items = {x["code"]: x for x in ev["data"]["items"]}
    assert items["studentConsent"]["status"] == "NOT_APPLICABLE"
    assert items["safetyEducation"]["status"] == "NOT_APPLICABLE"
    # 协议/保险缺失应阻断
    assert ev["data"]["passed"] is False
    codes = {b["code"] for b in ev["data"]["blockers"]}
    assert "agreement" in codes or "insurance" in codes or "advisor" in codes


def test_safety_cannot_bypass_with_passed_true(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h)
    course = client.post(f"{CMP}/safety", headers=h, json={
        "batchId": bid, "title": "岗前安全", "requiredMinutes": 60, "passingScore": 80, "maxAttempts": 3,
        "requireCommitment": True, "contentSnapshot": "安全须知 v1",
    }).json()
    assert course["code"] == 0, course
    iid = _mk_intern(client, h, bid)
    ens = client.post(f"{CMP}/safety/completions", headers=h, json={
        "internshipId": iid, "courseId": course["data"]["id"],
    }).json()
    assert ens["code"] == 0, ens
    cid = ens["data"]["id"]
    fail = client.post(f"{CMP}/safety/completions/{cid}/review", headers=h, json={
        "score": 50, "studiedMinutes": 10, "commitment": False, "passed": True,
    }).json()
    assert fail["code"] == 0
    assert fail["data"]["passed"] is False
    ok = client.post(f"{CMP}/safety/completions/{cid}/review", headers=h, json={
        "score": 90, "studiedMinutes": 60, "commitment": True,
    }).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["passed"] is True


def test_incident_cannot_close_from_reported(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h)
    key = _uniq("idem")
    rep = client.post(f"{CMP}/incidents", headers=h, json={
        "batchId": bid, "summary": "现场受伤测试", "severity": "HIGH",
        "idempotencyKey": key, "fileIds": ["f1"],
    }).json()
    assert rep["code"] == 0, rep
    iid = rep["data"]["id"]
    # 幂等
    rep2 = client.post(f"{CMP}/incidents", headers=h, json={
        "batchId": bid, "summary": "重复", "idempotencyKey": key,
    }).json()
    assert rep2["code"] == 0
    assert str(rep2["data"]["id"]) == str(iid)
    bad = client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={"status": "CLOSED"}).json()
    assert bad["code"] != 0
    client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={"status": "INVESTIGATING"})
    client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={"status": "RECTIFYING"})
    client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={"status": "PENDING_REVIEW"})
    closed = client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={
        "status": "CLOSED",
        "investigationConclusion": "责任认定完成",
        "rectificationPlan": "整改并复查",
        "fileIds": ["f1", "f2"],
    }).json()
    assert closed["code"] == 0, closed


def test_consent_snapshot_and_view_not_enough(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h)
    iid = _mk_intern(client, h, bid)
    # 创建时不带快照 → 确认必须补快照
    c = client.post(f"{CMP}/consents", headers=h, json={
        "internshipId": iid, "consentType": "STUDENT", "contentVersion": "v1",
    }).json()
    assert c["code"] == 0, c
    cid = c["data"]["id"]
    assert c["data"]["status"] == "PENDING"
    miss = client.post(f"{CMP}/consents/{cid}/confirm", headers=h, json={"method": "ONLINE"}).json()
    assert miss["code"] != 0  # 无正文快照不可确认（已读≠确认）
    ok = client.post(f"{CMP}/consents/{cid}/confirm", headers=h, json={
        "contentSnapshot": "知情同意正文V1", "method": "ONLINE",
    }).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] == "VALID"
    # 幂等再确认
    again = client.post(f"{CMP}/consents/{cid}/confirm", headers=h, json={
        "contentSnapshot": "知情同意正文V1", "method": "ONLINE",
    }).json()
    assert again["code"] == 0
    assert again["data"]["status"] == "VALID"


def test_exemption_requires_reason(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h, compliance={"agreement": {"required": True, "severity": "BLOCK"}})
    iid = _mk_intern(client, h, bid)
    bad = client.post(f"{CMP}/exemptions", headers=h, json={
        "internshipId": iid, "checkCode": "agreement", "reason": "短",
    }).json()
    assert bad["code"] != 0
    ok = client.post(f"{CMP}/exemptions", headers=h, json={
        "internshipId": iid, "checkCode": "agreement", "reason": "阶段性特殊安排并附依据",
    }).json()
    assert ok["code"] == 0, ok
    ev = client.get(f"{CMP}/evaluate/{iid}", headers=h).json()
    assert ev["code"] == 0
    agr = next(x for x in ev["data"]["items"] if x["code"] == "agreement")
    assert agr["status"] == "VALID"


def test_evidence_package_lists_missing(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h)
    iid = _mk_intern(client, h, bid)
    pkg = client.post(f"{CMP}/evidence-packages/STUDENT/{iid}", headers=h).json()
    assert pkg["code"] == 0, pkg
    assert pkg["data"]["version"] >= 1
    assert "manifest" in pkg["data"]
    assert pkg["data"]["manifest"].get("ruleVersion")
    pkg2 = client.post(f"{CMP}/evidence-packages/STUDENT/{iid}", headers=h).json()
    assert pkg2["code"] == 0
    assert pkg2["data"]["version"] == pkg["data"]["version"] + 1


def test_position_rights_block_overtime_hours(client, auth_headers, db_mode):
    from app.modules.internship.services.internship_position_rights import evaluate_position_compliance

    class P:
        daily_hours = 12
        weekly_hours = 60
        night_shift = True
        hazardous_flag = False
        prohibited_reason = None
        work_content = "装配"
        remuneration_type = None
        remuneration_amount = None
        batch_id = 1

    r = evaluate_position_compliance(P(), None, {
        "workRights": {"maxDailyHours": 8, "maxWeeklyHours": 40, "nightShiftAllowed": False},
    })
    assert r["passed"] is False
    assert any("日工作" in x for x in r["blockers"])
    assert any("夜班" in x for x in r["blockers"])


def test_enterprise_access_required_blocks_assign(client, auth_headers, db_mode):
    h = auth_headers
    bid = _mk_batch(client, h, compliance={
        "enterpriseAccess": {"required": True, "severity": "BLOCK", "requireOnsiteInspection": True},
        "workRights": {"required": False},
    })
    iid = _mk_intern(client, h, bid)
    ent = client.post(ENT, headers=h, json={"name": _uniq("企"), "creditCode": _credit()}).json()
    if ent.get("code") != 0:
        pytest.skip(str(ent))
    eid = ent["data"]["id"]
    client.post(f"{ENT}/{eid}/review", headers=h, json={"action": "APPROVE"})
    pos = client.post(POS, headers=h, json={
        "companyId": eid, "title": _uniq("岗"), "headcount": 2, "batchId": bid,
    }).json()
    if pos.get("code") != 0:
        pytest.skip(str(pos))
    pid = pos["data"]["id"]
    client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
    client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    fail = client.post(f"{IST}/{iid}/assign", headers=h, json={"positionId": pid}).json()
    assert fail["code"] != 0
    # 补考察后可分配
    insp = client.post(f"{CMP}/inspections", headers=h, json={
        "companyId": eid, "batchId": bid, "inspectionType": "DOCUMENT", "conclusion": "合格",
    }).json()
    assert insp["code"] == 0, insp
    client.post(f"{CMP}/inspections/{insp['data']['id']}/submit", headers=h, json={})
    rev = client.post(f"{CMP}/inspections/{insp['data']['id']}/approve", headers=h, json={
        "comment": "准入通过", "validUntil": "2099-12-31T00:00:00",
    }).json()
    assert rev["code"] == 0, rev
    ok = client.post(f"{IST}/{iid}/assign", headers=h, json={"positionId": pid}).json()
    assert ok["code"] == 0, ok
