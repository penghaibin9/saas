from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_w74_summary_failure_is_non_blocking_for_queue_and_detail():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

    assert 'v-if="summaryError"' in view
    assert '评阅摘要加载失败：{{ summaryError }}' in view
    assert '@click="retrySummary"' in view
    assert "summaryError: ''" in view

    best_effort = section(view, "async loadSummaryBestEffort", "async retrySummary")
    assert "await this.loadSummary(token)" in best_effort
    assert "if (token === this.loadToken) this.summaryError = errorMessage" in best_effort
    assert "return false" in best_effort

    load_all = section(view, "async loadAll", "resetSelection() {")
    assert "void this.loadSummaryBestEffort(token)" in load_all
    assert "await this.loadQueue({ preserveSelection, token })" in load_all
    assert "Promise.all" not in load_all
    assert "this.error = errorMessage(error, '评阅中心数据加载失败')" in load_all


def test_w74_filter_page_and_mutation_refresh_do_not_refetch_summary_as_queue_dependency():
    view = text("frontend/src/modules/graduation/views/GraduationReviewCenterView.vue")

    reload_first = section(view, "reloadFromFirstPage() {", "async loadSummary")
    assert "this.page = 1; this.loadQueueOnly()" in reload_first
    assert "this.loadAll()" not in reload_first

    change_page = section(view, "async changePage", "async submitBusiness")
    assert "await this.loadQueueOnly()" in change_page
    assert "await this.loadAll()" not in change_page

    queue_only = section(view, "async loadQueueOnly", "async loadAll")
    assert "const token = ++this.loadToken" in queue_only
    assert "++this.selectionToken" in queue_only
    assert "await this.loadQueue({ preserveSelection, token })" in queue_only
    assert "if (token === this.loadToken) this.loading = false" in queue_only

    after_mutation = section(view, "async afterMutation", "async openStudentDossier")
    assert "void this.loadSummaryBestEffort(token)" in after_mutation
    assert "await this.loadQueue({ select: false, token })" in after_mutation
    assert "Promise.all" not in after_mutation
