"""SYS-10 访问解释、职责分离、紧急访问与权限复核（真库）。

对应必测 SYS10-T01～T04：
真实 403 可按 traceId 复现 / 无权解释时不泄露存在性 / 职责冲突后端强制 / 紧急访问自动到期。

最要紧的一条是"解释不许自己算"：解释器若照着鉴权逻辑重写一遍，两套逻辑必然漂移，
到时候解释会理直气壮地给出与实际相反的结论。这里用一批对照测试锁住
"解释结论 == has_permission 的返回"。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services import policy_decision_service as svc

TENANT = 8401
OTHER_TENANT = 8402


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _user(role_code: str, user_id: int = 9001) -> dict:
    """按鉴权核心真正读取的字段构造身份。

    ``permissions._role_of`` 读的是顶层 ``currentRoleCode`` / ``userType``，
    不是嵌套的 ``currentRole.roleCode``——用错字段会让所有权限判定静默变成"无角色"。
    """
    return {"userId": user_id, "tenantId": TENANT, "currentRoleCode": role_code, "userType": role_code}


# ── SYS10-T01：解释结论必须与真实鉴权一致，且可按 traceId 复现 ──────────────
def test_t01_explanation_matches_real_authorization(db_mode):
    """逐个动作对照：解释给出的 ALLOW/DENY 必须等于 has_permission 的返回。"""
    cases = [
        ("SYS_ADMIN", "systemAdmin.role.view"),
        ("SYS_ADMIN", "academicAffairs.course.create"),
        ("ACADEMIC_ADMIN", "academicAffairs.course.create"),
        ("ACADEMIC_ADMIN", "systemAdmin.role.view"),
        ("COUNSELOR", "studentAffairs.leave.approve"),
        ("COUNSELOR", "systemAdmin.user.create"),
    ]
    for role, action in cases:
        user = _user(role)
        expected = "ALLOW" if has_permission(user, action) else "DENY"
        result = svc.explain(user, action_code=action, tenant_id=TENANT)
        assert result["decision"] == expected, f"{role} 对 {action} 的解释与真实鉴权不一致"
        # 自检层必须通过——不通过说明解释链推导与权威判定打架
        self_check = [c for c in result["chain"] if c["step"] == "SELF_CHECK"]
        assert self_check and self_check[0]["pass"] is True
        assert result["reasonCode"] != "EXPLAINER_DRIFT"


def test_t01_denial_can_be_reproduced_by_trace_id(db_mode):
    user = _user("COUNSELOR")
    result = svc.explain(user, action_code="systemAdmin.user.create", tenant_id=TENANT)
    assert result["decision"] == "DENY"
    trace_id = result["traceId"]
    assert trace_id

    replay = svc.get_trace(trace_id, tenant_id=TENANT)
    assert replay["decision"] == "DENY"
    assert replay["actionCode"] == "systemAdmin.user.create"
    assert replay["chain"], "复现出来却没有判定链，等于没解释"
    # 链路必须逐层记录，而不是只给一个结论
    steps = [c["step"] for c in replay["chain"]]
    assert "PERMISSION_CHECK" in steps
    assert "SELF_CHECK" in steps


def test_t01_explanation_records_every_layer(db_mode):
    user = _user("SYS_ADMIN")
    result = svc.explain(user, action_code="systemAdmin.role.view", tenant_id=TENANT)
    steps = [c["step"] for c in result["chain"]]
    for expected in ("SUPER_ADMIN", "ACTIVE_ROLE", "PERMISSION_PATTERNS", "ROLE_DENY", "PERMISSION_CHECK"):
        assert expected in steps, f"判定链缺少 {expected} 层"


def test_t01_denials_are_listed(db_mode):
    user = _user("COUNSELOR")
    svc.explain(user, action_code="systemAdmin.user.create", tenant_id=TENANT)
    svc.explain(user, action_code="systemAdmin.role.config", tenant_id=TENANT)
    denials = svc.list_denials(tenant_id=TENANT)["items"]
    assert len(denials) >= 2
    assert all(d["traceId"] for d in denials)


# ── SYS10-T02：不得泄露对象存在性、不得跨租户 ───────────────────────────────
def test_t02_resource_id_is_never_echoed_back(db_mode):
    """解释结果与留痕都只能出现摘要，绝不能回显原始 id。"""
    secret_id = "STUDENT-2024-0007"
    user = _user("COUNSELOR")
    result = svc.explain(
        user, action_code="studentAffairs.student.view",
        resource_type="STUDENT", resource_id=secret_id, tenant_id=TENANT,
    )
    assert secret_id not in str(result), "原始资源 id 被回显，解释接口成了枚举器"
    assert result["resourceIdHash"].startswith("sha256:")

    replay = svc.get_trace(result["traceId"], tenant_id=TENANT)
    assert secret_id not in str(replay)
    assert replay["resourceIdHash"] == result["resourceIdHash"]

    # 相同 id 得到相同摘要，便于比对；不同 id 摘要不同
    other = svc.explain(
        user, action_code="studentAffairs.student.view",
        resource_type="STUDENT", resource_id=secret_id, tenant_id=TENANT,
    )
    assert other["resourceIdHash"] == result["resourceIdHash"]


def test_t02_trace_is_tenant_isolated(db_mode):
    user = _user("COUNSELOR")
    result = svc.explain(user, action_code="systemAdmin.user.create", tenant_id=TENANT)
    # 另一个学校拿同一个 traceId 一律 404，不确认它是否存在
    with pytest.raises(AppException):
        svc.get_trace(result["traceId"], tenant_id=OTHER_TENANT)


def test_t02_scope_denial_overrides_permission_grant(db_mode):
    """有功能权限但数据范围拒绝时，最终必须是 DENY。"""
    from app.models import College, Major, SchoolClass

    with _session() as db:
        college = College(tenant_id=TENANT, college_name="解释测试学院", status="ACTIVE")
        db.add(college)
        db.commit()
        db.refresh(college)
        major = Major(tenant_id=TENANT, college_id=college.id, major_name="解释测试专业", status="ACTIVE")
        db.add(major)
        db.commit()
        db.refresh(major)
        klass = SchoolClass(tenant_id=TENANT, major_id=major.id, class_name="解释测试班", status="ACTIVE")
        db.add(klass)
        db.commit()
        db.refresh(klass)
        class_id = int(klass.id)

    from app.services import scope_policy_service as sps

    sps.set_policy(
        "SYS_ADMIN", effect="DENY", target_type="CLASS", target_id=str(class_id),
        reason="该班涉密，任何角色都不可见", tenant_id=TENANT,
    )

    user = _user("SYS_ADMIN")
    assert has_permission(user, "systemAdmin.role.view") is True
    result = svc.explain(
        user, action_code="systemAdmin.role.view",
        scope_target_type="CLASS", scope_target_id=str(class_id), tenant_id=TENANT,
    )
    assert result["decision"] == "DENY"
    assert result["reasonCode"] == "DATA_SCOPE_DENIED"


# ── SYS10-T03：职责分离必须由后端强制 ───────────────────────────────────────
def test_t03_sod_conflict_is_enforced_not_just_reported(db_mode):
    svc.add_sod_rule(
        rule_code="SOD-FUND", role_a="FUNDING_ADMIN", role_b="SECURITY_AUDITOR",
        reason="资助发放与安全审计不得由同一人兼任", tenant_id=TENANT,
    )

    clean = svc.check_sod(9101, ["FUNDING_ADMIN", "COUNSELOR"], tenant_id=TENANT)
    assert clean["conflict"] is False

    conflict = svc.check_sod(9102, ["FUNDING_ADMIN", "SECURITY_AUDITOR"], tenant_id=TENANT)
    assert conflict["conflict"] is True
    assert conflict["violations"][0]["ruleCode"] == "SOD-FUND"

    # 关键：不是"检出了但还是放行"，assert_sod 必须真的抛 403
    with pytest.raises(AppException) as exc:
        svc.assert_sod(9102, ["FUNDING_ADMIN", "SECURITY_AUDITOR"], tenant_id=TENANT)
    assert exc.value.code == "SOD_CONFLICT"
    assert exc.value.http_status == 403

    # 合规组合不该被拦
    svc.assert_sod(9101, ["FUNDING_ADMIN", "COUNSELOR"], tenant_id=TENANT)


def test_t03_sod_violation_is_recorded_once(db_mode):
    svc.add_sod_rule(
        rule_code="SOD-DUP", role_a="ACADEMIC_ADMIN", role_b="SECURITY_AUDITOR",
        reason="教务与审计不得兼任", tenant_id=TENANT,
    )
    svc.check_sod(9103, ["ACADEMIC_ADMIN", "SECURITY_AUDITOR"], tenant_id=TENANT)
    svc.check_sod(9103, ["ACADEMIC_ADMIN", "SECURITY_AUDITOR"], tenant_id=TENANT)
    violations = svc.list_sod(tenant_id=TENANT)["violations"]
    same = [v for v in violations if v["ruleCode"] == "SOD-DUP" and v["subjectUserId"] == "9103"]
    assert len(same) == 1, "重复检查不该产生重复冲突记录"


def test_t03_sod_rule_validation(db_mode):
    with pytest.raises(AppException):
        svc.add_sod_rule(rule_code="X", role_a="A", role_b="A", reason="两个角色相同", tenant_id=TENANT)
    with pytest.raises(AppException):
        svc.add_sod_rule(rule_code="Y", role_a="A", role_b="B", reason="短", tenant_id=TENANT)
    svc.add_sod_rule(rule_code="Z", role_a="A", role_b="B", reason="正当理由说明", tenant_id=TENANT)
    # 理由要够长，否则先撞上长度校验，测不到重复编码这条
    with pytest.raises(AppException) as exc:
        svc.add_sod_rule(rule_code="Z", role_a="A", role_b="C", reason="编码重复应当被拒绝", tenant_id=TENANT)
    assert exc.value.code == "SOD_RULE_EXISTS"


# ── SYS10-T04：紧急访问必须自动到期 ─────────────────────────────────────────
def test_t04_emergency_access_expires_on_read_not_by_cron(db_mode):
    session = svc.grant_emergency(
        subject_user_id=9201, granted_role_code="SYS_ADMIN", ticket_ref="INC-2026-001",
        reason="生产故障需临时提权排查", minutes=1, tenant_id=TENANT,
    )
    assert session["activeNow"] is True

    # 定时任务还没跑，读取时校验就必须已经失效
    from app.services import policy_decision_service as mod

    real_now = mod._now

    def fake_now():
        return real_now() + timedelta(minutes=5)

    mod._now = fake_now
    try:
        assert svc.active_emergency(9201, tenant_id=TENANT) is None, "过期紧急访问仍被当作有效"
    finally:
        mod._now = real_now


def test_t04_emergency_requires_ticket_and_bounded_duration(db_mode):
    with pytest.raises(AppException):
        svc.grant_emergency(
            subject_user_id=9202, granted_role_code="SYS_ADMIN", ticket_ref="",
            reason="没有工单号", minutes=30, tenant_id=TENANT,
        )
    # 不存在无限期紧急访问
    with pytest.raises(AppException):
        svc.grant_emergency(
            subject_user_id=9202, granted_role_code="SYS_ADMIN", ticket_ref="INC-2",
            reason="想开一整天", minutes=1000, tenant_id=TENANT,
        )
    with pytest.raises(AppException):
        svc.grant_emergency(
            subject_user_id=9202, granted_role_code="SYS_ADMIN", ticket_ref="INC-3",
            reason="短", minutes=30, tenant_id=TENANT,
        )


def test_t04_emergency_can_be_revoked_early(db_mode):
    session = svc.grant_emergency(
        subject_user_id=9203, granted_role_code="SYS_ADMIN", ticket_ref="INC-2026-002",
        reason="临时排查数据问题", minutes=120, tenant_id=TENANT,
    )
    assert svc.active_emergency(9203, tenant_id=TENANT) is not None
    svc.revoke_emergency(session["sessionCode"], reason="排查完毕提前收回", tenant_id=TENANT)
    assert svc.active_emergency(9203, tenant_id=TENANT) is None


def test_t04_expire_job_marks_status(db_mode):
    svc.grant_emergency(
        subject_user_id=9204, granted_role_code="SYS_ADMIN", ticket_ref="INC-2026-003",
        reason="定时清理测试", minutes=1, tenant_id=TENANT,
    )
    result = svc.expire_emergency_sessions(now=datetime.utcnow() + timedelta(minutes=5))
    assert result["expired"] >= 1
    rows = svc.list_emergency(tenant_id=TENANT)["items"]
    assert any(r["status"] == "EXPIRED" for r in rows)


# ── 权限复核：不允许"打个勾就算复核过" ──────────────────────────────────────
def test_review_revoke_requires_follow_up_change(db_mode):
    campaign = svc.create_campaign(title="2026 春季高权复核", role_codes=["SYS_ADMIN"], tenant_id=TENANT)
    cid = int(campaign["campaignId"])
    item = svc.add_review_item(cid, subject_user_id=9301, role_code="SYS_ADMIN", tenant_id=TENANT)
    item_id = int(item["itemId"])

    # 回收权限却不关联安全变更 → 拒绝
    with pytest.raises(AppException) as exc:
        svc.decide_review_item(item_id, decision="REVOKE", note="该收回了", tenant_id=TENANT)
    assert exc.value.code == "REVIEW_FOLLOW_UP_REQUIRED"

    # 关联了安全变更才允许
    svc.decide_review_item(
        item_id, decision="REVOKE", note="已提交安全变更", follow_up_change_set_id=1, tenant_id=TENANT
    )
    detail = svc.get_campaign(cid, tenant_id=TENANT)
    assert detail["items"][0]["decision"] == "REVOKE"


def test_review_cannot_close_with_pending_items(db_mode):
    campaign = svc.create_campaign(title="待办复核", tenant_id=TENANT)
    cid = int(campaign["campaignId"])
    svc.add_review_item(cid, subject_user_id=9302, role_code="COUNSELOR", tenant_id=TENANT)

    with pytest.raises(AppException) as exc:
        svc.close_campaign(cid, tenant_id=TENANT)
    assert exc.value.code == "REVIEW_ITEMS_PENDING"

    items = svc.get_campaign(cid, tenant_id=TENANT)["items"]
    svc.decide_review_item(int(items[0]["itemId"]), decision="KEEP", note="继续保留", tenant_id=TENANT)
    closed = svc.close_campaign(cid, tenant_id=TENANT)
    assert closed["status"] == "CLOSED"


def test_review_item_is_deduplicated(db_mode):
    campaign = svc.create_campaign(title="去重复核", tenant_id=TENANT)
    cid = int(campaign["campaignId"])
    first = svc.add_review_item(cid, subject_user_id=9303, role_code="SYS_ADMIN", tenant_id=TENANT)
    second = svc.add_review_item(cid, subject_user_id=9303, role_code="SYS_ADMIN", tenant_id=TENANT)
    assert second["duplicated"] is True
    assert first["itemId"] == second["itemId"]
