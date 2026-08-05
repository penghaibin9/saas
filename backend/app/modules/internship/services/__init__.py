"""岗位实习中心服务层。

导入服务包时安装权威合规兼容入口，确保生产路由、定时任务、测试和脚本无论
以何种顺序导入旧服务，都使用“全部必修安全课程按当前版本通过”的统一事实源。

同时安装实习成绩/总档案统一状态守卫，以及过程事实建议分、人工调分证据和
来源 hash 守卫。所有成绩写入口和总归档入口使用同一锁顺序、同一权威合规
事实与最终成绩冻结合同，禁止继续产生独立成绩归档事实或客户端直填过程分。

包 8 起，校内实习导师授权只认稳定 userId；姓名仅作展示快照，历史缺 ID 记录
运行时 fail-closed。豁免和强制归档共用文件 evidence validator，冻结文件版本、
hash 与 binding，证据变化自动 INVALIDATED。强制归档依据在生成不可变档案
快照前完成正式绑定，避免同一文件被快照链重复解释为第二个业务对象；归档
采集器只从冻结字典读取稳定 fileId，不把整份字典误当文件引用。

禁止在这里给 ORM 模型动态添加非持久化字段。业务构造参数必须有真实数据库列，
或由明确的审计/归档 manifest 快照表达，避免“构造成功但数据未落库”。
"""
from app.modules.internship.services import internship_compliance_authoritative_service as _compliance_authoritative  # noqa: F401,E501
from app.modules.internship.services import internship_complaint_auditor_scope as _complaint_auditor_scope
from app.modules.internship.services import internship_score_archive_guard as _score_archive_guard
from app.modules.internship.services import internship_score_fact_guard as _score_fact_guard
from app.modules.internship.services import internship_material_transaction_guard as _material_transaction_guard
from app.modules.internship.services import internship_score_fact_transaction_fix as _score_fact_transaction_fix
from app.modules.internship.services import internship_advisor_identity_guard as _advisor_identity_guard
from app.modules.internship.services import internship_evidence_authority_guard as _evidence_authority_guard
from app.modules.internship.services import internship_force_archive_evidence_fix as _force_archive_evidence_fix
from app.modules.internship.services import internship_archive_file_ref_fix as _archive_file_ref_fix

_complaint_auditor_scope.install()
_score_archive_guard.install()
_score_fact_guard.install()
_material_transaction_guard.install()
_score_fact_transaction_fix.install()
_advisor_identity_guard.install()
_evidence_authority_guard.install()
_force_archive_evidence_fix.install()
_archive_file_ref_fix.install()
