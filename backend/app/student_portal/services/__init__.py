"""学生 PC 门户 · 服务层。

仅将教务服务公开入口切到独立安全门面；毕设、实习、学工等服务仍由原模块加载。
"""

from . import academic_evaluation_safety_facade as academic_service

__all__ = ["academic_service"]
