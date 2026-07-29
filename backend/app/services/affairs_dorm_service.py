"""13A-P6 宿舍房源台账（楼/房/床）+ 学生选床入住 + 调宿 + 宿舍检查。

房源三级：楼(building) → 房(room,含 floor_no/capacity) → 床(bed,占用事实源)。
生成器：给「层数×每层房数×每间床位」一键铺满整栋。入住/退宿/调宿事务内回写 t_cs_dorm_record。
学生选床级联：选楼(按性别过滤)→选层/房(带空床数)→选空床→入住。检查异常→回写 t_cs_dorm_exception+生成风险(DORM)。
"""

from app.core.optimistic_lock import atomic_claim_version

import json
from datetime import datetime

from sqlalchemy import func, or_, select, update

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, no_permission, not_found
from app.core.pagination import normalize_page
from app.services.db_service import _iso, _tid, session

GENDER_LIMITS = ("MALE", "FEMALE", "MIXED")
# 学校级"学生自选宿舍"开关（规则中心 AFFAIRS_DORM_RULE/self_select）：
# 开→学生可自选空床；关→仅辅导员/宿管分配。默认关（保守，学校主动放开）。
_DORM_CFG_TYPE = "AFFAIRS_DORM_RULE"
_SELF_SELECT_KEY = "self_select"
TRANSFER_NODES = ["COUNSELOR_REVIEW", "DORM_MANAGER_REVIEW"]
CHECK_TYPES = ("HYGIENE", "SAFETY", "CONTRABAND", "NIGHT_ABSENCE")
TODO_TRANSFER = "DORM_TRANSFER"
TODO_EXCEPTION = "DORM_EXCEPTION"


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _counselor_assignee_id(db, student_id) -> int:
    """COUNSELOR_REVIEW：班级 counselor_id（= User.id）；无法解析返回 0。"""
    from app.models import SchoolClass, StudentProfile
    if not student_id:
        return 0
    s = db.get(StudentProfile, int(student_id))
    if s and s.class_id:
        c = db.get(SchoolClass, int(s.class_id))
        if c and c.counselor_id:
            return int(c.counselor_id)
    return 0


def _resolve_user_by_manager_key(db, key: str) -> int:
    """DormBuilding.manager_teacher_key → User.id（工号/login/数字 id/唯一姓名）。"""
    from app.models import User
    k = (key or "").strip()
    if not k:
        return 0
    if k.isdigit():
        u = db.get(User, int(k))
        if u and not u.is_deleted and u.tenant_id == _tid() and u.status == "ACTIVE":
            return int(u.id)
    row = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.login_name == k,
        User.is_deleted.is_(False), User.status == "ACTIVE")).first()
    if row:
        return int(row.id)
    rows = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.real_name == k,
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
        User.is_deleted.is_(False), User.status == "ACTIVE")).all()
    return int(rows[0].id) if len(rows) == 1 else 0


def _dorm_manager_assignee_ids(db, building_id) -> list[int]:
    """目标楼栋宿管 User.id 列表；优先 manager_teacher_key。"""
    from app.models import DormBuilding
    if not building_id:
        return []
    b = db.get(DormBuilding, int(building_id))
    if not b or b.is_deleted or b.tenant_id != _tid():
        return []
    aid = _resolve_user_by_manager_key(db, b.manager_teacher_key or "")
    return [aid] if aid else []


def _todo_upsert(db, biz_id, assignee_id, student_id, title, todo_type, *,
                 biz_type="DORM", allow_pool: bool = False) -> bool:
    """幂等写待办；禁止用 assignee_id=0 隐藏责任人配置错误。"""
    from app.models import UnifiedTodo
    aid = int(assignee_id or 0)
    if aid <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"未配置受理人：{todo_type}")
    if not biz_id:
        return False
    bid = int(biz_id)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == bid, UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == aid, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title = title
        row.status = "PENDING"
        row.student_id = student_id
        row.source_biz_type = biz_type
        row.version = int(row.version or 0) + 1
        return True
    db.add(UnifiedTodo(
        tenant_id=_tid(), source_module="student-affairs", source_biz_type=biz_type,
        source_biz_id=bid, todo_type=todo_type, assignee_id=aid,
        student_id=student_id, title=title, status="PENDING"))
    return True


def _todo_done(db, biz_id, todo_type) -> int:
    from app.models import UnifiedTodo
    if not biz_id:
        return 0
    n = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING")).all():
        r.status = "DONE"
        r.version = int(r.version or 0) + 1
        n += 1
    return n


def _push_dorm_manager_todos(db, *, biz_id, building_id, student_id, title, todo_type,
                             biz_type="DORM_TRANSFER") -> None:
    """为楼栋宿管写待办；解析失败时显式阻断并暴露配置异常。"""
    aids = _dorm_manager_assignee_ids(db, building_id)
    if aids:
        for aid in aids:
            _todo_upsert(db, biz_id, aid, student_id, title, todo_type, biz_type=biz_type)
    else:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"楼栋 {building_id} 未配置有效宿管")


def _require_dorm_scope(db, building_id, user):
    """写操作楼栋范围校验：DORM_MANAGER 只能操作本人负责楼栋，越界 403 NO_DATA_SCOPE。
    此前仅读接口（occupancy_stats/list_transfers/list_check_tasks/list_exceptions/list_buildings）
    做了范围过滤，写操作（建楼/铺床/入住/退宿/调宿/检查/处置异常）全部缺校验，宿管可越楼栋操作任意数据。"""
    scope = _dorm_scope_building_ids(db, user)
    if scope is not None and (building_id is None or int(building_id) not in scope):
        raise AppException("NO_DATA_SCOPE", "该楼栋不在您的数据范围内")
    return scope


