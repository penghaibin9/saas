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
    detail_service = text("backend/app/modules/graduation/services/graduation_review_center_detail_service.py")

    assert "review_read.list_reviews" in overlay
    assert "closure._row(db, row" in read_service
    for token in ("version", "materialId", "fileVersionId", "sourceSha256"):
        assert token in read_service or token in api or token in detail_service
    assert "GraduationReview.version" in detail_service
    assert 'case["version"] = int(version_row.version or 0)' in detail_service
    assert "row.version == null || row.fileVersionId == null" in api
    assert "function canonicalWrite" in api
    assert "error?.bizCode" in api and "error.code = error.bizCode" in api


def test_w74_legacy_formal_read_is_stable_reviewer_task_scoped():
    read_service = text("backend/app/modules/graduation/services/graduation_review_read_service.py")

    assert 'reviewer_role = _role() == "GD_REVIEWER"' in read_service
    assert "mentor = gid.current_user_mentor(db)" in read_service
    assert "if mentor is None:" in read_service
    assert "GraduationReview.reviewer_mentor_id == int(mentor.id)" in read_service
    assert "GraduationStudent.tenant_id == GraduationReview.tenant_id" in read_service
    assert 'GraduationStudent.record_status == "ACTIVE"' in read_service
    reviewer_branch = read_service.split("if reviewer_role:", 1)[1].split("scope_ids = accessible_student_ids", 1)[0]
    assert "reviewer_name" not in reviewer_branch


def test_w74_formal_write_context_uses_task_scoped_detail_not_student_wide_list():
    api = text("frontend/src/modules/graduation/api/graduation-review-center.api.js")
    formal = api.split("if (type === 'FORMAL_REVIEW') {", 1)[1].split("throw new Error(`不支持的评阅类型", 1)[0]

    assert "pageSize: 200" not in formal
    assert "gdStudentId: task.gdStudentId" not in formal
    assert "request(FORMAL" not in formal
    assert "async writeContext(task = {}, detailData = null)" in api
    assert "const data = detailData || await request(" in formal
    assert "`${CENTER}/tasks/${encodeURIComponent(type)}/${encodeURIComponent(recordId)}`" in formal
    assert "const row = data?.case" in formal
    assert "String(row.recordId) !== String(recordId)" in formal


def test_w74_backend_allowed_actions_and_reviewer_scope_are_actor_authoritative():
    contract = text("backend/app/modules/graduation/services/graduation_review_center_contract_service.py")
    summary = text("backend/app/modules/graduation/services/graduation_review_center_summary_service.py")

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
    assert detail_body.index("_preflight_reviewer_detail_scope(") < detail_body.index("detail_query.detail(")
    assert detail_body.index("detail_query.detail(") < detail_body.index("_assert_reviewer_detail_scope(")


def test_w74_reviewer_scope_is_set_based_and_detail_hydrates_proven_batch():
    scope = text("backend/app/modules/graduation/services/graduation_review_center_scope_service.py")
    detail = text("backend/app/modules/graduation/services/graduation_review_center_detail_service.py")
    priority = text("backend/app/modules/graduation/services/graduation_review_center_priority_service.py")
    summary = text("backend/app/modules/graduation/services/graduation_review_center_summary_service.py")
    contract = text("backend/app/modules/graduation/services/graduation_review_center_contract_service.py")

    assert "def reviewer_student_ids" in scope
    assert "GraduationReview.reviewer_mentor_id == reviewer_id" in scope
    assert "GraduationReview.gd_student_id == GraduationStudent.id" in scope
    assert ".distinct()" in scope
    assert "reviewer_student_ids(" in priority
    assert "reviewer_student_ids(" in summary
    assert "reviewer_student_ids(" in detail
    assert 'row = {**dict(raw), "batch_id": int(batch_id)}' in detail
    assert 'where += " AND reviewer_mentor_id=:reviewer_mentor_id"' in detail
    assert "graduation_review_center_detail_service as detail_query" in contract
    assert "detail_query.detail(" in contract
    assert "graduation_review_center_query_service as query" not in contract


def test_w74_pc_consumes_backend_allowed_actions_and_mutations_fail_closed_by_case():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

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

    assert "if (!this.canReviewBusiness || !this.canSubmitCurrent || this.submitting) return" in view
    assert "if (!['APPROVE', 'REJECT'].includes(action))" in view
    assert "if (!['PROPOSAL', 'FINAL', 'FINAL_DRAFT'].includes(type)) return" in view
    assert "if (!this.canSubmitFormal || !this.canSubmitCurrent || this.submitting) return" in view
    assert "if (!this.canReturnFormal || this.submitting) return" in view


def test_w74_pc_async_reads_are_latest_wins_and_dossier_is_context_bound():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

    assert "loadToken: 0, selectionToken: 0, dossierToken: 0" in view
    assert "const token = ++this.loadToken" in view
    assert "if (token !== this.loadToken) return false" in view
    assert "if (token === this.loadToken) this.loading = false" in view
    assert "++this.selectionToken" in view.split("resetSelection()", 1)[1].split("async selectTask", 1)[0]
    assert "detailPromise.then((detail) => graduationReviewCenterApi.writeContext(task, detail))" in view

    dossier = view.split("async openStudentDossier", 1)[1].split("closeDossier()", 1)[0]
    assert "const token = ++this.dossierToken" in dossier
    assert "token !== this.dossierToken || !this.dossierOpen" in dossier
    assert "catch (error)" in dossier
    assert "finally" in dossier
    assert "if (token === this.dossierToken) this.dossierLoading = false" in dossier
    close = view.split("closeDossier()", 1)[1]
    assert "++this.dossierToken" in close
    assert "this.dossierOpen = false; this.dossierLoading = false" in close


def test_w74_pc_locks_task_context_for_entire_canonical_mutation():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")
    workspace = text("frontend/src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue")

    # Shared workspace must finally consume its submitting prop; otherwise a successful
    # mutation for A can finish while the user has switched the UI to B.
    assert ':class="{ \'is-active\': index === currentIndex }" :disabled="submitting"' in workspace
    assert ':disabled="submitting || currentIndex <= 0"' in workspace
    assert ':disabled="submitting || currentIndex >= queue.length - 1"' in workspace
    assert ':checked="autoNext" :disabled="submitting"' in workspace
    assert 'class="gd-review-workspace__dossier" :disabled="submitting"' in workspace

    # Reader/version reload and page/filter movements are also rejected while the canonical
    # mutation owns the current task context. Conflict refresh uses an internal force path
    # without temporarily unlocking the UI.
    assert "if (this.submitting) return" in view
    assert "if (this.submitting || !item) return" in view
    assert "if (this.submitting || next < 1" in view
    assert "if ((!force && this.submitting) || !this.activeTask) return" in view
    assert "this.reloadCurrent({ preserveDraft: true, force: true })" in view
    assert "this.submitting = false" not in view.split("async handleMutationError", 1)[1].split("async afterMutation", 1)[0]
