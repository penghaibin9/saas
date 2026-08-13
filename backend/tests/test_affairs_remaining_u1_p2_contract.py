from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_material_history_is_server_paginated_and_focusable():
    router = _read("backend/app/api/v1/affairs_operations_api.py")
    service = _read("backend/app/modules/student_affairs/services/affairs_material_center_service.py")
    assert "requirementId: Optional[int]" in router
    assert "pageSize: int = Query(20" in router
    assert "return success(paginate(items, total, page, pageSize))" in router
    assert ".offset((page - 1) * page_size).limit(page_size)" in service
    assert "AffairsMaterialRequirement.student_id == int(student.id)" in service


def test_archive_collect_preview_reuses_formal_scope_and_does_not_claim_version():
    api = _read("backend/app/api/v1/student_affairs.py")
    service = _read("backend/app/services/affairs_archive_service.py")
    assert '"/archive/batches/{batchId}/collect-preview"' in api
    preview = service[service.index("def preview_collect"):service.index("def collect(")]
    assert "_collect_candidates" in preview
    assert "check_version(batch.version, expected_version)" in preview
    assert "atomic_claim_version" not in preview
    assert "db.commit()" not in preview


def test_activity_exception_priority_remains_scope_filtered_and_server_backed():
    service = _read("backend/app/services/affairs_activity_reliability_service.py")
    core = _read("backend/app/services/affairs_activity_service.py")
    assert 'str(priority or "").upper() == "EXCEPTION"' in service
    assert "base_conds, exception_predicate" in service
    assert 'status_counts["EXCEPTION"]' in service
    assert "model.status == \"FINISHED\"" in core
