"""准备保留办理记录的 V5 虚构身份；默认只读预览，绝不清库或迁移。

从 backend 目录执行，先显式提供隔离库 DATABASE_URL、DB_ENABLED=true、
APP_ENV=test、DEPLOYMENT_MODE=local、E2E_ALLOW_DESTRUCTIVE_TESTS=true。
预览：python scripts/e2e_seed_academic_v5_journey.py --run-id <6至12位小写字母数字>
执行：同一命令追加 --execute；--state / --credentials 可指定仓库内已忽略的新文件。
目标固定为本轮专用本机 3311/student_lifecycle_v5_e2e，不使用现有清理型测试库。
两个输出禁止覆盖；再次执行相同前缀拒绝。
后端正常密码登录也必须显式使用该 DATABASE_URL，TEST_DATABASE_URL 不能替代它。
脚本不登录、不生成令牌；正常页面登录与后续业务办理仍须分别验收。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
TENANT_ID = 1000000000000000001
TENANT_CODE = "demo"
DATABASE_NAME = "student_lifecycle_v5_e2e"
ENTRY_YEAR = 2023
GRADUATE_YEAR = 2026
IDENTITIES = {
    "school": ("校教务处测试员", "ACADEMIC_ADMIN", None),
    "schoolReviewer": ("校教务处独立复核员", "ACADEMIC_ADMIN", None),
    "collegeA": ("甲学院教学秘书", "COLLEGE_ADMIN", "A"),
    "collegeB": ("乙学院教学秘书", "COLLEGE_ADMIN", "B"),
    "teacherA": ("甲学院任课教师", "ACADEMIC_TEACHER", "A"),
    "teacherB": ("乙学院任课教师", "ACADEMIC_TEACHER", "B"),
    "leader": ("学校只读观察员", "LEADER", None),
}


class PreparationError(RuntimeError):
    """只包含可安全展示的信息，不携带连接串、口令或驱动异常。"""


def require_target(environment):
    from sqlalchemy.engine import make_url

    if environment.get("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise PreparationError("必须显式允许独立测试数据准备")
    if environment.get("APP_ENV") != "test" or environment.get("DEPLOYMENT_MODE") != "local":
        raise PreparationError("仅允许 APP_ENV=test 且 DEPLOYMENT_MODE=local")
    if any(environment.get(key, "test").lower() not in {"test", "testing"} for key in ("ENV", "ENVIRONMENT")):
        raise PreparationError("旧环境变量与测试环境不一致")
    if str(environment.get("DB_ENABLED", "")).lower() != "true":
        raise PreparationError("必须显式启用数据库")
    raw = environment.get("DATABASE_URL", "")
    try:
        url = make_url(raw)
    except Exception:
        raise PreparationError("必须显式提供合法的隔离数据库地址") from None
    if (url.drivername not in {"mysql", "mysql+pymysql"}
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or url.port != 3311 or url.database != DATABASE_NAME):
        raise PreparationError("仅允许本机 3311 的精确 student_lifecycle_v5_e2e 库")
    # 不允许连接参数把本机 TCP 目标替换成套接字、配置文件或执行初始化 SQL。
    if set(url.query) - {"charset"}:
        raise PreparationError("数据库地址仅允许 charset 查询参数")
    return raw


def require_run_id(run_id):
    if not re.fullmatch(r"[a-z0-9]{6,12}", run_id):
        raise PreparationError("run-id 仅允许 6 至 12 位小写字母或数字")
    return "v5j_" + run_id + "_"


def output_path(value, default):
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = REPOSITORY / path
    # 防止已忽略目录的符号链接/连接点把凭据送到仓库外。
    original = path.absolute()
    path = path.resolve()
    if original != path or not path.is_relative_to(REPOSITORY.resolve()):
        raise PreparationError("输出必须位于本仓库真实本机目录，不能经链接或路径跳转")
    if path.exists() or path.suffix.lower() != ".json":
        raise PreparationError("输出必须是尚不存在的 JSON 文件，禁止覆盖")
    relative = path.relative_to(REPOSITORY).as_posix()
    ignored = subprocess.run(["git", "check-ignore", "--quiet", "--", relative],
        cwd=REPOSITORY, capture_output=True, check=False)
    if ignored.returncode != 0:
        raise PreparationError("输出路径必须已被当前仓库忽略，不能写入源码或跟踪文件")
    return path


def _schema_check(db):
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text
    from app.models import (College, CustomRoleSource, DataScopeRule, Major, Permission,
        PlatformConfig, PlatformOrder, Role, RoleAssignmentScope, RolePermission,
        RoleTemplate, RoleTemplatePermission, SchoolClass, StaffAssignment,
        StudentProfile, Tenant, User, UserRole)

    if db.scalar(text("SELECT DATABASE()")) != DATABASE_NAME:
        raise PreparationError("数据库会话实际目标与允许目标不符")
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    actual = set(MigrationContext.configure(db.connection()).get_current_heads())
    if not expected or actual != expected:
        raise PreparationError("迁移版本未与当前代码一致；本脚本不会迁移、重建或伪造版本")
    models = (College, CustomRoleSource, DataScopeRule, Major, Permission, PlatformConfig,
        PlatformOrder, Role, RoleAssignmentScope, RolePermission, RoleTemplate,
        RoleTemplatePermission, SchoolClass, StaffAssignment, StudentProfile, Tenant, User, UserRole)
    inspector = inspect(db.connection())
    tables = set(inspector.get_table_names())
    missing = []
    for model in models:
        table = model.__table__
        if table.name not in tables:
            missing.append(table.name)
            continue
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in columns)
    if missing:
        raise PreparationError("前置表或字段缺失：" + "、".join(missing))
    return sorted(actual)


def preflight(db, prefix):
    from sqlalchemy import select
    from app.models import College, Major, Permission, Role, SchoolClass, StudentProfile, Tenant, User
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import system_role_shadow_service as shadow
    from app.services.auth_service_db import _tenant_operating_status

    heads = _schema_check(db)
    tenant = db.get(Tenant, TENANT_ID)
    if (tenant is None or tenant.is_deleted or tenant.tenant_code != TENANT_CODE
            or str(tenant.status).upper() != "ACTIVE" or _tenant_operating_status(db, TENANT_ID) != "active"):
        raise PreparationError("既有 demo 虚构测试学校未正常启用；不创建或修改租户")
    commercial_state = commercial.commercial_state(TENANT_ID)
    if (not commercial_state.get("verified") or commercial_state.get("authoritySource") != "PAID_ORDER"
            or not commercial_state.get("features", {}).get("academicAffairs")):
        raise PreparationError("既有测试学校缺少真实、有效的教务商业授权；不修改订单或套餐")

    # 含软删记录也拒绝重复，绝不复活、接管或重置旧身份。
    for model, field in ((User, User.login_name), (Role, Role.role_code), (College, College.code),
            (Major, Major.code), (SchoolClass, SchoolClass.class_code), (StudentProfile, StudentProfile.student_no)):
        model_prefix = prefix.upper() if model is Role else prefix
        if db.scalar(select(model.id).where(model.tenant_id == TENANT_ID,
                field.startswith(model_prefix, autoescape=True)).limit(1)) is not None:
            raise PreparationError("该运行前缀已有身份或组织数据，请保留已有回执并使用新的运行前缀")

    templates, permissions, roles = {}, {}, {}
    for code in sorted({value[1] for value in IDENTITIES.values()}):
        codes = set(shadow.published_system_role_permissions(db, code))
        if code == "LEADER":
            codes = {value for value in codes if value.startswith("academicAffairs.")
                and value.rsplit(".", 1)[-1] in {"view", "stat"}}
        if not codes or any("*" in value for value in codes):
            raise PreparationError("已发布角色模板没有可用的具体权限集合：" + code)
        found = dict(db.execute(select(Permission.permission_code, Permission.id).where(
            Permission.permission_code.in_(codes))).all())
        if set(found) != codes:
            raise PreparationError("角色模板权限尚未全部落入现有权限目录：" + code)
        template = shadow._latest_published_template(db, code)
        templates[code] = {"id": str(template.id), "version": template.template_version,
            "permissionCount": len(codes), "permissionDigest": template.permission_digest}
        permissions[code] = found
        if code != "LEADER":
            role = db.scalar(select(Role).where(Role.tenant_id == TENANT_ID, Role.role_code == code))
            if role is not None and (role.is_deleted or role.status != "ACTIVE" or role.role_type != "SYSTEM"):
                raise PreparationError("现有运行角色不可直接复用，不修改其配置：" + code)
            roles[code] = role
    return {"heads": heads, "templates": templates, "permissions": permissions, "roles": roles}


def _write_private_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            # 先收紧新文件权限，再写口令；不改目录或已有文件的访问控制。
            who = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                capture_output=True, text=True, check=True)
            import csv
            sid = next(csv.reader([who.stdout.strip()]))[1]
            secured = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                capture_output=True, check=False)
            if secured.returncode != 0:
                raise PreparationError("无法保护本机回执文件；尚未写入口令或提交数据库")
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = None
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
    finally:
        if descriptor is not None:
            os.close(descriptor)


def prepare(db, prefix, plan, state_path, credentials_path):
    from app.core.security import hash_password
    from app.core.student_lifecycle import ENROLLED
    from app.models import (College, CustomRoleSource, DataScopeRule, Major, Role,
        RoleAssignmentScope, RolePermission, SchoolClass, StaffAssignment, StudentProfile, User, UserRole)

    now = datetime.utcnow()
    effective = now - timedelta(minutes=1)
    note = "V5 独立测试库虚构身份准备；" + prefix
    roles = dict(plan["roles"])
    role_names = {"ACADEMIC_ADMIN": "校教务处测试岗位", "COLLEGE_ADMIN": "学院教务测试岗位",
        "ACADEMIC_TEACHER": "任课教师测试岗位"}
    for code, role in roles.items():
        if role is None:
            role = Role(tenant_id=TENANT_ID, role_code=code, role_name=role_names[code],
                role_type="SYSTEM", status="ACTIVE", remark=note)
            db.add(role); db.flush()
            # 只给新运行角色具体模板权限，不调整已存在角色或模板。
            db.add_all([RolePermission(tenant_id=TENANT_ID, role_id=role.id,
                permission_id=permission_id, status="ACTIVE") for permission_id in plan["permissions"][code].values()])
            roles[code] = role
    reader = Role(tenant_id=TENANT_ID, role_code=(prefix + "reader").upper(), role_name="V5 学校只读观察员",
        role_type="CUSTOM", status="ACTIVE", remark=note)
    db.add(reader); db.flush()
    roles["LEADER"] = reader
    codes = sorted(plan["permissions"]["LEADER"])
    db.add(CustomRoleSource(tenant_id=TENANT_ID, role_id=reader.id, role_code=reader.role_code,
        source_template_code="LEADER", source_template_version=plan["templates"]["LEADER"]["version"],
        permission_codes_json={"items": codes}, drift_json={"pinned": True, "automaticUpgrade": False}, status="ACTIVE"))
    db.add(DataScopeRule(tenant_id=TENANT_ID, role_code=reader.role_code, rule_name=prefix + "reader",
        scope_type="SCHOOL", status="ACTIVE", remark=note))
    db.add_all([RolePermission(tenant_id=TENANT_ID, role_id=reader.id,
        permission_id=permission_id, status="ACTIVE") for permission_id in plan["permissions"]["LEADER"].values()])

    colleges, objects = {}, {}
    for label, title in (("A", "甲"), ("B", "乙")):
        college = College(tenant_id=TENANT_ID, code=prefix + label, college_name=f"V5 {title}学院 {prefix}",
            status="ACTIVE", remark=note)
        db.add(college); db.flush()
        major = Major(tenant_id=TENANT_ID, college_id=college.id, code=prefix + label,
            major_name=f"V5 {title}专业", status="ACTIVE", education_years=3, training_level="HIGHER", remark=note)
        db.add(major); db.flush()
        group = SchoolClass(tenant_id=TENANT_ID, major_id=major.id, class_code=prefix + label,
            class_name=f"V5 {title}学院虚构班", grade=str(ENTRY_YEAR), graduate_year=str(GRADUATE_YEAR),
            capacity=30, status="ACTIVE", class_status="NORMAL", remark=note)
        db.add(group); db.flush()
        students = [StudentProfile(tenant_id=TENANT_ID, student_no=prefix + label + str(index),
            real_name=f"V5 {title}学院虚构学生{index}", college_id=college.id, major_id=major.id,
            class_id=group.id, grade=group.grade, current_stage=ENROLLED, student_status="NORMAL",
            enroll_date=datetime(ENTRY_YEAR, 9, 1), status="ACTIVE", remark=note) for index in (1, 2)]
        db.add_all(students); db.flush()
        objects[label] = (college, major, group)
        colleges[label] = {"collegeId": str(college.id), "majorId": str(major.id),
            "classId": str(group.id), "studentIds": [str(student.id) for student in students]}

    accounts, credentials = {}, {}
    for key, (name, source, label) in IDENTITIES.items():
        role = roles[source]
        login = prefix + key.lower()
        password = "Aa9!" + secrets.token_urlsafe(24)
        user = User(tenant_id=TENANT_ID, login_name=login, real_name="V5 " + name,
            password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE", must_change_password=False)
        db.add(user); db.flush()
        link = UserRole(tenant_id=TENANT_ID, user_id=user.id, role_id=role.id, status="ACTIVE")
        db.add(link); db.flush()
        teacher = key.startswith("teacher")
        scope_type = "SCHOOL" if label is None else ("CLASS" if teacher else "COLLEGE")
        scope_id = 0 if label is None else int(colleges[label]["classId" if teacher else "collegeId"])
        db.add(RoleAssignmentScope(tenant_id=TENANT_ID, user_id=user.id, user_role_id=link.id,
            role_code=role.role_code, scope_type=scope_type, scope_id=scope_id,
            effective_at=effective, status="ACTIVE", reason=note))
        if key != "leader":
            db.add(StaffAssignment(tenant_id=TENANT_ID, user_id=user.id,
                org_type="SCHOOL" if label is None else "COLLEGE",
                org_node_id=TENANT_ID if label is None else int(colleges[label]["collegeId"]),
                assignment_type="ACADEMIC_REVIEWER" if label is None else ("OTHER" if teacher else "SECRETARY"),
                is_primary=True, source_type="MANUAL", source_id=prefix,
                effective_at=effective, status="ACTIVE", reason=note))
        if key.startswith("college"):
            objects[label][0].secretary_id = user.id  # 仅本事务刚新增的虚构学院。
        accounts[key] = {"loginName": login, "userId": str(user.id), "roleCode": role.role_code,
            "roleId": str(role.id), "contextId": f"role:{role.id}"}
        if teacher:
            accounts[key]["teacherKey"] = login  # 正式任课写服务的规范键。
        credentials[login] = {"password": password}
    db.flush()
    state = {"tenantCode": TENANT_CODE, "tenantId": str(TENANT_ID), "prefix": prefix,
        "accounts": accounts, "colleges": colleges,
        "cohort": {"entryYear": ENTRY_YEAR, "expectedGraduateYear": GRADUATE_YEAR},
        "migrationHeads": plan["heads"],
        "sourceTemplates": plan["templates"], "createdAt": now.isoformat() + "Z",
        "note": "仅身份与组织前置；无学生登录账号、课程、培养方案或业务终态。正常登录及业务流程尚未验收。"}
    # 先保全新身份的随机口令，再提交；任何提交异常都保留回执，禁止自动重复运行。
    _write_private_json(credentials_path, credentials)
    _write_private_json(state_path, state)
    db.commit()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true", help="显式新增虚构身份；默认仅只读预览")
    parser.add_argument("--state", help="无口令回执的新 JSON 路径")
    parser.add_argument("--credentials", help="独立私有口令的新 JSON 路径")
    args = parser.parse_args(argv)
    raw = require_target(os.environ)
    prefix = require_run_id(args.run_id)
    directory = REPOSITORY / ".codex-temp" / "e2e-v5"
    state_path = output_path(args.state, directory / f"{args.run_id}-state.json")
    credentials_path = output_path(args.credentials, directory / f"{args.run_id}-credentials.json")
    if state_path == credentials_path:
        raise PreparationError("无密回执和口令文件必须分开")
    sys.path.insert(0, str(BACKEND))
    from app.core.config import settings
    if settings.effective_database_url != raw or not settings.DB_ENABLED or settings.APP_ENV != "test":
        raise PreparationError("实际应用配置与显式隔离目标不一致")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool
    engine = create_engine(raw, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            if not args.execute:
                connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
                connection.commit()
            with Session(bind=connection) as db:
                plan = preflight(db, prefix)
                if args.execute:
                    prepare(db, prefix, plan, state_path, credentials_path)
                else:
                    db.rollback()
        print(json.dumps({"executed": args.execute, "accountCount": len(IDENTITIES),
            "collegeCount": 2, "studentCount": 4, "statePath": str(state_path),
            "credentialsPath": str(credentials_path)}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except PreparationError as error:
        print("拒绝准备：" + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:
        # 驱动异常可能携带连接参数/INSERT 参数，绝不输出原异常或堆栈。
        print("准备失败（" + type(error).__name__ + "）；检查前置条件及无密回执，禁止自动重试或覆盖口令文件。", file=sys.stderr)
        raise SystemExit(1) from None
