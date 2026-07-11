"""
mock RBAC 服务：菜单 / 按钮权限 / 数据范围
────────────────────────────────────────────────────────────
对齐 docs/05-数据接口权限与安全/api/01（§1.9 数据范围、§1.10 菜单、§1.11 按钮）与冻结契约 §八（12 种数据范围）。
菜单 = 已购模块 ∩ 角色权限 ∩（学生端再 ∩ 学生阶段），真实接库后据 t_role_permission 等计算。
"""
from __future__ import annotations

from app.services.mock_auth_service import get_active_context

# 冻结契约 §八：12 种数据范围
DATA_SCOPE_CATALOG = [
    {"scopeType": "SELF", "scopeLabel": "本人"},
    {"scopeType": "CLASS", "scopeLabel": "本班"},
    {"scopeType": "COUNSELOR_CLASSES", "scopeLabel": "本人所带班级学生"},
    {"scopeType": "GD_STUDENTS", "scopeLabel": "本人指导毕设学生"},
    {"scopeType": "INTERN_STUDENTS", "scopeLabel": "本人指导实习学生"},
    {"scopeType": "ENTERPRISE_AUTH_STUDENTS", "scopeLabel": "企业授权可见学生"},
    {"scopeType": "MAJOR", "scopeLabel": "本专业学生"},
    {"scopeType": "COLLEGE", "scopeLabel": "本学院学生"},
    {"scopeType": "SCHOOL", "scopeLabel": "全校学生"},
    {"scopeType": "DEPARTMENT", "scopeLabel": "本部门"},
    {"scopeType": "TEMP_AUTH", "scopeLabel": "临时授权范围"},
    {"scopeType": "CUSTOM", "scopeLabel": "自定义范围"},
]

