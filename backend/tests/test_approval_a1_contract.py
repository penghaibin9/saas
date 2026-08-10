import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pc_formal_facade_cannot_reach_approval_mock():
    text = read("frontend/src/modules/approval/api/approval.api.js")
    assert "@/mocks/approval" not in text
    assert "withFallback" not in text
    assert "mockApproval" not in text
    assert "approvalList" not in text
    assert "doneItems" not in text
    assert "returnedItems" not in text


def test_return_and_reject_are_distinct_in_all_formal_clients():
    pc = read("frontend/src/modules/approval/api/approval.api.js")
    adapter = read("frontend/src/services/http/adapters.js")
    mini = read("miniapp/src/services/approvalApi.js")

    # PC facade 与旧适配器都使用显式正式路径。
    for text in (pc, adapter):
        assert "/return" in text
        assert "/reject" in text

    assert "returnTask(taskId" in adapter
    return_body = adapter.split("export async function returnTask", 1)[1].split("export async function rejectTask", 1)[0]
    assert "/return" in return_body
    assert "/reject" not in return_body
    assert "status: 'RETURNED'" not in return_body

    # 小程序通过受控动作映射拼接正式路径，锁定 RETURN/REJECT 不得共用 endpoint。
    assert "移动端驳回" not in mini
    assert "pathByAction" in mini
    assert "RETURN: 'return'" in mini
    assert "REJECT: 'reject'" in mini
    assert "RETURN: 'reject'" not in mini


def test_teacher_page_never_synthesizes_terminal_approval_status():
    page = read("miniapp/src/pages/teacher/approval/index.vue")
    # 只禁止赋值；模板中的 a.status === 'PENDING_REVIEW' 是合法只读判断。
    assert not re.search(r"\ba\.status\s*=(?!=)", page)
    assert not re.search(r"\btask\.status\s*=(?!=)", page)
    assert "await this.load()" in page
    assert "已退回修改" in page
    assert "已驳回终止原流程" in page


def test_backend_route_and_runtime_enforce_real_return_semantics():
    routes = read("backend/app/api/v1/approval.py")
    runtime = read("backend/app/services/approval_runtime_service.py")

    assert '@router.post("/tasks/{task_id}/return"' in routes
    assert '@router.post("/tasks/{task_id}/reject"' in routes
    assert "runtime.return_for_revision" in routes
    assert "runtime.reject" in routes

    assert "APPROVAL_BACKEND_UNAVAILABLE" in runtime
    assert '"status": "RETURNED"' in runtime
    assert 'inst.status = "RUNNING"' in runtime
    assert 'inst.current_node = "APPLICANT_RESUBMIT"' in runtime
    assert 'todo_type="APPROVAL_RESUBMIT"' in runtime
    assert "UnifiedMessage(" in runtime
    assert '"action": "RESUBMIT"' in runtime


def test_pc_detail_has_explicit_return_reject_and_server_refresh_next_queue():
    page = read("frontend/src/views/admin/approval/ApprovalDetailView.vue")
    assert "退回修改" in page
    assert "驳回终止" in page
    assert "approvalApi.returnTask" in page
    assert "approvalApi.rejectTask" in page
    assert "await this.load()" in page
    assert "await this.goNext()" in page
    assert "该审批事实已经变化" in page
