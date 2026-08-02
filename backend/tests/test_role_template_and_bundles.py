"""SYS-06 权限包、交付角色模板与自定义角色（真库）。

对应必测 SYS06-T01～T04。额外锁住一条回归：通配展开必须取自权限码权威全集
（``collect_concrete_permission_codes``），不能从 ROLE_PERMISSIONS 的值里筛——
后者会让 ``systemAdmin.*`` 展开出 0 条，SYS_ADMIN 的模板上限变成空集，
学校自定义角色一个权限都配不出来，而且不报错，静默算错。
"""
import pytest

from app.core.exceptions import AppException
from app.services import permission_bundle_service as svc

TENANT = 8701
OTHER_TENANT = 8702


# ── 通配展开回归锁 ──────────────────────────────────────────────────────────
def test_wildcard_expansion_uses_authoritative_universe():
    universe = svc.all_known_permission_codes()
    assert len(universe) > 200, "权限码全集异常偏小，可能取错了来源"

    star = svc.expand_wildcard("*")
    assert star == universe

    sys_admin = svc.expand_wildcard("systemAdmin.*")
    assert len(sys_admin) > 0, "systemAdmin.* 展开为空——又取回 ROLE_PERMISSIONS 了"
    assert all(c.startswith("systemAdmin.") for c in sys_admin)

    # 后缀通配也要能展开（既有 expand_permission_patterns 支持）
    assert len(svc.expand_wildcard("*.view")) > 0


