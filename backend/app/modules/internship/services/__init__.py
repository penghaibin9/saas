"""岗位实习中心服务层。

导入服务包时安装权威合规兼容入口，确保生产路由、定时任务、测试和脚本无论
以何种顺序导入旧服务，都使用“全部必修安全课程按当前版本通过”的统一事实源。

禁止在这里给 ORM 模型动态添加非持久化字段。业务构造参数必须有真实数据库列，
或由明确的 package_type / manifest 快照表达，避免“构造成功但数据未落库”。
"""
from app.modules.internship.services import internship_compliance_authoritative_service as _compliance_authoritative  # noqa: F401,E501