def _gender_ok(building_gender, student_gender) -> bool:
    if building_gender == "MIXED" or not building_gender:
        return True
    g = (student_gender or "").upper()
    male = g in ("M", "MALE", "男", "1")
    female = g in ("F", "FEMALE", "女", "2")
    return (building_gender == "MALE" and male) or (building_gender == "FEMALE" and female) \
        or (not male and not female)  # 性别未知不拦（数据兜底）


def _cs_student_id(db, student_id):
    from app.models import CsServiceStudent
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False))).first()
    return cs.id if cs else int(student_id)


def _dorm_scope_building_ids(db, user):
    """宿管数据范围(DORM_BUILDING)：返回其负责的 building_id 集合。
    None=全部可见（学工处/学院/超管等非宿管角色）；set()=宿管未分配楼栋（看不到任何楼）。
    键派生与 resolve_teacher_scope 一致（mock u_dorm01→dorm01 / ctx_<login> / 姓名兜底），匹配 DormBuilding.manager_teacher_key。
    另兼容 loginName / 工号（师生导入后常见把楼栋绑到工号）。"""
    from app.core.affairs_security import build_affairs_context
    scope_ctx = build_affairs_context(user, db)
    if scope_ctx.scope_type == "TENANT_ALL":
        return None
    if scope_ctx.scope_type == "DORM_BUILDING":
        return set(scope_ctx.dorm_building_ids)
    return set()

    from app.core.permissions import is_super_admin
    from app.models import DormBuilding
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role != "DORM_MANAGER":
        return None  # 非宿管（学工处/学院/超管）按自身权限全楼可见
    uid = str(u.get("userId") or "")
    ctx = str(u.get("activeContextId") or "")
    name = u.get("realName") or ""
    login = str(u.get("loginName") or u.get("username") or "")
    keys = {k for k in (uid, uid[2:] if uid.startswith("u_") else "",
                        uid[3:] if uid.startswith("db-") else "",
                        ctx[4:] if ctx.startswith("ctx_") else "", name, login) if k}
    rows = db.scalars(select(DormBuilding).where(
        DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False),
        DormBuilding.manager_teacher_key.in_(keys))).all()
    return {b.id for b in rows}


# ═══════════ 楼栋 ═══════════

def _building_row(b, vacant=None, total=None) -> dict:
    return {"buildingId": str(b.id), "buildingName": b.building_name,
            "buildingCode": b.building_code or "", "genderLimit": b.gender_limit,
            "managerTeacherKey": b.manager_teacher_key or "", "floorCount": b.floor_count,
            "status": b.status, "vacantBeds": vacant, "totalBeds": total}


def create_building(body, user) -> dict:
    if (body.genderLimit or "MIXED") not in GENDER_LIMITS:
        raise AppException("VALIDATION_ERROR", "性别限制非法")
    with session() as db:
        from app.models import DormBuilding
        b = DormBuilding(tenant_id=_tid(), building_name=body.buildingName,
                         building_code=getattr(body, "buildingCode", None),
                         gender_limit=(body.genderLimit or "MIXED"),
                         manager_teacher_key=getattr(body, "managerTeacherKey", None),
                         floor_count=getattr(body, "floorCount", None), status="ENABLED")
        db.add(b)
        db.flush()
        _audit(db, "DORM_BUILDING", b.id, "CREATE", body.buildingName)
        bid = b.id
        # 一步到位：建楼同时带布局参数则直接铺床
        floors = getattr(body, "floors", None)
        if floors:
            _generate(db, b, floors, getattr(body, "roomsPerFloor", 0) or 0,
                      getattr(body, "bedsPerRoom", 0) or 0)
        db.commit()
        db.refresh(b)
        return _building_row(b)


def _generate(db, b, floors, rooms_per_floor, beds_per_room) -> dict:
    """给整栋楼铺房+床：floor(1..N) × room(每层 M 间) × bed(每间 K 床)。跳过已存在房号（幂等）。"""
    from app.models import DormBed, DormRoom
    if floors <= 0 or rooms_per_floor <= 0 or beds_per_room <= 0:
        raise AppException("VALIDATION_ERROR", "层数/每层房数/每间床位须为正整数")
    existing = {r.room_no for r in db.scalars(select(DormRoom).where(
        DormRoom.tenant_id == _tid(), DormRoom.building_id == b.id,
        DormRoom.is_deleted.is_(False))).all()}
    rooms_made = beds_made = 0
    for floor in range(1, floors + 1):
        for seq in range(1, rooms_per_floor + 1):
            room_no = f"{floor}{seq:02d}"  # 5层1号→501
            if room_no in existing:
                continue
            room = DormRoom(tenant_id=_tid(), building_id=b.id, floor_no=floor, room_no=room_no,
                            capacity=beds_per_room, room_type="STANDARD", status="ENABLED")
            db.add(room)
            db.flush()
            rooms_made += 1
            for i in range(1, beds_per_room + 1):
                db.add(DormBed(tenant_id=_tid(), building_id=b.id, room_id=room.id,
                               bed_no=f"{room_no}-{i}", status="VACANT"))
                beds_made += 1
    b.floor_count = floors
    _audit(db, "DORM_BUILDING", b.id, "GENERATE", f"{floors}层×{rooms_per_floor}间×{beds_per_room}床")
    return {"roomsCreated": rooms_made, "bedsCreated": beds_made}


