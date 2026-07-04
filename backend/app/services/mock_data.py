"""
mock 数据源（骨架阶段唯一数据来源，不连库）
────────────────────────────────────────────────────────────
结构 100% 对齐 docs/api 冻结契约（01 认证租户、04 待办消息）与 DB 冻结册字段命名。
将来接库：本文件整体被 services/*(SQLAlchemy) 替换，路由层不动。
"""
from __future__ import annotations

# ── 用户（mock 登录：任意非空密码可登录）──
# userType: STUDENT / TEACHER / ADMIN
MOCK_USERS: dict[str, dict] = {
    "student01": {
        "userId": "2000000000000000101",
        "loginName": "student01",
        "realName": "陈晓",
        "userType": "STUDENT",
        "phoneMasked": "138****1234",
        "avatarFileId": None,
        "mustChangePassword": False,
        "contexts": [
            {
                "contextId": "ctx-stu-101",
                "contextType": "STUDENT",
                "contextName": "软件技术2401班 学生",
                "orgName": "信息工程学院",
                "dataScope": "SELF",
                "todoCount": 3,
                "riskCount": 0,
                "enabled": True,
            }
        ],
    },
    "teacher01": {
        "userId": "2000000000000000201",
        "loginName": "teacher01",
        "realName": "李涛",
        "userType": "TEACHER",
        "phoneMasked": "139****5678",
        "avatarFileId": None,
        "mustChangePassword": False,
        "contexts": [
            {
                "contextId": "ctx-t-201",
                "contextType": "COUNSELOR",
                "contextName": "软件2401/2402 辅导员",
                "orgName": "信息工程学院",
                "dataScope": "COUNSELOR_CLASSES",
                "todoCount": 8,
                "riskCount": 2,
                "enabled": True,
            },
            {
                "contextId": "ctx-t-202",
                "contextType": "GD_ADVISOR",
                "contextName": "毕业设计指导教师",
                "orgName": "信息工程学院",
                "dataScope": "GD_STUDENTS",
                "todoCount": 5,
                "riskCount": 1,
                "enabled": True,
            },
            {
                "contextId": "ctx-t-203",
                "contextType": "INTERN_ADVISOR",
                "contextName": "岗位实习指导教师",
                "orgName": "信息工程学院",
                "dataScope": "INTERN_STUDENTS",
                "todoCount": 4,
                "riskCount": 1,
                "enabled": True,
            },
        ],
    },
    "admin01": {
        "userId": "2000000000000000301",
        "loginName": "admin01",
        "realName": "王芳",
        "userType": "ADMIN",
        "phoneMasked": "137****9012",
        "avatarFileId": None,
        "mustChangePassword": False,
        "contexts": [
            {
                "contextId": "ctx-a-301",
                "contextType": "SCHOOL_ADMIN",
                "contextName": "校级管理员",
                "orgName": "示范职业技术学院",
                "dataScope": "SCHOOL",
                "todoCount": 12,
                "riskCount": 3,
                "enabled": True,
            }
        ],
    },
}

# 服务端记忆的「当前身份」（mock 期用内存代替 t_user_active_context）
ACTIVE_CONTEXT: dict[str, str] = {}


def get_user_by_login(login_name: str) -> dict | None:
    return MOCK_USERS.get(login_name)


def get_user_by_id(user_id: str) -> dict | None:
    for u in MOCK_USERS.values():
        if u["userId"] == user_id:
            return u
    return None


def get_context(user: dict, context_id: str) -> dict | None:
    for c in user["contexts"]:
        if c["contextId"] == context_id and c["enabled"]:
            return c
    return None


def get_active_context(user: dict) -> dict:
    ctx_id = ACTIVE_CONTEXT.get(user["userId"]) or user["contexts"][0]["contextId"]
    return get_context(user, ctx_id) or user["contexts"][0]


