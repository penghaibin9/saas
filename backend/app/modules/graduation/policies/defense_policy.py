"""包 9：毕业设计答辩写入的四重权威门禁。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import GraduationBatch, GraduationDefenseGroup

from .base import authorize_student_action

_READ_ACTIONS = {"view", "list", "detail", "stats", "export"}


def _date_value(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _stage_rows(stage_config) -> list[dict]:
    if isinstance(stage_config, list):
        return [item for item in stage_config if isinstance(item, dict)]
    if isinstance(stage_config, dict):
        for key in ("stages", "phases", "items"):
            rows = stage_config.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _defense_phase_open(batch: GraduationBatch, *, today: date | None = None) -> bool:
    """批次必须运行中；显式阶段配置存在时 DEFENSE 必须启用且在时间窗内。"""
    if str(batch.status or "").upper() != "RUNNING":
        return False
    rows = _stage_rows(batch.stage_config)
    if not rows:
        # 兼容未配置阶段时间轴的历史运行中批次；新配置一旦存在即严格执行。
        return True
    defense = next(
        (item for item in rows if str(item.get("code") or item.get("key") or "").upper() == "DEFENSE"),
        None,
    )
    if not defense or defense.get("enabled") is False:
        return False
    status = str(defense.get("status") or "").upper()
    if status in {"CLOSED", "DISABLED", "LOCKED", "PAUSED", "DRAFT"}:
        return False
    current = today or date.today()
    start_raw = defense.get("startDate") or defense.get("start_at") or defense.get("startAt")
    end_raw = defense.get("endDate") or defense.get("end_at") or defense.get("endAt")
    start = _date_value(start_raw)
    end = _date_value(end_raw)
    if start_raw not in (None, "") and start is None:
        return False
    if end_raw not in (None, "") and end is None:
        return False
    if start and current < start:
        return False
    if end and current > end:
        return False
    return True


def _requires_write_gate(action: str) -> bool:
    value = str(action or "view").strip().lower()
    return not (value in _READ_ACTIONS or value.startswith("view") or value.startswith("list"))


def authorize(db, student, action="view"):
    result = authorize_student_action(
        db,
        student,
        action=f"defense.{action}",
        permission_code=f"graduationDesign.defense.{action}",
    )
    if not _requires_write_gate(action):
        return result

    if str(student.stage or "").upper() != "DEFENSE":
        raise AppException("DATA_CONFLICT", "学生尚未进入答辩阶段，禁止写入答辩事实")
    if not student.batch_id:
        raise AppException("DATA_CONFLICT", "学生未绑定有效毕设批次")

    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.id == int(student.batch_id),
        GraduationBatch.tenant_id == int(student.tenant_id),
        GraduationBatch.is_deleted.is_(False),
    )).first()
    if not batch or not _defense_phase_open(batch):
        raise AppException("DATA_CONFLICT", "当前批次答辩阶段未开放")

    if not student.defense_group_id:
        raise AppException("DATA_CONFLICT", "学生尚未绑定答辩组")
    group = db.scalars(select(GraduationDefenseGroup).where(
        GraduationDefenseGroup.id == int(student.defense_group_id),
        GraduationDefenseGroup.tenant_id == int(student.tenant_id),
        GraduationDefenseGroup.batch_id == int(student.batch_id),
        GraduationDefenseGroup.is_deleted.is_(False),
    )).first()
    if not group:
        raise AppException("DATA_CONFLICT", "学生答辩组不存在或与批次不一致")
    if not bool(group.published):
        raise AppException("DATA_CONFLICT", "答辩组尚未发布，禁止写入答辩事实")
    return result