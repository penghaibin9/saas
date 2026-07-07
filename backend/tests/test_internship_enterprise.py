"""岗位实习中心 · 企业库测试：CRUD + 信用码去重 + 审核状态机 + 合作启停 + 黑名单
+ 联系人/导师 + 统计 + 导入(dry-run/confirm) + 导出 + 脱敏 + 越权404。
共享企业主档 t_emp_company；全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

BASE = "/api/v1/internship/enterprises"


def _create(client, headers, **over):
    body = {"name": "测试科技有限公司", "creditCode": "91310000TEST0001XA",
            "industry": "软件", "region": "上海", "contactPerson": "王经理",
            "contactPhone": "13800001234", "source": "SELF_BUILT"}
    body.update(over)
    return client.post(BASE, headers=headers, json=body).json()


def test_create_and_list(client, auth_headers, db_mode):
    r = _create(client, auth_headers)
    assert r["code"] == 0
    assert r["data"]["coopStatus"] == "PENDING"
    assert r["data"]["qualificationStatus"] == "UNREVIEWED"
    lst = client.get(BASE, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    # 列表联系电话脱敏
    row = next(x for x in lst["data"]["items"] if x["id"] == r["data"]["id"])
    assert "****" in row["contactPhoneMasked"]


def test_credit_code_dedup(client, auth_headers, db_mode):
    assert _create(client, auth_headers, creditCode="91310000DUP00001XA")["code"] == 0
    dup = _create(client, auth_headers, name="另一家", creditCode="91310000DUP00001XA")
    assert dup["code"] != 0  # DATA_CONFLICT


def test_name_required(client, auth_headers, db_mode):
    r = client.post(BASE, headers=auth_headers, json={"name": ""}).json()
    assert r["code"] != 0


def test_review_state_machine(client, auth_headers, db_mode):
    cid = _create(client, auth_headers)["data"]["id"]
    # 待审核 → 通过 → 合作中 + 资质通过
    ap = client.post(f"{BASE}/{cid}/review", headers=auth_headers,
                     json={"action": "APPROVE", "comment": "资质齐全"}).json()
    assert ap["code"] == 0
    assert ap["data"]["coopStatus"] == "ACTIVE"
    assert ap["data"]["qualificationStatus"] == "PASSED"
    # 非法：已合作中不能再审核
    again = client.post(f"{BASE}/{cid}/review", headers=auth_headers,
                        json={"action": "APPROVE"}).json()
    assert again["code"] != 0


def test_review_reject(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000REJ00001XA")["data"]["id"]
    rj = client.post(f"{BASE}/{cid}/review", headers=auth_headers,
                     json={"action": "REJECT", "comment": "资质不符"}).json()
    assert rj["code"] == 0 and rj["data"]["coopStatus"] == "REJECTED"


def test_cooperation_suspend_resume_archive(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000COOP001XA")["data"]["id"]
    # 未审核直接暂停 → 非法
    assert client.post(f"{BASE}/{cid}/cooperation", headers=auth_headers,
                       json={"action": "SUSPEND"}).json()["code"] != 0
    client.post(f"{BASE}/{cid}/review", headers=auth_headers, json={"action": "APPROVE"})
    assert client.post(f"{BASE}/{cid}/cooperation", headers=auth_headers,
                       json={"action": "SUSPEND"}).json()["data"]["coopStatus"] == "SUSPENDED"
    assert client.post(f"{BASE}/{cid}/cooperation", headers=auth_headers,
                       json={"action": "RESUME"}).json()["data"]["coopStatus"] == "ACTIVE"
    assert client.post(f"{BASE}/{cid}/cooperation", headers=auth_headers,
                       json={"action": "ARCHIVE"}).json()["data"]["coopStatus"] == "ARCHIVED"


def test_blacklist(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000BLK00001XA")["data"]["id"]
    # 拉黑无原因 → 非法
    assert client.post(f"{BASE}/{cid}/blacklist", headers=auth_headers,
                       json={"on": True, "reason": ""}).json()["code"] != 0
    on = client.post(f"{BASE}/{cid}/blacklist", headers=auth_headers,
                     json={"on": True, "reason": "多次拖欠实习津贴"}).json()
    assert on["code"] == 0 and on["data"]["blacklist"] is True and on["data"]["coopStatus"] == "BLACKLIST"
    off = client.post(f"{BASE}/{cid}/blacklist", headers=auth_headers,
                      json={"on": False}).json()
    assert off["data"]["blacklist"] is False and off["data"]["coopStatus"] == "ACTIVE"


def test_contacts_crud_and_primary(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000CON00001XA")["data"]["id"]
    a = client.post(f"{BASE}/{cid}/contacts", headers=auth_headers,
                    json={"contactType": "MENTOR", "name": "李导师", "phone": "13900005678",
                          "isPrimary": True}).json()
    assert a["code"] == 0 and a["data"]["isPrimary"] is True
    assert "****" in a["data"]["phoneMasked"]  # 电话脱敏
    # 第二个设为主 → 第一个自动取消主
    b = client.post(f"{BASE}/{cid}/contacts", headers=auth_headers,
                    json={"contactType": "MENTOR", "name": "赵导师", "isPrimary": True}).json()
    lst = client.get(f"{BASE}/{cid}/contacts", headers=auth_headers).json()["data"]["items"]
    primaries = [x for x in lst if x["isPrimary"]]
    assert len(primaries) == 1 and primaries[0]["name"] == "赵导师"
    # 编辑
    up = client.put(f"{BASE}/{cid}/contacts/{a['data']['id']}", headers=auth_headers,
                    json={"title": "技术总监"}).json()
    assert up["code"] == 0 and up["data"]["title"] == "技术总监"
    # 删除
    dl = client.delete(f"{BASE}/{cid}/contacts/{a['data']['id']}", headers=auth_headers).json()
    assert dl["code"] == 0
    assert all(x["id"] != a["data"]["id"] for x in
               client.get(f"{BASE}/{cid}/contacts", headers=auth_headers).json()["data"]["items"])


def test_stats(client, auth_headers, db_mode):
    _create(client, auth_headers, creditCode="91310000STA00001XA")
    s = client.get(f"{BASE}/stats", headers=auth_headers).json()
    assert s["code"] == 0
    assert s["data"]["total"] >= 1
    assert any(x["status"] == "PENDING" for x in s["data"]["byCoopStatus"])


def test_import_dry_run_and_confirm(client, auth_headers, db_mode):
    rows = [{"name": "导入企业A", "creditCode": "91310000IMP0001XA", "industry": "制造"},
            {"name": "", "creditCode": "91310000IMP0002XA"}]  # 第二行缺名称
    dry = client.post(f"{BASE}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0
    assert dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 1
    # 含非法行 → 确认被拒
    assert client.post(f"{BASE}/import/confirm", headers=auth_headers,
                       json={"rows": rows}).json()["code"] != 0
    # 全通过 → 确认写入
    ok = client.post(f"{BASE}/import/confirm", headers=auth_headers,
                     json={"rows": [rows[0]]}).json()
    assert ok["code"] == 0 and ok["data"]["created"] == 1


def test_export_masked(client, auth_headers, db_mode):
    _create(client, auth_headers, creditCode="91310000EXP0001XA")
    ex = client.post(f"{BASE}/export", headers=auth_headers).json()
    assert ex["code"] == 0
    assert "企业名称" in ex["data"]["content"] and ex["data"]["rowCount"] >= 1
    # 导出不含完整手机号（脱敏）
    assert "13800001234" not in ex["data"]["content"]


def test_detail_and_not_found(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000DET0001XA")["data"]["id"]
    d = client.get(f"{BASE}/{cid}", headers=auth_headers).json()
    assert d["code"] == 0 and "contacts" in d["data"] and "auditTrail" in d["data"]
    nf = client.get(f"{BASE}/99999999", headers=auth_headers).json()
    assert nf["code"] != 0
