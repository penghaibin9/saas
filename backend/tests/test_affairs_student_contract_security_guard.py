from pathlib import Path

from app.services.affairs_student_contract_security_guard import _safe_status_token


SOURCE = (Path(__file__).parents[1] / "app/services/affairs_student_contract_security_guard.py").read_text(
    encoding="utf-8"
)


def test_internal_audit_payload_is_not_a_student_status_token():
    assert _safe_status_token("COUNSELOR_REVIEW") == "COUNSELOR_REVIEW"
    assert _safe_status_token("reason=家庭经济说明") == ""
    assert _safe_status_token("内部意见：建议重点关注") == ""


def test_student_material_metadata_is_owner_scoped():
    assert "AffairsAttachment.created_by.in_(owner_ids)" in SOURCE
    assert '"visibility": "OWNER_ONLY"' in SOURCE
    assert "无法确认本人时 fail-closed" in SOURCE


def test_discipline_id_is_stable_and_dorm_has_no_fake_resubmit():
    assert 'item["applicationId"] = f"discipline-{case_id}"' in SOURCE
    assert '"SUBMIT_APPEAL" not in (item.get("allowedActions") or [])' in SOURCE
    assert 'item["allowedActions"] = []' in SOURCE
    assert "调宿退回没有真实编辑重提接口时不返回假动作" in SOURCE
