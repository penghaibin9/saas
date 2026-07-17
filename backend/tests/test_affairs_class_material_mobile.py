"""学工中心 · 移动端班级材料（辅导员本班新增/列表/作废）。全部经 HTTP client 走真库(db_mode)。
COUNSELOR 权限矩阵本就含 studentAffairs.class.create，PC 端 add_material/void_material 已在
服务层 _class_in_scope_or_403 自校验；本文件覆盖移动端新增入口的全链路及跨班越权拦截。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_classes(db_mode):
    """A 班(辅导员 counselor01 授权)+ B 班(无授权)。返回 {A, B}。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2201", grade="2022", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2202", grade="2022", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2201",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id}
    db.close()
    return ids


def test_material_add_list_void_full_flow_via_mobile(client, db_mode):
    """本班材料新增→列表可见→作废→列表不再含该材料（void 逻辑删除）。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")

    add = client.post(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials", headers=hdr,
                      json={"materialType": "CLASS_MEETING", "title": "第10周主题班会记录",
                            "materialAt": "2026-05-10", "remark": "全员到齐"})
    assert add.status_code == 200 and add.json()["code"] == 0
    material_id = add.json()["data"]["id"]

    lst = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials", headers=hdr).json()
    assert lst["code"] == 0
    assert any(m["id"] == material_id and m["title"] == "第10周主题班会记录" for m in lst["data"]["list"])

    void = client.post(f"{MOB}/teacher/affairs/classes/materials/{material_id}/void", headers=hdr,
                       json={"reason": "记录有误重新登记"})
    assert void.status_code == 200 and void.json()["data"]["status"] == "VOIDED"

    lst2 = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials", headers=hdr).json()
    assert not any(m["id"] == material_id for m in lst2["data"]["list"])


def test_material_type_filter_via_mobile(client, db_mode):
    """按 materialType 过滤：只返回指定类型的材料。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    client.post(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials", headers=hdr,
               json={"materialType": "CLASS_MEETING", "title": "班会A"})
    client.post(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials", headers=hdr,
               json={"materialType": "SUMMARY", "title": "总结B"})

    meeting = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/materials",
                         headers=hdr, params={"materialType": "CLASS_MEETING"}).json()["data"]["list"]
    assert all(m["title"] != "总结B" for m in meeting)
    assert any(m["title"] == "班会A" for m in meeting)


def test_cross_class_material_add_403_via_mobile(client, db_mode):
    """越权：辅导员(范围=A班)对 B 班新增材料 → 403（复用 add_material 内部 _class_in_scope_or_403）。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    r = client.post(f"{MOB}/teacher/affairs/classes/{ids['B']}/materials", headers=hdr,
                    json={"materialType": "OTHER", "title": "越权材料"})
    assert r.status_code == 403
