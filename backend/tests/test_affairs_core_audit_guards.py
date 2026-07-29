"""学工核心审计安全门静态合同。

不启动教务、实习、毕设等无关业务；只防本轮已确认的范围、状态与数据口径回归。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_router_installs_guards_after_existing_four_end_contract():
    source = read("backend/app/api/v1/router.py")
    contract = source.index("install_affairs_four_end_contract()")
    data = source.index("install_data_integrity_guard()")
    terminal = source.index("install_affairs_four_end_terminal_guard(api_router)")
    assert contract < data < terminal
    assert "install_counselor_handover_guard()" in source
    assert "install_risk_evidence_guard()" in source
    assert "install_counselor_eval_guard()" in source


def test_student_overview_and_profile_do_not_emit_false_current_state():
    source = read("backend/app/services/affairs_data_integrity_guard.py")
    assert 'data["careActionCount"] = int(count)' in source
    assert 'DormBed.status == "OCCUPIED"' in source
    assert 'AffairsRiskRecord.status != "CLOSED"' in source
    assert 'has_permission(user, "studentAffairs.discipline.view")' in source
    assert 'StudentProfile.tenant_id == _tid()' in source
    assert 'StudentProfile.is_deleted.is_(False)' in source


def test_decimal_14_2_overflow_is_rejected_before_mysql_commit():
    source = read("backend/app/services/affairs_data_integrity_guard.py")
    assert 'Decimal("999999999999.99")' in source
    assert "result.is_finite()" in source
    assert "result > _MAX_DECIMAL_14_2" in source
    assert "最多保留2位小数" in source


def test_counselor_handover_cannot_move_non_affairs_todos():
    source = read("backend/app/services/affairs_counselor_handover_guard.py")
    assert 'UnifiedTodo.source_module == "student-affairs"' in source
    assert "UnifiedTodo.source_biz_type == todo.source_biz_type" in source
    assert '(instance.source_biz_type or "").upper() != "LEAVE"' in source


def test_risk_high_impact_actions_require_auditable_evidence():
    source = read("backend/app/services/affairs_risk_evidence_guard.py")
    for label in ("跟进记录", "转办原因", "升级依据", "接管说明", "重开原因"):
        assert label in source
    assert "if receiver <= 0" in source


def test_counselor_evaluation_scope_and_publish_preconditions():
    source = read("backend/app/services/affairs_counselor_eval_guard.py")
    assert "expected_version = int(period.version or 0)" in source
    assert 'raise AppException("NO_DATA_SCOPE"' in source
    assert 'scope_type != "TENANT_ALL"' in source
    assert 'row.status != "SCORED" or row.college_score is None' in source
