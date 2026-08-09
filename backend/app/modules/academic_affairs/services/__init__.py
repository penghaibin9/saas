"""教务中心服务包。

本包集中声明各业务域的正式公开入口。兼容模块只保留历史导入路径，Router 不得自行选择
旧实现或依赖导入顺序抢占函数。
"""

# 各域最终公开入口。
from . import academic_affairs_dashboard_scope_facade as academic_affairs_service
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
