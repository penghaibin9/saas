"""13B-P6 毕业资格预审（七项跨域供数三态判定 + 学院初审→教务终审）。

七项只读六域(学籍/学分成绩/实习/毕设/处分/就业)，每项 PASS/FAIL/UNKNOWN + 证据引用。
终审经 change_student_status 写主档 GRADUATED/COMPLETED/INCOMPLETE(强制二次确认)。
学分项按培养方案总学分逐项审(对齐商业软件)。批次生成/预审均幂等，结果覆盖非追加。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.academic_affairs_status_service import (audit_status_change,
                                                          change_student_status, is_enrolled)
from app.services.db_service import _iso, _tid, session

# 七项供数（PASS/FAIL/UNKNOWN）；就业默认提醒非卡审（规则开关）
ITEMS = ("STATUS", "CREDIT", "INTERNSHIP", "GRADUATION_DESIGN", "DISCIPLINE", "EMPLOYMENT", "ARCHIVE")
_CONCLUSION = {"GRADUATED": "GRADUATED", "COMPLETED": "COMPLETED", "DELAYED": "INCOMPLETE"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_GRAD_AUDIT", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


# ── 七项供数检查（只读六域，三态）──

def _check_status(db, s):
    ok = is_enrolled(s.student_status)
    return {"item": "STATUS", "result": "PASS" if ok else "FAIL",
            "owner": "COLLEGE_STAFF", "evidence": f"student_status={s.student_status}"}


def _check_credit(db, s):
    """学分按培养方案总学分逐项审（获得学分 >= 方案 total_credits）。无方案/无成绩→UNKNOWN。"""
    from app.models import (AaProgram, AaProgramBinding, AcademicGrade, AcademicStudent)
    prog = None
    if s.major_id:
        binding = db.scalars(select(AaProgramBinding).where(
            AaProgramBinding.tenant_id == _tid(), AaProgramBinding.major_id == s.major_id,
            AaProgramBinding.status == "ACTIVE", AaProgramBinding.is_deleted.is_(False))).first()
        if binding:
            prog = db.get(AaProgram, int(binding.program_id))
    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == s.id,
        AcademicStudent.is_deleted.is_(False))).first()
    if not prog or not prog.total_credits or not acad:
        return {"item": "CREDIT", "result": "UNKNOWN", "owner": "AA_STAFF",
                "evidence": "无培养方案绑定或无学业记录"}
    earned = db.scalar(select(func.coalesce(func.sum(AcademicGrade.credit_value), 0)).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.pass_status == "PASSED", AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False))) or 0
    ok = float(earned) >= float(prog.total_credits)
    return {"item": "CREDIT", "result": "PASS" if ok else "FAIL", "owner": "AA_STAFF",
            "evidence": f"已得 {float(earned)}/{float(prog.total_credits)} 学分"}


def _check_discipline(db, s):
    """无未解除处分(record_status=ACTIVE)。无在校台账→UNKNOWN。"""
    from app.models import CsDiscipline, CsServiceStudent
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == s.id,
        CsServiceStudent.is_deleted.is_(False))).first()
    active = 0
    if cs:
        active = db.scalar(select(func.count()).select_from(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.cs_student_id == cs.id,
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False))) or 0
    return {"item": "DISCIPLINE", "result": "PASS" if active == 0 else "FAIL", "owner": "COUNSELOR",
            "evidence": f"未解除处分 {active} 条"}


def _check_domain_exists(db, item, model, student_field, s, owner, done_check=None):
    """通用：域内有该生记录则视情况 PASS，无则 UNKNOWN（默认非卡审提醒）。"""
    try:
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(), getattr(model, student_field) == s.id,
            model.is_deleted.is_(False))).all()
    except Exception:  # noqa: BLE001
        rows = []
    if not rows:
        return {"item": item, "result": "UNKNOWN", "owner": owner, "evidence": "无该域记录"}
    ok = True if done_check is None else any(done_check(r) for r in rows)
    return {"item": item, "result": "PASS" if ok else "FAIL", "owner": owner,
            "evidence": f"{len(rows)} 条记录"}


def _run_items(db, s) -> list:
    from app.models import EmpStudent, GraduationStudent, InternshipRecord
    items = [_check_status(db, s), _check_credit(db, s), _check_discipline(db, s)]
    items.append(_check_domain_exists(db, "INTERNSHIP", InternshipRecord, "student_id", s, "GD_MENTOR"))
    items.append(_check_domain_exists(db, "GRADUATION_DESIGN", GraduationStudent, "student_id", s, "GD_MENTOR"))
    # 就业默认提醒非卡审 → 有记录 PASS，无则 UNKNOWN（不判 FAIL）
    items.append(_check_domain_exists(db, "EMPLOYMENT", EmpStudent, "student_id", s, "AA_STAFF"))
    items.append({"item": "ARCHIVE", "result": "UNKNOWN", "owner": "COUNSELOR", "evidence": "迎新归档待接入"})
    return items


def _overall(items) -> str:
    # 任一 FAIL → 异常；否则通过（UNKNOWN 不阻断，进人工复核）
    return "SYSTEM_ABNORMAL" if any(i["result"] == "FAIL" for i in items) else "SYSTEM_PASSED"


# ═══════════ 批次 / 生成 / 预审 ═══════════

def create_batch(body, user) -> dict:
    with session() as db:
        from app.models import AaGraduationAuditBatch
        b = AaGraduationAuditBatch(tenant_id=_tid(), batch_name=body.batchName,
                                   grade_year=getattr(body, "gradeYear", None),
                                   major_id=(int(body.majorId) if getattr(body, "majorId", None) else None),
                                   status="DRAFT")
        db.add(b)
        db.flush()
        _audit(db, b.id, "CREATE")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "batchName": b.batch_name, "status": b.status}


def generate(batch_id, user, student_ids=None) -> dict:
    """圈定应届生生成预审结果行（幂等）。传 student_ids 显式圈定，否则按批次年级/专业。"""
    with session() as db:
        from app.models import (AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile)
        b = db.get(AaGraduationAuditBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("预审批次不存在")
        if student_ids:
            sids = [int(x) for x in student_ids]
        else:
            conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
            if b.grade_year:
                conds.append(StudentProfile.grade == b.grade_year)
            if b.major_id:
                conds.append(StudentProfile.major_id == b.major_id)
            sids = [s.id for s in db.scalars(select(StudentProfile).where(*conds)).all()]
        made = 0
        for sid in sids:
            exist = db.scalars(select(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
                AaGraduationAuditResult.student_id == sid, AaGraduationAuditResult.is_deleted.is_(False))).first()
            if exist:
                continue
            db.add(AaGraduationAuditResult(tenant_id=_tid(), batch_id=b.id, student_id=sid,
                                           status="WAIT_PRECHECK"))
            made += 1
        b.status, b.generate_at = "GENERATED", datetime.utcnow()
        _audit(db, b.id, "GENERATE", f"+{made}")
        db.commit()
        return {"batchId": str(batch_id), "generated": made, "status": "GENERATED"}


def precheck(batch_id, user) -> dict:
    """七项供数三态判定（幂等，结果覆盖非追加）。"""
    with session() as db:
        from app.models import (AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile)
        b = db.get(AaGraduationAuditBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("预审批次不存在")
        rows = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
            AaGraduationAuditResult.status.in_(["WAIT_PRECHECK", "SYSTEM_PASSED", "SYSTEM_ABNORMAL"]),
            AaGraduationAuditResult.is_deleted.is_(False))).all()
        passed = abnormal = 0
        for r in rows:
            s = db.get(StudentProfile, int(r.student_id))
            if not s:
                continue
            items = _run_items(db, s)
            overall = _overall(items)
            r.item_results_json = json.dumps(items, ensure_ascii=False)
            r.overall, r.status = overall, overall
            r.rerun_count += 1
            if overall == "SYSTEM_PASSED":
                passed += 1
            else:
                abnormal += 1
        b.status = "PRECHECKED"
        _audit(db, b.id, "PRECHECK", f"pass={passed},abnormal={abnormal}")
        db.commit()
        return {"batchId": str(batch_id), "passed": passed, "abnormal": abnormal}


# ═══════════ 审核（学院初审→教务终审，终审写主档）═══════════

def college_review(result_id, user, action, note="") -> dict:
    with session() as db:
        from app.models import AaGraduationAuditResult
        r = db.get(AaGraduationAuditResult, int(result_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("预审结果不存在")
        if r.status not in ("SYSTEM_PASSED", "SYSTEM_ABNORMAL", "COLLEGE_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该结果当前状态不可初审")
        if (action or "").upper() == "APPROVE":
            r.status, r.review_note = "ACADEMIC_REVIEW", note
            _audit(db, r.id, "COLLEGE_APPROVE")
        else:
            if not note or len(note.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            r.status, r.review_note = "REJECTED", note.strip()
            _audit(db, r.id, "COLLEGE_REJECT", note.strip())
        db.commit()
        db.refresh(r)
        return _row(r)


def academic_final(result_id, user, conclusion, confirm=False) -> dict:
    """教务终审：写结论(GRADUATED/COMPLETED/DELAYED)，经 change_student_status 写主档，强制二次确认。"""
    conclusion = (conclusion or "").upper()
    if conclusion not in _CONCLUSION:
        raise AppException("VALIDATION_ERROR", "结论非法（GRADUATED/COMPLETED/DELAYED）")
    if not confirm:
        raise AppException("DATA_CONFLICT", "毕业结论涉及学籍终态，需二次确认(confirm=true)")
    _n, _r, uid = _op()
    with session() as db:
        from app.models import AaGraduationAuditResult
        r = db.get(AaGraduationAuditResult, int(result_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("预审结果不存在")
        if r.status != "ACADEMIC_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅学院初审通过的结果可终审")
        to_status = _CONCLUSION[conclusion]
        res = change_student_status(db, r.student_id, to_status, change_type="GRADUATE",
                                    reason=f"毕业预审终审：{conclusion}", operator=uid, source_biz_id=r.id)
        r.conclusion, r.status = conclusion, conclusion
        _audit(db, r.id, "ACADEMIC_FINAL", f"{conclusion}/{to_status}")
        db.commit()
        db.refresh(r)
        out = _row(r)
    audit_status_change(r.student_id, res["fromStatus"], res["toStatus"], "GRADUATE", uid)
    return out


# ═══════════ 查询 / 名单 ═══════════

def _row(r) -> dict:
    return {"resultId": str(r.id), "batchId": str(r.batch_id), "studentId": str(r.student_id),
            "overall": r.overall, "conclusion": r.conclusion, "status": r.status,
            "rerunCount": r.rerun_count,
            "items": json.loads(r.item_results_json) if r.item_results_json else []}


def get_result(result_id, user) -> dict:
    with session() as db:
        from app.models import AaGraduationAuditResult
        r = db.get(AaGraduationAuditResult, int(result_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("预审结果不存在")
        return _row(r)


def list_results(batch_id, user, status=None, overall=None, page=1, page_size=50):
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        conds = [AaGraduationAuditResult.tenant_id == _tid(),
                 AaGraduationAuditResult.batch_id == int(batch_id),
                 AaGraduationAuditResult.is_deleted.is_(False)]
        if status:
            conds.append(AaGraduationAuditResult.status == status)
        if overall:
            conds.append(AaGraduationAuditResult.overall == overall)
        rows = db.scalars(select(AaGraduationAuditResult).where(*conds).order_by(
            AaGraduationAuditResult.id.desc())).all()
        out = []
        for r in rows:
            s = db.get(StudentProfile, int(r.student_id))
            d = _row(r)
            d["realName"] = s.real_name if s else ""
            out.append(d)
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def rosters(batch_id, user) -> dict:
    """三名单：毕业/结业/延毕（按终审结论）。"""
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        rows = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(),
            AaGraduationAuditResult.batch_id == int(batch_id),
            AaGraduationAuditResult.conclusion.is_not(None),
            AaGraduationAuditResult.is_deleted.is_(False))).all()
        buckets = {"GRADUATED": [], "COMPLETED": [], "DELAYED": []}
        for r in rows:
            s = db.get(StudentProfile, int(r.student_id))
            if r.conclusion in buckets:
                buckets[r.conclusion].append({"studentId": str(r.student_id),
                                              "realName": s.real_name if s else ""})
        return {"graduated": buckets["GRADUATED"], "completed": buckets["COMPLETED"],
                "delayed": buckets["DELAYED"],
                "counts": {k: len(v) for k, v in buckets.items()}}
