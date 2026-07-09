"""岗位实习中心 · 实习学生测试（MySQL 真库 via db_mode）：建档 + 学生-岗位分配闭环
（allocated_count 收口）+ 满员/黑名单/未上架拒绝 + 调岗/退岗 + 状态机 + 资格 + 去向 + 统计 + 导入。"""
from __future__ import annotations

ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"


def _company(client, h, cc, name="实习学生测试企业"):
    cid = client.post(ENT, headers=h, json={"name": name, "creditCode": cc}).json()["data"]["id"]
    client.post(f"{ENT}/{cid}/review", headers=h, json={"action": "APPROVE"})  # → 合作中
    return cid


def _position(client, h, cid, headcount=2, title="前端实习岗位", publish=True):
    pid = client.post(POS, headers=h, json={"companyId": cid, "title": title,
                                            "headcount": headcount}).json()["data"]["id"]
    if publish:
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    return pid


def _student(client, h, no, name="测试学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]


def _record(client, h, sid):
    return client.post(IST, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_create_and_list(client, auth_headers, db_mode):
    sid = _student(client, auth_headers, "S-IST-001")
    r = client.post(IST, headers=auth_headers, json={"studentId": sid}).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["status"] == "PREPARING" and d["eligibilityStatus"] == "PENDING"
    assert d["destinationType"] == "NONE" and d["positionId"] == ""
    lst = client.get(IST, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    # 同学生重复建档(同批次空)拒绝
    assert client.post(IST, headers=auth_headers, json={"studentId": sid}).json()["code"] != 0


def test_assign_updates_allocated_count(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTA001X")
    pid = _position(client, auth_headers, cid, headcount=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-010"))
    a = client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()
    assert a["code"] == 0
    assert a["data"]["positionId"] == pid and a["data"]["destinationType"] == "ASSIGNED"
    assert a["data"]["enterpriseName"] and a["data"]["positionName"]
    # 岗位库 allocated_count 真实回填 + 已分配学生列表
    pd = client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]
    assert pd["allocatedCount"] == 1 and pd["assignedCount"] == 1
    assert pd["assignedStudents"][0]["studentNo"] == "S-IST-010"


def test_assign_full_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTF001X")
    pid = _position(client, auth_headers, cid, headcount=1)
    r1 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-020"))
    assert client.post(f"{IST}/{r1}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] == 0
    # 岗位满员 → 状态 FULL；第二人分配被拒
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["status"] == "FULL"
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-021"))
    assert client.post(f"{IST}/{r2}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_assign_non_published_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTN001X")
    pid = _position(client, auth_headers, cid, publish=False)  # 草稿
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-030"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_assign_blacklist_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTB001X")
    pid = _position(client, auth_headers, cid)
    client.post(f"{ENT}/{cid}/blacklist", headers=auth_headers, json={"on": True, "reason": "多次违规拖欠"})
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-040"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_reassign_moves_allocation(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTR001X")
    p1 = _position(client, auth_headers, cid, title="岗位一")
    p2 = _position(client, auth_headers, cid, title="岗位二")
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-050"))
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p1})
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p2})  # 调岗
    assert client.get(f"{POS}/{p1}", headers=auth_headers).json()["data"]["allocatedCount"] == 0
    assert client.get(f"{POS}/{p2}", headers=auth_headers).json()["data"]["allocatedCount"] == 1


def test_unassign_releases(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTU001X")
    pid = _position(client, auth_headers, cid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-060"))
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid})
    u = client.post(f"{IST}/{rid}/unassign", headers=auth_headers, json={"reason": "岗位调整"}).json()
    assert u["code"] == 0 and u["data"]["positionId"] == "" and u["data"]["destinationType"] == "NONE"
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["allocatedCount"] == 0


def test_status_machine(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTS001X")
    pid = _position(client, auth_headers, cid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-070"))
    # 未合格不能待上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={"status": "QUALIFIED"})
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["data"]["status"] == "READY"
    # 未分配岗位不能上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid})
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["data"]["status"] == "ONBOARD"
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ASSESS"}).json()["data"]["status"] == "ASSESSING"
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ARCHIVE"}).json()["data"]["status"] == "ARCHIVED"
    # 已归档不可编辑
    assert client.put(f"{IST}/{rid}", headers=auth_headers, json={"remark": "x"}).json()["code"] != 0


def test_destination(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-080"))
    d = client.post(f"{IST}/{rid}/destination", headers=auth_headers, json={"destination": "SELF_ARRANGED"}).json()
    assert d["code"] == 0 and d["data"]["destinationType"] == "SELF_ARRANGED"
    # 已分配岗位则不能直接改去向
    cid = _company(client, auth_headers, "91310000ISTD001X")
    pid = _position(client, auth_headers, cid)
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-081"))
    client.post(f"{IST}/{r2}/assign", headers=auth_headers, json={"positionId": pid})
    assert client.post(f"{IST}/{r2}/destination", headers=auth_headers, json={"destination": "EXEMPTED"}).json()["code"] != 0


def test_stats_and_export(client, auth_headers, db_mode):
    _record(client, auth_headers, _student(client, auth_headers, "S-IST-090"))
    s = client.get(f"{IST}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1
    assert any(x["status"] == "PREPARING" for x in s["data"]["byStatus"])
    ex = client.post(f"{IST}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and "姓名" in ex["data"]["content"] and ex["data"]["rowCount"] >= 1


def test_import(client, auth_headers, db_mode):
    _student(client, auth_headers, "S-IST-100", "导入学生甲")
    rows = [{"studentNo": "S-IST-100"}, {"studentNo": ""}, {"studentNo": "S-NOEXIST"}]
    dry = client.post(f"{IST}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 2
    assert client.post(f"{IST}/import/confirm", headers=auth_headers, json={"rows": rows}).json()["code"] != 0
    ok = client.post(f"{IST}/import/confirm", headers=auth_headers, json={"rows": [rows[0]]}).json()
    assert ok["code"] == 0 and ok["data"]["created"] == 1
