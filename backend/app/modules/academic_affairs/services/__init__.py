"""教务中心服务包。

本包集中声明各业务域的正式公开入口。兼容模块只保留历史导入路径，Router 不得自行选择
旧实现或依赖导入顺序抢占函数。
"""

# 第一个公开入口完成基础 db_service -> app.models 初始化。
from . import academic_affairs_dashboard_scope_facade as academic_affairs_service

# 有效成绩安全层必须在其它可能按值导入 policy 函数的业务 Service 之前安装。
# 过去这组模块由 app.models.academic_affairs_registry 反向 import，冷启动会形成
# services -> db_service -> app.models -> registry -> services -> db_service 的循环依赖。
# 现在模型注册表保持 model-only，在基础模型完成后由 Service 包统一、按固定顺序安装：
# 兼容身份/学期顺序 -> 当前学期 -> ACTIVE-only -> 无策略 fail-closed。
from . import academic_affairs_effective_grade_policy_compat
from . import academic_affairs_effective_grade_policy_current_term
from . import academic_affairs_effective_grade_active_only
from . import academic_affairs_effective_grade_policy_failclosed

academic_affairs_effective_grade_policy_failclosed.install()

# 其余各域最终公开入口。
from . import academic_affairs_archive_service
from . import academic_affairs_attendance_public_service as academic_affairs_attendance_service
from . import academic_affairs_stats_public_service as academic_affairs_stats_service
from . import academic_affairs_evaluation_public_service as academic_affairs_evaluation_service
from . import academic_affairs_selection_final_service as academic_affairs_selection_service
from . import academic_affairs_selection_round_facade as academic_affairs_selection_round_service
from . import academic_affairs_scheduling_public_service as academic_affairs_scheduling_service
from . import academic_affairs_autoschedule_final_service as academic_affairs_autoschedule_service
from . import academic_affairs_schedule_final_service as academic_affairs_schedule_service
from . import academic_affairs_exam_facade as academic_affairs_exam_service
from . import academic_affairs_textbook_final_facade as academic_affairs_textbook_service
from . import academic_affairs_recognition_public_service as academic_affairs_recognition_service
from . import academic_affairs_major_split_public_service as academic_affairs_major_split_service
from . import academic_affairs_org_fact_facade as academic_affairs_org_service
from . import mobile_academic_affairs_public_service as mobile_academic_affairs_service

# D6：Selection Final 模块对象仍是唯一公开 owner；这里只安装等价只读优化/范围门禁。
# AaSelectionRecord 写链、Selection Final 状态机和 TeachingRoster 投影均不在此模块实现。
from . import academic_affairs_selection_read_service
from . import academic_affairs_selection_round_read_guard

for _selection_read_name in (
    "list_batches", "get_batch", "list_courses", "course_roster", "student_courses",
    "reselect_guide", "batch_stats", "get_conflict_report", "export_conflict_report_xlsx",
    "list_archived_batches", "archive_detail", "export_archive_xlsx",
):
    setattr(
        academic_affairs_selection_service,
        _selection_read_name,
        getattr(academic_affairs_selection_read_service, _selection_read_name),
    )
academic_affairs_selection_round_service.list_rounds = academic_affairs_selection_round_read_guard.list_rounds

# 统计 08/09/14 历史曾存在同名重复定义，后定义的缩水实现会覆盖完整合同，连内部 xlsx 导出一起打坏。
# 显式安装唯一 canonical contract；公开 wrapper 动态调用 legacy 时与 legacy 内部 export 使用同一函数对象。
from . import academic_affairs_stats_contract_facade

academic_affairs_stats_contract_facade.install()
academic_affairs_stats_service.resource_stats = academic_affairs_stats_contract_facade.resource_stats
academic_affairs_stats_service.resource_detail = academic_affairs_stats_contract_facade.resource_detail

# 学生课表必须按当前 schedule batch 合并 LOCKED 选课，禁止把其它批次/学期排课串进来。
from . import academic_affairs_schedule_facade as academic_affairs_schedule_student_view_facade

academic_affairs_schedule_service.student_view = academic_affairs_schedule_student_view_facade.student_view

# V2-03 最终规则安全层必须成为包级可见入口，并显式绑定到公开排课/自动排课服务。
from . import academic_affairs_scheduling_rule_final_facade

academic_affairs_autoschedule_service._load_params = (
    academic_affairs_scheduling_rule_final_facade.load_effective_params
)
academic_affairs_scheduling_service.save_rule = academic_affairs_scheduling_rule_final_facade.save_rule
academic_affairs_scheduling_service.delete_rule = academic_affairs_scheduling_rule_final_facade.delete_rule
academic_affairs_scheduling_service.submit_availability = (
    academic_affairs_scheduling_rule_final_facade.submit_availability
)
academic_affairs_scheduling_service.list_availability = (
    academic_affairs_scheduling_rule_final_facade.list_availability
)
academic_affairs_scheduling_service.review_availability = (
    academic_affairs_scheduling_rule_final_facade.review_availability
)

# 包 3：成绩单目标学生与无行政班成绩任务必须经过对象级范围裁决。
from . import academic_affairs_object_scope_guard

