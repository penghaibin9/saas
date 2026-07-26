"""岗位实习中心服务层。

导入服务包时即安装权威合规兼容入口，确保生产路由、定时任务、测试和脚本无论
以何种顺序导入旧服务，都使用“全部必修安全课程按当前版本通过”的统一事实源。
"""
from app.modules.internship.services import internship_compliance_authoritative_service as _compliance_authoritative  # noqa: F401,E501

# 归档包旧构造代码曾传入 source_module；数据库事实由 package_type 表达，禁止为此
# 新增冗余列。SQLAlchemy 的声明式构造器只要类上存在该兼容属性即可安全接收，
# 不会写入数据库，也不会改变历史迁移或包版本契约。
from app.models import InternshipEvidencePackage as _InternshipEvidencePackage
if not hasattr(_InternshipEvidencePackage, "source_module"):
    _InternshipEvidencePackage.source_module = None
