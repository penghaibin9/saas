"""A3 封板前治理合同：不靠提高预算或改名绕过 runtime-installer 门禁。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_returned_aid_projection_is_formal_service_logic_not_runtime_patch():
    router = _read("backend/app/api/v1/router.py")
    mobile = _read("backend/app/services/mobile_affairs_service.py")
    legacy_shim = _read("backend/app/services/affairs_returned_view_service.py")

    assert "install_returned_view_projection" not in router
    assert '"DRAFT": "已退回待修改"' in mobile
    assert 'x.status in {"DRAFT", "RETURNED"}' in mobile
    assert "affairs.aid_my =" not in legacy_shim


def test_runtime_installer_budget_is_not_relaxed_for_closeout():
    audit = _read("scripts/audit_student_affairs_surface.py")
    assert '"runtimeInstallerBudget": 27' in audit or "runtime_installer_budget = 27" in audit
