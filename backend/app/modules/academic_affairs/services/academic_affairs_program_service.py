"""13B-P2 培养方案编制骨架（建/编/列 + 课程明细）。审批发布(两审→PUBLISHED→绑年级)留 P3。
Tier1 续工（方案制定/方案版本/课程模块/学分要求/毕业要求/方案审核/方案发布）新增：
课程明细增删改、学分结构(学分要求)读写、毕业要求结构化条目 CRUD、新建版本+版本链、方案绑定查询。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_PROGRAM", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _row(p) -> dict:
    return {"programId": str(p.id), "programName": p.program_name, "majorId": str(p.major_id or ""),
            "gradeYear": p.grade_year or "", "totalCredits": p.total_credits, "version": p.version,
            "status": p.status}


def create_program(body, user) -> dict:
    with session() as db:
        from app.models import AaProgram
        p = AaProgram(tenant_id=_tid(), program_name=body.programName,
                      major_id=(int(body.majorId) if getattr(body, "majorId", None) else None),
                      grade_year=getattr(body, "gradeYear", None),
                      total_credits=getattr(body, "totalCredits", None),
                      requirement_json=json.dumps(getattr(body, "requirement", {}) or {}, ensure_ascii=False),
                      version=1, status="DRAFT")
        db.add(p)
        db.flush()
        _audit(db, p.id, "CREATE", body.programName)
        db.commit()
        db.refresh(p)
        return _row(p)


def update_program(program_id, user, body) -> dict:
    with session() as db:
        from app.models import AaProgram
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "已进入审批/发布的方案不可直接编辑（发布后改动强制新版本，P3）")
        if getattr(body, "programName", None):
            p.program_name = body.programName
        if getattr(body, "totalCredits", None) is not None:
            p.total_credits = body.totalCredits
        if getattr(body, "requirement", None) is not None:
            p.requirement_json = json.dumps(body.requirement, ensure_ascii=False)
        p.version += 0  # 编辑不升版本，发布后改动才强制新版本(P3)
        _audit(db, p.id, "UPDATE")
        db.commit()
        db.refresh(p)
        return _row(p)


def add_course(program_id, user, body) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可增删课程")
        c = AaProgramCourse(tenant_id=_tid(), program_id=p.id,
                            course_id=(int(body.courseId) if getattr(body, "courseId", None) else None),
                            course_name=getattr(body, "courseName", None),
                            open_term_no=getattr(body, "openTermNo", None),
                            module=getattr(body, "module", None),
                            credit_snapshot=getattr(body, "credit", None))
        db.add(c)
        db.flush()
        _audit(db, p.id, "ADD_COURSE", getattr(body, "courseName", "") or "")
        db.commit()
        return {"programCourseId": str(c.id), "programId": str(program_id),
                "courseName": c.course_name or ""}


def get_program(program_id, user) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        courses = db.scalars(select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == p.id,
            AaProgramCourse.is_deleted.is_(False)).order_by(AaProgramCourse.open_term_no)).all()
        d = _row(p)
        d["requirement"] = json.loads(p.requirement_json) if p.requirement_json else {}
        d["courses"] = [{"programCourseId": str(c.id), "courseName": c.course_name or "",
                         "openTermNo": c.open_term_no, "module": c.module or "",
                         "credit": c.credit_snapshot} for c in courses]
        # 编制期学分校验提示（真实：课程学分合计 vs 毕业总学分）
        course_sum = sum(float(c.credit_snapshot or 0) for c in courses)
        d["creditSum"] = course_sum
        d["creditGap"] = (float(p.total_credits) - course_sum) if p.total_credits else None
        return d


def list_programs(user, major_id=None, status=None, page=1, page_size=20, status_in=None):
    """方案列表。status_in：逗号分隔多状态（供「方案审核」「方案发布」工作台按状态集筛选），
    与单值 status 二选一，同时传入以 status_in 优先。"""
    from app.models import AaProgram
    with session() as db:
        conds = [AaProgram.tenant_id == _tid(), AaProgram.is_deleted.is_(False)]
        if major_id:
            conds.append(AaProgram.major_id == int(major_id))
        statuses = [s.strip() for s in status_in.split(",") if s.strip()] if status_in else None
        if statuses:
            conds.append(AaProgram.status.in_(statuses))
        elif status:
            conds.append(AaProgram.status == status)
        rows = db.scalars(select(AaProgram).where(*conds).order_by(AaProgram.id.desc())).all()
        out = [_row(p) for p in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 方案两审发布 + 绑定年级（13B-P3）═══════════

def _credit_sum(db, program_id):
    from app.models import AaProgramCourse
    rows = db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == int(program_id),
        AaProgramCourse.is_deleted.is_(False))).all()
    return sum(float(c.credit_snapshot or 0) for c in rows)


def submit_program(program_id, user) -> dict:
    """提交方案审核（编制→学院审）。发布前校验课程学分合计达毕业总学分。"""
    with session() as db:
        from app.models import AaProgram
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅编制/退回态方案可提交")
        csum = _credit_sum(db, p.id)
        if p.total_credits and csum < float(p.total_credits):
            raise AppException("VALIDATION_ERROR",
                               f"课程学分合计 {csum} 未达毕业总学分 {p.total_credits}，不可提交")
        p.status = "COLLEGE_REVIEW"
        _audit(db, p.id, "SUBMIT", f"creditSum={csum}")
        db.commit()
        db.refresh(p)
        return _row(p)


def review_program(program_id, user, action, reason="") -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import AaProgram
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("COLLEGE_REVIEW", "ACADEMIC_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该方案当前状态不可审核")
        if action == "APPROVE":
            p.status = "ACADEMIC_REVIEW" if p.status == "COLLEGE_REVIEW" else "PUBLISHED"
            _audit(db, p.id, "APPROVE", f"->{p.status}")
        elif action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            p.status = "RETURNED"
            _audit(db, p.id, "RETURNED", reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(p)
        return _row(p)


def bind_grade(program_id, user, grade_year, class_id=None) -> dict:
    """已发布方案绑定年级（同专业+年级旧绑定置 SUPERSEDED，历史年级锁旧版本）。"""
    with session() as db:
        from app.models import AaProgram, AaProgramBinding
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("PUBLISHED", "ENABLED"):
            raise AppException("DATA_CONFLICT", "仅已发布方案可绑定年级")
        # 同专业+年级旧绑定 SUPERSEDED
        for old in db.scalars(select(AaProgramBinding).where(
                AaProgramBinding.tenant_id == _tid(), AaProgramBinding.major_id == p.major_id,
                AaProgramBinding.grade_year == grade_year, AaProgramBinding.status == "ACTIVE",
                AaProgramBinding.is_deleted.is_(False))).all():
            old.status = "SUPERSEDED"
        b = AaProgramBinding(tenant_id=_tid(), program_id=p.id, major_id=p.major_id,
                             grade_year=grade_year,
                             class_id=(int(class_id) if class_id else None),
                             bound_at=datetime.utcnow(), status="ACTIVE")
        db.add(b)
        p.status = "ENABLED"
        _audit(db, p.id, "BIND", f"grade={grade_year}")
        db.commit()
        return {"programId": str(program_id), "gradeYear": grade_year, "status": "ENABLED"}


def list_program_bindings(program_id, user):
    """已发布方案的年级绑定记录（方案发布工作台展示，含历史 SUPERSEDED）。"""
    from app.models import AaProgram, AaProgramBinding
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        rows = db.scalars(select(AaProgramBinding).where(
            AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id == p.id,
            AaProgramBinding.is_deleted.is_(False)).order_by(AaProgramBinding.id.desc())).all()
        return [{"bindingId": str(b.id), "gradeYear": b.grade_year or "", "classId": str(b.class_id or ""),
                "boundAt": (b.bound_at.isoformat() if b.bound_at else ""),
                "status": b.status} for b in rows]


# ═══════════ 课程模块（课程明细增删改，编制态限定）Tier1 ═══════════

def update_course(program_course_id, user, body) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        c = db.get(AaProgramCourse, int(program_course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("方案课程明细不存在")
        p = db.get(AaProgram, c.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改课程")
        if getattr(body, "courseName", None):
            c.course_name = body.courseName
        if getattr(body, "openTermNo", None) is not None:
            c.open_term_no = body.openTermNo
        if getattr(body, "module", None) is not None:
            c.module = body.module
        if getattr(body, "credit", None) is not None:
            c.credit_snapshot = body.credit
        _audit(db, p.id, "UPDATE_COURSE", c.course_name or "")
        db.commit()
        return {"programCourseId": str(c.id), "programId": str(c.program_id), "courseName": c.course_name or "",
                "openTermNo": c.open_term_no, "module": c.module or "", "credit": c.credit_snapshot}


def delete_course(program_course_id, user) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        c = db.get(AaProgramCourse, int(program_course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("方案课程明细不存在")
        p = db.get(AaProgram, c.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可删除课程")
        c.is_deleted = True
        _audit(db, p.id, "DELETE_COURSE", c.course_name or "")
        db.commit()
        return {"programCourseId": str(program_course_id), "deleted": True}


# ═══════════ 学分要求（学分结构：分模块学分目标，复用 requirement_json）Tier1 ═══════════

def get_credit_requirements(program_id, user) -> dict:
    from app.models import AaProgram
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        req = json.loads(p.requirement_json) if p.requirement_json else {}
        items = req.get("creditStructure") or []
        target_sum = sum(float(i.get("creditTarget") or 0) for i in items)
        return {"programId": str(program_id), "totalCredits": p.total_credits,
                "items": items, "targetSum": target_sum,
                "editable": p.status in ("DRAFT", "RETURNED")}


def save_credit_requirements(program_id, user, items) -> dict:
    """保存分模块学分结构（module + creditTarget[+ note]）。仅编制态可写；模块名必填且不重复。"""
    with session() as db:
        from app.models import AaProgram
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改学分结构")
        clean = []
        seen = set()
        for it in (items or []):
            module = (it.get("module") or "").strip()
            if not module:
                raise AppException("VALIDATION_ERROR", "学分结构每行必须填写课程模块名称")
            if module in seen:
                raise AppException("VALIDATION_ERROR", f"课程模块「{module}」重复")
            seen.add(module)
            try:
                target = float(it.get("creditTarget") or 0)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", f"「{module}」学分目标必须为数字")
            if target < 0:
                raise AppException("VALIDATION_ERROR", f"「{module}」学分目标不可为负数")
            clean.append({"module": module, "creditTarget": target, "note": (it.get("note") or "").strip()})
        req = json.loads(p.requirement_json) if p.requirement_json else {}
        req["creditStructure"] = clean
        p.requirement_json = json.dumps(req, ensure_ascii=False)
        target_sum = sum(i["creditTarget"] for i in clean)
        _audit(db, p.id, "UPDATE_CREDIT_STRUCTURE", f"targetSum={target_sum}")
        db.commit()
        return {"programId": str(program_id), "items": clean, "targetSum": target_sum,
                "totalCredits": p.total_credits}


# ═══════════ 毕业要求（结构化条目 CRUD，t_aa_program_graduation_requirement）Tier1 ═══════════

def _grad_row(r) -> dict:
    return {"requirementId": str(r.id), "programId": str(r.program_id), "category": r.category,
            "content": r.content, "sortOrder": r.sort_order, "status": r.status}


def list_graduation_requirements(program_id, user):
    from app.models import AaProgram, AaProgramGraduationRequirement as Req
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        rows = db.scalars(select(Req).where(
            Req.tenant_id == _tid(), Req.program_id == p.id, Req.is_deleted.is_(False),
            Req.status == "ACTIVE").order_by(Req.sort_order, Req.id)).all()
        return [_grad_row(r) for r in rows]


def create_graduation_requirement(program_id, user, body) -> dict:
    from app.models import AaProgram, AaProgramGraduationRequirement as Req
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改毕业要求")
        content = (getattr(body, "content", "") or "").strip()
        if not content:
            raise AppException("VALIDATION_ERROR", "毕业要求内容必填")
        r = Req(tenant_id=_tid(), program_id=p.id,
               category=(getattr(body, "category", None) or "ABILITY"),
               content=content, sort_order=(getattr(body, "sortOrder", None) or 0), status="ACTIVE")
        db.add(r)
        db.flush()
        _audit(db, p.id, "ADD_GRAD_REQUIREMENT", content[:50])
        db.commit()
        return _grad_row(r)


def update_graduation_requirement(requirement_id, user, body) -> dict:
    from app.models import AaProgram, AaProgramGraduationRequirement as Req
    with session() as db:
        r = db.get(Req, int(requirement_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("毕业要求条目不存在")
        p = db.get(AaProgram, r.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改毕业要求")
        if getattr(body, "content", None) is not None:
            content = body.content.strip()
            if not content:
                raise AppException("VALIDATION_ERROR", "毕业要求内容必填")
            r.content = content
        if getattr(body, "category", None):
            r.category = body.category
        if getattr(body, "sortOrder", None) is not None:
            r.sort_order = body.sortOrder
        _audit(db, p.id, "UPDATE_GRAD_REQUIREMENT", r.content[:50])
        db.commit()
        return _grad_row(r)


def delete_graduation_requirement(requirement_id, user) -> dict:
    from app.models import AaProgram, AaProgramGraduationRequirement as Req
    with session() as db:
        r = db.get(Req, int(requirement_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("毕业要求条目不存在")
        p = db.get(AaProgram, r.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改毕业要求")
        r.is_deleted = True
        r.status = "REMOVED"
        _audit(db, p.id, "DELETE_GRAD_REQUIREMENT", r.content[:50])
        db.commit()
        return {"requirementId": str(requirement_id), "deleted": True}


# ═══════════ 方案版本（新建版本 + 版本链）Tier1 ═══════════

def create_new_version(program_id, user, reason=None) -> dict:
    """已发布/启用/冻结方案改动须走新版本：复制基本信息+课程+毕业要求为新 DRAFT（version+1，
    prev_version_id 回链旧版本）；旧版本状态不变，历史绑定年级学生继续沿用旧版本。

    reason（可选，教务中心-教学计划「计划变更」收编入口 R3 新增）：提供时视为一次正式「计划变更」，
    校验≥5字并记专属审计事件 CHANGE_NEW_VERSION（原因写入 detail，供变更留痕追溯）；
    「方案版本」入口沿用原调用方式（不传 reason），行为与既有契约完全一致，不受影响。"""
    if reason is not None:
        reason = reason.strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaProgram, AaProgramCourse, AaProgramGraduationRequirement as Req
        old = db.get(AaProgram, int(program_id))
        if not old or old.is_deleted or old.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if old.status not in ("PUBLISHED", "ENABLED", "FROZEN", "DISABLED"):
            raise AppException("DATA_CONFLICT", "仅已发布/启用/冻结/停用方案可新建版本（编制/退回态直接编辑即可）")
        new_p = AaProgram(tenant_id=_tid(), program_name=old.program_name, major_id=old.major_id,
                          grade_year=old.grade_year, total_credits=old.total_credits,
                          requirement_json=old.requirement_json, version=old.version + 1,
                          prev_version_id=old.id, status="DRAFT")
        db.add(new_p)
        db.flush()
        for c in db.scalars(select(AaProgramCourse).where(
                AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == old.id,
                AaProgramCourse.is_deleted.is_(False))).all():
            db.add(AaProgramCourse(tenant_id=_tid(), program_id=new_p.id, course_id=c.course_id,
                                   course_name=c.course_name, open_term_no=c.open_term_no,
                                   module=c.module, credit_snapshot=c.credit_snapshot))
        for r in db.scalars(select(Req).where(
                Req.tenant_id == _tid(), Req.program_id == old.id, Req.is_deleted.is_(False),
                Req.status == "ACTIVE")).all():
            db.add(Req(tenant_id=_tid(), program_id=new_p.id, category=r.category,
                      content=r.content, sort_order=r.sort_order, status="ACTIVE"))
        if reason:
            _audit(db, new_p.id, "CHANGE_NEW_VERSION",
                  f"reason={reason};fromProgramId={old.id},fromVersion={old.version}")
        else:
            _audit(db, new_p.id, "NEW_VERSION", f"fromProgramId={old.id},fromVersion={old.version}")
        db.commit()
        db.refresh(new_p)
        return _row(new_p)


def list_program_versions(program_id, user):
    """给定任一版本 id，返回同一方案谱系的全部版本（按 prev_version_id 链前后遍历），version 升序。"""
    from app.models import AaProgram
    with session() as db:
        cur = db.get(AaProgram, int(program_id))
        if not cur or cur.is_deleted or cur.tenant_id != _tid():
            raise not_found("培养方案不存在")
        # 回溯到最早版本（根）
        root = cur
        seen_ids = {root.id}
        while root.prev_version_id and root.prev_version_id not in seen_ids:
            parent = db.get(AaProgram, root.prev_version_id)
            if not parent or parent.is_deleted or parent.tenant_id != _tid():
                break
            root = parent
            seen_ids.add(root.id)
        # 从根开始正向收集全部后继版本（线性链，逐级找 prev_version_id = 当前 id 的行）
        chain = [root]
        seen_ids = {root.id}
        cursor = root
        while True:
            nxt = db.scalars(select(AaProgram).where(
                AaProgram.tenant_id == _tid(), AaProgram.prev_version_id == cursor.id,
                AaProgram.is_deleted.is_(False))).first()
            if not nxt or nxt.id in seen_ids:
                break
            chain.append(nxt)
            seen_ids.add(nxt.id)
            cursor = nxt
        return [dict(_row(p), canNewVersion=(p.status in ("PUBLISHED", "ENABLED", "FROZEN", "DISABLED")),
                    isCurrent=(p.id == cur.id)) for p in chain]


# ═══════════ 实践环节（集中性实践教学环节：认识实习/课程设计/顶岗实习/毕业设计等，以周计）Tier1 R3 ═══════════

def _practice_row(s) -> dict:
    return {"segmentId": str(s.id), "programId": str(s.program_id), "segmentName": s.segment_name,
            "segmentType": s.segment_type, "openTermNo": s.open_term_no,
            "weeks": float(s.weeks) if s.weeks is not None else None,
            "credit": float(s.credit) if s.credit is not None else None,
            "orgMode": s.org_mode, "location": s.location or "", "assessmentMode": s.assessment_mode,
            "sortOrder": s.sort_order, "status": s.status}


def list_practice_segments(program_id, user):
    from app.models import AaProgram, AaProgramPracticeSegment as Seg
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        rows = db.scalars(select(Seg).where(
            Seg.tenant_id == _tid(), Seg.program_id == p.id, Seg.is_deleted.is_(False),
            Seg.status == "ACTIVE").order_by(Seg.open_term_no, Seg.sort_order, Seg.id)).all()
        return [_practice_row(s) for s in rows]


def create_practice_segment(program_id, user, body) -> dict:
    from app.models import AaProgram, AaProgramPracticeSegment as Seg
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改实践环节")
        name = (getattr(body, "segmentName", "") or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "实践环节名称必填")
        weeks = getattr(body, "weeks", None)
        if weeks is not None and float(weeks) <= 0:
            raise AppException("VALIDATION_ERROR", "周数必须大于 0")
        s = Seg(tenant_id=_tid(), program_id=p.id, segment_name=name,
               segment_type=(getattr(body, "segmentType", None) or "OTHER"),
               open_term_no=getattr(body, "openTermNo", None), weeks=weeks,
               credit=getattr(body, "credit", None),
               org_mode=(getattr(body, "orgMode", None) or "CENTRALIZED"),
               location=(getattr(body, "location", None) or None),
               assessment_mode=(getattr(body, "assessmentMode", None) or "CHECK"),
               sort_order=(getattr(body, "sortOrder", None) or 0), status="ACTIVE")
        db.add(s)
        db.flush()
        _audit(db, p.id, "ADD_PRACTICE_SEGMENT", name)
        db.commit()
        return _practice_row(s)


def update_practice_segment(segment_id, user, body) -> dict:
    from app.models import AaProgram, AaProgramPracticeSegment as Seg
    with session() as db:
        s = db.get(Seg, int(segment_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("实践环节条目不存在")
        p = db.get(AaProgram, s.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改实践环节")
        if getattr(body, "segmentName", None):
            s.segment_name = body.segmentName.strip()
        if getattr(body, "segmentType", None):
            s.segment_type = body.segmentType
        if getattr(body, "openTermNo", None) is not None:
            s.open_term_no = body.openTermNo
        if getattr(body, "weeks", None) is not None:
            if float(body.weeks) <= 0:
                raise AppException("VALIDATION_ERROR", "周数必须大于 0")
            s.weeks = body.weeks
        if getattr(body, "credit", None) is not None:
            s.credit = body.credit
        if getattr(body, "orgMode", None):
            s.org_mode = body.orgMode
        if getattr(body, "location", None) is not None:
            s.location = body.location
        if getattr(body, "assessmentMode", None):
            s.assessment_mode = body.assessmentMode
        if getattr(body, "sortOrder", None) is not None:
            s.sort_order = body.sortOrder
        _audit(db, p.id, "UPDATE_PRACTICE_SEGMENT", s.segment_name)
        db.commit()
        return _practice_row(s)


def delete_practice_segment(segment_id, user) -> dict:
    from app.models import AaProgram, AaProgramPracticeSegment as Seg
    with session() as db:
        s = db.get(Seg, int(segment_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("实践环节条目不存在")
        p = db.get(AaProgram, s.program_id)
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可修改实践环节")
        s.is_deleted = True
        s.status = "REMOVED"
        _audit(db, p.id, "DELETE_PRACTICE_SEGMENT", s.segment_name)
        db.commit()
        return {"segmentId": str(segment_id), "deleted": True}


# ═══════════ 方案变更（状态生命周期：冻结/停用/恢复）Tier1 R3 ═══════════
# 内容型改动（课程/学分/毕业要求）发布后强制走「方案版本」新建 DRAFT（既有约束，见 submit_program 之上
# update_program 注释）。本组只处理不改变方案内容、只改变方案「是否可继续使用」的生命周期动作——
# FROZEN/DISABLED 两个终态早已写入模型注释与 create_new_version()/list_program_versions() 的前置校验
# （canNewVersion 已预期这两个终态可再新建版本），但此前没有任何端点能把方案实际置于这两个状态，
# 属真实缺口，本轮补齐。bind_grade() 已隐式排斥 FROZEN（仅接受 PUBLISHED/ENABLED），故冻结后自动
# 阻止新绑定，无需额外改动 bind_grade。

_LIFECYCLE_ACTIONS = {"FREEZE", "RESUME", "DISABLE"}
_LIFECYCLE_ACTION_LOG_CODES = ("LIFECYCLE_FREEZE", "LIFECYCLE_RESUME", "LIFECYCLE_DISABLE",
                               "NEW_VERSION", "RETURNED")


def change_program_status(program_id, user, action, reason) -> dict:
    """方案状态生命周期变更：FREEZE 冻结 / RESUME 恢复 / DISABLE 停用。原因必填(≥5字)，写入审计留痕。
    冻结/停用不改动既有年级绑定记录（历史学生仍按已绑定版本执行，只是不再接受新绑定/新审批流转）。"""
    action = (action or "").strip().upper()
    if action not in _LIFECYCLE_ACTIONS:
        raise AppException("VALIDATION_ERROR", "无效的变更操作（仅支持 FREEZE/RESUME/DISABLE）")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaProgram, AaProgramBinding
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        from_status = p.status
        if action == "FREEZE":
            if p.status not in ("PUBLISHED", "ENABLED"):
                raise AppException("DATA_CONFLICT", "仅已发布/已启用方案可冻结")
            p.status = "FROZEN"
        elif action == "RESUME":
            if p.status != "FROZEN":
                raise AppException("DATA_CONFLICT", "仅已冻结方案可恢复")
            has_active_binding = db.scalars(select(AaProgramBinding.id).where(
                AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id == p.id,
                AaProgramBinding.status == "ACTIVE", AaProgramBinding.is_deleted.is_(False))).first()
            p.status = "ENABLED" if has_active_binding else "PUBLISHED"
        else:  # DISABLE
            if p.status not in ("PUBLISHED", "ENABLED", "FROZEN"):
                raise AppException("DATA_CONFLICT", "仅已发布/已启用/已冻结方案可停用")
            p.status = "DISABLED"
        _audit(db, p.id, f"LIFECYCLE_{action}", f"{from_status}->{p.status}；原因：{reason}")
        db.commit()
        db.refresh(p)
        return _row(p)


def list_program_lifecycle_log(program_id, user):
    """方案变更记录：状态生命周期动作审计（冻结/恢复/停用/新建版本/退回），供「方案变更」页留痕查询。"""
    from app.models import AaProgram, AffairsAuditTrail
    with session() as db:
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        rows = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "AA_PROGRAM",
            AffairsAuditTrail.biz_id == p.id,
            AffairsAuditTrail.action.in_(_LIFECYCLE_ACTION_LOG_CODES)
        ).order_by(AffairsAuditTrail.id.desc())).all()
        return [{"action": r.action, "detail": r.detail or "", "operator": r.operator or "",
                "roleName": r.role_name or "", "occurredAt": _iso(r.occurred_at)} for r in rows]


# ═══════════ 方案归档（只读：已停用方案 + 已被取代的历史版本）Tier1 R3 ═══════════
# 不新增状态值/新表：DISABLED 复用「方案变更」新落地的生命周期终态；"历史版本"判定 = 存在更新版本以
# prev_version_id 回链本记录（即另一条 AaProgram.prev_version_id == 本方案.id）。两者取并集，去重展示。

def list_archived_programs(user, page=1, page_size=20):
    from app.models import AaProgram
    with session() as db:
        all_rows = db.scalars(select(AaProgram).where(
            AaProgram.tenant_id == _tid(), AaProgram.is_deleted.is_(False))).all()
        superseded_ids = {r.prev_version_id for r in all_rows if r.prev_version_id}
        successor_by_prev = {r.prev_version_id: r for r in all_rows if r.prev_version_id}
        out = []
        for r in all_rows:
            reasons = []
            if r.status == "DISABLED":
                reasons.append("DISABLED")
            if r.id in superseded_ids:
                reasons.append("SUPERSEDED")
            if not reasons:
                continue
            successor = successor_by_prev.get(r.id)
            d = _row(r)
            d["archiveReasons"] = reasons
            d["supersededByProgramId"] = str(successor.id) if successor else None
            d["supersededByVersion"] = successor.version if successor else None
            out.append(d)
        out.sort(key=lambda x: int(x["programId"]), reverse=True)
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
