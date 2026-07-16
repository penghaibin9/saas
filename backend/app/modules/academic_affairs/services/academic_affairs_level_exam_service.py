"""等级考务服务（对标商业教务 5-2：四六级/普通话/职业技能等级证书报名闭环）。

流程：建考试(类别/等级/费用) → OPEN 学生报名(可取消) → 教务缴费确认 → CLOSED →
成绩录入(分数按合格线判 PASS/FAIL，或直接录结论+证书号) → FINISHED。

费用为登记口径（实际收缴走财务/校园缴费渠道，本域只记"已缴确认"状态与操作留痕）。
通过记录可回填证书号——供 1+X 证书台账与国标数据上报（数字基座 ODS_GZXZSSJ）后续取数。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

CATEGORIES = ("CET", "PUTONGHUA", "SKILL", "OTHER")


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("realName") or ctx.get("loginName") or ctx.get("userId") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_LEVEL_EXAM", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可管理等级考务")
    return ctx


def _e_dto(e):
    return {"examId": str(e.id), "examName": e.exam_name, "category": e.category, "level": e.level,
            "examDate": e.exam_date, "fee": float(e.fee) if e.fee is not None else None,
            "regStart": _iso(e.reg_start), "regEnd": _iso(e.reg_end),
            "passLine": e.pass_line, "status": e.status}


def _r_dto(r):
    return {"regId": str(r.id), "examId": str(r.exam_id), "studentId": str(r.student_id),
            "studentNo": r.student_no, "studentName": r.student_name, "feeStatus": r.fee_status,
            "score": r.score, "result": r.result, "certNo": r.cert_no, "status": r.status}


def _get_exam(db, eid):
    from app.models import AaLevelExam
    e = db.get(AaLevelExam, int(eid))
    if not e or e.is_deleted or e.tenant_id != _tid():
        raise not_found("等级考试不存在")
    return e


def create_exam(user, body) -> dict:
    from app.models import AaLevelExam
    with session() as db:
        _require_school(user, db)
        name = (getattr(body, "examName", None) or "").strip()
        if not name:
            raise _bad("考试名称必填")
        cat = (getattr(body, "category", None) or "SKILL").upper()
        if cat not in CATEGORIES:
            raise _bad("考试类别非法（CET/PUTONGHUA/SKILL/OTHER）")
        e = AaLevelExam(tenant_id=_tid(), exam_name=name, category=cat,
                        level=getattr(body, "level", None),
                        exam_date=getattr(body, "examDate", None),
                        fee=getattr(body, "fee", None),
                        pass_line=getattr(body, "passLine", None), status="DRAFT")
        db.add(e)
        db.flush()
        _audit(db, e.id, "LEVEL_EXAM_CREATE", name)
        db.commit()
        return _e_dto(e)


def list_exams(user, status=None, page=1, page_size=20):
    from app.models import AaLevelExam
    with session() as db:
        build_affairs_context(user, db)
        q = db.query(AaLevelExam).filter(AaLevelExam.tenant_id == _tid(),
                                         AaLevelExam.is_deleted.is_(False))
        if status:
            q = q.filter(AaLevelExam.status == status)
        rows = q.order_by(AaLevelExam.id.desc()).all()
        return [_e_dto(e) for e in rows[(page - 1) * page_size: page * page_size]], len(rows)


def transition(user, exam_id, action) -> dict:
    """OPEN 开放报名 / CLOSE 截止 / FINISH 完成（须成绩全录）。"""
    from app.models import AaLevelExamReg
    with session() as db:
        _require_school(user, db)
        e = _get_exam(db, exam_id)
        act = (action or "").upper()
        legal = {"OPEN": ("DRAFT",), "CLOSE": ("OPEN",), "FINISH": ("CLOSED",)}
        if act not in legal:
            raise _bad("无效动作（OPEN/CLOSE/FINISH）")
        if e.status not in legal[act]:
            raise _invalid(f"当前状态 {e.status} 不可执行 {act}")
        if act == "FINISH":
            pend = db.query(AaLevelExamReg).filter(
                AaLevelExamReg.tenant_id == _tid(), AaLevelExamReg.exam_id == e.id,
                AaLevelExamReg.status == "REGISTERED",
                AaLevelExamReg.is_deleted.is_(False)).count()
            if pend:
                raise _invalid(f"尚有 {pend} 条报名未录成绩，不可完成")
        e.status = {"OPEN": "OPEN", "CLOSE": "CLOSED", "FINISH": "FINISHED"}[act]
        _audit(db, e.id, f"LEVEL_EXAM_{act}", e.exam_name)
        db.commit()
        return _e_dto(e)


# ══════════ 报名 ══════════

def _student_profile(db):
    from app.models import StudentProfile
    ctx = get_current_user_ctx() or {}
    p = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                        StudentProfile.student_no == ctx.get("studentNo"),
                                        StudentProfile.is_deleted.is_(False)).first()
    if not p:
        raise not_found("学生档案不存在")
    return p


def student_register(user, exam_id) -> dict:
    """学生报名（取消后可复报，复用同行）。"""
    from app.models import AaLevelExamReg
    with session() as db:
        e = _get_exam(db, exam_id)
        if e.status != "OPEN":
            raise _invalid("不在报名时间内")
        p = _student_profile(db)
        if p.student_status != "NORMAL":
            raise no_data_scope("当前学籍状态不可报名")
        r = db.query(AaLevelExamReg).filter(
            AaLevelExamReg.tenant_id == _tid(), AaLevelExamReg.exam_id == e.id,
            AaLevelExamReg.student_id == p.id).first()
        if r and r.status == "REGISTERED":
            raise _invalid("已报名本次考试")
        if r:
            r.status, r.fee_status = "REGISTERED", "UNPAID"
            r.score = r.result = r.cert_no = None
        else:
            r = AaLevelExamReg(tenant_id=_tid(), exam_id=e.id, student_id=p.id,
                               student_no=p.student_no, student_name=p.real_name,
                               fee_status="UNPAID", status="REGISTERED")
            db.add(r)
        db.flush()
        _audit(db, e.id, "LEVEL_REG", f"{p.student_no} 报名 {e.exam_name}")
        db.commit()
        return _r_dto(r)


def student_cancel(user, exam_id) -> dict:
    from app.models import AaLevelExamReg
    with session() as db:
        e = _get_exam(db, exam_id)
        if e.status != "OPEN":
            raise _invalid("报名已截止，不可取消")
        p = _student_profile(db)
        r = db.query(AaLevelExamReg).filter(
            AaLevelExamReg.tenant_id == _tid(), AaLevelExamReg.exam_id == e.id,
            AaLevelExamReg.student_id == p.id,
            AaLevelExamReg.status == "REGISTERED").first()
        if not r:
            raise not_found("无有效报名记录")
        r.status = "CANCELLED"
        _audit(db, e.id, "LEVEL_REG_CANCEL", p.student_no)
        db.commit()
        return _r_dto(r)


def my_regs(user):
    from app.models import AaLevelExamReg
    with session() as db:
        p = _student_profile(db)
        rows = db.query(AaLevelExamReg).filter(
            AaLevelExamReg.tenant_id == _tid(), AaLevelExamReg.student_id == p.id,
            AaLevelExamReg.is_deleted.is_(False)).order_by(AaLevelExamReg.id.desc()).all()
        return [_r_dto(r) for r in rows]


def list_regs(user, exam_id, status=None, page=1, page_size=100):
    """报名名单(教务处口径)。收敛 TENANT_ALL,防越范围读全校报名/缴费/成绩(修数据范围红线)。"""
    from app.models import AaLevelExamReg
    with session() as db:
        _require_school(user, db)
        _get_exam(db, exam_id)
        q = db.query(AaLevelExamReg).filter(
            AaLevelExamReg.tenant_id == _tid(), AaLevelExamReg.exam_id == int(exam_id),
            AaLevelExamReg.is_deleted.is_(False))
        if status:
            q = q.filter(AaLevelExamReg.status == status)
        rows = q.order_by(AaLevelExamReg.id).all()
        return [_r_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], len(rows)


def confirm_fee(user, reg_id) -> dict:
    """教务缴费确认（UNPAID→PAID，留痕）。"""
    from app.models import AaLevelExamReg
    with session() as db:
        _require_school(user, db)
        r = db.get(AaLevelExamReg, int(reg_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("报名记录不存在")
        if r.status != "REGISTERED":
            raise _invalid("仅有效报名可确认缴费")
        if r.fee_status == "PAID":
            raise _invalid("已确认缴费")
        r.fee_status = "PAID"
        _audit(db, r.exam_id, "LEVEL_FEE_CONFIRM", r.student_no or "")
        db.commit()
        return _r_dto(r)


def enter_result(user, reg_id, body) -> dict:
    """成绩录入：分数制按合格线判定；结论制直接录 PASS/FAIL；通过可回填证书号。"""
    from app.models import AaLevelExamReg
    with session() as db:
        _require_school(user, db)
        r = db.get(AaLevelExamReg, int(reg_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("报名记录不存在")
        e = _get_exam(db, r.exam_id)
        if e.status not in ("CLOSED", "FINISHED"):
            raise _invalid("请先截止报名再录成绩")
        if r.status == "CANCELLED":
            raise _invalid("已取消的报名不可录成绩")
        score = getattr(body, "score", None)
        result = (getattr(body, "result", None) or "").upper() or None
        if score is not None:
            score = int(score)
            if not (0 <= score <= 750):
                raise _bad("分数非法")
            r.score = score
            if e.pass_line:
                result = "PASS" if score >= e.pass_line else "FAIL"
        if result not in ("PASS", "FAIL"):
            raise _bad("须提供结论（PASS/FAIL）或在设置合格线后录入分数")
        r.result = result
        r.cert_no = getattr(body, "certNo", None) if result == "PASS" else None
        r.status = "SCORED"
        _audit(db, r.exam_id, "LEVEL_RESULT", f"{r.student_no} {result}{'/' + str(r.score) if r.score is not None else ''}")
        db.commit()
        return _r_dto(r)