# 各角色/端的菜单树（示意）。字段对齐 §1.10：menuCode/title/path/icon/moduleCode/readonly/children
_STUDENT_MENUS = [
    {"menuCode": "stu_home", "title": "首页", "path": "/student/home", "icon": "home", "moduleCode": "core", "readonly": False, "children": []},
    {"menuCode": "stu_profile", "title": "我的档案", "path": "/student/profile", "icon": "id", "moduleCode": "student", "readonly": False, "children": []},
    {"menuCode": "stu_enroll", "title": "迎新报到", "path": "/student/enroll", "icon": "flag", "moduleCode": "enrollment", "readonly": False, "children": []},
    {"menuCode": "stu_service", "title": "在校服务", "path": "/student/service", "icon": "service", "moduleCode": "campus_service", "readonly": False, "children": []},
    {"menuCode": "stu_intern", "title": "岗位实习", "path": "/student/intern", "icon": "work", "moduleCode": "internship", "readonly": False, "children": []},
    {"menuCode": "stu_gd", "title": "毕业设计", "path": "/student/graduation", "icon": "book", "moduleCode": "graduation", "readonly": False, "children": []},
    {"menuCode": "stu_employ", "title": "就业去向", "path": "/student/employment", "icon": "career", "moduleCode": "employment", "readonly": False, "children": []},
    {"menuCode": "stu_msg", "title": "消息中心", "path": "/student/messages", "icon": "bell", "moduleCode": "core", "readonly": False, "children": []},
]
_TEACHER_MENUS = [
    {"menuCode": "t_dashboard", "title": "工作台", "path": "/teacher/dashboard", "icon": "dashboard", "moduleCode": "core", "readonly": False, "children": []},
    {"menuCode": "t_todo", "title": "待办中心", "path": "/teacher/todos", "icon": "task", "moduleCode": "core", "readonly": False, "children": []},
    {"menuCode": "t_approval", "title": "审批处理", "path": "/teacher/approvals", "icon": "check", "moduleCode": "workflow", "readonly": False, "children": []},
    {"menuCode": "t_students", "title": "我的学生", "path": "/teacher/students", "icon": "team", "moduleCode": "student", "readonly": False, "children": []},
    {"menuCode": "t_intern", "title": "实习管理", "path": "/teacher/intern", "icon": "work", "moduleCode": "internship", "readonly": False, "children": []},
    {"menuCode": "t_gd", "title": "毕设指导", "path": "/teacher/graduation", "icon": "book", "moduleCode": "graduation", "readonly": False, "children": []},
    {"menuCode": "t_employ", "title": "就业跟进", "path": "/teacher/employment", "icon": "career", "moduleCode": "employment", "readonly": False, "children": []},
    {"menuCode": "t_msg", "title": "消息中心", "path": "/teacher/messages", "icon": "bell", "moduleCode": "core", "readonly": False, "children": []},
]
_ADMIN_MENUS = [
    {"menuCode": "a_dashboard", "title": "工作台", "path": "/admin/dashboard", "icon": "dashboard", "moduleCode": "core", "readonly": False, "children": []},
    {"menuCode": "a_students", "title": "学生管理", "path": "/admin/students", "icon": "team", "moduleCode": "student", "readonly": False, "children": [
        {"menuCode": "a_students_list", "title": "学生主档", "path": "/admin/students/list", "icon": "list", "moduleCode": "student", "readonly": False, "children": []},
        {"menuCode": "a_students_360", "title": "学生360", "path": "/admin/students/360", "icon": "profile", "moduleCode": "student", "readonly": False, "children": []},
    ]},
    {"menuCode": "a_data", "title": "数据中心", "path": "/admin/data", "icon": "chart", "moduleCode": "analytics", "readonly": False, "children": []},
    {"menuCode": "a_enroll", "title": "迎新管理", "path": "/admin/enrollment", "icon": "flag", "moduleCode": "enrollment", "readonly": False, "children": []},
    {"menuCode": "a_intern", "title": "实习管理", "path": "/admin/intern", "icon": "work", "moduleCode": "internship", "readonly": False, "children": []},
    {"menuCode": "a_gd", "title": "毕设管理", "path": "/admin/graduation", "icon": "book", "moduleCode": "graduation", "readonly": False, "children": []},
    {"menuCode": "a_employ", "title": "就业管理", "path": "/admin/employment", "icon": "career", "moduleCode": "employment", "readonly": False, "children": []},
    {"menuCode": "a_authz", "title": "权限与审批", "path": "/admin/authz", "icon": "lock", "moduleCode": "workflow", "readonly": False, "children": []},
    {"menuCode": "a_io", "title": "导入导出", "path": "/admin/io", "icon": "swap", "moduleCode": "core", "readonly": False, "children": []},
    {"menuCode": "a_settings", "title": "系统设置", "path": "/admin/settings", "icon": "setting", "moduleCode": "core", "readonly": False, "children": []},
]

_MENUS_BY_TYPE = {"STUDENT": _STUDENT_MENUS, "TEACHER": _TEACHER_MENUS, "ADMIN": _ADMIN_MENUS}

# 各角色按钮权限码（permissionActions），对齐 §1.11。真实接库后据 t_role_permission。
_BUTTONS_BY_TYPE = {
    "STUDENT": ["service.apply", "intern.log.submit", "gd.material.upload", "employment.report"],
    "TEACHER": ["todo.handle", "approval.approve", "approval.return", "approval.reject",
                "intern.report.review", "student.field.view_full", "student.export"],
    "ADMIN": ["student.import", "student.export", "student.field.view_full",
              "role.assign", "module.entitlement.manage", "audit.view", "data.export"],
}


def get_menus(user_ctx: dict) -> dict:
    active = get_active_context(user_ctx)
    menus = _MENUS_BY_TYPE.get(user_ctx.get("userType"), _TEACHER_MENUS)
    return {"activeContextId": active["contextId"], "contextType": active["contextType"], "items": menus}


def get_permissions(user_ctx: dict, page: str | None) -> dict:
    active = get_active_context(user_ctx)
    buttons = _BUTTONS_BY_TYPE.get(user_ctx.get("userType"), [])
    return {"page": page, "contextType": active["contextType"], "buttons": buttons}


def get_data_scope(user_ctx: dict) -> dict:
    active = get_active_context(user_ctx)
    return {
        "scopeType": active["dataScope"],
        "scopeLabel": active.get("scopeLabel", ""),
        "studentCount": active.get("studentCount", 0),
        "catalog": DATA_SCOPE_CATALOG,  # 全部 12 种数据范围（供前端渲染/参考）
    }


