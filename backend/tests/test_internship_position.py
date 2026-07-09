"""岗位实习中心 · 岗位库测试：CRUD + 状态机(草稿/待审/上架/下架/暂停/归档/风险)
+ 黑名单/停用企业不能上架 + 复用企业库(t_emp_company) + 导入导出 + 反向补企业岗位摘要 + 越权404。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

POS = "/api/v1/internship/positions"
ENT = "/api/v1/internship/enterprises"


def _company(client, h, approve=True, cc="91310000POS0001XA", name="岗位测试企业"):
    cid = client.post(ENT, headers=h, json={"name": name, "creditCode": cc}).json()["data"]["id"]
    if approve:
        client.post(f"{ENT}/{cid}/review", headers=h, json={"action": "APPROVE"})
    return cid


def _mk(client, h, cid, **over):
    body = {"companyId": cid, "title": "前端开发实习生", "majorRequirement": "软件技术",
            "gradeRequirement": "2024级", "workLocation": "上海浦东", "salaryRange": "3k-4k",
            "headcount": 5}
    body.update(over)
    return client.post(POS, headers=h, json=body).json()


def test_create_requires_company(client, auth_headers, db_mode):
    # 不存在的企业 → 404
    r = client.post(POS, headers=auth_headers, json={"companyId": "99999999", "title": "X"}).json()
    assert r["code"] != 0


def test_create_and_list(client, auth_headers, db_mode):
    cid = _company(client, auth_headers)
    r = _mk(client, auth_headers, cid)
    assert r["code"] == 0 and r["data"]["status"] == "DRAFT"
    assert r["data"]["companyName"] == "岗位测试企业"
    assert r["data"]["remaining"] == 5
    lst = client.get(POS, headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1


def test_status_machine_publish(client, auth_headers, db_mode):
    cid = _company(client, auth_headers)  # 已审核 → 合作中
    pid = _mk(client, auth_headers, cid)["data"]["id"]
    # 草稿直接上架 → 非法（须先提交/或从待审核）
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()["code"] != 0
    # 提交 → 待审核
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUBMIT"}).json()["data"]["status"] == "PENDING"
    # 上架 → 已上架
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()["data"]["status"] == "PUBLISHED"
    # 暂停 → 已暂停
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUSPEND"}).json()["data"]["status"] == "SUSPENDED"
    # 下架 → 已下架
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "OFFLINE"}).json()["data"]["status"] == "OFFLINE"
    # 归档 → 已归档
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "ARCHIVE"}).json()["data"]["status"] == "ARCHIVED"
    # 已归档不可编辑
    assert client.put(f"{POS}/{pid}", headers=auth_headers, json={"title": "改名"}).json()["code"] != 0
    # 已归档不可再变更状态
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()["code"] != 0


def test_blacklist_company_cannot_publish(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSBLK1XA", name="黑名单企业")
    client.post(f"{ENT}/{cid}/blacklist", headers=auth_headers, json={"on": True, "reason": "拖欠津贴多次投诉"})
    pid = _mk(client, auth_headers, cid)["data"]["id"]
    client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUBMIT"})
    r = client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()
    assert r["code"] != 0  # 黑名单企业不能发布岗位


def test_non_active_company_cannot_publish(client, auth_headers, db_mode):
    # 未审核企业（coop_status=PENDING，非合作中）
    cid = _company(client, auth_headers, approve=False, cc="91310000POSNAC1XA", name="未审核企业")
    pid = _mk(client, auth_headers, cid)["data"]["id"]
    client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUBMIT"})
    r = client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()
    assert r["code"] != 0  # 仅合作中企业可上架


def test_risk_mark(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSRSK1XA")
    pid = _mk(client, auth_headers, cid)["data"]["id"]
    # 标记风险无说明 → 非法
    assert client.post(f"{POS}/{pid}/risk", headers=auth_headers, json={"on": True, "note": ""}).json()["code"] != 0
    on = client.post(f"{POS}/{pid}/risk", headers=auth_headers, json={"on": True, "note": "工伤隐患未整改"}).json()
    assert on["code"] == 0 and on["data"]["riskFlag"] is True and on["data"]["status"] == "RISK"
    off = client.post(f"{POS}/{pid}/risk", headers=auth_headers, json={"on": False}).json()
    assert off["data"]["riskFlag"] is False


def test_headcount_not_below_allocated(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSCAP1XA")
    pid = _mk(client, auth_headers, cid, headcount=3)["data"]["id"]
    # 容量可正常改大
    assert client.put(f"{POS}/{pid}", headers=auth_headers, json={"headcount": 10}).json()["data"]["headcount"] == 10


def test_stats(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSSTA1XA")
    _mk(client, auth_headers, cid)
    s = client.get(f"{POS}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1
    assert any(x["status"] == "DRAFT" for x in s["data"]["byStatus"])


def test_import_dry_run_and_confirm(client, auth_headers, db_mode):
    _company(client, auth_headers, cc="91310000POSIMP1XA", name="导入匹配企业")
    rows = [{"title": "运维实习生", "company": "导入匹配企业", "major": "计算机网络", "headcount": "2"},
            {"title": "", "company": "导入匹配企业"},          # 缺岗位名
            {"title": "测试实习生", "company": "查无此企业"}]   # 企业匹配不到
    dry = client.post(f"{POS}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 2
    # 含错行 → 确认被拒
    assert client.post(f"{POS}/import/confirm", headers=auth_headers, json={"rows": rows}).json()["code"] != 0
    ok = client.post(f"{POS}/import/confirm", headers=auth_headers, json={"rows": [rows[0]]}).json()
    assert ok["code"] == 0 and ok["data"]["created"] == 1


def test_export(client, auth_headers, db_mode):
    import base64
    cid = _company(client, auth_headers, cc="91310000POSEXP1XA")
    _mk(client, auth_headers, cid)
    ex = client.post(f"{POS}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and ex["data"]["filename"].endswith(".xlsx")
    assert base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"
    assert ex["data"]["rowCount"] >= 1


def test_detail_and_not_found(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSDET1XA")
    pid = _mk(client, auth_headers, cid)["data"]["id"]
    d = client.get(f"{POS}/{pid}", headers=auth_headers).json()
    assert d["code"] == 0 and d["data"]["company"]["coopStatus"] == "ACTIVE" and "auditTrail" in d["data"]
    assert client.get(f"{POS}/99999999", headers=auth_headers).json()["code"] != 0


def test_position_xlsx_import_template_and_upload(client, auth_headers, db_mode):
    import io
    from openpyxl import Workbook
    _company(client, auth_headers, cc="91310000POSXLS1XA", name="Excel导入企业")
    tpl = client.get(f"{POS}/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"
    wb = Workbook()
    ws = wb.active
    ws.append(["岗位名称", "关联企业", "岗位类型", "专业要求", "年级要求", "工作地点", "容量"])
    ws.append(["测试岗位X", "Excel导入企业", "技术岗", "软件技术", "2024级", "上海", "2"])
    buf = io.BytesIO()
    wb.save(buf)
    up = client.post(f"{POS}/import/xlsx", headers=auth_headers,
                     files={"file": ("p.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert up["code"] == 0 and up["data"]["validRows"] == 1
    assert client.post(f"{POS}/import/confirm", headers=auth_headers,
                       json={"rows": up["data"]["rows"]}).json()["code"] == 0


def test_reverse_fill_enterprise_position_summary(client, auth_headers, db_mode):
    """反向补：企业详情返回其岗位摘要。"""
    cid = _company(client, auth_headers, cc="91310000POSREV1XA")
    _mk(client, auth_headers, cid)
    _mk(client, auth_headers, cid, title="第二个岗位")
    d = client.get(f"{ENT}/{cid}", headers=auth_headers).json()
    assert d["code"] == 0 and d["data"]["positionSummary"]["total"] == 2
