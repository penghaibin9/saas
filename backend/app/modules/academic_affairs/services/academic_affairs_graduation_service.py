"""13B-P6/Tier1 毕业资格审核（十项跨域供数三态判定 + 学院初审→教务终审→归档）。

十项只读六域(学籍/学分/必修课程/选修课程/实践环节/实习/毕设/处分/就业/归档)，每项 PASS/FAIL/UNKNOWN + 证据引用。
终审经 change_student_status 写主档 GRADUATED/COMPLETED/INCOMPLETE(强制二次确认)。
学分/课程/实践三项按培养方案 requirement_json 分模块学分逐项审(对齐商业软件§5.4 取数矩阵)。
批次生成/预审均幂等，结果覆盖非追加；归档只收敛已终审的 GRADUATED/COMPLETED 行，DELAYED/REJECTED 留待重审不归档。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.modules.academic_affairs.services.academic_affairs_status_service import (audit_status_change,
                                                          change_student_status, is_enrolled)
from app.services.db_service import _iso, _tid, session

# 十项供数（PASS/FAIL/UNKNOWN），顺序对齐 13B-教务中心全业务流程设计总册§3.11 E05；就业/归档默认提醒非卡审
ITEMS = ("STATUS", "CREDIT", "COURSE_REQUIRED", "COURSE_ELECTIVE", "PRACTICE",
         "INTERNSHIP", "GRADUATION_DESIGN", "DISCIPLINE", "EMPLOYMENT", "ARCHIVE")
_CONCLUSION = {"GRADUATED": "GRADUATED", "COMPLETED": "COMPLETED", "DELAYED": "INCOMPLETE"}
_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}  # 建批次/预审/终审/归档超高危角色白名单（同 grade_service 惯例）


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _require_review_role(user):
    role = (user.get("currentRoleCode") or "").upper()
    if role not in _REVIEW_ROLES and user.get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅教务处可执行该操作")


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


def _get_program(db, s):
    """按学生专业查最新 ACTIVE 绑定的培养方案（供学分/课程/实践三项复用，不重复查绑定）。"""
    from app.models import AaProgram, AaProgramBinding
    if not s.major_id:
        return None
    binding = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == _tid(), AaProgramBinding.major_id == s.major_id,
        AaProgramBinding.status == "ACTIVE", AaProgramBinding.is_deleted.is_(False))).first()
    return db.get(AaProgram, int(binding.program_id)) if binding else None


def _acad_of(db, s):
    """学生 → 学业过程台账（供学分/课程/实践三项复用）。"""
    from app.models import AcademicStudent
    return db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == s.id,
        AcademicStudent.is_deleted.is_(False))).first()


def _check_credit(db, s):
    """学分按培养方案总学分逐项审（获得学分 >= 方案 total_credits）。无方案/无成绩→UNKNOWN。"""
    from app.models import AcademicGrade
    prog = _get_program(db, s)
    acad = _acad_of(db, s)
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


def _check_course_required(db, s):
    """必修全通过：t_acad_grade.nature=REQUIRED 中无 FAILED（§5.4 取数矩阵）。无必修成绩行→UNKNOWN。"""
    from app.models import AcademicGrade
    acad = _acad_of(db, s)
    if not acad:
        return {"item": "COURSE_REQUIRED", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "无学业记录"}
    rows = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.nature == "REQUIRED", AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False))).all()
    if not rows:
        return {"item": "COURSE_REQUIRED", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "无必修课程成绩记录"}
    from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows
    eff_rows = effective_grade_rows(rows)  # 同课程按最高分去重：补考/清考已通过的课程不再计入未通过
    failed = [r.course_name for r in eff_rows if r.pass_status == "FAILED"]
    ok = not failed
    ev = f"必修 {len(eff_rows)} 门全部通过" if ok else f"必修未通过 {len(failed)} 门：{'、'.join(failed[:3])}{'…' if len(failed) > 3 else ''}"
    return {"item": "COURSE_REQUIRED", "result": "PASS" if ok else "FAIL", "owner": "AA_STAFF", "evidence": ev}


def _check_course_elective(db, s):
    """选修学分达标：nature=ELECTIVE 已通过学分 >= 方案 requirement_json「选修」目标。无目标值→UNKNOWN。"""
    from app.models import AcademicGrade
    prog = _get_program(db, s)
    acad = _acad_of(db, s)
    if not acad:
        return {"item": "COURSE_ELECTIVE", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "无学业记录"}
    earned = db.scalar(select(func.coalesce(func.sum(AcademicGrade.credit_value), 0)).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.nature == "ELECTIVE", AcademicGrade.pass_status == "PASSED",
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))) or 0
    target = None
    if prog and prog.requirement_json:
        try:
            req = json.loads(prog.requirement_json)
            target = req.get("选修") or req.get("ELECTIVE")
        except Exception:  # noqa: BLE001
            target = None
    if target is None:
        return {"item": "COURSE_ELECTIVE", "result": "UNKNOWN", "owner": "AA_STAFF",
                "evidence": f"方案未设置选修学分要求（已修选修 {float(earned)} 学分）"}
    ok = float(earned) >= float(target)
    return {"item": "COURSE_ELECTIVE", "result": "PASS" if ok else "FAIL", "owner": "AA_STAFF",
            "evidence": f"选修已得 {float(earned)}/{float(target)} 学分"}


def _check_practice(db, s):
    """实践环节达标：方案课程配置中 module 含「实践」的课程学分 >= requirement_json「实践」目标。
    数据不足（无方案/未标注实践课程）→ UNKNOWN，不判 FAIL（design_source=project_rule §3.5 学分结构）。"""
    from app.models import AaProgramCourse, AcademicGrade
    prog = _get_program(db, s)
    if not prog or not prog.requirement_json:
        return {"item": "PRACTICE", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "无培养方案绑定或未设置模块学分要求"}
    try:
        req = json.loads(prog.requirement_json)
    except Exception:  # noqa: BLE001
        req = {}
    target = req.get("实践") or req.get("PRACTICE")
    if target is None:
        return {"item": "PRACTICE", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "方案未设置实践环节学分要求"}
    acad = _acad_of(db, s)
    if not acad:
        return {"item": "PRACTICE", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "无学业记录"}
    practice_names = {r.course_name for r in db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == prog.id,
        AaProgramCourse.module.ilike("%实践%"), AaProgramCourse.is_deleted.is_(False))).all() if r.course_name}
    if not practice_names:
        return {"item": "PRACTICE", "result": "UNKNOWN", "owner": "AA_STAFF", "evidence": "方案未标注实践环节课程"}
    earned = db.scalar(select(func.coalesce(func.sum(AcademicGrade.credit_value), 0)).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.course_name.in_(practice_names), AcademicGrade.pass_status == "PASSED",
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))) or 0
    ok = float(earned) >= float(target)
    return {"item": "PRACTICE", "result": "PASS" if ok else "FAIL", "owner": "AA_STAFF",
            "evidence": f"实践环节已得 {float(earned)}/{float(target)} 学分"}


def _check_discipline(db, s):
    """无未解除处分(record_status=ACTIVE)。无在校台账→UNKNOWN。refId 供「处分状态联动」跳转学工处分详情。"""
    from app.models import CsDiscipline, CsServiceStudent
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == s.id,
        CsServiceStudent.is_deleted.is_(False))).first()
    active_rows = []
    if cs:
        active_rows = db.scalars(select(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.cs_student_id == cs.id,
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False))).all()
    ok = len(active_rows) == 0
    return {"item": "DISCIPLINE", "result": "PASS" if ok else "FAIL", "owner": "COUNSELOR",
            "evidence": f"未解除处分 {len(active_rows)} 条", "refId": str(active_rows[0].id) if active_rows else None}


def _check_domain_exists(db, item, model, student_field, s, owner, done_check=None):
    """通用：域内有该生记录则视情况 PASS，无则 UNKNOWN（默认非卡审提醒）。refId 供联动页跳转责任模块详情。"""
    try:
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(), getattr(model, student_field) == s.id,
            model.is_deleted.is_(False))).all()
    except Exception:  # noqa: BLE001
        rows = []
    if not rows:
        return {"item": item, "result": "UNKNOWN", "owner": owner, "evidence": "无该域记录", "refId": None}
    ok = True if done_check is None else any(done_check(r) for r in rows)
    return {"item": item, "result": "PASS" if ok else "FAIL", "owner": owner,
            "evidence": f"{len(rows)} 条记录", "refId": str(rows[0].id)}


def _run_items(db, s) -> list:
    from app.models import EmpStudent, GraduationStudent, InternshipRecord
    items = [_check_status(db, s), _check_credit(db, s), _check_course_required(db, s),
             _check_course_elective(db, s), _check_practice(db, s)]
    items.append(_check_domain_exists(db, "INTERNSHIP", InternshipRecord, "student_id", s, "GD_MENTOR"))
    items.append(_check_domain_exists(db, "GRADUATION_DESIGN", GraduationStudent, "student_id", s, "GD_MENTOR"))
    items.append(_check_discipline(db, s))
    # 就业默认提醒非卡审 → 有记录 PASS，无则 UNKNOWN（不判 FAIL）
    items.append(_check_domain_exists(db, "EMPLOYMENT", EmpStudent, "student_id", s, "AA_STAFF"))
    items.append(_check_archive(db, s))
    items.append(_check_fee(db, s))
    return items


def _check_archive(db, s) -> dict:
    """学工归档包（t_affairs_archive_package）：已归档 PASS；退回/待补 FAIL；无包或在途 UNKNOWN。"""
    from app.models import ArchivePackage
    pkg = db.scalars(select(ArchivePackage).where(
        ArchivePackage.tenant_id == _tid(), ArchivePackage.student_id == s.id,
        ArchivePackage.is_deleted.is_(False)).order_by(ArchivePackage.id.desc())).first()
    if not pkg:
        return {"item": "ARCHIVE", "result": "UNKNOWN", "owner": "COUNSELOR",
                "evidence": "学工归档包未生成（不阻断，人工复核）", "refId": None}
    st = (pkg.status or "").upper()
    if st == "ARCHIVED":
        return {"item": "ARCHIVE", "result": "PASS", "owner": "COUNSELOR",
                "evidence": f"学工归档包已归档 status={st}", "refId": str(pkg.id)}
    if st in ("RETURNED", "PENDING_SUPPLEMENT"):
        return {"item": "ARCHIVE", "result": "FAIL", "owner": "COUNSELOR",
                "evidence": f"学工归档包待补齐 status={st}", "refId": str(pkg.id)}
    return {"item": "ARCHIVE", "result": "UNKNOWN", "owner": "COUNSELOR",
            "evidence": f"学工归档包处理中 status={st}", "refId": str(pkg.id)}


def _check_fee(db, s) -> dict:
    """费用结清：优先读财务回填（item 覆盖见 import_fee_clearance）；否则看教材费台账欠费作提醒证据。
    学费/住宿费无财务对接前仍不伪造 PASS/FAIL 卡审结论（默认 UNKNOWN，不阻断）。"""
    from app.models import AaTextbookFeeLedger
    unpaid = db.scalars(select(AaTextbookFeeLedger).where(
        AaTextbookFeeLedger.tenant_id == _tid(), AaTextbookFeeLedger.student_id == s.id,
        AaTextbookFeeLedger.is_deleted.is_(False),
        AaTextbookFeeLedger.status.in_(["UNPAID", "PARTIAL"]))).all()
    if unpaid:
        amt = sum(float(x.amount or 0) - float(x.paid_amount or 0) for x in unpaid)
        return {"item": "FEE", "result": "UNKNOWN", "owner": "FINANCE",
                "evidence": f"教材费台账有未结清 {len(unpaid)} 笔约 {amt:.2f} 元（学费/住宿费仍待财务回填，本项不阻断）",
                "refId": str(unpaid[0].id)}
    return {"item": "FEE", "result": "UNKNOWN", "owner": "FINANCE",
            "evidence": "待财务回填结清状态（教材费台账无欠费记录；学费/住宿费未对接，本项不阻断）",
            "refId": None}


def _overall(items) -> str:
    # 任一 FAIL → 异常；否则通过（UNKNOWN 不阻断，进人工复核）
    return "SYSTEM_ABNORMAL" if any(i["result"] == "FAIL" for i in items) else "SYSTEM_PASSED"


# ═══════════ 批次 / 生成 / 预审 ═══════════

def create_batch(body, user) -> dict:
    _require_review_role(user)
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


def list_batches(user, status=None, page=1, page_size=50):
    """批次列表（供批次选择器/审核批次页）：附各批次应审/通过/异常/已终审/已归档统计。"""
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult
    with session() as db:
        conds = [AaGraduationAuditBatch.tenant_id == _tid(), AaGraduationAuditBatch.is_deleted.is_(False)]
        if status:
            conds.append(AaGraduationAuditBatch.status == status)
        total = db.scalar(select(func.count()).select_from(AaGraduationAuditBatch).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaGraduationAuditBatch).where(*conds)
                          .order_by(AaGraduationAuditBatch.id.desc()).offset(offset).limit(page_size)).all()
        out = []
        for b in rows:
            results = db.scalars(select(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
                AaGraduationAuditResult.is_deleted.is_(False))).all()
            out.append({
                "batchId": str(b.id), "batchName": b.batch_name, "gradeYear": b.grade_year,
                "majorId": str(b.major_id) if b.major_id else None, "status": b.status,
                "total": len(results),
                "passed": sum(1 for r in results if r.overall == "SYSTEM_PASSED"),
                "abnormal": sum(1 for r in results if r.overall == "SYSTEM_ABNORMAL"),
                "concluded": sum(1 for r in results if r.conclusion),
                "archived": sum(1 for r in results if r.status == "ARCHIVED"),
            })
        return out, total


def generate(batch_id, user, student_ids=None) -> dict:
    """圈定应届生生成预审结果行（幂等）。传 student_ids 显式圈定，否则按批次年级/专业。"""
    _require_review_role(user)
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
    """十一项供数三态判定（幂等，结果覆盖非追加；维度清单见 `_run_items`）。"""
    _require_review_role(user)
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
    role = (user.get("currentRoleCode") or "").upper()
    if role not in ({"COLLEGE_ADMIN"} | _REVIEW_ROLES) and user.get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅学院教务员/教务处可执行学院初审")
    with session() as db:
        from app.models import AaGraduationAuditResult
        r = db.get(AaGraduationAuditResult, int(result_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("预审结果不存在")
        _assert_result_in_scope(db, user, r)
        if r.status not in ("SYSTEM_PASSED", "SYSTEM_ABNORMAL", "COLLEGE_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该结果当前状态不可初审")
        if (action or "").upper() == "APPROVE":
            r.status, r.review_note = "ACADEMIC_REVIEW", note
            _audit(db, r.id, "COLLEGE_APPROVE")
        else:
            if not note or len(note.strip()) < 5:
                raise AppException("BAD_REQUEST", "退回原因必填且不少于 5 字")
            r.status, r.review_note = "REJECTED", note.strip()
            _audit(db, r.id, "COLLEGE_REJECT", note.strip())
        db.commit()
        db.refresh(r)
        return _row(r)


def academic_final(result_id, user, conclusion, confirm=False) -> dict:
    """毕业资格终审：写结论(GRADUATED/COMPLETED/DELAYED)，经 change_student_status 写主档，强制二次确认。
    超高危动作，仅教务处/学校管理员可执行（同 grade_service 终审惯例）。"""
    _require_review_role(user)
    conclusion = (conclusion or "").upper()
    if conclusion not in _CONCLUSION:
        raise AppException("BAD_REQUEST", "结论非法（GRADUATED/COMPLETED/DELAYED）")
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


def archive_batch(batch_id, user) -> dict:
    """审核归档：收敛该批次已终审的 GRADUATED/COMPLETED 结果 → ARCHIVED；DELAYED（滚入下批）/REJECTED
    （待重新初审）不在本次归档范围。全部结果均已归档/终止态时批次本身转 ARCHIVED（design_source=project_rule §SM-14）。"""
    _require_review_role(user)
    with session() as db:
        from app.models import AaGraduationAuditBatch, AaGraduationAuditResult
        b = db.get(AaGraduationAuditBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("预审批次不存在")
        if b.status == "ARCHIVED":
            raise AppException("IDEMPOTENCY_CONFLICT", "该批次已归档")
        eligible = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
            AaGraduationAuditResult.status.in_(["GRADUATED", "COMPLETED"]),
            AaGraduationAuditResult.is_deleted.is_(False))).all()
        if not eligible:
            already = db.scalar(select(func.count()).select_from(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
                AaGraduationAuditResult.status == "ARCHIVED", AaGraduationAuditResult.is_deleted.is_(False))) or 0
            if already:
                # 该批次已归档过一轮且无新增可归档结果（部分批次：其余学生仍在延毕/退回等未完结状态）→ 幂等冲突
                raise AppException("IDEMPOTENCY_CONFLICT", "该批次已归档，暂无新增可归档结果")
            raise AppException("BAD_REQUEST", "该批次暂无已终审的毕业/结业结果，无法归档")
        for r in eligible:
            r.status = "ARCHIVED"
        remaining_open = db.scalar(select(func.count()).select_from(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.batch_id == b.id,
            AaGraduationAuditResult.status.notin_(["ARCHIVED", "DELAYED", "REJECTED"]),
            AaGraduationAuditResult.is_deleted.is_(False))) or 0
        batch_closed = remaining_open == 0
        if batch_closed:
            b.status = "ARCHIVED"
        _audit(db, b.id, "ARCHIVE", f"archived={len(eligible)},batchClosed={batch_closed}")
        db.commit()
        return {"batchId": str(batch_id), "archived": len(eligible), "batchStatus": b.status,
                "batchClosed": batch_closed}


# ═══════════ 查询 / 名单 ═══════════

def _row(r) -> dict:
    return {"resultId": str(r.id), "batchId": str(r.batch_id), "studentId": str(r.student_id),
            "overall": r.overall, "conclusion": r.conclusion, "status": r.status,
            "rerunCount": r.rerun_count, "reviewNote": r.review_note or "",
            "items": json.loads(r.item_results_json) if r.item_results_json else []}


def get_result(result_id, user) -> dict:
    with session() as db:
        from app.models import AaGraduationAuditResult
        r = db.get(AaGraduationAuditResult, int(result_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("预审结果不存在")
        _assert_result_in_scope(db, user, r)
        return _row(r)


def list_results(batch_id, user, status=None, overall=None, item=None, item_result=None, page=1, page_size=50):
    """预审结果列表。item/item_result 供单项透视；COLLEGE_ADMIN 按本院 college_ids fail-closed 收敛。"""
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        scope_college_ids = _college_scope_ids(db, user)
        conds = [AaGraduationAuditResult.tenant_id == _tid(),
                 AaGraduationAuditResult.batch_id == int(batch_id),
                 AaGraduationAuditResult.is_deleted.is_(False)]
        if status:
            conds.append(AaGraduationAuditResult.status == status)
        if overall:
            conds.append(AaGraduationAuditResult.overall == overall)
        join = and_(StudentProfile.id == AaGraduationAuditResult.student_id,
                    StudentProfile.tenant_id == AaGraduationAuditResult.tenant_id)
        if scope_college_ids is not None:
            if not scope_college_ids:
                return [], 0
            conds.append(StudentProfile.college_id.in_(scope_college_ids))
        if item:
            rows_all = db.execute(select(AaGraduationAuditResult, StudentProfile)
                                  .outerjoin(StudentProfile, join).where(*conds)
                                  .order_by(AaGraduationAuditResult.id.desc())).all()
            out_all = []
            for r, s in rows_all:
                d = _row(r)
                hit = next((it for it in d["items"] if it.get("item") == item), None)
                if hit is None or (item_result and hit.get("result") != item_result):
                    continue
                d["realName"] = s.real_name if s else ""
                d["studentNo"] = s.student_no if s else ""
                d["itemDetail"] = hit
                out_all.append(d)
            total = len(out_all)
            offset = (max(1, page) - 1) * page_size
            return out_all[offset:offset + page_size], total
        total = db.scalar(select(func.count()).select_from(AaGraduationAuditResult)
                          .outerjoin(StudentProfile, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AaGraduationAuditResult, StudentProfile)
                          .outerjoin(StudentProfile, join).where(*conds)
                          .order_by(AaGraduationAuditResult.id.desc()).offset(offset).limit(page_size)).all()
        out = []
        for r, s in rows:
            d = _row(r)
            d["realName"] = s.real_name if s else ""
            d["studentNo"] = s.student_no if s else ""
            out.append(d)
        return out, total


def _college_scope_ids(db, user) -> set[int] | None:
    """None=全校（教务处/校管）；set=学院收敛（可空=fail-closed）。"""
    from app.core.affairs_security import build_affairs_context
    from app.core.permissions import is_super_admin
    role = (user.get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in _REVIEW_ROLES or user.get("userType") == "PLATFORM_SUPER_ADMIN":
        return None
    if role != "COLLEGE_ADMIN":
        return None
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return None
    return set(ctx.college_ids or set())


def _assert_result_in_scope(db, user, result):
    from app.core.exceptions import no_data_scope
    from app.models import StudentProfile
    scope = _college_scope_ids(db, user)
    if scope is None:
        return
    if not scope:
        raise no_data_scope("未配置学院数据范围")
    s = db.get(StudentProfile, int(result.student_id))
    if not s or s.is_deleted or s.tenant_id != _tid() or int(s.college_id or 0) not in scope:
        raise no_data_scope("该学生不在您的学院数据范围内")


def import_fee_clearance(batch_id, user, rows: list) -> dict:
    """财务回填费用结清：按学号写入结果行 FEE 项（CLEARED→PASS / OWED→FAIL），不改整体卡审策略以外的项。
    仅教务处可执行；写入后刷新 overall（FAIL 仍按既有规则计入 SYSTEM_ABNORMAL）。"""
    _require_review_role(user)
    from app.models import AaGraduationAuditResult, StudentProfile
    if not isinstance(rows, list) or not rows:
        raise AppException("BAD_REQUEST", "rows 不能为空")
    updated, skipped = 0, 0
    with session() as db:
        for row in rows:
            sno = str((row or {}).get("studentNo") or "").strip()
            st = str((row or {}).get("status") or "").upper().strip()
            evidence = str((row or {}).get("evidence") or "").strip() or "财务回填"
            if not sno or st not in ("CLEARED", "OWED"):
                skipped += 1
                continue
            s = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.student_no == sno,
                StudentProfile.is_deleted.is_(False))).first()
            if not s:
                skipped += 1
                continue
            r = db.scalars(select(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == _tid(),
                AaGraduationAuditResult.batch_id == int(batch_id),
                AaGraduationAuditResult.student_id == s.id,
                AaGraduationAuditResult.is_deleted.is_(False))).first()
            if not r:
                skipped += 1
                continue
            items = json.loads(r.item_results_json or "[]")
            fee_result = "PASS" if st == "CLEARED" else "FAIL"
            found = False
            for it in items:
                if it.get("item") == "FEE":
                    it["result"], it["evidence"], it["owner"] = fee_result, evidence[:200], "FINANCE"
                    found = True
                    break
            if not found:
                items.append({"item": "FEE", "result": fee_result, "owner": "FINANCE",
                              "evidence": evidence[:200], "refId": None})
            r.item_results_json = json.dumps(items, ensure_ascii=False)
            r.overall = _overall(items)
            if r.status in ("WAIT_PRECHECK", "SYSTEM_PASSED", "SYSTEM_ABNORMAL"):
                r.status = "SYSTEM_ABNORMAL" if r.overall == "SYSTEM_ABNORMAL" else "SYSTEM_PASSED"
            updated += 1
            _audit(db, r.id, "FEE_CLEARANCE", f"{sno}:{st}")
        db.commit()
    return {"batchId": str(batch_id), "updated": updated, "skipped": skipped}


def mark_fee_clearance_one(batch_id, user, student_no=None, student_id=None,
                           status="CLEARED", evidence="") -> dict:
    """人工勾选过渡：单生费用结清（CLEARED/OWED）。财务对接前由教务处人工确认，不得默认 PASS。

    复用 import_fee_clearance 写入口；evidence 缺省标注「人工勾选过渡」。
    """
    st = str(status or "").upper().strip()
    if st not in ("CLEARED", "OWED"):
        raise AppException("BAD_REQUEST", "status 仅支持 CLEARED / OWED")
    sno = str(student_no or "").strip()
    if not sno and student_id:
        from app.models import StudentProfile
        with session() as db:
            s = db.get(StudentProfile, int(student_id))
            if not s or s.is_deleted or s.tenant_id != _tid():
                raise not_found("学生不存在")
            sno = s.student_no or ""
    if not sno:
        raise AppException("BAD_REQUEST", "studentNo 或 studentId 必填")
    note = (evidence or "").strip() or "人工勾选过渡（财务系统未对接）"
    return import_fee_clearance(batch_id, user, [
        {"studentNo": sno, "status": st, "evidence": note[:200]}
    ])


def _org_names(db, s):
    """学生 → 学院/专业/班级名称（供「毕业学生名单」补全展示；与 academic_affairs_service._resolve_org_names
    同口径，本文件独立维护同款只读小函数，避免跨 service 文件引用私有函数）。"""
    from app.models import College, Major, SchoolClass
    college_name = major_name = class_name = ""
    if s.class_id:
        c = db.get(SchoolClass, int(s.class_id))
        if c and not c.is_deleted and c.tenant_id == _tid():
            class_name = c.class_name
    if s.major_id:
        m = db.get(Major, int(s.major_id))
        if m and not m.is_deleted and m.tenant_id == _tid():
            major_name = m.major_name
    if s.college_id:
        col = db.get(College, int(s.college_id))
        if col and not col.is_deleted and col.tenant_id == _tid():
            college_name = col.college_name
    return college_name, major_name, class_name


def rosters(batch_id, user) -> dict:
    """三名单：毕业/结业/延毕（按终审结论）。COLLEGE_ADMIN 按本院收敛。"""
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        scope = _college_scope_ids(db, user)
        rows = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(),
            AaGraduationAuditResult.batch_id == int(batch_id),
            AaGraduationAuditResult.conclusion.is_not(None),
            AaGraduationAuditResult.is_deleted.is_(False))).all()
        buckets = {"GRADUATED": [], "COMPLETED": [], "DELAYED": []}
        for r in rows:
            s = db.get(StudentProfile, int(r.student_id))
            if scope is not None:
                if not scope or not s or int(s.college_id or 0) not in scope:
                    continue
            if r.conclusion in buckets:
                college_name, major_name, class_name = _org_names(db, s) if s else ("", "", "")
                buckets[r.conclusion].append({
                    "studentId": str(r.student_id), "studentNo": s.student_no if s else "",
                    "realName": s.real_name if s else "", "collegeName": college_name,
                    "majorName": major_name, "className": class_name})
        return {"graduated": buckets["GRADUATED"], "completed": buckets["COMPLETED"],
                "delayed": buckets["DELAYED"],
                "counts": {k: len(v) for k, v in buckets.items()}}


# ══════════ 毕业/结业证书管理（对标商业教务 7-7：编号规则+批量生成+台账+作废）══════════

def _cert_dto(c):
    return {"certificateId": str(c.id), "studentId": str(c.student_id), "studentNo": c.student_no,
            "studentName": c.student_name, "certType": c.cert_type, "certNo": c.cert_no,
            "eRegNo": c.e_reg_no, "issueYear": c.issue_year, "issueDate": c.issue_date,
            "majorName": c.major_name, "voidReason": c.void_reason, "status": c.status,
            "auditBatchId": str(c.audit_batch_id) if c.audit_batch_id else None}


def generate_certificates(batch_id, user, body) -> dict:
    """按审核批次终审结论批量生成证书编号（GRADUATED→毕业证 / COMPLETED→结业证）。

    编号 = prefix(学校代码) + year + 5位流水（租户内按 prefix+year 续号，不回收空号）。
    电子注册号 = 编号前加 eRegPrefix（未传则不生成）。幂等：同学生同类型已有未作废证书跳过。
    """
    _require_review_role(user)
    from app.models import (AaGraduationAuditBatch, AaGraduationAuditResult,
                            AaGraduationCertificate, Major, StudentProfile)
    prefix = (getattr(body, "prefix", None) or "").strip()
    year = (getattr(body, "year", None) or "").strip()
    if not prefix or not year or not year.isdigit():
        raise AppException("VALIDATION_ERROR", "编号前缀(学校代码)与年份必填")
    ereg_prefix = (getattr(body, "eRegPrefix", None) or "").strip()
    issue_date = (getattr(body, "issueDate", None) or "").strip() or None
    with session() as db:
        b = db.get(AaGraduationAuditBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("毕业审核批次不存在")
        results = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(),
            AaGraduationAuditResult.batch_id == b.id,
            AaGraduationAuditResult.conclusion.in_(("GRADUATED", "COMPLETED")),
            AaGraduationAuditResult.is_deleted.is_(False))).all()
        if not results:
            raise AppException("DATA_CONFLICT", "该批次尚无毕业/结业终审结论，无可生成对象",
                               http_status=409)
        # 续号基数：同前缀同年份已发号数（含作废——编号不回收，防重号）
        seq = db.query(AaGraduationCertificate).filter(
            AaGraduationCertificate.tenant_id == _tid(),
            AaGraduationCertificate.cert_no.like(f"{prefix}{year}%")).count()
        created, skipped = 0, 0
        for r in results:
            cert_type = "GRADUATION" if r.conclusion == "GRADUATED" else "COMPLETION"
            dup = db.query(AaGraduationCertificate).filter(
                AaGraduationCertificate.tenant_id == _tid(),
                AaGraduationCertificate.student_id == r.student_id,
                AaGraduationCertificate.cert_type == cert_type,
                AaGraduationCertificate.status != "VOIDED",
                AaGraduationCertificate.is_deleted.is_(False)).first()
            if dup:
                skipped += 1
                continue
            seq += 1
            cert_no = f"{prefix}{year}{seq:05d}"
            p = db.get(StudentProfile, int(r.student_id))
            major = db.get(Major, int(p.major_id)) if (p and p.major_id) else None
            db.add(AaGraduationCertificate(
                tenant_id=_tid(), student_id=r.student_id,
                student_no=(p.student_no if p else None), student_name=(p.real_name if p else None),
                audit_batch_id=b.id, cert_type=cert_type, cert_no=cert_no,
                e_reg_no=(f"{ereg_prefix}{cert_no}" if ereg_prefix else None),
                issue_year=year, issue_date=issue_date,
                major_name=(major.major_name if major else None), status="GENERATED"))
            created += 1
        _audit(db, b.id, "CERT_GENERATE", f"生成{created}张(跳过已有{skipped}) 前缀{prefix}{year}")
        db.commit()
        return {"batchId": str(b.id), "created": created, "skipped": skipped,
                "nextSeq": seq}


def list_certificates(user, status=None, cert_type=None, batch_id=None, keyword=None,
                      page=1, page_size=50):
    # 证书台账收敛到审核角色(ACADEMIC_ADMIN/SCHOOL_ADMIN),与生成/发放/作废同守卫,
    # 防越范围读全校学号/证书编号/电子注册号(修数据范围红线)。
    _require_review_role(user)
    from app.models import AaGraduationCertificate
    with session() as db:
        q = db.query(AaGraduationCertificate).filter(
            AaGraduationCertificate.tenant_id == _tid(),
            AaGraduationCertificate.is_deleted.is_(False))
        if status:
            q = q.filter(AaGraduationCertificate.status == status)
        if cert_type:
            q = q.filter(AaGraduationCertificate.cert_type == cert_type)
        if batch_id:
            q = q.filter(AaGraduationCertificate.audit_batch_id == int(batch_id))
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter((AaGraduationCertificate.student_no.like(kw))
                         | (AaGraduationCertificate.student_name.like(kw))
                         | (AaGraduationCertificate.cert_no.like(kw)))
        rows = q.order_by(AaGraduationCertificate.id.desc()).all()
        return ([_cert_dto(c) for c in rows[(page - 1) * page_size: page * page_size]], len(rows))


def issue_certificate(cert_id, user) -> dict:
    """发放签收：GENERATED→ISSUED。"""
    _require_review_role(user)
    from app.models import AaGraduationCertificate
    with session() as db:
        c = db.get(AaGraduationCertificate, int(cert_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("证书不存在")
        if c.status != "GENERATED":
            raise AppException("DATA_CONFLICT", "仅已生成未发放的证书可登记发放", http_status=409)
        c.status = "ISSUED"
        _audit(db, c.id, "CERT_ISSUE", f"{c.student_no} {c.cert_no}")
        db.commit()
        return _cert_dto(c)


def void_certificate(cert_id, user, reason="") -> dict:
    """作废（补发前置）：原因≥5字留痕；编号不回收。"""
    _require_review_role(user)
    from app.models import AaGraduationCertificate
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        c = db.get(AaGraduationCertificate, int(cert_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("证书不存在")
        if c.status == "VOIDED":
            raise AppException("DATA_CONFLICT", "证书已作废", http_status=409)
        c.status, c.void_reason = "VOIDED", reason.strip()
        _audit(db, c.id, "CERT_VOID", f"{c.cert_no}：{reason.strip()[:100]}")
        db.commit()
        return _cert_dto(c)
