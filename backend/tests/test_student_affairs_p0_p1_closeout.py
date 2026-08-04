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


def test_application_projection_is_batch_loaded_not_per_row_queries():
    source = read("backend/app/services/affairs_student_contract_service.py")
    assert "def _batch_workflow_contexts" in source
    assert "def _batch_timelines" in source
    assert "def _batch_materials" in source
    block = source[source.index("def _build_my_applications"):source.index("def _patch_discipline_actions")]
    assert "_workflow_context(db" not in block
    assert "_timeline(db" not in block
    assert "_materials(db, biz_types=" not in block


def test_stats_integrity_guard_uses_sql_aggregates_instead_of_loading_full_rows():
    source = read("backend/app/services/affairs_stats_integrity_guard.py")
    for marker in ("def activity_stats", "def disbursement_stats", "def cockpit_view"):
        block = source[source.index(marker):]
        next_def = block.find("\n    def ", 1)
        if next_def > 0:
            block = block[:next_def]
        assert "func.count" in block
        assert "db.scalars(select(AffairsActivity)" not in block
        assert "db.scalars(select(FundingDisbursement)" not in block
        assert "db.scalars(package_stmt).all()" not in block
        assert "db.scalars(work_stmt).all()" not in block
        assert "db.scalars(family_stmt).all()" not in block


def test_funding_eligibility_has_versioned_tenant_and_project_rule_contract():
    funding = read("backend/app/services/affairs_funding_service.py")
    config = read("backend/app/services/effective_config_service.py")
    assert "AFFAIRS_FUNDING_ELIGIBILITY_JSON" in config
    assert "def _eligibility_rules" in funding
    assert '"ruleVersion"' in funding
    assert '"projectOverrides"' in funding
    assert "project.condition_json" in funding


def test_second_review_alembic_merge_is_single_declared_head():
    migration = read("backend/alembic/versions/20260804_merge_affairs_second_review_heads.py")
    assert 'revision = "20260804_affairs_r2_merge"' in migration
    assert 'down_revision = ("0169_change_management", "20260804_affairs_final_merge")' in migration


def test_archive_package_generation_is_leased_background_work_not_http_work():
    archive = read("backend/app/services/affairs_archive_service.py")
    model = read("backend/app/models/affairs_archive.py")
    scheduler = read("backend/scripts/run_scheduled_jobs.py")
    main = read("backend/app/main.py")
    collect_block = archive[archive.index("def collect"):archive.index("def advance")]
    assert "def _claim_pending_packages" in archive
    assert "def run_pending_packages" in archive
    assert "with_for_update(skip_locked=True)" in archive
    assert "_package_bytes(" not in collect_block
    assert "generation_lease_token" in model
    assert "generation_lease_until" in model
    assert "archive.run_pending_packages(limit=2)" in scheduler
    assert "affairs_archive_service.run_pending_packages(limit=2)" in main


def test_archive_queries_are_paginated_and_batch_loaded():
    archive = read("backend/app/services/affairs_archive_service.py")
    list_block = archive[archive.index("def list_batches"):archive.index("def create_batch")]
    collect_block = archive[archive.index("def collect"):archive.index("def advance")]
    detail_block = archive[archive.index("def get_batch"):]
    assert "select(func.count()).select_from(ArchiveBatch)" in list_block
    assert ".outerjoin(package_counts" in list_block
    assert ".offset((page - 1) * page_size)" in list_block
    assert "existing_ids = set(db.scalars(" in collect_block
    assert "db.get(StudentProfile" not in collect_block
    assert "students = {" in detail_block
    assert "db.get(StudentProfile" not in detail_block


def test_archive_async_migration_follows_second_review_merge():
    migration = read("backend/alembic/versions/20260804_affairs_archive_async.py")
    assert 'revision = "20260804_affairs_archive_async"' in migration
    assert 'down_revision = "20260804_affairs_r2_merge"' in migration


def test_second_review_pagination_actions_and_reconfirm_are_fail_closed():
    risk = read("backend/app/services/affairs_risk_service.py")
    risk_api = read("backend/app/api/v1/student_affairs.py")
    dorm_api = read("backend/app/api/v1/affairs_student_dorm.py")
    mini = read("miniapp/src/services/affairsContractApi.js")
    portal = read("student-portal/src/services/affairsFourEndApi.js")
    dorm_view = read("frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue")
    mental_view = read("frontend/src/modules/studentAffairs/views/mental/MentalReferralFollowView.vue")
    activity = read("backend/app/services/affairs_activity_service.py")
    router = read("backend/app/api/v1/router.py")
    assert "def list_owner_candidates" in risk
    assert ".offset((page - 1) * page_size).limit(page_size)" in risk
    assert "pageSize: int = Query(50, ge=1, le=100)" in risk_api
    assert '"hasMore": page * pageSize < total' in dorm_api
    assert "loadAllTransferPages" in mini and "loadAllTransferPages" in portal
    assert "Array.isArray(row.allowedActions) && row.allowedActions.includes(action)" in dorm_view
    assert "Array.isArray(row.allowedActions) ? row.allowedActions : []" in mental_view
    assert "FALLBACK_ACTIONS" not in mental_view
    assert 'event_stage = "ACTIVITY_RECONFIRMED"' in activity
    assert '"ACTIVITY_RECONFIRM" if restored' in activity
    assert "install_activity_reconfirm_guard" not in router


