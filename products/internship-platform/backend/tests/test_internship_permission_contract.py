"""Static guard: SPA internship route permissionKey must match backend action codes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPA_ROUTES = ROOT / "frontend" / "src" / "modules" / "internship" / "routes.js"
ROUTERS = ROOT / "backend" / "app" / "modules" / "internship" / "routers"

# path fragment → expected permissionKey for view/manage split
SPA_ROUTE_PERMISSIONS = {
    "path: 'reports'": "internship.report.view",
    "path: 'reports/:id'": "internship.report.view",
    "path: 'process-reports/:id'": "internship.report.view",
    "path: 'guidance/new'": "internship.guidance.manage",
    "path: 'enterprises/new'": "internship.enterprise.manage",
    "path: 'enterprises/:id/edit'": "internship.enterprise.manage",
    "path: 'positions/new'": "internship.position.manage",
    "path: 'positions/:id/edit'": "internship.position.manage",
    "path: 'enterprise-evals/new'": "internship.eval.enterprise.manage",
    "path: 'leaves'": "internship.leave.view",
}

CRITICAL_ROUTER_PERMISSIONS = {
    "internship_application.py": "internship.application.view",
    "internship_process.py": "internship.change.view",
    "internship_plan.py": "internship.plan.view",
    "internship.py": "internship.visit.view",
}


def test_critical_route_permission_contract_strings_exist():
    for filename, permission in CRITICAL_ROUTER_PERMISSIONS.items():
        assert permission in (ROUTERS / filename).read_text(encoding="utf-8"), (
            f"{filename} must retain {permission} for SPA route contract")


def test_spa_route_permission_keys_view_manage_split():
    text = SPA_ROUTES.read_text(encoding="utf-8")
    for marker, permission in SPA_ROUTE_PERMISSIONS.items():
        idx = text.find(marker)
        assert idx >= 0, f"missing route marker {marker}"
        window = text[idx: idx + 450]
        assert f"permissionKey: '{permission}'" in window, (
            f"{marker} must use permissionKey={permission}, got window:\n{window}")