# ── SYS06-T01：学校角色权限必须是模板上限的子集 ─────────────────────────────
def test_t01_custom_role_cannot_exceed_template_ceiling(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    template = svc.get_template("SYS_ADMIN", tenant_id=TENANT)
    ceiling = set(template["permissionCeiling"])
    assert ceiling, "模板上限为空，说明通配没展开"

    # 取上限内的一个子集：允许
    subset = sorted(ceiling)[:3]
    created = svc.clone_template(
        "SYS_ADMIN", new_role_code="SCHOOL_SYS_ADMIN", permission_codes=subset, tenant_id=TENANT
    )
    assert set(created["permissionCodes"]) == set(subset)
    assert created["sourceTemplate"] == "SYS_ADMIN"

    # 越过上限：拒绝
    outside = next(c for c in svc.all_known_permission_codes() if c not in ceiling)
    with pytest.raises(AppException) as exc:
        svc.clone_template(
            "SYS_ADMIN", new_role_code="BAD_ROLE", permission_codes=[*subset, outside], tenant_id=TENANT
        )
    assert exc.value.code == "PERMISSION_EXCEEDS_TEMPLATE"
    assert exc.value.http_status == 403


def test_t01_update_also_enforces_ceiling(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    ceiling = set(svc.get_template("SYS_ADMIN", tenant_id=TENANT)["permissionCeiling"])
    created = svc.clone_template(
        "SYS_ADMIN", new_role_code="ROLE_TO_EDIT", permission_codes=sorted(ceiling)[:2], tenant_id=TENANT
    )

    outside = next(c for c in svc.all_known_permission_codes() if c not in ceiling)
    with pytest.raises(AppException) as exc:
        svc.update_custom_role(
            "ROLE_TO_EDIT", permission_codes=[outside],
            expected_version=int(created["version"]), tenant_id=TENANT,
        )
    assert exc.value.code == "PERMISSION_EXCEEDS_TEMPLATE"

    # 上限内可以正常裁剪
    updated = svc.update_custom_role(
        "ROLE_TO_EDIT", permission_codes=sorted(ceiling)[:1],
        expected_version=int(created["version"]), tenant_id=TENANT,
    )
    assert len(updated["permissionCodes"]) == 1


def test_t01_clone_without_codes_inherits_full_ceiling(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    ceiling = set(svc.get_template("ACADEMIC_ADMIN", tenant_id=TENANT)["permissionCeiling"])
    created = svc.clone_template("ACADEMIC_ADMIN", new_role_code="SCHOOL_AA_ADMIN", tenant_id=TENANT)
    assert set(created["permissionCodes"]) == ceiling


def test_t01_duplicate_role_code_rejected(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    svc.clone_template("SYS_ADMIN", new_role_code="DUP_ROLE", permission_codes=[], tenant_id=TENANT)
    with pytest.raises(AppException) as exc:
        svc.clone_template("SYS_ADMIN", new_role_code="DUP_ROLE", permission_codes=[], tenant_id=TENANT)
    assert exc.value.code == "ROLE_ALREADY_EXISTS"


def test_t01_stale_version_rejected(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    created = svc.clone_template("SYS_ADMIN", new_role_code="VERSION_ROLE", permission_codes=[], tenant_id=TENANT)
    svc.update_custom_role(
        "VERSION_ROLE", permission_codes=[], expected_version=int(created["version"]), tenant_id=TENANT
    )
    with pytest.raises(AppException) as exc:
        svc.update_custom_role(
            "VERSION_ROLE", permission_codes=[], expected_version=int(created["version"]), tenant_id=TENANT
        )
    assert exc.value.code == "VERSION_CONFLICT"


# ── SYS06-T02：交付模板只读，不会被学校改动污染 ─────────────────────────────
def test_t02_delivered_templates_are_marked_and_shared(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    templates = svc.list_templates(tenant_id=TENANT)["items"]
    assert templates
    assert all(t["delivered"] for t in templates), "交付模板必须标记为 DELIVERED"

    # 学校自定义角色不会混进模板列表
    svc.clone_template("SYS_ADMIN", new_role_code="MY_ROLE", permission_codes=[], tenant_id=TENANT)
    after = svc.list_templates(tenant_id=TENANT)["items"]
    assert len(after) == len(templates)
    assert "MY_ROLE" not in {t["templateCode"] for t in after}


def test_t02_bootstrap_is_idempotent(db_mode):
    first = svc.bootstrap_from_code(tenant_id=TENANT)
    second = svc.bootstrap_from_code(tenant_id=TENANT)
    assert first["createdTemplates"] > 0
    assert second["createdTemplates"] == 0
    assert second["createdBundles"] == 0
    assert second["createdWildcards"] == 0


def test_t02_bundles_cover_every_domain(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    bundles = svc.list_bundles(tenant_id=TENANT)["items"]
    assert bundles
    assert all(b["delivered"] for b in bundles)
    assert all(b["permissionCount"] > 0 for b in bundles), "空权限包没有意义"
    domains = {b["ownerDomain"] for b in bundles}
    assert "SYSTEMADMIN" in domains or "SYSTEM" in {d.upper() for d in domains}


# ── SYS06-T03：通配权限进入退役队列并可见 ───────────────────────────────────
def test_t03_wildcards_are_registered_with_expansion(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    queue = svc.wildcard_queue(tenant_id=TENANT)
    items = queue["items"]
    assert items, "代码里明明有通配，退役队列却是空的"

    holders = {i["roleCode"] for i in items}
    assert "SCHOOL_ADMIN" in holders, "持有 * 的学校管理员必须被登记"

    school_admin = next(i for i in items if i["roleCode"] == "SCHOOL_ADMIN" and i["wildcardCode"] == "*")
    assert school_admin["expandedCount"] == len(svc.all_known_permission_codes())
    assert school_admin["status"] == "PENDING"

    # 展开是下界这件事必须对使用者写明，不能让人以为是精确全集
    assert "下界" in queue["disclaimer"]


def test_t03_coverage_gap_is_surfaced_not_hidden(db_mode):
    """展开为 0 的通配必须被显式标成覆盖缺口。

    实测发现 30 个通配里有 10 个展开为 0（``dataCenter.*`` / ``employment.*`` 等），
    原因是权限目录 SCHOOL_PERMISSION_GROUPS 没覆盖这些域。真实鉴权走前缀匹配、
    不受影响，所以这些通配其实**照样在放行**，只是治理侧看不见它放开了什么——
    比普通通配更危险。绝不能因为"展开是 0"就当成无害而放松断言。
    """
    svc.bootstrap_from_code(tenant_id=TENANT)
    queue = svc.wildcard_queue(tenant_id=TENANT)
    module_wildcards = [i for i in queue["items"] if i["wildcardCode"].endswith(".*")]
    assert module_wildcards

    # 至少要有一部分能正常展开，否则说明权限码来源整个取错了
    assert any(i["expandedCount"] > 0 for i in module_wildcards)

    # 展开数与 coverageGap 必须一致，缺口要出现在汇总里
    for item in module_wildcards:
        assert item["coverageGap"] == (item["expandedCount"] == 0)
        if item["coverageGap"]:
            assert "权限目录未覆盖" in (item["note"] or ""), "缺口没有写明原因，运维看不懂"
            assert item["wildcardCode"] in queue["coverageGaps"]

    assert "需先补全权限目录再退役" in queue["disclaimer"]


# ── SYS06-T04：不改动真实鉴权，且租户隔离 ───────────────────────────────────
def test_t04_saving_custom_role_does_not_change_real_authz(db_mode):
    """治理层保存不得影响 ROLE_PERMISSIONS 的鉴权结果。"""
    from app.core.permissions import has_permission

    svc.bootstrap_from_code(tenant_id=TENANT)
    user = {"currentRole": {"roleCode": "SYS_ADMIN"}, "tenantId": TENANT}
    before = has_permission(user, "systemAdmin.role.view")

    svc.clone_template("SYS_ADMIN", new_role_code="NO_EFFECT_ROLE", permission_codes=[], tenant_id=TENANT)
    after = has_permission(user, "systemAdmin.role.view")
    assert before == after, "治理层写入竟然改变了真实鉴权结果"


def test_t04_custom_roles_are_tenant_isolated(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    svc.bootstrap_from_code(tenant_id=OTHER_TENANT)
    svc.clone_template("SYS_ADMIN", new_role_code="TENANT_A_ROLE", permission_codes=[], tenant_id=TENANT)

    mine = {r["roleCode"] for r in svc.list_custom_roles(tenant_id=TENANT)["items"]}
    theirs = {r["roleCode"] for r in svc.list_custom_roles(tenant_id=OTHER_TENANT)["items"]}
    assert "TENANT_A_ROLE" in mine
    assert "TENANT_A_ROLE" not in theirs

    # 同名角色在另一个租户下可以独立存在
    svc.clone_template("SYS_ADMIN", new_role_code="TENANT_A_ROLE", permission_codes=[], tenant_id=OTHER_TENANT)
    assert "TENANT_A_ROLE" in {r["roleCode"] for r in svc.list_custom_roles(tenant_id=OTHER_TENANT)["items"]}


def test_t04_unknown_template_returns_not_found(db_mode):
    svc.bootstrap_from_code(tenant_id=TENANT)
    with pytest.raises(AppException):
        svc.get_template("NOT_A_REAL_TEMPLATE", tenant_id=TENANT)
