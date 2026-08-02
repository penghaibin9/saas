"""SYS-08 组织安全树：DENY 优先、继承与未来生效（真库）。

对应必测 SYS08-T01～T04：
DENY 覆盖父级 ALLOW / 引用统计与真实鉴权同源 / 未来范围生效前不影响当前 / 模拟与真实同核心。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import scope_policy_service as svc

TENANT = 8601
OTHER_TENANT = 8602
ROLE = "COLLEGE_LEADER"


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _mk_college(tenant_id: int, name: str) -> int:
    from app.models import College

    with _session() as db:
        row = College(tenant_id=tenant_id, college_name=name, status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _mk_major(tenant_id: int, college_id: int, name: str) -> int:
    from app.models import Major

    with _session() as db:
        row = Major(tenant_id=tenant_id, college_id=college_id, major_name=name, status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _mk_class(tenant_id: int, major_id: int, name: str) -> int:
    from app.models import SchoolClass

    with _session() as db:
        row = SchoolClass(tenant_id=tenant_id, major_id=major_id, class_name=name, status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _tree(tenant_id: int = TENANT):
    college = _mk_college(tenant_id, "安全树学院")
    major = _mk_major(tenant_id, college, "安全树专业")
    klass = _mk_class(tenant_id, major, "安全树班级")
    return college, major, klass


# ── SYS08-T01：DENY 覆盖父级 ALLOW ──────────────────────────────────────────
def test_t01_explicit_deny_beats_inherited_allow(db_mode):
    college, major, klass = _tree()
    # 学院级 ALLOW，向下继承
    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                   reason="学院领导可看本院", tenant_id=TENANT)
    # 班级单独 DENY
    svc.set_policy(ROLE, effect="DENY", target_type="CLASS", target_id=str(klass),
                   reason="该班涉密", tenant_id=TENANT)

    # 专业继承到 ALLOW
    major_decision = svc.decide(ROLE, target_type="MAJOR", target_id=str(major), tenant_id=TENANT)
    assert major_decision["decision"] == "ALLOW"
    assert major_decision["reasonCode"] == "INHERITED_ALLOW"

    # 班级被显式 DENY，且 DENY 必须先于任何 ALLOW 命中
    class_decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert class_decision["decision"] == "DENY"
    assert class_decision["reasonCode"] == "EXPLICIT_DENY"
    # 判定链第一步就是 DENY，且命中
    assert class_decision["chain"][0]["step"] == "DENY"
    assert class_decision["chain"][0]["hit"] is True


def test_t01_inherited_deny_blocks_children(db_mode):
    college, major, klass = _tree()
    svc.set_policy(ROLE, effect="DENY", target_type="COLLEGE", target_id=str(college),
                   include_children=True, reason="整个学院暂停访问", tenant_id=TENANT)
    svc.set_policy(ROLE, effect="ALLOW", target_type="CLASS", target_id=str(klass),
                   reason="想单独放开这个班", tenant_id=TENANT)

    # 即使班级上有直接 ALLOW，父级的继承 DENY 仍然赢
    decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert decision["decision"] == "DENY"
    assert decision["reasonCode"] == "INHERITED_DENY"


def test_t01_deny_without_inheritance_does_not_affect_children(db_mode):
    college, major, klass = _tree()
    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                   reason="全院可看", tenant_id=TENANT)
    # 只 DENY 学院本身，不向下继承
    svc.set_policy(ROLE, effect="DENY", target_type="COLLEGE", target_id=str(college),
                   include_children=False, reason="仅学院本级不可见", tenant_id=TENANT)

    college_decision = svc.decide(ROLE, target_type="COLLEGE", target_id=str(college), tenant_id=TENANT)
    assert college_decision["decision"] == "DENY"
    # 子节点不受这条 DENY 影响，仍然继承到 ALLOW
    class_decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert class_decision["decision"] == "ALLOW"


def test_t01_default_is_deny(db_mode):
    _, _, klass = _tree()
    decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert decision["decision"] == "DENY"
    assert decision["reasonCode"] == "DEFAULT_DENY"


# ── SYS08-T02：判定顺序与业务关系层 ─────────────────────────────────────────
def test_t02_business_relation_allows_but_deny_still_wins(db_mode):
    _, _, klass = _tree()
    # 业务关系说可以（比如他确实是这个班的辅导员），但显式 DENY 必须仍然拦住
    svc.set_policy(ROLE, effect="DENY", target_type="CLASS", target_id=str(klass),
                   reason="涉密班级，任何关系都不放行", tenant_id=TENANT)
    decision = svc.decide(
        ROLE, target_type="CLASS", target_id=str(klass), business_relation_allows=True, tenant_id=TENANT
    )
    assert decision["decision"] == "DENY"
    assert decision["reasonCode"] == "EXPLICIT_DENY"


def test_t02_business_relation_beats_direct_allow_order(db_mode):
    _, _, klass = _tree()
    decision = svc.decide(
        ROLE, target_type="CLASS", target_id=str(klass), business_relation_allows=True, tenant_id=TENANT
    )
    assert decision["decision"] == "ALLOW"
    assert decision["reasonCode"] == "BUSINESS_RELATION_ALLOW"


def test_t02_sensitive_domain_deny(db_mode):
    svc.set_policy(ROLE, effect="DENY", target_type="DOMAIN", target_id="PSYCHOLOGY",
                   sensitive_domain="PSYCHOLOGY", reason="心理材料专项限制", tenant_id=TENANT)
    decision = svc.decide(ROLE, target_type="DOMAIN", target_id="PSYCHOLOGY", tenant_id=TENANT)
    assert decision["decision"] == "DENY"
    assert decision["reasonCode"] in ("EXPLICIT_DENY", "SENSITIVE_DOMAIN_RESTRICTED")


def test_t02_references_come_from_structured_table_only(db_mode):
    college, _, klass = _tree()
    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                   reason="a", tenant_id=TENANT)
    svc.set_policy(ROLE, effect="DENY", target_type="CLASS", target_id=str(klass),
                   reason="b", tenant_id=TENANT)
    refs = svc.references(ROLE, tenant_id=TENANT)
    assert refs["allowCount"] == 1
    assert refs["denyCount"] == 1
    # 引用统计必须来自结构化表，不能去搜 Role.remark 那种自由文本
    assert refs["source"] == "t_scope_policy_target"


# ── SYS08-T03：未来生效与到期 ───────────────────────────────────────────────
def test_t03_future_policy_does_not_apply_yet(db_mode):
    college, _, klass = _tree()
    future = datetime.utcnow() + timedelta(days=2)
    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                   effective_at=future, reason="下学期开放", tenant_id=TENANT)

    now_decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert now_decision["decision"] == "DENY"

    later = svc.decide(
        ROLE, target_type="CLASS", target_id=str(klass), at=future + timedelta(hours=1), tenant_id=TENANT
    )
    assert later["decision"] == "ALLOW"


def test_t03_expired_policy_stops_applying(db_mode):
    college, _, klass = _tree()
    start = datetime.utcnow() - timedelta(days=2)
    end = datetime.utcnow() - timedelta(hours=1)
    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                   effective_at=start, expires_at=end, reason="临时开放已结束", tenant_id=TENANT)
    # 读取时就要失效，不依赖定时任务
    assert svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)["decision"] == "DENY"


def test_t03_revoked_policy_stops_applying(db_mode):
    college, _, klass = _tree()
    created = svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                             reason="先开放", tenant_id=TENANT)
    assert svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)["decision"] == "ALLOW"

    svc.revoke_policy(
        int(created["policyId"]), reason="收回", expected_version=int(created["version"]), tenant_id=TENANT
    )
    assert svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)["decision"] == "DENY"


def test_t03_stale_version_rejected(db_mode):
    college, _, _ = _tree()
    created = svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(college),
                             reason="第一次", tenant_id=TENANT)
    with pytest.raises(AppException) as exc:
        svc.revoke_policy(int(created["policyId"]), reason="用旧版本号", expected_version=99, tenant_id=TENANT)
    assert exc.value.code == "VERSION_CONFLICT"


# ── SYS08-T04：跨租户与解释一致性 ───────────────────────────────────────────
def test_t04_cannot_target_other_tenant_node(db_mode):
    foreign_college = _mk_college(OTHER_TENANT, "别校学院")
    with pytest.raises(AppException):
        svc.set_policy(ROLE, effect="DENY", target_type="COLLEGE", target_id=str(foreign_college),
                       reason="想拦别人学校的", tenant_id=TENANT)


def test_t04_policies_are_tenant_isolated(db_mode):
    mine_college, _, mine_class = _tree(TENANT)
    theirs_college = _mk_college(OTHER_TENANT, "他校学院")
    theirs_major = _mk_major(OTHER_TENANT, theirs_college, "他校专业")
    theirs_class = _mk_class(OTHER_TENANT, theirs_major, "他校班级")

    svc.set_policy(ROLE, effect="ALLOW", target_type="COLLEGE", target_id=str(mine_college),
                   reason="本校开放", tenant_id=TENANT)

    assert svc.decide(ROLE, target_type="CLASS", target_id=str(mine_class), tenant_id=TENANT)["decision"] == "ALLOW"
    # 另一个租户不受影响，仍是默认拒绝
    theirs = svc.decide(ROLE, target_type="CLASS", target_id=str(theirs_class), tenant_id=OTHER_TENANT)
    assert theirs["decision"] == "DENY"
    assert theirs["reasonCode"] == "DEFAULT_DENY"


def test_t04_decision_always_carries_trace_and_full_chain(db_mode):
    _, _, klass = _tree()
    decision = svc.decide(ROLE, target_type="CLASS", target_id=str(klass), tenant_id=TENANT)
    assert decision["traceId"]
    steps = [c["step"] for c in decision["chain"]]
    # 判定链必须把每一层都走一遍并如实记录命中与否，便于向管理员解释"为什么看不到"
    assert steps == ["DENY", "INHERITED_DENY", "SENSITIVE", "BUSINESS_RELATION",
                     "DIRECT_ALLOW", "INHERITED_ALLOW", "DEFAULT_DENY"]


def test_t04_unknown_target_type_rejected(db_mode):
    with pytest.raises(AppException):
        svc.decide(ROLE, target_type="NOT_A_TYPE", target_id="1", tenant_id=TENANT)
