"""学工第一阶段契约回归：状态机、乐观锁与前端大页码清理。"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/api/v1/student_affairs.py"
RISK_SERVICE = ROOT / "app/services/affairs_risk_service.py"
AFFAIRS_SECURITY = ROOT / "app/core/affairs_security.py"
VIEWS = ROOT.parent / "frontend/src/modules/studentAffairs/views"


def _class_body(source: str, class_name: str) -> str:
    match = re.search(
        rf"^class {re.escape(class_name)}\(BaseModel\):\n(.*?)(?=^class |\n@router|\Z)",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, f"未找到 {class_name}"
    return match.group(1)


def test_risk_transition_registry_process_sources_are_exact():
    src = RISK_SERVICE.read_text(encoding="utf-8")
    assert "RISK_TRANSITIONS = {" in src
    assert re.search(
        r'"PROCESS": \{"from": \{"ASSIGNED", "PROCESSING"\}',
        src,
    )


def test_state_write_bodies_require_versions():
    src = ROUTER.read_text(encoding="utf-8")
    for body in (
        "RiskAssignBody", "RiskContentBody", "AidReviewBody", "AidObjectionReviewBody",
        "FundingReviewBody", "FundingAppealReviewBody", "ReasonBody", "LeagueStageBody",
        "CreditAppealReviewBody",
    ):
        assert re.search(r"version:\s*int\s*=\s*Field\(\.\.\.", _class_body(src, body)), body


def test_student_affairs_views_have_no_oversized_page_requests():
    for view in VIEWS.rglob("*.vue"):
        src = view.read_text(encoding="utf-8")
        assert not re.search(r"pageSize:\s*(?:300|500)\b", src), view


def test_risk_detail_does_not_claim_missing_handle_log():
    src = (VIEWS / "StudentAffairsRiskDetailView.vue").read_text(encoding="utf-8")
    assert "暂无处置留痕" not in src


def test_paginate_exposes_optional_status_counts():
    src = (ROOT / "app/core/response.py").read_text(encoding="utf-8")
    assert "status_counts: dict | None = None" in src
    assert 'data["statusCounts"] = status_counts' in src


def test_aid_workbench_uses_server_status_counts_not_current_page_counts():
    src = (VIEWS / "AidWorkbenchView.vue").read_text(encoding="utf-8")
    assert "statusCounts: null" in src
    assert "scoped.filter((x) => arr.includes(x.status)).length" not in src
    assert "this.statusCounts" in src


def test_metric_cards_never_count_current_page_with_filter():
    for view in VIEWS.rglob("*.vue"):
        src = view.read_text(encoding="utf-8")
        for block in re.findall(
            r"metricCards\(\)\s*\{(.*?)\n\s{4}\}(?=\n\s{4}(?:[A-Za-z_$][\w$]*\(\)|methods:|mounted\(\)))",
            src,
            flags=re.DOTALL,
        ):
            assert not re.search(r"\.filter\(\(.*?\.length", block, flags=re.DOTALL), view


def test_affairs_security_uses_dynamic_permission_grants():
    src = AFFAIRS_SECURITY.read_text(encoding="utf-8")
    assert "_db_granted" in src
    assert "ROLE_PERMISSIONS.get(role" not in src


def test_risk_owner_candidates_require_handle_permission():
    src = RISK_SERVICE.read_text(encoding="utf-8")
    body = src.split("def list_owner_candidates", 1)[1].split("def _validate_owner", 1)[0]
    assert "has_permission" in src
    assert "studentAffairs.risk.handle" in body or "studentAffairs.risk.handle" in src


def test_risk_mental_view_uses_permission_check():
    src = RISK_SERVICE.read_text(encoding="utf-8")
    body = src.split("def _can_view_mental", 1)[1].split("def _sensitive_view_audit", 1)[0]
    assert "has_permission" in body
    assert "studentAffairs.risk.psyDetail.view" in body
