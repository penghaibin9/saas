"""组织目录（学院→专业→班级）公共只读接口。

为什么单独开一个：选人（实习批次、毕设批次、评奖名单）需要一棵按"我能管到谁"
裁剪过的组织树，但现有两个组织树接口的权限口径都对不上——
`/system/org-tree` 要 `systemAdmin.org.view`，教务 `/orgs/tree` 要教务权限，
而选人的是实习管理员、学院管理员、辅导员。各业务域各写一份必然口径分裂，
所以收敛成一个公共端点，谁都用它。

组织树安全口径：

- 学生 / 家长身份直接拒绝：组织结构不是给他们看的；
- 其余身份按 `岗位实习统一数据范围` 裁剪：全校角色看全部，
  教师及组织范围仅看授权实习学生所在班级，没配范围的一律空树（fail-closed），不回退全校；
- 只回组织名称与人数，不含任何学生个人信息。

建档学生选择使用同校学生主档及稳定组织授权范围，包含尚未建实习档案的在读学生；
编号回显仍经过同一范围校验，仅返回编号、姓名和学号。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, or_

from app.core.context import current_tenant_id
from app.core.permissions import require_any_permission, require_module, require_staff
from app.core.response import success
from app.db.session import get_sessionmaker

router = APIRouter(prefix="/directory", tags=["组织目录"],
                   dependencies=[Depends(require_staff), Depends(require_module("internship"))])

# 学生端与家长端不给组织结构：他们只需要看到自己，给整棵树属于越权暴露
_DENY_USER_TYPES = {"STUDENT", "PARENT", "GUARDIAN"}


@router.get('/student-options', summary='本人管理范围内的学生主档选择')
def student_options(page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
                    keyword: str = Query('', max_length=100), ids: str | None = Query(None, max_length=1999),
                    user=Depends(require_any_permission('internship.student.manage', 'internship.batch.manage'))):
    from app.core.exceptions import AppException, no_permission
    from app.models import StudentProfile
    from app.services.mobile_teacher_service import _role
    from app.services.student_scope_resolver import DEFAULT_STAGES, DEFAULT_STUDENT_STATUSES
    from app.services.system_management import scoped_students
    _reject_student_side(user)
    if _role(user) == 'PLATFORM_SUPER_ADMIN':
        raise no_permission('平台身份不可查看学校学生目录')
    selected = None
    if ids is not None:
        raw = ids.split(',')
        if not 1 <= len(raw) <= 100 or any(not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**63 for value in raw):
            raise AppException('VALIDATION_ERROR', '学生编号格式错误或超过单次读取数量', http_status=422)
        selected = list(dict.fromkeys(map(int, raw)))
        page, pageSize = 1, len(selected)
    with get_sessionmaker()() as db:
        query = scoped_students(db, user).where(StudentProfile.status == 'ACTIVE',
            StudentProfile.current_stage.in_(DEFAULT_STAGES), StudentProfile.student_status.in_(DEFAULT_STUDENT_STATUSES))
        if selected is not None:
            query = query.where(StudentProfile.id.in_(selected))
        elif keyword:
            query = query.where(or_(StudentProfile.real_name.contains(keyword, autoescape=True),
                                     StudentProfile.student_no.contains(keyword, autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.scalars(query.order_by(StudentProfile.student_no, StudentProfile.id).offset((page-1)*pageSize).limit(pageSize)).all()
        return success({'items': [{'id': str(row.id), 'name': row.real_name, 'studentNo': row.student_no} for row in rows],
                        'total': total, 'page': page, 'pageSize': pageSize})


def _reject_student_side(user: dict) -> None:
    from app.core.exceptions import no_permission
    utype = str((user or {}).get("userType") or "").upper()
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if utype in _DENY_USER_TYPES or role in _DENY_USER_TYPES:
        raise no_permission("学生/家长身份不可查看组织结构")


def _visible_student_ids(user: dict):
    """Reuse internship SQL scope; None is only the existing school-admin scope."""
    from app.models import InternshipRecord
    from app.services.mobile_teacher_service import resolve_teacher_scope, _role
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.core.exceptions import no_permission
    _reject_student_side(user)
    if _role(user) == "PLATFORM_SUPER_ADMIN":
        raise no_permission("平台身份不可查看学校组织目录")
    scope = resolve_teacher_scope(user)
    if scope.get("mode") == "ADMIN_TENANT":
        return None
    if scope.get("mode") != "SCOPED":
        raise no_permission("组织目录数据范围不可用")
    query = select(InternshipRecord.student_id).where(
        InternshipRecord.tenant_id == int(current_tenant_id() or 0),
        InternshipRecord.is_deleted.is_(False))
    return apply_internship_record_scope(query, user, resolved_scope=scope).distinct()


@router.get("/org-tree", summary="组织树（学院→专业→班级，按本人数据范围裁剪）")
def org_tree(user=Depends(require_any_permission("internship.student.view", "internship.archive.view"))):
    """直接返回 AppOrgCascader 可用的 {value,label,children} 结构。

    只保留"里面有可见班级"的专业与学院——否则学院管理员会看到一堆点开是空的外院节点。
    """
    from app.models import College, Major, SchoolClass, StudentProfile

    _reject_student_side(user)
    tenant_id = int(current_tenant_id() or 0)
    visible = _visible_student_ids(user)

    db = get_sessionmaker()()
    try:
        cls_conds = [SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False)]
        if visible is not None:
            cls_conds.append(SchoolClass.id.in_(select(StudentProfile.class_id).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False),
                StudentProfile.id.in_(visible))))
        classes = db.scalars(select(SchoolClass).where(*cls_conds)
                             .order_by(SchoolClass.grade.desc(), SchoolClass.class_name)).all()
        if not classes:
            return success({"tree": [], "scopeLimited": visible is not None})

        count_scope = [] if visible is None else [StudentProfile.id.in_(visible)]
        counts = dict(db.execute(
            select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_([c.id for c in classes]), *count_scope)
            .group_by(StudentProfile.class_id)).all())

        major_ids = {c.major_id for c in classes if c.major_id}
        majors = db.scalars(select(Major).where(
            Major.tenant_id == tenant_id, Major.is_deleted.is_(False), Major.id.in_(list(major_ids) or [0]))).all() if major_ids else []
        college_ids = {m.college_id for m in majors if m.college_id}
        colleges = db.scalars(select(College).where(
            College.tenant_id == tenant_id, College.is_deleted.is_(False), College.id.in_(list(college_ids) or [0]))
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
        visible_college_ids = {c.id for c in colleges}
        linked_major_ids = {int(m.id) for m in majors if m.college_id in visible_college_ids}
        orphan = [row for mid, rows in cls_by_major.items() if mid not in linked_major_ids for row in rows]
        if orphan:
            tree.append({"value": "__ORPHAN__", "label": "待补组织关系的班级", "children":
                         [{"value": "__ORPHAN_MAJOR__", "label": "待补组织关系",
                           "children": orphan}]})

        return success({"tree": tree, "scopeLimited": visible is not None})
    finally:
        db.close()
