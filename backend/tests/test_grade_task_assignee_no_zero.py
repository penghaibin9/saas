"""NEW-P1-02 残留：成绩任务与调停课的审批任务也必须落真实受理人，禁止 assignee_id=0。

包 1 只收口了「成绩更正」链；成绩任务本身的 submit_task → college_review 和调停课的
两级审批仍在写 assignee_id=0。后果：流程进了待审却没有办理人，统一待办按 assignee_id
过滤时谁都查不到，只能靠人肉巡列表；同时任何持该权限的账号都能抢办，职责分离失效。

不变量：这两条链创建 WorkflowTask/UnifiedTodo 时，assignee_id 必须是唯一真实账号；
解析不到（无人持权限、候选人不唯一、任务未绑学院）一律 409 阻断，绝不落 0。
"""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException


def _code_only(fn) -> str:
    """函数体去掉文档字符串和注释后的紧凑源码。

    直接扫原始 source 会把解释「为什么不能写 assignee_id=0」的注释本身当成违规命中。
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    node = tree.body[0]
    body = node.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]  # 去掉 docstring
    return "".join(ast.unparse(stmt) for stmt in body).replace(" ", "")


def test_no_live_workflow_task_is_created_with_zero_assignee():
    """静态合同：两条链的建任务处不得再出现字面量 assignee_id=0。

    只扫真正会执行到的函数体——被包 1 的 install() 顶替掉的旧更正实现留在文件里属于
    死代码，不在本合同范围内（它们已由 academic_affairs_grade_correction_command
    接管，实证见 test_grade_correction_command_takes_over_all_entries）。
    """
    from app.modules.academic_affairs.services import (
        academic_affairs_grade_core_service as core,
        academic_affairs_grade_service as public,
        academic_affairs_schedule_change_service as sched,
    )

    live = [
        (core.submit_task, "成绩任务提交"),
        (core.college_review, "成绩任务学院审核"),
        (public.submit_task, "成绩任务提交（公开层）"),
        (sched._open_wf, "调停课发起"),
        (sched._todo_upsert, "调停课统一待办"),
        (sched.review, "调停课审核"),
    ]
    for fn, label in live:
        assert "assignee_id=0" not in _code_only(fn), (
            f"{label} 仍在创建 assignee_id=0 的无人任务")


def test_grade_correction_command_takes_over_all_entries():
    """包 1 的接管必须成立，否则上面那条豁免（旧实现是死代码）就不成立。"""
    from app.modules.academic_affairs.services import (
        academic_affairs_grade_core_service as core,
        academic_affairs_grade_service as public,
    )

    expected = "academic_affairs_grade_correction_command"
    for module in (core, public):
        for name in ("change_request", "change_college_review", "change_academic_review"):
            assert getattr(module, name).__module__.endswith(expected), (
                f"{module.__name__}.{name} 未被统一更正命令接管")


@pytest.mark.parametrize("node,expected_perm", [
    ("ACADEMIC_REVIEW", "academicAffairs.grade.publish"),
    ("COLLEGE_REVIEW", "academicAffairs.grade.collegeReview"),
])
def test_resolver_refuses_when_no_real_assignee_exists(db_mode, node, expected_perm):
    """空租户里没有任何人持有该权限 → 必须 409，不得回落 0。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard import (
        resolve_grade_task_assignee,
    )

    db = get_sessionmaker()()
    set_tenant({"tenantId": "1000000000000000001"})
    try:
        task = type("_Task", (), {"class_id": None})()
        with pytest.raises(AppException) as exc:
            resolve_grade_task_assignee(db, node, task)
        assert exc.value.http_status == 409
    finally:
        set_tenant(None)
        db.close()


def test_schedule_change_reuses_the_same_resolver_with_its_own_permissions():
    """调停课复用同一套收敛规则，但必须用自己的权限码，不能借成绩的权限判人。"""
    from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as g

    assert g.SCHEDULE_CHANGE_COLLEGE_PERM == "academicAffairs.scheduleChange.collegeReview"
    assert g.SCHEDULE_CHANGE_ACADEMIC_PERM == "academicAffairs.scheduleChange.academicReview"
    source = inspect.getsource(
        __import__("app.modules.academic_affairs.services.academic_affairs_schedule_change_service",
                   fromlist=["x"])._schedule_change_assignee)
    assert "SCHEDULE_CHANGE_COLLEGE_PERM" in source
    assert "SCHEDULE_CHANGE_ACADEMIC_PERM" in source
