"""聚合全部 ORM 模型的 metadata（Alembic autogenerate 入口）。"""
from __future__ import annotations

from app.models.base import Base  # noqa: F401

# 显式导入所有模型模块，确保注册进 Base.metadata
from app.models import tenant as _tenant  # noqa: F401
from app.models import org as _org  # noqa: F401
from app.models import rbac as _rbac  # noqa: F401
from app.models import student as _student  # noqa: F401
from app.models import student_parent as _student_parent  # noqa: F401  (学生PC门户·家长授权代理)
from app.models import portal_otp as _portal_otp  # noqa: F401  (学生PC门户·登录验证码)
from app.models import approval as _approval  # noqa: F401
from app.models import audit as _audit  # noqa: F401
from app.models import file as _file  # noqa: F401
from app.models import platform as _platform  # noqa: F401
from app.models import internship as _internship  # noqa: F401
from app.models import orientation as _orientation  # noqa: F401
from app.models import campus_service as _campus_service  # noqa: F401
from app.models import academic as _academic  # noqa: F401
from app.models import graduation as _graduation  # noqa: F401
from app.models import employment as _employment  # noqa: F401
from app.models import message as _message  # noqa: F401
from app.models import portal as _portal  # noqa: F401
from app.models import teacher_scope as _teacher_scope  # noqa: F401
from app.models import affairs as _affairs  # noqa: F401
from app.models import excel_import_job as _excel_import_job  # noqa: F401
from app.models import internship_agreement_template as _internship_agreement_template  # noqa: F401

metadata = Base.metadata
