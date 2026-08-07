"""包 13：风险学生范围必须下推 SQL，不能先截断再过滤。

事故路径：三个来源域各自 `order by id desc limit 80` 取最新 80 条，**之后**才在 Python
里按教师范围过滤。辅导员负责的学生只要不在全租户最新 80 条里，风险页就返回空——本该
被看到的高风险学生被静默隐藏，页面还不给任何提示，老师以为"本班没有风险学生"。

不变量：范围条件进 SQL，先过滤再排序取数；命中扫描上限时必须如实标记 truncated。
"""
from __future__ import annotations

import pytest

from app.core.context import set_current_user, set_tenant

TID = 1000000000000000001
NOISE = 120  # 远超旧实现的 80 条截断阈值


def _seed(db, *, target_class="风险2601班"):
    """先灌 NOISE 条不属于目标辅导员的高关注记录，再插 1 条属于他的（id 最小）。

    旧实现按 id 倒序取前 80 条，目标学生排在最后，必然被截掉。
    """
    from app.models import CsServiceStudent

    target = CsServiceStudent(
        tenant_id=TID, student_no="RISK-TARGET-001", student_id=770001,
        name="本班风险生", class_name=target_class, care_level="HIGH",
        risk_level="HIGH", mental_flag=False, record_status="ACTIVE")
    db.add(target)
    db.flush()

    for i in range(NOISE):
        db.add(CsServiceStudent(
            tenant_id=TID, student_no=f"RISK-OTHER-{i:04d}", student_id=780000 + i,
            name=f"他班风险生{i}", class_name="其他2601班", care_level="HIGH",
            risk_level="HIGH", mental_flag=False, record_status="ACTIVE"))
    db.commit()
    return target


@pytest.fixture()
def _counselor(monkeypatch):
    """把当前教师钉成只负责 风险2601班 的 SCOPED 辅导员。"""
    from app.services import _mobile_teacher_service_impl as impl

    user = {"userId": "db-9001", "userType": "TEACHER", "realName": "范围辅导员",
            "currentRoleCode": "COUNSELOR"}
    scope = {"mode": "SCOPED", "by": "CLASS", "advisorName": "范围辅导员",
             "roleCode": "COUNSELOR", "tenantId": TID,
             "classNames": {"风险2601班"}, "studentNos": set(),
             "collegeNames": set(), "advisorNames": set(), "advisorUserIds": {"9001"}}
    monkeypatch.setattr(impl, "resolve_teacher_scope", lambda _u: scope)
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    try:
        yield user
    finally:
        set_current_user(None)
        set_tenant(None)


def test_in_scope_student_is_not_hidden_by_the_scan_cap(db_mode, _counselor):
    """本班唯一的高风险学生排在最旧，绝不能被"先截断后过滤"吃掉。"""
    from app.db.session import get_sessionmaker
    from app.services import mobile_teacher_service as tea

    db = get_sessionmaker()()
    try:
        _seed(db)
    finally:
        db.close()

    result = tea.risk_students(_counselor)
    nos = [row.get("studentNo") for row in result.get("list") or []]
    assert "RISK-TARGET-001" in nos, (
        f"本班风险学生被截断隐藏了；返回 {len(nos)} 条：{nos[:5]}")


def test_out_of_scope_students_never_leak(db_mode, _counselor):
    """反向：其他班的风险学生一条都不能出现。"""
    from app.db.session import get_sessionmaker
    from app.services import mobile_teacher_service as tea

    db = get_sessionmaker()()
    try:
        _seed(db)
    finally:
        db.close()

    result = tea.risk_students(_counselor)
    leaked = [row.get("studentNo") for row in result.get("list") or []
              if str(row.get("studentNo") or "").startswith("RISK-OTHER-")]
    assert not leaked, f"越范围泄漏了他班学生：{leaked[:5]}"


def test_paged_endpoint_reports_truncation_and_error_visibility(db_mode, _counselor):
    """分页接口必须透出 truncated / available / errors，不能把故障与截断显示成"就这么多"。"""
    from app.services import mobile_teacher_service as tea

    risk = tea.risk_students_page(_counselor, level="all", page=1, page_size=20)
    assert "truncated" in risk, "风险分页未透出 truncated"

    todos = tea.todos_page(_counselor, group="all", page=1, page_size=20)
    assert "available" in todos and "errors" in todos, "待办分页未透出故障可见性字段"


def test_scoped_teacher_without_any_scope_is_denied_not_granted_everything(db_mode, monkeypatch):
    """SCOPED 但范围为空 → 默认拒绝，不能因为"没有可下推的条件"而放行全租户。"""
    from app.db.session import get_sessionmaker
    from app.services import _mobile_teacher_service_impl as impl
    from app.services import mobile_teacher_service as tea

    empty_scope = {"mode": "SCOPED", "by": "DEFAULT_DENY", "advisorName": "",
                   "roleCode": "ACADEMIC_TEACHER", "tenantId": TID,
                   "classNames": set(), "studentNos": set(),
                   "collegeNames": set(), "advisorNames": set(), "advisorUserIds": set()}
    monkeypatch.setattr(impl, "resolve_teacher_scope", lambda _u: empty_scope)
    user = {"userId": "db-9002", "userType": "TEACHER", "realName": "无范围教师",
            "currentRoleCode": "ACADEMIC_TEACHER"}
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    try:
        db = get_sessionmaker()()
        try:
            _seed(db)
        finally:
            db.close()
        result = tea.risk_students(user)
        assert not (result.get("list") or []), "无范围教师不得看到任何风险学生"
    finally:
        set_current_user(None)
        set_tenant(None)
