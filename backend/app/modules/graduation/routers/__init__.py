"""毕业设计中心 API 路由。"""

from app.modules.graduation.services.graduation_permission_extensions import (
    register_graduation_permission_extensions,
)
from app.modules.graduation.services.graduation_package9_guard import (
    install as install_graduation_package9_guard,
)

# 包加载即登记动作权限与包 9 生产守卫；未登记接口继续 fail-closed。
register_graduation_permission_extensions()
install_graduation_package9_guard()