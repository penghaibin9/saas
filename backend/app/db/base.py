"""聚合全部 ORM 模型的 metadata（Alembic autogenerate 入口）。"""
from __future__ import annotations

from app.models.base import Base  # noqa: F401

# 显式导入所有模型模块，确保注册进 Base.metadata
from app.models import tenant as _tenant  # noqa: F401
from app.models import org as _org  # noqa: F401
from app.models import rbac as _rbac  # noqa: F401
from app.models import student as _student  # noqa: F401
from app.models import approval as _approval  # noqa: F401
from app.models import audit as _audit  # noqa: F401
from app.models import file as _file  # noqa: F401
from app.models import platform as _platform  # noqa: F401
from app.models import message as _message  # noqa: F401

metadata = Base.metadata
