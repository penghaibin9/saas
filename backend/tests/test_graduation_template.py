"""毕业设计中心 · 材料模板中心闭环测试：
新建(草稿)→按类型列表→设默认须启用→启用→设默认→第二个设默认使第一个失默认→停用失默认→归档后不可编辑→统计。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

T = "/api/v1/graduation/gd-templates"


def _create(graduation_client, h, ttype, name):
    return graduation_client.post(T, headers=h, json={"templateType": ttype, "name": name,
                       "content": "尊敬的{学生姓名}，课题《{课题名称}》…", "applicableNote": "全校"}).json()["data"]


def test_template_lifecycle_and_default(graduation_client, auth_headers, db_mode):
    h = auth_headers
    a = _create(graduation_client, h, "MATERIAL", "材料模板A")
    assert a["status"] == "DRAFT"
    assert a["templateType"] == "MATERIAL"

    # 草稿不可设默认
    bad = graduation_client.post(f"{T}/{a['id']}/default", headers=h)
    assert bad.json()["code"] != 0

    # 启用后可设默认
    graduation_client.post(f"{T}/{a['id']}/status", headers=h, json={"action": "ENABLE"})
    d1 = graduation_client.post(f"{T}/{a['id']}/default", headers=h).json()["data"]
    assert d1["isDefault"] is True

    # 第二个模板设默认 → 第一个失默认
    b = _create(graduation_client, h, "MATERIAL", "材料模板B")
    graduation_client.post(f"{T}/{b['id']}/status", headers=h, json={"action": "ENABLE"})
    graduation_client.post(f"{T}/{b['id']}/default", headers=h)
    a_now = graduation_client.get(f"{T}/{a['id']}", headers=h).json()["data"]
    assert a_now["isDefault"] is False

    # 停用 B → 失默认
    graduation_client.post(f"{T}/{b['id']}/status", headers=h, json={"action": "DISABLE"})
    b_now = graduation_client.get(f"{T}/{b['id']}", headers=h).json()["data"]
    assert b_now["isDefault"] is False and b_now["status"] == "DISABLED"


def test_list_filtered_by_type(graduation_client, auth_headers, db_mode):
    h = auth_headers
    _create(graduation_client, h, "TASKBOOK", "任务书模板X")
    _create(graduation_client, h, "PROPOSAL", "开题模板Y")

    tb = graduation_client.get(T, headers=h, params={"templateType": "TASKBOOK"}).json()["data"]
    assert all(i["templateType"] == "TASKBOOK" for i in tb["items"])
    assert any(i["name"] == "任务书模板X" for i in tb["items"])


def test_archive_blocks_edit(graduation_client, auth_headers, db_mode):
    h = auth_headers
    a = _create(graduation_client, h, "MATERIAL", "待归档模板")
    graduation_client.post(f"{T}/{a['id']}/status", headers=h, json={"action": "ARCHIVE"})
    edited = graduation_client.put(f"{T}/{a['id']}", headers=h, json={"name": "改名"})
    assert edited.json()["code"] != 0  # 已归档不可编辑

    stats = graduation_client.get(f"{T}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1