def generate_layout(building_id, user, floors, rooms_per_floor, beds_per_room) -> dict:
    with session() as db:
        from app.models import DormBuilding
        b = db.get(DormBuilding, int(building_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("楼栋不存在")
        _require_dorm_scope(db, b.id, user)
        res = _generate(db, b, floors, rooms_per_floor, beds_per_room)
        db.commit()
        return {"buildingId": str(building_id), **res}


def list_buildings(user, gender=None, page=1, page_size=50):
    """楼栋列表（gender 传入时按性别过滤——学生自选床位用）。附空床/总床数。"""
    from app.models import DormBed, DormBuilding
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False),
                 DormBuilding.status == "ENABLED"]
        rows = db.scalars(select(DormBuilding).where(*conds).order_by(DormBuilding.id)).all()
        out = []
        for b in rows:
            if scope is not None and b.id not in scope:  # 宿管仅本人负责楼栋
                continue
            if gender and not _gender_ok(b.gender_limit, gender):
                continue
            total = db.scalar(select(func.count()).select_from(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.building_id == b.id,
                DormBed.is_deleted.is_(False))) or 0
            vacant = db.scalar(select(func.count()).select_from(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.building_id == b.id,
                DormBed.status == "VACANT", DormBed.is_deleted.is_(False))) or 0
            out.append(_building_row(b, vacant, total))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def list_rooms(building_id, user, floor=None, page=1, page_size=100):
    """房间列表（级联第2级：选层后列房，带空床数）。"""
    from app.models import DormBed, DormRoom
    with session() as db:
        _require_dorm_scope(db, int(building_id), user)
        conds = [DormRoom.tenant_id == _tid(), DormRoom.building_id == int(building_id),
                 DormRoom.is_deleted.is_(False)]
        if floor is not None:
            conds.append(DormRoom.floor_no == int(floor))
        rows = db.scalars(select(DormRoom).where(*conds).order_by(DormRoom.floor_no, DormRoom.room_no)).all()
        out = []
        for r in rows:
            vacant = db.scalar(select(func.count()).select_from(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.room_id == r.id,
                DormBed.status == "VACANT", DormBed.is_deleted.is_(False))) or 0
            out.append({"roomId": str(r.id), "buildingId": str(r.building_id), "floorNo": r.floor_no,
                        "roomNo": r.room_no, "capacity": r.capacity, "roomType": r.room_type or "",
                        "status": r.status, "vacantBeds": vacant})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def list_beds(room_id, user):
    """床位列表（级联第3级：选房后列床，标空/已住）。"""
    from app.models import DormBed, DormRoom, StudentProfile
    with session() as db:
        room = db.get(DormRoom, int(room_id))
        if room:
            _require_dorm_scope(db, room.building_id, user)
        rows = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.room_id == int(room_id),
            DormBed.is_deleted.is_(False)).order_by(DormBed.bed_no)).all()
        out = []
        for x in rows:
            occ = None
            if x.student_id:
                s = db.get(StudentProfile, int(x.student_id))
                occ = s.real_name if s else str(x.student_id)
            out.append({"bedId": str(x.id), "roomId": str(x.room_id), "bedNo": x.bed_no,
                        "status": x.status, "studentId": str(x.student_id or ""),
                        "occupantName": occ, "occupiedAt": _iso(x.occupied_at)})
        return out


# ═══════════ 入住 / 退宿（回写 t_cs_dorm_record）═══════════

def _writeback_dorm_record(db, student_id, building, room, bed) -> int:
    """事务内回写 t_cs_dorm_record（既有"我的宿舍"读链路零改动）。返回记录 id。"""
    from app.models import CsDormRecord
    csid = _cs_student_id(db, student_id)
    rec = db.scalars(select(CsDormRecord).where(
        CsDormRecord.tenant_id == _tid(), CsDormRecord.cs_student_id == csid,
        CsDormRecord.record_status == "ACTIVE", CsDormRecord.is_deleted.is_(False))).first()
    if rec:
        rec.building, rec.room, rec.bed, rec.status = building, room, bed, "IN"
    else:
        rec = CsDormRecord(tenant_id=_tid(), cs_student_id=csid, building=building, room=room,
                           bed=bed, checkin_date=datetime.utcnow(), status="IN", record_status="ACTIVE")
        db.add(rec)
        db.flush()
    return rec.id


def _release_student_beds(db, student_id, exclude_bed_id=None):
    from app.models import DormBed
    for b in db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == int(student_id),
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).all():
        if exclude_bed_id and b.id == exclude_bed_id:
            continue
        b.student_id, b.status, b.occupied_at, b.version = None, "VACANT", None, b.version + 1


