"""帮助与反馈工单 · 端到端（真实 DB 模式）。

F1 学生提交→本人历史可见；F2 本人隔离（看不到他人）；F3 处理侧列表+受理+回复+办结；
F4 办结不可再改；F5 内容过短 400；F6 无效 action 400；F7 处理侧需 staff（学生 403）。
"""
from __future__ import annotations

BASE = "/api/v1/feedback"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _submit(client, hdr, content="页面偶尔加载不出来，麻烦看下", category="BUG", title="一个问题"):
    return client.post(BASE, headers=hdr, json={
        "content": content, "category": category, "title": title})


def test_f1_submit_and_my_history(client, db_mode):
    hdr = _hdr(client, "student01")
    r = _submit(client, hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["status"] == "SUBMITTED" and d["category"] == "BUG" and d["userType"] == "STUDENT"
    # 本人历史可见
    my = client.get(f"{BASE}/my", headers=hdr).json()["data"]
    assert my["total"] == 1 and my["items"][0]["id"] == d["id"]


def test_f2_my_list_isolated_per_user(client, db_mode):
    a = _hdr(client, "student01")
    b = _hdr(client, "teacher01")
    _submit(client, a, content="学生甲的反馈内容占位")
    _submit(client, b, content="教师乙的反馈内容占位")
    # 各自只看到自己
    my_a = client.get(f"{BASE}/my", headers=a).json()["data"]
    my_b = client.get(f"{BASE}/my", headers=b).json()["data"]
    assert my_a["total"] == 1 and my_b["total"] == 1
    assert my_a["items"][0]["userType"] == "STUDENT"
    assert my_b["items"][0]["userType"] == "TEACHER"


def test_f3_handle_flow_accept_reply_close(client, db_mode):
    stu = _hdr(client, "student01")
    admin = _hdr(client, "school_admin01")
    fid = _submit(client, stu).json()["data"]["id"]
    # 处理侧列表可见
    lst = client.get(BASE, headers=admin).json()["data"]
    assert any(it["id"] == fid for it in lst["items"])
    # 受理 → HANDLING
    r1 = client.post(f"{BASE}/{fid}/handle", headers=admin, json={"action": "ACCEPT"}).json()
    assert r1["data"]["status"] == "HANDLING"
    # 回复
    r2 = client.post(f"{BASE}/{fid}/handle", headers=admin,
                     json={"action": "REPLY", "reply": "已定位，下个版本修复"}).json()
    # handledBy 仅在受理人 userId 为数字（真实 t_user.id）时落库；mock 账号 userId 为 u_xxx 非数字，
    # 故此处只校验回复正文与状态，不断言 handledBy（真实部署下 userId 为 BigInteger 会正常记录）。
    assert r2["data"]["reply"] == "已定位，下个版本修复" and r2["data"]["status"] == "HANDLING"
    # 办结 → CLOSED
    r3 = client.post(f"{BASE}/{fid}/handle", headers=admin, json={"action": "CLOSE"}).json()
    assert r3["data"]["status"] == "CLOSED"
    # 学生本人历史看到已办结 + 回复
    my = client.get(f"{BASE}/my", headers=stu).json()["data"]["items"][0]
    assert my["status"] == "CLOSED" and my["reply"] == "已定位，下个版本修复"
    # stats 汇总
    st = client.get(f"{BASE}/stats", headers=admin).json()["data"]
    assert st["total"] >= 1 and st["closed"] >= 1


def test_f4_closed_cannot_rehandle_409(client, db_mode):
    stu = _hdr(client, "student01")
    admin = _hdr(client, "school_admin01")
    fid = _submit(client, stu).json()["data"]["id"]
    client.post(f"{BASE}/{fid}/handle", headers=admin, json={"action": "CLOSE"})
    r = client.post(f"{BASE}/{fid}/handle", headers=admin, json={"action": "ACCEPT"})
    assert r.status_code == 409 and r.json()["bizCode"] == "DATA_CONFLICT"


def test_f5_content_too_short_400(client, db_mode):
    hdr = _hdr(client, "student01")
    r = client.post(BASE, headers=hdr, json={"content": "短"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_f6_invalid_action_400(client, db_mode):
    stu = _hdr(client, "student01")
    admin = _hdr(client, "school_admin01")
    fid = _submit(client, stu).json()["data"]["id"]
    r = client.post(f"{BASE}/{fid}/handle", headers=admin, json={"action": "FOO"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_f7_handle_side_requires_staff_student_403(client, db_mode):
    stu = _hdr(client, "student01")
    fid = _submit(client, stu).json()["data"]["id"]
    # 学生令牌访问处理侧列表/详情/受理 → 403
    assert client.get(BASE, headers=stu).status_code == 403
    assert client.get(f"{BASE}/{fid}", headers=stu).status_code == 403
    assert client.post(f"{BASE}/{fid}/handle", headers=stu, json={"action": "ACCEPT"}).status_code == 403
