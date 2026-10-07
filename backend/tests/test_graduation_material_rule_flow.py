"""毕业设计材料规则：创建草稿 → 影响分析 → 启用，以及整批一次生成材料清单。"""
from __future__ import annotations

from conftest import make_org_class

RULES = "/api/v1/graduation/material-center/rules"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(graduation_client, h, no, name):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def _material_codes(gd_student_id):
    from app.db.session import get_sessionmaker
    from app.models.graduation_material import GraduationStudentMaterial

    db = get_sessionmaker()()
    try:
        rows = db.query(GraduationStudentMaterial).filter(
            GraduationStudentMaterial.gd_student_id == int(gd_student_id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).all()
        return sorted(row.material_code for row in rows)
    finally:
        db.close()


def test_rule_list_exposes_template_and_version(graduation_client, auth_headers, db_mode):
    _gd_student(graduation_client, auth_headers, "MR000", "规则测试零")
    batch_id = graduation_client._active_batch_id
    data = graduation_client.get(RULES, headers=auth_headers, params={"batchId": batch_id}).json()["data"]
    assert data["defaultTemplate"], "规则编辑页需要系统标准模板"
    assert "THESIS_FINAL" in data["reviewSupportedCodes"]
    codes = {row["materialCode"] for row in data["defaultTemplate"]}
    assert {"TASKBOOK", "PROPOSAL_REPORT", "MIDTERM_REPORT", "THESIS_DRAFT", "THESIS_FINAL"} <= codes
    for rule in data["items"]:
        assert isinstance(rule["version"], int)


def test_draft_impact_and_activate_regenerates_catalog(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid_a = _gd_student(graduation_client, h, "MR001", "规则测试甲")
    gid_b = _gd_student(graduation_client, h, "MR002", "规则测试乙")
    batch_id = graduation_client._active_batch_id

    listing = graduation_client.get(RULES, headers=h, params={"batchId": batch_id}).json()["data"]
    template = listing["defaultTemplate"]
    keep = [dict(row) for row in template if row["materialCode"] not in {"SOURCE_CODE", "DESIGN_WORK"}]

    created = graduation_client.post(RULES, headers=h, json={"batchId": batch_id, "ruleName": "流程测试规则", "items": keep})
    assert created.status_code == 200, created.text
    draft_id = created.json()["data"]["id"]

    listing = graduation_client.get(RULES, headers=h, params={"batchId": batch_id}).json()["data"]
    draft = next(rule for rule in listing["items"] if rule["id"] == draft_id)
    assert draft["status"] == "DRAFT"
    assert len(draft["items"]) == len(keep)

    impact = graduation_client.get(f"{RULES}/{draft_id}/impact", headers=h)
    assert impact.status_code == 200, impact.text
    assert impact.json()["data"]["affectedStudents"] >= 2

    # 影响到已有材料目录时，不显式确认不能启用
    activated = graduation_client.post(
        f"{RULES}/{draft_id}/activate", headers=h,
        json={"expectedVersion": draft["version"], "confirmCatalogRepair": True},
    )
    assert activated.status_code == 200, activated.text

    after = graduation_client.get(RULES, headers=h, params={"batchId": batch_id}).json()["data"]
    enabled = [rule for rule in after["items"] if rule["status"] == "ENABLED" and rule["enabled"]]
    assert [rule["id"] for rule in enabled] == [draft_id]

    expected = sorted(row["materialCode"] for row in keep)
    for gid in (gid_a, gid_b):
        codes = _material_codes(gid)
        assert codes == expected, (gid, "多出", sorted(set(codes) - set(expected)), "缺少", sorted(set(expected) - set(codes)))
        assert "SOURCE_CODE" not in codes


def test_activation_is_idempotent_for_existing_catalog(graduation_client, auth_headers, db_mode):
    """再启用同样内容的新版本，不会给同一学生重复生成同一项材料。"""
    h = auth_headers
    gid = _gd_student(graduation_client, h, "MR003", "规则幂等测试")
    batch_id = graduation_client._active_batch_id
    template = graduation_client.get(RULES, headers=h, params={"batchId": batch_id}).json()["data"]["defaultTemplate"]
    items = [dict(row) for row in template]
    for _ in range(2):
        created = graduation_client.post(RULES, headers=h, json={"batchId": batch_id, "ruleName": "幂等规则", "items": items})
        rid = created.json()["data"]["id"]
        draft = next(r for r in graduation_client.get(RULES, headers=h, params={"batchId": batch_id}).json()["data"]["items"] if r["id"] == rid)
        res = graduation_client.post(f"{RULES}/{rid}/activate", headers=h,
                                     json={"expectedVersion": draft["version"], "confirmCatalogRepair": True})
        assert res.status_code == 200, res.text
    codes = _material_codes(gid)
    assert len(codes) == len(set(codes)) == len(items)
