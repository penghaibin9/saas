"""SYS-09 安全变更激活（真库）。

对应必测 SYS09-T01～T05：
草稿/批准/排期不改变真实权限 / 激活失败保持旧值 / 版本号与客户端一致 /
回滚生成新版本并恢复快照 / 并发激活仅一个成功。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import permission_bundle_service as pbs
from app.services import scope_policy_service as sps
from app.services import security_change_service as svc

TENANT = 8501
OTHER_TENANT = 8502
ROLE = "SEC_TEST_ROLE"


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _role_permissions(role_code: str = ROLE, tenant_id: int = TENANT) -> list[str]:
    """直接读目标表，判断「真实权限」到底变没变——不经过 service，避免被它的逻辑掩盖。"""
    from sqlalchemy import select

    from app.models.permission_governance import CustomRoleSource

    with _session() as db:
        row = db.scalars(
            select(CustomRoleSource).where(
                CustomRoleSource.tenant_id == tenant_id,
                CustomRoleSource.role_code == role_code,
                CustomRoleSource.is_deleted.is_(False),
            )
        ).first()
        return list((row.permission_codes_json or {}).get("items") or []) if row else []


def _prepare_role(tenant_id: int = TENANT, role_code: str = ROLE) -> tuple[list[str], list[str]]:
    """建一个自定义角色，返回 (当前权限, 模板上限)。"""
    pbs.bootstrap_from_code(tenant_id=tenant_id)
    ceiling = pbs.get_template("SYS_ADMIN", tenant_id=tenant_id)["permissionCeiling"]
    initial = sorted(ceiling)[:2]
    pbs.clone_template("SYS_ADMIN", new_role_code=role_code, permission_codes=initial, tenant_id=tenant_id)
    return initial, ceiling


def _new_change(tenant_id: int = TENANT) -> dict:
    return svc.create_change_set(title="调整角色权限", reason="学期初权限梳理", tenant_id=tenant_id)


def _advance(change_id: int, target: str, *, tenant_id: int = TENANT, **kw) -> dict:
    current = svc.get_change_set(change_id, tenant_id=tenant_id)
    return svc.transition(
        change_id, target, expected_version=int(current["version"]), tenant_id=tenant_id, **kw
    )


def _approve(change_id: int, tenant_id: int = TENANT) -> dict:
    """走完提交 + 自复核。测试里发起人和复核人是同一个（都是 None/同一 actor）。"""
    _advance(change_id, "PENDING_REVIEW", tenant_id=tenant_id)
    return _advance(
        change_id, "APPROVED", tenant_id=tenant_id,
        reason="自复核通过，影响已确认", self_review_ack=svc.SELF_REVIEW_TEXT,
    )


# ── SYS09-T01：草稿/批准/排期都不得改变真实权限 ─────────────────────────────
def test_t01_draft_review_schedule_do_not_touch_real_permissions(db_mode):
    initial, ceiling = _prepare_role()
    target_codes = sorted(ceiling)[:5]
    assert set(target_codes) != set(initial)

    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": target_codes}, tenant_id=TENANT,
    )
    # 加了变更项，权限不能动
    assert _role_permissions() == initial

    _advance(cid, "PENDING_REVIEW")
    assert _role_permissions() == initial, "提交审核就改了权限"

    _advance(cid, "APPROVED", reason="自复核通过", self_review_ack=svc.SELF_REVIEW_TEXT)
    assert _role_permissions() == initial, "批准就改了权限"

    _advance(cid, "SCHEDULED", scheduled_at=datetime.utcnow() + timedelta(days=1))
    assert _role_permissions() == initial, "排期就改了权限"

    # 只有激活才真正生效
    _advance(cid, "ACTIVATED")
    assert _role_permissions() == sorted(target_codes)


def test_t01_revision_only_advances_on_activation(db_mode):
    _prepare_role()
    before = svc.current_revision(tenant_id=TENANT)

    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    _approve(cid)
    assert svc.current_revision(tenant_id=TENANT) == before, "审批阶段就动了版本号"

    _advance(cid, "ACTIVATED")
    assert svc.current_revision(tenant_id=TENANT) == before + 1


def test_t01_empty_change_set_cannot_be_submitted(db_mode):
    change = _new_change()
    with pytest.raises(AppException):
        _advance(int(change["changeSetId"]), "PENDING_REVIEW")


def test_t01_locked_change_set_rejects_new_items(db_mode):
    _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    _advance(cid, "PENDING_REVIEW")
    with pytest.raises(AppException) as exc:
        svc.add_item(
            cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT
        )
    assert exc.value.code == "SECURITY_CHANGE_LOCKED"


# ── SYS09-T02：非法内容与失败时保持旧值 ─────────────────────────────────────
def test_t02_change_cannot_exceed_template_ceiling(db_mode):
    """安全变更不能成为绕过模板上限的后门。"""
    _prepare_role()
    universe = pbs.all_known_permission_codes()
    ceiling = set(pbs.get_template("SYS_ADMIN", tenant_id=TENANT)["permissionCeiling"])
    outside = next(c for c in universe if c not in ceiling)

    change = _new_change()
    with pytest.raises(AppException) as exc:
        svc.add_item(
            int(change["changeSetId"]), target_type="CUSTOM_ROLE", target_id=ROLE,
            after={"permissionCodes": [outside]}, tenant_id=TENANT,
        )
    assert exc.value.code == "PERMISSION_EXCEEDS_TEMPLATE"


def test_t02_activation_failure_keeps_old_permissions_and_revision(db_mode):
    """激活中途失败必须整体回滚：权限保持旧值，版本号不前进。"""
    initial, ceiling = _prepare_role()
    before_revision = svc.current_revision(tenant_id=TENANT)

    change = _new_change()
    cid = int(change["changeSetId"])
    # 第一条合法
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": sorted(ceiling)[:4]}, tenant_id=TENANT,
    )
    # 第二条指向一个稍后会被删掉的范围策略，制造激活期失败
    college = _mk_college(TENANT)
    policy = sps.set_policy(
        "COLLEGE_LEADER", effect="ALLOW", target_type="COLLEGE", target_id=str(college),
        reason="临时策略", tenant_id=TENANT,
    )
    svc.add_item(
        cid, target_type="SCOPE_POLICY", target_id=policy["policyId"],
        after={"status": "REVOKED"}, tenant_id=TENANT,
    )
    _approve(cid)

    _hard_delete_policy(int(policy["policyId"]))

    with pytest.raises(AppException):
        _advance(cid, "ACTIVATED")

    # 第一条虽然合法，也不能留下痕迹——整体事务回滚
    assert _role_permissions() == initial, "激活失败却留下了半生效的权限"
    assert svc.current_revision(tenant_id=TENANT) == before_revision, "激活失败却推进了版本号"
    assert svc.get_change_set(cid, tenant_id=TENANT)["status"] == "APPROVED", "状态不该变成已激活"


def _mk_college(tenant_id: int) -> int:
    from app.models import College

    with _session() as db:
        row = College(tenant_id=tenant_id, college_name="安全变更测试学院", status="ACTIVE")
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)


def _hard_delete_policy(policy_id: int) -> None:
    from sqlalchemy import delete

    from app.models.scope_policy import ScopePolicyTarget

    with _session() as db:
        db.execute(delete(ScopePolicyTarget).where(ScopePolicyTarget.id == policy_id))
        db.commit()


def test_t02_illegal_transition_rejected(db_mode):
    _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    # 草稿不能直接激活
    with pytest.raises(AppException) as exc:
        _advance(cid, "ACTIVATED")
    assert exc.value.code == "STATE_TRANSITION_DENIED"


def test_t02_self_review_requires_exact_ack_text(db_mode):
    _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    _advance(cid, "PENDING_REVIEW")

    # 不填确认文本
    with pytest.raises(AppException) as exc:
        _advance(cid, "APPROVED", reason="随手点通过")
    assert exc.value.code == "SELF_REVIEW_ACK_REQUIRED"

    # 文本不完全一致也不行
    with pytest.raises(AppException):
        _advance(cid, "APPROVED", reason="随手点通过", self_review_ack="我已确认")

    approved = _advance(
        cid, "APPROVED", reason="影响已逐条确认", self_review_ack=svc.SELF_REVIEW_TEXT
    )
    assert approved["status"] == "APPROVED"
    assert approved["selfReviewed"] is True


# ── SYS09-T03：版本号可被客户端读取且单调 ───────────────────────────────────
def test_t03_revision_is_monotonic_and_tenant_scoped(db_mode):
    _prepare_role()
    _prepare_role(tenant_id=OTHER_TENANT, role_code=ROLE)

    assert svc.current_revision(tenant_id=TENANT) == 0
    assert svc.current_revision(tenant_id=OTHER_TENANT) == 0

    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    _approve(cid)
    _advance(cid, "ACTIVATED")

    assert svc.current_revision(tenant_id=TENANT) == 1
    # 另一个学校的版本号不受影响
    assert svc.current_revision(tenant_id=OTHER_TENANT) == 0


def test_t03_activation_history_records_every_step(db_mode):
    initial, ceiling = _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": sorted(ceiling)[:3]}, tenant_id=TENANT,
    )
    _approve(cid)
    _advance(cid, "ACTIVATED")
    _advance(cid, "ROLLED_BACK", reason="发现影响过大")

    history = svc.activation_history(tenant_id=TENANT)
    actions = [h["action"] for h in history["items"]]
    assert actions == ["ROLLBACK", "ACTIVATE"]
    assert history["currentRevision"] == 2
    assert all(h["traceId"] for h in history["items"])


# ── SYS09-T04：回滚恢复快照且版本号继续前进 ─────────────────────────────────
def test_t04_rollback_restores_snapshot_and_advances_revision(db_mode):
    initial, ceiling = _prepare_role()
    target_codes = sorted(ceiling)[:6]

    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": target_codes}, tenant_id=TENANT,
    )
    _approve(cid)
    _advance(cid, "ACTIVATED")
    assert _role_permissions() == sorted(target_codes)
    revision_after_activate = svc.current_revision(tenant_id=TENANT)

    _advance(cid, "ROLLED_BACK", reason="回退到调整前")
    # 权限恢复
    assert _role_permissions() == initial
    # 版本号继续前进而不是退回——安全历史只进不退
    assert svc.current_revision(tenant_id=TENANT) == revision_after_activate + 1


def test_t04_rolled_back_change_is_terminal(db_mode):
    initial, ceiling = _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": sorted(ceiling)[:3]}, tenant_id=TENANT,
    )
    _approve(cid)
    _advance(cid, "ACTIVATED")
    _advance(cid, "ROLLED_BACK", reason="回退")
    with pytest.raises(AppException):
        _advance(cid, "ACTIVATED")


# ── SYS09-T05：并发与版本冲突 ───────────────────────────────────────────────
def test_t05_stale_version_is_rejected(db_mode):
    _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    stale = int(svc.get_change_set(cid, tenant_id=TENANT)["version"])
    _advance(cid, "PENDING_REVIEW")

    with pytest.raises(AppException) as exc:
        svc.transition(cid, "APPROVED", expected_version=stale, reason="用旧版本号", tenant_id=TENANT)
    assert exc.value.code == "VERSION_CONFLICT"


def test_t05_revision_uniqueness_is_enforced_by_database(db_mode):
    """两次激活抢同一个版本号时，数据库唯一约束必须兜底。"""
    from sqlalchemy.exc import IntegrityError

    from app.models.security_change import SecurityActivation

    _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(cid, target_type="CUSTOM_ROLE", target_id=ROLE, after={"permissionCodes": []}, tenant_id=TENANT)
    _approve(cid)
    _advance(cid, "ACTIVATED")
    revision = svc.current_revision(tenant_id=TENANT)

    with _session() as db:
        db.add(
            SecurityActivation(
                tenant_id=TENANT, revision=revision, change_set_id=cid, action="ACTIVATE",
                snapshot_json={"items": []},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_t05_scheduled_activation_is_idempotent(db_mode):
    initial, ceiling = _prepare_role()
    change = _new_change()
    cid = int(change["changeSetId"])
    svc.add_item(
        cid, target_type="CUSTOM_ROLE", target_id=ROLE,
        after={"permissionCodes": sorted(ceiling)[:3]}, tenant_id=TENANT,
    )
    _approve(cid)
    _advance(cid, "SCHEDULED", scheduled_at=datetime.utcnow() + timedelta(hours=1))

    early = svc.activate_due_change_sets(now=datetime.utcnow())
    assert not any(i["changeSetId"] == str(cid) for i in early["activated"])
    assert _role_permissions() == initial

    later = datetime.utcnow() + timedelta(hours=2)
    first = svc.activate_due_change_sets(now=later)
    assert any(i["changeSetId"] == str(cid) for i in first["activated"])
    second = svc.activate_due_change_sets(now=later)
    assert not any(i["changeSetId"] == str(cid) for i in second["activated"])
    assert svc.current_revision(tenant_id=TENANT) == 1


def test_t05_cross_tenant_change_is_invisible(db_mode):
    _prepare_role()
    change = _new_change()
    with pytest.raises(AppException):
        svc.get_change_set(int(change["changeSetId"]), tenant_id=OTHER_TENANT)
