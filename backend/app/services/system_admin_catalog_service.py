"""学校侧系统管理：可配置权限目录树与通配展开。

供角色复制（禁止落库字面量 *）与角色权限配置页使用。
树节点 key 即后端 permissionCode，前端勾选后原样提交，禁止 UI 假 key 映射丢码。
"""
from __future__ import annotations

from app.core.permissions import ROLE_PERMISSIONS, has_permission

# 学校管理员可裁剪的显式权限目录（按业务中心分组；含菜单级 view 与操作级动作）。
# 通配角色复制时展开为这些具体码，避免 RolePermission 写入 "*"。
SCHOOL_PERMISSION_GROUPS: list[dict] = [
    {
        "key": "mod-systemAdmin",
        "label": "系统管理",
        "menus": [
            {"code": "systemAdmin.dashboard.view", "label": "系统概览", "actions": []},
            {"code": "systemAdmin.user.view", "label": "师生账号", "actions": [
                ("systemAdmin.user.manage", "停用/启用/重置密码"),
                ("systemAdmin.user.assign-role", "分配角色"),
                ("systemAdmin.user.import", "导入师生"),
                ("systemAdmin.user.export", "导出账号"),
                ("systemAdmin.user.exception.view", "账号异常查看"),
            ]},
            {"code": "systemAdmin.org.view", "label": "组织主数据", "actions": [
                ("systemAdmin.org.create", "新建组织"),
                ("systemAdmin.org.update", "编辑组织"),
                ("systemAdmin.org.manage", "停用组织"),
                ("systemAdmin.org.major.manage", "维护专业"),
                ("systemAdmin.org.class.manage", "维护班级"),
                ("systemAdmin.org.affiliation.manage", "岗位与归属"),
            ]},
            {"code": "systemAdmin.role.view", "label": "角色与权限", "actions": [
                ("systemAdmin.role.create", "新建/复制角色"),
                ("systemAdmin.role.config", "配置权限"),
            ]},
            {"code": "systemAdmin.scope.view", "label": "数据范围规则", "actions": [
                ("systemAdmin.scope.manage", "维护范围规则"),
            ]},
            {"code": "systemAdmin.config.view", "label": "学校配置", "actions": [
                ("systemAdmin.config.manage", "修改配置/品牌"),
                ("systemAdmin.security.policy.manage", "登录安全策略"),
                ("systemAdmin.config.feature.view", "模块授权查看"),
            ]},
            {"code": "systemAdmin.audit.view", "label": "安全与审计", "actions": [
                ("systemAdmin.audit.sensitive.view", "敏感与导入导出审计"),
            ]},
            {"code": "systemAdmin.implementation.view", "label": "实施与预设", "actions": [
                ("systemAdmin.implementation.configure", "开局配置"),
                ("systemAdmin.implementation.preset.view", "预设与国标"),
                ("systemAdmin.implementation.mapping.manage", "数据匹配"),
                ("systemAdmin.implementation.mapping.apply", "安装组织与角色"),
                ("systemAdmin.implementation.installed.view", "已安装配置"),
                ("systemAdmin.implementation.change.manage", "变更升级"),
                ("systemAdmin.implementation.check.run", "上线检查"),
                ("systemAdmin.implementation.accept", "验收封板"),
            ]},
            {"code": "systemAdmin.migration.view", "label": "老系统迁移", "actions": []},
            {"code": "systemAdmin.delegation.manage", "label": "临时授权", "actions": []},
            {"code": "systemAdmin.integration.manage", "label": "接口与凭证", "actions": [
                ("systemAdmin.integration.sync.view", "同步任务查看"),
            ]},
        ],
    },
    {
        "key": "mod-studentAffairs",
        "label": "学工中心",
        "menus": [
            {"code": "studentAffairs.student.view", "label": "学生档案", "actions": [
                ("studentAffairs.*", "学工全权（通配，仅复制学校管理员时展开为具体码）"),
            ]},
        ],
    },
    {
        "key": "mod-academicAffairs",
        "label": "教务中心",
        "menus": [
            {"code": "academicAffairs.course.view", "label": "课程与教学", "actions": [
                ("academicAffairs.*", "教务全权（通配占位，保存时展开）"),
            ]},
        ],
    },
    {
        "key": "mod-graduationDesign",
        "label": "毕业设计中心",
        "menus": [
            {"code": "graduationDesign.dashboard.view", "label": "毕设看板", "actions": [
                ("graduationDesign.*", "毕设全权（通配占位，保存时展开）"),
            ]},
        ],
    },
    {
        "key": "mod-internship",
        "label": "岗位实习中心",
        "menus": [
            {"code": "internship.dashboard.view", "label": "实习看板", "actions": [
                ("internship.student.view", "实习学生查看"),
                ("internship.application.view", "实习申请查看"),
                ("internship.risk.view", "风险查看"),
                ("internship.stats.view", "统计查看"),
                ("internship.archive.view", "归档查看"),
                ("internship.archive.prepare", "归档检查与提交"),
                ("internship.archive.execute", "普通归档"),
                ("internship.archive.force", "强制归档"),
                ("internship.archive.revoke", "撤销归档"),
                ("internship.archive.package", "归档包生成与导出"),
            ]},
        ],
    },
]


