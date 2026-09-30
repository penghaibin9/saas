"""D5 宿舍检查、文件证据、整改与复检的 canonical service。

保留 DormCheckTask / DormCheckRecord 作为检查事实；DormRectification 承载整改状态机。
文件只通过 FileObject + FileBinding 关联，消息走 MessageEventOutbox，待办复用 UnifiedTodo。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy import and_, func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.core.permissions import has_permission
from app.core.tenant_scoped import tenant_get
from app.services.db_service import _iso, _tid, session

POLICY_KEY = "DORM_INSPECTION_POLICY"
CHECK_TYPES = ("HYGIENE", "SAFETY", "CONTRABAND", "NIGHT_ABSENCE", "FIRE_SAFETY", "FACILITY", "OTHER")
SEVERITIES = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
SEVERITY_RANK = {value: index for index, value in enumerate(SEVERITIES)}
RECTIFICATION_OPEN = ("OPEN", "RECTIFYING", "WAITING_RECHECK", "ESCALATED")
TODO_RECTIFY = "DORM_RECTIFICATION"
TODO_RECHECK = "DORM_RECTIFICATION_RECHECK"


def _template(key: str, name: str, check_type: str, items: list[tuple]) -> dict:
    return {
        "key": key, "version": 1, "name": name, "checkType": check_type,
        "items": [
            {"code": code, "name": label, "maxScore": score, "required": required, "severity": severity}
            for code, label, score, required, severity in items
        ],
    }


DEFAULT_POLICY = {
    "policyVersion": 1,
    "riskSeverities": ["HIGH", "CRITICAL"],
    "evidenceRequiredSeverities": ["HIGH", "CRITICAL"],
    "deadlineHours": {"LOW": 72, "MEDIUM": 48, "HIGH": 24, "CRITICAL": 4},
    "templates": [
        _template("DORM-HYGIENE-DEFAULT", "日常卫生检查", "HYGIENE", [
            ("FLOOR", "地面", 20, True, "LOW"), ("DESK", "桌面", 20, True, "LOW"),
            ("BED", "床铺", 20, True, "LOW"), ("BALCONY", "阳台", 20, True, "MEDIUM"),
            ("WASTE", "垃圾与异味", 20, True, "MEDIUM"),
        ]),
        _template("DORM-SAFETY-DEFAULT", "用电与消防安全检查", "SAFETY", [
            ("ELECTRIC", "用电安全", 35, True, "HIGH"),
            ("FIRE_PASSAGE", "消防通道", 35, True, "CRITICAL"),
            ("CONTRABAND", "违禁电器", 30, True, "HIGH"),
        ]),
        _template("DORM-CONTRABAND-DEFAULT", "违禁品专项检查", "CONTRABAND", [
            ("APPLIANCE", "违禁电器", 50, True, "HIGH"),
            ("DANGEROUS_GOODS", "危险物品", 50, True, "CRITICAL"),
        ]),
        _template("DORM-NIGHT-DEFAULT", "夜间在寝人工核验", "NIGHT_ABSENCE", [
            ("PRESENCE", "本人在寝情况", 70, True, "HIGH"),
            ("CONTACT", "联系核验情况", 30, True, "HIGH"),
        ]),
        _template("DORM-FIRE-DEFAULT", "消防安全专项检查", "FIRE_SAFETY", [
            ("PASSAGE", "消防通道", 40, True, "CRITICAL"),
            ("EQUIPMENT", "消防器材", 30, True, "HIGH"),
            ("CHARGING", "违规充电", 30, True, "HIGH"),
        ]),
        _template("DORM-FACILITY-DEFAULT", "公共设施检查", "FACILITY", [
            ("WATER", "给排水", 35, True, "MEDIUM"),
            ("ELECTRIC", "公共用电", 35, True, "HIGH"),
            ("DOOR_WINDOW", "门窗与锁具", 30, True, "MEDIUM"),
        ]),
        _template("DORM-OTHER-DEFAULT", "其他宿舍检查", "OTHER", [
            ("CUSTOM", "自定义检查项", 100, True, "MEDIUM"),
        ]),
    ],
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(body: Any) -> dict:
    if isinstance(body, dict):
        return body
    if hasattr(body, "model_dump"):
        return body.model_dump()
    if hasattr(body, "dict"):
        return body.dict()
    return {key: getattr(body, key) for key in dir(body) if not key.startswith("_")}


def _parse_datetime(value: Any, *, required: bool = False, field: str = "时间") -> datetime | None:
    if value in (None, ""):
        if required:
            raise AppException("VALIDATION_ERROR", f"{field}必填")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _text(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", f"{field}格式非法") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _decimal(value: Any, *, field: str, minimum: Decimal = Decimal("0"), maximum: Decimal = Decimal("100")) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{field}须为数字") from exc
    if number < minimum or number > maximum:
        raise AppException("VALIDATION_ERROR", f"{field}须在 {minimum}-{maximum} 之间")
    return number.quantize(Decimal("0.01"))


def _validate_policy(raw: Any) -> dict:
    policy = raw if isinstance(raw, dict) else {}
    templates = policy.get("templates")
    risks = [str(value).upper() for value in (policy.get("riskSeverities") or [])]
    evidence = [str(value).upper() for value in (policy.get("evidenceRequiredSeverities") or [])]
    deadlines = policy.get("deadlineHours") or {}
    if not isinstance(templates, list) or not templates:
        raise AppException("CONFIG_INVALID", "宿舍检查模板配置为空或格式错误")
    if not risks or any(value not in {"HIGH", "CRITICAL"} for value in risks):
        raise AppException("CONFIG_INVALID", "宿舍风险阈值只能包含 HIGH/CRITICAL，禁止把普通卫生问题批量转风险")
    if any(value not in SEVERITIES[1:] for value in evidence):
        raise AppException("CONFIG_INVALID", "宿舍检查证据阈值配置非法")
    normalized = []
    seen = set()
    for item in templates:
        if not isinstance(item, dict):
            raise AppException("CONFIG_INVALID", "宿舍检查模板须为对象")
        key = _text(item.get("key"))
        check_type = _text(item.get("checkType")).upper()
        try:
            version = int(item.get("version") or 0)
        except (TypeError, ValueError) as exc:
            raise AppException("CONFIG_INVALID", f"检查模板 {key or '-'} 版本非法") from exc
        rows = item.get("items")
        if not key or key in seen or check_type not in CHECK_TYPES or version < 1 or not isinstance(rows, list) or not rows:
            raise AppException("CONFIG_INVALID", f"检查模板 {key or '-'} 定义非法")
        seen.add(key)
        normalized_items = []
        item_codes = set()
        for row in rows:
            code = _text((row or {}).get("code")).upper()
            severity = _text((row or {}).get("severity") or "MEDIUM").upper()
            max_score = _decimal((row or {}).get("maxScore"), field=f"{key}.{code}分值", maximum=Decimal("1000"))
            if not code or code in item_codes or severity not in SEVERITIES[1:] or max_score <= 0:
                raise AppException("CONFIG_INVALID", f"检查模板 {key} 的项目定义非法")
            item_codes.add(code)
            normalized_items.append({
                "code": code, "name": _text((row or {}).get("name")) or code,
                "maxScore": float(max_score), "required": bool((row or {}).get("required", True)),
                "severity": severity,
            })
        normalized.append({
            "key": key, "version": version, "name": _text(item.get("name")) or key,
            "checkType": check_type, "items": normalized_items,
        })
    normalized_deadlines = {}
    for severity in SEVERITIES[1:]:
        try:
            hours = int(deadlines.get(severity) or DEFAULT_POLICY["deadlineHours"][severity])
        except (TypeError, ValueError) as exc:
            raise AppException("CONFIG_INVALID", f"{severity} 整改时限非法") from exc
        if hours < 1 or hours > 720:
            raise AppException("CONFIG_INVALID", f"{severity} 整改时限须为 1-720 小时")
        normalized_deadlines[severity] = hours
    return {
        "policyVersion": int(policy.get("policyVersion") or 1),
        "riskSeverities": list(dict.fromkeys(risks)),
        "evidenceRequiredSeverities": list(dict.fromkeys(evidence)),
        "deadlineHours": normalized_deadlines,
        "templates": normalized,
    }


def resolve_policy() -> dict:
    source = "PACKAGE_DEFAULT_CODE"
    chain = []
    value = DEFAULT_POLICY
    try:
        from app.services import effective_config_service
        resolved = effective_config_service.resolve(POLICY_KEY, tenant_id=_tid())
        if resolved.get("value") is not None:
            value = resolved["value"]
            source = resolved.get("sourceLayer") or "PACKAGE_DEFAULT"
            chain = resolved.get("chain") or []
    except AppException as exc:
        if exc.code not in {"NOT_FOUND", "DATA_NOT_FOUND"}:
            raise
    policy = _validate_policy(value)
    return {**policy, "configKey": POLICY_KEY, "sourceLayer": source, "chain": chain}


def list_templates(user: dict) -> dict:
    if not has_permission(user or {}, "studentAffairs.dorm.view"):
        raise no_permission("无宿舍检查查看权限")
    policy = resolve_policy()
    return {
        "configKey": POLICY_KEY,
        "policyVersion": policy["policyVersion"],
        "sourceLayer": policy["sourceLayer"],
        "riskSeverities": policy["riskSeverities"],
        "evidenceRequiredSeverities": policy["evidenceRequiredSeverities"],
        "deadlineHours": policy["deadlineHours"],
        "items": policy["templates"],
    }


def _actor_user_id(user: dict) -> int:
    from app.services.message_identity import resolve_message_user_id
    value = int(resolve_message_user_id(user or {}) or 0)
    if value <= 0:
        raise AppException("VALIDATION_ERROR", "无法识别当前正式账号")
    return value


def _require_staff(user: dict, permission: str = "studentAffairs.dorm.inspection.manage") -> None:
    if str((user or {}).get("userType") or "").upper() == "STUDENT" or not has_permission(user or {}, permission):
        raise no_permission("无宿舍检查操作权限")


def _select_template(policy: dict, key: str | None, version: Any, check_type: str | None) -> dict:
    wanted_key = _text(key)
    wanted_type = _text(check_type).upper()
    candidates = list(policy["templates"])
    if wanted_key:
        candidates = [item for item in candidates if item["key"] == wanted_key]
    elif wanted_type:
        candidates = [item for item in candidates if item["checkType"] == wanted_type]
    if version not in (None, ""):
        try:
            wanted_version = int(version)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "模板版本非法") from exc
        candidates = [item for item in candidates if item["version"] == wanted_version]
    if len(candidates) != 1:
        raise AppException("VALIDATION_ERROR", "未找到唯一可用的宿舍检查模板")
    template = candidates[0]
    if wanted_type and template["checkType"] != wanted_type:
        raise AppException("VALIDATION_ERROR", "检查类型与模板不一致")
    return template


def _task_row(task, *, building=None, totals: dict | None = None) -> dict:
    snapshot = task.template_snapshot_json or {}
    return {
        "taskId": str(task.id), "taskName": task.task_name,
        "buildingId": str(task.building_id or ""),
        "buildingName": getattr(building, "building_name", "") or "",
        "floorScope": task.floor_scope_json or [],
        "checkType": task.check_type,
        "templateKey": task.template_key, "templateVersion": task.template_version,
        "templateName": snapshot.get("templateName") or snapshot.get("name") or task.template_key,
        "templateItems": snapshot.get("items") or [],
        "checkerUserId": str(task.checker_user_id or ""), "checkerKey": task.checker_key or "",
        "plannedAt": _iso(task.planned_at), "publishedAt": _iso(task.published_at),
        "completedAt": _iso(task.completed_at), "status": task.status,
        "version": int(task.version or 0), "createdAt": _iso(task.created_at),
        "recordCount": int((totals or {}).get("recordCount") or 0),
        "abnormalCount": int((totals or {}).get("abnormalCount") or 0),
        "pendingRectificationCount": int((totals or {}).get("pendingRectificationCount") or 0),
    }


def create_task(body: Any, user: dict) -> dict:
    _require_staff(user)
    payload = _as_dict(body)
    task_name = _text(payload.get("taskName"))
    if not 2 <= len(task_name) <= 200:
        raise AppException("VALIDATION_ERROR", "检查任务名称需2-200字")
    building_raw = _text(payload.get("buildingId"))
    if not building_raw.isdigit():
        raise AppException("VALIDATION_ERROR", "检查任务必须选择具体楼栋")
    building_id = int(building_raw)
    policy = resolve_policy()
    template = _select_template(
        policy, payload.get("templateKey"), payload.get("templateVersion"), payload.get("checkType"),
    )
    floors = []
    for raw in payload.get("floorScope") or []:
        try:
            floor = int(raw)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "楼层范围须为整数数组") from exc
        if floor <= 0:
            raise AppException("VALIDATION_ERROR", "楼层范围须为正整数")
        if floor not in floors:
            floors.append(floor)
    floors.sort()
    planned_at = _parse_datetime(payload.get("plannedAt"), field="计划检查时间")
    client_request_id = _text(payload.get("clientRequestId")) or None
    if client_request_id and not 8 <= len(client_request_id) <= 100:
        raise AppException("VALIDATION_ERROR", "clientRequestId 长度须为8-100")
    actor_id = _actor_user_id(user)
    checker_id_raw = _text(payload.get("checkerUserId"))
    checker_id = int(checker_id_raw) if checker_id_raw.isdigit() else actor_id
    now = datetime.utcnow()
    snapshot = {
        "policyVersion": policy["policyVersion"], "policySource": policy["sourceLayer"],
        "templateKey": template["key"], "templateVersion": template["version"],
        "templateName": template["name"], "checkType": template["checkType"],
        "items": template["items"], "riskSeverities": policy["riskSeverities"],
        "evidenceRequiredSeverities": policy["evidenceRequiredSeverities"],
        "deadlineHours": policy["deadlineHours"],
    }
    with session() as db:
        from app.models import DormBuilding, DormCheckTask, User
        from app.services import affairs_dorm_service as dorm
        building = db.get(DormBuilding, building_id)
        if not building or building.is_deleted or building.tenant_id != _tid() or building.status != "ENABLED":
            raise not_found("检查楼栋不存在或未启用")
        dorm._require_dorm_scope(db, building_id, user)
        if floors and building.floor_count and max(floors) > int(building.floor_count):
            raise AppException("VALIDATION_ERROR", "检查楼层超出楼栋实际层数")
        checker = db.get(User, checker_id)
        if not checker or checker.is_deleted or checker.tenant_id != _tid() or checker.status != "ACTIVE":
            raise not_found("指定检查人不存在或未启用")
        if client_request_id:
            existing = db.scalars(select(DormCheckTask).where(
                DormCheckTask.tenant_id == _tid(), DormCheckTask.client_request_id == client_request_id,
                DormCheckTask.is_deleted.is_(False),
            ).with_for_update()).first()
            if existing:
                if (
                    existing.task_name != task_name or int(existing.building_id or 0) != building_id
                    or existing.template_key != template["key"] or int(existing.template_version or 0) != template["version"]
                    or list(existing.floor_scope_json or []) != floors
                ):
                    raise AppException("IDEMPOTENCY_CONFLICT", "同一 clientRequestId 已用于不同检查任务")
                return _task_row(existing, building=building)
        task = DormCheckTask(
            tenant_id=_tid(), task_name=task_name, building_id=building_id,
            check_type=template["checkType"], floor_scope_json=floors,
            template_key=template["key"], template_version=template["version"],
            template_snapshot_json=snapshot, client_request_id=client_request_id,
            checker_key=checker.login_name, checker_user_id=checker.id,
            planned_at=planned_at, published_at=now, status="RUNNING",
        )
        db.add(task); db.flush()
        dorm._audit(db, "DORM_CHECK", task.id, "TASK_PUBLISHED", f"template={template['key']}@{template['version']}")
        db.commit(); db.refresh(task)
        return _task_row(task, building=building)


def list_tasks(user: dict, status: str | None = None, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    if not has_permission(user or {}, "studentAffairs.dorm.view"):
        raise no_permission("无宿舍检查查看权限")
    from app.models import DormBuilding, DormCheckRecord, DormCheckTask, DormRectification
    from app.services import affairs_dorm_service as dorm
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 50), 200))
    with session() as db:
        scope = dorm._dorm_scope_building_ids(db, user)
        conds = [DormCheckTask.tenant_id == _tid(), DormCheckTask.is_deleted.is_(False)]
        if status:
            wanted = _text(status).upper()
            if wanted not in {"DRAFT", "PUBLISHED", "RUNNING", "DONE", "CANCELLED"}:
                raise AppException("VALIDATION_ERROR", "检查任务状态非法")
            conds.append(DormCheckTask.status == wanted)
        if scope is not None:
            conds.append(DormCheckTask.building_id.in_(scope or {-1}))
        total = int(db.scalar(select(func.count()).select_from(DormCheckTask).where(*conds)) or 0)
        rows = db.execute(
            select(DormCheckTask, DormBuilding).outerjoin(
                DormBuilding, and_(DormBuilding.tenant_id == _tid(), DormBuilding.id == DormCheckTask.building_id,
                                   DormBuilding.is_deleted.is_(False)),
            ).where(*conds).order_by(DormCheckTask.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        task_ids = [int(task.id) for task, _ in rows]
        record_counts = {}
        if task_ids:
            for task_id, count_all, count_abnormal in db.execute(select(
                DormCheckRecord.task_id,
                func.count(DormCheckRecord.id),
                func.sum(func.if_(DormCheckRecord.result == "ABNORMAL", 1, 0)),
            ).where(
                DormCheckRecord.tenant_id == _tid(), DormCheckRecord.task_id.in_(task_ids),
                DormCheckRecord.is_deleted.is_(False),
            ).group_by(DormCheckRecord.task_id)).all():
                record_counts[int(task_id)] = {"recordCount": int(count_all or 0), "abnormalCount": int(count_abnormal or 0)}
            pending = db.execute(select(
                DormRectification.task_id, func.count(DormRectification.id),
            ).where(
                DormRectification.tenant_id == _tid(), DormRectification.task_id.in_(task_ids),
                DormRectification.status.in_(RECTIFICATION_OPEN), DormRectification.is_deleted.is_(False),
            ).group_by(DormRectification.task_id)).all()
            for task_id, count_pending in pending:
                record_counts.setdefault(int(task_id), {})["pendingRectificationCount"] = int(count_pending or 0)
        return [_task_row(task, building=building, totals=record_counts.get(int(task.id))) for task, building in rows], total


def _normalize_file_ids(raw: Any, *, required: bool = False, label: str = "照片证据") -> list[str]:
    if raw is None:
        values = []
    elif isinstance(raw, list):
        values = list(dict.fromkeys(_text(value) for value in raw if _text(value)))
    else:
        raise AppException("VALIDATION_ERROR", "fileIds 必须是数组")
    if len(values) > 9 or any(not value.isdigit() for value in values):
        raise AppException("VALIDATION_ERROR", "fileIds 最多9个且必须是数字文件ID")
    if required and not values:
        raise AppException("VALIDATION_ERROR", f"{label}必填")
    return values


def _normalize_item_results(template: dict, raw: Any, *, legacy_allowed: bool, result_hint: str) -> tuple[list[dict], str, Decimal, str]:
    if not raw:
        if not legacy_allowed:
            raise AppException("VALIDATION_ERROR", "请逐项完成检查模板后再提交")
        severity = "NONE" if result_hint == "NORMAL" else "MEDIUM"
        return ([{"itemCode": "LEGACY_RESULT", "status": "PASS" if result_hint == "NORMAL" else "FAIL",
                  "score": None, "note": "兼容旧端提交"}], result_hint, Decimal("100") if result_hint == "NORMAL" else Decimal("0"), severity)
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "itemResults 必须是数组")
    definitions = {item["code"]: item for item in template["items"]}
    normalized = []
    seen = set()
    total, max_total = Decimal("0"), sum(Decimal(str(item["maxScore"])) for item in template["items"])
    failed_severity = "NONE"
    for item in raw:
        code = _text((item or {}).get("itemCode") or (item or {}).get("code")).upper()
        status = _text((item or {}).get("status")).upper()
        if code not in definitions or code in seen or status not in {"PASS", "FAIL", "NA"}:
            raise AppException("VALIDATION_ERROR", f"检查项目 {code or '-'} 结果非法")
        definition = definitions[code]
        if definition["required"] and status == "NA":
            raise AppException("VALIDATION_ERROR", f"必检项“{definition['name']}”不能标记不适用")
        score = _decimal((item or {}).get("score") if (item or {}).get("score") is not None else (
            definition["maxScore"] if status == "PASS" else 0
        ), field=f"{definition['name']}得分", maximum=Decimal(str(definition["maxScore"])))
        total += score
        if status == "FAIL" and SEVERITY_RANK[definition["severity"]] > SEVERITY_RANK[failed_severity]:
            failed_severity = definition["severity"]
        normalized.append({
            "itemCode": code, "itemName": definition["name"], "status": status,
            "score": float(score), "maxScore": definition["maxScore"],
            "severity": definition["severity"], "note": _text((item or {}).get("note"))[:500],
        })
        seen.add(code)
    missing = [item["name"] for item in template["items"] if item["required"] and item["code"] not in seen]
    if missing:
        raise AppException("VALIDATION_ERROR", "缺少必检项：" + "、".join(missing))
    computed_result = "ABNORMAL" if failed_severity != "NONE" else "NORMAL"
    score100 = (total * Decimal("100") / max_total).quantize(Decimal("0.01")) if max_total else Decimal("0")
    return normalized, computed_result, score100, failed_severity


def _student_in_room(db, student_id: int, room_id: int):
    from app.models import DormBed, DormStay, StudentProfile
    student = db.get(StudentProfile, int(student_id))
    if not student or student.is_deleted or student.tenant_id != _tid():
        raise not_found("涉事学生不存在或不在本租户")
    occupied = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(), DormBed.room_id == int(room_id),
        DormBed.student_id == int(student_id), DormBed.status == "OCCUPIED",
        DormBed.is_deleted.is_(False),
    )).first()
    active_stay = db.scalars(select(DormStay).where(
        DormStay.tenant_id == _tid(), DormStay.room_id == int(room_id),
        DormStay.student_id == int(student_id), DormStay.status.in_(("ACTIVE", "RESERVED")),
        DormStay.is_deleted.is_(False),
    )).first()
    if not occupied and not active_stay:
        raise AppException("DATA_CONFLICT", "涉事学生当前不属于该房间，禁止错误归责")
    return student


def _bind_files(db, *, file_ids: list[str], biz_type: str, biz_id: int, relation_type: str,
                actor: dict, student=None, room=None, building_id: int | None = None) -> None:
    from app.services.file_business_binding_service import bind_file_to_business
    for file_id in file_ids:
        binding = bind_file_to_business(
            db, file_id=file_id, biz_type=biz_type, biz_id=biz_id, actor=actor,
            subject_type="STUDENT" if student is not None else "ROOM",
            subject_id=student.id if student is not None else room.id,
            relation_type=relation_type, module_code="STUDENT_AFFAIRS",
            student_id=int(student.id) if student is not None else None,
            college_id=int(student.college_id) if student is not None and student.college_id else None,
            class_id=int(student.class_id) if student is not None and student.class_id else None,
            scope={
                "studentId": str(student.id) if student is not None else None,
                "buildingId": str(building_id or ""), "roomId": str(room.id if room is not None else ""),
            },
        )
        if str(binding.relation_type or "").upper() != relation_type.upper():
            raise AppException(
                "FILE_ALREADY_BOUND",
                "同一文件已作为该业务对象的其他阶段证据，复检请上传新的现场文件",
            )


def _files_for(db, biz_type: str, biz_ids: list[int]) -> dict[int, list[dict]]:
    from app.models.file import FileBinding, FileObject
    if not biz_ids:
        return {}
    rows = db.execute(select(FileBinding, FileObject).join(
        FileObject, and_(FileObject.id == FileBinding.file_id, FileObject.tenant_id == FileBinding.tenant_id),
    ).where(
        FileBinding.tenant_id == _tid(), FileBinding.biz_type == biz_type,
        FileBinding.biz_id.in_([str(value) for value in biz_ids]),
        FileBinding.status == "ACTIVE", FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False), FileObject.is_deleted.is_(False),
    ).order_by(FileBinding.id)).all()
    grouped: dict[int, list[dict]] = {}
    for binding, file_obj in rows:
        if not str(binding.biz_id).isdigit():
            continue
        grouped.setdefault(int(binding.biz_id), []).append({
            "fileId": str(file_obj.id), "fileName": file_obj.file_name,
            "mimeType": file_obj.mime_type or "", "sizeBytes": file_obj.size_bytes,
            "scanStatus": file_obj.scan_status, "relationType": binding.relation_type,
        })
    return grouped


def _active_student_user_id(db, student_id: int) -> int | None:
    from app.models import StudentAccountLink, User
    rows = db.execute(select(StudentAccountLink, User).join(
        User, and_(User.id == StudentAccountLink.user_id, User.tenant_id == StudentAccountLink.tenant_id),
    ).where(
        StudentAccountLink.tenant_id == _tid(), StudentAccountLink.student_id == int(student_id),
        StudentAccountLink.link_status == "ACTIVE", StudentAccountLink.is_deleted.is_(False),
        User.status == "ACTIVE", User.is_deleted.is_(False),
    )).all()
    if len(rows) > 1:
        raise AppException("DATA_CONFLICT", "学生存在多个有效账号绑定，无法生成唯一整改待办")
    return int(rows[0][1].id) if rows else None


def _set_rectification_todo(db, rect, *, room_no: str, student=None, recheck: bool = False) -> None:
    from app.services import affairs_dorm_service as dorm
    if recheck:
        aids = dorm._dorm_manager_assignee_ids(db, rect.building_id)
        if not aids:
            raise AppException("ASSIGNEE_NOT_CONFIGURED", f"楼栋 {rect.building_id} 未配置有效宿管")
        rect.assignee_type, rect.assignee_id = "DORM_MANAGER", aids[0]
        dorm._todo_upsert(
            db, rect.id, aids[0], rect.student_id,
            f"宿舍整改待复检：{room_no}", TODO_RECHECK, biz_type="DORM_RECTIFICATION",
        )
        return
    student_user_id = _active_student_user_id(db, rect.student_id) if rect.student_id else None
    if student_user_id:
        rect.assignee_type, rect.assignee_id = "STUDENT", int(rect.student_id)
        dorm._todo_upsert(
            db, rect.id, student_user_id, rect.student_id,
            f"宿舍整改待完成：{room_no}", TODO_RECTIFY, biz_type="DORM_RECTIFICATION",
        )
        return
    aids = dorm._dorm_manager_assignee_ids(db, rect.building_id)
    if not aids:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"楼栋 {rect.building_id} 未配置有效宿管")
    rect.assignee_type, rect.assignee_id = "DORM_MANAGER", aids[0]
    dorm._todo_upsert(
        db, rect.id, aids[0], rect.student_id,
        f"宿舍整改待完成：{room_no}", TODO_RECTIFY, biz_type="DORM_RECTIFICATION",
    )


def _emit_student_notice(db, *, rect, event_code: str, title: str, content: str) -> None:
    if not rect.student_id:
        return
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db, event_code=event_code, source_module="student-affairs",
        source_biz_type="DORM_RECTIFICATION", source_biz_id=int(rect.id),
        receiver_id=int(rect.student_id), receiver_as="student",
        title=title, content=content,
        action_key="STUDENT_AFFAIRS_DORM_RECTIFICATION",
        action_params={"rectificationId": str(rect.id)}, dedup_extra=f"{event_code}:{rect.version}",
    )


def _create_risk_if_threshold(db, *, rect, record, student, task, room, policy: dict):
    if not student or rect.severity not in set(policy["riskSeverities"]):
        return None
    from app.models import AffairsRiskRecord
    from app.services import affairs_dorm_service as dorm
    from app.services import affairs_risk_service as risk_service
    owner_ids = dorm._dorm_manager_assignee_ids(db, rect.building_id)
    owner_id = owner_ids[0] if owner_ids else None
    risk = AffairsRiskRecord(
        tenant_id=_tid(), student_id=int(student.id), source="DORM", source_ref_id=int(rect.id),
        risk_level=rect.severity,
        title=f"宿舍{task.check_type}高风险异常：{room.room_no}",
        detail=record.detail, owner_id=owner_id, deadline_at=rect.deadline_at,
        assigned_at=datetime.utcnow() if owner_id else None,
        status="ASSIGNED" if owner_id else "NEW",
    )
    db.add(risk); db.flush()
    if owner_id:
        risk_service._todo_upsert(db, risk.id, owner_id, student.id, f"宿舍高风险待处置：{student.real_name}")
        risk_service._msg(db, owner_id, "宿舍高风险待处置", record.detail or "宿舍检查发现高风险异常", "RISK_ALERT", risk.id)
    rect.related_risk_id = risk.id
    record.related_risk_id = risk.id
    return risk


def submit_record(task_id: int, body: Any, user: dict) -> dict:
    _require_staff(user)
    payload = _as_dict(body)
    result_hint = _text(payload.get("result") or "NORMAL").upper()
    if result_hint not in {"NORMAL", "ABNORMAL"}:
        raise AppException("VALIDATION_ERROR", "检查结果须为 NORMAL/ABNORMAL")
    room_raw = _text(payload.get("roomId"))
    if not room_raw.isdigit():
        raise AppException("VALIDATION_ERROR", "逐房检查必须选择具体房间")
    room_id = int(room_raw)
    client_request_id = _text(payload.get("clientRequestId")) or None
    if client_request_id and not 8 <= len(client_request_id) <= 100:
        raise AppException("VALIDATION_ERROR", "clientRequestId 长度须为8-100")
    actor_id = _actor_user_id(user)
    with session() as db:
        from app.models import (CsDormException, DormCheckRecord, DormCheckTask,
                                DormRectification, DormRoom)
        from app.services import affairs_dorm_service as dorm
        task = db.scalars(select(DormCheckTask).where(
            DormCheckTask.tenant_id == _tid(), DormCheckTask.id == int(task_id),
            DormCheckTask.is_deleted.is_(False),
        ).with_for_update()).first()
        if not task:
            raise not_found("检查任务不存在")
        dorm._require_dorm_scope(db, task.building_id, user)
        if task.status not in {"PUBLISHED", "RUNNING"}:
            raise AppException("DATA_CONFLICT", "该检查任务当前不可录入")
        room = db.get(DormRoom, room_id)
        if not room or room.is_deleted or room.tenant_id != _tid() or int(room.building_id) != int(task.building_id):
            raise AppException("NO_DATA_SCOPE", "房间不属于检查任务楼栋")
        if task.floor_scope_json and int(room.floor_no) not in {int(value) for value in task.floor_scope_json}:
            raise AppException("NO_DATA_SCOPE", "房间不在检查任务楼层范围内")
        if client_request_id:
            existing = db.scalars(select(DormCheckRecord).where(
                DormCheckRecord.tenant_id == _tid(), DormCheckRecord.task_id == int(task.id),
                DormCheckRecord.client_request_id == client_request_id,
                DormCheckRecord.is_deleted.is_(False),
            ).with_for_update()).first()
            if existing:
                if int(existing.room_id or 0) != room_id:
                    raise AppException("IDEMPOTENCY_CONFLICT", "同一 clientRequestId 已用于其他房间")
                return _record_row(db, existing)
        snapshot = task.template_snapshot_json or {}
        template = {
            "items": snapshot.get("items") or [],
            "key": task.template_key, "version": task.template_version,
        }
        items, computed_result, computed_score, failed_severity = _normalize_item_results(
            template, payload.get("itemResults"), legacy_allowed=not bool(client_request_id), result_hint=result_hint,
        )
        if payload.get("itemResults") and result_hint != computed_result:
            raise AppException("VALIDATION_ERROR", "检查总结果与逐项结果不一致")
        requested_severity = _text(payload.get("severity") or failed_severity).upper()
        if computed_result == "NORMAL":
            severity = "NONE"
        else:
            if requested_severity not in SEVERITIES[1:]:
                raise AppException("VALIDATION_ERROR", "异常严重级别非法")
            severity = max((requested_severity, failed_severity), key=lambda value: SEVERITY_RANK[value])
        detail = _text(payload.get("detail"))
        if computed_result == "ABNORMAL" and not 5 <= len(detail) <= 1000:
            raise AppException("VALIDATION_ERROR", "异常说明需5-1000字")
        student = None
        student_raw = _text(payload.get("studentId"))
        if student_raw:
            if not student_raw.isdigit():
                raise AppException("VALIDATION_ERROR", "涉事学生ID非法")
            student = _student_in_room(db, int(student_raw), room_id)
        if task.check_type == "NIGHT_ABSENCE" and computed_result == "ABNORMAL" and not student:
            raise AppException("VALIDATION_ERROR", "夜不归宿异常须指定真实涉事学生")
        risk_severities = list(snapshot.get("riskSeverities") or ["HIGH", "CRITICAL"])
        evidence_severities = list(snapshot.get("evidenceRequiredSeverities") or ["HIGH", "CRITICAL"])
        deadlines = dict(snapshot.get("deadlineHours") or DEFAULT_POLICY["deadlineHours"])
        file_ids = _normalize_file_ids(
            payload.get("fileIds"), required=(computed_result == "ABNORMAL" and severity in evidence_severities),
            label="中高风险检查照片证据",
        )
        deadline = None
        if computed_result == "ABNORMAL":
            deadline = _parse_datetime(payload.get("rectifyDeadline"), field="整改期限")
            if deadline is None:
                deadline = datetime.utcnow() + timedelta(hours=int(deadlines.get(severity) or 48))
            if deadline <= datetime.utcnow():
                raise AppException("VALIDATION_ERROR", "整改期限须晚于当前时间")
        record = DormCheckRecord(
            tenant_id=_tid(), task_id=task.id, room_id=room.id,
            result=computed_result, severity=severity, score=computed_score,
            item_results_json=items, client_request_id=client_request_id,
            issue_type=_text(payload.get("issueType")) or (task.check_type if computed_result == "ABNORMAL" else None),
            detail=detail or None, rectify_deadline=deadline,
            inspected_by_user_id=actor_id, inspected_at=datetime.utcnow(),
            student_ids_json=json.dumps([int(student.id)]) if student else None,
            status="ABNORMAL" if computed_result == "ABNORMAL" else "NORMAL",
        )
        db.add(record); db.flush()
        _bind_files(
            db, file_ids=file_ids, biz_type="DORM_CHECK_RECORD", biz_id=record.id,
            relation_type="INSPECTION_EVIDENCE", actor=user, student=student, room=room,
            building_id=task.building_id,
        )
        rect = None
        if computed_result == "ABNORMAL":
            exception = CsDormException(
                tenant_id=_tid(), cs_student_id=(dorm._cs_student_id(db, student.id) if student else 0),
                exc_type=record.issue_type or task.check_type, happen_time=record.inspected_at,
                detail=detail[:500], status="PENDING_HANDLE",
            )
            db.add(exception); db.flush()
            record.related_exception_id = exception.id
            rect = DormRectification(
                tenant_id=_tid(), check_record_id=record.id, task_id=task.id,
                building_id=room.building_id, room_id=room.id,
                student_id=int(student.id) if student else None,
                related_exception_id=exception.id, source_type="INSPECTION_RUNTIME",
                severity=severity, requirement=detail, deadline_at=deadline,
                status="OPEN", assignee_type="STUDENT" if student else "DORM_MANAGER",
                assignee_id=int(student.id) if student else None,
            )
            db.add(rect); db.flush()
            policy_for_record = {"riskSeverities": risk_severities}
            _create_risk_if_threshold(
                db, rect=rect, record=record, student=student, task=task, room=room,
                policy=policy_for_record,
            )
            _set_rectification_todo(db, rect, room_no=room.room_no, student=student)
            _emit_student_notice(
                db, rect=rect, event_code="DORM.RECTIFICATION.CREATED",
                title="宿舍检查有待整改项",
                content=f"{room.room_no} 室检查发现问题，请于 {_iso(deadline)} 前提交整改证据。",
            )
            dorm._audit(db, "DORM_RECTIFICATION", rect.id, "OPENED", f"severity={severity};record={record.id}")
        dorm._audit(
            db, "DORM_CHECK", record.id, computed_result,
            f"task={task.id};room={room.id};severity={severity};rectification={rect.id if rect else '-'}",
        )
        db.commit(); db.refresh(record)
        return _record_row(db, record)


def _record_row(db, record) -> dict:
    from app.models import DormRectification, DormRoom
    room = db.get(DormRoom, int(record.room_id)) if record.room_id else None
    rect = db.scalars(select(DormRectification).where(
        DormRectification.tenant_id == _tid(), DormRectification.check_record_id == int(record.id),
        DormRectification.is_deleted.is_(False),
    )).first()
    try:
        student_ids = [int(value) for value in (json.loads(record.student_ids_json or "[]") or [])]
    except (TypeError, ValueError):
        student_ids = []
    students = []
    if student_ids:
        from app.models import StudentProfile
        students = list(db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(student_ids),
            StudentProfile.is_deleted.is_(False),
        )).all())
    files = _files_for(db, "DORM_CHECK_RECORD", [int(record.id)]).get(int(record.id), [])
    return {
        "recordId": str(record.id), "taskId": str(record.task_id),
        "roomId": str(record.room_id or ""), "roomNo": room.room_no if room else "",
        "result": record.result, "severity": record.severity,
        "score": float(record.score) if record.score is not None else None,
        "itemResults": record.item_results_json or [], "issueType": record.issue_type or "",
        "detail": record.detail or "", "rectifyDeadline": _iso(record.rectify_deadline),
        "inspectedAt": _iso(record.inspected_at), "status": record.status,
        "students": [{"studentId": str(student.id), "realName": student.real_name, "studentNo": student.student_no} for student in students],
        "files": files, "fileIds": [item["fileId"] for item in files],
        "relatedExceptionId": str(record.related_exception_id or ""),
        "relatedRiskId": str(record.related_risk_id or ""),
        "rectificationId": str(rect.id if rect else ""),
        "rectificationStatus": rect.status if rect else "",
        "version": int(record.version or 0),
    }


def list_records(task_id: int, user: dict, page: int = 1, page_size: int = 100) -> tuple[list[dict], int]:
    if not has_permission(user or {}, "studentAffairs.dorm.view"):
        raise no_permission("无宿舍检查查看权限")
    from app.models import DormCheckRecord, DormCheckTask
    from app.services import affairs_dorm_service as dorm
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 100), 200))
    with session() as db:
        task = db.get(DormCheckTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _tid():
            raise not_found("检查任务不存在")
        dorm._require_dorm_scope(db, task.building_id, user)
        conds = [DormCheckRecord.tenant_id == _tid(), DormCheckRecord.task_id == int(task.id), DormCheckRecord.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(DormCheckRecord).where(*conds)) or 0)
        rows = list(db.scalars(select(DormCheckRecord).where(*conds).order_by(DormCheckRecord.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all())
        return [_record_row(db, record) for record in rows], total


def _resolve_student_actor(db, user: dict):
    from app.services.mobile_student_service import resolve_student
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        return None
    student = resolve_student(db, user or {})
    if not student:
        raise no_permission("尚未建立你的正式学生档案")
    return student


def _assert_rect_access(db, rect, user: dict, *, staff_permission: str = "studentAffairs.dorm.view"):
    from app.services import affairs_dorm_service as dorm
    student = _resolve_student_actor(db, user)
    if student:
        if not rect.student_id or int(rect.student_id) != int(student.id):
            raise no_permission("只能查看和处理本人整改")
        return student
    if not has_permission(user or {}, staff_permission):
        raise no_permission("无宿舍整改访问权限")
    dorm._require_dorm_scope(db, rect.building_id, user)
    return None


def _rect_row(db, rect, *, user: dict) -> dict:
    from app.models import DormBuilding, DormCheckRecord, DormCheckTask, DormRoom, StudentProfile
    task = tenant_get(db, DormCheckTask, int(rect.task_id))
    record = tenant_get(db, DormCheckRecord, int(rect.check_record_id))
    room = tenant_get(db, DormRoom, int(rect.room_id))
    building = tenant_get(db, DormBuilding, int(rect.building_id))
    student = tenant_get(db, StudentProfile, int(rect.student_id)) if rect.student_id else None
    inspection_files = _files_for(db, "DORM_CHECK_RECORD", [int(rect.check_record_id)]).get(int(rect.check_record_id), [])
    rect_files = _files_for(db, "DORM_RECTIFICATION", [int(rect.id)]).get(int(rect.id), [])
    is_student = str((user or {}).get("userType") or "").upper() == "STUDENT"
    actions = []
    if is_student:
        if rect.status == "OPEN": actions = ["START", "SUBMIT"]
        elif rect.status == "RECTIFYING": actions = ["SUBMIT"]
    elif has_permission(user or {}, "studentAffairs.dorm.inspection.manage"):
        if rect.status == "OPEN" and rect.assignee_type == "DORM_MANAGER": actions = ["START", "SUBMIT"]
        elif rect.status == "RECTIFYING" and rect.assignee_type == "DORM_MANAGER": actions = ["SUBMIT"]
        elif rect.status == "WAITING_RECHECK": actions = ["PASS", "RETURN", "ESCALATE"]
    return {
        "rectificationId": str(rect.id), "checkRecordId": str(rect.check_record_id),
        "taskId": str(rect.task_id), "taskName": task.task_name if task else "",
        "checkType": task.check_type if task else "", "buildingId": str(rect.building_id),
        "buildingName": building.building_name if building else "",
        "roomId": str(rect.room_id), "roomNo": room.room_no if room else "",
        "studentId": str(rect.student_id or ""), "studentName": student.real_name if student else "",
        "studentNo": student.student_no if student else "",
        "severity": rect.severity, "requirement": rect.requirement,
        "deadlineAt": _iso(rect.deadline_at), "overdue": bool(rect.status in RECTIFICATION_OPEN and rect.deadline_at < datetime.utcnow()),
        "status": rect.status, "assigneeType": rect.assignee_type, "assigneeId": str(rect.assignee_id or ""),
        "startedAt": _iso(rect.started_at), "rectifyNote": rect.rectify_note or "",
        "submittedAt": _iso(rect.submitted_at), "recheckNote": rect.recheck_note or "",
        "recheckedAt": _iso(rect.rechecked_at), "closedAt": _iso(rect.closed_at),
        "escalatedAt": _iso(rect.escalated_at), "relatedRiskId": str(rect.related_risk_id or ""),
        "inspectionDetail": record.detail if record else "", "inspectionScore": float(record.score) if record and record.score is not None else None,
        "inspectionFiles": inspection_files,
        "rectificationFiles": [item for item in rect_files if item["relationType"] == "RECTIFICATION_EVIDENCE"],
        "recheckFiles": [item for item in rect_files if item["relationType"] == "RECHECK_EVIDENCE"],
        "allowedActions": actions, "version": int(rect.version or 0), "createdAt": _iso(rect.created_at),
    }


def list_rectifications(user: dict, status: str | None = None, page: int = 1, page_size: int = 50, *, mine: bool = False) -> tuple[list[dict], int]:
    from app.models import DormRectification
    from app.services import affairs_dorm_service as dorm
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 50), 200))
    with session() as db:
        student = _resolve_student_actor(db, user)
        conds = [DormRectification.tenant_id == _tid(), DormRectification.is_deleted.is_(False)]
        if status:
            wanted = _text(status).upper()
            if wanted == "PENDING":
                conds.append(DormRectification.status.in_(RECTIFICATION_OPEN))
            elif wanted in {"OPEN", "RECTIFYING", "WAITING_RECHECK", "CLOSED", "ESCALATED"}:
                conds.append(DormRectification.status == wanted)
            else:
                raise AppException("VALIDATION_ERROR", "整改状态非法")
        if student:
            conds.append(DormRectification.student_id == int(student.id))
        else:
            if not has_permission(user or {}, "studentAffairs.dorm.view"):
                raise no_permission("无宿舍整改查看权限")
            scope = dorm._dorm_scope_building_ids(db, user)
            if scope is not None:
                conds.append(DormRectification.building_id.in_(scope or {-1}))
            if mine:
                actor_id = _actor_user_id(user)
                conds.append(and_(DormRectification.assignee_type == "DORM_MANAGER", DormRectification.assignee_id == actor_id))
        total = int(db.scalar(select(func.count()).select_from(DormRectification).where(*conds)) or 0)
        rows = list(db.scalars(select(DormRectification).where(*conds)
                               .order_by(DormRectification.deadline_at.asc(), DormRectification.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all())
        return [_rect_row(db, row, user=user) for row in rows], total


def get_rectification(rectification_id: int, user: dict) -> dict:
    from app.models import DormRectification
    with session() as db:
        rect = db.get(DormRectification, int(rectification_id))
        if not rect or rect.is_deleted or rect.tenant_id != _tid():
            raise not_found("整改记录不存在")
        _assert_rect_access(db, rect, user)
        return _rect_row(db, rect, user=user)


def start_rectification(rectification_id: int, *, expected_version: int, user: dict) -> dict:
    from app.models import DormRectification
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        rect = db.scalars(select(DormRectification).where(
            DormRectification.tenant_id == _tid(), DormRectification.id == int(rectification_id),
            DormRectification.is_deleted.is_(False),
        ).with_for_update()).first()
        if not rect:
            raise not_found("整改记录不存在")
        _assert_rect_access(db, rect, user, staff_permission="studentAffairs.dorm.inspection.manage")
        if rect.status != "OPEN":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该整改当前不能开始")
        atomic_claim_version(db, rect, expected_version)
        rect.status, rect.started_at, rect.version = "RECTIFYING", datetime.utcnow(), int(rect.version or 0) + 1
        dorm._audit(db, "DORM_RECTIFICATION", rect.id, "START", f"assignee={rect.assignee_type}:{rect.assignee_id}")
        db.commit(); db.refresh(rect)
        return _rect_row(db, rect, user=user)


def submit_rectification(rectification_id: int, body: Any, user: dict) -> dict:
    payload = _as_dict(body)
    note = _text(payload.get("note"))
    if not 5 <= len(note) <= 1000:
        raise AppException("VALIDATION_ERROR", "整改说明需5-1000字")
    request_id = _text(payload.get("clientRequestId"))
    if not 8 <= len(request_id) <= 100:
        raise AppException("VALIDATION_ERROR", "clientRequestId 长度须为8-100")
    file_ids = _normalize_file_ids(payload.get("fileIds"), required=True, label="整改照片证据")
    digest = hashlib.sha256(json.dumps({"note": note, "fileIds": sorted(file_ids)}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    from app.models import DormRectification, DormRoom, StudentProfile
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        rect = db.scalars(select(DormRectification).where(
            DormRectification.tenant_id == _tid(), DormRectification.id == int(rectification_id),
            DormRectification.is_deleted.is_(False),
        ).with_for_update()).first()
        if not rect:
            raise not_found("整改记录不存在")
        student_actor = _assert_rect_access(db, rect, user, staff_permission="studentAffairs.dorm.inspection.manage")
        if rect.last_client_request_id == request_id:
            if rect.last_submission_hash != digest:
                raise AppException("IDEMPOTENCY_CONFLICT", "同一 clientRequestId 的整改内容发生变化")
            return _rect_row(db, rect, user=user)
        reused = db.scalars(select(DormRectification).where(
            DormRectification.tenant_id == _tid(),
            DormRectification.last_client_request_id == request_id,
            DormRectification.id != int(rect.id),
            DormRectification.is_deleted.is_(False),
        )).first()
        if reused:
            raise AppException("IDEMPOTENCY_CONFLICT", "clientRequestId 已用于其他整改记录")
        if rect.status not in {"OPEN", "RECTIFYING"}:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该整改当前不可提交")
        expected = payload.get("expectedVersion")
        atomic_claim_version(db, rect, expected)
        room = tenant_get(db, DormRoom, int(rect.room_id))
        student = tenant_get(db, StudentProfile, int(rect.student_id)) if rect.student_id else student_actor
        _bind_files(
            db, file_ids=file_ids, biz_type="DORM_RECTIFICATION", biz_id=rect.id,
            relation_type="RECTIFICATION_EVIDENCE", actor=user, student=student, room=room,
            building_id=rect.building_id,
        )
        now = datetime.utcnow()
        rect.status, rect.rectify_note, rect.submitted_at = "WAITING_RECHECK", note, now
        rect.started_at = rect.started_at or now
        rect.last_client_request_id, rect.last_submission_hash = request_id, digest
        rect.version = int(rect.version or 0) + 1
        dorm._todo_done(db, rect.id, TODO_RECTIFY)
        _set_rectification_todo(db, rect, room_no=room.room_no if room else str(rect.room_id), student=student, recheck=True)
        dorm._audit(db, "DORM_RECTIFICATION", rect.id, "SUBMIT", f"files={len(file_ids)}")
        db.commit(); db.refresh(rect)
        return _rect_row(db, rect, user=user)


def recheck_rectification(rectification_id: int, body: Any, user: dict) -> dict:
    _require_staff(user)
    payload = _as_dict(body)
    action = _text(payload.get("action")).upper()
    if action not in {"PASS", "RETURN", "ESCALATE"}:
        raise AppException("VALIDATION_ERROR", "复检动作须为 PASS/RETURN/ESCALATE")
    note = _text(payload.get("note"))
    if not 5 <= len(note) <= 1000:
        raise AppException("VALIDATION_ERROR", "复检意见需5-1000字")
    from app.models import (AffairsRiskRecord, CsDormException, DormCheckRecord,
                            DormRectification, DormRoom, StudentProfile)
    from app.services import affairs_dorm_service as dorm
    policy = resolve_policy()
    with session() as db:
        rect = db.scalars(select(DormRectification).where(
            DormRectification.tenant_id == _tid(), DormRectification.id == int(rectification_id),
            DormRectification.is_deleted.is_(False),
        ).with_for_update()).first()
        if not rect:
            raise not_found("整改记录不存在")
        _assert_rect_access(db, rect, user, staff_permission="studentAffairs.dorm.inspection.manage")
        if rect.status != "WAITING_RECHECK":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该整改当前不在待复检状态")
        if action == "ESCALATE" and rect.severity not in {"HIGH", "CRITICAL"}:
            raise AppException("VALIDATION_ERROR", "普通卫生整改不得升级为学生风险")
        file_ids = _normalize_file_ids(
            payload.get("fileIds"), required=(action == "PASS" and rect.severity in policy["evidenceRequiredSeverities"]),
            label="高风险复检照片证据",
        )
        atomic_claim_version(db, rect, payload.get("expectedVersion"))
        room = tenant_get(db, DormRoom, int(rect.room_id))
        student = tenant_get(db, StudentProfile, int(rect.student_id)) if rect.student_id else None
        _bind_files(
            db, file_ids=file_ids, biz_type="DORM_RECTIFICATION", biz_id=rect.id,
            relation_type="RECHECK_EVIDENCE", actor=user, student=student, room=room,
            building_id=rect.building_id,
        )
        now = datetime.utcnow()
        rect.recheck_note, rect.rechecked_at, rect.rechecked_by_user_id = note, now, _actor_user_id(user)
        record = tenant_get(db, DormCheckRecord, int(rect.check_record_id))
        exception = tenant_get(db, CsDormException, int(rect.related_exception_id)) if rect.related_exception_id else None
        if action == "PASS":
            rect.status, rect.closed_at = "CLOSED", now
            if record: record.status = "CLOSED"
            if exception:
                exception.status, exception.handler, exception.handle_note, exception.handle_time = "HANDLED", _text(user.get("realName")), note[:500], now
            dorm._todo_done(db, rect.id, TODO_RECHECK)
            _emit_student_notice(db, rect=rect, event_code="DORM.RECTIFICATION.CLOSED", title="宿舍整改已通过复检", content=note)
        elif action == "RETURN":
            rect.status, rect.closed_at = "RECTIFYING", None
            if record: record.status = "RECTIFYING"
            dorm._todo_done(db, rect.id, TODO_RECHECK)
            _set_rectification_todo(db, rect, room_no=room.room_no if room else str(rect.room_id), student=student)
            _emit_student_notice(db, rect=rect, event_code="DORM.RECTIFICATION.RETURNED", title="宿舍整改复检未通过", content=note)
        else:
            rect.status, rect.escalated_at = "ESCALATED", now
            if record: record.status = "RECTIFYING"
            if rect.related_risk_id:
                risk = db.get(AffairsRiskRecord, int(rect.related_risk_id))
                if risk and risk.tenant_id == _tid() and not risk.is_deleted and risk.status != "CLOSED":
                    risk.status, risk.escalated_at, risk.version = "ESCALATED", now, int(risk.version or 0) + 1
            dorm._todo_done(db, rect.id, TODO_RECHECK)
            _emit_student_notice(db, rect=rect, event_code="DORM.RECTIFICATION.ESCALATED", title="宿舍整改已升级处置", content=note)
        rect.version = int(rect.version or 0) + 1
        dorm._audit(db, "DORM_RECTIFICATION", rect.id, f"RECHECK_{action}", f"files={len(file_ids)};note={note[:100]}")
        db.commit(); db.refresh(rect)
        return _rect_row(db, rect, user=user)
