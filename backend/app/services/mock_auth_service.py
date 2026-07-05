"""
mock 认证服务（登录 / 当前用户 / 切换身份）
────────────────────────────────────────────────────────────
字段对齐 docs/api/01（§1.1 登录、§1.4 me、§1.6 身份列表、§1.8 切换、§1.9 数据范围）。
多身份、当前身份 active_context、切换后菜单/待办/数据范围改变，均在此体现。
真实接库后：查 t_user / t_user_context / t_user_active_context，叠加权限四要素。
"""
from __future__ import annotations

from typing import Optional

from app.core.exceptions import AppException, not_found
from app.core.security import create_access_token

# ── 演示用户注册表（将来由 t_user + t_user_context 提供）──
DEMO_USERS = {
    "u_teacher_001": {
        "userId": "u_teacher_001",
        "loginName": "20230101",
        "realName": "王建国",
        "userType": "TEACHER",
        "avatarFileId": None,
        "phoneMasked": "138****6621",
        "contexts": [
            {"contextId": "ctx_counselor_01", "contextType": "COUNSELOR",
             "contextName": "软件2401辅导员", "orgName": "软件学院·软件2401班",
             "dataScope": "COUNSELOR_CLASSES", "scopeLabel": "本人所带班级学生",
             "studentCount": 45, "todoCount": 6, "riskCount": 2, "enabled": True},
            {"contextId": "ctx_gd_mentor_01", "contextType": "GD_MENTOR",
             "contextName": "毕业设计指导教师", "orgName": "软件学院",
             "dataScope": "GD_STUDENTS", "scopeLabel": "本人指导毕设学生",
             "studentCount": 8, "todoCount": 3, "riskCount": 0, "enabled": True},
            {"contextId": "ctx_intern_mentor_01", "contextType": "INTERN_MENTOR",
             "contextName": "岗位实习指导教师", "orgName": "软件学院",
             "dataScope": "INTERN_STUDENTS", "scopeLabel": "本人指导实习学生",
             "studentCount": 18, "todoCount": 5, "riskCount": 1, "enabled": True},
        ],
    },
    "u_student_001": {
        "userId": "u_student_001",
        "loginName": "20230999",
        "realName": "李晓萌",
        "userType": "STUDENT",
        "studentId": "stu_1001",
        "avatarFileId": None,
        "phoneMasked": "159****0088",
        "contexts": [
            {"contextId": "ctx_student_self", "contextType": "STUDENT",
             "contextName": "学生本人", "orgName": "软件学院·软件2401班",
             "dataScope": "SELF", "scopeLabel": "本人", "studentCount": 1,
             "todoCount": 2, "riskCount": 0, "enabled": True},
        ],
    },
    "u_admin_001": {
        "userId": "u_admin_001",
        "loginName": "admin",
        "realName": "教务处·赵敏",
        "userType": "ADMIN",
        "avatarFileId": None,
        "phoneMasked": "137****3311",
        "contexts": [
            {"contextId": "ctx_college_admin", "contextType": "COLLEGE_ADMIN",
             "contextName": "软件学院管理员", "orgName": "软件学院",
             "dataScope": "COLLEGE", "scopeLabel": "本学院全体学生",
             "studentCount": 1260, "todoCount": 12, "riskCount": 9, "enabled": True},
            {"contextId": "ctx_school_admin", "contextType": "SCHOOL_ADMIN",
             "contextName": "校级管理员", "orgName": "示范职院",
             "dataScope": "SCHOOL", "scopeLabel": "全校学生",
             "studentCount": 9800, "todoCount": 30, "riskCount": 41, "enabled": True},
        ],
    },
}

_LOGIN_INDEX = {u["loginName"]: uid for uid, u in DEMO_USERS.items()}
_USERTYPE_INDEX = {"TEACHER": "u_teacher_001", "STUDENT": "u_student_001", "ADMIN": "u_admin_001"}