# ── 租户品牌（tenantBrandConfig 唯一来源，对齐契约 1.5）──
MOCK_BRAND: dict[str, dict] = {
    "demo": {
        "tenantId": "1000000000000000001",
        "platformName": "职校学生全生命周期平台",
        "platformSubtitle": "学生成长一体化管理",
        "browserTitle": "示范职业技术学院 · 学生全生命周期平台",
        "logoLightUrl": "/static/brand/demo/logo-light.png",
        "logoDarkUrl": "/static/brand/demo/logo-dark.png",
        "faviconUrl": "/static/brand/demo/favicon.ico",
        "badgeUrl": "/static/brand/demo/badge.png",
        "loginBgUrl": "/static/brand/demo/login-bg.jpg",
        "campusLineUrl": "/static/brand/demo/campus-line.svg",
        "primaryColor": "#2563EB",
        "secondaryColor": "#0EA5E9",
        "defaultTheme": "academy_blue",
        "motto": "厚德 精技 笃行",
        "watermarkText": "示范职业技术学院",
    },
    "hnsh": {
        "tenantId": "1000000000000000002",
        "platformName": "华南商贸学生成长平台",
        "platformSubtitle": "全生命周期管理",
        "browserTitle": "华南商贸职业学院 · 学生成长平台",
        "logoLightUrl": "/static/brand/hnsh/logo-light.png",
        "logoDarkUrl": "/static/brand/hnsh/logo-dark.png",
        "faviconUrl": "/static/brand/hnsh/favicon.ico",
        "badgeUrl": "/static/brand/hnsh/badge.png",
        "loginBgUrl": "/static/brand/hnsh/login-bg.jpg",
        "campusLineUrl": "/static/brand/hnsh/campus-line.svg",
        "primaryColor": "#059669",
        "secondaryColor": "#10B981",
        "defaultTheme": "jade_green",
        "motto": "商行天下 贸通四海",
        "watermarkText": "华南商贸职业学院",
    },
}

# ── 数据范围标签（契约 §八：12 种枚举的展示层）──
DATA_SCOPE_META: dict[str, dict] = {
    "SELF": {"scopeLabel": "本人数据", "studentCount": None},
    "CLASS": {"scopeLabel": "本班学生", "studentCount": 48},
    "COUNSELOR_CLASSES": {"scopeLabel": "辅导员带班学生", "studentCount": 96},
    "GD_STUDENTS": {"scopeLabel": "本人指导毕设学生", "studentCount": 12},
    "INTERN_STUDENTS": {"scopeLabel": "本人指导实习学生", "studentCount": 18},
    "ENTERPRISE_AUTH_STUDENTS": {"scopeLabel": "企业授权实习学生", "studentCount": 9},
    "MAJOR": {"scopeLabel": "本专业学生", "studentCount": 320},
    "COLLEGE": {"scopeLabel": "本学院学生", "studentCount": 1450},
    "SCHOOL": {"scopeLabel": "全校学生", "studentCount": 4200},
    "DEPARTMENT": {"scopeLabel": "本部门数据", "studentCount": None},
    "TEMP_AUTH": {"scopeLabel": "临时授权范围", "studentCount": None},
    "CUSTOM": {"scopeLabel": "自定义范围", "studentCount": None},
}


def _menu(code: str, title: str, path: str, icon: str, module: str,
          children: list | None = None, readonly: bool = False) -> dict:
    return {"menuCode": code, "title": title, "path": path, "icon": icon,
            "moduleCode": module, "readonly": readonly, "children": children or []}


