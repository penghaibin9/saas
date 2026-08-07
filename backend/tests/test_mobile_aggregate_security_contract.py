"""包 13：所有教师端聚合必须强制过身份与数据范围裁决，指标必须自带完整合同。

总表要求「所有聚合 service 强制接收 SecurityContext」。本代码库的 SecurityContext 等价物
是 `_require_teacher(user)`（身份白名单）+ `resolve_teacher_scope(user)`（数据范围）。
用签名重构去逐个塞一个 context 参数，收益不如把「入口必须裁决」这条不变量钉死——
真正会出事的是有人新增一个吃 user 的聚合却忘了裁决，那一刻它就对全租户开放。

本文件是静态合同：新增聚合忘了裁决时，CI 直接红，而不是等越权发生。
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

# 这些函数本身就是裁决器/纯工具，不需要再自我裁决（否则无限递归）。
_EXEMPT = {
    "is_teacher_user",          # 身份判定本体
    "resolve_teacher_scope",    # 范围解析本体，由调用方在裁决后调用
    "scope_match_row",          # 纯函数，入参是已解析的 scope 而非 user
    "can_teacher_view_student",  # 纯判定，返回 bool 供调用方 fail-closed
    "filter_students_for_teacher",  # 纯过滤，入参已是查询结果
}


def _teacher_aggregates():
    """impl 里所有以 user 为第一个参数的公开函数——即对外的聚合入口。"""
    from app.services import _mobile_teacher_service_impl as impl

    for name in dir(impl):
        if name.startswith("_") or name in _EXEMPT:
            continue
        fn = getattr(impl, name)
        if not inspect.isfunction(fn) or fn.__module__ != impl.__name__:
            continue
        params = list(inspect.signature(fn).parameters)
        if params and params[0] == "user":
            yield name, fn


def _calls(fn) -> set[str]:
    """函数体里直接调用的名字集合（含 obj.attr() 的 attr）。"""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                found.add(target.id)
            elif isinstance(target, ast.Attribute):
                found.add(target.attr)
    return found


# 这些私有助手自身会调 _require_teacher，经它们中转的入口视为已裁决。
_ENFORCING_HELPERS = {"_domain"}


def test_every_teacher_aggregate_enforces_identity():
    """每个吃 user 的聚合入口都必须先过身份白名单，不能直接查库。

    三种合规写法：自己调 _require_teacher；经 _domain 这类会裁决的助手中转；
    委托给另一个已裁决的聚合（如 todos_page → todos）。
    """
    from app.services import _mobile_teacher_service_impl as impl

    # 安全包装层会把 overview/todos/my_students 换成自己的版本（__module__ 不再是 impl），
    # 这些同样是合法的委托目标，不能因为被替换就当成"不存在"。
    aggregate_names = {name for name, _ in _teacher_aggregates()}
    aggregate_names |= {n for n in ("overview", "todos", "my_students")
                        if callable(getattr(impl, n, None))}

    offenders = []
    for name, fn in _teacher_aggregates():
        calls = _calls(fn)
        if "_require_teacher" in calls:
            continue
        if calls & _ENFORCING_HELPERS:
            continue
        if calls & aggregate_names:
            continue
        offenders.append(name)
    assert not offenders, (
        "以下教师端聚合没有做身份裁决，新增聚合忘了 _require_teacher 会对全租户开放："
        + "、".join(sorted(offenders)))


# 按设计就是租户级、不做学生范围收敛的聚合；必须写清为什么。
_TENANT_WIDE_BY_DESIGN = {
    "orientation_today_checkins":
        "迎新现场核验：老师需要看到今日全部核验记录才能避免重复核验，按业务就是租户级",
    "internship_visit_plans":
        "范围收敛下沉到 plan_svc.list_visit_plans(user=user) 的 owner 口径，本函数只做展示拆分",
}


def test_aggregates_that_read_students_also_resolve_scope():
    """直接查库的聚合必须做某种范围裁决，不能只判身份就全租户查。

    两种合规机制：
    - resolve_teacher_scope：解析出教师范围再收敛查询；
    - `*_in_scope_or_403` 式逐对象校验：先确认这个具体对象在调用者范围内。

    按业务确实该租户级的，登记进 _TENANT_WIDE_BY_DESIGN 并写明理由——不允许无声放行。
    """
    scope_markers = {"resolve_teacher_scope", "_scope_sql_predicate", "scope_match_row",
                     "_allowed_class_ids"}
    offenders = []
    for name, fn in _teacher_aggregates():
        if name in _TENANT_WIDE_BY_DESIGN:
            continue
        calls = _calls(fn)
        if "_require_teacher" not in calls:
            continue  # 委托型入口由被委托者负责，已由上一条守住
        if not (calls & {"select", "scalars", "execute"}):
            continue
        if calls & scope_markers:
            continue
        if any(c.endswith("_in_scope_or_403") or c.endswith("_or_403") for c in calls):
            continue
        offenders.append(name)
    assert not offenders, (
        "以下聚合直接查库却没有做任何范围裁决：" + "、".join(sorted(offenders)))


@pytest.mark.parametrize("field", ["value", "available", "calculatedAt", "scope", "errorCode"])
def test_overview_metrics_carry_the_full_contract(db_mode, field):
    """包 13 指标合同：五个字段缺一不可。

    calculatedAt 让使用者知道数据新鲜度；scope 让「12」这个数字有明确含义——
    校级管理员的 12 和辅导员的 12 是完全不同的东西。
    """
    from app.core.context import set_current_user, set_tenant
    from app.services import mobile_teacher_service as tea

    user = {"userId": "db-9100", "userType": "TEACHER", "realName": "指标合同教师",
            "currentRoleCode": "SCHOOL_ADMIN"}
    set_tenant({"tenantId": "1000000000000000001"})
    set_current_user(user)
    try:
        data = tea.overview(user)
        metrics = data.get("metrics") or []
        assert metrics, "工作台总览未返回任何指标"
        for metric in metrics:
            assert field in metric, f"指标 {metric.get('key')} 缺少 {field} 字段"
    finally:
        set_current_user(None)
        set_tenant(None)
