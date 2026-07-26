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


def _batch(client, h):
    """岗位上架要求挂在有效批次上（合规规则 BATCH_UNKNOWN），这里备一个可复用的批次。"""
    from uuid import uuid4
    r = client.post("/api/v1/internship/batches", headers=h, json={
        "batchName": f"岗位测试批次-{uuid4().hex[:6]}", "batchNo": f"POSB-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 10}).json()
    return r["data"]["id"]


# 上架前必须录全的劳动权益事实（见 internship_position_rights.field_map）：
# 缺任何一项都会被判 REQUIRED_UNKNOWN——"未录入不能解释为安全"
_RIGHTS_FACTS = {
    "workContent": "参与前端页面开发与联调", "dailyHours": 8, "weeklyHours": 40,
    "nightShift": False, "overtimeAllowed": False, "restDaysPerWeek": 2,
    "remunerationType": "MONTHLY", "accommodationProvided": True,
    "mealProvided": True, "hazardousFlag": False,
    # 有报酬岗位还必须写清金额与发放周期，否则判 REMUNERATION_*_UNKNOWN
    "remunerationAmount": 2000, "remunerationCycle": "MONTHLY",
}


def _mk(client, h, cid, **over):
    body = {"companyId": cid, "title": "前端开发实习生", "majorRequirement": "软件技术",
            "gradeRequirement": "2024级", "workLocation": "上海浦东", "salaryRange": "3k-4k",
            "headcount": 5, **_RIGHTS_FACTS}
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


def test_list_filter_by_batch(client, auth_headers, db_mode):
    """batch_id 联调收口：岗位列表按 batchId 筛选（只返回该批次岗位）。"""
    cid = _company(client, auth_headers, cc="91310000POSBAT1XA")
    _mk(client, auth_headers, cid, title="批次A岗位", batchId="101")
    _mk(client, auth_headers, cid, title="批次B岗位", batchId="202")
    _mk(client, auth_headers, cid, title="无批次岗位")
    only_a = client.get(f"{POS}?batchId=101", headers=auth_headers).json()["data"]
    assert only_a["total"] == 1 and only_a["items"][0]["title"] == "批次A岗位"
    # 非数字 batchId → 400（不再 int() 500）
    assert client.get(f"{POS}?batchId=abc", headers=auth_headers).status_code == 400


def test_status_machine_publish(client, auth_headers, db_mode):
    cid = _company(client, auth_headers)  # 已审核 → 合作中
    bid = _batch(client, auth_headers)
    pid = _mk(client, auth_headers, cid, batchId=str(bid))["data"]["id"]
    # 草稿直接上架 → 非法（须先提交/或从待审核）
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()["code"] != 0
    # 提交 → 待审核
    assert client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "SUBMIT"}).json()["data"]["status"] == "PENDING"
    # 上架 → 已上架
    pub = client.post(f"{POS}/{pid}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()
    assert pub["code"] == 0, f"上架被拒：{pub.get('message')}"
    assert pub["data"]["status"] == "PUBLISHED"
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
    created = _mk(client, auth_headers, cid, headcount=3)["data"]
    pid = created["id"]
    # 容量可正常改大（expectedVersion 已是必填，防并发覆盖）
    assert client.put(f"{POS}/{pid}", headers=auth_headers, json={
        "headcount": 10, "expectedVersion": created.get("version", 0)}).json()["data"]["headcount"] == 10


def test_stats(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, cc="91310000POSSTA1XA")
    _mk(client, auth_headers, cid)
    s = client.get(f"{POS}/stats", headers=auth_headers).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1
    assert any(x["status"] == "DRAFT" for x in s["data"]["byStatus"])


# 导入行的劳动权益事实同样必填（服务层逐字段校验"不能留空"），且必须指到已存在的批次编号
_IMPORT_FACTS = {
    "templateVersion": "POSITION_IMPORT_V2",
    "workContent": "运维值班与巡检", "dailyHours": "8", "weeklyHours": "40",
    "nightShift": "否", "overtimeAllowed": "否", "restDaysPerWeek": "2",
    "remunerationType": "MONTHLY", "accommodationProvided": "是",
    "mealProvided": "是", "hazardousFlag": "否",
}


def test_import_dry_run_and_confirm(client, auth_headers, db_mode):
    from uuid import uuid4
    _company(client, auth_headers, cc="91310000POSIMP1XA", name="导入匹配企业")
    batch_no = f"POSIMP-{uuid4().hex[:8]}"
    client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": "导入用批次", "batchNo": batch_no,
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5})
    rows = [{"title": "运维实习生", "company": "导入匹配企业", "major": "计算机网络",
             "headcount": "2", "batchNo": batch_no, **_IMPORT_FACTS},
            {"title": "", "company": "导入匹配企业", "batchNo": batch_no, **_IMPORT_FACTS},   # 缺岗位名
            {"title": "测试实习生", "company": "查无此企业", "batchNo": batch_no, **_IMPORT_FACTS}]  # 企业匹配不到
    dry = client.post(f"{POS}/import/dry-run", headers=auth_headers,
                      json={"rows": rows, "templateVersion": "POSITION_IMPORT_V2"}).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 2
    # 含错行 → 确认被拒
    assert client.post(f"{POS}/import/confirm", headers=auth_headers,
                       json={"rows": rows, "templateVersion": "POSITION_IMPORT_V2"}).json()["code"] != 0
    ok = client.post(f"{POS}/import/confirm", headers=auth_headers,
                     json={"rows": [rows[0]], "templateVersion": "POSITION_IMPORT_V2"}).json()
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


