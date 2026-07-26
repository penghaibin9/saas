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


def _org_class():
    """建档必须挂真实学院/专业/班级，见 tests/test_student.py::org_class。"""
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=1000000000000000001, college_name=_uniq("学院"), status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=1000000000000000001, college_id=col.id, major_name=_uniq("专业"), status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=1000000000000000001, major_id=maj.id, class_name=_uniq("班级"),
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


def _mk_student(client, h):
    sno = _uniq("P2S")
    r = client.post(STU, headers=h, json={"studentNo": sno, "realName": f"生{sno[-4:]}",
                                          "classId": _org_class()}).json()
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
    from app.core.security import create_access_token
    h = auth_headers
    bid = _mk_batch(client, h)
    course = client.post(f"{CMP}/safety", headers=h, json={
        "batchId": bid, "title": "岗前安全", "requiredMinutes": 60, "passingScore": 80, "maxAttempts": 3,
        "requireCommitment": True, "contentSnapshot": "安全须知 v1",
    }).json()
    assert course["code"] == 0, course
    course_id = course["data"]["id"]
    sno = _uniq("P2SAFE")
    sid = client.post(STU, headers=h, json={"studentNo": sno, "realName": "安全测试生",
                                            "classId": _org_class()}).json()["data"]["id"]
    rec = client.post(IST, headers=h, json={"studentId": sid, "batchId": bid}).json()
    assert rec["code"] == 0, rec
    stu_h = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "安全测试生", "userType": "STUDENT", "tid": "x",
        "tenantId": "1000000000000000001", "studentNo": sno,
        "currentRoleCode": "STUDENT", "clientType": "MP"})}
    # 教师只能审核学生已提交(PENDING_REVIEW)的学习记录，须先由学生开始+提交
    start = client.post(f"/api/v1/mobile/internship/safety/courses/{course_id}/start", headers=stu_h).json()
    assert start["code"] == 0, start
    cid = start["data"]["id"]
    # 学习时长按 started_at 到提交时的真实流逝时间"可信折算"，自动化用例瞬间跑完，
    # 把开始时间往回拨，让流逝时长真实满足 requiredMinutes=60，而不是伪造 studiedMinutes 字段
    from datetime import datetime, timedelta

    from app.db.session import get_sessionmaker
    from app.models import InternshipSafetyCompletion
    db = get_sessionmaker()()
    try:
        row = db.get(InternshipSafetyCompletion, int(cid))
        row.started_at = datetime.utcnow() - timedelta(minutes=70)
        db.commit()
    finally:
        db.close()
    submit = client.post(f"/api/v1/mobile/internship/safety/courses/{course_id}/submit", headers=stu_h,
                         json={"studiedMinutes": 10, "expectedVersion": 0}).json()
    assert submit["code"] == 0, submit
    fail = client.post(f"{CMP}/safety/completions/{cid}/review", headers=h, json={
        "score": 50, "studiedMinutes": 10, "commitment": False, "passed": True,
        "expectedVersion": submit["data"]["version"],
    }).json()
    assert fail["code"] == 0, fail
    assert fail["data"]["passed"] is False
    # 未通过可重新提交学习记录再审（maxAttempts=3 未超限）
    resubmit = client.post(f"/api/v1/mobile/internship/safety/courses/{course_id}/submit", headers=stu_h,
                           json={"studiedMinutes": 60, "expectedVersion": fail["data"]["version"]}).json()
    assert resubmit["code"] == 0, resubmit
    # 课程 requireCommitment=True：还须学生本人完成安全承诺，否则通过率永远算不出 True
    commit = client.post(f"/api/v1/mobile/internship/safety/completions/{cid}/commit", headers=stu_h,
                         json={"contentHash": "commitment-ack", "expectedVersion": resubmit["data"]["version"]}).json()
    assert commit["code"] == 0, commit
    ok = client.post(f"{CMP}/safety/completions/{cid}/review", headers=h, json={
        "score": 90, "studiedMinutes": 60, "commitment": True,
        "expectedVersion": commit["data"]["version"],
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
    bad = client.post(f"{CMP}/incidents/{iid}/transition", headers=h,
                      json={"status": "CLOSED", "expectedVersion": 0}).json()
    assert bad["code"] != 0
    # 每次流转都会把事故记录的乐观锁版本 +1，须逐次回传当前版本
    assert client.post(f"{CMP}/incidents/{iid}/transition", headers=h,
                       json={"status": "INVESTIGATING", "expectedVersion": 0}).json()["code"] == 0
    assert client.post(f"{CMP}/incidents/{iid}/transition", headers=h,
                       json={"status": "RECTIFYING", "expectedVersion": 1}).json()["code"] == 0
    assert client.post(f"{CMP}/incidents/{iid}/transition", headers=h,
                       json={"status": "PENDING_REVIEW", "expectedVersion": 2}).json()["code"] == 0
    closed = client.post(f"{CMP}/incidents/{iid}/transition", headers=h, json={
        "status": "CLOSED", "expectedVersion": 3,
        "investigationConclusion": "责任认定完成",
        "rectificationPlan": "整改并复查",
        "responsibilityConclusion": "企业现场安全管理不到位，已通报整改",
        "fileIds": ["f1", "f2"],
    }).json()
    assert closed["code"] == 0, closed


def test_consent_snapshot_and_view_not_enough(client, auth_headers, db_mode):
    from app.core.security import create_access_token
    h = auth_headers
    bid = _mk_batch(client, h)
    sno = _uniq("P2CONSENT")
    sid = client.post(STU, headers=h, json={"studentNo": sno, "realName": "知情确认生",
                                            "classId": _org_class()}).json()["data"]["id"]
    rec = client.post(IST, headers=h, json={"studentId": sid, "batchId": bid}).json()
    assert rec["code"] == 0, rec
    iid = rec["data"]["id"]
    stu_h = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "知情确认生", "userType": "STUDENT", "tid": "x",
        "tenantId": "1000000000000000001", "studentNo": sno,
        "currentRoleCode": "STUDENT", "clientType": "MP"})}
    # 创建时正文快照与正文版本必填（无正文的确认任务不再允许创建）
    missing_snapshot = client.post(f"{CMP}/consents", headers=h, json={
        "internshipId": iid, "consentType": "STUDENT", "contentVersion": "v1",
    }).json()
    assert missing_snapshot["code"] != 0
    c = client.post(f"{CMP}/consents", headers=h, json={
        "internshipId": iid, "consentType": "STUDENT",
        "contentVersion": "v1", "contentSnapshot": "知情同意正文V1",
    }).json()
    assert c["code"] == 0, c
    cid = c["data"]["id"]
    assert c["data"]["status"] == "PENDING"
    # 未先打开正文（viewed_at 为空）不可确认（已读≠确认）
    miss = client.post(f"/api/v1/mobile/internship/consents/{cid}/confirm", headers=stu_h, json={
        "expectedVersion": 0, "contentVersion": "v1",
    }).json()
    assert miss["code"] != 0
    viewed = client.post(f"/api/v1/mobile/internship/consents/{cid}/view", headers=stu_h).json()
    assert viewed["code"] == 0, viewed
    content_hash = viewed["data"]["contentHash"]
    ok = client.post(f"/api/v1/mobile/internship/consents/{cid}/confirm", headers=stu_h, json={
        "expectedVersion": viewed["data"]["version"], "contentVersion": "v1", "contentHash": content_hash,
    }).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] == "VALID"
    # 幂等再确认（已 VALID 直接返回，不重复处理）
    again = client.post(f"/api/v1/mobile/internship/consents/{cid}/confirm", headers=stu_h, json={
        "expectedVersion": ok["data"]["version"], "contentVersion": "v1", "contentHash": content_hash,
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
    import io
    up = client.post("/api/v1/files/upload", headers=h,
                     files={"file": ("exempt-evidence.txt", io.BytesIO(b"exemption basis"), "text/plain")},
                     data={"bizType": "ATTACHMENT"})
    fid = up.json()["data"]["fileId"]
    ok = client.post(f"{CMP}/exemptions", headers=h, json={
        "internshipId": iid, "checkCode": "agreement", "reason": "阶段性特殊安排并附依据",
        "validUntil": "2099-12-31T00:00:00", "evidenceFileIds": [fid],
    }).json()
    assert ok["code"] == 0, ok
    # 豁免申请默认 PENDING_REVIEW，须校级管理员审批通过才生效（BLOCK 级还须绑定依据文件）
    eid = ok["data"]["id"]
    approved = client.post(f"{CMP}/exemptions/{eid}/review", headers=h,
                           json={"action": "APPROVE", "expectedVersion": 0}).json()
    assert approved["code"] == 0, approved
    ev = client.get(f"{CMP}/evaluate/{iid}", headers=h).json()
    assert ev["code"] == 0
    agr = next(x for x in ev["data"]["items"] if x["code"] == "agreement")
    assert agr["status"] == "EXEMPTED"


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
    # 阻断原因文案已改为"每日工时超过规则上限"，语义不变
    assert any("每日工时" in x for x in r["blockers"])
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
        "workContent": "现场值守", "dailyHours": 8, "weeklyHours": 40, "nightShift": False,
        "overtimeAllowed": False, "restDaysPerWeek": 2, "remunerationType": "MONTHLY",
        "accommodationProvided": True, "mealProvided": True, "hazardousFlag": False,
        "remunerationAmount": 2000, "remunerationCycle": "MONTHLY",
    }).json()
    if pos.get("code") != 0:
        pytest.skip(str(pos))
    pid = pos["data"]["id"]
    client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
    client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    fail = client.post(f"{IST}/{iid}/assign", headers=h, json={"positionId": pid, "expectedVersion": 0}).json()
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
    ok = client.post(f"{IST}/{iid}/assign", headers=h, json={"positionId": pid, "expectedVersion": 0}).json()
    assert ok["code"] == 0, ok
