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
    failed = [r.course_name for r in rows if r.pass_status == "FAILED"]
    ok = not failed
    ev = f"必修 {len(rows)} 门全部通过" if ok else f"必修未通过 {len(failed)} 门：{'、'.join(failed[:3])}{'…' if len(failed) > 3 else ''}"
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
    items.append({"item": "ARCHIVE", "result": "UNKNOWN", "owner": "COUNSELOR", "evidence": "迎新归档待接入", "refId": None})
    items.append(_check_fee(db, s))
    return items


def _check_fee(db, s) -> dict:
    """费用结清（欠费状态联动）——恒 UNKNOWN（提醒不卡审），如实标注"未对接财务系统"，不伪造结论。

    外部对标（R3 联网核验）：职业院校毕业资格审核确实把"费用结清"列为核心条件（沧州航空职业学院
    《关于做好2023级学生毕业资格审核工作的通知》第六项："学费、住宿费等应缴费用全部结清，无欠费"），
    但该项的核查责任方是**财务处/后勤/图书馆联合核查**，落点在"离校手续→领证"，不在教务的学业审核；
    正方软件更是把它做成与教学管理平台并列的独立《离校管理服务平台》产品。硬/软是分级的：普通欠费
    不进"结业"清单、不改变学业结论（软），仅"长期恶意欠费"才作暂缓毕业（硬）。故本项设为不阻断，
    与项目冻结口径一致（13A-13B-学校参数配置中心设计.md：graduation.conditions.feeCheck 默认 false；
    对标审计与补丁建议：欠费卡审为"供数接口位"，默认"提醒不卡审"）。

    为什么不接现有数据：全仓审计确认**本系统没有可用于毕业欠费判定的数据源**——
      · `t_aa_textbook_fee_ledger`（教材费）是真实欠费数据，但只覆盖教材费、且依赖签收记录生成，
        而毕业审核要的是"学费、住宿费"，用它代表毕业欠费会以偏概全；
      · 奖助域的 `FeeReduction`（学费减免申请）/`StudentLoan`（助学贷款登记）是**资助**语义，不是
        应收欠费——误当欠费用会把受助/贷款学生判成欠费生挡在毕业门外，性质严重，坚决不用；
      · `t_orientation_student.payment_status` 是入学报到缴费快照，对毕业班是数年前的陈旧数据；
      · 后端无任何财务系统对接接口/配置/适配器（全仓 grep 命中全部落在 docs 与小程序 mock）。
    缺的是前置条件（学校财务系统对接），不是代码能力，故照 ARCHIVE 同款先例做诚实占位。
    后续路径：P2 财务处按批次 Excel 回填（走既有导入 dry-run 管线）→ P3 财务适配器只读拉取，
    准入=学校书面确认财务系统接口能力与对账口径。
    """
    return {"item": "FEE", "result": "UNKNOWN", "owner": "FINANCE",
            "evidence": "待接入学校财务系统（未对接，本项不阻断毕业资格）", "refId": None}


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
    """十项供数三态判定（幂等，结果覆盖非追加）。"""
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
        return _row(r)


def list_results(batch_id, user, status=None, overall=None, item=None, item_result=None, page=1, page_size=50):
    """预审结果列表。item/item_result 供「学分/课程/实践达成审核」与「毕设/实习/处分状态联动」等
    单项透视 tab 按项过滤（沿用既有 item_results_json 不建 item 表的设计，Python 侧收敛）。"""
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        conds = [AaGraduationAuditResult.tenant_id == _tid(),
                 AaGraduationAuditResult.batch_id == int(batch_id),
                 AaGraduationAuditResult.is_deleted.is_(False)]
        if status:
            conds.append(AaGraduationAuditResult.status == status)
        if overall:
            conds.append(AaGraduationAuditResult.overall == overall)
        join = and_(StudentProfile.id == AaGraduationAuditResult.student_id,
                    StudentProfile.tenant_id == AaGraduationAuditResult.tenant_id)
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
    """三名单：毕业/结业/延毕（按终审结论）。供「毕业学生名单」页展示学号/姓名/学院/专业/班级
    （只读展示字段，非新增数据源；院系信息缺失时对应字段留空，不阻断名单展示）。"""
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
                college_name, major_name, class_name = _org_names(db, s) if s else ("", "", "")
                buckets[r.conclusion].append({
                    "studentId": str(r.student_id), "studentNo": s.student_no if s else "",
                    "realName": s.real_name if s else "", "collegeName": college_name,
                    "majorName": major_name, "className": class_name})
        return {"graduated": buckets["GRADUATED"], "completed": buckets["COMPLETED"],
                "delayed": buckets["DELAYED"],
                "counts": {k: len(v) for k, v in buckets.items()}}
