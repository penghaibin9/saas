"""毕业设计中心 API 路由。"""

from app.modules.graduation.services.graduation_permission_extensions import (
    register_graduation_permission_extensions,
)
from app.modules.graduation.services.graduation_package9_guard import (
    install as install_graduation_package9_guard,
)
from app.modules.graduation.services.graduation_mentor_subject_guard import (
    install as install_graduation_mentor_subject_guard,
)

# 包加载即登记动作权限与包 9 生产守卫；未登记接口继续 fail-closed。
register_graduation_permission_extensions()
install_graduation_package9_guard()
# 主包先安装批量分配与归档守卫，再由主体类型守卫接管最终分配入口。
install_graduation_mentor_subject_guard()


def _install_review_center_projection() -> None:
    """把 W7.3 纯读投影挂到现有敏感 Router，继承同一毕业设计安全门禁。"""
    from app.modules.graduation.routers import graduation_review_center
    from app.modules.graduation.routers import graduation_sensitive_router

    graduation_sensitive_router.router.include_router(graduation_review_center.router)


_install_review_center_projection()
