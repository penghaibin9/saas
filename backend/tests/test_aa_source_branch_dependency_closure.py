"""施工源分支必须能够独立加载共享路由依赖。"""


def test_source_branch_shared_route_dependencies_import():
    from app.modules.graduation.routers import graduation_extension
    from app.modules.graduation.services import graduation_consistency_install
    from app.modules.internship.routers import internship_enterprise_eval_versioned

    assert graduation_extension.router is not None
    assert callable(graduation_consistency_install.install_consistency_guards)
    assert internship_enterprise_eval_versioned.router is not None
