"""逐页验证真实演示沙箱：所有四大业务域可点击集合页必须可访问且有数据。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


PREFIXES = ("/api/v1/student-affairs", "/api/v1/internship",
            "/api/v1/employment", "/api/v1/graduation")
SKIP_PARTS = ("/export", "/import/template", "/variables", "/options")


def _payload_nonempty(data) -> bool:
    if data is None:
        return False
    if isinstance(data, list):
        return bool(data)
    if not isinstance(data, dict):
        return True
    for key in ("items", "list", "records", "rows"):
        if key in data:
            return bool(data[key])
    # 看板/统计只要返回了结构化字段即视为有演示口径。
    return bool(data)


def run() -> int:
    with tempfile.TemporaryDirectory(prefix="sandbox-coverage-", ignore_cleanup_errors=True) as tmp:
        db_path = (Path(tmp) / "coverage.db").as_posix()
        os.environ["APP_ENV"] = "test"
        os.environ["DB_ENABLED"] = "true"
        os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
        os.environ["TEST_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"

        from fastapi.testclient import TestClient
        from app.db.base import metadata
        from app.db.session import get_engine, get_sessionmaker
        from app.main import app
        from scripts._seed_demo_school import seed_demo_school
        from scripts._seed_two_tenants import seed_two_tenants

        metadata.create_all(bind=get_engine())
        db = get_sessionmaker()()
        try:
            seed_demo_school(db)
            seed_two_tenants(db)
        finally:
            db.close()

        checked, failures, empty = [], [], []
        login_failed = None
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login",
                                json={"loginName": "admin2", "password": "123456"}).json()
            if login.get("code") != 0:
                login_failed = login
            else:
                headers = {"Authorization": "Bearer " + login["data"]["accessToken"]}
                for path, operations in sorted(app.openapi()["paths"].items()):
                    if not path.startswith(PREFIXES) or "get" not in operations or "{" in path:
                        continue
                    if any(part in path for part in SKIP_PARTS):
                        continue
                    required = [p for p in operations["get"].get("parameters", []) if p.get("required")]
                    if required:
                        continue
                    response = client.get(path, headers=headers)
                    item = {"path": path, "http": response.status_code}
                    try:
                        body = response.json()
                        item["code"] = body.get("code")
                        item["message"] = body.get("message")
                    except Exception:
                        body = None
                    checked.append(item)
                    if response.status_code != 200 or not isinstance(body, dict) or body.get("code") != 0:
                        failures.append(item)
                    elif not _payload_nonempty(body.get("data")):
                        empty.append(item)

        if login_failed is not None:
            print(json.dumps({"loginFailed": login_failed}, ensure_ascii=False, indent=2))
            get_engine().dispose()
            return 2

        from scripts._seed_sandbox_coverage import sandbox_flow_coverage_report
        db = get_sessionmaker()()
        try:
            coverage = sandbox_flow_coverage_report(db, 1000000000000000007)
            status_rows = {}
            if coverage["missing"]:
                from app.models import Base
                from sqlalchemy import select
                for missing in coverage["missing"]:
                    table = Base.metadata.tables[missing["table"]]
                    status_rows[missing["table"]] = [
                        {"id": str(row.id), "status": row.status}
                        for row in db.execute(select(table.c.id, table.c.status).where(
                            table.c.tenant_id == 1000000000000000007)).all()
                    ]
        finally:
            db.close()
        result = {"checked": len(checked), "failures": failures, "empty": empty,
                  "tableCoverage": {"covered": coverage["coveredCount"],
                                    "missing": coverage["missing"],
                                    "statusRows": status_rows}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        exit_code = 1 if failures or empty or coverage["missingCount"] else 0
        get_engine().dispose()
        return exit_code


if __name__ == "__main__":
    sys.exit(run())
