"""
统一权限执行层（后端唯一入口）—— permissionCode / 超管判定 / 模块授权。
────────────────────────────────────────────────────────────
背景（见系统管理中心只读审查 P0-3 / P1-11）：
- 此前全后端约 913/926 端点仅有身份门禁（require_staff 只拦学生），无任何 permissionCode 级校验；
- "超级管理员/管理员" 判定散落在 ≥4 处、常量与机制各异；
- 唯一的 /authz/check 是"默认放行"装饰件。

本模块收敛为单一入口，默认拒绝（fail-closed）：
- is_super_admin(user)            集中式超管判定（替换散落判断）
- has_permission(user, code)      纯判定，不抛异常
- enforce_permission(user, code)  命令式校验（不嵌套 Depends，抛 403 + 写审计），供既有端点内联复用
- require_permission(code)         FastAPI 依赖工厂（供新端点声明式挂载）
- require_any_permission(*codes)   任一命中即放行
- require_module(module_key)       模块授权门禁（DB 模式 fail-closed）

角色→permissionCode 授予集当前为集中式内置表（替换散落硬编码，命名对齐 CLAUDE.md §10：
module.domain.action）。真实接库后 _granted() 优先查 t_role_permission，未命中再回落本表——
调用点与端点声明无需再改。
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Depends

from app.core.exceptions import no_permission
from app.core.security import get_current_user

PLATFORM_SUPER_ADMIN = "PLATFORM_SUPER_ADMIN"

# 角色 → 授予的 permissionCode 模式集合。支持三种模式：
#   "*"                              全部放行（平台超管 / 学校管理员本校全权；接库后按 t_role_permission 收敛）
#   "studentAffairs.*" / "audit.*"   前缀通配（"a.b.*" 命中 "a.b.xxx"）
#   "academicAffairs.grade.publish"  精确匹配
# 未登记的角色一律得到空集（默认拒绝）。数据范围（本人/班级/学院…）不在此裁定，由 scope 解析器另行收敛。
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "PLATFORM_SUPER_ADMIN": {"*"},
    "SCHOOL_ADMIN": {"*"},                       # 学校管理员：本校全权（接库后再按需收敛）
    "SYS_ADMIN": {"systemAdmin.*", "audit.*"},
    "SECURITY_AUDITOR": {"audit.*", "systemAdmin.audit.*", "campusService.audit.view",
                         # 实习督导/审计：只读监督（看板/学生/风险/统计/分配日志/审核台账），不授予任何写操作
                         "internship.dashboard.view", "internship.student.view", "internship.risk.view",
                         "internship.stats.view", "internship.stats.enterprise.view", "internship.stats.position.view",
                         "internship.stats.score.view", "internship.match.log.view", "internship.application.view",
                         "internship.archive.view", "internship.complaint.view"},
    "LEADER": {"audit.view", "*.view", "*.stat"},  # 校/院领导：只读驾驶舱（含 campusService.*.view）
    "COLLEGE_ADMIN": {"studentAffairs.*", "academicAffairs.*", "campusService.*", "graduationDesign.*",
                      "internship.*", "audit.view"},  # 本院（范围另行收敛）；实习学院负责人本院全权，成绩发布等超高危由端点层校级再收敛
    "ACADEMIC_TEACHER": {"academicAffairs.*"},
    "ACADEMIC_ADMIN": {"academicAffairs.*", "audit.view"},  # 教务处管理员：本校教务全权（TENANT_ALL），
                                                             # 与 COLLEGE_ADMIN 区分——成绩发布/退回/归档等
                                                             # 超高危动作端点内额外校验角色=ACADEMIC_ADMIN/SCHOOL_ADMIN

    "STUDENT_AFFAIRS": {"studentAffairs.*", "campusService.*"},
    "STUDENT_AFFAIRS_ADMIN": {"studentAffairs.*", "campusService.*", "audit.view"},  # 学工处管理员：全校学工+在校服务（心理原始明细默认不可见，由风险/心理模块按角色遮蔽）
    "PSYCHOLOGY_TEACHER": {"studentAffairs.risk.*", "studentAffairs.talk.*", "studentAffairs.stats.view",
                           "studentAffairs.archive.psySensitive", "studentAffairs.student.view"},  # 心理老师：数据范围限授权学生(PSY_STUDENT)
    # 资助老师（§12「资」列 / §13 FUNDING_BIZ）：困难认定 + 奖助勤贷全域经办，数据范围限资助业务学生。
    # 只授资助能力，不授违纪明细办理/心理/风险/宿舍（§12 资列：discipline 仅「资格校验只读结论」，risk/talk/dorm=✗）。
    # 注：FUNDING_BIZ 数据范围解析器尚未实现（见历史欠账），当前 scope 回退 NONE→受范围过滤的列表 fail-closed 为空；能力门禁已生效。
    "FUNDING_TEACHER": {
        "studentAffairs.dashboard.view", "studentAffairs.student.view", "studentAffairs.stats.view",
        "studentAffairs.aid.view", "studentAffairs.aid.batch.manage", "studentAffairs.aid.create",
        "studentAffairs.aid.approve", "studentAffairs.aid.adjust",
        "studentAffairs.funding.view", "studentAffairs.funding.project.manage",
        "studentAffairs.funding.create", "studentAffairs.funding.approve",
        "studentAffairs.funding.publicity.manage", "studentAffairs.funding.workstudy.manage",
        "studentAffairs.funding.loan.manage", "studentAffairs.funding.reduction.manage",
        "studentAffairs.funding.disburse.manage",
    },
    # 团委（社团/学生组织/党团发展 + 二课活动组织）：全校团学口径。边界（是否含全部二课/志愿）待学校确认。
    "YOUTH_LEAGUE": {
        "studentAffairs.dashboard.view", "studentAffairs.student.view", "studentAffairs.stats.view",
        "studentAffairs.club.view", "studentAffairs.club.manage",
        "studentAffairs.org.view", "studentAffairs.org.manage",
        "studentAffairs.league.view", "studentAffairs.league.manage",
        "studentAffairs.activity.view", "studentAffairs.activity.create",
        "studentAffairs.activity.publish", "studentAffairs.activity.confirm",
    },
    # 组织人事：辅导员考评的组织与复核（指标/评分/发布/申诉复核）；不介入学生业务。角色归属待学校确认。
    "ORG_PERSONNEL": {
        "studentAffairs.dashboard.view", "studentAffairs.stats.view",
        "studentAffairs.counselorEval.view", "studentAffairs.counselorEval.manage",
    },
    "DORM_MANAGER": {"studentAffairs.dorm.*", "campusService.dorm.*"},  # 宿管：仅宿舍域（数据范围限负责楼栋 DORM_BUILDING）；不得见学业/心理/困难/处分
    # 辅导员：数据范围限本人所带班级（服务层 _allowed_class_ids/scope 收敛，越权返回 NO_DATA_SCOPE）。
    # 本班范围内广读 + 操作 班级/请假/风险/谈话/家校；困难/资助/违纪的正式审批与登记归学工处/院，辅导员默认只读。
    "COUNSELOR": {
        "studentAffairs.dashboard.view",
        "studentAffairs.class.view", "studentAffairs.class.create", "studentAffairs.class.cadre.manage",
        "studentAffairs.student.view",
        "studentAffairs.leave.*", "studentAffairs.risk.*", "studentAffairs.talk.*",
        "studentAffairs.homeSchool.*",
        "studentAffairs.aid.view", "studentAffairs.funding.view", "studentAffairs.discipline.view",
        "studentAffairs.archive.view", "studentAffairs.stats.view",
        # 辅导员对「本人」考评的自助权：查看本人考评结果 + 对本人考评提起申诉（不含考评/复核 manage）
        "studentAffairs.counselorEval.view", "studentAffairs.counselorEval.appeal.create",
        # 旧「在校服务」面：本班范围广读 + 请假审批；资助/违纪/工单/学生台账写操作归学工处/院
        "campusService.dashboard.view", "campusService.student.view", "campusService.leave.*",
        "campusService.dorm.view", "campusService.grant.view", "campusService.discipline.view",
        "campusService.workOrder.view",
        # 岗位实习：辅导员对本班实习学生只读协同（学生/打卡/请假/周报/风险），不授予审批与配置
        "internship.dashboard.view", "internship.student.view", "internship.attendance.view",
        "internship.leave.view", "internship.report.view", "internship.risk.view",
        # 教务·缓考首级审批（13B 考务 D-08）：辅导员对本人所带班级学生的缓考申请首级审核，
        # 仅此一个 academicAffairs.* 点，不含其它教务权限（其余节点由任课教师/学院/教务处按 academicAffairs.* 通配覆盖）
        "academicAffairs.deferredExam.counselorReview",
        # 教务·学籍异动辅导员初审（13B 学籍异动 Tier1 R1）：辅导员对本人所带班级学生的休学/复学/
        # 退学/转专业申请首级审核（范围限本班，service 端 _check_node_authority 收敛），不授予发起/学院/教务处终审。
        "academicAffairs.statusChange.counselorReview",
    },
    # 毕设角色权限只决定“能做什么”；具体学生/评阅/答辩组必须再由业务关系收敛。
    "GRADUATION_ADMIN": {"graduationDesign.*"},
    "GD_COLLEGE_ADMIN": {"graduationDesign.*"},
    "GD_MAJOR_ADMIN": {
        "graduationDesign.view", "graduationDesign.topic.*", "graduationDesign.mentor.assign",
        "graduationDesign.proposal.review", "graduationDesign.stats.view",
    },
    "GD_MENTOR": {
        "graduationDesign.view", "graduationDesign.guide.*",
        "graduationDesign.proposal.review", "graduationDesign.final.review",
    },
    "GD_REVIEWER": {"graduationDesign.view", "graduationDesign.final.review"},
    "GD_DEFENSE_SECRETARY": {"graduationDesign.view", "graduationDesign.defense.manage"},
    "GD_DEFENSE_EXPERT": {"graduationDesign.view", "graduationDesign.defense.score"},
    # 校内指导教师：本人指导学生（范围由 scope 收敛）——工作台/学生/打卡请假审批/周报批阅/指导巡访/风险处理/评价，看企业岗位与匹配结果
    "INTERN_MENTOR": {
        "internship.guide.*", "internship.dashboard.view",
        "internship.student.view", "internship.student.material.view",
        "internship.attendance.*", "internship.makeup.*", "internship.leave.view", "internship.leave.review",
        "internship.report.view", "internship.report.review", "internship.report.export",
        "internship.plan.view", "internship.task.view",
        "internship.guidance.*", "internship.visit.*", "internship.communication.*",
        "internship.risk.view", "internship.risk.handle",
        # 评价：导师录入/审核本人指导学生的企业评价，填写鉴定意见并审核学生鉴定（数据范围由 service owner scope 收敛，跨学生 403）
        "internship.eval.self.view", "internship.eval.self.review",
        "internship.eval.enterprise.view", "internship.eval.enterprise.manage", "internship.eval.enterprise.review",
        "internship.eval.advisor.manage",
        # 成绩：导师核算/发布/撤回本人指导学生实习成绩；权重配置(score.config)与台账导出(score.export)归学校/学院
        "internship.score.view", "internship.score.manage", "internship.score.publish",
        "internship.application.view", "internship.application.review",
        # 三方协议：导师对本人指导学生生成/下发/记录企业签署/学校确认/驳回/作废/归档/电子签（跨学生由 service 拦 403）
        "internship.agreement.view", "internship.agreement.manage", "internship.agreement.sign",
        "internship.enterprise.view", "internship.position.view",
        "internship.match.intention.view", "internship.match.recommend.view", "internship.match.result.view",
        "internship.stats.view",
        # 保险查看、任务完成度审核、调岗退岗初审（§3 投影：导师查本人学生保险、审任务、初审变更）
        "internship.insurance.*", "internship.task.review", "internship.change.view", "internship.change.review",
        "internship.archive.*",  # 材料检查与归档（§3.12 导师参与归档，service scope 收敛到本人指导学生）
    },
    # 就业教师：实习就业转化 + 归档统计（跨中心与就业域衔接），不介入日常实习审批
    "EMPLOYMENT_TEACHER": {
        "employment.*", "internship.dashboard.view",
        "internship.employment.view", "internship.archive.*",
        "internship.stats.view", "internship.stats.enterprise.view",
        "internship.stats.position.view", "internship.stats.score.view",
    },
    "STAFF": set(),      # 最小权限兜底（未分配角色的真实账号，对齐 P0-2 修复）
    "STUDENT": set(),    # 学生走移动端本人端点，不进 PC 管理端
}


def _role_of(user: dict) -> str:
    return (user.get("currentRoleCode") or user.get("userType") or "").strip()


def is_super_admin(user: dict) -> bool:
    """集中式平台超管判定（替换 platform.py / student_portal_admin.py 等散落判断）。"""
    return _role_of(user) == PLATFORM_SUPER_ADMIN or user.get("userType") == PLATFORM_SUPER_ADMIN


def _granted(role: str) -> set[str]:
    """角色授予的 permissionCode 集合。接库钩子：DB 模式可在此优先查 t_role_permission。"""
    return ROLE_PERMISSIONS.get(role, set())


def _db_granted(user: dict) -> set[str] | None:
    """自定义角色仅从 t_role_permission 取权；内置模板仍由平台基线维护。"""
    context_id = str(user.get("activeContextId") or "")
    tenant_id = str(user.get("tenantId") or "")
    if not (context_id.startswith("role:") and context_id[5:].isdigit() and tenant_id.isdigit()):
        return None
    try:
        from sqlalchemy import select
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            return None
        from app.models import Permission, Role, RolePermission
        db = get_sessionmaker()()
        try:
            role = db.scalars(select(Role).where(Role.id == int(context_id[5:]),
                                                 Role.tenant_id == int(tenant_id),
                                                 Role.is_deleted.is_(False))).first()
            if role is None or str(role.role_type or "").upper() != "CUSTOM":
                return None
            return set(db.scalars(select(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id).where(
                RolePermission.tenant_id == int(tenant_id), RolePermission.role_id == role.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))).all())
        finally:
            db.close()
    except Exception:
        # 鉴权读取异常默认拒绝自定义角色，绝不回落为更宽的内置授权。
        return set()


def _match(code: str, patterns: Iterable[str]) -> bool:
    for p in patterns:
        if p == "*" or code == p:
            return True
        if p.endswith(".*") and (code == p[:-2] or code.startswith(p[:-1])):  # "a.b.*" → "a.b" / "a.b.x"
            return True
        if p.startswith("*.") and code.endswith(p[1:]):                        # "*.view" → "x.view"
            return True
    return False


def has_permission(user: dict, code: str) -> bool:
    """纯判定：当前身份是否拥有指定 permissionCode。默认拒绝。"""
    if is_super_admin(user):
        return True
    database_patterns = _db_granted(user)
    return _match(code, database_patterns if database_patterns is not None else _granted(_role_of(user)))


def _audit_denied(user: dict, code: str) -> None:
    try:  # 审计绝不阻塞主流程
        from app.services import audit_log
        audit_log.record("PERMISSION_DENIED", f"perm:{code}",
                         detail={"role": _role_of(user), "userId": user.get("userId"), "code": code},
                         result="DENIED")
    except Exception:  # noqa: BLE001
        pass


def enforce_permission(user: dict, code: str) -> dict:
    """命令式校验（不嵌套 Depends）：无权限则 403 + 写拒绝审计。供既有端点在函数体内内联调用。"""
    if not has_permission(user, code):
        _audit_denied(user, code)
        raise no_permission(f"无权限执行该操作（{code}）")
    return user


def require_permission(code: str):
    """FastAPI 依赖工厂：新端点声明式挂载 —— Depends(require_permission("module.domain.action"))。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        return enforce_permission(user, code)
    return _dep


def require_any_permission(*codes: str):
    """任一 permissionCode 命中即放行。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if is_super_admin(user) or any(has_permission(user, c) for c in codes):
            return user
        _audit_denied(user, "|".join(codes))
        raise no_permission("无权限执行该操作")
    return _dep


def require_module(module_key: str):
    """模块授权门禁：DB 模式下未授权租户 fail-closed 403；DB 未启用（mock 演示态）不阻断。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        from app.db.session import db_enabled
        if not db_enabled():
            return user  # mock 演示态：模块授权 DB 未启用，不误伤演示
        if is_super_admin(user):
            return user
        from app.core.context import current_tenant_id
        from app.services.platform_service import feature_enabled
        tid = current_tenant_id()
        if tid and not feature_enabled(int(tid), module_key):
            try:
                from app.services import audit_log
                audit_log.record("MODULE_DENIED", f"module:{module_key}", result="DENIED")
            except Exception:  # noqa: BLE001
                pass
            raise no_permission(f"该模块未授权：{module_key}")
        return user
    return _dep
