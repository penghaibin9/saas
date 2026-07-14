"""13A-P6 宿舍房源台账（楼/房/床）+ 学生选床入住 + 调宿 + 宿舍检查。

房源三级：楼(building) → 房(room,含 floor_no/capacity) → 床(bed,占用事实源)。
生成器：给「层数×每层房数×每间床位」一键铺满整栋。入住/退宿/调宿事务内回写 t_cs_dorm_record。
学生选床级联：选楼(按性别过滤)→选层/房(带空床数)→选空床→入住。检查异常→回写 t_cs_dorm_exception+生成风险(DORM)。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _iso, _tid, session

GENDER_LIMITS = ("MALE", "FEMALE", "MIXED")
# 学校级"学生自选宿舍"开关（规则中心 AFFAIRS_DORM_RULE/self_select）：
# 开→学生可自选空床；关→仅辅导员/宿管分配。默认关（保守，学校主动放开）。
_DORM_CFG_TYPE = "AFFAIRS_DORM_RULE"
_SELF_SELECT_KEY = "self_select"
TRANSFER_NODES = ["COUNSELOR_REVIEW", "DORM_MANAGER_REVIEW"]
CHECK_TYPES = ("HYGIENE", "SAFETY", "CONTRABAND", "NIGHT_ABSENCE")


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


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
    键派生与 resolve_teacher_scope 一致（mock u_dorm01→dorm01 / ctx_<login> / 姓名兜底），匹配 DormBuilding.manager_teacher_key。"""
    from app.core.permissions import is_super_admin
    from app.models import DormBuilding
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role != "DORM_MANAGER":
        return None  # 非宿管（学工处/学院/超管）按自身权限全楼可见
    uid = str(u.get("userId") or "")
    ctx = str(u.get("activeContextId") or "")
    name = u.get("realName") or ""
    keys = {k for k in (uid, uid[2:] if uid.startswith("u_") else "",
                        ctx[4:] if ctx.startswith("ctx_") else "", name) if k}
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
        _release_student_beds(db, s.id)  # 换床：先释放原床
        room = db.get(DormRoom, int(bed.room_id))
        rec_id = _writeback_dorm_record(db, s.id, b.building_name if b else "",
                                        room.room_no if room else "", bed.bed_no)
        bed.student_id, bed.status, bed.occupied_at = s.id, "OCCUPIED", datetime.utcnow()
        bed.cs_dorm_record_id, bed.version = rec_id, bed.version + 1
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


def checkout(bed_id, user) -> dict:
    with session() as db:
        from app.models import CsDormRecord, DormBed
        bed = db.get(DormBed, int(bed_id))
        if not bed or bed.is_deleted or bed.tenant_id != _tid():
            raise not_found("床位不存在")
        _require_dorm_scope(db, bed.building_id, user)
        if bed.status != "OCCUPIED":
            raise AppException("DATA_CONFLICT", "该床位无人入住")
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
        first = TRANSFER_NODES[0]
        t = DormTransfer(tenant_id=_tid(), student_id=s.id,
                         from_bed_id=(from_bed.id if from_bed else None), to_bed_id=to_bed.id,
                         reason=reason, status=first, current_node=first)
        db.add(t)
        db.flush()
        _audit(db, "DORM_TRANSFER", t.id, "SUBMIT")
        db.commit()
        db.refresh(t)
        return _transfer_row(t)


def _transfer_row(t) -> dict:
    return {"transferId": str(t.id), "studentId": str(t.student_id),
            "fromBedId": str(t.from_bed_id or ""), "toBedId": str(t.to_bed_id or ""),
            "reason": t.reason or "", "status": t.status, "currentNode": t.current_node or "",
            "version": t.version}


def review_transfer(transfer_id, user, action, reason="") -> dict:
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
        if action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            t.status, t.return_reason, t.version = "REJECTED", reason.strip(), t.version + 1
            _audit(db, "DORM_TRANSFER", t.id, "REJECTED", reason.strip())
        elif action == "APPROVE":
            i = TRANSFER_NODES.index(t.current_node) if t.current_node in TRANSFER_NODES else 0
            if i + 1 < len(TRANSFER_NODES):
                nxt = TRANSFER_NODES[i + 1]
                t.current_node, t.status, t.version = nxt, nxt, t.version + 1
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

def list_transfers(user, status=None, page=1, page_size=50):
    from app.models import DormBed, DormTransfer, StudentProfile
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [DormTransfer.tenant_id == _tid(), DormTransfer.is_deleted.is_(False)]
        if status:
            conds.append(DormTransfer.status == status)
        rows = db.scalars(select(DormTransfer).where(*conds).order_by(DormTransfer.id.desc())).all()
        out = []
        for t in rows:
            if scope is not None:  # 宿管仅见目标床所在楼栋的调宿
                tb = db.get(DormBed, int(t.to_bed_id)) if t.to_bed_id else None
                if not tb or tb.building_id not in scope:
                    continue
            s = db.get(StudentProfile, int(t.student_id)) if t.student_id else None
            r = _transfer_row(t)
            r["realName"], r["studentNo"] = (s.real_name if s else ""), (s.student_no if s else "")
            out.append(r)
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


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
    from app.models import DormCheckRecord, DormRoom, StudentProfile
    with session() as db:
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
    或 0（纯房间级异常无涉事学生）。解析出 (realName, studentNo, buildingId)：优先经学生当前占用床位
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
    return real_name, student_no, building_id


def list_exceptions(user, status=None, page=1, page_size=50):
    """宿舍异常列表（含夜不归宿）。按学生当前占用床位反查楼栋，宿管收敛至负责楼栋；展示学生姓名/学号。"""
    from app.models import CsDormException
    with session() as db:
        scope = _dorm_scope_building_ids(db, user)
        conds = [CsDormException.tenant_id == _tid(), CsDormException.is_deleted.is_(False)]
        if status:
            conds.append(CsDormException.status == status)
        rows = db.scalars(select(CsDormException).where(*conds).order_by(CsDormException.id.desc())).all()
        out = []
        for x in rows:
            real_name, student_no, building_id = _resolve_exception_student(db, x.id, x.cs_student_id)
            if scope is not None and (building_id is None or building_id not in scope):
                continue
            out.append({"exceptionId": str(x.id), "csStudentId": str(x.cs_student_id or ""),
                       "realName": real_name, "studentNo": student_no,
                       "excType": x.exc_type or "", "detail": x.detail or "", "status": x.status,
                       "createdAt": _iso(x.created_at)})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def handle_exception(exception_id, user, note=""):
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置说明必填且不少于 5 字")
    with session() as db:
        from app.models import CsDormException
        x = db.get(CsDormException, int(exception_id))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("异常记录不存在")
        _, _, building_id = _resolve_exception_student(db, x.id, x.cs_student_id)
        _require_dorm_scope(db, building_id, user)
        if x.status == "HANDLED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该异常已处置")
        x.status = "HANDLED"
        _audit(db, "DORM_EXCEPTION", x.id, "HANDLE", note.strip()[:100])
        db.commit()
        return {"exceptionId": str(x.id), "status": x.status}