# ── 菜单树（按 contextType 过滤 = 已购模块 ∩ 角色权限，契约 1.10）──
MOCK_MENUS: dict[str, list[dict]] = {
    "STUDENT": [
        _menu("stu.home", "首页", "/home", "home", "BASE"),
        _menu("stu.profile", "我的档案", "/profile", "user", "STUDENT_PROFILE"),
        _menu("stu.onboarding", "迎新报到", "/onboarding", "flag", "ONBOARDING"),
        _menu("stu.services", "在校服务", "/services", "grid", "CAMPUS_SERVICE"),
        _menu("stu.academic", "学业进度", "/academic", "book", "ACADEMIC"),
        _menu("stu.internship", "岗位实习", "/internship", "briefcase", "INTERNSHIP"),
        _menu("stu.gd", "毕业设计", "/graduation-design", "edit", "GRAD_DESIGN"),
        _menu("stu.employment", "就业去向", "/employment", "send", "EMPLOYMENT"),
        _menu("stu.messages", "消息中心", "/messages", "bell", "BASE"),
    ],
    "COUNSELOR": [
        _menu("csl.workbench", "工作台", "/workbench", "dashboard", "BASE"),
        _menu("csl.todos", "今日待办", "/todos", "check-square", "TODO_CENTER"),
        _menu("csl.approvals", "审批处理", "/approvals", "audit", "TODO_CENTER"),
        _menu("csl.risk", "风险学生", "/risk-students", "warning", "STUDENT_PROFILE"),
        _menu("csl.students", "学生管理", "/students", "team", "STUDENT_PROFILE",
              children=[_menu("csl.students.list", "学生列表", "/students/list", "list", "STUDENT_PROFILE"),
                        _menu("csl.students.360", "学生360", "/students/360", "radar", "STUDENT_PROFILE")]),
        _menu("csl.messages", "消息中心", "/messages", "bell", "BASE"),
    ],
    "GD_ADVISOR": [
        _menu("gd.workbench", "毕设工作台", "/gd/workbench", "dashboard", "GRAD_DESIGN"),
        _menu("gd.topics", "选题审核", "/gd/topics", "file-search", "GRAD_DESIGN"),
        _menu("gd.review", "过程批阅", "/gd/review", "highlight", "GRAD_DESIGN"),
        _menu("gd.defense", "答辩安排", "/gd/defense", "schedule", "GRAD_DESIGN"),
        _menu("gd.messages", "消息中心", "/messages", "bell", "BASE"),
    ],
    "INTERN_ADVISOR": [
        _menu("itn.workbench", "实习工作台", "/intern/workbench", "dashboard", "INTERNSHIP"),
        _menu("itn.reports", "周报批阅", "/intern/reports", "file-done", "INTERNSHIP"),
        _menu("itn.visits", "巡访记录", "/intern/visits", "environment", "INTERNSHIP"),
        _menu("itn.leaves", "请假审批", "/intern/leaves", "carry-out", "INTERNSHIP"),
        _menu("itn.messages", "消息中心", "/messages", "bell", "BASE"),
    ],
    "SCHOOL_ADMIN": [
        _menu("adm.datacenter", "数据中心", "/data-center", "bar-chart", "DATA_CENTER"),
        _menu("adm.students", "学生主档", "/students", "team", "STUDENT_PROFILE"),
        _menu("adm.org", "组织机构", "/org", "cluster", "BASE"),
        _menu("adm.rbac", "权限管理", "/rbac", "safety", "BASE"),
        _menu("adm.modules", "模块授权", "/modules", "appstore", "BASE"),
        _menu("adm.audit", "审计日志", "/audit-logs", "file-protect", "BASE"),
        _menu("adm.transfer", "导入导出", "/transfer", "swap", "STUDENT_PROFILE"),
        _menu("adm.brand", "品牌配置", "/brand", "bg-colors", "BASE"),
    ],
}

# ── 按钮权限（契约 1.11：按页面返回权限码集合）──
MOCK_BUTTONS: dict[str, dict[str, list[str]]] = {
    "studentList": {
        "COUNSELOR": ["student.view", "student.remark"],
        "SCHOOL_ADMIN": ["student.view", "student.create", "student.import",
                         "student.export", "student.field.view_full"],
    },
    "approvals": {
        "COUNSELOR": ["approval.approve", "approval.return", "approval.reject"],
        "GD_ADVISOR": ["approval.approve", "approval.return"],
        "INTERN_ADVISOR": ["approval.approve", "approval.return", "approval.reject"],
        "SCHOOL_ADMIN": ["approval.approve", "approval.return", "approval.reject", "approval.transfer"],
    },
}

