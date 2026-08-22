"""教师/管理 PC · Workbench 源码契约（V3 施工手册 Lane T / T1）。

按手册 §12 Lane T 的"可以与 #183 并行的前端安全项"施工，只改
frontend/src/modules/workbench/** 与 ApprovalTodoListView.vue 的纯前端 contract，
不碰 #183 owner 的共享后端文件（workbench_snapshot_service.py / workbench_todo_service.py /
todo_route_registry.py）。

覆盖：
- TP-W01 nearDeadline urgency 合法值
- TP-W04 Workbench 不再向 Approval 发送装饰性 status 参数
- TP-W05 ApprovalTodoListView 不再把 todoType 塞进 keyword 全文检索
- TP-W06 openTodo() 不再本地猜路由（TODO_TYPE_ROUTES/todoType 拼接兜底已删除）
- TP-W07 todoTypedRouteBridge 显式暴露 focusMode，不假装 NONE 是精确对象
- TP-W08 load() 用 allSettled 分区加载，stats 故障不拖垮核心待办/消息
- TP-W09 schedule 故障与真实空课表分开报告
- TP-W10 风险数字不再用 `||` 丢一类
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_workbench_summary_cues_use_legal_urgency_and_no_decorative_status():
    recipes = _read("frontend/src/modules/workbench/config/workbenchRecipes.js")
    # TP-W01：Approval 页合法 urgency 是 NEAR_DEADLINE，不是 NEAR。
    assert "urgency=NEAR_DEADLINE" in recipes
    assert "urgency=NEAR`" not in recipes
    assert "urgency=NEAR'" not in recipes
    # TP-W04：pending/doneToday 不再向 Approval "我的待办" 列表发送它从不消费的
    # status 参数；doneToday 改跳真实存在的已办列表。
    assert "${TODO_ALL}?status=PENDING`" not in recipes
    assert "${TODO_ALL}?status=DONE`" not in recipes
    assert "/admin/approval/done" in recipes


def test_workbench_view_does_not_send_decorative_status_query():
    view = _read("frontend/src/modules/workbench/views/WorkbenchView.vue")
    assert "/admin/approval/todos?status=PENDING" not in view
    assert "/admin/approval/todos?status=DONE" not in view


def test_workbench_open_todo_is_fail_closed_not_local_guessing():
    """TP-W06：没有服务端 typedRouteTarget 就禁用 + 提示，不再拿 TODO_TYPE_ROUTES
    或拼 todoType/status 兜底猜路由。"""
    view = _read("frontend/src/modules/workbench/views/WorkbenchView.vue")
    assert "TODO_TYPE_ROUTES[type]" not in view
    assert "todoType=${encodeURIComponent(type)}" not in view
    assert "if (!typedTarget)" in view


def test_typed_todo_bridge_exposes_focus_mode_not_fake_precision():
    """TP-W07：bridge 显式给出 focusMode，NONE 不能被上层当成"打开了对象"。"""
    bridge = _read("frontend/src/modules/workbench/config/todoTypedRouteBridge.js")
    assert "focusMode" in bridge
    assert "item.routeExact ? 'DETAIL' : 'NONE'" in bridge


def test_workbench_load_uses_allsettled_not_all():
    """TP-W08：核心待办/消息与非核心 stats 分区加载，stats 超时/500 不得清空核心数据。"""
    view = _read("frontend/src/modules/workbench/views/WorkbenchView.vue")
    assert "Promise.allSettled([" in view
    assert "statsError" in view
    # 旧的"一个 Promise.all 打包全部请求，失败就整页清空"链路必须消失。
    assert "const reqs = [fetchTodoSummary()" not in view


def test_workbench_schedule_failure_is_distinct_from_empty():
    """TP-W09：教务课表接口故障必须显式报错，不能显示成"今天暂无安排"。"""
    view = _read("frontend/src/modules/workbench/views/WorkbenchView.vue")
    assert "scheduleError" in view
    assert "课表暂不可用" in view


def test_workbench_risk_items_do_not_drop_a_category():
    """TP-W10：逾期待办与学业预警是两类风险，`||` 只取其一会丢真实风险数字；
    改成 riskItems 列表，两类同时存在时都要展示。"""
    view = _read("frontend/src/modules/workbench/views/WorkbenchView.vue")
    assert "this.summary.overdue || this.stats.academicWarning" not in view
    assert "riskItems()" in view


def test_approval_todo_list_no_longer_stuffs_todo_type_into_keyword():
    """TP-W05：todoType 是英文分类码，不是给人看的关键词，不能塞进全文检索。"""
    view = _read("frontend/src/views/admin/approval/ApprovalTodoListView.vue")
    assert "this.filters.keyword = String(this.$route.query.todoType)" not in view
