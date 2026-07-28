"""毕业设计中心 API 路由。"""

from app.modules.graduation.services.graduation_permission_extensions import (
    register_graduation_permission_extensions,
)

# 包加载即登记本轮精确安全路由的动作权限；未登记接口继续 fail-closed。
register_graduation_permission_extensions()
