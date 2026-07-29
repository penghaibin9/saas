"""学工核心数据口径安全门：真实计数、数值边界、租户条件与学生画像。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_INSTALLED = False
_MAX_DECIMAL_14_2 = Decimal("999999999999.99")


def _patch_student_overview() -> None:
    from app.models import AffairsRiskRecord
    from app.services import mobile_affairs_service as affairs

    previous = affairs.overview_my

    def overview_my(user):
        data = dict(previous(user) or {})
        with session() as db:
            student = affairs._me(db, user)
            count = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(),
                AffairsRiskRecord.student_id == int(student.id),
                AffairsRiskRecord.status != "CLOSED",
                AffairsRiskRecord.is_deleted.is_(False),
            )) or 0
        data.pop("riskOpen", None)
        data["careActionCount"] = int(count)
        return data

    affairs.overview_my = overview_my


def _patch_decimal_boundaries() -> None:
    from app.services import affairs_student_atomic_service as atomic

    def optional_non_negative_decimal(value, field_name: str):
        if value in (None, ""):
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise AppException("VALIDATION_ERROR", f"{field_name}格式非法") from exc
        if not result.is_finite():
            raise AppException("VALIDATION_ERROR", f"{field_name}格式非法")
        if result < 0:
            raise AppException("VALIDATION_ERROR", f"{field_name}不能小于0")
        if result > _MAX_DECIMAL_14_2:
            raise AppException("VALIDATION_ERROR", f"{field_name}不能超过999999999999.99")
        if result.as_tuple().exponent < -2:
            raise AppException("VALIDATION_ERROR", f"{field_name}最多保留2位小数")
        return result

    atomic._optional_non_negative_decimal = optional_non_negative_decimal


def _patch_aid_student_lookup() -> None:
    from app.models import StudentProfile
    from app.services import affairs_aid_service as aid

    def students_by_ids(db, rows, attr="student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(ids),
            StudentProfile.is_deleted.is_(False),
        )).all()
        return {int(student.id): student for student in students}

    aid._students_by_ids = students_by_ids


def _patch_student_profile() -> None:
    from app.models import AffairsRiskRecord, DisciplineCase, DormBed, DormBuilding, DormRoom
    from app.services import affairs_profile_service as profile

    original_profile = profile.get_profile
    original_timeline = profile.get_timeline

    def get_profile(student_id, user):
        data = dict(original_profile(student_id, user) or {})
        sid = int(student_id)
        with session() as db:
            bed = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.student_id == sid,
                DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
            ).order_by(DormBed.id.desc())).first()
            dorm = {"hasDorm": False, "text": ""}
            if bed and bed.room_id:
                room = db.get(DormRoom, int(bed.room_id))
                if room and not room.is_deleted and room.tenant_id == _tid():
                    building = db.get(DormBuilding, int(room.building_id)) if room.building_id else None
                    if building and (building.is_deleted or building.tenant_id != _tid()):
                        building = None
                    parts = [
                        building.building_name if building else "",
                        str(room.room_no or ""),
                        f"{bed.bed_no}床" if bed.bed_no else "",
                    ]
                    dorm = {"hasDorm": True, "text": " · ".join(x for x in parts if x) or "已入住"}
            data["dormSummary"] = dorm

            open_mental = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.student_id == sid,
                AffairsRiskRecord.source == "MENTAL", AffairsRiskRecord.status != "CLOSED",
                AffairsRiskRecord.is_deleted.is_(False),
            )) or 0
            data["psyFlag"] = "需关注" if open_mental else "无"

            if has_permission(user, "studentAffairs.discipline.view"):
                active = db.scalar(select(func.count()).select_from(DisciplineCase).where(
                    DisciplineCase.tenant_id == _tid(), DisciplineCase.student_id == sid,
                    DisciplineCase.status == "EFFECTIVE", DisciplineCase.is_deleted.is_(False),
                )) or 0
                data["disciplineSummary"] = {"activeCount": int(active)}
            else:
                data["disciplineSummary"] = {"activeCount": None, "restricted": True}
        return data

    required = {
        "leave": "studentAffairs.leave.view", "aid": "studentAffairs.aid.view",
        "funding": "studentAffairs.funding.view", "discipline": "studentAffairs.discipline.view",
        "risk": "studentAffairs.risk.view", "talk": "studentAffairs.talk.view",
    }

    def get_timeline(student_id, user, event_type=None, page=1, page_size=20):
        items, total = original_timeline(student_id, user, event_type, page, page_size)
        for item in items:
            permission = required.get(item.get("module"))
            if permission and not has_permission(user, permission):
                item.update({"title": "受限学工事件", "detail": "当前角色无权查看该业务事件内容", "restricted": True})
        return items, total

    profile.get_profile = get_profile
    profile.get_timeline = get_timeline


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_student_overview()
    _patch_decimal_boundaries()
    _patch_aid_student_lookup()
    _patch_student_profile()
    _INSTALLED = True
