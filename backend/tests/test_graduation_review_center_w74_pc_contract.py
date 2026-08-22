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


def test_w74_backend_allowed_actions_and_reviewer_scope_are_actor_authoritative():
    contract = text("backend/app/modules/graduation/services/graduation_review_center_contract_service.py")
    summary = text("backend/app/modules/graduation/services/graduation_review_center_summary_service.py")

    # Write affordances are projected from backend permission authority, not guessed by the PC.
    for code in (
        "graduationDesign.proposal.review",
        "graduationDesign.final.review",
        "graduationDesign.review.submit",
        "graduationDesign.review.return",
    ):
        assert f'has_permission(user, "{code}")' in contract
    assert 'result["allowedActions"] = _allowed_actions(result, actor)' in contract
    assert 'status in {"ASSIGNED", "REVIEWING", "RETURNED"}' in contract
    assert 'and _formal_submit_owned(item, actor)' in contract
    assert 'return ["SUBMIT"]' in contract
    assert 'return ["RETURN"]' in contract
    assert '"START"' not in contract

    # GD_REVIEWER is task-scoped. Stable reviewerMentorId is mandatory for list/summary/detail;
    # relation to the same student must not expose another reviewer's task or other case types.
    assert 'if actor["role"] == "GD_REVIEWER":' in contract
    assert 'reviewer_only = True' in contract
    assert 'return [], 0' in contract
    assert "_assert_reviewer_detail_scope" in contract
    assert '_deny_reviewer_detail()' in contract
    assert 'summary_query.summary(batch_id, reviewer_mentor_id=reviewer_id)' in contract
    assert "reviewer_mentor_id=:reviewer_mentor_id" in summary
    assert "WHERE case_type='FORMAL_REVIEW'" in summary


def test_w74_reviewer_detail_authorizes_before_sensitive_hydration():
    contract = text("backend/app/modules/graduation/services/graduation_review_center_contract_service.py")

    assert "def _preflight_reviewer_detail_scope" in contract
    assert "GraduationReview.reviewer_mentor_id == int(reviewer_id)" in contract
    assert "GraduationStudent.batch_id == int(batch_id)" in contract
    assert 'GraduationStudent.record_status == "ACTIVE"' in contract
    assert "GraduationStudent.tenant_id == GraduationReview.tenant_id" in contract
    detail_body = contract.split("def detail(*,", 1)[1]
    assert detail_body.index("_preflight_reviewer_detail_scope(") < detail_body.index("query.detail(")
    assert detail_body.index("query.detail(") < detail_body.index("_assert_reviewer_detail_scope(")


def test_w74_pc_consumes_backend_allowed_actions_and_mutations_fail_closed_by_case():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

    # Backend allowedActions is the action authority. The page must not independently
    # reconstruct permissionCode decisions and drift from the server projection.
    assert "matchPermission" not in view
    assert "permissionPatterns()" not in view
    assert "writePermission()" not in view
    assert "hasWritePermission()" not in view
    assert "allowedActions()" in view
    assert "this.allowedActions.includes('REVIEW')" in view
    assert "this.allowedActions.includes('SUBMIT')" in view
    assert "this.allowedActions.includes('RETURN')" in view
    assert 'v-if="canSubmitFormal"' in view
    assert 'v-else-if="canReviewBusiness"' in view
    assert 'v-if="canReturnFormalAction"' in view

    # Method-level guards prevent a stale/incorrect event binding from crossing case types.
    assert "if (!this.canReviewBusiness || !this.canSubmitCurrent || this.submitting) return" in view
    assert "if (!['APPROVE', 'REJECT'].includes(action))" in view
    assert "if (!['PROPOSAL', 'FINAL', 'FINAL_DRAFT'].includes(type)) return" in view
    assert "if (!this.canSubmitFormal || !this.canSubmitCurrent || this.submitting) return" in view
    assert "if (!this.canReturnFormal || this.submitting) return" in view
