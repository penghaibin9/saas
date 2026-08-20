from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_student_affairs_history_export_requires_full_scope_before_querying_rows():
    source = _read("backend/app/services/domain_export_service.py")

    guard_call = 'if domain == "student-affairs":\n        _require_student_affairs_full_scope(user)'
    # Security intent: the full-tenant scope guard must execute before any row query.
    # Keep the contract independent from benign _call_list signature evolution such as
    # adding batch_id for another domain; exact argument-string matching caused false red.
    scoped_query = "items, total = _call_list("
    assert guard_call in source
    assert 'ctx.scope_type != "TENANT_ALL"' in source
    assert scoped_query in source
    assert source.index(guard_call) < source.index(scoped_query)


def test_student_message_detail_never_routes_students_into_teacher_pages():
    """安全意图不变：学生打开消息，绝不能被带进教师页；解析不出安全落点时必须明确拒绝。

    变的是这条约束落在哪里。以前消息详情页自己维护 ACTION_ROUTES/MODULE_ROUTES，
    按 actionKey/actionParams 猜路由，所以只能在页面源码里断言那两张表（V3 深审 P0-02）。
    V3 之后页面不再有任何本地路由表，唯一事实源是服务端已解析的 action.target，
    因此这里断言真正生效的三道闸：页面不含教师路由且只执行服务端 action、
    服务端 Adapter 的 client 前缀白名单、客户端 canNavigate 的同一道白名单。
    """
    source = _read("miniapp/src/pages/common/message-detail/index.vue")
    assert "/pages/teacher/" not in source
    # 页面不得再有本地路由推断：没有自建路由表，只调用服务端 action。
    assert "const ACTION_ROUTES" not in source
    assert "const MODULE_ROUTES" not in source
    assert "runAction(" in source
    assert "canNavigate(" in source

    # 服务端：studentMini 只允许落到学生页/公共页，教师前缀一律 fail-closed。
    from app.services.mobile_action_service import CLIENT_STUDENT_MINI, _ALLOWED_PREFIXES
    student_prefixes = _ALLOWED_PREFIXES[CLIENT_STUDENT_MINI]
    assert student_prefixes == ("/pages/student/", "/pages/common/")
    assert not any(prefix.startswith("/pages/teacher/") for prefix in student_prefixes)

    # 客户端：同一道白名单在 actionRouter 里再拦一次，服务端被绕过也跳不过去。
    router = _read("miniapp/src/services/actionRouterCore.mjs")
    assert "student: ['/pages/student/', '/pages/common/']" in router
    assert "export function canNavigate" in router


def test_student_portal_message_click_reads_action_metadata_and_uses_whitelisted_routes():
    source = _read("student-portal/src/views/messages/MessagesView.vue")

    assert "ACTION_ROUTES" in source
    assert "MODULE_ROUTES" in source
    assert "request(`/mobile/me/messages/${mid}`)" in source
    assert "router.push(messageTarget(detail))" in source
    assert "'student-affairs': '/campus-service'" in source
