"""课表唯一正式版本（P0-D05）。

既有排课门禁只回答「这个批次内部有没有冲突」，回答不了两个更要命的问题：

1. 同一学期可以并存多个 PUBLISHED 批次——那学生的正式课表到底是哪一份？
2. 学院 A 和学院 B 各自发布，两边批次内部都合法，但张老师、301 教室、以及跨学院上课的
   学生是全校共享的，同一时段照样被排两次。

本模块用「范围头 + 顶替链」回答问题一：一个(学期,范围)在任一时刻只有一个 active_batch_id，
换版必须显式把旧批次标 SUPERSEDED，而不是再造一份 PUBLISHED。
用「全校共享资源扫描」回答问题二：无论批次自身是不是学院级，教师、教室、学生一律拿到全校
当前正式课表里比对。

发布顺序固定为：锁范围头 → 校验当前 active → 全校资源冲突 → CAS 换版 → 旧版 SUPERSEDED。
锁必须早于校验，否则两个事务会双双查到"无冲突"再双双发布。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.services.db_service import _tid

_SCHOOL = "SCHOOL"
_COLLEGE = "COLLEGE"
# 已经对外成立、必须参与资源竞争的课表状态。
_LIVE_STATUSES = ("PUBLISHED",)


def scope_of(batch) -> tuple[str, int]:
    """批次落在哪个范围。college_id 为空表示全校排课。

    全校范围的 scope_id 落 0 而不是 NULL：MySQL 唯一索引里 NULL 互不相等，用 NULL 会让
    (学期,全校) 出现任意多行，唯一性形同虚设。
    """
    college_id = getattr(batch, "college_id", None)
    if college_id:
        return _COLLEGE, int(college_id)
    return _SCHOOL, 0


def lock_scope_head(db, term_id, scope_type, scope_id):
    """取本(学期,范围)的范围头行锁；不存在则先建再锁，保证并发只有一个赢家。"""
    from app.models import AaScheduleScopeHead

    def _query():
        return db.query(AaScheduleScopeHead).filter(
            AaScheduleScopeHead.tenant_id == _tid(),
            AaScheduleScopeHead.term_id == int(term_id),
            AaScheduleScopeHead.scope_type == scope_type,
            AaScheduleScopeHead.scope_id == int(scope_id),
            AaScheduleScopeHead.is_deleted.is_(False),
        )

    head = _query().with_for_update().first()
    if head:
        return head
    # 并发下另一个事务可能抢先插入同键，唯一约束会让本次 INSERT 失败。用 savepoint 包住：
    # 裸 db.rollback() 会把整个发布事务一起回滚掉，这里只回滚这一小段，再改读对方那一行。
    # 进 savepoint 前先 flush 已有待写数据，否则它们会被卷进这个 savepoint 一起回滚。
    db.flush()
    try:
        with db.begin_nested():
            head = AaScheduleScopeHead(
                tenant_id=_tid(), term_id=int(term_id), scope_type=scope_type,
                scope_id=int(scope_id), active_batch_id=None, version=0,
            )
            db.add(head)
            db.flush()
    except IntegrityError:
        head = None
    # 重新加锁读，确保拿到的是行锁而不仅仅是本事务的待插入对象
    return _query().with_for_update().first() or head


def active_batch_id(db, term_id, scope_type, scope_id):
    from app.models import AaScheduleScopeHead

    head = db.query(AaScheduleScopeHead).filter(
        AaScheduleScopeHead.tenant_id == _tid(),
        AaScheduleScopeHead.term_id == int(term_id),
        AaScheduleScopeHead.scope_type == scope_type,
        AaScheduleScopeHead.scope_id == int(scope_id),
        AaScheduleScopeHead.is_deleted.is_(False),
    ).first()
    return int(head.active_batch_id) if head and head.active_batch_id else None


def _supports_share_lock(db) -> bool:
    try:
        return db.get_bind().dialect.name == "mysql"
    except Exception:  # noqa: BLE001
        return False


def _fresh(query, db):
    """加锁读：MySQL REPEATABLE READ 下普通读会停在事务开始时的快照，
    看不见并发发布者刚提交的占用；加锁读总是读最新已提交版本。"""
    if _supports_share_lock(db):
        return query.with_for_update(read=True).all()
    return query.all()


def _live_batch_ids(db, term_id, exclude_batch_id):
    """同学期全部当前正式课表批次——不分学院，教师和教室是全校共享资源。"""
    from app.models import AaScheduleBatch

    rows = _fresh(db.query(AaScheduleBatch.id).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == int(term_id),
        AaScheduleBatch.id != int(exclude_batch_id),
        AaScheduleBatch.status.in_(_LIVE_STATUSES),
        AaScheduleBatch.is_deleted.is_(False),
    ), db)
    return [int(value) for (value,) in rows]


def _items(db, batch_ids, *, fresh=False):
    from app.models import AaScheduleItem

    batch_ids = [int(value) for value in batch_ids]
    if not batch_ids:
        return []
    query = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(batch_ids),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    )
    return _fresh(query, db) if fresh else query.all()


def _weeks_overlap(left, right) -> bool:
    """周次区间相交，且单双周不互斥。"""
    left_start = int(getattr(left, "start_week", 0) or 0)
    left_end = int(getattr(left, "end_week", 0) or 0) or left_start
    right_start = int(getattr(right, "start_week", 0) or 0)
    right_end = int(getattr(right, "end_week", 0) or 0) or right_start
    if left_end < right_start or right_end < left_start:
        return False
    left_parity = str(getattr(left, "week_parity", None) or "ALL").upper()
    right_parity = str(getattr(right, "week_parity", None) or "ALL").upper()
    if left_parity in ("ODD", "EVEN") and right_parity in ("ODD", "EVEN"):
        return left_parity == right_parity
    return True


def _slot_key(item):
    return (int(item.weekday or 0), int(item.slot_no or 0))


_RESOURCE_CODE = {
    "TEACHER": "TEACHER_SCHEDULE_CONFLICT",
    "CLASSROOM": "CLASSROOM_SCHEDULE_CONFLICT",
    "CLASS": "CLASS_SCHEDULE_CONFLICT",
}
_RESOURCE_LABEL = {"TEACHER": "教师", "CLASSROOM": "教室", "CLASS": "班级"}


def _resources(item):
    """一条课表行占用的全校共享资源。

    教室只认 canonical classroom_id：人工填的教室文本"一教301""1教301"是不同字符串，
    按文本比对等于放弃跨批次教室冲突检测。
    """
    out = []
    if item.teacher_key:
        out.append(("TEACHER", str(item.teacher_key), item.teacher_name or item.teacher_key))
    classroom_id = getattr(item, "classroom_id", None)
    if classroom_id:
        out.append(("CLASSROOM", str(int(classroom_id)),
                    getattr(item, "classroom_text", None) or f"教室{classroom_id}"))
    if item.class_id:
        out.append(("CLASS", str(int(item.class_id)), item.class_name or f"班级{item.class_id}"))
    return out


def _describe(item) -> str:
    weeks = f"{getattr(item, 'start_week', '?')}-{getattr(item, 'end_week', '?')}周"
    return f"{item.course_name or '课程'}（周{item.weekday} 第{item.slot_no}节 {weeks}）"


def validate_school_wide_conflicts(db, batch) -> dict:
    """把本批次课表行与全校当前正式课表比对，返回问题清单。

    只比对跨批次：批次内部冲突由既有 gate_service 负责，不在这里重复实现第二套规则。
    """
    own = _items(db, [int(batch.id)])
    others = _items(db, _live_batch_ids(db, batch.term_id, batch.id), fresh=True)
    if not own or not others:
        return {"problems": [], "items": len(own), "comparedAgainst": len(others)}

    index = {}
    for item in others:
        for kind, resource_id, _label in _resources(item):
            index.setdefault((kind, resource_id, _slot_key(item)), []).append(item)

    problems = []
    seen = set()
    for item in own:
        slot = _slot_key(item)
        for kind, resource_id, label in _resources(item):
            for other in index.get((kind, resource_id, slot), []):
                if not _weeks_overlap(item, other):
                    continue
                signature = (kind, resource_id, slot, int(other.batch_id))
                if signature in seen:
                    continue
                seen.add(signature)
                problems.append(
                    f"{_RESOURCE_CODE[kind]}：{_RESOURCE_LABEL[kind]} {label} 在 {_describe(item)} "
                    f"与已发布课表的 {_describe(other)} 冲突"
                )
    return {"problems": problems, "items": len(own), "comparedAgainst": len(others)}


def promote_to_active(db, batch, head) -> dict:
    """CAS 换版：旧 active 标 SUPERSEDED，本批次成为该范围唯一正式课表。"""
    from app.models import AaScheduleBatch

    previous_id = int(head.active_batch_id) if head.active_batch_id else None
    if previous_id and previous_id != int(batch.id):
        previous = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == previous_id,
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if previous and previous.status == "PUBLISHED":
            previous.status = "SUPERSEDED"
        batch.supersedes_batch_id = previous_id
    head.active_batch_id = int(batch.id)
    head.version = int(head.version or 0) + 1
    head.published_at = datetime.utcnow()
    return {
        "scopeType": head.scope_type,
        "scopeId": str(head.scope_id),
        "activeBatchId": str(head.active_batch_id),
        "headVersion": head.version,
        "supersededBatchId": str(previous_id) if previous_id and previous_id != int(batch.id) else None,
    }


def require_no_school_wide_conflict(db, batch) -> dict:
    result = validate_school_wide_conflicts(db, batch)
    if result["problems"]:
        found = result["problems"]
        raise AppException(
            "DATA_CONFLICT",
            "与全校当前正式课表存在共享资源冲突，不可发布："
            + "；".join(found[:5]) + ("…" if len(found) > 5 else ""),
            details={"conflicts": found[:50]},
            http_status=409,
        )
    return result
