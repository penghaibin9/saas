"""Unmodified pure placement functions extracted from the user-approved archive. No app startup or DB."""

from __future__ import annotations

def _weeks_overlap(s1, e1, p1, s2, e2, p2) -> bool:
    """周次区间相交 且 单双周相容（ALL 与任何相容；ODD 仅与 ODD/ALL；EVEN 仅与 EVEN/ALL）。"""
    if e1 < s2 or e2 < s1:  # 区间不相交
        return False
    if p1 == "ALL" or p2 == "ALL" or p1 == p2:
        return True
    return False

class _Grid:
    """课表占用索引。key→[(start_week,end_week,parity)]，判重用周次相容语义（与手工排课同源）。"""

    def __init__(self):
        self.teacher = {}
        self.klass = {}
        self.room = {}
        self.class_day = {}    # (class_id, weekday) → 已排节数
        self.teacher_day = {}  # (teacher_key, weekday) → 已排节数

    @staticmethod
    def _hit(bucket, key, sw, ew, par) -> bool:
        for (s, e, p) in bucket.get(key, ()):
            if _weeks_overlap(sw, ew, par, s, e, p):
                return True
        return False

    @staticmethod
    def _put(bucket, key, sw, ew, par):
        bucket.setdefault(key, []).append((sw, ew, par))

    def teacher_busy(self, tk, wd, sl, sw, ew, par):
        return bool(tk) and self._hit(self.teacher, (tk, wd, sl), sw, ew, par)

    def class_busy(self, cid, wd, sl, sw, ew, par):
        return bool(cid) and self._hit(self.klass, (int(cid), wd, sl), sw, ew, par)

    def room_busy(self, rid, wd, sl, sw, ew, par):
        return bool(rid) and self._hit(self.room, (int(rid), wd, sl), sw, ew, par)

    def occupy(self, tk, cid, rid, wd, sl, sw, ew, par):
        if tk:
            self._put(self.teacher, (tk, wd, sl), sw, ew, par)
            self.teacher_day[(tk, wd)] = self.teacher_day.get((tk, wd), 0) + 1
        if cid:
            self._put(self.klass, (int(cid), wd, sl), sw, ew, par)
            self.class_day[(int(cid), wd)] = self.class_day.get((int(cid), wd), 0) + 1
        if rid:
            self._put(self.room, (int(rid), wd, sl), sw, ew, par)

def _room_candidates(rooms, need_type, headcount, params) -> list:
    out = []
    for r in rooms:
        if params["roomTypeMatch"] and need_type and (r.room_type or "") != need_type:
            continue
        if params["capacityCheck"] and headcount and (r.capacity or 0) < headcount:
            continue
        out.append(r)
    return out

def _place_task(t, need, sw, ew, par, params, forbidden, grid, cand_rooms, all_rooms, avail_block):
    """给单个任务找 need 个位置。返回 (已放置列表, 失败原因码)。

    失败归因优先级：先判"结构性无解"（无教师/无教室类型/教室都太小），
    再判"时间被占满"——这样教务员看到的是根因，不是表象。
    """
    if not t.teacher_key:
        return [], "NO_TEACHER"
    if not cand_rooms:
        # 区分"没有这型教室" vs "有但都太小"——两者处置完全不同
        by_type = [r for r in all_rooms
                   if not (params["roomTypeMatch"] and t.required_room_type
                           and (r.room_type or "") != t.required_room_type)]
        return [], ("ROOM_TOO_SMALL" if by_type else "NO_ROOM_TYPE")

    got = []
    blocked = {"TEACHER_BUSY": 0, "CLASS_BUSY": 0, "ROOM_BUSY": 0,
               "TEACHER_UNAVAILABLE": 0, "DAY_LIMIT": 0, "NO_SLOT": 0}
    for wd in params["weekdays"]:
        for sl in params["slots"]:
            if len(got) >= need:
                break
            if (wd, sl) in forbidden:
                blocked["NO_SLOT"] += 1
                continue
            if params["respectAvail"] and (t.teacher_key, wd, sl) in avail_block:
                blocked["TEACHER_UNAVAILABLE"] += 1
                continue
            if grid.teacher_day.get((t.teacher_key, wd), 0) >= params["teacherMaxPerDay"]:
                blocked["DAY_LIMIT"] += 1
                continue
            if t.class_id and grid.class_day.get((int(t.class_id), wd), 0) >= params["classMaxPerDay"]:
                blocked["DAY_LIMIT"] += 1
                continue
            if grid.teacher_busy(t.teacher_key, wd, sl, sw, ew, par):
                blocked["TEACHER_BUSY"] += 1
                continue
            if grid.class_busy(t.class_id, wd, sl, sw, ew, par):
                blocked["CLASS_BUSY"] += 1
                continue
            room = next((r for r in cand_rooms
                         if not grid.room_busy(r.id, wd, sl, sw, ew, par)), None)
            if room is None:
                blocked["ROOM_BUSY"] += 1
                continue
            grid.occupy(t.teacher_key, t.class_id, room.id, wd, sl, sw, ew, par)
            got.append((wd, sl, room))
        if len(got) >= need:
            break

    if len(got) >= need:
        return got, ""
    why = max(blocked, key=lambda k: blocked[k]) if any(blocked.values()) else "NO_SLOT"
    return got, why