def checkin(bed_id, user, student_id) -> dict:
    with session() as db:
        from app.models import DormBed, DormBuilding, DormRoom, StudentProfile
        bed = db.get(DormBed, int(bed_id))
        if not bed or bed.is_deleted or bed.tenant_id != _tid():
            raise not_found("床位不存在")
        _require_dorm_scope(db, bed.building_id, user)
        if bed.status != "VACANT":
            raise AppException("DATA_CONFLICT", "该床位已被占用或锁定")
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        b = db.get(DormBuilding, int(bed.building_id))
        if b and not _gender_ok(b.gender_limit, s.gender):
            raise AppException("DATA_CONFLICT", "学生性别与楼栋限制不符")
        # Claim the target before releasing the old bed. The version/status
        # predicate makes two simultaneous check-ins mutually exclusive.
        claimed = db.execute(update(DormBed).where(
            DormBed.id == bed.id,
            DormBed.tenant_id == _tid(),
            DormBed.status == "VACANT",
            DormBed.student_id.is_(None),
            DormBed.version == bed.version,
            DormBed.is_deleted.is_(False),
        ).values(
            student_id=s.id, status="OCCUPIED", occupied_at=datetime.utcnow(),
            version=DormBed.version + 1,
        ))
        if (claimed.rowcount or 0) != 1:
            raise AppException("DATA_CONFLICT", "该床位刚刚已被其他人占用，请刷新后重试")
        db.refresh(bed)
        _release_student_beds(db, s.id, exclude_bed_id=bed.id)
        room = db.get(DormRoom, int(bed.room_id))
        rec_id = _writeback_dorm_record(db, s.id, b.building_name if b else "",
                                        room.room_no if room else "", bed.bed_no)
        bed.cs_dorm_record_id = rec_id
        _audit(db, "DORM_BED", bed.id, "CHECKIN", f"student={s.id}")
        db.commit()
        return {"bedId": str(bed.id), "bedNo": bed.bed_no, "studentId": str(s.id),
                "building": b.building_name if b else "", "room": room.room_no if room else "",
                "status": "OCCUPIED"}


# ── 学校级"学生自选宿舍"开关（规则中心）──

def is_self_select_enabled() -> bool:
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), _DORM_CFG_TYPE, _SELF_SELECT_KEY)
    return bool(cfg.get("enabled", False)) if cfg else False


# 学生端提醒文案（前端/小程序直接展示，无需自己拼）
_NOTICE_OFF = "本校宿舍暂由辅导员统一分配，暂未开放学生自选。如需调整床位请联系辅导员。"
_NOTICE_ON = "已开放学生自选宿舍，请在开放时段内选择空床完成入住。"


def get_dorm_config(user) -> dict:
    """前端/小程序据此决定是否显示"学生自选床位"入口，并直接展示 studentNotice。"""
    on = is_self_select_enabled()
    return {"selfSelectEnabled": on,
            "assignMode": "SELF_SELECT" if on else "COUNSELOR_ASSIGN",
            "studentNotice": _NOTICE_ON if on else _NOTICE_OFF}


def set_self_select(user, enabled: bool) -> dict:
    """学校管理员开/关学生自选宿舍。"""
    from app.services.platform_service import put_config_json
    put_config_json(_tid(), _DORM_CFG_TYPE, _SELF_SELECT_KEY, {"enabled": bool(enabled)})
    _n, _r, _u = _op()
    with session() as db:
        _audit(db, "DORM_CONFIG", 0, "SET_SELF_SELECT", f"enabled={bool(enabled)}")
        db.commit()
    return get_dorm_config(user)


def self_select_checkin(bed_id, user, student_id) -> dict:
    """学生自选床位入住（学生端调用）。学校未放开 → 403，引导找辅导员分配。"""
    if not is_self_select_enabled():
        raise no_permission(_NOTICE_OFF)
    return checkin(bed_id, user, student_id)


def checkout(bed_id, user, expected_version=None) -> dict:
    with session() as db:
        from app.models import CsDormRecord, DormBed
        bed = db.get(DormBed, int(bed_id))
        if not bed or bed.is_deleted or bed.tenant_id != _tid():
            raise not_found("床位不存在")
        _require_dorm_scope(db, bed.building_id, user)
        if bed.status != "OCCUPIED":
            raise AppException("DATA_CONFLICT", "该床位无人入住")
        atomic_claim_version(db, bed, expected_version)
        if bed.cs_dorm_record_id:
            rec = db.get(CsDormRecord, int(bed.cs_dorm_record_id))
            if rec:
                rec.status, rec.record_status = "OUT", "INACTIVE"
        bed.student_id, bed.status, bed.occupied_at, bed.cs_dorm_record_id, bed.version = \
            None, "VACANT", None, None, bed.version + 1
        _audit(db, "DORM_BED", bed.id, "CHECKOUT")
        db.commit()
        return {"bedId": str(bed.id), "status": "VACANT"}


# ═══════════ 调宿（审批：辅导员→宿管→执行）═══════════

def submit_transfer(user, student_id, to_bed_id, reason="") -> dict:
    with session() as db:
        from app.models import DormBed, DormTransfer, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        to_bed = db.get(DormBed, int(to_bed_id))
        if not to_bed or to_bed.is_deleted or to_bed.tenant_id != _tid():
            raise not_found("目标床位不存在")
        _require_dorm_scope(db, to_bed.building_id, user)
        if to_bed.status != "VACANT":
            raise AppException("DATA_CONFLICT", "目标床位已被占用")
        from_bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == int(student_id),
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).first()
        # 调宿须同时在源楼栋与目标楼栋数据范围内（此前只校验目标楼，宿管可对他人楼栋学生发起调出）
        if from_bed:
            _require_dorm_scope(db, from_bed.building_id, user)
        first = TRANSFER_NODES[0]
        t = DormTransfer(tenant_id=_tid(), student_id=s.id,
                         from_bed_id=(from_bed.id if from_bed else None), to_bed_id=to_bed.id,
                         reason=reason, status=first, current_node=first)
        db.add(t)
        db.flush()
        counselor = _counselor_assignee_id(db, s.id)
        _todo_upsert(db, t.id, counselor, s.id,
                     f"调宿待审：{s.real_name or ''}", TODO_TRANSFER, biz_type="DORM_TRANSFER")
        _audit(db, "DORM_TRANSFER", t.id, "SUBMIT")
        db.commit()
        db.refresh(t)
        return _transfer_row(t)


