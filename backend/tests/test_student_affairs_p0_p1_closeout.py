"""学工 P0/P1 收口静态门禁。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_permission_registry_and_generated_catalog_are_zero_drift():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "scripts/audit_student_affairs_surface.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_key_security_rules_no_longer_depend_on_router_install_order():
    router = read("backend/app/api/v1/router.py")
    for installer in (
        "install_teacher_workbench_guard", "install_self_scope_guard",
        "install_sensitive_audit_guard", "install_aid_list_argument_guard",
        "install_counselor_handover_guard",
    ):
        assert installer not in router


def test_student_affairs_action_contract_has_no_legacy_can_flags():
    paths = [
        "backend/app/services/mobile_affairs_service.py",
        "backend/app/services/affairs_four_end_contract.py",
        "backend/app/services/affairs_returned_view_service.py",
        "student-portal/src/views/affairs/AffairsFourEndView.vue",
        "miniapp/src/pages/student/affairs/leave.vue",
        "miniapp/src/pages/student/affairs/aid.vue",
        "miniapp/src/pages/student/affairs/funding.vue",
        "miniapp/src/pages/student/affairs/discipline.vue",
    ]
    text = "\n".join(read(path) for path in paths)
    for field in ("canResubmit", "canObject", "canAppeal", "canCancel", "canExtend"):
        assert field not in text
    assert "allowedActions" in text


def test_pagination_no_longer_uses_reported_fixed_caps():
    candidates = read("backend/app/api/v1/affairs_four_end.py")
    activities = read("backend/app/services/affairs_activity_reliability_service.py")
    mini_contract = read("miniapp/src/services/affairsContractApi.js")
    assert "limit: int = 200" not in candidates
    assert ".limit(500)" not in activities
    assert "page=1&pageSize=100" not in mini_contract
    assert "page: 1, pageSize: 50" not in mini_contract


def test_leave_export_is_async_and_external_scheduler_runs_it():
    leave = read("backend/app/services/affairs_leave_service.py")
    export = read("backend/app/services/affairs_leave_export_service.py")
    scheduler = read("backend/scripts/run_scheduled_jobs.py")
    route = read("backend/app/api/v1/student_affairs.py")
    assert "page_size=1_000_000" not in leave
    assert 'status="CREATED"' in export
    assert "page_size=_PAGE_SIZE" in export
    assert "job_student_affairs_background" in scheduler
    assert "leave_export.run_pending" in scheduler
    assert "/leave/export-jobs/{jobId}" in route


def test_appeal_repair_uses_dedicated_lease_job_and_external_scheduler():
    repair = read("backend/app/services/affairs_appeal_repair_service.py")
    scheduler = read("backend/scripts/run_scheduled_jobs.py")
    assert "AffairsRepairJob" in repair
    assert "lease_until <= now" in repair
    assert "IdempotencyRecord" not in repair
    assert "repair.repair_pending" in scheduler


def test_appeal_todo_contract_is_explicit_not_runtime_replacement():
    router = read("backend/app/api/v1/router.py")
    todo = read("backend/app/services/affairs_appeal_todo_service.py")
    scheduler = read("backend/app/services/affairs_appeal_repair_scheduler.py")
    assert "install_appeal_todo_reconciliation" not in router
    for assignment in (
        "aid.submit_objection =", "aid.review_objection =",
        "funding.submit_appeal =", "funding.review_appeal =",
        "discipline.submit_appeal =", "discipline.review_appeal =",
        "activity.submit_credit_appeal =", "activity.review_credit_appeal =",
    ):
        assert assignment not in todo
    assert "_wrap_periodic" not in scheduler
    for path in (
        "backend/app/services/affairs_aid_service.py",
        "backend/app/services/affairs_funding_service.py",
        "backend/app/services/affairs_discipline_service.py",
        "backend/app/services/affairs_activity_service.py",
    ):
        assert "sync_after_submit" in read(path)
        assert "sync_after_review" in read(path)


def test_activity_rate_limit_has_dedicated_audit_semantics():
    source = read("backend/app/services/affairs_activity_code_service.py")
    assert "IdempotencyRecord" not in source
    assert "SecurityAuditLog" in source
    assert "AFFAIRS_ACTIVITY_CHECKIN_ATTEMPT" in source
    assert "with_for_update" in source


def test_stats_are_database_aggregations_not_full_python_scans():
    targets = {
        "backend/app/services/affairs_aid_service.py": "def aid_stats",
        "backend/app/services/affairs_funding_service.py": "def funding_stats",
        "backend/app/services/affairs_discipline_service.py": "def discipline_stats",
        "backend/app/services/affairs_activity_service.py": "def activity_stats",
    }
    for path, marker in targets.items():
        source = read(path)
        block = source[source.index(marker):]
        next_def = block.find("\ndef ", 1)
        if next_def > 0:
            block = block[:next_def]
        assert ".group_by(" in block
        assert "for x in rows" not in block
        assert "for a in acts" not in block


def test_archive_timeline_is_complete_and_dorm_dead_code_is_removed():
    archive = read("backend/app/services/affairs_archive_service.py")
    dorm = read("backend/app/services/affairs_dorm_service.py")
    assert "while True:" in archive
    assert "len(timeline) >= int(total or 0)" in archive
    assert "from app.core.permissions import is_super_admin" not in dorm[dorm.index("def _dorm_scope_building_ids"):dorm.index("# ═", dorm.index("def _dorm_scope_building_ids"))]


def test_leave_export_worker_keeps_explicit_tenant_ownership():
    source = read("backend/app/services/affairs_leave_export_service.py")
    assert "def _finish(job_id: int, tenant_id: int" in source
    assert "int(row.tenant_id) != int(tenant_id)" in source
    assert "previous_tenant = get_tenant()" in source
    assert "set_tenant(previous_tenant)" in source


def test_aid_and_funding_appeal_lists_use_true_sql_pagination_without_n_plus_one():
    for path, marker in (
        ("backend/app/services/affairs_aid_service.py", "def list_objections"),
        ("backend/app/services/affairs_funding_service.py", "def list_appeals"),
    ):
        source = read(path)
        block = source[source.index(marker):]
        next_def = block.find("\ndef ", 1)
        if next_def > 0:
            block = block[:next_def]
        assert "select(func.count())" in block
        assert ".offset((page - 1) * page_size).limit(page_size)" in block
        assert "db.get(StudentProfile" not in block
