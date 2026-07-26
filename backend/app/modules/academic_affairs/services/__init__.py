"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

# 必须先加载官方名单最终策略，再导入考勤/考务/成绩/选课消费者；否则 from-import 会缓存旧函数对象。
from . import academic_affairs_teaching_roster_policy as academic_affairs_teaching_roster_policy
# 最终归档链：旧9域 + 选课 + 补考重修免修 + 评教 + 教材，共13域。
from . import academic_affairs_archive_textbook_facade as academic_affairs_archive_service
from . import academic_affairs_attendance_facade as academic_affairs_attendance_service
from . import academic_affairs_evaluation_term_facade as academic_affairs_evaluation_service
from . import academic_affairs_exam_term_facade as academic_affairs_exam_service
from . import academic_affairs_grade_term_facade as academic_affairs_grade_service
from . import academic_affairs_makeup_term_facade as academic_affairs_makeup_service
from . import academic_affairs_schedule_facade as academic_affairs_schedule_service
from . import academic_affairs_selection_facade as academic_affairs_selection_service
from . import academic_affairs_selection_round_facade as academic_affairs_selection_round_service
from . import academic_affairs_stats_facade as academic_affairs_stats_service
from . import academic_affairs_task_security_facade as academic_affairs_task_service
from . import academic_affairs_textbook_lock_facade as academic_affairs_textbook_service
from . import mobile_academic_affairs_facade as mobile_academic_affairs_service

# 归档路由和业务模块统一进入最终13域叠加策略层。
sys.modules[f"{__name__}.academic_affairs_archive_service"] = academic_affairs_archive_service
# 普通教师创建考勤必须选择当前学期本人教学任务。
sys.modules[f"{__name__}.academic_affairs_attendance_service"] = academic_affairs_attendance_service
# 评教批次、窗口、匿名提交、结果和申诉统一执行所属学期写保护。
sys.modules[f"{__name__}.academic_affairs_evaluation_service"] = academic_affairs_evaluation_service
# 考务新建、名单、异常、结束与归档全部进入最终叠加facade。
sys.modules[f"{__name__}.academic_affairs_exam_service"] = academic_affairs_exam_service
# 成绩有效口径、官方名单与学期写保护统一经最终叠加facade。
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
# 补考、清考、重修和免修统一消费有效成绩口径并执行学期写保护。
sys.modules[f"{__name__}.academic_affairs_makeup_service"] = academic_affairs_makeup_service
# 学生课表等完整路径导入统一使用“同一发布批次内合并LOCKED选课”的安全读侧。
sys.modules[f"{__name__}.academic_affairs_schedule_service"] = academic_affairs_schedule_service
# 选课锁定前必须形成可复核的正式教学任务名单。
sys.modules[f"{__name__}.academic_affairs_selection_service"] = academic_affairs_selection_service
# 选课轮次新建、开关轮和摇号全部执行所属学期写保护。
sys.modules[f"{__name__}.academic_affairs_selection_round_service"] = academic_affairs_selection_round_service
# 教学任务生成运行时完整路径导入统计范围函数；统一切到空范围fail-closed版本。
sys.modules[f"{__name__}.academic_affairs_stats_service"] = academic_affairs_stats_service
# 教学任务批次、明细、确认链和管理数据范围统一进入最终安全工作台facade。
sys.modules[f"{__name__}.academic_affairs_task_service"] = academic_affairs_task_service
# 教材选用、审核、征订、发放、退领、费用和并发锁统一进入最终层；目录/库存主数据保持跨学期可维护。
sys.modules[f"{__name__}.academic_affairs_textbook_service"] = academic_affairs_textbook_service
# 移动聚合路由和后续完整路径导入统一去掉教师姓名授权。
sys.modules[f"{__name__}.mobile_academic_affairs_service"] = mobile_academic_affairs_service
