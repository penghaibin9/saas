from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_b6_product_iam_has_dedicated_platform_workspace():
    routes = _read("frontend/src/modules/platform/platform.routes.js")
    view = _read("frontend/src/modules/platform/views/control/PlatformProductIamView.vue")
    api = _read("frontend/src/modules/platform/api/productIam.api.js")
    layout = _read("frontend/src/modules/platform/views/AdminPlatformLayout.vue")
    assert "path: 'product-iam'" in routes
    assert "PlatformProductIamView.vue" in routes
    assert "permissionKey: 'platform.productIam.view'" in routes
    assert "redirect: '/admin/platform/product-iam'" in routes
    assert "'plt-standards': '/admin/platform/product-iam'" in layout
    assert "/platform/product-iam/source" in api
    assert "/platform/product-iam/releases" in api
    assert "internshipHealthy" in view
    assert "secondRecruitmentModule" in view
    assert "/admin/platform/access" not in view


def test_b7_school_iam_workspace_consumes_canonical_endpoints():
    routes = _read("frontend/src/modules/system/system.routes.js")
    facade = _read("frontend/src/modules/system/views/SystemIamWorkspaceView.vue")
    assert "SystemIamGovernancePanel" in facade and "<SystemRoleListView" in facade
    view = facade + _read("frontend/src/modules/system/components/workspace/SystemIamGovernancePanel.vue")
    api = _read("frontend/src/modules/system/api/schoolIam.api.js")
    layout = _read("frontend/src/modules/system/views/AdminSystemLayout.vue")
    assert "path: 'iam'" in routes
    assert "SystemIamWorkspaceView.vue" in routes
    assert "permissionKey: 'systemAdmin.role.view'" in routes
    assert "'sys-access': '/admin/system/iam'" in layout
    for endpoint in (
        "/system/iam/summary",
        "/system/iam/permission-catalog",
        "/system/iam/role-templates",
        "/system/iam/access-explain/",
    ):
        assert endpoint in api
    assert "/impact" in api
    assert "/members" in api
    assert "/audit" in api
    for surface in ("roles", "templates", "members", "permissions", "dataScopes", "delegations", "securityChanges", "accessExplain"):
        assert surface in view
    assert "企业实习权限" in view
    assert "企业成员和访问授权" in view
    assert "业务守卫" in view


def test_b7_exposes_real_template_provenance_drift_and_school_scoped_impact():
    # The historical workspace module is now only a compatibility import shim.
    # Contracts must follow the canonical B7 Authority implementation so the
    # source gate cannot accidentally force logic back into the shim.
    service = _read("backend/app/modules/system_admin/services/school_iam_authority_projection_service.py")
    router = _read("backend/app/modules/system_admin/routers/school_iam_router.py")
    facade = _read("frontend/src/modules/system/views/SystemIamWorkspaceView.vue")
    assert "SystemIamGovernancePanel" in facade and "<SystemRoleListView" in facade
    view = facade + _read("frontend/src/modules/system/components/workspace/SystemIamGovernancePanel.vue")
    for term in (
        "templateProvenance",
        "sourceTemplateVersion",
        "currentTemplateVersion",
        "runtimeVsRecorded",
        "templateVersionDrift",
        "templateImpact",
        "DERIVED_PINNED",
        "school_template_impact",
    ):
        assert term in service
    assert "CustomRoleSource.tenant_id == tid" in service
    assert '"tenantId": str(tid)' in service
    assert '"automaticUpgrade": False' in service
    assert '/role-templates/{template_id}/impact' in router
    assert "templateImpact" in view
    assert "provenanceText" in view
    assert "driftText" in view
    assert "impactText" in view
    assert 'value="internship"' not in view


def test_b7_reuses_20k_safe_member_and_security_audit_pagination():
    i4 = _read("backend/app/modules/system_admin/routers/system_i4_router.py")
    api = _read("frontend/src/modules/system/api/schoolIam.api.js")
    facade = _read("frontend/src/modules/system/views/SystemIamWorkspaceView.vue")
    assert "SystemIamGovernancePanel" in facade and "<SystemRoleListView" in facade
    view = facade + _read("frontend/src/modules/system/components/workspace/SystemIamGovernancePanel.vue")
    assert '/system/roles/{role_id}/members' in i4
    assert '/system/roles/{role_id}/audit' in i4
    assert 'pageSize: int = Query(50, ge=1, le=200)' in i4
    assert 'SecurityAuditLog.tenant_id == tenant_id' in i4
    assert 'Role.tenant_id == int(tenant_id)' in i4
    assert "roleMembers" in api and "roleAudit" in api
    assert "loadRoleEvidence" in view
    assert "安全审计日志" in view
    assert "evidencePages" in view
    assert "不会把前 50 条预览数据当作完整结果" in view


def test_role_list_member_count_opens_paginated_member_directory():
    view = _read("frontend/src/modules/system/views/SystemRoleListView.vue")
    api = _read("frontend/src/modules/system/api/schoolIam.api.js")
    router = _read("backend/app/modules/system_admin/routers/system_i4_router.py")
    assert "<RoleMembersPanel" in view
    assert "openRole(row.id, 'members')" in view
    view = _read("frontend/src/modules/system/components/workspace/RoleMembersPanel.vue")
    assert "schoolIamApi.roleMembers" in view
    assert "wc.paged(wc.unwrap(await fn()))" in view
    assert "loadMembers(members.page + 1)" in view
    assert "openAdd" in view
    assert "batchAddRoleMembers" in view and "roleMemberCandidates" in view
    assert "member-candidates" in api and "members/batch" in api
    assert "/system/roles/{role_id}/member-candidates" in router
    assert "/system/roles/{role_id}/members/batch" in router


def test_b6_b7_do_not_create_second_permission_authority_in_frontend():
    product = _read("frontend/src/modules/platform/views/control/PlatformProductIamView.vue")
    school = _read("frontend/src/modules/system/components/workspace/SystemIamGovernancePanel.vue")
    assert "权限目录" in product
    assert "权限目录" in school
    assert "productIamApi.source()" in product
    assert "schoolIamApi.permissionCatalog()" in school
