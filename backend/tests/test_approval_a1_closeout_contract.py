from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_returned_rectify_filter_is_database_first_and_formal_route_uses_it():
    routes = read("backend/app/api/v1/approval.py")
    service = read("backend/app/services/approval_returned_service.py")

    assert "approval_returned_service as returnedsvc" in routes
    returned_route = routes.split('@router.get("/tasks/returned"', 1)[1].split(
        '@router.get("/transfer-targets"', 1
    )[0]
    assert "returnedsvc.list_returned" in returned_route
    assert "runtime.list_returned" not in returned_route

    # rectifyStatus 必须先转成 SQL 条件，再 COUNT，再 OFFSET/LIMIT；禁止页内 Python 二次过滤。
    assert 'wanted == "PENDING_RESUBMIT"' in service
    assert 'wanted == "RESUBMITTED"' in service
    assert 'wanted == "CLOSED"' in service
    assert "count_q =" in service
    assert ".offset(" in service
    assert ".limit(" in service
    assert "rows = [x for x in rows if" not in service
    assert service.index('wanted == "PENDING_RESUBMIT"') < service.index("count_q =")
    assert service.index("count_q =") < service.index(".offset(")


def test_export_formal_route_is_persisted_background_lifecycle():
    routes = read("backend/app/api/v1/approval.py")
    service = read("backend/app/services/approval_export_service.py")

    export_route = routes.split('@router.post("/export"', 1)[1].split(
        '@router.get("/export/{task_id}"', 1
    )[0]
    assert "BackgroundTasks" in routes
    assert "exportsvc.create_job" in export_route
    assert "background_tasks.add_task" in export_route
    assert "exportsvc.run_job" in export_route
    assert "adminsvc.create_export" not in export_route

    # POST 先创建 PENDING；后台任务再落 RUNNING/SUCCESS/FAILED。
    assert 'status="PENDING"' in service
    assert 'task.status = "RUNNING"' in service
    assert 'task.status = "SUCCESS"' in service
    assert 'task.status = "FAILED"' in service
    assert service.index('status="PENDING"') < service.index('task.status = "RUNNING"')
    assert service.index('task.status = "RUNNING"') < service.index('task.status = "SUCCESS"')

    # 必须可查任务状态；未成功时下载必须 fail-closed。
    assert '@router.get("/export/{task_id}"' in routes
    assert "exportsvc.get_job" in routes
    assert 'status != "SUCCESS"' in service
    assert '"APPROVAL_EXPORT_NOT_READY"' in service
    assert "exportsvc.export_file_path" in routes
    assert "adminsvc.export_file_path" not in routes


def test_background_export_restores_request_tenant_and_user_context():
    service = read("backend/app/services/approval_export_service.py")
    assert "set_tenant(dict(tenant or {}))" in service
    assert "set_current_user(dict(user or {}))" in service
    assert "set_tenant(previous_tenant)" in service
    assert "set_current_user(previous_user)" in service
