"""D6 宿舍归寝 Provider 边界与研判。

核心 SaaS 只消费标准化事件。NONE 是完整、诚实的默认实现；外部门禁未接通、
Provider 报错或没有可用事件时一律 UNKNOWN，绝不把“没数据”伪装成“未归”。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.timeutil import tenant_tz, to_utc_naive
from app.services.db_service import _iso, _tid, session

CONFIG_KEY = "DORM_PRESENCE_POLICY"
PROVIDERS = ("NONE", "MANUAL", "ACCESS_GATE", "FACE_GATE", "THIRD_PARTY_CAMPUS")
PRESENCE_STATUSES = ("IN_DORM", "OUT", "ON_LEAVE", "LATE_RETURN", "NOT_RETURNED", "UNKNOWN")
STATUS_LABELS = {
    "IN_DORM": "在寝", "OUT": "外出", "ON_LEAVE": "已请假", "LATE_RETURN": "晚归",
    "NOT_RETURNED": "未归", "UNKNOWN": "未知",
}
DEFAULT_POLICY = {
    "policyVersion": 1,
    "provider": "NONE",
    "curfewTime": "22:30",
    "lateGraceMinutes": 15,
    "notReturnTime": "23:30",
    "noEventHours": 24,
    "consecutiveAnomalyThreshold": 3,
}


class DormPresenceProvider(ABC):
    """门禁/归寝适配器契约；设备平台在仓库外实现这个边界。"""

    code = "NONE"

    @abstractmethod
    def get_events(self, db, *, student_id: int, building_id: int, since: datetime) -> list:
        raise NotImplementedError

    @abstractmethod
    def get_device_health(self, db) -> dict:
        raise NotImplementedError

    @abstractmethod
    def normalize_event(self, raw: dict) -> dict:
        raise NotImplementedError


class NonePresenceProvider(DormPresenceProvider):
    code = "NONE"

    def get_events(self, db, *, student_id: int, building_id: int, since: datetime) -> list:
        return []

    def get_device_health(self, db) -> dict:
        return {"healthStatus": "DISABLED", "lastSyncAt": None}

    def normalize_event(self, raw: dict) -> dict:
        raise AppException("PROVIDER_DISABLED", "门禁 Provider 未配置")


class DatabasePresenceProvider(DormPresenceProvider):
    """已接入 Provider 的标准事件读取器；不访问、不保存外部生物特征原始数据。"""

    def __init__(self, code: str):
        self.code = code

    def get_events(self, db, *, student_id: int, building_id: int, since: datetime) -> list:
        from app.models import DormAccessEvent
        return db.scalars(select(DormAccessEvent).where(
            DormAccessEvent.tenant_id == _tid(),
            DormAccessEvent.provider == self.code,
            DormAccessEvent.student_id == int(student_id),
            DormAccessEvent.building_id == int(building_id),
            DormAccessEvent.event_time >= since,
            DormAccessEvent.is_deleted.is_(False),
        ).order_by(DormAccessEvent.event_time.desc(), DormAccessEvent.id.desc())).all()

    def get_device_health(self, db) -> dict:
        from app.models import DormAccessEvent
        latest = db.scalar(select(func.max(DormAccessEvent.event_time)).where(
            DormAccessEvent.tenant_id == _tid(),
            DormAccessEvent.provider == self.code,
            DormAccessEvent.is_deleted.is_(False),
        ))
        return {"healthStatus": "HEALTHY" if latest else "NO_DATA", "lastSyncAt": _iso(latest)}

    def normalize_event(self, raw: dict) -> dict:
        forbidden = {"faceTemplate", "biometricVector", "rawImage", "imageBase64"}
        if forbidden & set(raw or {}):
            raise AppException("SENSITIVE_DATA_FORBIDDEN", "标准事件禁止携带人脸模板、特征向量或原始图片")
        provider_event_id = str((raw or {}).get("providerEventId") or "").strip()
        event_type = str((raw or {}).get("eventType") or "").strip().upper()
        if not provider_event_id or event_type not in ("IN", "OUT"):
            raise AppException("VALIDATION_ERROR", "Provider 事件标识和 IN/OUT 类型必填")
        student_id = int((raw or {}).get("studentId") or 0)
        building_id = int((raw or {}).get("buildingId") or 0)
        if student_id <= 0 or building_id <= 0:
            raise AppException("VALIDATION_ERROR", "归寝事件必须绑定真实学生和楼栋")
        event_time = (raw or {}).get("eventTime")
        if isinstance(event_time, str):
            try:
                event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            except ValueError as exc:
                raise AppException("VALIDATION_ERROR", "eventTime 格式非法") from exc
        if not isinstance(event_time, datetime):
            raise AppException("VALIDATION_ERROR", "eventTime 必填")
        event_time = to_utc_naive(event_time)
        return {
            "provider": self.code, "provider_event_id": provider_event_id,
            "student_id": student_id, "building_id": building_id,
            "event_type": event_type, "event_time": event_time,
            "device_ref": str((raw or {}).get("deviceRef") or "").strip() or None,
            "result": str((raw or {}).get("result") or "SUCCESS").strip().upper(),
            "raw_ref_hash": str((raw or {}).get("rawRefHash") or "").strip() or None,
        }


def _policy() -> dict:
    from app.services.effective_config_service import resolve
    value = DEFAULT_POLICY
    source = "PACKAGE_DEFAULT_CODE"
    try:
        resolved = resolve(CONFIG_KEY, tenant_id=_tid())
        if resolved.get("value") is not None:
            value = resolved["value"]
            source = resolved.get("sourceLayer") or "PACKAGE_DEFAULT"
    except AppException as exc:
        # metadata.create_all 的单元测试/离线恢复窗口没有迁移种子时仍使用与迁移完全
        # 相同的代码默认值；其他配置错误必须显式失败，不能静默改判归寝状态。
        if exc.code not in {"NOT_FOUND", "DATA_NOT_FOUND"}:
            raise
    policy = {**DEFAULT_POLICY, **value}
    provider = str(policy.get("provider") or "NONE").upper()
    if provider not in PROVIDERS:
        raise AppException("CONFIG_INVALID", f"不支持的宿舍归寝 Provider：{provider}")
    policy["provider"] = provider
    for key in ("lateGraceMinutes", "noEventHours", "consecutiveAnomalyThreshold"):
        try:
            policy[key] = int(policy[key])
        except (TypeError, ValueError) as exc:
            raise AppException("CONFIG_INVALID", f"归寝规则 {key} 必须为整数") from exc
        if policy[key] < 0:
            raise AppException("CONFIG_INVALID", f"归寝规则 {key} 不得为负数")
    policy["policyVersion"] = int(policy.get("policyVersion") or 1)
    _parse_clock(str(policy.get("curfewTime") or ""), "curfewTime")
    _parse_clock(str(policy.get("notReturnTime") or ""), "notReturnTime")
    policy["sourceLayer"] = source
    return policy


def _parse_clock(value: str, key: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise AppException("CONFIG_INVALID", f"归寝规则 {key} 必须为 HH:MM") from exc


def _local_clock_utc(moment: datetime, clock: time) -> datetime:
    """Return a tenant-local wall-clock cutoff as UTC-naive database time."""
    utc_moment = (
        moment.replace(tzinfo=timezone.utc)
        if moment.tzinfo is None else moment.astimezone(timezone.utc)
    )
    local_day = utc_moment.astimezone(tenant_tz()).date()
    local_cutoff = datetime.combine(local_day, clock, tzinfo=tenant_tz())
    return local_cutoff.astimezone(timezone.utc).replace(tzinfo=None)


def _provider(code: str) -> DormPresenceProvider:
    return NonePresenceProvider() if code == "NONE" else DatabasePresenceProvider(code)


def _active_leave(db, student_id: int, now: datetime):
    from app.models import CsLeave
    return db.scalars(select(CsLeave).where(
        CsLeave.tenant_id == _tid(), CsLeave.student_id == int(student_id),
        CsLeave.affairs_status == "APPROVED",
        CsLeave.start_time <= now, CsLeave.end_time >= now,
        CsLeave.is_deleted.is_(False),
    ).order_by(CsLeave.end_time.desc(), CsLeave.id.desc())).first()


def _status_payload(status: str, *, event=None, leave=None, policy: dict, reason: str | None = None) -> dict:
    return {
        "status": status, "statusLabel": STATUS_LABELS[status],
        "lastEventType": getattr(event, "event_type", None),
        "lastEventAt": _iso(getattr(event, "event_time", None)),
        "leaveId": str(leave.id) if leave else None,
        "leaveEndAt": _iso(leave.end_time) if leave else None,
        "reason": reason,
        "policyVersion": int(policy.get("policyVersion") or 1),
    }


def evaluate_presence(
    db, *, student_id: int, building_id: int, now: datetime | None = None,
    policy: dict | None = None, provider: DormPresenceProvider | None = None,
) -> dict:
    """研判单个真实学生。请假优先；无数据/Provider 故障均为 UNKNOWN。"""
    if int(student_id or 0) <= 0 or int(building_id or 0) <= 0:
        raise AppException("DATA_INCONSISTENT", "归寝研判拒绝 student_id=0 或无楼栋记录")
    moment = now or datetime.utcnow()
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    rule = {**DEFAULT_POLICY, **(policy or _policy())}
    leave = _active_leave(db, int(student_id), moment)
    if leave:
        return _status_payload("ON_LEAVE", leave=leave, policy=rule, reason="APPROVED_LEAVE")
    adapter = provider or _provider(str(rule.get("provider") or "NONE").upper())
    if adapter.code == "NONE":
        return _status_payload("UNKNOWN", policy=rule, reason="PROVIDER_DISABLED")
    since = moment - timedelta(hours=max(int(rule.get("noEventHours") or 24), 1))
    try:
        events = adapter.get_events(
            db, student_id=int(student_id), building_id=int(building_id), since=since,
        )
    except Exception:
        return _status_payload("UNKNOWN", policy=rule, reason="PROVIDER_UNAVAILABLE")
    event = next((row for row in events if str(getattr(row, "result", "")).upper() == "SUCCESS"), None)
    if not event:
        return _status_payload("UNKNOWN", policy=rule, reason="NO_USABLE_EVENT")
    if event.event_time < since:
        return _status_payload("UNKNOWN", event=event, policy=rule, reason="STALE_EVENT")
    if event.event_type == "IN":
        curfew = _parse_clock(str(rule.get("curfewTime")), "curfewTime")
        deadline = _local_clock_utc(event.event_time, curfew) + timedelta(
            minutes=int(rule.get("lateGraceMinutes") or 0)
        )
        status = "LATE_RETURN" if event.event_time > deadline else "IN_DORM"
        return _status_payload(status, event=event, policy=rule)
    judgement = _parse_clock(str(rule.get("notReturnTime")), "notReturnTime")
    judgement_at = _local_clock_utc(moment, judgement)
    status = "NOT_RETURNED" if moment >= judgement_at else "OUT"
    return _status_payload(status, event=event, policy=rule)


def provider_status(user: dict | None = None) -> dict:
    rule = _policy()
    adapter = _provider(rule["provider"])
    with session() as db:
        try:
            health = adapter.get_device_health(db)
        except Exception:
            health = {"healthStatus": "UNAVAILABLE", "lastSyncAt": None}
    configured = adapter.code != "NONE"
    return {
        "provider": adapter.code,
        "providerLabel": "未配置" if not configured else adapter.code,
        "configured": configured,
        "lastSyncAt": health.get("lastSyncAt"),
        "healthStatus": health.get("healthStatus") or ("DISABLED" if not configured else "UNKNOWN"),
        "policyVersion": rule["policyVersion"],
        "configKey": CONFIG_KEY,
        "sourceLayer": rule.get("sourceLayer") or "PACKAGE_DEFAULT_CODE",
        "rules": {
            "curfewTime": rule["curfewTime"],
            "lateGraceMinutes": rule["lateGraceMinutes"],
            "notReturnTime": rule["notReturnTime"],
            "noEventHours": rule["noEventHours"],
            "consecutiveAnomalyThreshold": rule["consecutiveAnomalyThreshold"],
        },
        "notice": "未接入归寝数据" if not configured else "状态仅依据已标准化的 Provider 事件研判",
    }


def list_presence(
    user: dict, *, status: str | None = None, page: int = 1, page_size: int = 50,
    now: datetime | None = None,
) -> tuple[list[dict], int, dict]:
    from app.models import DormBed, DormBuilding, DormRoom, StudentProfile
    from app.services import affairs_dorm_service as dorm
    moment = now or datetime.utcnow()
    rule = _policy()
    adapter = _provider(rule["provider"])
    with session() as db:
        scope = dorm._dorm_scope_building_ids(db, user)
        stmt = select(DormBed, StudentProfile, DormBuilding, DormRoom).join(
            StudentProfile, StudentProfile.id == DormBed.student_id
        ).join(DormBuilding, DormBuilding.id == DormBed.building_id).join(
            DormRoom, DormRoom.id == DormBed.room_id
        ).where(
            DormBed.tenant_id == _tid(), DormBed.status == "OCCUPIED",
            DormBed.student_id.is_not(None), DormBed.student_id > 0,
            DormBed.is_deleted.is_(False), StudentProfile.is_deleted.is_(False),
            DormBuilding.is_deleted.is_(False), DormRoom.is_deleted.is_(False),
        )
        if scope is not None:
            if not scope:
                return [], 0, {key: 0 for key in PRESENCE_STATUSES}
            stmt = stmt.where(DormBed.building_id.in_(scope))
        rows = db.execute(stmt.order_by(DormBuilding.building_name, DormRoom.room_no, DormBed.bed_no)).all()
        items = []
        counts = {key: 0 for key in PRESENCE_STATUSES}
        for bed, student, building, room in rows:
            current = evaluate_presence(
                db, student_id=int(student.id), building_id=int(building.id), now=moment,
                policy=rule, provider=adapter,
            )
            counts[current["status"]] += 1
            if status and current["status"] != str(status).upper():
                continue
            items.append({
                "studentId": str(student.id), "studentNo": student.student_no,
                "studentName": student.real_name, "buildingId": str(building.id),
                "buildingName": building.building_name, "roomId": str(room.id),
                "roomNo": room.room_no, "bedNo": bed.bed_no, **current,
            })
        total = len(items)
        start = max(page - 1, 0) * page_size
        return items[start:start + page_size], total, counts


def my_presence(user: dict) -> dict:
    from app.models import DormBed
    from app.services.mobile_student_service import _require_student, resolve_student
    _require_student(user)
    rule = _policy()
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == int(student.id),
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
        )).first()
        if not bed:
            return {**_status_payload("UNKNOWN", policy=rule, reason="NO_ACTIVE_STAY"), "summary": "暂无有效住宿记录"}
        result = evaluate_presence(
            db, student_id=int(student.id), building_id=int(bed.building_id), policy=rule,
        )
        result["summary"] = "未接入归寝数据" if result["reason"] == "PROVIDER_DISABLED" else (
            f"最近事件：{result['lastEventAt'] or '—'}"
        )
        return result


def teacher_summary(user: dict) -> dict:
    _, total, counts = list_presence(user, page=1, page_size=1)
    return {
        "provider": provider_status(user), "residentTotal": total,
        "counts": counts,
        "tonightNotReturned": counts["NOT_RETURNED"],
        "lateReturn": counts["LATE_RETURN"],
        "onLeave": counts["ON_LEAVE"],
        "unknown": counts["UNKNOWN"],
    }


def store_normalized_event(db, raw: dict, *, provider_code: str) -> dict:
    """供未来 Adapter/受控同步任务调用；幂等落标准事件，不提供伪造设备数据的演示入口。"""
    from app.models import DormAccessEvent, DormBed, DormBuilding, StudentProfile
    code = str(provider_code or "").upper()
    if code not in PROVIDERS or code == "NONE":
        raise AppException("VALIDATION_ERROR", "只能写入已声明的非 NONE Provider")
    normalized = DatabasePresenceProvider(code).normalize_event(raw)
    student = db.get(StudentProfile, normalized["student_id"])
    building = db.get(DormBuilding, normalized["building_id"])
    occupied = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(), DormBed.student_id == normalized["student_id"],
        DormBed.building_id == normalized["building_id"], DormBed.status == "OCCUPIED",
        DormBed.is_deleted.is_(False),
    )).first()
    if not student or student.is_deleted or student.tenant_id != _tid() or not building \
            or building.is_deleted or building.tenant_id != _tid() or not occupied:
        raise AppException("DATA_CONFLICT", "归寝事件必须绑定当前在该楼住宿的真实学生")
    existing = db.scalars(select(DormAccessEvent).where(
        DormAccessEvent.tenant_id == _tid(), DormAccessEvent.provider == code,
        DormAccessEvent.provider_event_id == normalized["provider_event_id"],
    )).first()
    if existing:
        return {"eventId": str(existing.id), "created": False}
    row = DormAccessEvent(tenant_id=_tid(), **normalized)
    db.add(row)
    db.flush()
    return {"eventId": str(row.id), "created": True}
