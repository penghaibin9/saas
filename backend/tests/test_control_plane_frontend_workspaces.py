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
    view = _read("frontend/src/modules/system/views/SystemIamWorkspaceView.vue")
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
    for surface in ("roles", "templates", "members", "permissions", "dataScopes", "delegations", "securityChanges", "accessExplain"):
        assert surface in view
    assert "enterprise.internship.*" in view
    assert "EnterpriseMember / AccessGrant" in view
    assert "DOMAIN_GUARD" in view or "Domain Guard" in view


def test_b6_b7_do_not_create_second_permission_authority_in_frontend():
    product = _read("frontend/src/modules/platform/views/control/PlatformProductIamView.vue")
    school = _read("frontend/src/modules/system/views/SystemIamWorkspaceView.vue")
    assert "Permission Catalog" in product
    assert "Permission Catalog" in school
    assert "productIamApi.source()" in product
    assert "schoolIamApi.permissionCatalog()" in school
