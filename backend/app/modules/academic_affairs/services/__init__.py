"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

# 先加载兼容名单策略、V2-02最终教学班策略与真实模型属性守卫。
from . import academic_affairs_teaching_roster_policy as academic_affairs_teaching_roster_policy
from . import academic_affairs_teaching_class_lock_service as academic_affairs_teaching_class_service
from . import academic_affairs_teaching_class_runtime_guard as academic_affairs_teaching_class_runtime_guard
# V2-03：在总路由导入 scheduling/autoschedule 之前，注入中文规则目录、最终校验和旧请求体兼容层。
from . import academic_affairs_scheduling_rule_policy as academic_affairs_scheduling_rule_policy
from . import academic_affairs_scheduling_rule_transport as academic_affairs_scheduling_rule_transport
# 最终归档链：旧9域 + 选课 + 补考重修免修 + 评教 + 教材，共13域。
from . import academic_affairs_archive_textbook_facade as academic_affairs_archive_service
from . import academic_affairs_attendance_facade as academic_affairs_attendance_service
from . import academic_affairs_evaluation_term_facade as academic_affairs_evaluation_service
from . import academic_affairs_exam_term_facade as academic_affairs_exam_service
# V2-04：正式成绩冻结courseId/课程版本/修读次数/教学班名单版本与业务来源。
from . import academic_affairs_grade_identity_facade as academic_affairs_grade_service
from . import academic_affairs_makeup_course_identity_guard as academic_affairs_makeup_service
from . import academic_affairs_recognition_identity_guard as academic_affairs_recognition_identity_guard
from . import academic_affairs_program_quality_facade as academic_affairs_program_service
from . import academic_affairs_program_quality_complete_service as academic_affairs_program_quality_service
from . import academic_affairs_schedule_facade as academic_affairs_schedule_service
from . import academic_affairs_selection_facade as academic_affairs_selection_service
from . import academic_affairs_selection_round_facade as academic_affairs_selection_round_service
from . import academic_affairs_stats_facade as academic_affairs_stats_service
from . import academic_affairs_task_teaching_class_facade as academic_affairs_task_service
from . import academic_affairs_textbook_lock_facade as academic_affairs_textbook_service
from . import mobile_academic_affairs_facade as mobile_academic_affairs_service

sys.modules[f"{__name__}.academic_affairs_archive_service"] = academic_affairs_archive_service
sys.modules[f"{__name__}.academic_affairs_attendance_service"] = academic_affairs_attendance_service
sys.modules[f"{__name__}.academic_affairs_evaluation_service"] = academic_affairs_evaluation_service
sys.modules[f"{__name__}.academic_affairs_exam_service"] = academic_affairs_exam_service
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
sys.modules[f"{__name__}.academic_affairs_makeup_service"] = academic_affairs_makeup_service
sys.modules[f"{__name__}.academic_affairs_program_service"] = academic_affairs_program_service
sys.modules[f"{__name__}.academic_affairs_program_quality_service"] = academic_affairs_program_quality_service
# V2-02独立教学班、教师关系和名单版本最终服务。
sys.modules[f"{__name__}.academic_affairs_teaching_class_service"] = academic_affairs_teaching_class_service
sys.modules[f"{__name__}.academic_affairs_schedule_service"] = academic_affairs_schedule_service
sys.modules[f"{__name__}.academic_affairs_selection_service"] = academic_affairs_selection_service
sys.modules[f"{__name__}.academic_affairs_selection_round_service"] = academic_affairs_selection_round_service
sys.modules[f"{__name__}.academic_affairs_task_service"] = academic_affairs_task_service
sys.modules[f"{__name__}.academic_affairs_stats_service"] = academic_affairs_stats_service
sys.modules[f"{__name__}.academic_affairs_textbook_service"] = academic_affairs_textbook_service
sys.modules[f"{__name__}.mobile_academic_affairs_service"] = mobile_academic_affairs_service