def test_counselor_assessment_collection_uses_batch_aggregates():
    source = read("backend/app/services/affairs_class_service.py")
    block = source[source.index("def collect_assessments"):source.index("def _recompute_ranks")]
    for token in (
        "select(SchoolClass.counselor_id, func.count(StudentProfile.id))",
        "select(SchoolClass.counselor_id, func.count(CsLeave.id))",
        "select(SchoolClass.counselor_id, func.count(AffairsRiskRecord.id))",
        "existing = {", "counselor_names = {",
    ):
        assert token in block
    assert "for counselor_id, cls in by_counselor.items()" not in block


def test_archive_admin_ui_exposes_async_package_states():
    source = read("frontend/src/modules/studentAffairs/views/ArchiveManageView.vue")
    for status in ("PENDING_GEN", "GENERATING", "PENDING_SUPPLEMENT", "SUBMITTED", "ARCHIVED"):
        assert status in source
    assert "已提交 ${res.data.packagesQueued" in source


def test_funding_extension_rules_are_formal_paginated_and_server_authoritative():
    router = read("backend/app/api/v1/router.py")
    service = read("backend/app/services/affairs_funding_ext_service.py")
    guard = read("backend/app/services/affairs_funding_ext_guard.py")
    api = read("backend/app/api/v1/student_affairs.py")
    assert "install_funding_ext_guard" not in router
    assert "Compatibility shim" in guard
    for token in (
        '"allowedActions": {', '"allowedActions": ["ADVANCE"]',
        "岗位录用人数已满", "累计补贴超过金额上限",
        ".offset((page - 1) * page_size).limit(page_size)", 'status_counts["ALL"]',
    ):
        assert token in service
    assert "pageSize: int = Query(50, ge=1, le=200)" in api


def test_class_and_funding_hot_lists_use_true_sql_pagination():
    class_service = read("backend/app/services/affairs_class_service.py")
    funding = read("backend/app/services/affairs_funding_service.py")
    for token in (
        "base.order_by(SchoolClass.id).offset(",
        "select(func.count()).select_from(AffairsClassMaterial)",
        "AffairsClassMaterial.id.desc()).offset((page - 1) * page_size).limit(page_size)",
    ):
        assert token in class_service
    for token in (
        "select(func.count()).select_from(FundingProject)",
        "FundingProject.id.desc()).offset((page - 1) * page_size).limit(page_size)",
        "select(func.count()).select_from(FundingBatch)",
        "FundingBatch.id.desc()).offset((page - 1) * page_size).limit(page_size)",
    ):
        assert token in funding


def test_counselor_evaluation_no_longer_depends_on_runtime_guard():
    router = read("backend/app/api/v1/router.py")
    service = read("backend/app/services/affairs_class_service.py")
    guard = read("backend/app/services/affairs_counselor_eval_guard.py")
    assert "install_counselor_eval_guard" not in router
    assert "Compatibility shim" in guard
    for token in (
        "def _allowed_counselor_ids", "expected_version = int(p.version or 0)",
        'raise AppException("NO_DATA_SCOPE"', 'scope_type != "TENANT_ALL"',
        'row.status != "SCORED" or row.college_score is None',
    ):
        assert token in service


def test_publicity_validation_and_serialized_scans_are_formal_services():
    router = read("backend/app/api/v1/router.py")
    guard = read("backend/app/services/affairs_publicity_guard.py")
    rules = read("backend/app/services/affairs_publicity_rules.py")
    aid = read("backend/app/services/affairs_aid_service.py")
    funding = read("backend/app/services/affairs_funding_service.py")
    assert "install_publicity_guard" not in router
    assert "Compatibility shim" in guard
    for token in ("正式公示天数应为1-30天", "学年格式应为YYYY-YYYY", "申请结束时间必须晚于开始时间"):
        assert token in rules
    assert "with_for_update(skip_locked=True)" in aid
    assert "with_for_update(skip_locked=True)" in funding


def test_credit_appeal_reliability_is_formal_service_not_runtime_patch():
    router = read("backend/app/api/v1/router.py")
    credit_guard = read("backend/app/services/affairs_credit_appeal_reliability.py")
    accounting_guard = read("backend/app/services/affairs_activity_accounting_guard.py")
    service = read("backend/app/services/affairs_activity_service.py")
    assert "install_credit_appeal_reliability" not in router
    assert "install_activity_accounting_guard" not in router
    assert "Compatibility shim" in credit_guard
    assert "Compatibility shim" in accounting_guard
    for token in (
        "def submit_credit_appeal",
        '_decimal(getattr(body, "claimValue", None), "主张数值")',
        "def review_credit_appeal",
        'adjustment = claim if appeal.appeal_type == "MISSING" else claim - current',
        "def unconfirm_activity",
        "撤销确认只追加冲正流水",
        'source="MANUAL_ADJUST"',
        "该记录已有待审核申诉",
        "require_submission_assignee",
        "sync_after_submit",
    ):
        assert token in service
    unconfirm = service[service.index("def unconfirm_activity"):service.index("def archive_activity")]
    assert "db.delete(" not in unconfirm
