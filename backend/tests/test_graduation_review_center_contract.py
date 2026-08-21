"""W7.0 architecture contracts: freeze authorities before Review Center construction."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_review_tasks_route_identity_is_preserved():
    routes = _read("frontend/src/modules/graduation/routes.js")
    assert "/admin/graduation/review-tasks" in routes
    assert "graduation-review-tasks" in routes
    assert "graduationDesign.review.view" in routes


def test_existing_gold_reader_remains_the_review_workspace_authority():
    final_view = _read("frontend/src/modules/graduation/views/FinalSubmissionListView.vue")
    workspace = _read("frontend/src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue")
    assert "GraduationDocumentReviewWorkspace" in final_view
    assert "AppDocumentViewer" in workspace
    assert "FileEvidencePanel" in workspace


def test_w7_does_not_introduce_second_review_or_file_authority():
    model_source = _read("backend/app/models/graduation.py")
    guard_source = _read("backend/app/modules/graduation/services/graduation_review_version_guard.py")
    assert "class ReviewTask" not in model_source
    assert "class ReviewRecord" not in model_source
    assert "class ReviewFile" not in model_source
    assert "GraduationReview" in guard_source
    assert "GraduationStudentMaterial" in guard_source
    assert "FileVersion" in guard_source
    assert "FileObject" in guard_source


def test_no_universal_review_center_write_endpoint_exists():
    review_router = _read("backend/app/modules/graduation/routers/graduation_review.py")
    assert "/review-center/submit" not in review_router
    assert "/gd-reviews/{rid}/submit" in review_router