# ── BACKEND-OVERNIGHT 追加 ──
ROLE_CATALOG = [
    {"roleCode": "STUDENT", "roleName": "学生", "side": "school", "defaultScope": "SELF"},
    {"roleCode": "COUNSELOR", "roleName": "辅导员", "side": "school", "defaultScope": "COUNSELOR_CLASSES"},
    {"roleCode": "GD_MENTOR", "roleName": "指导教师", "side": "school", "defaultScope": "GD_STUDENTS"},
    {"roleCode": "EMPLOYMENT_TEACHER", "roleName": "就业老师", "side": "school", "defaultScope": "SCHOOL"},
    {"roleCode": "ACADEMIC_TEACHER", "roleName": "教务老师", "side": "school", "defaultScope": "SCHOOL"},
    {"roleCode": "STUDENT_AFFAIRS", "roleName": "学工老师", "side": "school", "defaultScope": "COLLEGE"},
    {"roleCode": "COLLEGE_ADMIN", "roleName": "学院管理员", "side": "school", "defaultScope": "COLLEGE"},
    {"roleCode": "SCHOOL_ADMIN", "roleName": "学校管理员", "side": "school", "defaultScope": "SCHOOL"},
    {"roleCode": "SYS_ADMIN", "roleName": "系统管理员", "side": "school", "defaultScope": "SCHOOL"},
    {"roleCode": "PLATFORM_OP", "roleName": "平台运营人员", "side": "platform", "defaultScope": "PLATFORM"},
    {"roleCode": "LEADER", "roleName": "校领导/院系领导", "side": "school", "defaultScope": "SCHOOL"},
]

DATA_SCOPE_CATALOG = [
    {"scope": "SELF", "label": "本人"},
    {"scope": "GD_STUDENTS", "label": "本人负责学生（毕设）"},
    {"scope": "INTERN_STUDENTS", "label": "本人负责学生（实习）"},
    {"scope": "CLASS", "label": "本班级"},
    {"scope": "COUNSELOR_CLASSES", "label": "本人所带班级"},
    {"scope": "MAJOR", "label": "本专业"},
    {"scope": "COLLEGE", "label": "本学院"},
    {"scope": "SCHOOL", "label": "全校"},
    {"scope": "PLATFORM", "label": "全平台（运营侧，不含学生敏感明文）"},
    {"scope": "DEPARTMENT", "label": "指定组织"},
    {"scope": "TEMP_AUTH", "label": "临时授权"},
    {"scope": "CUSTOM", "label": "自定义范围"},
]


def get_role_catalog(user_ctx: dict) -> dict:
    """角色目录：平台运营与学校角色边界隔离——学校侧看不到 platform 角色详情之外的能力。"""
    from app.services.mock_auth_service import get_active_context
    active = get_active_context(user_ctx)
    is_platform = active["contextType"] == "PLATFORM_OP"
    roles = ROLE_CATALOG if is_platform else [r for r in ROLE_CATALOG if r["side"] == "school"]
    return {"roles": roles, "dataScopes": DATA_SCOPE_CATALOG}


def get_current_context(user_ctx: dict) -> dict:
    """当前身份上下文：currentRole + dataScope + permissionActions（前端 ctx 契约）。"""
    from app.services.mock_auth_service import get_active_context
    active = get_active_context(user_ctx)
    is_platform = active["contextType"] == "PLATFORM_OP"
    return {
        "currentRole": {"roleCode": active["contextType"], "roleName": active["contextName"],
                        "userName": user_ctx.get("realName", "")},
        "dataScope": {"scope": active["dataScope"], "scopeLabel": active.get("scopeLabel", ""),
                      "scopeName": active.get("scopeLabel", "")},
        "permissionActions": {
            "viewList": {"visible": True, "enabled": True},
            "export": {"visible": not is_platform, "enabled": not is_platform,
                       "reason": "平台运营不可导出学校学生数据" if is_platform else ""},
            "viewSensitive": {"visible": False, "enabled": False,
                              "reason": "敏感明文需字段级授权（field:view_full），默认脱敏"},
        },
        "boundary": "平台运营与学校角色边界：平台侧不可见学校学生敏感明文；学生仅拥有小程序侧能力",
    }
