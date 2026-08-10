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

    # rectifyStatus 必须先进入 SQL 条件，再 COUNT，再 OFFSET/LIMIT；禁止页内 Python 二次过滤。
    assert 'wanted == "PENDING_RESUBMIT"' in service
    assert 'wanted == "RESUBMITTED"' in service
    assert 'wanted == "CLOSED"' in service
    assert "count_q =" in service
    assert ".offset(" in service
    assert ".limit(" in service
    assert "rows = [x for x in rows if" not in service
    assert service.index('wanted == "PENDING_RESUBMIT"') < service.index("count_q =")
    assert service.index("count_q =") < service.index(".offset(")


def test_export_formal_route_uses_unified_export_job_not_request_thread_generation():
    routes = read("backend/app/api/v1/approval.py")
    service = read("backend/app/services/approval_export_service.py")

    export_route = routes.split('@router.post("/export"', 1)[1].split(
        '@router.get("/export/{task_id}"', 1
    )[0]
    assert "exportsvc.create_job" in export_route
    assert "adminsvc.create_export" not in export_route
    assert "BackgroundTasks" not in routes
    assert "background_tasks.add_task" not in routes

    assert "ExportJob" in service
    assert 'status="CREATED"' in service
    assert 'row.status = "RUNNING"' in service
    assert 'row.status = "SUCCEEDED"' in service
    assert 'row.status = "DEAD"' in service
    assert 'ExportJob.status.in_(("CREATED", "FAILED"))' in service
    assert "with_for_update(skip_locked=True)" in service
    assert '"leaseToken"' in service
    assert "_write_generated_file" in service


def test_export_worker_is_scheduler_driven_retryable_and_ticket_downloaded():
    routes = read("backend/app/api/v1/approval.py")
    service = read("backend/app/services/approval_export_service.py")
    main = read("backend/app/main.py")

    assert "approval_export_service.run_pending" in main
    assert 'worker_id=f"web-approval:{tenant_id}"' in main
    assert "def run_pending(" in service
    assert "attempts >= _MAX_ATTEMPTS" in service
    assert 'ExportJob.status == "RUNNING"' in service
    assert "ExportJob.updated_at <= stale_before" in service

    assert '@router.get("/export/{task_id}"' in routes
    assert "exportsvc.get_job" in routes
    assert '@router.post("/export/{task_id}/download-ticket"' in routes
    assert "exportsvc.create_download_ticket" in routes
    assert '@router.get("/export/{task_id}/download"' in routes
    assert "exportsvc.consume_download_ticket" in routes
    assert "adminsvc.export_file_path" not in routes


def test_export_generation_restores_tenant_and_user_context():
    service = read("backend/app/services/approval_export_service.py")
    assert 'set_tenant({"tenantId": str(tenant_id)})' in service
    assert "set_current_user(user)" in service
    assert "set_tenant(previous_tenant)" in service
    assert "set_current_user(previous_user)" in service


def test_approval_export_file_capability_is_registered():
    inventory = read("docs/architecture/file-capability-inventory.d/10-approval-center-export.yaml")
    assert "backend/app/api/v1/approval.py" in inventory
    assert "backend/app/services/approval_export_service.py" in inventory
    assert "one-time-ticket" in inventory
    assert "scanGated: true" in inventory
