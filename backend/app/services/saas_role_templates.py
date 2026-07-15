"""SaaS 内置角色模板目录。

学校只能从目录选择系统角色；角色编码、默认范围和适用账号类型由平台版本控制，
避免实施人员在每所学校临时造角色。自定义角色走独立流程，不允许由导入文件隐式创建。
"""
from __future__ import annotations

import re

from app.core.exceptions import AppException

ROLE_TEMPLATE_VERSION = "2026.07.v1"


def _role(code: str, name: str, category: str, scope: str,
          *, teacher: bool = True, aliases: tuple[str, ...] = ()) -> dict:
    return {
        "roleCode": code, "roleName": name, "category": category,
        "defaultScope": scope, "teacherAssignable": teacher,
        "aliases": aliases,
    }


BUILTIN_ROLE_TEMPLATES = (
    _role("SCHOOL_ADMIN", "学校管理员", "SYSTEM", "SCHOOL", teacher=False,
          aliases=("校级管理员", "学校超级管理员")),
    _role("SYS_ADMIN", "系统管理员", "SYSTEM", "SCHOOL", teacher=False,
          aliases=("信息中心管理员",)),
    _role("SECURITY_AUDITOR", "安全审计员", "SYSTEM", "SCHOOL", teacher=False,
          aliases=("审计员",)),
    _role("LEADER", "校院领导", "MANAGEMENT", "SCHOOL", aliases=("校领导", "院领导")),
    _role("COLLEGE_ADMIN", "学院管理员", "MANAGEMENT", "COLLEGE", aliases=("学院负责人", "学院教务员")),
    _role("ACADEMIC_ADMIN", "教务处管理员", "ACADEMIC", "SCHOOL", aliases=("教务管理员",)),
    _role("ACADEMIC_TEACHER", "任课教师", "ACADEMIC", "ASSIGNED",
          aliases=("课程教师", "教务老师", "ACADEMIC", "专业课教师", "公共课教师", "兼职教师")),
    _role("STUDENT_AFFAIRS_ADMIN", "学工处管理员", "STUDENT_AFFAIRS", "SCHOOL", aliases=("学工管理员",)),
    _role("STUDENT_AFFAIRS", "学工老师", "STUDENT_AFFAIRS", "COLLEGE", aliases=("学工干事",)),
    _role("COUNSELOR", "辅导员", "STUDENT_AFFAIRS", "COUNSELOR_CLASSES", aliases=("班主任",)),
    _role("PSYCHOLOGY_TEACHER", "心理老师", "STUDENT_AFFAIRS", "PSY_STUDENT", aliases=("心理教师",)),
    _role("FUNDING_TEACHER", "资助老师", "STUDENT_AFFAIRS", "FUNDING_BIZ", aliases=("资助管理员",)),
    _role("DORM_MANAGER", "宿管老师", "STUDENT_AFFAIRS", "DORM_BUILDING", aliases=("宿舍管理员",)),
    _role("YOUTH_LEAGUE", "团委老师", "STUDENT_AFFAIRS", "SCHOOL", aliases=("团委",)),
    _role("ORG_PERSONNEL", "组织人事", "MANAGEMENT", "DEPARTMENT", aliases=("人事老师",)),
    _role("GRADUATION_ADMIN", "毕设管理员", "GRADUATION", "SCHOOL", aliases=("毕业设计管理员",)),
    _role("GD_COLLEGE_ADMIN", "学院毕设管理员", "GRADUATION", "COLLEGE"),
    _role("GD_MAJOR_ADMIN", "专业毕设负责人", "GRADUATION", "MAJOR", aliases=("毕设专业负责人",)),
    _role("GD_MENTOR", "毕设指导教师", "GRADUATION", "GD_STUDENTS", aliases=("毕业设计导师", "毕设导师")),
    _role("GD_REVIEWER", "毕设评阅教师", "GRADUATION", "ASSIGNED", aliases=("毕设评阅人",)),
    _role("GD_DEFENSE_SECRETARY", "答辩秘书", "GRADUATION", "ASSIGNED"),
    _role("GD_DEFENSE_EXPERT", "答辩专家", "GRADUATION", "ASSIGNED"),
    _role("INTERN_MENTOR", "实习指导教师", "INTERNSHIP", "INTERN_STUDENTS", aliases=("实习导师",)),
    _role("EMPLOYMENT_TEACHER", "就业老师", "EMPLOYMENT", "ASSIGNED", aliases=("就业管理员",)),
    _role("STAFF", "普通教职工", "SYSTEM", "CUSTOM", teacher=False),
    _role("STUDENT", "学生", "STUDENT", "SELF", teacher=False),
)

ROLE_TEMPLATE_BY_CODE = {r["roleCode"]: r for r in BUILTIN_ROLE_TEMPLATES}
_ALIAS_TO_CODE = {
    alias.strip().upper(): role["roleCode"]
    for role in BUILTIN_ROLE_TEMPLATES
    for alias in (role["roleCode"], role["roleName"], *role["aliases"])
}


def role_catalog(*, teacher_only: bool = False) -> dict:
    items = [dict(r) for r in BUILTIN_ROLE_TEMPLATES
             if not teacher_only or r["teacherAssignable"]]
    return {"templateVersion": ROLE_TEMPLATE_VERSION, "items": items}


def resolve_role_code(value: object, *, teacher_only: bool = True) -> str:
    raw = str(value or "").strip()
    code = _ALIAS_TO_CODE.get(raw.upper())
    role = ROLE_TEMPLATE_BY_CODE.get(code or "")
    if role is None or (teacher_only and not role["teacherAssignable"]):
        raise AppException("VALIDATION_ERROR", f"不支持的预设角色：{raw or '空'}")
    return role["roleCode"]


def role_codes_from_row(row: dict, *, teacher_only: bool = True) -> list[str]:
    raw = row.get("roleCodes")
    if raw in (None, "", []):
        raw = row.get("roleCode") or row.get("position") or row.get("roleName")
    values = raw if isinstance(raw, (list, tuple, set)) else re.split(r"[,，;；|]+", str(raw or ""))
    codes: list[str] = []
    for value in values:
        if not str(value or "").strip():
            continue
        code = resolve_role_code(value, teacher_only=teacher_only)
        if code not in codes:
            codes.append(code)
    if not codes:
        raise AppException("VALIDATION_ERROR", "至少选择一个预设角色")
    return codes
