"""学生基础服务台账安全门：主档范围、身份只读、租户批量查询和乐观锁。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_INSTALLED = False


def _text(value, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}不能超过{maximum}字")
    return text or None


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import CsAuditTrail, CsDiscipline, CsGrant, CsLeave, CsServiceStudent, CsWorkOrder
    from app.services import affairs_four_end_contract as contract
    from app.services import campus_service_service as service
    from app.services import shadow_student_service as shadow
    from app.core.optimistic_lock import atomic_versioned_update, require_expected_version

    old_predicate = contract._is_affairs_mobile_path
    old_raw = service._stu_row_raw
    old_create = service.create_student

    def request_context_path(path: str) -> bool:
        return old_predicate(path) or path.startswith("/api/v1/campus-service/students/")

    def student_row_raw(row):
        data = old_raw(row)
        data["version"] = int(row.version or 0)
        data["allowedActions"] = ["EDIT", "VOID"] if row.record_status == "ACTIVE" else []
        return data

    def students_by_ids(db, rows, attr="cs_student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        records = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(),
            CsServiceStudent.id.in_(ids),
            CsServiceStudent.is_deleted.is_(False),
        )).all()
        return {int(row.id): row for row in records}

    def create_student(body: dict):
        with session() as db:
            profile = shadow.resolve_profile_for_shadow(
                db,
                _tid(),
                domain_label="在校服务台账",
                student_id=body.get("studentId") or body.get("profileStudentId"),
                student_no=body.get("studentNo"),
            )
            from app.core.affairs_security import build_affairs_context

            build_affairs_context(get_current_user_ctx() or {}, db).require_student(db, int(profile.id))
        care = str(body.get("careLevel") or "NORMAL").upper()
        if care not in service.L_CARE:
            raise AppException("VALIDATION_ERROR", "关怀等级非法")
        payload = dict(body)
        payload["careLevel"] = care
        payload["building"] = _text(payload.get("building"), "楼栋", 100)
        payload["room"] = _text(payload.get("room"), "房间", 100)
        payload["counselor"] = _text(payload.get("counselor"), "辅导员", 100)
        result = old_create(payload)
        with session() as db:
            row = service._get_stu(db, result["id"])
            result["version"] = int(row.version or 0)
        return result

    def update_student(student_id, body: dict):
        expected = require_expected_version(contract.request_version())
        with session() as db:
            row = service._get_stu(db, student_id)
            # 允许前端把未修改的只读字段原样回传；真正修改由统一主档比较器拒绝。
            shadow.assert_identity_immutable(db, row, body, "在校服务台账")
            values = {}
            if body.get("careLevel") is not None:
                care = str(body["careLevel"]).upper()
                if care not in service.L_CARE:
                    raise AppException("VALIDATION_ERROR", "关怀等级非法")
                values["care_level"] = care
            if body.get("building") is not None:
                values["building"] = _text(body.get("building"), "楼栋", 100)
            if body.get("room") is not None:
                values["room"] = _text(body.get("room"), "房间", 100)
            if body.get("counselor") is not None:
                values["counselor"] = _text(body.get("counselor"), "辅导员", 100)
            if not values:
                raise AppException("VALIDATION_ERROR", "没有可保存的服务字段")
            atomic_versioned_update(
                db,
                CsServiceStudent,
                entity_id=int(row.id),
                tenant_id=_tid(),
                expected_version=expected,
                values=values,
                expected_status=None,
            )
            service._audit(db, "RECORD", row.id, "编辑服务记录", after=str(sorted(values)))
            db.commit()
            return {"id": str(row.id), "version": expected + 1}

    def void_student(student_id, reason):
        text = str(reason or "").strip()
        if not 5 <= len(text) <= 500:
            raise AppException("VALIDATION_ERROR", "作废原因需5-500字")
        expected = require_expected_version(contract.request_version())
        with session() as db:
            row = service._get_stu(db, student_id)
            atomic_versioned_update(
                db,
                CsServiceStudent,
                entity_id=int(row.id),
                tenant_id=_tid(),
                expected_version=expected,
                values={"record_status": "VOIDED", "void_reason": text, "is_deleted": True},
                expected_status=None,
            )
            service._audit(db, "RECORD", row.id, "作废服务记录", text)
            db.commit()
            return {"id": str(row.id), "version": expected + 1}

    def get_student_detail(student_id):
        with session() as db:
            row = service._get_stu(db, student_id)

            def common(model):
                return [
                    model.tenant_id == _tid(),
                    model.cs_student_id == row.id,
                    model.is_deleted.is_(False),
                ]

            leaves = db.scalars(select(CsLeave).where(*common(CsLeave)).order_by(CsLeave.id.desc())).all()
            grants = db.scalars(select(CsGrant).where(*common(CsGrant)).order_by(CsGrant.id.desc())).all()
            disciplines = db.scalars(select(CsDiscipline).where(*common(CsDiscipline)).order_by(CsDiscipline.id.desc())).all()
            orders = db.scalars(select(CsWorkOrder).where(*common(CsWorkOrder)).order_by(CsWorkOrder.id.desc())).all()
            logs = db.scalars(select(CsAuditTrail).where(
                CsAuditTrail.tenant_id == _tid(),
                CsAuditTrail.biz_id == str(row.id),
            ).order_by(CsAuditTrail.id.desc()).limit(20)).all()
            profiles = shadow.load_profiles(db, [row])
            return {
                "student": service._stu_row(row, db=db, profiles=profiles),
                "leaves": [service._leave_row(item, row) for item in leaves],
                "grants": [service._grant_row(item, row) for item in grants],
                "disciplines": [service._disc_row(item, row) for item in disciplines],
                "workOrders": [service._wo_row(item, row) for item in orders],
                "auditLogs": [service._log_row(item) for item in logs],
            }

    contract._is_affairs_mobile_path = request_context_path
    service._stu_row_raw = student_row_raw
    service._cs_students_by_ids = students_by_ids
    service.create_student = create_student
    service.update_student = update_student
    service.void_student = void_student
    service.get_student_detail = get_student_detail
    _INSTALLED = True
