"""学生 PC 门户 · 服务层。

教务增量通过独立门面接入；毕设、实习、学工等服务仍由原模块加载。
"""

from . import academic_evaluation_safety_facade as academic_service
from . import academic_home_todo_facade as home_service

__all__ = ["academic_service", "home_service"]
