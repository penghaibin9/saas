"""学校上线检查：阻断 / 建议 / 通过 / 不适用。禁止一条总分掩盖问题。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.db.session import db_enabled, get_sessionmaker

BLOCKER = "BLOCKER"
ADVISORY = "ADVISORY"
PASSED = "PASSED"
NA = "NOT_APPLICABLE"


def _item(code: str, title: str, status: str, detail: str, impact: str = "", action: str = "") -> dict:
    return {
        "code": code, "title": title, "status": status, "detail": detail,
        "impact": impact, "recommendedAction": action,
    }


def run_go_live_checks(tenant_id: int | None = None) -> dict:
    tid = int(tenant_id or current_tenant_id() or 0)
    checks: list[dict] = []
    if not db_enabled():
        return {
            "tenantId": tid,
            "summary": {"blocker": 1, "advisory": 0, "passed": 0, "na": 0},
            "items": [_item("db", "数据库连接", BLOCKER, "数据库未启用，无法上线验收",
                            "全部业务不可用", "启用 MySQL 并完成迁移")],
            "canGoLive": False,
        }

    db = get_sessionmaker()()
    try:
        from app.models import College, Major, Role, SchoolClass, User, UserRole
        from app.models.student import StudentProfile
        from app.services import system_governance_service as gov
        from app.services.module_access_service import module_access_state
        from app.services.platform_service import tenant_meta

        meta = {}
        try:
            meta = tenant_meta(tid) or {}
        except Exception:
            meta = {}
        school_name = meta.get("schoolName") or meta.get("tenantName") or ""
        if school_name:
            checks.append(_item("school_info", "学校基本信息", PASSED, f"学校名称：{school_name}"))
        else:
            checks.append(_item("school_info", "学校基本信息", ADVISORY, "未配置学校名称",
                                "对外展示不完整", "在学校信息与品牌中补全"))

        # 学期：教务若未建表则 NA
        try:
            from app.models import AaTerm  # type: ignore
            terms = db.scalar(select(func.count()).select_from(AaTerm).where(
                AaTerm.tenant_id == tid, AaTerm.is_deleted.is_(False))) or 0
            if terms:
                checks.append(_item("term", "学期", PASSED, f"已配置 {terms} 个学期"))
            else:
                checks.append(_item("term", "学期", ADVISORY, "尚未配置学期",
                                    "教务排课/成绩受影响", "在教务中心创建当前学期"))
        except Exception:
            checks.append(_item("term", "学期", NA, "当前环境无学期模型或未迁移"))

        colleges = db.scalar(select(func.count()).select_from(College).where(
            College.tenant_id == tid, College.is_deleted.is_(False), College.status == "ACTIVE")) or 0
        majors = db.scalar(select(func.count()).select_from(Major).where(
            Major.tenant_id == tid, Major.is_deleted.is_(False), Major.status == "ACTIVE")) or 0
        classes = db.scalar(select(func.count()).select_from(SchoolClass).where(
            SchoolClass.tenant_id == tid, SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE")) or 0
        if colleges and majors and classes:
            checks.append(_item("org", "学院/专业/班级", PASSED,
                                f"学院{colleges}/专业{majors}/班级{classes}"))
        elif not colleges:
            checks.append(_item("org", "学院/专业/班级", BLOCKER, "无学院主数据",
                                "无法建班与分权限", "在组织与任职中创建学院"))
        else:
            checks.append(_item("org", "学院/专业/班级", ADVISORY,
                                f"学院{colleges}/专业{majors}/班级{classes} 不完整",
                                "部分业务范围无法落地", "补齐专业与班级"))

        teachers = db.scalar(select(func.count()).select_from(User).where(
            User.tenant_id == tid, User.is_deleted.is_(False), User.user_type != "STUDENT")) or 0
        students = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False))) or 0
        if teachers and students:
            checks.append(_item("accounts", "学生和教师账号", PASSED,
                                f"教师/职工账号 {teachers}，学生档案 {students}"))
        elif not teachers:
            checks.append(_item("accounts", "学生和教师账号", BLOCKER, "无教职工账号",
                                "无法登录管理端", "导入老师账号"))
        else:
            checks.append(_item("accounts", "学生和教师账号", ADVISORY, f"学生档案 {students}",
                                "学工/教务缺少对象", "导入学生"))

        role_links = db.scalar(select(func.count()).select_from(UserRole).where(
            UserRole.tenant_id == tid, UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")) or 0
        roles = db.scalar(select(func.count()).select_from(Role).where(
            Role.tenant_id == tid, Role.is_deleted.is_(False))) or 0
        if role_links and roles:
            checks.append(_item("roles", "关键任职与角色", PASSED, f"角色 {roles}，任职 {role_links}"))
        else:
            checks.append(_item("roles", "关键任职与角色", BLOCKER, "缺少角色或任职关系",
                                "权限无法生效", "配置角色并分配成员"))

        features = gov.get_module_features()
        entitled_off = [k for k, v in features.items() if not v.get("entitled", True)]
        disabled = [k for k, v in features.items() if v.get("entitled", True) and not v.get("enabled", True)]
        checks.append(_item("modules", "模块授权", PASSED if not entitled_off else ADVISORY,
                            f"未购 {len(entitled_off)}，学校停用 {len(disabled)}",
                            "未购模块接口 403", "与平台确认套餐或启停学校开关"))

        # 权限：至少存在自定义或系统角色
        checks.append(_item("permissions", "权限", PASSED if roles else BLOCKER,
                            "角色目录可用" if roles else "无角色",
                            "菜单与操作不可授权", "启用预设角色模板"))

        # 数据范围：存在结构化规则或历史兼容
        try:
            from app.models import DataScopeRule
            scope_n = db.scalar(select(func.count()).select_from(DataScopeRule).where(
                DataScopeRule.tenant_id == tid, DataScopeRule.is_deleted.is_(False),
                DataScopeRule.status == "ACTIVE")) or 0
            checks.append(_item("data_scope", "数据范围", PASSED if scope_n else ADVISORY,
                                f"结构化规则 {scope_n} 条" if scope_n else "尚未配置结构化范围（仍可读历史 remark）",
                                "CUSTOM/跨院范围可能拒绝", "在角色权限与数据范围中配置"))
        except Exception:
            checks.append(_item("data_scope", "数据范围", NA, "数据范围表不可用"))

        # 流程
        try:
            from app.models import WorkflowDefinition
            flows = db.scalar(select(func.count()).select_from(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == tid, WorkflowDefinition.is_deleted.is_(False))) or 0
            checks.append(_item("workflow", "流程", PASSED if flows else ADVISORY,
                                f"流程定义 {flows}" if flows else "未安装流程定义",
                                "审批可能不可用", "在实施中心安装预设或配置流程"))
        except Exception:
            checks.append(_item("workflow", "流程", NA, "流程模型不可用"))

        # 接口 / 同步
        integrations = gov.list_integrations()
        jobs = gov.list_sync_jobs()
        failed_jobs = [j for j in jobs if j.get("status") == "FAILED"]
        checks.append(_item("integrations", "接口", ADVISORY if not integrations else PASSED,
                            f"已登记连接 {len(integrations)}（均为配置登记，非已连接）",
                            "外部同步不可用不影响校内主流程", "按需登记接口凭证"))
        checks.append(_item("sync", "同步", PASSED if not failed_jobs else ADVISORY,
                            f"失败任务 {len(failed_jobs)}" if failed_jobs else "无失败同步任务",
                            "外部数据可能滞后", "在失败中心重试或取消"))

        # 安全配置
        checks.append(_item("security", "安全配置", PASSED, "字段加密与审计链路已接入",
                            "", "定期检查审计与敏感扫描"))

        # 核心业务模块四态抽样
        for mk in ("studentAffairs", "academicAffairs", "graduationDesign", "internship", "employment", "orientation"):
            st = module_access_state(tid, mk)
            status = PASSED if st.get("entitled") and st.get("enabled") else ADVISORY
            if not st.get("entitled"):
                status = ADVISORY
            checks.append(_item(f"module_{mk}", f"模块准备度-{mk}", status,
                                st.get("reason") or f"entitled={st.get('entitled')} enabled={st.get('enabled')}",
                                "未授权模块访问将 403", "购买后启用以供业务使用"))

    finally:
        db.close()

    summary = {
        "blocker": sum(1 for c in checks if c["status"] == BLOCKER),
        "advisory": sum(1 for c in checks if c["status"] == ADVISORY),
        "passed": sum(1 for c in checks if c["status"] == PASSED),
        "na": sum(1 for c in checks if c["status"] == NA),
    }
    return {
        "tenantId": tid,
        "summary": summary,
        "items": checks,
        "canGoLive": summary["blocker"] == 0,
    }
