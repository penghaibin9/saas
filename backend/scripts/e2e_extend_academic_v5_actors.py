"""为既有 V5 gold cohort 追加真实可登录的业务角色身份；默认只读预览。"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import secrets
import sys

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
import e2e_seed_academic_v5_journey as base

RUN_ID = "v5gold01"
PREFIX = base.require_run_id(RUN_ID)
STATE_PATH = REPOSITORY / ".codex-temp" / "e2e-v5" / f"{RUN_ID}-state.json"
ACTOR_RECEIPT_PATH = REPOSITORY / ".codex-temp" / "e2e-v5" / f"{RUN_ID}-actors-private.json"
ACTORS = {
    "affairsAdmin": ("学工管理员", "STUDENT_AFFAIRS_ADMIN", None, "学工管理员"),
    "internMentorA": ("甲学院实习导师", "INTERN_MENTOR", "A", "实习指导教师"),
    "internMentorB": ("乙学院实习导师", "INTERN_MENTOR", "B", "实习指导教师"),
    "gdMentorA": ("甲学院毕设导师", "GD_MENTOR", "A", "毕设指导教师"),
    "gdMentorB": ("乙学院毕设导师", "GD_MENTOR", "B", "毕设指导教师"),
    "gdReviewerA": ("甲学院独立评阅教师", "GD_REVIEWER", "A", "毕设评阅教师"),
}


def preflight(db):
    from sqlalchemy import select, text
    from app.models import College, Permission, Role, RolePermission, Tenant, User, UserRole
    from app.services import system_role_shadow_service as shadow

    if db.scalar(text("SELECT DATABASE()")) != base.DATABASE_NAME:
        raise base.PreparationError("数据库会话实际目标与允许目标不符")
    heads = base._schema_check(db)
    tenant = db.get(Tenant, base.TENANT_ID)
    if tenant is None or tenant.is_deleted or tenant.tenant_code != base.TENANT_CODE or str(tenant.status).upper() != "ACTIVE":
        raise base.PreparationError("既有 demo 租户未正常启用")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if (state.get("tenantCode") != base.TENANT_CODE or str(state.get("tenantId")) != str(base.TENANT_ID)
            or state.get("prefix") != PREFIX or set(state.get("accounts", {})) != set(base.IDENTITIES)
            or not state.get("colleges")):
        raise base.PreparationError("既有 V5 gold 回执的租户、前缀或原账号集合不匹配")
    expected_keys = {"A", "B"}
    if set(state["colleges"]) != expected_keys:
        raise base.PreparationError("既有 V5 gold 学院回执不完整")
    colleges = {}
    for label in sorted(expected_keys):
        college_id = int(state["colleges"][label]["collegeId"])
        college = db.get(College, college_id)
        if (college is None or college.tenant_id != base.TENANT_ID or college.is_deleted
                or college.code != PREFIX + label):
            raise base.PreparationError("V5 gold 学院编号与隔离库记录不匹配")
        colleges[label] = college
    for key, account in state["accounts"].items():
        user = db.get(User, int(account["userId"]))
        expected_role = (PREFIX.upper() + "READER" if key == "leader" else base.IDENTITIES[key][1])
        role = db.get(Role, int(account["roleId"]))
        if (user is None or user.tenant_id != base.TENANT_ID or user.is_deleted
                or user.login_name != account["loginName"] or account.get("roleCode") != expected_role
                or role is None or role.tenant_id != base.TENANT_ID or role.role_code != expected_role
                or db.scalar(select(UserRole.id).where(UserRole.tenant_id == base.TENANT_ID,
                    UserRole.user_id == user.id, UserRole.role_id == int(account["roleId"]),
                    UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))) is None):
            raise base.PreparationError("既有 V5 gold 账号与隔离库记录不匹配")

    permissions, templates, roles = {}, {}, {}
    for code in sorted({actor[1] for actor in ACTORS.values()}):
        codes = set(shadow.published_system_role_permissions(db, code))
        if not codes or any("*" in permission for permission in codes):
            raise base.PreparationError("已发布角色模板无权限或含通配权限：" + code)
        rows = dict(db.execute(select(Permission.permission_code, Permission.id)
                               .where(Permission.permission_code.in_(codes))).all())
        if set(rows) != codes:
            raise base.PreparationError("已发布模板权限未全部落入权限目录：" + code)
        template = shadow._latest_published_template(db, code)
        templates[code] = {"id": str(template.id), "version": template.template_version,
                           "permissionCount": len(codes), "permissionDigest": template.permission_digest}
        roles[code] = db.scalar(select(Role).where(Role.tenant_id == base.TENANT_ID, Role.role_code == code))
        role = roles[code]
        if role is not None and (role.is_deleted or role.status != "ACTIVE" or role.role_type != "SYSTEM"):
            raise base.PreparationError("租户角色不可安全复用：" + code)
        if role is not None:
            existing = set(db.scalars(select(RolePermission.permission_id).where(
                RolePermission.tenant_id == base.TENANT_ID, RolePermission.role_id == role.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))))
            if existing != set(rows.values()):
                raise base.PreparationError("既有租户角色权限与已发布模板不一致：" + code)
        permissions[code] = rows

    logins = {PREFIX + key.lower() for key in ACTORS}
    if db.scalar(select(User.id).where(User.tenant_id == base.TENANT_ID,
                                       User.login_name.in_(logins)).limit(1)) is not None:
        raise base.PreparationError("追加身份已存在；不覆盖或接管现有账号")
    return {"heads": heads, "state": state, "colleges": colleges, "permissions": permissions,
            "templates": templates, "roles": roles}


def prepare(db, plan):
    from app.core.security import hash_password
    from app.models import Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole

    now = datetime.utcnow()
    note = "V5 gold 隔离测试追加身份；" + PREFIX
    roles = plan["roles"]
    for code in plan["templates"]:
        if roles[code] is None:
            role = Role(tenant_id=base.TENANT_ID, role_code=code,
                        role_name={"STUDENT_AFFAIRS_ADMIN": "学工处管理员", "INTERN_MENTOR": "实习指导教师",
                                   "GD_MENTOR": "毕设指导教师", "GD_REVIEWER": "毕设评阅教师"}[code],
                        role_type="SYSTEM", status="ACTIVE", remark=note)
            db.add(role); db.flush()
            db.add_all([RolePermission(tenant_id=base.TENANT_ID, role_id=role.id,
                permission_id=permission_id, status="ACTIVE")
                for permission_id in plan["permissionIds"][code]])
            roles[code] = role

    accounts, credentials = {}, {}
    for key, (title, code, label, assignment_type) in ACTORS.items():
        login = PREFIX + key.lower()
        password = "Aa9!" + secrets.token_urlsafe(24)
        user = User(tenant_id=base.TENANT_ID, login_name=login, real_name="V5 " + title,
                    password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE",
                    must_change_password=False)
        db.add(user); db.flush()
        link = UserRole(tenant_id=base.TENANT_ID, user_id=user.id, role_id=roles[code].id, status="ACTIVE")
        db.add(link); db.flush()
        college_id = 0 if label is None else int(plan["state"]["colleges"][label]["collegeId"])
        if label is None:
            db.add(RoleAssignmentScope(tenant_id=base.TENANT_ID, user_id=user.id, user_role_id=link.id,
                role_code=code, scope_type="SCHOOL", scope_id=0,
                scope_name_snapshot="全校", source_type="MANUAL", status="ACTIVE",
                effective_at=now - timedelta(minutes=1), reason=note))
        db.add(StaffAssignment(tenant_id=base.TENANT_ID, user_id=user.id,
            org_type="SCHOOL" if label is None else "COLLEGE",
            org_node_id=base.TENANT_ID if label is None else college_id,
            assignment_type=assignment_type, is_primary=True, source_type="MANUAL", source_id=PREFIX,
            effective_at=now - timedelta(minutes=1), status="ACTIVE", reason=note))
        accounts[key] = {"loginName": login, "userId": str(user.id), "roleCode": code,
                         "roleId": str(roles[code].id), "contextId": f"role:{roles[code].id}"}
        credentials[login] = {"password": password}

    actor_state = {"tenantCode": base.TENANT_CODE, "tenantId": str(base.TENANT_ID), "prefix": PREFIX,
                   "baseStatePath": str(STATE_PATH.relative_to(REPOSITORY)), "accounts": accounts,
                   "sourceTemplates": plan["templates"], "createdAt": now.isoformat() + "Z",
                   "note": "仅追加可登录身份、角色范围与教职任职；未创建业务关系或业务终态。"}
    # Keep the only password receipt before commit: an uncertain commit must not orphan usable accounts.
    base._write_private_json(ACTOR_RECEIPT_PATH, {"state": actor_state, "credentials": credentials})
    db.commit()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="显式新增 V5 gold 测试身份；默认只读预览")
    args = parser.parse_args(argv)
    raw = base.require_target(os.environ)
    if not STATE_PATH.is_file() or STATE_PATH.resolve() != STATE_PATH.absolute():
        raise base.PreparationError("既有 V5 gold 状态回执不存在或路径异常")
    if ACTOR_RECEIPT_PATH.exists():
        raise base.PreparationError("追加身份回执已存在；不覆盖")
    base.output_path(str(ACTOR_RECEIPT_PATH), ACTOR_RECEIPT_PATH)

    from app.core.config import settings
    if settings.effective_database_url != raw or not settings.DB_ENABLED or settings.APP_ENV != "test":
        raise base.PreparationError("实际应用配置与显式隔离目标不一致")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool
    engine = create_engine(raw, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            if not args.execute:
                connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
                connection.commit()
            with Session(bind=connection) as db:
                plan = preflight(db)
                plan["permissionIds"] = {code: list(rows.values())
                                          for code, rows in plan["permissions"].items()}
                if args.execute:
                    prepare(db, plan)
                else:
                    db.rollback()
        print(json.dumps({"executed": args.execute, "actorCount": len(ACTORS),
                          "roles": sorted(plan["templates"]),
                          "privateReceiptPath": str(ACTOR_RECEIPT_PATH)}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except base.PreparationError as error:
        print("拒绝准备：" + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:
        print("准备失败（" + type(error).__name__ + "）；核验前置回执，不自动重试或覆盖。", file=sys.stderr)
        raise SystemExit(1) from None
