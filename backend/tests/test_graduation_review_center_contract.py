from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w73_review_center_is_read_only_projection():
    router = _read("app/modules/graduation/routers/graduation_review_center.py")
    service = _read("app/modules/graduation/services/graduation_review_center_service.py")
    assert 'APIRouter(prefix="/review-center"' in router
    assert '@router.get("/summary"' in router
    assert '@router.get("/tasks"' in router
    assert '@router.get("/tasks/{case_type}/{record_id}"' in router
    assert "@router.post" not in router
    assert "/review-center/submit" not in router
    assert "read-only" in service


def test_w73_queue_contract_exposes_required_case_and_evidence_fields():
    service = _read("app/modules/graduation/services/graduation_review_center_service.py")
    for case_type in ("PROPOSAL", "FINAL_DRAFT", "FINAL", "FORMAL_REVIEW"):
        assert case_type in service
    for field in (
        "caseKey", "caseType", "recordId", "batchId", "gdStudentId",
        "studentNo", "studentName", "className", "majorId", "topicTitle", "advisorName",
        "reviewerName", "statusGroup", "fileId", "fileVersionId", "versionNo",
        "sourceSha256", "reviewReady", "versionConflict", "blockingReasons",
        "latestFeedback", "allowedActions",
    ):
        assert f'"{field}"' in service
    for group in ("WAITING", "IN_REVIEW", "RETURNED", "DONE", "BLOCKED"):
        assert group in service


def test_w73_projection_batches_material_file_and_feedback_queries():
    service = _read("app/modules/graduation/services/graduation_review_center_service.py")
    assert "GraduationStudentMaterial.gd_student_id.in_(record_student_ids or [-1])" in service
    assert "FileVersion.id.in_(version_ids or [-1])" in service
    assert "FileObject.id.in_(file_object_ids or [-1])" in service
    assert "SELECT * FROM t_gd_review_feedback" in service
    assert "_feedback_indexes(feedback_rows)" in service
    assert "for row in proposals:" in service
    assert "for row in finals:" in service
    assert "for row in reviews:" in service


def test_w73_detail_contains_version_history_feedback_plagiarism_and_blockers():
    service = _read("app/modules/graduation/services/graduation_review_center_service.py")
    for field in (
        "canonicalFile", "frozenFile", "versionHistory", "feedbackHistory",
        "plagiarism", "blockers", "allowedActions",
    ):
        assert f'"{field}"' in service
    assert "CANONICAL_VERSION_CHANGED" in service
    assert "FROZEN_EVIDENCE_MISSING" in service
    assert "PLAGIARISM_PENDING" in service
    assert "PLAGIARISM_BLOCKED" in service


def test_w73_router_is_attached_under_sensitive_graduation_gate():
    init_source = _read("app/modules/graduation/routers/__init__.py")
    permissions = _read("app/modules/graduation/services/graduation_permission_extensions.py")
    assert "graduation_sensitive_router" in init_source
    assert "graduation_review_center" in init_source
    assert "graduation_sensitive_router.router.include_router(graduation_review_center.router)" in init_source
    assert 'module = "graduation_review_center"' in permissions
    assert '"graduationDesign.review.view"' in permissions
    for endpoint in ("review_center_summary", "review_center_tasks", "review_center_detail"):
        assert f'"{endpoint}"' in permissions
