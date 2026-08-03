"""毕业设计中心 · 开题材料闭环测试：
学生端提交/重交（不可重复提交）→ 管理端列表/详情（历史版本）→ 批阅通过推进阶段/驳回需理由 →
未提交学生派生 + 催交（已提交不可催）→ Excel 台账导出。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
PROP = "/api/v1/graduation/proposals"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _gd_student_with_topic(graduation_client, h, no, name):
    """建档 + 选题确认（stage→TASKBOOK_CONFIRM，满足开题提交前置）。"""
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = graduation_client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": "指导张老师",
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    graduation_client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    graduation_client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def _submit_proposal(graduation_client, sh, background="选题背景说明：面向职校学生的实训管理系统",
                     plan="研究方案：需求分析→设计→实现→测试，共 12 周", outcome="预期成果：可运行系统 + 论文"):
    return graduation_client.post(f"{MOBILE}/graduation/proposal", headers=sh,
                       json={"background": background, "plan": plan, "outcome": outcome})


def test_student_submit_and_no_duplicate(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name = "开题小明"
    _gd_student_with_topic(graduation_client, h, "PR001", name)
    sh = _stu_token(name)

    # 提交前：可提交、无最新版
    view0 = graduation_client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]
    assert view0["hasData"] is True
    assert view0["canSubmit"] is True
    assert view0["latest"] is None

    ok = _submit_proposal(graduation_client, sh)
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["status"] == "PENDING_REVIEW"
    assert ok.json()["data"]["version"] == "v1"

    # 待审阅时不可重复提交
    dup = _submit_proposal(graduation_client, sh)
    assert dup.json()["code"] != 0

    view1 = graduation_client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]
    assert view1["canSubmit"] is False
    assert view1["latest"]["status"] == "PENDING_REVIEW"


def test_review_approve_advances_stage_and_detail_versions(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name = "开题小红"
    gid = _gd_student_with_topic(graduation_client, h, "PR101", name)
    sh = _stu_token(name)
    _submit_proposal(graduation_client, sh)

    lst = graduation_client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]
    row = next(r for r in lst["items"] if r["studentName"] == name)
    pid = row["id"]

    detail = graduation_client.get(f"{PROP}/{pid}", headers=h).json()["data"]
    assert len(detail["versions"]) == 1
    assert detail["content"]["background"]

    # 驳回需理由≥5
    bad = graduation_client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "REJECT", "comment": "x"})
    assert bad.json()["code"] != 0

    ok = graduation_client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "APPROVE", "comment": "选题合理"})
    assert ok.json()["code"] == 0

    stu_after = graduation_client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu_after["stage"] == "GUIDING"

    # 已批阅不可再批
    again = graduation_client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "APPROVE"})
    assert again.json()["code"] != 0


def test_reject_then_resubmit_new_version(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name = "开题小刚"
    _gd_student_with_topic(graduation_client, h, "PR201", name)
    sh = _stu_token(name)
    _submit_proposal(graduation_client, sh)

    lst = graduation_client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]
    pid = next(r for r in lst["items"] if r["studentName"] == name)["id"]
    graduation_client.post(f"{PROP}/{pid}/review", headers=h, json={"action": "REJECT", "comment": "研究方案需细化进度安排"})

    # 被驳回后可重交，版本 v2 + 重交标记
    view = graduation_client.get(f"{MOBILE}/graduation/proposal", headers=sh).json()["data"]
    assert view["canSubmit"] is True
    assert view["latest"]["status"] == "REJECTED"

    resub = _submit_proposal(graduation_client, sh, background="修订后的选题背景说明：补充可行性论证",
                             plan="修订研究方案：细化到每周里程碑")
    assert resub.json()["code"] == 0
    assert resub.json()["data"]["version"] == "v2"
    assert resub.json()["data"]["isResubmit"] is True

    lst2 = graduation_client.get(PROP, headers=h, params={"status": "PENDING_REVIEW"}).json()["data"]
    pid2 = next(r for r in lst2["items"] if r["studentName"] == name)["id"]
    detail = graduation_client.get(f"{PROP}/{pid2}", headers=h).json()["data"]
    assert len(detail["versions"]) == 2  # 历史含被驳回的 v1


def test_not_submitted_derivation_and_remind(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name = "未交小李"
    _gd_student_with_topic(graduation_client, h, "PR301", name)  # 已确认选题但未提交开题

    # 未提交页签应派生出该生
    nb = graduation_client.get(PROP, headers=h, params={"status": "NOT_SUBMITTED"}).json()["data"]
    target = next(r for r in nb["items"] if r["studentName"] == name)
    assert target["status"] == "NOT_SUBMITTED"

    # 催交成功（真实写审计，非 mock）
    remind = graduation_client.post(f"{PROP}/remind", headers=h, json={"gdStudentId": target["gdStudentId"]})
    assert remind.json()["code"] == 0
    assert remind.json()["data"]["reminded"] is True

    # 已提交的学生不可催交
    sh = _stu_token(name)
    _submit_proposal(graduation_client, sh)
    remind2 = graduation_client.post(f"{PROP}/remind", headers=h, json={"gdStudentId": target["gdStudentId"]})
    assert remind2.json()["code"] != 0


def test_export_proposals_ledger(graduation_client, auth_headers, db_mode):
    h = auth_headers
    name = "导出小周"
    _gd_student_with_topic(graduation_client, h, "PR401", name)
    sh = _stu_token(name)
    _submit_proposal(graduation_client, sh)

    exp = graduation_client.post(f"{PROP}/export", headers=h)
    body = exp.json()
    assert body["code"] == 0
    assert body["data"]["rowCount"] >= 1
    assert body["data"]["filename"].endswith(".xlsx")
    assert body["data"]["contentBase64"]
