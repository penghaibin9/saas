"""组织目录（学院→专业→班级）公共只读接口。

为什么单独开一个：选人（实习批次、毕设批次、评奖名单）需要一棵按"我能管到谁"
裁剪过的组织树，但现有两个组织树接口的权限口径都对不上——
`/system/org-tree` 要 `systemAdmin.org.view`，教务 `/orgs/tree` 要教务权限，
而选人的是实习管理员、学院管理员、辅导员。各业务域各写一份必然口径分裂，
所以收敛成一个公共端点，谁都用它。

安全口径（与学生选择器完全一致，避免出现"选择器看不到、组织树却看得到"）：

- 学生 / 家长身份直接拒绝：组织结构不是给他们看的；
- 其余身份按 `student_directory_scope` 裁剪：全校角色看全部，
  学院/班级范围只看范围内的班级，没配范围的一律空树（fail-closed），不回退全校；
- 只回组织名称与人数，不含任何学生个人信息。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.permissions import get_current_user
from app.core.response import success
from app.db.session import get_sessionmaker

router = APIRouter(prefix="/directory", tags=["组织目录"])

# 学生端与家长端不给组织结构：他们只需要看到自己，给整棵树属于越权暴露
_DENY_USER_TYPES = {"STUDENT", "PARENT", "GUARDIAN"}


def _reject_student_side(user: dict) -> None:
    from app.core.exceptions import no_permission
    utype = str((user or {}).get("userType") or "").upper()
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if utype in _DENY_USER_TYPES or role in _DENY_USER_TYPES:
        raise no_permission("学生/家长身份不可查看组织结构")


def _visible_class_ids(user: dict):
    """None = 不限（全校角色）；set() = 一个都看不到；否则为可见班级 id 集合。"""
    from app.core.affairs_security import student_directory_scope
    class_ids, student_ids = student_directory_scope(user)
    if class_ids is None and student_ids is None:
        return None
    if class_ids:
        return {int(i) for i in class_ids}
    if student_ids:
        # 只按学生授权的角色（如心理老师）：由这些学生反推所在班级
        from app.models import StudentProfile
        db = get_sessionmaker()()
        try:
            rows = db.scalars(select(StudentProfile.class_id).where(
                StudentProfile.tenant_id == int(current_tenant_id() or 0),
                StudentProfile.id.in_([int(i) for i in student_ids]),
                StudentProfile.is_deleted.is_(False))).all()
            return {int(c) for c in rows if c}
        finally:
            db.close()
    return set()


@router.get("/org-tree", summary="组织树（学院→专业→班级，按本人数据范围裁剪）")
def org_tree(user=Depends(get_current_user)):
    """直接返回 AppOrgCascader 可用的 {value,label,children} 结构。

    只保留"里面有可见班级"的专业与学院——否则学院管理员会看到一堆点开是空的外院节点。
    """
    from app.models import College, Major, SchoolClass, StudentProfile

    _reject_student_side(user)
    tenant_id = int(current_tenant_id() or 0)
    visible = _visible_class_ids(user)
    if visible is not None and not visible:
        return success({"tree": [], "scopeLimited": True})

    db = get_sessionmaker()()
    try:
        cls_conds = [SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False)]
        if visible is not None:
            cls_conds.append(SchoolClass.id.in_(list(visible)))
        classes = db.scalars(select(SchoolClass).where(*cls_conds)
                             .order_by(SchoolClass.grade.desc(), SchoolClass.class_name)).all()
        if not classes:
            return success({"tree": [], "scopeLimited": visible is not None})

        counts = dict(db.execute(
            select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_([c.id for c in classes]))
            .group_by(StudentProfile.class_id)).all())

        major_ids = {c.major_id for c in classes if c.major_id}
        majors = db.scalars(select(Major).where(
            Major.tenant_id == tenant_id, Major.id.in_(list(major_ids) or [0]))).all() if major_ids else []
        college_ids = {m.college_id for m in majors if m.college_id}
        colleges = db.scalars(select(College).where(
            College.tenant_id == tenant_id, College.id.in_(list(college_ids) or [0]))
            .order_by(College.sort_order, College.college_name)).all() if college_ids else []

        cls_by_major: dict[int, list] = {}
        for c in classes:
            cls_by_major.setdefault(int(c.major_id or 0), []).append({
                "value": str(c.id), "label": c.class_name, "grade": c.grade or "",
                "studentCount": int(counts.get(c.id, 0)),
                "classStatus": c.class_status, "children": []})

        maj_by_college: dict[int, list] = {}
        for m in majors:
            children = cls_by_major.get(int(m.id), [])
            if not children:
                continue
            maj_by_college.setdefault(int(m.college_id or 0), []).append({
                "value": str(m.id), "label": m.major_name, "children": children})

        tree = []
        for col in colleges:
            children = maj_by_college.get(int(col.id), [])
            if not children:
                continue
            tree.append({"value": str(col.id), "label": col.college_name, "children": children})

        # 组织链不完整的班级（专业或学院被删/未挂）单独归一档，否则页面上直接消失、
        # 用户会以为是权限问题；这里显式暴露，便于教学秘书去补组织关系。
        orphan = [row for mid, rows in cls_by_major.items() if not mid or mid not in
                  {int(m.id) for m in majors} for row in rows]
        if orphan:
            tree.append({"value": "__ORPHAN__", "label": "未挂专业的班级", "children":
                         [{"value": "__ORPHAN_MAJOR__", "label": "待补组织关系",
                           "children": orphan}]})

        return success({"tree": tree, "scopeLimited": visible is not None})
    finally:
        db.close()


@router.get("/teachers", summary="教职工目录（供辅导员/导师/责任人等选择器使用）")
def teachers(keyword: str | None = None, roleCode: str | None = None,
             limit: int = 50, user=Depends(get_current_user)):
    """选人之外的另一半：很多页面要选"某位老师"，此前只能让用户手填用户 ID。

    只回姓名与登录名，不回手机号/邮箱等联系方式——选择器不需要，回了就是多余暴露。
    """
    from app.models import Role, User, UserRole

    _reject_student_side(user)
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        conds = [User.tenant_id == tenant_id, User.is_deleted.is_(False),
                 User.status == "ACTIVE", User.user_type != "STUDENT"]
        kw = (keyword or "").strip()
        if kw:
            conds.append(User.real_name.contains(kw) | User.login_name.contains(kw))
        if roleCode:
            sub = select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
                Role.tenant_id == tenant_id, Role.role_code == roleCode,
                UserRole.is_deleted.is_(False))
            conds.append(User.id.in_(sub))
        rows = db.scalars(select(User).where(*conds)
                          .order_by(User.real_name).limit(max(1, min(int(limit or 50), 200)))).all()
        return success({"items": [{"value": str(u.id), "label": u.real_name or u.login_name,
                                   "loginName": u.login_name or "",
                                   "userType": u.user_type or ""} for u in rows]})
    finally:
        db.close()


@router.get("/grades", summary="年级列表（按本人数据范围裁剪）")
def grades(user=Depends(get_current_user)):
    """年级没有独立实体表，是主档上的字符串；这里给去重后的可选项，供普通下拉使用。"""
    from app.models import StudentProfile

    _reject_student_side(user)
    tenant_id = int(current_tenant_id() or 0)
    visible = _visible_class_ids(user)
    if visible is not None and not visible:
        return success({"items": []})

    db = get_sessionmaker()()
    try:
        conds = [StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False),
                 StudentProfile.grade.is_not(None)]
        if visible is not None:
            conds.append(StudentProfile.class_id.in_(list(visible)))
        rows = db.execute(select(StudentProfile.grade, func.count(StudentProfile.id))
                          .where(*conds).group_by(StudentProfile.grade)).all()
        items = [{"value": g, "label": g, "studentCount": int(n)}
                 for g, n in rows if str(g or "").strip()]
        items.sort(key=lambda x: x["value"], reverse=True)
        return success({"items": items})
    finally:
        db.close()
