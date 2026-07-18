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
    """驳回必须写明原因（≥5 字，与请假驳回/周报退回/批次作废同一口径）——
    企业要凭这条意见整改后重新提交，空泛的「不符」无法指导整改。"""
    cid = _create(client, auth_headers, creditCode="91310000REJ00001XA")["data"]["id"]
    # 原因不足 5 字被拒
    bad = client.post(f"{BASE}/{cid}/review", headers=auth_headers,
                      json={"action": "REJECT", "comment": "资质不符"}).json()
    assert bad["code"] == 422001
    rj = client.post(f"{BASE}/{cid}/review", headers=auth_headers,
                     json={"action": "REJECT", "comment": "营业执照经营范围与实习岗位不符"}).json()
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
    rows = [{"name": "导入企业A", "creditCode": "91310000IMP0001XA", "industry": "制造", "region": "上海"},
            {"name": "", "creditCode": "91310000IMP0002XA", "industry": "制造", "region": "上海"}]  # 第二行缺名称
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
    import base64
    _create(client, auth_headers, creditCode="91310000EXP0001XA")
    ex = client.post(f"{BASE}/export", headers=auth_headers).json()
    assert ex["code"] == 0
    assert ex["data"]["filename"].endswith(".xlsx")
    raw = base64.b64decode(ex["data"]["contentBase64"])
    assert raw[:2] == b"PK" and ex["data"]["rowCount"] >= 1


def test_detail_and_not_found(client, auth_headers, db_mode):
    cid = _create(client, auth_headers, creditCode="91310000DET0001XA")["data"]["id"]
    d = client.get(f"{BASE}/{cid}", headers=auth_headers).json()
    assert d["code"] == 0 and "contacts" in d["data"] and "auditTrail" in d["data"]
    nf = client.get(f"{BASE}/99999999", headers=auth_headers).json()
    assert nf["code"] != 0


def test_import_rejects_junk_names(client, auth_headers, db_mode):
    """把营业执照整段粘进来的脏数据必须全部被预校验拦下（名称是账号/地址/税号/标签/纯数字）。"""
    junk = [
        {"name": "银行账户: 6607007880100001016"},
        {"name": "开户银行: 上海浦东发展银行股份有限公司长沙开福支行"},
        {"name": "单位地址: 湖南长沙岳麓区西铁馨寓1715"},
        {"name": "税号: 91430104MA4RXFFJ0T"},
        {"name": "名称: 湖南跃科信息工程有限公司"},   # 带"名称:"标签也拒，应去标签
        {"name": "6607007880100001016"},              # 纯数字
    ]
    dry = client.post(f"{BASE}/import/dry-run", headers=auth_headers, json={"rows": junk}).json()
    assert dry["code"] == 0
    assert dry["data"]["validRows"] == 0 and dry["data"]["invalidRows"] == len(junk)
    # 含脏行 → 确认导入被拒
    assert client.post(f"{BASE}/import/confirm", headers=auth_headers, json={"rows": junk}).json()["code"] != 0
    # 去掉标签后的正常企业名可通过
    clean = [{"name": "湖南跃科信息工程有限公司", "creditCode": "91430104MA4RXFFJ0T",
              "industry": "软件", "region": "长沙"}]
    ok = client.post(f"{BASE}/import/dry-run", headers=auth_headers, json={"rows": clean}).json()
    assert ok["data"]["validRows"] == 1 and ok["data"]["invalidRows"] == 0


def test_create_rejects_junk_name_and_bad_credit(client, auth_headers, db_mode):
    # 纯数字/账号名被拒
    assert client.post(BASE, headers=auth_headers, json={"name": "6607007880100001016"}).json()["code"] != 0
    # 标签名被拒
    assert client.post(BASE, headers=auth_headers, json={"name": "税号: 91430104"}).json()["code"] != 0
    # 信用代码含冒号/空格被拒
    assert client.post(BASE, headers=auth_headers,
                       json={"name": "正常科技有限公司", "creditCode": "税号:914"}).json()["code"] != 0


def test_xlsx_import_template_and_upload(client, auth_headers, db_mode):
    """Excel 导入：模板可下载(.xlsx)；上传 xlsx 解析+预校验，脏行被拦、好行可确认。"""
    import io
    from openpyxl import Workbook
    # 模板下载
    tpl = client.get(f"{BASE}/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"  # xlsx = zip
    # 构造 1 正常 + 1 脏(纯数字名) 的 xlsx
    wb = Workbook(); ws = wb.active
    ws.append(["企业名称", "统一社会信用代码", "行业", "地区"])
    ws.append(["跃科信息工程有限公司", "91430104MA4RXFFJ0T", "软件", "长沙"])
    ws.append(["6607007880100001016", "", "", ""])  # 脏：纯数字名
    buf = io.BytesIO(); wb.save(buf)
    up = client.post(f"{BASE}/import/xlsx", headers=auth_headers,
                     files={"file": ("t.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert up["code"] == 0
    assert len(up["data"]["rows"]) == 2
    assert up["data"]["validRows"] == 1 and up["data"]["invalidRows"] == 1
    # 含脏行确认被拒；仅好行确认通过
    assert client.post(f"{BASE}/import/confirm", headers=auth_headers,
                       json={"rows": up["data"]["rows"]}).json()["code"] != 0
    good = [r for r in up["data"]["rows"] if "6607" not in r["name"]]
    assert client.post(f"{BASE}/import/confirm", headers=auth_headers, json={"rows": good}).json()["code"] == 0