academic_affairs_object_scope_guard.install()

# Stage C2：对象级范围门禁之后再包一层历史身份；学期成绩单只能读取
# AcademicFact(as_of=term.start_date)，累计成绩单禁止隐式拿当前专业当 header。
from . import academic_affairs_transcript_historical_facade

academic_affairs_transcript_historical_facade.install()

# 包 4：毕业资格跨域事实必须命中正式完成状态、成绩和归档证据。
from . import academic_affairs_graduation_truth_guard

academic_affairs_graduation_truth_guard.install()

# Stage C3：预览/正式预审共用同一 evaluator；正式预审和终审追加不可变 Run/Decision。
# 正式 overall 只允许由 immutable service 内部的单一 fail-closed 实现决定，
# 禁止再从包初始化阶段 monkey-patch 第二套规则覆盖它。
from . import academic_affairs_graduation_immutable_service

academic_affairs_graduation_immutable_service.install()

# 包 5：异动详情范围、所属学期与真实工作流受理人 fail-closed。
from . import academic_affairs_change_safety_guard

academic_affairs_change_safety_guard.install()

# Stage C1：在包 5 安全层之后叠加 temporal fact / future-effective 语义；不得绕过原门禁。
from . import academic_affairs_change_temporal_guard

academic_affairs_change_temporal_guard.install()

# Stage C3：正式归档确认必须在同事务生成不可变 Manifest；归档后纠错仅追加 V2+，不重开学期。
from . import academic_affairs_archive_manifest_service

academic_affairs_archive_manifest_service.install()

# Stage C3：高风险归档命令必须有稳定 actor。真实账号优先用 DB id；旧签名身份
# 只生成租户绑定的确定性审计 key，不参与授权，仅用于不可变证据和双人复核比较。
from . import academic_affairs_archive_actor_identity

academic_affairs_archive_actor_identity.install(academic_affairs_archive_manifest_service)

# Stage C3：ARCHIVED 是不可逆历史事实；正式归档入口不得再走普通 unfreeze 回退到 DRAFT/PUBLISHED。
from . import academic_affairs_archive_immutable_guard

academic_affairs_archive_immutable_guard.install(academic_affairs_archive_service)

# 包 1：正式成绩更正统一命令——申请不改正式成绩，终审追加版本且与工作流同事务。
from . import academic_affairs_grade_correction_command

academic_affairs_grade_correction_command.install()

# 成绩审计普通教师必须按真实任务/记录对象归属裁决，禁止用展示姓名充当身份键。
from . import academic_affairs_grade_audit_scope_guard

academic_affairs_grade_audit_scope_guard.install()

# PR #101 生产复审：只读便利性加固必须在真实包初始化时自动生效，不能依赖测试手动 install。
# 该 guard 仅收紧 dataScope、pageSize 和冲突详情脱敏，不接管任何 canonical 写链。
from . import academic_affairs_production_audit_guard

academic_affairs_production_audit_guard.install()

# 学籍名册页面保持 200 行 pageSize 上限；完整 XLSX 导出走独立 SQL 查询，
# 禁止用 pageSize=10000 绕过公开列表边界或在 2 万学生学校静默截断。
from . import academic_affairs_roster_export_guard

academic_affairs_roster_export_guard.install()

# 学籍更正高频台账只读收口：SQL count/page + STUDENT/SELF 精确到人，
# 创建、材料、敏感字段加密和审核命令仍由既有 canonical service 持有。
from . import academic_affairs_roster_correction_read_guard

academic_affairs_roster_correction_read_guard.install()

# 注册管理高频读侧继续复用原事实与写链，仅把资格/异常/暂缓改为 SQL 真分页，
# 并保持 STUDENT/SELF 精确到人的 fail-closed dataScope，禁止扩大到整班。
from . import academic_affairs_registration_read_guard

academic_affairs_registration_read_guard.install()

# PR #101 生产复审：正式归档批次必须绑定一个真实学期；历史 nullable 列只作兼容，
# 任何新建 HTTP/脚本/内部 service 调用都不得生成不会冻结学期的孤儿归档批次。
from . import academic_affairs_archive_term_guard

academic_affairs_archive_term_guard.install()

# PR #101 生产复审：归档批次列表保持原公开 DTO，只把全量 materialize 后切片改成
# SQL COUNT + OFFSET/LIMIT，并统一 page/pageSize 边界；不接管任何归档写链。
from . import academic_affairs_archive_read_guard

academic_affairs_archive_read_guard.install()

# PR #101 生产复审：统计总览的纯 count/rate 指标由数据库聚合，禁止为求两个数字
# materialize 全校注册、成绩、考务、毕业等明细；public/canonical/XLSX owner 均不改变。
from . import academic_affairs_stats_scale_guard

academic_affairs_stats_scale_guard.install()

# PR #101 生产复审：高频统计下钻必须 SQL 真分页并消除 N+1；当前先收课表冲突，
# 返回 DTO/冲突判定口径不变，不接管排课事实或写链。
from . import academic_affairs_stats_detail_scale_guard

academic_affairs_stats_detail_scale_guard.install()
