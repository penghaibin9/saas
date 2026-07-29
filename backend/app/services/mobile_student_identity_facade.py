"""教务兼容导入：统一复用 latest main 的学生身份解析，不再维护第二套实现。"""

from app.services.mobile_student_service import resolve_student

__all__ = ["resolve_student"]
