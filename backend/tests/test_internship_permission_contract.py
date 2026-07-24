"""Static guard for route permission keys shared by the SPA and API."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTERS = ROOT / "app" / "modules" / "internship" / "routers"

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
