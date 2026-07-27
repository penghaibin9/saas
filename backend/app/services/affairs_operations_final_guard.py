"""学工材料与安全批次终态安全门。

- 材料审核附件按“业务权限 + 学生数据范围”做对象级授权；
- 教师材料队列在计数和分页前按业务权限过滤，禁止跨域数量泄露。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_INSTALLED = False


def _install_material_file_access_guard(operations) -> None:
    from app.services import file_service

    original = file_service.authorize_file_access

    def authorize_file_access(user: dict, file_obj, action: str = "download") -> bool:
        if original(user, file_obj, action):
            return True
        if file_obj is None or str(getattr(file_obj, "biz_type", "") or "").upper() != "MATERIAL_REQUIREMENT":
            return False
        raw_id = str(getattr(file_obj, "biz_id", "") or "").strip()
        if not raw_id.isdigit():
            return False
        try:
            from app.core.affairs_security import build_affairs_context
            from app.models.affairs_operations import AffairsMaterialRequirement

            with session() as db:
                requirement = db.scalars(select(AffairsMaterialRequirement).where(
                    AffairsMaterialRequirement.tenant_id == _tid(),
                    AffairsMaterialRequirement.id == int(raw_id),
                    AffairsMaterialRequirement.is_deleted.is_(False),
                )).first()
                if not requirement:
                    return False
                permissions = operations._BIZ_PERMISSIONS.get(requirement.biz_type, ())
                if not any(has_permission(user or {}, code) for code in permissions):
                    return False
                build_affairs_context(user or {}, db).require_student(db, requirement.student_id)
                return True
        except Exception:
            # 文件授权必须 fail-closed；调用方统一按不存在处理，不泄露文件存在性。
            return False

    file_service.authorize_file_access = authorize_file_access


def _install_teacher_requirement_scope_guard(operations) -> None:
    def list_teacher_requirements(user: dict, *, status: str | None = None,
                                  page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        from app.models import StudentProfile, User
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.services.affairs_dashboard_service import _allowed_class_ids

        visible_biz_types = {
            biz_type
            for biz_type, permissions in operations._BIZ_PERMISSIONS.items()
            if any(has_permission(user or {}, code) for code in permissions)
        }
        if not visible_biz_types:
            return [], 0
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        with session() as db:
            allowed, _ = _allowed_class_ids(db, user)
            conds = [
                AffairsMaterialRequirement.tenant_id == _tid(),
                AffairsMaterialRequirement.biz_type.in_(visible_biz_types),
                AffairsMaterialRequirement.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == AffairsMaterialRequirement.student_id,
                StudentProfile.is_deleted.is_(False),
            ]
            if status:
                conds.append(AffairsMaterialRequirement.status == str(status).upper())
            if allowed is not None:
                conds.append(StudentProfile.class_id.in_(allowed or {-1}))
            joined = select(AffairsMaterialRequirement).join(
                StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id,
            )
            total = int(db.scalar(
                select(func.count()).select_from(AffairsMaterialRequirement).join(
                    StudentProfile, StudentProfile.id == AffairsMaterialRequirement.student_id,
                ).where(*conds)
            ) or 0)
            rows = db.scalars(
                joined.where(*conds).order_by(AffairsMaterialRequirement.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            ).all()
            submissions = operations._submission_rows(db, [row.id for row in rows])
            owner_ids = {int(row.review_owner_id) for row in rows if row.review_owner_id}
            owners = {
                int(owner.id): owner.real_name
                for owner in db.scalars(select(User).where(
                    User.tenant_id == _tid(),
                    User.id.in_(owner_ids or {-1}),
                    User.is_deleted.is_(False),
                )).all()
            }
            items = [
                operations._requirement_dict(
                    row,
                    submissions.get(int(row.id), []),
                    student_view=False,
                    owner_name=owners.get(int(row.review_owner_id or 0), ""),
                )
                for row in rows
            ]
            return items, total

    operations.list_teacher_requirements = list_teacher_requirements


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_operations_service as operations

    _install_material_file_access_guard(operations)
    _install_teacher_requirement_scope_guard(operations)
    _INSTALLED = True
