from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w74_has_dedicated_gold_center_route_and_reuses_reader():
    routes = text("frontend/src/modules/graduation/routes.js")
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")
    workspace = text("frontend/src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue")

    assert "path: 'review-tasks'" in routes
    assert "GraduationReviewCenterView.vue" in routes
    assert "GraduationDefenseGradeView.vue" not in routes.split("path: 'review-tasks'", 1)[1].split("},", 1)[0]
    assert "GraduationDocumentReviewWorkspace" in view
    assert "queue-title=\"统一评阅队列\"" in view
    assert "queueTitle" in workspace
    assert "window.open" not in view
    assert "target=\"_blank\"" not in view
    assert "downloadMaterial(" not in view


def test_w74_has_summary_filters_continuous_queue_and_version_locked_drafts():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

    for token in (
        "pending", "inReview", "returned", "doneToday", "overdue", "avgHours",
        "caseType", "statusGroup", "keyword", "reviewerOnly", "autoNext",
        "PROPOSAL", "FINAL_DRAFT", "FINAL", "FORMAL_REVIEW",
        "blockingReasons", "versionConflict", "feedbackHistory",
    ):
        assert token in view
    assert "gd-review-center-draft:v1" in view
    assert "caseKey" in view and "targetFileVersionId" in view
    assert "sessionStorage" in view
    assert "afterMutation" in view
    assert "openStudentDossier" in view
    assert "w74-modal" in view


def test_w74_review_center_is_read_only_projection_and_writes_stay_canonical():
    api = text("frontend/src/modules/graduation/api/graduation-review-center.api.js")
    backend = text("backend/app/modules/graduation/routers/graduation_review_center.py")

    assert "const CENTER = '/graduation/review-center'" in api
    assert "`${CENTER}/summary`" in api
    assert "`${CENTER}/tasks`" in api
    assert "method: 'POST'" not in "\n".join(
        line for line in api.splitlines() if "CENTER" in line or "review-center" in line
    )
    for canonical in (
        "`${PROPOSAL}/${encodeURIComponent(recordId)}/review`",
        "`${FINAL}/${encodeURIComponent(recordId)}/review`",
        "`${FORMAL}/${encodeURIComponent(recordId)}/submit`",
        "`${FORMAL}/${encodeURIComponent(recordId)}/return`",
    ):
        assert canonical in api
    assert "expectedVersion" in api and "fileVersionId" in api
    assert "categories" in api and "issues" in api
    assert "@router.post" not in backend
    assert "All mutations intentionally stay on the canonical" in backend


def test_w74_formal_read_context_exposes_w7_lock_fields_and_conflict_code():
    api = text("frontend/src/modules/graduation/api/graduation-review-center.api.js")
    overlay = text("backend/app/modules/graduation/routers/graduation_review_w7_router.py")
    read_service = text("backend/app/modules/graduation/services/graduation_review_read_service.py")

    assert "review_read.list_reviews" in overlay
    assert "closure._row(db, row" in read_service
    for token in ("version", "materialId", "fileVersionId", "sourceSha256"):
        assert token in read_service or token in api
    assert "row.version == null || row.fileVersionId == null" in api
    assert "function canonicalWrite" in api
    assert "error?.bizCode" in api and "error.code = error.bizCode" in api
