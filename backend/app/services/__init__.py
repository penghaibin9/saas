"""应用服务层公共初始化。"""

# P0-05：在任何业务模块取得 mobile_student_service.resolve_student 前，先安装统一身份解析器。
from . import mobile_student_identity_facade as mobile_student_identity_facade

__all__ = ["mobile_student_identity_facade"]
