"""毕业设计域 · 稳定身份辅助（导师/评委 ID + 姓名快照）。

权限与回避优先比 mentor_id / teacher_no；姓名仅作展示与历史兜底。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import not_found
from app.models import GraduationMentor
from app.services.db_service import _tid


def login_name() -> str:
    return str((get_current_user_ctx() or {}).get("loginName") or "").strip()


def get_mentor(db, mentor_id) -> GraduationMentor | None:
    if mentor_id is None or mentor_id == "":
        return None
    m = db.get(GraduationMentor, int(mentor_id))
    if not m or m.is_deleted or m.tenant_id != _tid():
        return None
    return m


def require_mentor(db, mentor_id) -> GraduationMentor:
    m = get_mentor(db, mentor_id)
    if not m:
        raise not_found("毕设导师台账不存在或不在当前租户")
    return m


def mentor_by_teacher_no(db, teacher_no: str, tenant_id=None) -> GraduationMentor | None:
    no = (teacher_no or "").strip()
    if not no:
        return None
    tid = int(tenant_id) if tenant_id is not None else _tid()
    return db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == tid,
        GraduationMentor.teacher_no == no,
        GraduationMentor.is_deleted.is_(False),
    ).limit(1)).first()


def current_user_mentor(db, tenant_id=None) -> GraduationMentor | None:
    """当前登录者对应的导师台账（teacher_no == loginName）。"""
    return mentor_by_teacher_no(db, login_name(), tenant_id=tenant_id)


def normalize_member(raw) -> dict:
    """统一 members_json 条目：{mentorId, name, teacherNo}。兼容历史纯字符串。"""
    if raw is None:
        return {"mentorId": None, "name": "", "teacherNo": ""}
    if isinstance(raw, str):
        return {"mentorId": None, "name": raw.strip(), "teacherNo": ""}
    if isinstance(raw, dict):
        mid = raw.get("mentorId") or raw.get("id")
        return {
            "mentorId": str(mid) if mid not in (None, "") else None,
            "name": str(raw.get("name") or raw.get("realName") or raw.get("teacherName") or "").strip(),
            "teacherNo": str(raw.get("teacherNo") or "").strip(),
        }
    return {"mentorId": None, "name": str(raw).strip(), "teacherNo": ""}


def member_snapshot(m: GraduationMentor) -> dict:
    return {
        "mentorId": str(m.id),
        "name": (m.teacher_name or "").strip(),
        "teacherNo": (m.teacher_no or "").strip(),
    }


def build_members_from_ids(db, member_ids: list | None, legacy_members: list | None = None) -> list[dict]:
    """优先 memberMentorIds；否则规范化 legacy members（字符串或 dict）。"""
    out: list[dict] = []
    seen: set[str] = set()
    if member_ids:
        for mid in member_ids:
            m = require_mentor(db, mid)
            snap = member_snapshot(m)
            key = snap["mentorId"]
            if key in seen:
                continue
            seen.add(key)
            out.append(snap)
        return out
    for raw in (legacy_members or []):
        item = normalize_member(raw)
        if item.get("mentorId"):
            m = get_mentor(db, item["mentorId"])
            if m:
                item = member_snapshot(m)
        if not item.get("name") and not item.get("mentorId"):
            continue
        key = item.get("mentorId") or f"name:{item.get('name')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def resolve_chair_secretary(db, *, mentor_id=None, name: str | None = None) -> tuple[int | None, str]:
    """写路径：有 mentorId 则解析姓名快照；仅姓名时不伪造 ID。"""
    if mentor_id not in (None, ""):
        m = require_mentor(db, mentor_id)
        return int(m.id), (m.teacher_name or "").strip()
    return None, (name or "").strip()


def panel_mentor_ids(group) -> set[int]:
    ids: set[int] = set()
    for attr in ("chair_mentor_id", "secretary_mentor_id"):
        mid = getattr(group, attr, None)
        if mid:
            ids.add(int(mid))
    for raw in (getattr(group, "members_json", None) or []):
        item = normalize_member(raw)
        if item.get("mentorId"):
            ids.add(int(item["mentorId"]))
    return ids


def panel_names(group) -> set[str]:
    names: set[str] = set()
    for attr in ("chair", "secretary"):
        n = (getattr(group, attr, None) or "").strip()
        if n:
            names.add(n)
    for raw in (getattr(group, "members_json", None) or []):
        item = normalize_member(raw)
        if item.get("name"):
            names.add(item["name"])
    return names


def judge_panel_names(group) -> list[str]:
    """应评分评委展示名：主席 + 成员（不含秘书）。"""
    names: list[str] = []
    chair = (getattr(group, "chair", None) or "").strip()
    if chair:
        names.append(chair)
    for raw in (getattr(group, "members_json", None) or []):
        item = normalize_member(raw)
        n = item.get("name") or ""
        if n and n not in names:
            names.append(n)
    return names


def judge_panel_mentor_ids(group) -> set[int]:
    ids: set[int] = set()
    if getattr(group, "chair_mentor_id", None):
        ids.add(int(group.chair_mentor_id))
    for raw in (getattr(group, "members_json", None) or []):
        item = normalize_member(raw)
        if item.get("mentorId"):
            ids.add(int(item["mentorId"]))
    return ids


def student_advisor_mentor_ids(db, student) -> set[int]:
    ids: set[int] = set()
    mid = getattr(student, "mentor_id", None)
    if mid:
        ids.add(int(mid))
    return ids


def sod_conflict_with_advisor(db, student, reviewer_mentor_id=None, reviewer_name: str = "") -> bool:
    """评阅 SoD：评阅人不得是该生指导教师（比 mentor_id，姓名仅兜底）。"""
    advisor_ids = student_advisor_mentor_ids(db, student)
    if reviewer_mentor_id and int(reviewer_mentor_id) in advisor_ids:
        return True
    names = {(getattr(student, "advisor_name", None) or "").strip()}
    if getattr(student, "mentor_id", None):
        m = get_mentor(db, student.mentor_id)
        if m:
            names.add((m.teacher_name or "").strip())
    if getattr(student, "topic_id", None):
        from app.models import GraduationTopic
        t = db.get(GraduationTopic, int(student.topic_id))
        if t and not t.is_deleted and t.tenant_id == _tid():
            names.add((t.advisor_name or "").strip())
    names.discard("")
    rn = (reviewer_name or "").strip()
    if rn and rn in names:
        # 若评阅人有稳定 ID 且不在顾问 ID 集合，以 ID 为准（同名不误伤）
        if reviewer_mentor_id and int(reviewer_mentor_id) not in advisor_ids:
            return False
        return True
    return False


def assert_member_not_advisor(db, student, panel_ids: set[int], panel_name_set: set[str]) -> str | None:
    """返回冲突导师展示名；无冲突返回 None。"""
    advisor_ids = student_advisor_mentor_ids(db, student)
    if advisor_ids & panel_ids:
        m = get_mentor(db, next(iter(advisor_ids & panel_ids)))
        return (m.teacher_name if m else None) or (getattr(student, "advisor_name", None) or "指导教师")
    an = (getattr(student, "advisor_name", None) or "").strip()
    if an and an in panel_name_set and not advisor_ids:
        return an
    return None
