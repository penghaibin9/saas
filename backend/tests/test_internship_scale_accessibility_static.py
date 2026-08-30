import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def function_source(path: str, name: str) -> str:
    source = read(path)
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_staff_dashboard_scopes_and_aggregates_in_sql_before_bounded_object_reads():
    body = function_source(
        "backend/app/modules/internship/services/internship_service.py",
        "get_dashboard_summary",
    )
    for token in (
        "apply_internship_record_scope",
        "scoped_id_select",
        ".group_by(InternshipRecord.status)",
        ".limit(5)",
        ".limit(4)",
        "work_candidates[:8]",
    ):
        assert token in body
    assert "recs = db.scalars(q).all()" not in body
    assert "for r in recs" not in body


def test_weekly_and_exception_queues_page_in_sql_without_batch_materialization():
    path = "backend/app/modules/internship/services/internship_service.py"
    for name in ("list_weekly_reports", "list_attendance_exceptions"):
        body = function_source(path, name)
        for token in (
            "apply_internship_record_scope",
            "select(func.count()).select_from(q.subquery())",
            ".offset(",
            ".limit(int(page_size))",
        ):
            assert token in body
        assert "batch_record_ids" not in body
        assert "_bulk_context" not in body
        assert "items[start:start + page_size]" not in body


def test_material_center_uses_one_current_version_aggregate_then_server_page():
    path = "backend/app/modules/internship/services/internship_material_center_service.py"
    body = function_source(path, "list_center")
    for token in (
        "material_stats = select(",
        "FileBinding.is_current.is_(True)",
        "FileVersion.is_current.is_(True)",
        "FileAsset.tenant_id == _tid()",
        "FileVersion.tenant_id == _tid()",
        "FileObject.tenant_id == _tid()",
        "select(func.count()).select_from(query.subquery())",
        ".offset((page - 1) * page_size).limit(page_size)",
    ):
        assert token in body
    assert "batch_record_ids" not in body
    assert "_current_rows" not in body


def test_archive_ledger_and_aggregates_read_committed_snapshots_without_per_student_rules():
    path = "backend/app/modules/internship/services/internship_archive_service.py"
    ledger = function_source(path, "list_by_student")
    aggregate = function_source(path, "_aggregate_committed_archive")
    for token in (
        "select(func.count()).select_from(query.subquery())",
        ".offset(",
        ".limit(int(page_size))",
        "_ledger_row(record, student, archive)",
    ):
        assert token in ledger
    assert "result = _row(" not in ledger
    assert "evaluate_internship_compliance" not in ledger
    assert "_scoped_records" not in ledger
    assert ".group_by(scoped.c.group_name)" in aggregate
    assert '"metricSource": "COMMITTED_ARCHIVE_SNAPSHOT"' in aggregate


def test_teacher_mini_queues_are_server_paged_and_sql_scoped():
    body = function_source("backend/app/services/_mobile_teacher_service_impl.py", "internship")
    for token in (
        "weekly_page=1",
        "exception_page=1",
        "page_size=20",
        "source_page, page_size, user=u",
        '"weeklyPendingTotal"',
        '"weeklyOverdueTotal"',
        '"exceptionHasMore"',
    ):
        assert token in body
    assert "scope_match_row" not in body
    assert "_advisor_map" not in read("backend/app/services/_mobile_teacher_service_impl.py")


def test_20k_runtime_probes_require_real_dataset_explain_query_latency_payload_and_browser_memory():
    scale = read("backend/scripts/measure_internship_v8_scale.py")
    browser = read("e2e/tools/measure-internship-v8-browser.mjs")
    for token in (
        "--minimum-records",
        "20_000",
        "queryCountMax",
        "p50Ms",
        "p95Ms",
        "payloadBytesMax",
        "pythonPeakBytes",
        "EXPLAIN FORMAT=JSON",
        "refusing 20K certification",
    ):
        assert token in scale
    for token in (
        "PerformanceObserver",
        "longtask",
        "resourceTransferBytes",
        "usedJSHeapBytes",
        "--enable-precise-memory-info",
    ):
        assert token in browser
