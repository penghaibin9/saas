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
from app.models import portal_sign as _portal_sign  # noqa: F401  (学生PC门户·电子签署留痕)
from app.models import approval as _approval  # noqa: F401
from app.models import audit as _audit  # noqa: F401
from app.models import file as _file  # noqa: F401
from app.models import platform as _platform  # noqa: F401
from app.models import internship as _internship  # noqa: F401
from app.models import orientation as _orientation  # noqa: F401
from app.models import campus_service as _campus_service  # noqa: F401
from app.models import academic as _academic  # noqa: F401
from app.models import graduation as _graduation  # noqa: F401
from app.models import graduation_extension as _graduation_extension  # noqa: F401
from app.models import employment as _employment  # noqa: F401
from app.models import message as _message  # noqa: F401
from app.models import portal as _portal  # noqa: F401
from app.models import teacher_scope as _teacher_scope  # noqa: F401
from app.models import affairs as _affairs  # noqa: F401
from app.models import excel_import_job as _excel_import_job  # noqa: F401
from app.models import internship_agreement_template as _internship_agreement_template  # noqa: F401
from app.models import service_catalog as _service_catalog  # noqa: F401  (PLAT-08·服务目录)
from app.models import tenant_provisioning as _tenant_provisioning  # noqa: F401  (PLAT-04·租户开通)
from app.models import incident as _incident  # noqa: F401  (PLAT-09·事件)
from app.models import change_management as _change_management  # noqa: F401  (PLAT-11·变更管理)
from app.models import customer_success as _customer_success  # noqa: F401  (PLAT-05·客户健康)
from app.models import problem_management as _problem_management  # noqa: F401  (PLAT-10·问题管理)
from app.models import tenant_metering as _tenant_metering  # noqa: F401  (PLAT-13·租户用量与公平使用)
from app.models import disaster_recovery as _disaster_recovery  # noqa: F401  (PLAT-12·备份恢复灾备)

metadata = Base.metadata