# ── BACKEND-OVERNIGHT 追加：任务规定的 8 个演示账号（单一身份，便于联调）──
def _mk_user(uid, login, name, utype, ctx_type, ctx_name, org, scope, scope_label, n_stu=0):
    return {
        "userId": uid, "loginName": login, "realName": name, "userType": utype,
        "avatarFileId": None, "phoneMasked": "1**********",
        "contexts": [{
            "contextId": f"ctx_{login}", "contextType": ctx_type, "contextName": ctx_name,
            "orgName": org, "dataScope": scope, "scopeLabel": scope_label,
            "studentCount": n_stu, "todoCount": 3, "riskCount": 1, "enabled": True,
        }],
    }

DEMO_USERS.update({
    "u_student01": {**_mk_user("u_student01", "student01", "张一鸣", "STUDENT", "STUDENT", "学生本人", "软件学院·软件2401班", "SELF", "本人", 1),
                    "studentNo": "2023100001"},
    "u_counselor01": _mk_user("u_counselor01", "counselor01", "王莉", "TEACHER", "COUNSELOR", "辅导员", "软件学院", "COUNSELOR_CLASSES", "本人所带班级学生", 486),
    "u_teacher01": _mk_user("u_teacher01", "teacher01", "李明", "TEACHER", "GD_MENTOR", "指导教师", "软件学院", "GD_STUDENTS", "本人指导学生", 28),
    "u_employment01": _mk_user("u_employment01", "employment01", "刘芳", "TEACHER", "EMPLOYMENT_TEACHER", "就业老师", "就业指导中心", "SCHOOL", "应届毕业生", 2641),
    "u_academic01": _mk_user("u_academic01", "academic01", "赵敏", "TEACHER", "ACADEMIC_TEACHER", "教务老师", "教务处", "SCHOOL", "全校教学过程", 9800),
    "u_college_admin01": _mk_user("u_college_admin01", "college_admin01", "张晓明", "ADMIN", "COLLEGE_ADMIN", "学院管理员", "软件学院", "COLLEGE", "本学院全体学生", 1260),
    "u_school_admin01": _mk_user("u_school_admin01", "school_admin01", "陈校", "ADMIN", "SCHOOL_ADMIN", "学校管理员", "示范职院", "SCHOOL", "全校学生", 9800),
    "u_platform_admin01": _mk_user("u_platform_admin01", "platform_admin01", "平台运营", "PLATFORM_OP", "PLATFORM_OP", "平台运营人员", "平台运营中心", "PLATFORM", "全平台租户（不含学生敏感明文）", 0),
})
_LOGIN_INDEX.update({u["loginName"]: uid for uid, u in DEMO_USERS.items()})



def _find_user(login_name: str, user_type: str) -> Optional[dict]:
    uid = _LOGIN_INDEX.get(login_name) or _USERTYPE_INDEX.get(user_type)
    return DEMO_USERS.get(uid) if uid else None


def _context_of(user: dict, context_id: str) -> Optional[dict]:
    return next((c for c in user["contexts"] if c["contextId"] == context_id), None)


def _resolve_tenant_claims(tenant_code: str) -> dict:
    """按租户码解析令牌租户声明；未知/缺省一律绑定默认租户，令牌带 tenantId
    后中间件以令牌为准，X-Tenant 头无法再切换已登录用户的数据租户。"""
    from app.core.config import settings
    from app.core.tenant_context import get_mock_tenant
    t = get_mock_tenant((tenant_code or "").strip()) or get_mock_tenant(settings.DEFAULT_TENANT_CODE)
    return {"tid": t["tenantCode"], "tenantId": t["tenantId"], "tenantName": t["tenantName"]}


