"""第三轮：风险 handles / allowedActions / 敏感审计契约。"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_risk_service_exposes_handles_and_allowed_actions():
    src = (ROOT / "app/services/affairs_risk_service.py").read_text(encoding="utf-8")
    assert "def list_handles(" in src
    assert "def _allowed_risk_actions(" in src
    assert 'row["allowedActions"]' in src or "row['allowedActions']" in src
    assert 'row["handles"]' in src or "row['handles']" in src
    # 强敏感审计不得吞异常后仍 reveal
    assert "except Exception" not in src.split("def _sensitive_view_audit")[1].split("def _row")[0]


def test_risk_handles_route_registered():
    src = (ROOT / "app/api/v1/student_affairs.py").read_text(encoding="utf-8")
    assert '/risk/records/{riskId}/handles' in src
    assert "list_handles" in src


def test_frontend_risk_detail_consumes_allowed_actions():
    vue = (ROOT.parent / "frontend/src/modules/studentAffairs/views/StudentAffairsRiskDetailView.vue").read_text(
        encoding="utf-8"
    )
    assert "canAct(" in vue
    assert "allowedActions" in vue
    assert "detail.handles" in vue
    assert "studentAffairs.risk.handle" in vue
    assert "studentAffairs.risk.process" not in vue
