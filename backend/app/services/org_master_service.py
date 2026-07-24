"""组织主数据唯一写入服务：学院 / 专业 / 班级。

业务模块可保留入口，但写操作应调用本服务（或本服务的领域适配）。
Expand-only：强化校验与乐观锁，不强制非空历史字段、不批量回填、不删除旧字段。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker


def _tid() -> int:
    return int(current_tenant_id() or 0)


def save_org_node(*, node_type: str, name: str, code: str | None = "", parent_id=None,
                  node_id: int | None = None, reason: str = "",
                  expected_version: int | None = None, actor: dict | None = None,
                  extras: dict | None = None) -> dict:
    """统一写入。extras 用于领域扩展字段（学制、年级等），仍在同一服务会话内落库。"""
    from app.models import College, Major, SchoolClass

    node_type = str(node_type or "").upper()
    name = str(name or "").strip()
    code = str(code or "").strip()
    extras = dict(extras or {})
    if node_type not in {"COLLEGE", "MAJOR", "CLASS"} or not name:
        raise AppException("VALIDATION_ERROR", "请填写名称，并选择学院/专业/班级类型")
    if node_id is not None and parent_id is not None and len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "调整组织归属须填写原因（≥5字）")

    tenant_id = _tid()
    model = {"COLLEGE": College, "MAJOR": Major, "CLASS": SchoolClass}[node_type]
    db = get_sessionmaker()()
    try:
        row = None
        if node_id:
            row = db.scalars(select(model).where(
                model.id == node_id, model.tenant_id == tenant_id, model.is_deleted.is_(False))).first()
            if row is None:
                raise AppException("DATA_NOT_FOUND", "组织节点不存在")
            if expected_version is not None and int(getattr(row, "version", 0) or 0) != int(expected_version):
                raise AppException("DATA_CONFLICT", "组织数据已被他人修改，请刷新后重试")

        if node_type == "MAJOR":
            pid = int(parent_id or getattr(row, "college_id", 0) or 0)
            if not pid:
                raise AppException("VALIDATION_ERROR", "专业必须归属学院")
            parent = db.scalars(select(College).where(
                College.id == pid, College.tenant_id == tenant_id, College.is_deleted.is_(False))).first()
            if parent is None:
                raise AppException("VALIDATION_ERROR", "学院不属于当前租户或不存在")
            if str(parent.status or "").upper() == "DISABLED" and not row:
                raise AppException("VALIDATION_ERROR", "父级学院已停用，禁止新建专业")
        if node_type == "CLASS":
            pid = int(parent_id or getattr(row, "major_id", 0) or 0)
            if not pid:
                raise AppException("VALIDATION_ERROR", "班级必须归属专业")
            parent = db.scalars(select(Major).where(
                Major.id == pid, Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).first()
            if parent is None:
                raise AppException("VALIDATION_ERROR", "专业不属于当前租户或不存在")
            if str(parent.status or "").upper() == "DISABLED" and not row:
                raise AppException("VALIDATION_ERROR", "父级专业已停用，禁止新建班级")

        if code:
            if node_type == "COLLEGE":
                clash = db.scalars(select(College).where(
                    College.tenant_id == tenant_id, College.code == code, College.is_deleted.is_(False),
                    College.id != (node_id or 0))).first()
                if clash:
                    raise AppException("VALIDATION_ERROR", f"学院编码已存在：{code}")
            elif node_type == "MAJOR":
                clash = db.scalars(select(Major).where(
                    Major.tenant_id == tenant_id, Major.code == code, Major.is_deleted.is_(False),
                    Major.id != (node_id or 0))).first()
                if clash:
                    raise AppException("VALIDATION_ERROR", f"专业编码已存在：{code}")
            else:
                clash = db.scalars(select(SchoolClass).where(
                    SchoolClass.tenant_id == tenant_id, SchoolClass.class_code == code,
                    SchoolClass.is_deleted.is_(False), SchoolClass.id != (node_id or 0))).first()
                if clash:
                    raise AppException("VALIDATION_ERROR", f"班级编码已存在：{code}")

        before = None
        if not row:
            if node_type == "COLLEGE":
                row = College(tenant_id=tenant_id, college_name=name, code=code or None, status="ACTIVE")
            elif node_type == "MAJOR":
                row = Major(tenant_id=tenant_id, college_id=int(parent_id), major_name=name,
                            code=code or None, status="ACTIVE")
            else:
                row = SchoolClass(tenant_id=tenant_id, major_id=int(parent_id), class_name=name,
                                  class_code=code or None, status="ACTIVE")
            db.add(row)
        else:
            before = {
                "name": getattr(row, "college_name", None) or getattr(row, "major_name", None)
                or getattr(row, "class_name", None),
                "code": getattr(row, "code", None) or getattr(row, "class_code", None),
                "parentId": getattr(row, "college_id", None) or getattr(row, "major_id", None),
                "version": getattr(row, "version", None),
            }
            if node_type == "COLLEGE":
                row.college_name = name
                if code or code == "":
                    row.code = code or None
            elif node_type == "MAJOR":
                row.major_name = name
                if code or code == "":
                    row.code = code or None
                if parent_id is not None:
                    row.college_id = int(parent_id)
            else:
                row.class_name = name
                if code or code == "":
                    row.class_code = code or None
                if parent_id is not None:
                    row.major_id = int(parent_id)
            row.version = int(getattr(row, "version", 0) or 0) + 1

        # 领域扩展字段：仅写入 extras 中显式给出的键（允许 None 清字段）
        for attr, val in extras.items():
            if hasattr(row, attr):
                setattr(row, attr, val)

        db.commit()
        db.refresh(row)
        from app.services import audit_log
        audit_log.record(
            "ORG_NODE_SAVE", f"{node_type}:{row.id}",
            detail={"name": name, "code": code, "before": before, "reason": reason,
                    "moduleCode": "systemAdmin", "actor": (actor or {}).get("userId"),
                    "extras": {k: extras[k] for k in list(extras)[:20]}},
        )
        return {"id": str(row.id), "version": int(getattr(row, "version", 0) or 0), "row": row}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def disable_org_node(*, node_type: str, node_id: int, reason: str,
                     expected_version: int | None = None, actor: dict | None = None,
                     enable: bool = False) -> dict:
    from app.models import College, Major, SchoolClass, StudentProfile

    if not enable and len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因不少于 5 个字")
    node_type = str(node_type or "").upper()
    tenant_id = _tid()
    model = {"COLLEGE": College, "MAJOR": Major, "CLASS": SchoolClass}[node_type]
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(model).where(
            model.id == node_id, model.tenant_id == tenant_id, model.is_deleted.is_(False))).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "组织节点不存在")
        if expected_version is not None and int(getattr(row, "version", 0) or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "组织数据已被他人修改，请刷新后重试")

        if enable:
            row.status = "ACTIVE"
            row.version = int(getattr(row, "version", 0) or 0) + 1
            db.commit()
            return {"id": str(node_id), "status": "ACTIVE", "impact": {}}

        impact = {"children": 0, "students": 0}
        if node_type == "COLLEGE":
            impact["children"] = db.scalar(select(func.count()).select_from(Major).where(
                Major.tenant_id == tenant_id, Major.college_id == node_id, Major.is_deleted.is_(False),
                Major.status == "ACTIVE")) or 0
            impact["students"] = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.college_id == node_id,
                StudentProfile.is_deleted.is_(False))) or 0
        elif node_type == "MAJOR":
            impact["children"] = db.scalar(select(func.count()).select_from(SchoolClass).where(
                SchoolClass.tenant_id == tenant_id, SchoolClass.major_id == node_id,
                SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE")) or 0
            impact["students"] = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.major_id == node_id,
                StudentProfile.is_deleted.is_(False))) or 0
        elif node_type == "CLASS":
            impact["students"] = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.class_id == node_id,
                StudentProfile.is_deleted.is_(False))) or 0
        if impact["children"] or impact["students"]:
            raise AppException(
                "VALIDATION_ERROR",
                f"存在未处理子级或学生，禁止停用（子级={impact['children']}，学生={impact['students']}）",
            )

        row.status = "DISABLED"
        row.version = int(getattr(row, "version", 0) or 0) + 1
        db.commit()
        from app.services import audit_log
        audit_log.record("ORG_NODE_DISABLE", f"{node_type}:{node_id}",
                         detail={"reason": reason, "impact": impact, "moduleCode": "systemAdmin",
                                 "actor": (actor or {}).get("userId")})
        return {"id": str(node_id), "status": "DISABLED", "impact": impact}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def find_duplicate_org_codes(tenant_id: int | None = None) -> dict:
    """只读：检测租户内学院/专业/班级编码重复。不改数据。"""
    from app.models import College, Major, SchoolClass

    tid = int(tenant_id or _tid() or 0)
    db = get_sessionmaker()()
    try:
        def dups(model, code_col):
            rows = db.execute(
                select(code_col, func.count())
                .where(model.tenant_id == tid, model.is_deleted.is_(False), code_col.isnot(None), code_col != "")
                .group_by(code_col).having(func.count() > 1)
            ).all()
            return [{"code": r[0], "count": int(r[1])} for r in rows]

        return {
            "tenantId": tid,
            "college": dups(College, College.code),
            "major": dups(Major, Major.code),
            "class": dups(SchoolClass, SchoolClass.class_code),
        }
    finally:
        db.close()
