"""系统管理中心 P0/P1 真实后端回归：登录/操作日志分流、账号停用启用/重置密码、
角色改名/停用、组织节点停用。直接调 API 端点函数（传 user dict 绕过 HTTP/Depends），
在 db_mode 真库上种最小数据后断言真实持久化与守卫。权限门禁另由 test_permissions* 覆盖。"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException

TID = 1000000000000000001
ADMIN = {"userId": "db-1", "realName": "测试管理员", "currentRoleCode": "SCHOOL_ADMIN",
         "tenantId": str(TID), "userType": "ADMIN"}


@pytest.fixture()
def seeded(db_mode):
    """在干净真库里种：1 管理员账号(id=1) + 1 目标教师账号(id=2) + 1 自定义角色 + 学院/班级/学生 + 审计若干。"""
    from app.services.db_service import session
    from app.core.security import hash_password
    from app.models import (College, Role, SchoolClass, SecurityAuditLog, StudentProfile, User, UserRole)
    set_tenant({"tenantId": TID})
    set_current_user(ADMIN)
    with session() as db:
        db.add(User(id=1, tenant_id=TID, login_name="admin01", real_name="测试管理员",
                    password_hash=hash_password("Init@123"), user_type="ADMIN", status="ACTIVE"))
        db.add(User(id=2, tenant_id=TID, login_name="t2020019", real_name="李敏",
                    password_hash=hash_password("Init@123"), user_type="TEACHER", status="ACTIVE"))
        role = Role(id=90, tenant_id=TID, role_code="CUSTOM_AAA", role_name="自定义辅导员",
                    role_type="CUSTOM", status="ACTIVE", remark="SAAS_CUSTOM;scope=COLLEGE;permMode=DB")
        role_sys = Role(id=91, tenant_id=TID, role_code="SCHOOL_ADMIN", role_name="学校管理员",
                        role_type="SYSTEM", status="ACTIVE", remark="")
        db.add(role); db.add(role_sys)
        college = College(id=10, tenant_id=TID, college_name="信息工程学院", status="ACTIVE")
        db.add(college)
        cls_empty = SchoolClass(id=20, tenant_id=TID, major_id=1, class_name="软件2301", status="ACTIVE")
        cls_full = SchoolClass(id=21, tenant_id=TID, major_id=1, class_name="软件2302", status="ACTIVE")
        db.add(cls_empty); db.add(cls_full)
        db.add(StudentProfile(id=500, tenant_id=TID, student_no="S001", real_name="学生甲",
                              class_id=21, college_id=10, current_stage="ENROLLED"))
        # 审计：2 条登录（含中文动作）+ 1 条登录失败 + 2 条业务操作
        for a, res, name in [("登录", "SUCCESS", "李敏"), ("登录", "SUCCESS", "测试管理员"),
                             ("LOGIN_FAIL", "FAIL", "未知")]:
            db.add(SecurityAuditLog(tenant_id=TID, action=a, operator_name=name, result=res,
                                    resource="auth", ip="10.1.2.3", created_at=datetime.utcnow()))
        for a in ("ROLE_PERMISSION_CONFIG", "EXPORT"):
            db.add(SecurityAuditLog(tenant_id=TID, action=a, operator_name="测试管理员", result="SUCCESS",
                                    resource=f"res:{a}", ip="10.1.2.3", created_at=datetime.utcnow()))
        db.commit()
    set_tenant({"tenantId": TID})
    set_current_user(ADMIN)
    yield


def test_login_operation_log_split(seeded):
    from app.api.v1 import system
    login = system.list_login_logs(user=ADMIN)["data"]
    op = system.list_operation_logs(user=ADMIN)["data"]
    login_actions_present = login["total"]
    # 登录日志含 3 条（2 登录 + 1 LOGIN_FAIL），不含业务操作
    assert login_actions_present == 3, login
    assert op["total"] == 2, op
    # 登录日志字段契约
    row = login["list"][0]
    for key in ("userName", "userNo", "roleName", "time", "result", "resultLabel", "ip", "device"):
        assert key in row
    # 登录失败被正确标记
    results = {r["result"] for r in login["list"]}
    assert "FAILED" in results and "SUCCESS" in results
    # 操作日志不含任何登录动作
    assert all(r["action"] not in ("登录", "LOGIN_FAIL") for r in op["list"])


def test_disable_enable_account(seeded):
    from app.api.v1 import system
    from app.services.db_service import session
    from app.models import User
    # 停用原因不足 5 字 → 拒绝
    with pytest.raises(AppException):
        system.set_system_user_status(2, {"action": "DISABLE", "reason": "离职"}, user=ADMIN)
    # 不能停用本人（admin db-1 → user_id 1）
    with pytest.raises(AppException):
        system.set_system_user_status(1, {"action": "DISABLE", "reason": "测试自我停用"}, user=ADMIN)
    # 正常停用
    res = system.set_system_user_status(2, {"action": "DISABLE", "reason": "离职交接完成"}, user=ADMIN)["data"]
    assert res["status"] == "DISABLED"
    with session() as db:
        assert db.get(User, 2).status == "DISABLED"
    # 启用
    res2 = system.set_system_user_status(2, {"action": "ENABLE"}, user=ADMIN)["data"]
    assert res2["status"] == "ACTIVE"
    with session() as db:
        assert db.get(User, 2).status == "ACTIVE"


def test_reset_password(seeded):
    from app.api.v1 import system
    from app.services.db_service import session
    from app.core.security import verify_password
    from app.models import User
    with session() as db:
        old_hash = db.get(User, 2).password_hash
    res = system.reset_system_user_password(2, user=ADMIN)["data"]
    assert res["tempPassword"] and res["mustChangePassword"] is True
    with session() as db:
        u = db.get(User, 2)
        assert u.password_hash != old_hash
        assert u.must_change_password is True
        assert verify_password(res["tempPassword"], u.password_hash)  # 临时密码可登录


def test_role_rename_and_disable(seeded):
    from app.api.v1 import system
    from app.services.db_service import session
    from app.models import Role, UserRole
    # 预设角色不可改名
    with pytest.raises(AppException):
        system.update_system_role(91, {"name": "改预设"}, user=ADMIN)
    # 自定义角色改名
    system.update_system_role(90, {"name": "自定义辅导员改"}, user=ADMIN)
    with session() as db:
        assert db.get(Role, 90).role_name == "自定义辅导员改"
    # 有成员时不可停用
    with session() as db:
        db.add(UserRole(tenant_id=TID, user_id=2, role_id=90, status="ACTIVE")); db.commit()
    with pytest.raises(AppException):
        system.set_system_role_status(90, {"action": "DISABLE", "reason": "不再使用该角色"}, user=ADMIN)
    # 改派掉成员后可停用
    with session() as db:
        link = db.query(UserRole).filter_by(role_id=90).first()
        link.status = "DISABLED"; link.is_deleted = True; db.commit()
    res = system.set_system_role_status(90, {"action": "DISABLE", "reason": "不再使用该角色"}, user=ADMIN)["data"]
    assert res["status"] == "DISABLED"


def test_org_node_disable_guards(seeded):
    from app.api.v1 import system
    from app.services.db_service import session
    from app.models import SchoolClass
    # 有在籍学生的班级不可停用
    with pytest.raises(AppException):
        system.set_system_org_node_status(21, {"type": "CLASS", "action": "DISABLE",
                                               "reason": "撤销该班级建制"}, user=ADMIN)
    # 空班级可停用
    res = system.set_system_org_node_status(20, {"type": "CLASS", "action": "DISABLE",
                                                 "reason": "撤销该班级建制"}, user=ADMIN)["data"]
    assert res["status"] == "DISABLED"
    with session() as db:
        assert db.get(SchoolClass, 20).status == "DISABLED"


def test_system_config_effective(seeded):
    """系统配置真实生效：保存后强制层 get_int 读到新值；越界拒绝。"""
    from app.api.v1 import system
    from app.services import system_config_service as cfg
    assert cfg.get_int("SEC_LOCK_MAX_FAIL", 5) == 5  # 默认
    system.save_system_config("SEC_LOCK_MAX_FAIL", {"valueText": "7", "reason": "收紧登录策略"}, user=ADMIN)
    assert cfg.get_int("SEC_LOCK_MAX_FAIL", 5) == 7  # 登录失败锁定逻辑真实读取此值
    with pytest.raises(AppException):  # 越界拒绝
        system.save_system_config("SEC_LOCK_MAX_FAIL", {"valueText": "99", "reason": "非法"}, user=ADMIN)
    with pytest.raises(AppException):  # 未知键拒绝
        system.save_system_config("UNKNOWN_KEY", {"valueText": "1", "reason": "x"}, user=ADMIN)
    items = system.list_system_configs(user=ADMIN)["data"]["list"]
    assert any(i["key"] == "SEC_LOCK_MAX_FAIL" and i["valueText"] == "7" for i in items)


def test_brand_edit_takes_effect(seeded):
    """品牌真实生效：保存后 get_brand（顶栏/登录页读取）反映新主色。"""
    from app.api.v1 import system
    from app.services import mock_tenant_service
    system.save_system_brand({"brandColor": "#FF6600", "watermarkText": "测试水印",
                              "loginSlogan": "知行合一", "reason": "品牌统一"}, user=ADMIN)
    form = system.get_system_brand(user=ADMIN)["data"]
    assert form["brandColor"] == "#FF6600" and form["watermarkText"] == "测试水印"
    brand = mock_tenant_service.get_brand()  # 顶栏/登录页真实数据源
    assert brand.get("primaryColor") == "#FF6600"
    # 非法主色拒绝
    with pytest.raises(AppException):
        system.save_system_brand({"brandColor": "红色"}, user=ADMIN)


def test_scope_rule_catalog(seeded):
    """数据范围规则真实可编辑目录：引用角色/影响用户由后端按角色 scopeCode 真实计算；被引用不可作废。"""
    from app.api.v1 import system
    # 种子里 role id=90 remark 含 ;scope=COLLEGE → COLLEGE 规则应显示被该角色引用
    rule = system.save_scope_rule({"name": "本学院范围", "scopeCode": "COLLEGE", "remark": "跨院不可见"}, user=ADMIN)["data"]
    assert rule["scopeLabel"] == "本学院"
    assert "自定义辅导员" in rule["appliedRoles"]  # 真实引用角色
    # 被角色引用时不可作废
    with pytest.raises(AppException):
        system.set_scope_rule_status(int(rule["id"]), {"action": "DISABLE", "reason": "不再使用该范围"}, user=ADMIN)
