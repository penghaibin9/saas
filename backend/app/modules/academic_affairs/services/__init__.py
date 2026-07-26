"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

from . import academic_affairs_archive_selection_facade as academic_affairs_archive_service
from . import academic_affairs_attendance_facade as academic_affairs_attendance_service
from . import academic_affairs_evaluation_facade as academic_affairs_evaluation_service
from . import academic_affairs_exam_facade as academic_affairs_exam_service
from . import academic_affairs_grade_roster_facade as academic_affairs_grade_service
from . import academic_affairs_makeup_facade as academic_affairs_makeup_service
from . import academic_affairs_schedule_facade as academic_affairs_schedule_service
from . import academic_affairs_selection_facade as academic_affairs_selection_service
from . import academic_affairs_stats_facade as academic_affairs_stats_service
from . import academic_affairs_task_facade as academic_affairs_task_service
from . import mobile_academic_affairs_facade as mobile_academic_affairs_service

# 归档路由和业务模块的完整路径导入统一进入最终叠加策略层（含第10域选课名单）。
sys.modules[f"{__name__}.academic_affairs_archive_service"] = academic_affairs_archive_service
# 普通教师创建考勤必须选择当前学期本人教学任务。
sys.modules[f"{__name__}.academic_affairs_attendance_service"] = academic_affairs_attendance_service
# 考务结束、异常闭环和归档统一执行同一门禁。
sys.modules[f"{__name__}.academic_affairs_exam_service"] = academic_affairs_exam_service
# 成绩有效口径和录入名单统一经叠加facade，完整路径导入不得绕回行政班旧逻辑。
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
# 补考/清考候选统一消费有效成绩口径。
sys.modules[f"{__name__}.academic_affairs_makeup_service"] = academic_affairs_makeup_service
# 学生课表等完整路径导入统一使用“同一发布批次内合并LOCKED选课”的安全读侧。
sys.modules[f"{__name__}.academic_affairs_schedule_service"] = academic_affairs_schedule_service
# 选课锁定前必须形成可复核的正式教学任务名单。
sys.modules[f"{__name__}.academic_affairs_selection_service"] = academic_affairs_selection_service
# 教学任务生成运行时完整路径导入统计范围函数；统一切到空范围fail-closed版本。
sys.modules[f"{__name__}.academic_affairs_stats_service"] = academic_affairs_stats_service
# 其它服务可能完整路径导入教学任务；统一切到读取学期/校历教学周的 facade。
sys.modules[f"{__name__}.academic_affairs_task_service"] = academic_affairs_task_service
# 移动聚合路由和后续完整路径导入统一去掉教师姓名授权。
sys.modules[f"{__name__}.mobile_academic_affairs_service"] = mobile_academic_affairs_service
