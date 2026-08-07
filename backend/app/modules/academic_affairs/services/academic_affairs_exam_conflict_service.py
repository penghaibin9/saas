"""考务发布前的全局资源冲突门禁（P0-D02）。

既有冲突检测都是「编排某一项时看这一项」——排监考时查这个老师、排巡考时查这个老师。
缺的是发布那一刻的一次性全局扫描：把整个批次即将成为正式事实的资源占用，和**全校已发布的
其它批次**放在一起比对。没有它，两个批次各自内部合法，同一间教室、同一个学生、同一个老师
仍然可以在同一时段被排两次。

四类资源占用统一建模：ROOM / STUDENT / INVIGILATOR / PATROL。
- ROOM 只认 canonical classroom_id。人工考场只填 classroom_text 时，"一教301""1教301""第一
  教学楼301"是三个互不相等的字符串，按文本比对等于放弃教室冲突检测，所以发布时强制要求
  classroom_id，解析不出来直接挡下，让教务去选正式教室而不是打字。
- 时段重叠沿用 exam_service._time_overlap 的同一套判定，不另起一套规则。

本模块只做只读校验并返回问题清单，不写库、不改状态；调用方在发布事务内决定如何处置。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.db_service import _tid

from . import academic_affairs_exam_service as _exam

# 已经对外成立、必须参与资源竞争的批次状态；DRAFT/COURSE_CONFIRMED/ARRANGED 还没对学生生效。
_LIVE_BATCH_STATUSES = ("PUBLISHED", "FINISHED")


def _overlap(left, right) -> bool:
    return _exam._time_overlap(
        left["examDate"], left["startTime"], left["endTime"],
        right["examDate"], right["startTime"], right["endTime"],
    )


def _course_slot(course) -> dict:
    return {
        "examCourseId": int(course.id),
        "batchId": int(course.batch_id),
        "courseName": course.course_name or f"课程{course.id}",
        "examDate": course.exam_date,
        "startTime": course.start_time,
        "endTime": course.end_time,
    }


def _supports_share_lock(db) -> bool:
    """SQLite 没有共享行锁；只有 MySQL 需要也支持这套读一致性处理。"""
    try:
        return db.get_bind().dialect.name == "mysql"
    except Exception:  # noqa: BLE001  取不到方言时保守走普通读
        return False


def _read(query, fresh: bool, db):
    """fresh=True 时走加锁读。

    MySQL 默认 REPEATABLE READ：事务里只要发生过一次普通读，读视图就定格了；此后即使拿到行锁、
    对方事务也已提交，普通读看到的仍是旧快照——锁住了却读到陈数据，冲突自然检测不出来。
    加锁读（FOR SHARE）总是读最新已提交版本，绕开这个快照。发布已被同学期批次排他锁串行化，
    因此这里的共享锁不会在发布者之间产生额外争用。
    """
    if fresh and _supports_share_lock(db):
        return query.with_for_update(read=True).all()
    return query.all()


def _collect_occupancy(db, batch_ids, *, fresh: bool = False):
    """把一批考试批次展开成四类资源占用条目。"""
    from app.models import (AaExamCourse, AaExamInvigilator, AaExamPatrol, AaExamRoom,
                            AaExamRoomStudent)

    batch_ids = [int(value) for value in batch_ids]
    if not batch_ids:
        return [], []

    courses = _read(db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.batch_id.in_(batch_ids),
        AaExamCourse.status == "CONFIRMED",
        AaExamCourse.is_deleted.is_(False),
    ), fresh, db)
    course_by_id = {int(row.id): row for row in courses}
    course_ids = list(course_by_id) or [0]

    rooms = _read(db.query(AaExamRoom).filter(
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.exam_course_id.in_(course_ids),
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    ), fresh, db)
    room_by_id = {int(row.id): row for row in rooms}
    room_ids = list(room_by_id) or [0]

    occupancy = []
    missing_identity = []
    for room in rooms:
        course = course_by_id.get(int(room.exam_course_id))
        if not course:
            continue
        slot = _course_slot(course)
        if not room.classroom_id:
            missing_identity.append({
                "examCourseId": str(course.id),
                "courseName": slot["courseName"],
                "roomSeq": room.room_seq,
                "classroomText": room.classroom_text,
            })
            continue
        occupancy.append({
            **slot, "resourceType": "ROOM", "resourceId": str(int(room.classroom_id)),
            "resourceLabel": room.classroom_text or f"教室{room.classroom_id}",
            "examRoomId": int(room.id),
        })

    seats = _read(db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == _tid(),
        AaExamRoomStudent.exam_room_id.in_(room_ids),
        AaExamRoomStudent.is_deleted.is_(False),
    ), fresh, db)
    for seat in seats:
        course = course_by_id.get(int(seat.exam_course_id))
        if not course:
            continue
        occupancy.append({
            **_course_slot(course), "resourceType": "STUDENT",
            "resourceId": str(int(seat.student_id)),
            "resourceLabel": seat.student_name or seat.student_no or f"学生{seat.student_id}",
        })

    invigilators = _read(db.query(AaExamInvigilator).filter(
        AaExamInvigilator.tenant_id == _tid(),
        AaExamInvigilator.exam_room_id.in_(room_ids),
        AaExamInvigilator.is_deleted.is_(False),
    ), fresh, db)
    for row in invigilators:
        room = room_by_id.get(int(row.exam_room_id))
        course = course_by_id.get(int(room.exam_course_id)) if room else None
        if not course:
            continue
        occupancy.append({
            **_course_slot(course), "resourceType": "INVIGILATOR",
            "resourceId": str(row.teacher_key or ""),
            "resourceLabel": row.teacher_name or row.teacher_key or "",
        })

    patrols = _read(db.query(AaExamPatrol).filter(
        AaExamPatrol.tenant_id == _tid(),
        AaExamPatrol.batch_id.in_(batch_ids),
        AaExamPatrol.status != "CANCELLED",
        AaExamPatrol.is_deleted.is_(False),
    ), fresh, db)
    for row in patrols:
        occupancy.append({
            "examCourseId": None, "batchId": int(row.batch_id), "courseName": "巡考",
            "examDate": row.patrol_date, "startTime": row.start_time, "endTime": row.end_time,
            "resourceType": "PATROL", "resourceId": str(row.teacher_key or ""),
            "resourceLabel": row.teacher_name or row.teacher_key or "",
        })

    return occupancy, missing_identity


def _live_batch_ids(db, term_id, exclude_batch_id):
    """同学期已经对外成立的其它批次——它们的占用是既成事实，本批次必须绕开。"""
    from app.models import AaExamBatch

    # 必须读到并发发布者刚提交的最新状态，因此走加锁读而不是普通读（见 _read 注释）。
    rows = _read(db.query(AaExamBatch.id).filter(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.term_id == int(term_id),
        AaExamBatch.id != int(exclude_batch_id),
        AaExamBatch.status.in_(_LIVE_BATCH_STATUSES),
        AaExamBatch.is_deleted.is_(False),
    ), True, db)
    return [int(value) for (value,) in rows]


def lock_term_exam_batches(db, term_id) -> None:
    """把同学期全部考务批次按 id 顺序上行锁，让「检测→发布」整体串行。

    两个批次同时抢同一间教室时，各自只锁自己那行是拦不住的：双方都先查到无冲突，再各自
    INSERT，两边都 PUBLISHED。这里统一锁同学期批次行——一学期发布次数本来就少，串行代价可以
    忽略；按 id 排序取锁，避免两个事务反向加锁死锁。
    """
    from app.models import AaExamBatch

    db.query(AaExamBatch.id).filter(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.term_id == int(term_id),
        AaExamBatch.is_deleted.is_(False),
    ).order_by(AaExamBatch.id).with_for_update().all()


_RESOURCE_LABEL = {
    "ROOM": "教室", "STUDENT": "考生", "INVIGILATOR": "监考教师", "PATROL": "巡考教师",
}
_RESOURCE_CODE = {
    "ROOM": "ROOM_CONFLICT", "STUDENT": "STUDENT_EXAM_CONFLICT",
    "INVIGILATOR": "INVIGILATOR_CONFLICT", "PATROL": "PATROL_CONFLICT",
}


def _describe(entry) -> str:
    when = f"{entry['examDate'] or '?'} {entry['startTime'] or '?'}-{entry['endTime'] or '?'}"
    return f"{entry['courseName']}（{when}）"


def validate_exam_batch_conflicts(db, batch, *, term_id=None) -> dict:
    """发布前一次性扫描四类资源占用，返回 {'problems': [...], 'occupancy': N}。

    同时覆盖批次内部（本批次两门课互撞）和跨批次（本批次撞已发布批次）。
    监考与巡考视为同一个人的同一份时间，因此 INVIGILATOR 和 PATROL 之间也要比对。
    """
    term_id = term_id if term_id is not None else batch.term_id
    if not term_id:
        raise AppException("DATA_CONFLICT", "考务批次未绑定正式学期，无法执行发布冲突门禁", http_status=409)

    own, missing_identity = _collect_occupancy(db, [int(batch.id)])
    problems = []
    for item in missing_identity:
        problems.append(
            f"CLASSROOM_IDENTITY_MISSING：{item['courseName']} 考场{item['roomSeq']}"
            f"（{item['classroomText'] or '未填写'}）未匹配到正式教室，无法参与教室冲突检测"
        )

    others, _ignored = _collect_occupancy(db, _live_batch_ids(db, term_id, batch.id), fresh=True)

    # 教师的一份时间同时受监考和巡考约束，归一到同一个资源身份下比对。
    def _key(entry):
        kind = entry["resourceType"]
        if kind in ("INVIGILATOR", "PATROL"):
            return ("TEACHER", entry["resourceId"])
        return (kind, entry["resourceId"])

    buckets = {}
    for entry in own:
        buckets.setdefault(_key(entry), {"own": [], "other": []})["own"].append(entry)
    for entry in others:
        key = _key(entry)
        if key in buckets:
            buckets[key]["other"].append(entry)

    seen = set()
    for (kind, resource_id), group in buckets.items():
        items = group["own"]
        for index, left in enumerate(items):
            for right in items[index + 1:]:
                if left["examCourseId"] and left["examCourseId"] == right["examCourseId"]:
                    continue  # 同一门考试的多个考场/多名监考本来就同时段
                if not _overlap(left, right):
                    continue
                code = _RESOURCE_CODE.get(left["resourceType"], "RESOURCE_CONFLICT")
                signature = (code, resource_id, left["examCourseId"], right["examCourseId"])
                if signature in seen:
                    continue
                seen.add(signature)
                label = _RESOURCE_LABEL.get(left["resourceType"], "资源")
                problems.append(
                    f"{code}：{label} {left['resourceLabel']} 在 {_describe(left)} "
                    f"与 {_describe(right)} 时间重叠"
                )
            for right in group["other"]:
                if not _overlap(left, right):
                    continue
                code = _RESOURCE_CODE.get(left["resourceType"], "RESOURCE_CONFLICT")
                signature = (code, resource_id, left["examCourseId"], right["batchId"], right["examCourseId"])
                if signature in seen:
                    continue
                seen.add(signature)
                label = _RESOURCE_LABEL.get(left["resourceType"], "资源")
                problems.append(
                    f"{code}：{label} {left['resourceLabel']} 在 {_describe(left)} "
                    f"与已发布批次的 {_describe(right)} 时间重叠"
                )

    return {"problems": problems, "occupancy": len(own), "comparedAgainst": len(others)}