# ── 模块授权（契约 1.12）──
MOCK_MODULES: list[dict] = [
    {"moduleCode": "BASE", "status": "ACTIVE", "expireAt": None, "features": {}},
    {"moduleCode": "STUDENT_PROFILE", "status": "ACTIVE", "expireAt": "2027-08-31T00:00:00+08:00", "features": {"student360": True}},
    {"moduleCode": "ONBOARDING", "status": "TRIAL", "expireAt": "2026-09-30T00:00:00+08:00", "features": {}},
    {"moduleCode": "TODO_CENTER", "status": "ACTIVE", "expireAt": "2027-08-31T00:00:00+08:00", "features": {}},
    {"moduleCode": "INTERNSHIP", "status": "ACTIVE", "expireAt": "2027-08-31T00:00:00+08:00", "features": {"checkin": True}},
    {"moduleCode": "GRAD_DESIGN", "status": "EXPIRING", "expireAt": "2026-07-31T00:00:00+08:00", "features": {}},
    {"moduleCode": "EMPLOYMENT", "status": "EXPIRED_READONLY", "expireAt": "2026-06-30T00:00:00+08:00", "features": {}},
    {"moduleCode": "DATA_CENTER", "status": "ACTIVE", "expireAt": "2027-08-31T00:00:00+08:00", "features": {}},
]

# ── 待办（契约 04：t_unified_todo 占位）──
MOCK_TODOS: list[dict] = [
    {"todoId": "td-1001", "todoType": "APPROVAL", "title": "请假申请待审批：陈晓（3 天）",
     "bizType": "LEAVE", "bizId": "lv-2001", "priority": "HIGH", "status": "PENDING",
     "dueAt": "2026-07-05T18:00:00+08:00", "createdAt": "2026-07-03T09:20:00+08:00"},
    {"todoId": "td-1002", "todoType": "REVIEW", "title": "实习周报待批阅：第 14 周（5 份）",
     "bizType": "INTERN_REPORT", "bizId": "rp-3005", "priority": "NORMAL", "status": "PENDING",
     "dueAt": "2026-07-06T18:00:00+08:00", "createdAt": "2026-07-03T10:00:00+08:00"},
    {"todoId": "td-1003", "todoType": "RISK", "title": "风险预警：学生连续 3 天未打卡",
     "bizType": "INTERN_CHECKIN", "bizId": "ck-4102", "priority": "HIGH", "status": "PENDING",
     "dueAt": None, "createdAt": "2026-07-04T08:00:00+08:00"},
    {"todoId": "td-1004", "todoType": "SUBMIT", "title": "毕设中期检查材料待提交",
     "bizType": "GD_MIDTERM", "bizId": "gd-5201", "priority": "NORMAL", "status": "PENDING",
     "dueAt": "2026-07-10T23:59:59+08:00", "createdAt": "2026-07-01T09:00:00+08:00"},
    {"todoId": "td-1005", "todoType": "CONFIRM", "title": "实习三方协议待确认签署",
     "bizType": "AGREEMENT", "bizId": "ag-6001", "priority": "NORMAL", "status": "DONE",
     "dueAt": None, "createdAt": "2026-06-28T14:00:00+08:00"},
]

# ── 消息（契约 04：t_unified_message 占位）──
MOCK_MESSAGES: list[dict] = [
    {"messageId": "msg-9001", "msgType": "APPROVAL_RESULT", "title": "你的证明申请已通过",
     "summary": "在读证明已开具，可到综合服务中心领取。", "readStatus": "UNREAD",
     "actionUrl": "/services/apply/ap-1201", "createdAt": "2026-07-04T09:00:00+08:00"},
    {"messageId": "msg-9002", "msgType": "SYSTEM", "title": "系统维护通知",
     "summary": "7 月 6 日 00:00-02:00 平台例行维护。", "readStatus": "UNREAD",
     "actionUrl": None, "createdAt": "2026-07-03T18:30:00+08:00"},
    {"messageId": "msg-9003", "msgType": "TODO_REMIND", "title": "周报提交提醒",
     "summary": "第 14 周实习周报请于周日 24:00 前提交。", "readStatus": "READ",
     "actionUrl": "/internship/reports", "createdAt": "2026-07-02T08:00:00+08:00"},
]