def _transfer_row(t) -> dict:
    return {"transferId": str(t.id), "studentId": str(t.student_id),
            "fromBedId": str(t.from_bed_id or ""), "toBedId": str(t.to_bed_id or ""),
            "reason": t.reason or "", "status": t.status, "currentNode": t.current_node or "",
            "version": t.version}


def review_transfer(transfer_id, user, action, reason="", expected_version=None) -> dict:
    """辅导员→宿管两级；终审通过即执行(原床释放/新床占用/回写)。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import DormBed, DormBuilding, DormRoom, DormTransfer
        t = db.get(DormTransfer, int(transfer_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("调宿申请不存在")
        if t.to_bed_id:
            to_bed_for_scope = db.get(DormBed, int(t.to_bed_id))
            if to_bed_for_scope:
                _require_dorm_scope(db, to_bed_for_scope.building_id, user)
        if t.status not in TRANSFER_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该调宿当前状态不可审批")
        atomic_claim_version(db, t, expected_version)
        from app.models import StudentProfile
        stu = db.get(StudentProfile, int(t.student_id)) if t.student_id else None
        stu_name = (stu.real_name if stu else "") or ""
        if action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            t.status, t.return_reason, t.version = "REJECTED", reason.strip(), t.version + 1
            _todo_done(db, t.id, TODO_TRANSFER)
            _audit(db, "DORM_TRANSFER", t.id, "REJECTED", reason.strip())
        elif action == "APPROVE":
            i = TRANSFER_NODES.index(t.current_node) if t.current_node in TRANSFER_NODES else 0
            if i + 1 < len(TRANSFER_NODES):
                nxt = TRANSFER_NODES[i + 1]
                t.current_node, t.status, t.version = nxt, nxt, t.version + 1
                _todo_done(db, t.id, TODO_TRANSFER)
                to_bed = db.get(DormBed, int(t.to_bed_id)) if t.to_bed_id else None
                building_id = to_bed.building_id if to_bed else None
                _push_dorm_manager_todos(
                    db, biz_id=t.id, building_id=building_id, student_id=t.student_id,
                    title=f"调宿待审（宿管）：{stu_name}", todo_type=TODO_TRANSFER,
                    biz_type="DORM_TRANSFER")
                _audit(db, "DORM_TRANSFER", t.id, "STEP", f"->{nxt}")
            else:
                # 终审通过 → 执行调宿
                to_bed = db.get(DormBed, int(t.to_bed_id)) if t.to_bed_id else None
                if not to_bed or to_bed.status != "VACANT":
                    raise AppException("DATA_CONFLICT", "目标床位已被占用，调宿无法执行")
                _release_student_beds(db, t.student_id)  # 释放原床
                b = db.get(DormBuilding, int(to_bed.building_id))
                room = db.get(DormRoom, int(to_bed.room_id))
                rec_id = _writeback_dorm_record(db, t.student_id, b.building_name if b else "",
                                                room.room_no if room else "", to_bed.bed_no)
                to_bed.student_id, to_bed.status, to_bed.occupied_at = t.student_id, "OCCUPIED", datetime.utcnow()
                to_bed.cs_dorm_record_id, to_bed.version = rec_id, to_bed.version + 1
                t.status, t.version = "EXECUTED", t.version + 1
                _todo_done(db, t.id, TODO_TRANSFER)
                _audit(db, "DORM_TRANSFER", t.id, "EXECUTED")
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(t)
        return _transfer_row(t)


# ═══════════ 宿舍检查（异常→回写异常表+生成风险）═══════════

def create_check_task(body, user) -> dict:
    if (body.checkType or "HYGIENE") not in CHECK_TYPES:
        raise AppException("VALIDATION_ERROR", "检查类型非法")
    building_id = int(body.buildingId) if getattr(body, "buildingId", None) else None
    with session() as db:
        from app.models import DormCheckTask
        _require_dorm_scope(db, building_id, user)
        t = DormCheckTask(tenant_id=_tid(), task_name=body.taskName, building_id=building_id,
                          check_type=(body.checkType or "HYGIENE"),
                          checker_key=getattr(body, "checkerKey", None), status="RUNNING")
        db.add(t)
        db.flush()
        _audit(db, "DORM_CHECK", t.id, "TASK_CREATE", body.checkType or "HYGIENE")
        db.commit()
        db.refresh(t)
        return {"taskId": str(t.id), "taskName": t.task_name, "checkType": t.check_type, "status": t.status}


def submit_check_record(task_id, user, body) -> dict:
    """录检查结果；ABNORMAL → 回写 t_cs_dorm_exception + 生成 t_affairs_risk_record(source=DORM)。"""
    result = (body.result or "NORMAL").upper()
    with session() as db:
        from app.models import (AffairsRiskRecord, CsDormException, DormCheckRecord,
                                DormCheckTask, DormRoom, StudentProfile)
        task = db.get(DormCheckTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _tid():
            raise not_found("检查任务不存在")
        _require_dorm_scope(db, task.building_id, user)
        room_id = int(body.roomId) if getattr(body, "roomId", None) else None
        rec = DormCheckRecord(tenant_id=_tid(), task_id=task.id, room_id=room_id, result=result,
                              issue_type=getattr(body, "issueType", None),
                              detail=getattr(body, "detail", None),
                              status=("ABNORMAL" if result == "ABNORMAL" else "NORMAL"))
        db.add(rec)
        db.flush()
        if result == "ABNORMAL":
            if not (body.detail or "").strip() or len((body.detail or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "异常说明必填且不少于 5 字")
            room = db.get(DormRoom, room_id) if room_id else None
            # SEC-4 修复：异常→风险须绑真实学生，不再硬编码 student_id=0（否则风险成孤儿、按数据范围恒不可见）。
            sid = getattr(body, "studentId", None)
            sid_int = int(str(sid).strip()) if sid and str(sid).strip().isdigit() else None
            if task.check_type == "NIGHT_ABSENCE" and not sid_int:
                raise AppException("VALIDATION_ERROR", "夜不归宿异常须指定涉事学生")
            if sid_int:
                s = db.get(StudentProfile, sid_int)
                if not s or s.is_deleted or s.tenant_id != _tid():
                    raise not_found("涉事学生不存在或不在本租户")
                rec.student_ids_json = json.dumps([sid_int])
            # 回写宿舍异常表：有涉事学生则绑真实 cs_student_id；纯房间级异常(无学生)记 0，由宿管在异常列表处置。
            exc = CsDormException(tenant_id=_tid(),
                                  cs_student_id=(_cs_student_id(db, sid_int) if sid_int else 0),
                                  exc_type=(rec.issue_type or task.check_type or "DORM_CHECK"),
                                  detail=rec.detail, status="PENDING_HANDLE")
            db.add(exc)
            db.flush()
            rec.related_exception_id = exc.id
            # 仅在有真实学生时生成学生风险（source=DORM）；纯房间级异常不再造 student_id=0 孤儿风险。
            if sid_int:
                risk = AffairsRiskRecord(
                    tenant_id=_tid(), student_id=sid_int, source="DORM", source_ref_id=rec.id,
                    risk_level="MEDIUM",
                    title=("宿舍夜不归宿" if task.check_type == "NIGHT_ABSENCE" else "宿舍检查异常")
                          + f"：{room.room_no if room else ''}",
                    detail=rec.detail, status="NEW")
                db.add(risk)
                db.flush()
                rec.related_risk_id = risk.id
            building_id = task.building_id or (room.building_id if room else None)
            stu_name = ""
            if sid_int:
                sp = db.get(StudentProfile, sid_int)
                stu_name = (sp.real_name if sp else "") or ""
            _push_dorm_manager_todos(
                db, biz_id=exc.id, building_id=building_id, student_id=sid_int,
                title=f"宿舍异常待处置：{stu_name or (room.room_no if room else '')}",
                todo_type=TODO_EXCEPTION, biz_type="DORM_EXCEPTION")
            _audit(db, "DORM_CHECK", rec.id, "ABNORMAL",
                   f"exc={exc.id},risk={rec.related_risk_id or '-'},student={sid_int or '-'}")
        else:
            _audit(db, "DORM_CHECK", rec.id, "NORMAL")
        db.commit()
        db.refresh(rec)
        return {"recordId": str(rec.id), "taskId": str(task.id), "result": rec.result,
                "relatedExceptionId": str(rec.related_exception_id or ""),
                "relatedRiskId": str(rec.related_risk_id or ""), "status": rec.status}


# ═══════════ 台账统计（入住率）═══════════

def occupancy_stats(user):
    """入住率汇总；宿管按 _dorm_scope_building_ids 收敛到负责楼栋，与下方楼栋列表口径一致。"""
    from app.models import DormBed
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds_total = [DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False)]
        conds_occ = conds_total + [DormBed.status == "OCCUPIED"]
        if scope is not None:
            conds_total.append(DormBed.building_id.in_(list(scope)) if scope else DormBed.building_id.in_([-1]))
            conds_occ.append(DormBed.building_id.in_(list(scope)) if scope else DormBed.building_id.in_([-1]))
        total = db.scalar(select(func.count()).select_from(DormBed).where(*conds_total)) or 0
        occupied = db.scalar(select(func.count()).select_from(DormBed).where(*conds_occ)) or 0
        return {"totalBeds": total, "occupiedBeds": occupied, "vacantBeds": total - occupied,
                "occupancyRate": round(occupied / total, 3) if total else 0.0}


# ═══════════ 列表（调宿/检查/异常，宿管按楼栋收敛）═══════════

def list_transfers(user, status=None, page=1, page_size=50, student_id=None):
    from app.models import DormBed, DormTransfer, StudentProfile
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [DormTransfer.tenant_id == _tid(), DormTransfer.is_deleted.is_(False)]
        if status == "PENDING":
            conds.append(DormTransfer.status.in_(
                ["PENDING", "SUBMITTED", "COUNSELOR_REVIEW", "DORM_REVIEW", "DORM_MANAGER_REVIEW"]))
        elif status:
            conds.append(DormTransfer.status == status)
        if student_id:
            try:
                conds.append(DormTransfer.student_id == int(student_id))
            except (TypeError, ValueError):
                return [], 0
        query = select(DormTransfer)
        count_query = select(func.count()).select_from(DormTransfer)
        if scope is not None:
            query = query.join(DormBed, DormBed.id == DormTransfer.to_bed_id)
            count_query = count_query.join(DormBed, DormBed.id == DormTransfer.to_bed_id)
            conds.append(DormBed.building_id.in_(scope or {-1}))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(count_query.where(*conds)) or 0)
        rows = db.scalars(query.where(*conds).order_by(DormTransfer.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_({int(t.student_id) for t in rows if t.student_id})
        )).all()} if rows else {}
        out = []
        for t in rows:
            s = students.get(int(t.student_id)) if t.student_id else None
            r = _transfer_row(t)
            r["realName"], r["studentNo"] = (s.real_name if s else ""), (s.student_no if s else "")
            out.append(r)
        return out, total


def list_check_tasks(user, status=None, page=1, page_size=50):
    from app.models import DormBuilding, DormCheckTask
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [DormCheckTask.tenant_id == _tid(), DormCheckTask.is_deleted.is_(False)]
        if status:
            conds.append(DormCheckTask.status == status)
        rows = db.scalars(select(DormCheckTask).where(*conds).order_by(DormCheckTask.id.desc())).all()
        out = []
        for t in rows:
            if scope is not None and (t.building_id is None or t.building_id not in scope):
                continue
            b = db.get(DormBuilding, int(t.building_id)) if t.building_id else None
            out.append({"taskId": str(t.id), "taskName": t.task_name, "checkType": t.check_type,
                        "buildingId": str(t.building_id or ""), "buildingName": b.building_name if b else "",
                        "status": t.status, "createdAt": _iso(t.created_at)})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def list_check_records(task_id, user, page=1, page_size=100):
    import json
    from app.models import DormCheckRecord, DormCheckTask, DormRoom, StudentProfile
    with session() as db:
        task = db.get(DormCheckTask, int(task_id))
        if not task or task.is_deleted or task.tenant_id != _tid():
            raise not_found("查寝任务不存在")
        _require_dorm_scope(db, task.building_id, user)
        rows = db.scalars(select(DormCheckRecord).where(
            DormCheckRecord.tenant_id == _tid(), DormCheckRecord.task_id == int(task_id),
            DormCheckRecord.is_deleted.is_(False)).order_by(DormCheckRecord.id.desc())).all()
        out = []
        for r in rows:
            room = db.get(DormRoom, int(r.room_id)) if r.room_id else None
            students = []
            if r.student_ids_json:
                try:
                    for sid in json.loads(r.student_ids_json) or []:
                        s = db.get(StudentProfile, int(sid))
                        if s:
                            students.append({"studentId": str(s.id), "realName": s.real_name,
                                            "studentNo": s.student_no})
                except (ValueError, TypeError):
                    pass
            out.append({"recordId": str(r.id), "taskId": str(r.task_id), "roomId": str(r.room_id or ""),
                        "roomNo": room.room_no if room else "", "result": r.result,
                        "issueType": r.issue_type or "", "detail": r.detail or "", "status": r.status,
                        "students": students,
                        "relatedRiskId": str(r.related_risk_id or ""),
                        "relatedExceptionId": str(r.related_exception_id or "")})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _resolve_exception_student(db, exception_id, cs_student_id):
    """t_cs_dorm_exception.cs_student_id 可能是 CsServiceStudent.id、（无台账行时）退化的全局 student_id、
    或 0（纯房间级异常无涉事学生）。解析出 (realName, studentNo, buildingId, globalStudentId)：优先经学生当前占用床位
    （DormBed.status=OCCUPIED）反查楼栋；纯房间级异常（cs_student_id=0）改经回链的 DormCheckRecord.room_id
    反查楼栋。供宿管楼栋范围收敛与列表展示学生身份用。"""
    from app.models import CsServiceStudent, DormBed, DormCheckRecord, DormRoom, StudentProfile
    real_name, student_no, global_sid = "", "", None
    if cs_student_id:
        cs = db.get(CsServiceStudent, int(cs_student_id))
        if cs and not cs.is_deleted:
            # CsServiceStudent 行确实存在——即使它没连 student_id（未做新旧数据对齐），也不能把
            # cs_student_id（CsServiceStudent 主键序列）误当 StudentProfile 主键去查，两套序列独立，
            # 数值撞上会张冠李戴到无关学生。只在"根本查不到 CsServiceStudent 行"时才走下面的兜底。
            real_name, student_no, global_sid = cs.name or "", cs.student_no or "", cs.student_id
        else:
            s = db.get(StudentProfile, int(cs_student_id))
            if s and not s.is_deleted:
                real_name, student_no, global_sid = s.real_name, s.student_no, s.id
    building_id = None
    if global_sid:
        bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == int(global_sid),
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).first()
        if bed:
            building_id = bed.building_id
    if building_id is None:
        rec = db.scalars(select(DormCheckRecord).where(
            DormCheckRecord.tenant_id == _tid(), DormCheckRecord.related_exception_id == exception_id,
            DormCheckRecord.is_deleted.is_(False))).first()
        if rec and rec.room_id:
            room = db.get(DormRoom, int(rec.room_id))
            if room:
                building_id = room.building_id
    return real_name, student_no, building_id, global_sid


def _resolve_exception_students(db, rows):
    """批量解析异常关联学生/楼栋，供列表避免逐条查学生、床位和检查记录。"""
    from app.models import CsServiceStudent, DormBed, DormCheckRecord, DormRoom, StudentProfile
    cs_ids = {int(x.cs_student_id) for x in rows if x.cs_student_id}
    cs_rows = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.id.in_(cs_ids),
        CsServiceStudent.is_deleted.is_(False))).all() if cs_ids else []
    cs_by_id = {int(x.id): x for x in cs_rows}
    fallback_ids = cs_ids - set(cs_by_id)
    fallback_students = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(fallback_ids),
        StudentProfile.is_deleted.is_(False))).all() if fallback_ids else []
    fallback_by_id = {int(x.id): x for x in fallback_students}
    identities = {}
    for x in rows:
        csid = int(x.cs_student_id or 0)
        cs = cs_by_id.get(csid)
        student = fallback_by_id.get(csid)
        identities[int(x.id)] = (
            (cs.name if cs else (student.real_name if student else "")) or "",
            (cs.student_no if cs else (student.student_no if student else "")) or "",
            (cs.student_id if cs else (student.id if student else None)),
        )
    student_ids = {int(identity[2]) for identity in identities.values() if identity[2]}
    beds = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(), DormBed.student_id.in_(student_ids),
        DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).all() if student_ids else []
    building_by_student = {int(b.student_id): b.building_id for b in beds if b.student_id}
    exception_ids = [int(x.id) for x in rows]
    check_rows = db.scalars(select(DormCheckRecord).where(
        DormCheckRecord.tenant_id == _tid(), DormCheckRecord.related_exception_id.in_(exception_ids),
        DormCheckRecord.is_deleted.is_(False))).all() if exception_ids else []
    rooms = db.scalars(select(DormRoom).where(
        DormRoom.tenant_id == _tid(), DormRoom.id.in_({int(r.room_id) for r in check_rows if r.room_id}),
        DormRoom.is_deleted.is_(False))).all() if check_rows else []
    room_buildings = {int(r.id): r.building_id for r in rooms}
    check_buildings = {
        int(r.related_exception_id): room_buildings.get(int(r.room_id))
        for r in check_rows if r.related_exception_id and r.room_id
    }
    return {
        int(x.id): (*identities[int(x.id)],
                    building_by_student.get(int(identities[int(x.id)][2]))
                    if identities[int(x.id)][2] else check_buildings.get(int(x.id)))
        for x in rows
    }


def list_exceptions(user, status=None, page=1, page_size=50, student_id=None):
    """宿舍异常列表（含夜不归宿）。按学生当前占用床位反查楼栋，宿管收敛至负责楼栋；展示学生姓名/学号。"""
    from app.models import CsDormException
    want_sid = None
    if student_id:
        try:
            want_sid = int(student_id)
        except (TypeError, ValueError):
            return [], 0
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [CsDormException.tenant_id == _tid(), CsDormException.is_deleted.is_(False)]
        if status in ("PENDING", "PENDING_HANDLE"):
            conds.append(CsDormException.status.in_(["PENDING_HANDLE", "OPEN", "PENDING"]))
        elif status:
            conds.append(CsDormException.status == status)
        from app.models import CsServiceStudent, DormBed, DormCheckRecord, DormRoom, StudentProfile
        if want_sid is not None:
            conds.append(or_(
                CsDormException.cs_student_id == want_sid,
                CsDormException.cs_student_id.in_(select(CsServiceStudent.id).where(
                    CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == want_sid,
                    CsServiceStudent.is_deleted.is_(False))),
            ))
        if scope is not None:
            scoped = scope or {-1}
            student_buildings = select(CsServiceStudent.id).join(
                DormBed, DormBed.student_id == CsServiceStudent.student_id).where(
                CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
                DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False),
                DormBed.status == "OCCUPIED", DormBed.building_id.in_(scoped))
            legacy_buildings = select(StudentProfile.id).join(
                DormBed, DormBed.student_id == StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False),
                DormBed.status == "OCCUPIED", DormBed.building_id.in_(scoped))
            room_exceptions = select(DormCheckRecord.related_exception_id).join(
                DormRoom, DormRoom.id == DormCheckRecord.room_id).where(
                DormCheckRecord.tenant_id == _tid(), DormCheckRecord.is_deleted.is_(False),
                DormRoom.tenant_id == _tid(), DormRoom.is_deleted.is_(False),
                DormRoom.building_id.in_(scoped))
            conds.append(or_(
                CsDormException.cs_student_id.in_(student_buildings),
                CsDormException.cs_student_id.in_(legacy_buildings),
                CsDormException.id.in_(room_exceptions),
            ))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(CsDormException).where(*conds)) or 0)
        rows = db.scalars(select(CsDormException).where(*conds).order_by(CsDormException.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        resolved = _resolve_exception_students(db, rows)
        out = []
        for x in rows:
            real_name, student_no, global_sid, _building_id = resolved[int(x.id)]
            out.append({"exceptionId": str(x.id), "csStudentId": str(x.cs_student_id or ""),
                       "studentId": str(global_sid or ""),
                       "realName": real_name, "studentNo": student_no,
                       "excType": x.exc_type or "", "detail": x.detail or "", "status": x.status,
                       "createdAt": _iso(x.created_at), "version": x.version})
        return out, total


def handle_exception(exception_id, user, note="", expected_version=None):
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置说明必填且不少于 5 字")
    with session() as db:
        from app.models import CsDormException
        x = db.get(CsDormException, int(exception_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("异常记录不存在")
        _, _, building_id, _ = _resolve_exception_student(db, x.id, x.cs_student_id)
        _require_dorm_scope(db, building_id, user)
        if x.status == "HANDLED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该异常已处置")
        atomic_claim_version(db, x, expected_version)
        x.status = "HANDLED"
        _todo_done(db, x.id, TODO_EXCEPTION)
        _audit(db, "DORM_EXCEPTION", x.id, "HANDLE", note.strip()[:100])
        db.commit()
        return {"exceptionId": str(x.id), "status": x.status, "version": x.version}
