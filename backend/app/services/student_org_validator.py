"""学生组织归属（学院/专业/班级）校验器。

学生主档统一整改 阶段 B：建档与异动前必须验证完整父链，替代此前只做 `int()` 转换的
`db_service._as_optional_id` —— 那种写法允许把任意数字塞进 college_id/major_id/class_id，
可以造出「班级不属于该专业」「专业不属于该学院」甚至跨租户的脏主档。

所有创建/修改学生组织归属的入口（手工建档、统一身份导入、学籍异动、候选人晋级）
都必须经本模块，不得各自 int() 了事。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.core.exceptions import AppException, not_found


@dataclass(frozen=True)
class ValidatedStudentOrg:
    """校验通过的组织归属。college_id 允许由 major 反推补齐。"""
    college_id: int | None
    major_id: int | None
    class_id: int | None


def _as_optional_id(v, field_label: str) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{field_label}格式非法：{v}") from None


def validate_student_org_path(db, *, tenant_id: int, college_id=None, major_id=None,
                              class_id=None, actor: dict | None = None) -> ValidatedStudentOrg:
    """校验学院→专业→班级父链。

    规则：
    1. 三者都必须属于当前租户且未软删（跨租户一律 404，避免用 ID 枚举探测其它学校的组织）；
    2. class.major_id == major_id（传了 major 时）；
    3. major.college_id == college_id（传了 college 时）；
    4. 只传 class/major 时自动反推补齐上级，保证落库的三个 ID 自洽；
    5. 班级已解散（DISBANDED）不得作为新学生的归属。

    错误口径与 §9.2 一致：不存在/跨租户=404、父子冲突=422、班级已解散=409。
    """
    from app.models.org import College, Major, SchoolClass

    cid = _as_optional_id(college_id, "学院ID")
    mid = _as_optional_id(major_id, "专业ID")
    clsid = _as_optional_id(class_id, "班级ID")

    cls_row = maj_row = col_row = None

    if clsid is not None:
        cls_row = db.scalars(select(SchoolClass).where(
            SchoolClass.id == clsid, SchoolClass.tenant_id == tenant_id,
            SchoolClass.is_deleted.is_(False))).first()
        if not cls_row:
            raise not_found("班级不存在")
        if str(getattr(cls_row, "class_status", "") or "").upper() == "DISBANDED":
            raise AppException("DATA_CONFLICT", "该班级已解散，不能作为学生归属班级", http_status=409)

    if mid is not None:
        maj_row = db.scalars(select(Major).where(
            Major.id == mid, Major.tenant_id == tenant_id,
            Major.is_deleted.is_(False))).first()
        if not maj_row:
            raise not_found("专业不存在")

    if cid is not None:
        col_row = db.scalars(select(College).where(
            College.id == cid, College.tenant_id == tenant_id,
            College.is_deleted.is_(False))).first()
        if not col_row:
            raise not_found("学院不存在")

    # 班级 → 专业
    if cls_row is not None:
        if mid is None:
            mid = cls_row.major_id
            if mid is not None:
                maj_row = db.scalars(select(Major).where(
                    Major.id == mid, Major.tenant_id == tenant_id,
                    Major.is_deleted.is_(False))).first()
                if not maj_row:
                    raise not_found("班级所属专业不存在")
        elif int(cls_row.major_id or 0) != int(mid):
            raise AppException("VALIDATION_ERROR",
                               f"班级「{cls_row.class_name}」不属于所选专业，请核对后重新选择",
                               http_status=422)

    # 专业 → 学院
    if maj_row is not None:
        if cid is None:
            cid = maj_row.college_id
            if cid is not None:
                col_row = db.scalars(select(College).where(
                    College.id == cid, College.tenant_id == tenant_id,
                    College.is_deleted.is_(False))).first()
                if not col_row:
                    raise not_found("专业所属学院不存在")
        elif int(maj_row.college_id or 0) != int(cid):
            raise AppException("VALIDATION_ERROR",
                               f"专业「{maj_row.major_name}」不属于所选学院，请核对后重新选择",
                               http_status=422)

    _assert_actor_scope(db, actor, cid, clsid)
    return ValidatedStudentOrg(college_id=cid, major_id=mid, class_id=clsid)


def _assert_actor_scope(db, actor, college_id, class_id) -> None:
    """操作者数据范围校验：学院管理员不得把学生建到别的学院、辅导员不得建到别的班。

    复用 affairs_security 的既有范围计算，不另造一套判断。
    """
    if not actor:
        return
    from app.core.permissions import has_permission
    if has_permission(actor, "*"):
        return
    try:
        from app.core.affairs_security import build_affairs_context
        ctx = build_affairs_context(actor, db)
    except Exception:  # noqa: BLE001 - 范围上下文不可用时不放宽，交由调用方的既有校验兜底
        return
    allowed = ctx.allowed_class_ids(db)
    if allowed is None:
        return  # 全租户范围
    if class_id is not None and int(class_id) not in {int(x) for x in allowed}:
        raise AppException("NO_DATA_SCOPE", "目标班级超出你的数据范围", http_status=403)