def test_create_non_numeric_ids_400_not_500(client, auth_headers, db_mode):
    """历史欠账收口：companyId/batchId 非数字此前 int() 抛 ValueError→500，现应 400 VALIDATION_ERROR。"""
    r1 = client.post(POS, headers=auth_headers, json={"companyId": "abc", "title": "X"})
    assert r1.status_code == 400 and r1.json()["bizCode"] == "VALIDATION_ERROR"
    cid = _company(client, auth_headers, cc="91310000POSNUM1XA")
    r2 = client.post(POS, headers=auth_headers, json={"companyId": cid, "title": "岗位", "batchId": "notnum"})
    assert r2.status_code == 400 and r2.json()["bizCode"] == "VALIDATION_ERROR"


def test_position_xlsx_import_template_and_upload(client, auth_headers, db_mode):
    import io
    from openpyxl import Workbook
    _company(client, auth_headers, cc="91310000POSXLS1XA", name="Excel导入企业")
    tpl = client.get(f"{POS}/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"
    from uuid import uuid4
    batch_no = f"POSXLS-{uuid4().hex[:8]}"
    client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": "Excel导入批次", "batchNo": batch_no,
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5})
    wb = Workbook()
    ws = wb.active
    # 表头必须与后端模板一致（_POS_XLSX_HEADERS）：含模板版本、批次编号与全部劳动权益事实
    ws.append(["模板版本", "实习批次编号", "岗位名称", "企业信用代码/企业名称", "工作内容", "工作地址",
               "每日工时", "每周工时", "班次", "是否夜班", "是否允许加班", "每周休息天数",
               "报酬类型", "报酬金额", "发放周期", "是否住宿", "是否供餐", "是否危险岗位",
               "特殊设备", "禁止安排原因", "容量", "专业要求", "年级要求", "企业导师", "备注"])
    ws.append(["POSITION_IMPORT_V2", batch_no, "测试岗位X", "Excel导入企业", "运维值班与巡检", "上海浦东",
               "8", "40", "白班", "否", "否", "2",
               "MONTHLY", "2000", "MONTHLY", "是", "是", "否",
               "", "", "2", "软件技术", "2024级", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    up = client.post(f"{POS}/import/xlsx", headers=auth_headers,
                     files={"file": ("p.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert up["code"] == 0, f"上传预检失败：{up.get('message')}"
    assert up["data"]["validRows"] == 1, up["data"].get("errors")
    assert client.post(f"{POS}/import/confirm", headers=auth_headers,
                       json={"rows": up["data"]["rows"],
                             "templateVersion": "POSITION_IMPORT_V2"}).json()["code"] == 0


def test_reverse_fill_enterprise_position_summary(client, auth_headers, db_mode):
    """反向补：企业详情返回其岗位摘要。"""
    cid = _company(client, auth_headers, cc="91310000POSREV1XA")
    _mk(client, auth_headers, cid)
    _mk(client, auth_headers, cid, title="第二个岗位")
    d = client.get(f"{ENT}/{cid}", headers=auth_headers).json()
    assert d["code"] == 0 and d["data"]["positionSummary"]["total"] == 2
