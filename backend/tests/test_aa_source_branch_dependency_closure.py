"""施工源分支必须能够独立加载最新 main 的共享路由依赖。"""


def test_source_branch_shared_route_dependencies_import():
    from app.api.v1 import (
        mobile_graduation_guard,
        mobile_graduation_teacher_context,
        mobile_internship_context,
        mobile_internship_student,
        student_portal_graduation_guard,
    )
    from app.modules.graduation.routers import graduation_extension
    from app.modules.internship.routers import internship_enterprise_eval_versioned
    from app.student_portal.internship_router import router as student_portal_internship_router

    assert graduation_extension.router is not None
    assert internship_enterprise_eval_versioned.router is not None
    assert mobile_graduation_guard.router is not None
    assert mobile_graduation_teacher_context.router is not None
    assert mobile_internship_context.router is not None
    assert mobile_internship_student.router is not None
    assert student_portal_graduation_guard.router is not None
    assert student_portal_internship_router is not None
