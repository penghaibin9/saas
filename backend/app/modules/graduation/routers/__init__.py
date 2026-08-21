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
from app.modules.graduation.services.graduation_review_version_guard import (
    install as install_graduation_review_version_guard,
)

# 包加载即登记动作权限与生产守卫；未登记接口继续 fail-closed。
register_graduation_permission_extensions()
install_graduation_package9_guard()
# 主包先安装批量分配与归档守卫，再由主体类型守卫接管最终分配入口。
install_graduation_mentor_subject_guard()
# W7.1 在既有 GraduationReview Authority 上冻结 canonical FileVersion，不新建第二状态源。
install_graduation_review_version_guard()
