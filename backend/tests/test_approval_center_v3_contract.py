"""审批中心源码契约（V3 施工手册 Lane T / T3，仅覆盖本轮已交付部分）。

按手册 §12 Lane T 的 T3（审批中心队列续航）施工，只改
backend/app/services/approval_service.py、approval_runtime_service.py、
backend/app/api/v1/approval.py 与 frontend/src/views/admin/approval/**、
frontend/src/modules/approval/api/approval.api.js，不碰 #183 owner 的共享文件。

覆盖：
- TP-A05 已办列表按真实办结时间（acted_at）区间筛选，与待办的 submitDate
  （created_at）互不复用。
- TP-A03/A04 详情页"下一条"改真实服务端 seek（(created_at, id) 定位锚点之后
  的下一条 PENDING 任务），不再用 pageSize=1 重新查第一页去猜；筛选从
  bizType 单一维度扩到 keyword/bizType/urgency/submitDate 全量透传。
- TP-A02（局部）：待办列表跳转详情时把当前生效筛选写入 route.query，详情页
  才有真实上下文可以透传给 seek，不会一进详情就丢光筛选退化成"队首"。
- TP-A02/TP-A09 PcQueueContext v1：新增 queueContext.js，列表→详情→返回列表
  的导航态（bizType/urgency/keyword/submitDate/result/actedFrom/actedTo/
  readStatus/page/pageSize/source/tab）铺平进 route.query，覆盖待办、已办、
  抄送三类队列；qctx 不参与授权，returnTo 只认内部 allowlist。
- TP-A01：非法 urgency 不再静默降级成"全部"，改为显式提示并丢弃该条件。

本轮未联通真实 MySQL 验证（沙箱环境 docker daemon 不可用，见施工记录），
以下测试均为源码契约测试（字符串/结构断言），不建立数据库连接、不冒充集成测试。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TP-A05：已办列表办结时间区间筛选
# ---------------------------------------------------------------------------

def test_db_list_accepts_and_validates_acted_range():
    src = _read("backend/app/services/approval_service.py")
    assert "acted_from: str | None = None" in src
    assert "acted_to: str | None = None" in src
    assert "actedFrom 不能晚于 actedTo" in src


def test_db_list_only_applies_acted_range_to_processed_branch():
    """acted_at 区间只属于已办列表；待办列表不应消费这两个参数。"""
    src = _read("backend/app/services/approval_service.py")
    assert "if processed and acted_start is not None:" in src
    assert "WorkflowTask.acted_at >= acted_start" in src
    assert "if processed and acted_end is not None:" in src
    assert "WorkflowTask.acted_at < acted_end" in src


def test_list_processed_signature_passes_acted_range_through():
    src = _read("backend/app/services/approval_service.py")
    assert "def list_processed(page: int, page_size: int, user: dict | None = None," in src
    assert "acted_from: str | None = None," in src
    assert "acted_from=acted_from, acted_to=acted_to" in src


def test_runtime_list_processed_forwards_acted_range():
    src = _read("backend/app/services/approval_runtime_service.py")
    assert "acted_from=None, acted_to=None" in src
    assert "acted_from=acted_from, acted_to=acted_to," in src


def test_router_exposes_acted_from_to_on_done_and_processed():
    src = _read("backend/app/api/v1/approval.py")
    assert src.count('actedFrom: str | None = Query(None, max_length=10)') == 2
    assert src.count('actedTo: str | None = Query(None, max_length=10)') == 2
    assert src.count("acted_from=actedFrom, acted_to=actedTo,") == 2


def test_frontend_get_done_items_sends_acted_range():
    src = _read("frontend/src/modules/approval/api/approval.api.js")
    assert "actedFrom: params.actedFrom," in src
    assert "actedTo: params.actedTo" in src


def test_done_list_view_exposes_acted_range_filter_fields():
    src = _read("frontend/src/views/admin/approval/ApprovalDoneListView.vue")
    assert "actedFrom: '', actedTo: ''" in src
    assert "{ key: 'actedFrom', label: '办结日期起', type: 'date' }" in src
    assert "{ key: 'actedTo', label: '办结日期止', type: 'date' }" in src


# ---------------------------------------------------------------------------
# TP-A03/A04：真实服务端 seek 取"下一条待办"
# ---------------------------------------------------------------------------

def test_backend_has_next_pending_task_seek_function():
    src = _read("backend/app/services/approval_service.py")
    assert "def next_pending_task(" in src
    # 必须按 created_at/id 做 seek，不能只按 id 或只取第一页。
    assert "WorkflowTask.created_at > anchor.created_at" in src
    assert "WorkflowTask.id > anchor.id" in src
    assert ".order_by(WorkflowTask.created_at.asc(), WorkflowTask.id.asc())" in src
    assert ".limit(1)" in src


def test_runtime_next_task_wraps_seek_and_enriches():
    src = _read("backend/app/services/approval_runtime_service.py")
    assert "def next_task(anchor_task_id, *, user=None" in src
    assert "base.next_pending_task(" in src


def test_router_exposes_next_todo_endpoint_with_full_filters():
    src = _read("backend/app/api/v1/approval.py")
    assert '@router.get("/tasks/{task_id}/next"' in src
    assert "def next_todo(" in src
    assert "urgency: str | None = Query(None, max_length=30)" in src
    assert "submitDate: str | None = Query(None, max_length=10)" in src


def test_frontend_api_has_get_next_todo():
    src = _read("frontend/src/modules/approval/api/approval.api.js")
    assert "getNextTodo: (taskId, params = {})" in src
    assert "/approvals/tasks/${encodeURIComponent(taskId)}/next" in src


def test_detail_view_go_next_uses_real_seek_not_page_size_one_guess():
    src = _read("frontend/src/views/admin/approval/ApprovalDetailView.vue")
    assert "approvalApi.getNextTodo(this.task?.taskId" in src
    # 旧的 pageSize=1 重查第一页去猜"下一条"必须消失。
    assert "pageSize: 1" not in src
    # 不再只保留 bizType 一个筛选维度。
    assert "urgency: q.urgency || ''" in src
    assert "submitDate: q.submitDate || ''" in src


def test_todo_list_view_carries_active_filters_into_detail_route():
    """TP-A02（局部）：详情页 seek 要透传的筛选，必须先从列表页 route.query 带进去，
    否则详情页永远只能拿到空筛选，seek 退化成"整个待办队列"而不是"用户实际在看的队列"。"""
    src = _read("frontend/src/views/admin/approval/ApprovalTodoListView.vue")
    assert "goDetail(taskId) {" in src
    assert "buildDetailQuery({" in src
    assert "@click=\"goDetail(row.taskId)\"" in src


# ---------------------------------------------------------------------------
# TP-A02/TP-A09：PcQueueContext v1（列表→详情→返回列表导航态）
# ---------------------------------------------------------------------------

def test_queue_context_module_defines_allowlist_and_never_authorizes():
    src = _read("frontend/src/modules/approval/utils/queueContext.js")
    assert "export const RETURN_ALLOWLIST" in src
    assert "'/admin/approval/todos'" in src
    assert "'/admin/approval/done'" in src
    # 手册 14.3 明示的安全规则必须在源码里留痕，不能只在文档里说。
    assert "qctx 永远不参与服务端授权" in src
    assert "export function buildDetailQuery(" in src
    assert "export function buildReturnQuery(" in src
    assert "export function returnPath(" in src


def test_done_list_view_restores_tab_filters_and_page_from_query():
    """TP-A09：Done/CC 详情返回列表要恢复原 tab（done/cc）+ 筛选 + 分页，
    不能永远回到 done tab 第一页。"""
    src = _read("frontend/src/views/admin/approval/ApprovalDoneListView.vue")
    assert "const tab = this.$route.query.tab === 'cc' ? 'cc' : 'done'" in src
    assert "this.activeTab = tab" in src
    assert "goDetail(taskId) {" in src
    assert "returnTo: '/admin/approval/done'," in src
    assert "tab: this.activeTab" in src
    assert "syncQueryFromState()" in src


def test_detail_view_has_allowlisted_back_to_list_and_goNext_falls_back_to_it():
    """详情页"返回列表"必须走 queueContext 的 allowlist，且 seek 队列耗尽时的
    兜底也要用同一条路径回到原列表 + 原筛选，不能无条件推到无筛选待办首页。"""
    src = _read("frontend/src/views/admin/approval/ApprovalDetailView.vue")
    assert "goBackToList() {" in src
    assert "returnPath(q)" in src
    assert "buildReturnQuery(q)" in src
    assert "this.goBackToList()" in src


def test_todo_list_view_rejects_illegal_urgency_with_explicit_notice():
    """TP-A01：非法 urgency 必须显式提示并丢弃，不能静默降级成"全部"让用户误以为
    筛选生效了。"""
    src = _read("frontend/src/views/admin/approval/ApprovalTodoListView.vue")
    assert "} else if (urgency) {" in src
    assert "toast.error(" in src
    assert "不受支持，已忽略该条件" in src
