"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

# 先加载兼容名单策略、V2-02最终教学班策略与真实模型属性守卫。
from . import academic_affairs_teaching_roster_policy as academic_affairs_teaching_roster_policy
from . import academic_affairs_teaching_class_lock_service as academic_affairs_teaching_class_service
# R8兼容层以副作用替换锁层写函数，但保留原公开模块名，避免既有消费者和合同断裂。
from . import academic_affairs_teaching_class_compat_migration_service as academic_affairs_teaching_class_compat_migration_service
from . import academic_affairs_teaching_class_runtime_guard as academic_affairs_teaching_class_runtime_guard
# V2-03：先装载目录和旧请求体兼容，再由最终安全层接管规则写入、引擎读取和教师不可排时间。
from . import academic_affairs_scheduling_rule_policy as academic_affairs_scheduling_rule_policy
from . import academic_affairs_scheduling_rule_transport as academic_affairs_scheduling_rule_transport
from . import academic_affairs_scheduling_rule_final_facade as academic_affairs_scheduling_rule_final_facade
# 最终归档链：旧9域 + 选课 + 补考重修免修 + 评教 + 教材，共13域。
from . import academic_affairs_archive_textbook_facade as academic_affairs_archive_service
from . import academic_affairs_attendance_facade as academic_affairs_attendance_service
# R9以副作用给考勤创建动作冻结名单版本，公开模块名保持兼容。
from . import academic_affairs_attendance_roster_identity_facade as academic_affairs_attendance_roster_identity_facade
from . import academic_affairs_evaluation_term_facade as academic_affairs_evaluation_service
from . import academic_affairs_exam_term_facade as academic_affairs_exam_service
# R9考务确认、铺位、发布检查统一消费冻结名单版本。
from . import academic_affairs_exam_roster_identity_facade as academic_affairs_exam_roster_identity_facade
# V2-04/R9：正式成绩冻结courseId、修读次数和统一名单版本。
from . import academic_affairs_grade_identity_facade as academic_affairs_grade_service
from . import academic_affairs_grade_roster_identity_guard as academic_affairs_grade_roster_identity_guard
from . import academic_affairs_makeup_course_identity_guard as academic_affairs_makeup_service
from . import academic_affairs_recognition_identity_guard as academic_affairs_recognition_identity_guard
from . import mobile_academic_grade_identity_facade as mobile_academic_grade_identity_facade
from . import academic_affairs_program_quality_facade as academic_affairs_program_service
# R7：完整结构校验继续复用既有层，开课差异由最终闭环统一生效状态、学时和范围口径。
from . import academic_affairs_program_opening_closure_service as academic_affairs_program_quality_service
from . import academic_affairs_schedule_facade as academic_affairs_schedule_service
from . import academic_affairs_selection_facade as academic_affairs_selection_service
# R8选课名单同步层替换 selection facade 的 adjust_record，公开名继续保持兼容。
from . import academic_affairs_selection_roster_migration_facade as academic_affairs_selection_roster_migration_facade
from . import academic_affairs_selection_round_facade as academic_affairs_selection_round_service
from . import academic_affairs_stats_facade as academic_affairs_stats_service
from . import academic_affairs_task_teaching_class_facade as academic_affairs_task_service
from . import academic_affairs_textbook_lock_facade as academic_affairs_textbook_service
# V2-05/R5：保留移动教务稳定身份/当前周 facade，再由最终层接管教师微信成绩批量保存与质量门禁。
from . import mobile_academic_affairs_facade as mobile_academic_affairs_facade
from . import mobile_academic_grade_entry_closure_service as mobile_academic_affairs_service

sys.modules[f"{__name__}.academic_affairs_archive_service"] = academic_affairs_archive_service
sys.modules[f"{__name__}.academic_affairs_attendance_service"] = academic_affairs_attendance_service
sys.modules[f"{__name__}.academic_affairs_evaluation_service"] = academic_affairs_evaluation_service
sys.modules[f"{__name__}.academic_affairs_exam_service"] = academic_affairs_exam_service
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
sys.modules[f"{__name__}.academic_affairs_makeup_service"] = academic_affairs_makeup_service
sys.modules[f"{__name__}.academic_affairs_program_service"] = academic_affairs_program_service
sys.modules[f"{__name__}.academic_affairs_program_quality_service"] = academic_affairs_program_quality_service
# R8/R9独立教学班、教师关系和名单版本最终服务。
sys.modules[f"{__name__}.academic_affairs_teaching_class_service"] = academic_affairs_teaching_class_service
sys.modules[f"{__name__}.academic_affairs_schedule_service"] = academic_affairs_schedule_service
sys.modules[f"{__name__}.academic_affairs_selection_service"] = academic_affairs_selection_service
sys.modules[f"{__name__}.academic_affairs_selection_round_service"] = academic_affairs_selection_round_service
sys.modules[f"{__name__}.academic_affairs_task_service"] = academic_affairs_task_service
sys.modules[f"{__name__}.academic_affairs_stats_service"] = academic_affairs_stats_service
sys.modules[f"{__name__}.academic_affairs_textbook_service"] = academic_affairs_textbook_service
sys.modules[f"{__name__}.mobile_academic_affairs_service"] = mobile_academic_affairs_service
