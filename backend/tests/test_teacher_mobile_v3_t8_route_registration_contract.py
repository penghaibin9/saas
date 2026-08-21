from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t8_every_teacher_mini_registry_path_is_registered_in_pages_json():
    from app.services.todo_route_registry import route_contract_snapshot

    pages = json.loads(_src("miniapp/src/pages.json"))
    registered = {"/" + item["path"] for item in pages.get("pages", [])}
    for package in pages.get("subPackages", []):
        root = str(package.get("root") or "").strip("/")
        for item in package.get("pages", []):
            registered.add("/" + root + "/" + str(item["path"]).strip("/"))

    routes = route_contract_snapshot().get("teacherMini") or {}
    assert routes, "teacherMini registry must not be empty after T8"
    missing = sorted({item["path"] for item in routes.values()} - registered)
    assert missing == [], f"teacherMini registry contains unregistered miniapp paths: {missing}"
