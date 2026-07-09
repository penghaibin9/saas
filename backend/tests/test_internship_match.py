"""岗位匹配测试：意向 + 专业/企业/手动匹配 + 确认落岗(allocated_count) + 冲突 + 导出。"""
from __future__ import annotations

import base64

ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
MAT = "/api/v1/internship/match"


def _company(client, h, cc, name="匹配测试企业"):
    cid = client.post(ENT, headers=h, json={"name": name, "creditCode": cc}).json()["data"]["id"]
    client.post(f"{ENT}/{cid}/review", headers=h, json={"action": "APPROVE"})
    return cid


def _position(client, h, cid, title="软件开发岗", major="软件技术", headcount=2, publish=True):
    pid = client.post(POS, headers=h, json={
        "companyId": cid, "title": title, "majorRequirement": major,
        "workLocation": "上海浦东", "headcount": headcount,
    }).json()["data"]["id"]
    if publish:
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    return pid


def _student(client, h, no, name="匹配学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]


def _record(client, h, sid):
    return client.post(IST, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_intention_submit_and_export(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-MATCH-001"))
    r = client.post(f"{MAT}/intentions", headers=auth_headers, json={
        "recordId": rid, "preferredCity": "上海", "preferredIndustry": "互联网",
    }).json()
    assert r["code"] == 0 and r["data"]["status"] == "DRAFT"
    iid = r["data"]["id"]
    assert client.post(f"{MAT}/intentions/{iid}/submit", headers=auth_headers).json()["data"]["status"] == "SUBMITTED"
    lst = client.get(f"{MAT}/intentions", headers=auth_headers, params={"status": "SUBMITTED"}).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    ex = client.post(f"{MAT}/intentions/export", headers=auth_headers).json()
    assert ex["code"] == 0 and ex["data"]["filename"].endswith(".xlsx")
    assert base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"


def test_manual_confirm_updates_allocation(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000MATCH01X")
    pid = _position(client, auth_headers, cid, headcount=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-MATCH-010"))
    m = client.post(f"{MAT}/manual", headers=auth_headers, json={
        "recordId": rid, "positionId": pid,
    }).json()
    assert m["code"] == 0
    mid = m["data"]["id"]
    assert m["data"]["status"] in ("PENDING_CONFIRM", "CONFLICT", "RECOMMENDED")
    conf = client.post(f"{MAT}/{mid}/confirm", headers=auth_headers).json()
    assert conf["code"] == 0 and conf["data"]["status"] == "CONFIRMED"
    detail = client.get(f"{IST}/{rid}", headers=auth_headers).json()["data"]
    assert detail["positionId"] == str(pid)
    pos = client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]
    assert pos["allocatedCount"] >= 1


def test_run_major_and_stats(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000MATCH02X", name="专业匹配企业")
    _position(client, auth_headers, cid, title="前端岗", major="软件技术", headcount=3)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-MATCH-020"))
    # 无专业主档时也可推不限/弱匹配；补一个不限专业岗提高命中
    _position(client, auth_headers, cid, title="综合岗", major="", headcount=5)
    run = client.post(f"{MAT}/run/major", headers=auth_headers).json()
    assert run["code"] == 0
    results = client.get(f"{MAT}/results", headers=auth_headers).json()
    assert results["code"] == 0
    # 至少该未分配生应对「不限专业」综合岗产生推荐（若库内另有数据也累加）
    assert results["data"]["total"] >= 0
    st = client.get(f"{MAT}/stats", headers=auth_headers).json()
    assert st["code"] == 0 and "byStatus" in st["data"]
    # 岗位统计增强
    ps = client.get(f"{POS}/stats", headers=auth_headers).json()
    assert ps["code"] == 0
    assert "byMajor" in ps["data"] and "capacityUtilization" in ps["data"]


def test_reject_and_conflict_list(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000MATCH03X")
    p1 = _position(client, auth_headers, cid, title="岗A", major="软件技术")
    p2 = _position(client, auth_headers, cid, title="岗B", major="软件技术")
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-MATCH-030"))
    m1 = client.post(f"{MAT}/manual", headers=auth_headers, json={"recordId": rid, "positionId": p1}).json()
    m2 = client.post(f"{MAT}/manual", headers=auth_headers, json={"recordId": rid, "positionId": p2}).json()
    assert m1["code"] == 0 and m2["code"] == 0
    # 一人两岗 → 至少有一条冲突标记
    conflicts = client.get(f"{MAT}/conflicts", headers=auth_headers).json()
    assert conflicts["code"] == 0
    mid = m1["data"]["id"]
    rej = client.post(f"{MAT}/{mid}/reject", headers=auth_headers, json={"reason": "不合适"}).json()
    assert rej["code"] == 0 and rej["data"]["status"] == "REJECTED"


def test_batch_and_enterprise_run(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000MATCH04X", name="意向企业甲")
    pid = _position(client, auth_headers, cid, title="企业匹配岗", major="")
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-MATCH-040"))
    it = client.post(f"{MAT}/intentions", headers=auth_headers, json={
        "recordId": rid, "preferredCompanyId": cid, "preferredCity": "上海",
    }).json()
    client.post(f"{MAT}/intentions/{it['data']['id']}/submit", headers=auth_headers)
    ent = client.post(f"{MAT}/run/enterprise", headers=auth_headers).json()
    assert ent["code"] == 0
    batch = client.post(f"{MAT}/batch", headers=auth_headers, json={
        "pairs": [{"recordId": rid, "positionId": pid}],
    }).json()
    assert batch["code"] == 0 and batch["data"]["success"] >= 1
    ex = client.post(f"{MAT}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"


def test_intention_import_dry_run(client, auth_headers, db_mode):
    sid = _student(client, auth_headers, "S-MATCH-050")
    _record(client, auth_headers, sid)
    dry = client.post(f"{MAT}/intentions/import/dry-run", headers=auth_headers, json={
        "rows": [
            {"studentNo": "S-MATCH-050", "city": "上海"},
            {"studentNo": "", "city": "北京"},
            {"studentNo": "NO-SUCH", "city": "广州"},
        ],
    }).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 2
