"""系统管理中心可编辑配置的真实落库（2026-07-22，经用户明确授权扩展冻结册）。

冻结册原设计"菜单由 RBAC 推导、不建 t_menu 表；数据范围由 resolver 推导"，
本批次经产品负责人明确决策改为「真实可编辑」：
- t_sys_config       系统配置键值（安全策略等，真实被强制层读取，如登录失败锁定阈值）
- t_data_scope_rule  自定义数据范围规则（按角色覆盖默认范围，resolver 优先读取）
- t_menu_node        菜单节点（从 navPlan 基线派生后可改名/排序/停用，前端导航优先读取）

三表均带 tenant_id 行级隔离 + CommonMixin(逻辑删除/乐观锁/操作留痕)。缺省缺表/空数据时
上层一律回落到原基线行为（硬编码默认/ navPlan / role 默认范围），保证平滑上线不破坏既有链路。
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SysConfig(PKMixin, TenantMixin, CommonMixin, Base):
    """t_sys_config 系统配置键值（学校侧可编辑，被真实强制层读取）。"""
    __tablename__ = "t_sys_config"
    __table_args__ = (UniqueConstraint("tenant_id", "config_key", name="uk_sysconfig_tenant_key"),)

    config_key: Mapped[str] = mapped_column(String(100), nullable=False, comment="配置键，如 SEC_LOCK_MAX_FAIL")
    config_group: Mapped[str | None] = mapped_column(String(50), comment="分组：安全策略/会话/通用等")
    config_name: Mapped[str | None] = mapped_column(String(100), comment="展示名")
    value_text: Mapped[str | None] = mapped_column(String(500), comment="配置值（文本，强制层按键解析）")
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(500))


class DataScopeRule(PKMixin, TenantMixin, CommonMixin, Base):
    """t_data_scope_rule 自定义数据范围规则：按角色覆盖默认范围。resolver 优先读取本表。"""
    __tablename__ = "t_data_scope_rule"

    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_code: Mapped[str | None] = mapped_column(String(50), index=True, comment="作用的角色编码；空=全局候选")
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                            comment="SELF/CLASS/COLLEGE/MAJOR/SCHOOL/CUSTOM…")
    target_json: Mapped[dict | None] = mapped_column(JSON, comment="CUSTOM 时的目标：{collegeIds,majorIds,classIds}")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", comment="ACTIVE/DISABLED")
    remark: Mapped[str | None] = mapped_column(String(500))


class MenuNode(PKMixin, TenantMixin, CommonMixin, Base):
    """t_menu_node 菜单节点：从 navPlan 基线派生，学校侧可改名/排序/停用。前端导航优先读取。"""
    __tablename__ = "t_menu_node"
    __table_args__ = (UniqueConstraint("tenant_id", "menu_code", name="uk_menu_tenant_code"),)

    menu_code: Mapped[str] = mapped_column(String(100), nullable=False, comment="菜单唯一码（对齐 navPlan leafKey）")
    parent_code: Mapped[str | None] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, comment="学校可改的展示名")
    path: Mapped[str | None] = mapped_column(String(200))
    icon: Mapped[str | None] = mapped_column(String(50))
    module_code: Mapped[str | None] = mapped_column(String(50))
    permission_key: Mapped[str | None] = mapped_column(String(100), comment="进入该菜单所需权限码")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", comment="ACTIVE/DISABLED")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="平台基线菜单 vs 学校新增")
