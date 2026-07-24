"""13A-D 党团建设（07 卡）：党/团员发展阶段台账 + 阶段流转（append-only）。

阶段码遵循公开《中国共产党发展党员工作细则》通用五阶段；本服务只做"记录学校实际推进"的台账，
不写死各校时限/审批权限（属校本制度，见历史欠账）。材料仅存 file_id 脱敏，列表/时间线不返回明文。
政治面貌回写学生主档为跨域集成，本波次不做（见历史欠账）。留痕 AffairsAuditTrail(biz_type=LEAGUE)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.services.db_service import _iso, _tid, session

DEV_TYPES = ("PARTY", "LEAGUE")
PARTY_STAGES = ("APPLICANT", "ACTIVIST", "DEVELOPMENT_TARGET", "PROBATIONARY", "FULL_MEMBER")
L_STAGE = {"APPLICANT": "入党申请人", "ACTIVIST": "入党积极分子", "DEVELOPMENT_TARGET": "发展对象",
           "PROBATIONARY": "预备党员", "FULL_MEMBER": "正式党员"}
L_TYPE = {"PARTY": "党员发展", "LEAGUE": "团员发展"}
L_STATUS = {"ONGOING": "发展中", "COMPLETED": "已转正", "TERMINATED": "已终止"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), u.get("userId")


def _uid_int(user):
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, _ = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="LEAGUE",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _load(db, dev_id):
    from app.models import AffairsLeagueDev
    d = db.scalars(select(AffairsLeagueDev).where(
        AffairsLeagueDev.id == int(dev_id), AffairsLeagueDev.tenant_id == _tid(),
        AffairsLeagueDev.is_deleted.is_(False))).first()
    if not d:
        raise not_found("发展台账不存在")
    return d


def _dev_row(d, s=None) -> dict:
    return {"devId": str(d.id), "studentId": str(d.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "devType": d.dev_type, "devTypeLabel": L_TYPE.get(d.dev_type, d.dev_type),
            "currentStage": d.current_stage, "currentStageLabel": L_STAGE.get(d.current_stage, d.current_stage),
            "branchName": d.branch_name or "", "status": d.status,
            "statusLabel": L_STATUS.get(d.status, d.status), "startedAt": _iso(d.started_at),
            "completedAt": _iso(d.completed_at), "version": d.version}


def list_dev(user, dev_type=None, stage=None, status=None, page=1, page_size=50):
    """发展台账列表（数据范围过滤；不含材料明文）。"""
    from app.models import AffairsLeagueDev, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [AffairsLeagueDev.tenant_id == _tid(), AffairsLeagueDev.is_deleted.is_(False)]
        if dev_type:
            conds.append(AffairsLeagueDev.dev_type == dev_type)
        if stage:
            conds.append(AffairsLeagueDev.current_stage == stage)
        if status:
            conds.append(AffairsLeagueDev.status == status)
        student_join = and_(
            StudentProfile.id == AffairsLeagueDev.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed))
        page = max(1, int(page or 1))
        page_size = max(1, min(200, int(page_size or 50)))
        total = int(db.scalar(select(func.count()).select_from(AffairsLeagueDev)
                              .outerjoin(StudentProfile, student_join).where(*conds)) or 0)
        rows = db.execute(select(AffairsLeagueDev, StudentProfile)
                          .outerjoin(StudentProfile, student_join).where(*conds)
                          .order_by(AffairsLeagueDev.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return [_dev_row(d, s) for d, s in rows], total


def create_dev(body, user) -> dict:
    from app.models import AffairsLeagueDev, AffairsLeagueDevStage, StudentProfile
    sid = int(getattr(body, "studentId", 0) or 0)
    dev_type = getattr(body, "devType", "PARTY") or "PARTY"
    if dev_type not in DEV_TYPES:
        raise AppException("VALIDATION_ERROR", "发展类型非法")
    with session() as db:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == sid, StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False))).first() if sid else None
        if not s:
            raise not_found("学生不存在")
        dup = db.scalars(select(AffairsLeagueDev).where(
            AffairsLeagueDev.tenant_id == _tid(), AffairsLeagueDev.student_id == sid,
            AffairsLeagueDev.dev_type == dev_type, AffairsLeagueDev.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生该类型发展台账已存在")
        d = AffairsLeagueDev(tenant_id=_tid(), student_id=sid, dev_type=dev_type,
                             current_stage="APPLICANT", branch_name=getattr(body, "branchName", None),
                             status="ONGOING", started_at=datetime.utcnow(), created_by=_uid_int(user))
        db.add(d); db.flush()
        db.add(AffairsLeagueDevStage(tenant_id=_tid(), dev_id=d.id, from_stage=None,
                                     to_stage="APPLICANT", operator=_op()[0],
                                     occurred_at=datetime.utcnow(), created_by=_uid_int(user)))
        _audit(db, d.id, "LEAGUE_DEV_CREATE", f"student={sid} {dev_type}")
        db.commit(); db.refresh(d)
        return _dev_row(d, s)


def advance_stage(dev_id, body, user) -> dict:
    """推进到指定阶段（记 append-only 流转 + 材料 file_id 脱敏）。到 FULL_MEMBER→COMPLETED。"""
    from app.models import AffairsLeagueDevStage, StudentProfile
    to_stage = (getattr(body, "toStage", "") or "").strip()
    if to_stage not in PARTY_STAGES:
        raise AppException("VALIDATION_ERROR", "目标阶段码非法")
    with session() as db:
        d = _load(db, dev_id)
        if d.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "该台账非发展中，不可推进")
        check_version(d.version, getattr(body, "version", None))
        cur_i = PARTY_STAGES.index(d.current_stage) if d.current_stage in PARTY_STAGES else -1
        to_i = PARTY_STAGES.index(to_stage)
        if to_i <= cur_i:
            raise AppException("DATA_CONFLICT", "目标阶段须晚于当前阶段")
        from_stage = d.current_stage
        d.current_stage, d.version = to_stage, d.version + 1
        if to_stage == "FULL_MEMBER":
            d.status, d.completed_at = "COMPLETED", datetime.utcnow()
        db.add(AffairsLeagueDevStage(tenant_id=_tid(), dev_id=d.id, from_stage=from_stage,
                                     to_stage=to_stage,
                                     material_file_id=getattr(body, "materialFileId", None),
                                     operator=_op()[0], remark=getattr(body, "remark", None),
                                     occurred_at=datetime.utcnow(), created_by=_uid_int(user)))
        _audit(db, d.id, "LEAGUE_DEV_ADVANCE", f"{from_stage}->{to_stage}")
        db.commit(); db.refresh(d)
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(d.student_id), StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False))).first()
        return _dev_row(d, s)


def terminate_dev(dev_id, user, reason="", expected_version=None) -> dict:
    from app.models import AffairsLeagueDevStage, StudentProfile
    if len((reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "终止原因至少 5 字")
    with session() as db:
        d = _load(db, dev_id)
        if d.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "仅发展中台账可终止")
        check_version(d.version, expected_version)
        d.status, d.version = "TERMINATED", d.version + 1
        db.add(AffairsLeagueDevStage(tenant_id=_tid(), dev_id=d.id, from_stage=d.current_stage,
                                     to_stage=d.current_stage, operator=_op()[0],
                                     remark=f"终止：{reason.strip()}", occurred_at=datetime.utcnow(),
                                     created_by=_uid_int(user)))
        _audit(db, d.id, "LEAGUE_DEV_TERMINATE", reason.strip())
        db.commit(); db.refresh(d)
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(d.student_id), StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False))).first()
        return _dev_row(d, s)


def list_stages(dev_id, user):
    """阶段时间线（材料仅返回是否有附件，不含明文/下载链，下载另走授权+审计后续接入）。"""
    from app.models import AffairsLeagueDevStage
    with session() as db:
        _load(db, dev_id)
        rows = db.scalars(select(AffairsLeagueDevStage).where(
            AffairsLeagueDevStage.tenant_id == _tid(), AffairsLeagueDevStage.dev_id == int(dev_id),
            AffairsLeagueDevStage.is_deleted.is_(False)).order_by(AffairsLeagueDevStage.id.asc())).all()
        return [{"stageId": str(r.id), "fromStage": r.from_stage or "",
                 "fromStageLabel": L_STAGE.get(r.from_stage, "") if r.from_stage else "",
                 "toStage": r.to_stage, "toStageLabel": L_STAGE.get(r.to_stage, r.to_stage),
                 "hasMaterial": r.material_file_id is not None, "operator": r.operator or "",
                 "remark": r.remark or "", "occurredAt": _iso(r.occurred_at)} for r in rows]
