"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

from . import academic_affairs_archive_facade as academic_affairs_archive_service
from . import academic_affairs_attendance_facade as academic_affairs_attendance_service
from . import academic_affairs_evaluation_facade as academic_affairs_evaluation_service
from . import academic_affairs_grade_facade as academic_affairs_grade_service
from . import academic_affairs_schedule_facade as academic_affairs_schedule_service
from . import academic_affairs_stats_facade as academic_affairs_stats_service
from . import academic_affairs_task_facade as academic_affairs_task_service
from . import mobile_academic_affairs_facade as mobile_academic_affairs_service

# 普通教师创建考勤必须选择当前学期本人教学任务。
sys.modules[f"{__name__}.academic_affairs_attendance_service"] = academic_affairs_attendance_service
# 毕业审核等旧服务使用完整子模块路径导入 effective_grade_rows；在包初始化完成后将该公开路径
# 指向兼容 facade，使所有读侧统一停止“按课程名取最高分”。facade 内仍保留 legacy 模块引用。
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
# 学生课表等完整路径导入统一使用“同一发布批次内合并LOCKED选课”的安全读侧。
sys.modules[f"{__name__}.academic_affairs_schedule_service"] = academic_affairs_schedule_service
# 教学任务生成运行时完整路径导入统计范围函数；统一切到空范围fail-closed版本。
sys.modules[f"{__name__}.academic_affairs_stats_service"] = academic_affairs_stats_service
# 其它服务可能完整路径导入教学任务；统一切到读取学期/校历教学周的 facade。
sys.modules[f"{__name__}.academic_affairs_task_service"] = academic_affairs_task_service
# 移动聚合路由和后续完整路径导入统一去掉教师姓名授权。
sys.modules[f"{__name__}.mobile_academic_affairs_service"] = mobile_academic_affairs_service
