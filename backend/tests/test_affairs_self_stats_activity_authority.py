"""学生本人范围、统计口径与活动管理权限静态回归合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_self_scope_is_resolved_server_side_and_only_allows_self():
    text = read("backend/app/core/affairs_security.py")
    guard = read("backend/app/services/affairs_self_scope_guard.py")
    assert "resolve_student" in text
    assert 'ctx.scope_source = "ACCOUNT_LINK_SELF" if ctx.self_student_id else "SELF_UNRESOLVED"' in text
    assert 'self.scope_type == "SELF"' in text
    assert 'int(self.self_student_id) != target_id' in text
    assert "学生只能访问本人数据" in text
    assert "build_affairs_context =" not in guard


def test_statistics_are_scoped_and_missing_metrics_are_not_fake_zero():
    text = read("backend/app/services/affairs_stats_integrity_guard.py")
    assert "SchoolClass.is_deleted.is_(False)" in text
    assert "activity_scope._teacher_scope_tokens" in text
    assert "StudentProfile.class_id.in_(allowed_classes or {-1})" in text
    assert "统计口径缺少必需字段" in text
    assert '"key": "workStudy"' in text
    assert '"key": "archive"' in text
    assert '"key": "family"' in text


def test_activity_create_and_state_actions_are_server_scoped():
    text = read("backend/app/services/affairs_activity_authority_guard.py")
    assert "学院角色只能创建本院活动" in text
    assert "辅导员只能创建本人负责班级的活动" in text
    assert "该活动不在您的管理范围内" in text
    for name in (
        "update_activity", "publish_activity", "transition_activity",
        "confirm_activity", "unconfirm_activity", "archive_activity",
    ):
        assert f"def {name}" in text
    assert 'path.startswith("/api/v1/student-affairs/activities/")' in text
    assert "类目权重格式非法" in text


def test_router_installs_authority_before_final_review_guards():
    source = read("backend/app/api/v1/router.py")
    authority = source.index("install_activity_authority_guard()")
    stats = source.index("install_stats_integrity_guard()")
    review = source.index("install_affairs_four_end_review_guard()")
    assert authority < stats < review


def test_four_end_contract_no_longer_replaces_scope_or_mental_audit():
    contract = read("backend/app/services/affairs_four_end_contract.py")
    assert "def _patch_student_scope" not in contract
    assert "def _patch_mental_audit" not in contract
    assert "mental._sensitive_view_audit =" not in contract
    assert "sys.modules" not in contract