def login(tenant_code: str, login_name: str, user_type: str, client_type: str) -> dict:
    user = _find_user(login_name, user_type)
    if not user:
        raise not_found("用户不存在（mock 支持 student01/counselor01/teacher01/employment01/academic01/college_admin01/school_admin01/platform_admin01 及 20230101/20230999/admin）")

    contexts = user["contexts"]
    active = contexts[0]
    tclaims = _resolve_tenant_claims(tenant_code)
    claims = {
        "userId": user["userId"], "realName": user["realName"], "userType": user["userType"],
        **tclaims, "activeContextId": active["contextId"],
        "currentRoleCode": active["contextType"], "clientType": client_type,
    }
    if user.get("studentNo"):
        claims["studentNo"] = user["studentNo"]
    token = create_access_token(claims)
    from app.core.token_store import issue_refresh
    refresh_token = issue_refresh(dict(claims))
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "refreshToken": refresh_token,
        "expiresIn": 7200,
        # ── BACKEND-OVERNIGHT 任务要求的扁平字段（与 user/contexts 并存）──
        "userId": user["userId"],
        "username": user["loginName"],
        "displayName": user["realName"],
        "tenantId": tclaims["tenantId"],
        "tenantName": tclaims["tenantName"],
        "currentRole": {"roleCode": active["contextType"], "roleName": active["contextName"],
                        "dataScope": active["dataScope"], "scopeLabel": active.get("scopeLabel", "")},
        "roles": [{"roleCode": c["contextType"], "roleName": c["contextName"]} for c in contexts],
        "dataScope": {"scope": active["dataScope"], "scopeLabel": active.get("scopeLabel", "")},
        "permissionActions": {"viewList": True, "export": active["contextType"] != "PLATFORM_OP",
                              "viewSensitive": False},
        "user": {
            "userId": user["userId"], "realName": user["realName"],
            "userType": user["userType"], "mustChangePassword": False,
        },
        "contexts": [_public_context(c) for c in contexts],
        "activeContextId": active["contextId"],
    }


def _public_context(c: dict) -> dict:
    return {
        "contextId": c["contextId"], "contextType": c["contextType"],
        "contextName": c["contextName"], "orgName": c["orgName"],
        "dataScope": c["dataScope"], "todoCount": c["todoCount"],
        "riskCount": c["riskCount"], "enabled": c["enabled"],
    }


def get_me(user_ctx: dict) -> dict:
    user = DEMO_USERS.get(user_ctx.get("userId"))
    if not user:
        raise not_found("用户不存在或令牌已失效")
    active_id = user_ctx.get("activeContextId") or user["contexts"][0]["contextId"]
    active = _context_of(user, active_id) or user["contexts"][0]
    return {
        "userId": user["userId"], "realName": user["realName"], "userType": user["userType"],
        "avatarFileId": user.get("avatarFileId"), "phoneMasked": user.get("phoneMasked"),
        "activeContextId": active["contextId"],
        "currentRole": {"contextType": active["contextType"], "contextName": active["contextName"],
                        "dataScope": active["dataScope"]},
        "contexts": [_public_context(c) for c in user["contexts"]],
    }


def switch_role(user_ctx: dict, context_id: str, client_type: str) -> dict:
    user = DEMO_USERS.get(user_ctx.get("userId"))
    if not user:
        raise not_found("用户不存在或令牌已失效")
    target = _context_of(user, context_id)
    if not target:
        raise AppException("ROLE_NOT_FOUND", "身份不存在或不属于当前用户")
    if not target["enabled"]:
        raise AppException("ROLE_NOT_FOUND", "该身份已禁用")

    sclaims = {
        "userId": user["userId"], "realName": user["realName"], "userType": user["userType"],
        **_resolve_tenant_claims(user_ctx.get("tenantCode") or ""),
        "activeContextId": target["contextId"],
        "currentRoleCode": target["contextType"], "clientType": client_type,
    }
    if user.get("studentNo"):
        sclaims["studentNo"] = user["studentNo"]
    token = create_access_token(sclaims)
    return {
        "accessToken": token,
        "activeContextId": target["contextId"],
        "contextType": target["contextType"],
        "contextName": target["contextName"],
        "dataScope": target["dataScope"],
        "menusChanged": True,
    }


def get_active_context(user_ctx: dict) -> dict:
    """取当前用户激活的身份（数据范围/菜单/仪表盘据此裁剪）。"""
    user = DEMO_USERS.get(user_ctx.get("userId"))
    if not user:
        raise not_found("用户不存在或令牌已失效")
    active_id = user_ctx.get("activeContextId") or user["contexts"][0]["contextId"]
    return _context_of(user, active_id) or user["contexts"][0]
