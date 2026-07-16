"""专业分流服务（对标商业教务 7-5：大类招生分流）。

流程：建批次(限年级/可限大类源专业) → 配可选专业与容量 → 开放学生填志愿(可改) → 截止 →
自动分配(绩点降序×志愿顺序=分数优先遵循志愿，确定性可复核) → 人工调剂(原因留痕) →
确认(写 StudentProfile.major_id + 逐生审计，终态)。

纪律：
- 分配算法确定性：绩点同分按学号稳定序，无随机源，摇不出两样结果；
- 分配绝不超容量；志愿全满 → UNALLOCATED 如实标记，等人工调剂，不硬塞；
- 确认前必须清零 UNALLOCATED（每个学生都要有去处，不允许"确认了但有人没专业"）；
- 写学籍只发生在 confirm 一处，逐生落审计（谁批的、原绩点、第几志愿），可倒查。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

STATUSES = ("DRAFT", "OPEN", "CLOSED", "ALLOCATED", "CONFIRMED")


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_MAJOR_SPLIT", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理专业分流")
    return ctx


def _b_dto(b):
    return {"batchId": str(b.id), "batchName": b.batch_name, "grade": b.grade,
            "sourceMajorId": str(b.source_major_id) if b.source_major_id else None,
            "maxChoices": b.max_choices, "volunteerStart": _iso(b.volunteer_start),
            "volunteerEnd": _iso(b.volunteer_end), "status": b.status}


def _get_batch(db, bid):
    from app.models import AaMajorSplitBatch
    b = db.get(AaMajorSplitBatch, int(bid))
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("分流批次不存在")
    return b


def _v_dto(v):
    return {"volunteerId": str(v.id), "studentId": str(v.student_id), "studentNo": v.student_no,
            "studentName": v.student_name,
            "choices": json.loads(v.choices_json) if v.choices_json else [],
            "gpa": float(v.gpa_snapshot) if v.gpa_snapshot is not None else None,
            "resultMajorId": str(v.result_major_id) if v.result_major_id else None,
            "resultChoiceRank": v.result_choice_rank, "adjustReason": v.adjust_reason,
            "status": v.status}


# ══════════ 批次与可选专业 ══════════

def create_batch(user, body) -> dict:
    from app.models import AaMajorSplitBatch
    with session() as db:
        _require_school(user, db)
        name = (getattr(body, "batchName", None) or "").strip()
        grade = (getattr(body, "grade", None) or "").strip()
        if not name or not grade:
            raise _bad("批次名称与分流年级必填")
        b = AaMajorSplitBatch(
            tenant_id=_tid(), batch_name=name, grade=grade,
            source_major_id=int(body.sourceMajorId) if getattr(body, "sourceMajorId", None) else None,
            max_choices=max(1, int(getattr(body, "maxChoices", 3) or 3)), status="DRAFT")
        db.add(b)
        db.flush()
        _audit(db, b.id, "SPLIT_BATCH_CREATE", f"{name} 年级{grade}")
        db.commit()
        return _b_dto(b)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaMajorSplitBatch
    with session() as db:
        build_affairs_context(user, db)
        q = db.query(AaMajorSplitBatch).filter(AaMajorSplitBatch.tenant_id == _tid(),
                                               AaMajorSplitBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaMajorSplitBatch.status == status)
        rows = q.order_by(AaMajorSplitBatch.id.desc()).all()
        return [_b_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def add_option(user, batch_id, body) -> dict:
    from app.models import AaMajorSplitOption, Major
    with session() as db:
        _require_school(user, db)
        b = _get_batch(db, batch_id)
        if b.status != "DRAFT":
            raise _invalid("仅草稿批次可配置可选专业")
        major_id = int(getattr(body, "majorId", 0) or 0)
        cap = int(getattr(body, "capacity", 0) or 0)
        if not major_id or cap <= 0:
            raise _bad("专业与容量必填（容量>0）")
        m = db.get(Major, major_id)
        if not m or m.tenant_id != _tid():
            raise not_found("专业不存在")
        dup = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
            AaMajorSplitOption.major_id == major_id, AaMajorSplitOption.is_deleted.is_(False)).first()
        if dup:
            raise _invalid("该专业已在可选列表中")
        o = AaMajorSplitOption(tenant_id=_tid(), batch_id=b.id, major_id=major_id,
                               major_name=m.major_name, capacity=cap, allocated_count=0)
        db.add(o)
        db.flush()
        _audit(db, b.id, "SPLIT_OPTION_ADD", f"{m.major_name} 容量{cap}")
        db.commit()
        return {"optionId": str(o.id), "majorId": str(major_id), "majorName": m.major_name,
                "capacity": cap}


def list_options(user, batch_id):
    from app.models import AaMajorSplitOption
    with session() as db:
        build_affairs_context(user, db)
        _get_batch(db, batch_id)
        rows = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == int(batch_id),
            AaMajorSplitOption.is_deleted.is_(False)).order_by(AaMajorSplitOption.id).all()
        return [{"optionId": str(o.id), "majorId": str(o.major_id), "majorName": o.major_name,
                 "capacity": o.capacity, "allocatedCount": o.allocated_count,
                 "remain": max(0, o.capacity - o.allocated_count)} for o in rows]


def open_batch(user, batch_id) -> dict:
    from app.models import AaMajorSplitOption
    with session() as db:
        _require_school(user, db)
        b = _get_batch(db, batch_id)
        if b.status != "DRAFT":
            raise _invalid("仅草稿批次可开放")
        n = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
            AaMajorSplitOption.is_deleted.is_(False)).count()
        if not n:
            raise _invalid("请先配置至少一个可选专业")
        b.status = "OPEN"
        _audit(db, b.id, "SPLIT_OPEN", "开放填报志愿")
        db.commit()
        return _b_dto(b)


def close_batch(user, batch_id) -> dict:
    with session() as db:
        _require_school(user, db)
        b = _get_batch(db, batch_id)
        if b.status != "OPEN":
            raise _invalid("仅开放中的批次可截止")
        b.status = "CLOSED"
        _audit(db, b.id, "SPLIT_CLOSE", "志愿截止")
        db.commit()
        return _b_dto(b)


# ══════════ 学生志愿 ══════════

def _student_profile(db, user):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    sno = ctx.get("studentNo")
    p = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                        StudentProfile.student_no == sno,
                                        StudentProfile.is_deleted.is_(False)).first()
    if not p:
        raise not_found("学生档案不存在")
    return p


def submit_volunteer(user, batch_id, choices) -> dict:
    """学生提交/修改志愿（OPEN 期间可反复改，截止后锁定）。"""
    from app.models import AaMajorSplitOption, AaMajorSplitVolunteer
    with session() as db:
        b = _get_batch(db, batch_id)
        if b.status != "OPEN":
            raise _invalid("不在志愿填报时间内")
        p = _student_profile(db, user)
        if (p.grade or "") != b.grade:
            raise _bad(f"本批次面向 {b.grade} 级，当前学籍年级不符")
        if b.source_major_id and int(p.major_id or 0) != int(b.source_major_id):
            raise _bad("不在本批次分流的大类专业范围内")
        if p.student_status != "NORMAL":
            raise no_data_scope("当前学籍状态不可填报分流志愿")
        ids = [int(x) for x in (choices or [])]
        if not ids:
            raise _bad("至少填报一个志愿")
        if len(ids) > b.max_choices:
            raise _bad(f"志愿数不得超过 {b.max_choices} 个")
        if len(set(ids)) != len(ids):
            raise _bad("志愿不得重复")
        valid = {int(o.major_id) for o in db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
            AaMajorSplitOption.is_deleted.is_(False)).all()}
        bad = [x for x in ids if x not in valid]
        if bad:
            raise _bad("志愿中包含不在可选列表的专业")
        v = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.batch_id == b.id,
            AaMajorSplitVolunteer.student_id == p.id).first()
        if v:
            v.choices_json = json.dumps(ids)
            v.status = "PENDING"
        else:
            v = AaMajorSplitVolunteer(tenant_id=_tid(), batch_id=b.id, student_id=p.id,
                                      student_no=p.student_no, student_name=p.real_name,
                                      choices_json=json.dumps(ids), status="PENDING")
            db.add(v)
        db.flush()
        _audit(db, b.id, "SPLIT_VOLUNTEER_SUBMIT", f"{p.student_no} 志愿{ids}")
        db.commit()
        return _v_dto(v)


def student_open_batches(user):
    """学生端:与本人年级(及大类源专业)匹配、正在开放填报的分流批次 + 各批可选专业。"""
    from app.models import AaMajorSplitBatch, AaMajorSplitOption
    with session() as db:
        p = _student_profile(db, user)
        rows = db.query(AaMajorSplitBatch).filter(
            AaMajorSplitBatch.tenant_id == _tid(), AaMajorSplitBatch.status == "OPEN",
            AaMajorSplitBatch.grade == (p.grade or ""),
            AaMajorSplitBatch.is_deleted.is_(False)).all()
        out = []
        for b in rows:
            if b.source_major_id and int(p.major_id or 0) != int(b.source_major_id):
                continue
            opts = db.query(AaMajorSplitOption).filter(
                AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
                AaMajorSplitOption.is_deleted.is_(False)).order_by(AaMajorSplitOption.id).all()
            d = _b_dto(b)
            d["options"] = [{"majorId": str(o.major_id), "majorName": o.major_name,
                             "capacity": o.capacity, "remain": max(0, o.capacity - o.allocated_count)}
                            for o in opts]
            out.append(d)
        return out


def my_volunteer(user, batch_id=None):
    from app.models import AaMajorSplitVolunteer
    with session() as db:
        p = _student_profile(db, user)
        q = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.student_id == p.id,
            AaMajorSplitVolunteer.is_deleted.is_(False))
        if batch_id:
            q = q.filter(AaMajorSplitVolunteer.batch_id == int(batch_id))
        return [_v_dto(v) for v in q.order_by(AaMajorSplitVolunteer.id.desc()).all()]


# ══════════ 分配 / 调剂 / 确认 ══════════

def _gpa_of(db, student_ids) -> dict:
    """学生绩点：读学业台账（成绩发布时由 _refresh_aggregates 维护的学分加权绩点）。无台账=0。"""
    from app.models import AcademicStudent
    if not student_ids:
        return {}
    rows = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(student_ids)).all()
    return {int(a.student_id): float(a.gpa or 0) for a in rows}


def allocate(user, batch_id, dry_run=False) -> dict:
    """自动分配：绩点降序（同分按学号稳定序）× 志愿顺序，首个有余量专业录取——分数优先遵循志愿。"""
    from app.models import AaMajorSplitOption, AaMajorSplitVolunteer
    with session() as db:
        _require_school(user, db)
        b = _get_batch(db, batch_id)
        if b.status != "CLOSED":
            raise _invalid("请先截止志愿再分配（已分配批次请用人工调剂）")
        vols = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.batch_id == b.id,
            AaMajorSplitVolunteer.is_deleted.is_(False)).all()
        opts = {int(o.major_id): o for o in db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
            AaMajorSplitOption.is_deleted.is_(False)).all()}
        gpa = _gpa_of(db, [v.student_id for v in vols])
        remain = {mid: max(0, o.capacity - o.allocated_count) for mid, o in opts.items()}

        ordered = sorted(vols, key=lambda v: (-(gpa.get(int(v.student_id), 0)), v.student_no or "", v.id))
        allocated, unallocated = 0, 0
        for v in ordered:
            choices = [int(x) for x in (json.loads(v.choices_json) if v.choices_json else [])]
            got = None
            for rank, mid in enumerate(choices, start=1):
                if remain.get(mid, 0) > 0:
                    got = (mid, rank)
                    remain[mid] -= 1
                    break
            v.gpa_snapshot = gpa.get(int(v.student_id), 0)
            if got:
                v.result_major_id, v.result_choice_rank, v.status = got[0], got[1], "ALLOCATED"
                allocated += 1
            else:
                v.result_major_id, v.result_choice_rank, v.status = None, None, "UNALLOCATED"
                unallocated += 1
        if dry_run:
            summary = _summary(vols, opts, remain)
            db.rollback()
            return {"batchId": str(b.id), "dryRun": True, "allocated": allocated,
                    "unallocated": unallocated, "options": summary}
        for mid, o in opts.items():
            o.allocated_count = o.capacity - remain.get(mid, 0) if mid in remain else o.allocated_count
        b.status = "ALLOCATED"
        _audit(db, b.id, "SPLIT_ALLOCATE", f"分配{allocated}/待调剂{unallocated}")
        db.commit()
        return {"batchId": str(b.id), "dryRun": False, "allocated": allocated,
                "unallocated": unallocated, "options": _summary(vols, opts, remain)}


def _summary(vols, opts, remain):
    return [{"majorId": str(mid), "majorName": o.major_name, "capacity": o.capacity,
             "allocated": o.capacity - remain.get(mid, 0), "remain": remain.get(mid, 0)}
            for mid, o in opts.items()]


def list_volunteers(user, batch_id, status=None, page=1, page_size=100):
    """志愿与分配结果名单(教务处口径)。收敛 TENANT_ALL,防越范围读全校学生绩点/志愿/录取(修数据范围红线)。"""
    from app.models import AaMajorSplitVolunteer
    with session() as db:
        _require_school(user, db)
        _get_batch(db, batch_id)
        q = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.batch_id == int(batch_id),
            AaMajorSplitVolunteer.is_deleted.is_(False))
        if status:
            q = q.filter(AaMajorSplitVolunteer.status == status)
        # MySQL 无 NULLS LAST 语法：先按"绩点是否为空"再按绩点降序（空排最后）
        rows = q.order_by(AaMajorSplitVolunteer.gpa_snapshot.is_(None),
                          AaMajorSplitVolunteer.gpa_snapshot.desc(),
                          AaMajorSplitVolunteer.id).all()
        return [_v_dto(v) for v in rows[(page - 1) * page_size: page * page_size]], len(rows)


def reassign(user, volunteer_id, major_id, reason) -> dict:
    """人工调剂（ALLOCATED 批次内）：目标专业须有余量；原因≥5字留痕；rank=0 标记为调剂。"""
    from app.models import AaMajorSplitOption, AaMajorSplitVolunteer
    if not reason or len(reason.strip()) < 5:
        raise _bad("调剂原因必填且不少于 5 字")
    with session() as db:
        _require_school(user, db)
        v = db.get(AaMajorSplitVolunteer, int(volunteer_id))
        if not v or v.is_deleted or v.tenant_id != _tid():
            raise not_found("志愿记录不存在")
        b = _get_batch(db, v.batch_id)
        if b.status != "ALLOCATED":
            raise _invalid("仅已分配（未确认）批次可人工调剂")
        target = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
            AaMajorSplitOption.major_id == int(major_id),
            AaMajorSplitOption.is_deleted.is_(False)).first()
        if not target:
            raise not_found("目标专业不在本批次可选列表")
        upd = db.query(AaMajorSplitOption).filter(
            AaMajorSplitOption.id == target.id, AaMajorSplitOption.tenant_id == _tid(),
            AaMajorSplitOption.allocated_count < AaMajorSplitOption.capacity).update(
            {AaMajorSplitOption.allocated_count: AaMajorSplitOption.allocated_count + 1},
            synchronize_session=False)
        if not upd:
            raise _invalid("目标专业容量已满")
        if v.result_major_id:
            db.query(AaMajorSplitOption).filter(
                AaMajorSplitOption.tenant_id == _tid(), AaMajorSplitOption.batch_id == b.id,
                AaMajorSplitOption.major_id == v.result_major_id,
                AaMajorSplitOption.allocated_count > 0).update(
                {AaMajorSplitOption.allocated_count: AaMajorSplitOption.allocated_count - 1},
                synchronize_session=False)
        v.result_major_id, v.result_choice_rank = int(major_id), 0
        v.adjust_reason, v.status = reason.strip(), "ALLOCATED"
        _audit(db, b.id, "SPLIT_REASSIGN", f"{v.student_no} 调剂至专业{major_id}：{reason.strip()[:100]}")
        db.commit()
        return _v_dto(v)


def confirm(user, batch_id) -> dict:
    """确认分流：写 StudentProfile.major_id + 逐生审计。UNALLOCATED 未清零禁止确认。"""
    from app.models import AaMajorSplitVolunteer, StudentProfile
    with session() as db:
        _require_school(user, db)
        b = _get_batch(db, batch_id)
        if b.status != "ALLOCATED":
            raise _invalid("仅已分配批次可确认")
        pend = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.batch_id == b.id,
            AaMajorSplitVolunteer.status == "UNALLOCATED",
            AaMajorSplitVolunteer.is_deleted.is_(False)).count()
        if pend:
            raise _invalid(f"尚有 {pend} 名学生未分配到专业，请先人工调剂后再确认")
        vols = db.query(AaMajorSplitVolunteer).filter(
            AaMajorSplitVolunteer.tenant_id == _tid(), AaMajorSplitVolunteer.batch_id == b.id,
            AaMajorSplitVolunteer.status == "ALLOCATED",
            AaMajorSplitVolunteer.is_deleted.is_(False)).all()
        n = 0
        for v in vols:
            p = db.get(StudentProfile, int(v.student_id))
            if p and not p.is_deleted:
                old = p.major_id
                p.major_id = int(v.result_major_id)
                v.status = "CONFIRMED"
                n += 1
                _audit(db, b.id, "SPLIT_APPLY_STUDENT",
                       f"{v.student_no} 专业 {old}→{v.result_major_id}（第{v.result_choice_rank or '调剂'}志愿，绩点{v.gpa_snapshot}）")
        b.status = "CONFIRMED"
        _audit(db, b.id, "SPLIT_CONFIRM", f"分流生效 {n} 人")
        db.commit()
        return {"batchId": str(b.id), "confirmed": n, "status": b.status}
