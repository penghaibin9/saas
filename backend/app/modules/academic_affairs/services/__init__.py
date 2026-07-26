"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""
from __future__ import annotations

import sys

from . import academic_affairs_archive_facade as academic_affairs_archive_service
from . import academic_affairs_evaluation_facade as academic_affairs_evaluation_service
from . import academic_affairs_grade_facade as academic_affairs_grade_service

# 毕业审核等旧服务使用完整子模块路径导入 effective_grade_rows；在包初始化完成后将该公开路径
# 指向兼容 facade，使所有读侧统一停止“按课程名取最高分”。facade 内仍保留 legacy 模块引用。
sys.modules[f"{__name__}.academic_affairs_grade_service"] = academic_affairs_grade_service