def _leaf_codes_from_groups() -> set[str]:
    codes: set[str] = set()
    for group in SCHOOL_PERMISSION_GROUPS:
        for menu in group["menus"]:
            code = menu["code"]
            if not code.endswith(".*"):
                codes.add(code)
            for action_code, _ in menu["actions"]:
                if not action_code.endswith(".*"):
                    codes.add(action_code)
    return codes


def collect_concrete_permission_codes() -> set[str]:
    """从内置角色表与学校目录收集可落库的具体 permissionCode（不含 * / 前缀通配）。"""
    codes = _leaf_codes_from_groups()
    for patterns in ROLE_PERMISSIONS.values():
        for p in patterns:
            if p == "*" or p.startswith("*.") or p.endswith(".*"):
                continue
            codes.add(p)
    return codes


def expand_permission_patterns(patterns: set[str] | list[str]) -> set[str]:
    """将 * / module.* / *.view 展开为具体码；无法展开的精确码原样保留。"""
    patterns = set(patterns or [])
    universe = collect_concrete_permission_codes()
    if "*" in patterns:
        return set(universe)
    out: set[str] = set()
    for p in patterns:
        if p.endswith(".*"):
            prefix = p[:-1]  # "a.b."
            out.update(c for c in universe if c.startswith(prefix) or c == p[:-2])
        elif p.startswith("*."):
            suffix = p[1:]  # ".view"
            out.update(c for c in universe if c.endswith(suffix))
        else:
            out.add(p)
    return out


def build_permission_tree(user: dict) -> list[dict]:
    """按当前操作者权限裁剪后的可配置树；节点 key = permissionCode。"""
    tree = []
    for group in SCHOOL_PERMISSION_GROUPS:
        menus = []
        for menu in group["menus"]:
            menu_code = menu["code"]
            if menu_code.endswith(".*"):
                continue
            if not has_permission(user, menu_code):
                continue
            actions = []
            for action_code, label in menu["actions"]:
                if action_code.endswith(".*"):
                    # 通配不直接勾选；展开为具体子码供勾选
                    for concrete in sorted(expand_permission_patterns({action_code})):
                        if concrete == menu_code:
                            continue
                        if has_permission(user, concrete):
                            actions.append({"key": concrete, "label": concrete.split(".")[-1],
                                            "type": "BUTTON", "permissionCode": concrete})
                elif has_permission(user, action_code):
                    actions.append({"key": action_code, "label": label, "type": "BUTTON",
                                    "permissionCode": action_code})
            menus.append({
                "key": menu_code, "label": menu["label"], "type": "MENU",
                "permissionCode": menu_code, "children": actions,
            })
        if menus:
            tree.append({"key": group["key"], "label": group["label"], "type": "MODULE", "children": menus})
    return tree


def visible_codes_from_tree(tree: list[dict]) -> set[str]:
    codes: set[str] = set()
    for mod in tree or []:
        for menu in mod.get("children") or []:
            codes.add(menu["key"])
            for btn in menu.get("children") or []:
                codes.add(btn["key"])
    return codes


def split_selection(permission_codes: list[str], tree: list[dict]) -> dict:
    menu_keys = set()
    button_keys = set()
    for mod in tree or []:
        for menu in mod.get("children") or []:
            menu_keys.add(menu["key"])
            for btn in menu.get("children") or []:
                button_keys.add(btn["key"])
    codes = [c for c in permission_codes or [] if c]
    return {
        "menuKeys": [c for c in codes if c in menu_keys],
        "buttonKeys": [c for c in codes if c in button_keys],
        "permissionCodes": codes,
    }
