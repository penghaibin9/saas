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
    """统一 members_json 条目；姓名仅作快照，不产生授权关系。"""
    if raw is None:
        return {"mentorId": None, "expertId": None, "name": "", "teacherNo": ""}
    if isinstance(raw, str):
        return {"mentorId": None, "expertId": None, "name": raw.strip(), "teacherNo": ""}
    if isinstance(raw, dict):
        mid = raw.get("mentorId") or raw.get("id")
        eid = raw.get("expertId")
        return {
            "mentorId": str(mid) if mid not in (None, "") else None,
            "expertId": str(eid) if eid not in (None, "") else None,
            "name": str(raw.get("name") or raw.get("realName") or raw.get("teacherName") or "").strip(),
            "teacherNo": str(raw.get("teacherNo") or "").strip(),
        }
    return {"mentorId": None, "expertId": None, "name": str(raw).strip(), "teacherNo": ""}


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
        if not item.get("name") and not item.get("mentorId") and not item.get("expertId"):
            continue
        key = item.get("mentorId") or (
            f"expert:{item.get('expertId')}" if item.get("expertId") else f"name:{item.get('name')}"
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge_person_fields(
    *,
    existing_mentor_id=None,
    existing_name: str | None = None,
    mentor_id=None,
    name: str | None = None,
    preserve_existing: bool = False,
    db=None,
) -> tuple[int | None, str | None]:
    """合并主席/秘书字段：有 ID 用 ID；仅姓名则写快照；都空且 preserve 则保留原值。"""
    if mentor_id not in (None, ""):
        if db is None:
            raise ValueError("db required when resolving mentor_id")
        m = require_mentor(db, mentor_id)
        return int(m.id), (m.teacher_name or "").strip() or None
    nm = (name or "").strip()
    if nm:
        # 仅姓名：若与原姓名相同则保留原 mentor_id，避免无意清掉已回填 ID
        if preserve_existing and existing_mentor_id and (existing_name or "").strip() == nm:
            return int(existing_mentor_id), nm
        return None, nm
    if preserve_existing:
        return (
            int(existing_mentor_id) if existing_mentor_id else None,
            (existing_name or "").strip() or None,
        )
    return None, None


def merge_members_fields(
    db,
    *,
    existing_members: list | None,
    member_ids: list | None = None,
    legacy_members: list | None = None,
    preserve_existing: bool = False,
) -> list:
    """成员合并：有 ID 列表优先；preserve 时保留未被 ID 覆盖的仅姓名席位。"""
    if member_ids:
        built = build_members_from_ids(db, member_ids, None)
        if not preserve_existing:
            return built
        # 显式传了 legacy_members 用它；未传则从 existing 抽出仅姓名席位
        if legacy_members is not None:
            name_only_raw = legacy_members
        else:
            name_only_raw = []
            for raw in (existing_members or []):
                item = normalize_member(raw)
                if item.get("mentorId"):
                    continue
                if item.get("name") or item.get("expertId"):
                    name_only_raw.append(item)
        covered_names = {(m.get("name") or "").strip() for m in built if m.get("name")}
        covered_ids = {str(m.get("mentorId")) for m in built if m.get("mentorId")}
        for raw in name_only_raw:
            item = normalize_member(raw)
            if item.get("mentorId") and str(item["mentorId"]) in covered_ids:
                continue
            if item.get("expertId"):
                built.append(item)
                continue
            nm = (item.get("name") or "").strip()
            if not nm or nm in covered_names:
                continue
            if item.get("mentorId"):
                # legacy 里偶发带 ID：并入
                m = get_mentor(db, item["mentorId"])
                if m:
                    snap = member_snapshot(m)
                    built.append(snap)
                    covered_ids.add(str(snap["mentorId"]))
                    covered_names.add(snap["name"])
                    continue
            built.append({"mentorId": None, "name": nm, "teacherNo": ""})
            covered_names.add(nm)
        return built
    if legacy_members:
        return build_members_from_ids(db, None, legacy_members)
    if preserve_existing and member_ids is None and legacy_members is None:
        return list(existing_members or [])
    if preserve_existing and member_ids == [] and not legacy_members:
        # 前端未选出任何 ID、也未传姓名时，视为未改成员而非清空
        return list(existing_members or [])
    return []


def judge_panel_seats(group) -> list[dict]:
    """应评分评委席位：稳定 mentorId/expertId + 姓名快照。"""
    seats: list[dict] = []
    if not group:
        return seats
    chair = (getattr(group, "chair", None) or "").strip()
    cid = getattr(group, "chair_mentor_id", None)
    if cid or chair:
        seats.append({
            "mentorId": int(cid) if cid else None,
            "expertId": None,
            "name": chair,
        })
    for raw in (getattr(group, "members_json", None) or []):
        item = normalize_member(raw)
        mid = int(item["mentorId"]) if item.get("mentorId") else None
        eid = int(item["expertId"]) if item.get("expertId") else None
        name = item.get("name") or ""
        if mid or eid or name:
            seats.append({"mentorId": mid, "expertId": eid, "name": name})
    return seats


def user_matches_judge_seat(seat: dict, *, mentor=None, expert_id=None, real_name: str = "") -> bool:
    """单席位匹配只认 mentorId/expertId；姓名参数仅为兼容调用签名。"""
    seat_id = seat.get("mentorId")
    seat_expert_id = seat.get("expertId")
    if mentor is not None and seat_id is not None and int(mentor.id) == int(seat_id):
        return True
    if expert_id not in (None, "") and seat_expert_id is not None and int(expert_id) == int(seat_expert_id):
        return True
    return False


def user_on_judge_panel(group, *, mentor=None, real_name: str = "") -> bool:
    """当前账号是否匹配稳定评委席位。"""
    from app.core.context import get_current_user_ctx
    expert_id = (get_current_user_ctx() or {}).get("expertId")
    return any(
        user_matches_judge_seat(seat, mentor=mentor, expert_id=expert_id)
        for seat in judge_panel_seats(group)
    )


def user_is_secretary(group, *, mentor=None, real_name: str = "") -> bool:
    sid = getattr(group, "secretary_mentor_id", None)
    return bool(sid is not None and mentor and int(mentor.id) == int(sid))


def score_row_covers_seat(row, seat: dict) -> bool:
    """A score covers a seat only when its stable mentor/expert identity matches."""
    if getattr(row, "status", None) not in ("SCORED", "CONFIRMED"):
        return False
    seat_id = seat.get("mentorId")
    row_id = getattr(row, "judge_mentor_id", None)
    if seat_id is not None and row_id is not None and int(seat_id) == int(row_id):
        return True
    seat_expert_id = seat.get("expertId")
    row_expert_id = getattr(row, "expert_id", None)
    return bool(
        seat_expert_id is not None and row_expert_id is not None
        and int(seat_expert_id) == int(row_expert_id)
    )


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
