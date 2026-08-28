from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
changed: set[str] = set()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")
    changed.add(path)


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def sub_once(path: str, pattern: str, repl: str, *, flags: int = 0) -> None:
    text = read(path)
    new, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{path}: regex expected one occurrence, got {count}: {pattern[:120]!r}")
    write(path, new)


# ---------------------------------------------------------------------------
# 1/2/enterprise concurrency: enterprise review integrity + optimistic locks.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_enterprise_service.py"
replace_once(P,
    '        "updatedAt": _iso(c.updated_at),\n    }',
    '        "updatedAt": _iso(c.updated_at), "version": int(c.version or 0),\n    }')
replace_once(P,
    '        "remark": t.remark or "", "status": t.status,\n    }',
    '        "remark": t.remark or "", "status": t.status, "version": int(t.version or 0),\n    }')

sub_once(P,
    r'def update_enterprise\(company_id, body\) -> dict:\n.*?(?=\n\ndef review_enterprise)',
'''def update_enterprise(company_id, body) -> dict:
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(expected) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业信息已被其他用户修改，请刷新后重试")
        if c.coop_status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档企业不可编辑")

        old_name = c.name or ""
        old_cc = c.credit_code or ""
        new_name = (getattr(body, "name", None) if "name" in body.model_fields_set else None)
        new_cc = (getattr(body, "creditCode", None) if "creditCode" in body.model_fields_set else None)
        if new_name is not None:
            normalized_name = (new_name or "").strip()
            err = _validate_company_name(normalized_name)
            if err:
                raise AppException("VALIDATION_ERROR", err)
            body.name = normalized_name
        if new_cc is not None:
            normalized_cc = (new_cc or "").strip()
            err = _validate_credit_code(normalized_cc)
            if err:
                raise AppException("VALIDATION_ERROR", err)
            body.creditCode = normalized_cc or None
            if normalized_cc and normalized_cc != old_cc:
                dup = db.scalars(select(EmpCompany).where(
                    EmpCompany.tenant_id == _tid(), EmpCompany.credit_code == normalized_cc,
                    EmpCompany.id != c.id, EmpCompany.is_deleted.is_(False))).first()
                if dup:
                    raise AppException("DATA_CONFLICT", f"统一社会信用代码已存在：{normalized_cc}")

        _apply(c, body)
        identity_changed = (c.name or "") != old_name or (c.credit_code or "") != old_cc
        if identity_changed:
            c.qualification_status = "UNREVIEWED"
            c.review_by = None
            c.review_at = None
            c.review_comment = None
            if c.coop_status != "BLACKLIST":
                c.coop_status = "PENDING"
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "UPDATE", {
            "name": c.name, "identityInvalidated": identity_changed,
            "previousName": old_name if identity_changed else "",
            "previousCreditCode": old_cc if identity_changed else "",
        })
        db.commit()
        db.refresh(c)
        return _row(c)
''', flags=re.S)

sub_once(P,
    r'def review_enterprise\(company_id, action: str, comment: str = ""\) -> dict:\n.*?(?=\n\ndef set_cooperation)',
'''def review_enterprise(company_id, action: str, comment: str = "", expected_version=None) -> dict:
    """资质审核：仅 PENDING 可审。APPROVE→ACTIVE+资质通过；REJECT→REJECTED+资质不通过。"""
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "非法审核动作")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 个字")
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        if expected_version is not None and int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业资质状态已变化，请刷新后重试")
        if c.coop_status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅「待审核」企业可审核，当前状态：{COOP_LABEL.get(c.coop_status)}")
        c.coop_status = "ACTIVE" if action == "APPROVE" else "REJECTED"
        c.qualification_status = "PASSED" if action == "APPROVE" else "FAILED"
        c.review_by = _op_name()
        c.review_at = datetime.utcnow()
        c.review_comment = comment or ""
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, f"REVIEW_{action}", {"comment": comment})
        db.commit()
        db.refresh(c)
        return _row(c)
''', flags=re.S)

sub_once(P,
    r'def set_cooperation\(company_id, action: str, reason: str = ""\) -> dict:\n.*?(?=\n\ndef set_blacklist)',
'''def set_cooperation(company_id, action: str, reason: str = "", expected_version=None) -> dict:
    """合作启停：SUSPEND(ACTIVE→SUSPENDED) / RESUME(SUSPENDED→ACTIVE) / ARCHIVE(→ARCHIVED)。"""
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        if expected_version is not None and int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业合作状态已变化，请刷新后重试")
        if action == "SUSPEND":
            if c.coop_status != "ACTIVE":
                raise AppException("DATA_CONFLICT", "仅「合作中」企业可暂停")
            c.coop_status = "SUSPENDED"
        elif action == "RESUME":
            if c.coop_status != "SUSPENDED":
                raise AppException("DATA_CONFLICT", "仅「已暂停」企业可恢复合作")
            if c.qualification_status != "PASSED":
                raise AppException("DATA_CONFLICT", "企业资质未通过，不能恢复合作")
            c.coop_status = "ACTIVE"
        elif action == "ARCHIVE":
            if c.coop_status in ("ARCHIVED", "BLACKLIST"):
                raise AppException("DATA_CONFLICT", "黑名单/已归档企业不可再归档")
            c.coop_status = "ARCHIVED"
            c.archived_at = datetime.utcnow()
            c.archived_by = _op_name()
        else:
            raise AppException("VALIDATION_ERROR", "非法合作动作")
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, f"COOP_{action}", {"reason": reason})
        db.commit()
        db.refresh(c)
        return _row(c)
''', flags=re.S)

sub_once(P,
    r'def set_blacklist\(company_id, on: bool, reason: str = ""\) -> dict:\n.*?(?=\n\n# ═══════════ 联系人)',
'''def set_blacklist(company_id, on: bool, reason: str = "", expected_version=None) -> dict:
    """拉黑 / 移出黑名单。移出时恢复拉黑前状态；缺历史证据则 fail-closed 回待审核。"""
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        if expected_version is not None and int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业黑名单状态已变化，请刷新后重试")
        if on:
            if not (reason or "").strip():
                raise AppException("VALIDATION_ERROR", "拉黑必须填写原因")
            if c.coop_status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档企业不可拉黑")
            previous = c.coop_status
            c.blacklist = True
            c.blacklist_reason = reason.strip()
            c.coop_status = "BLACKLIST"
            detail = {"reason": reason, "previousCoopStatus": previous}
        else:
            if not c.blacklist:
                raise AppException("DATA_CONFLICT", "该企业不在黑名单中")
            trail = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "ENTERPRISE",
                InternshipAuditTrail.target_id == c.id,
                InternshipAuditTrail.action == "BLACKLIST_ON",
            ).order_by(InternshipAuditTrail.id.desc())).first()
            previous = str(((trail.detail_json or {}).get("previousCoopStatus") if trail else "") or "").upper()
            if previous not in {"PENDING", "ACTIVE", "REJECTED", "SUSPENDED"}:
                previous = "PENDING"
            if previous == "ACTIVE" and c.qualification_status != "PASSED":
                previous = "PENDING"
            c.blacklist = False
            c.blacklist_reason = None
            c.coop_status = previous
            detail = {"reason": reason, "restoredCoopStatus": previous}
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "BLACKLIST_ON" if on else "BLACKLIST_OFF", detail)
        db.commit()
        db.refresh(c)
        return _row(c)
''', flags=re.S)

sub_once(P,
    r'def update_contact\(company_id, contact_id, body\) -> dict:\n.*?(?=\n\ndef delete_contact)',
'''def update_contact(company_id, contact_id, body) -> dict:
    with session() as db:
        c = _get(db, company_id)
        t = db.scalar(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.id == _as_id(contact_id),
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == c.id,
            InternshipEnterpriseContact.is_deleted.is_(False)).with_for_update())
        if not t:
            raise not_found("联系人不存在")
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(expected) != int(t.version or 0):
            raise AppException("DATA_CONFLICT", "联系人已被其他用户修改，请刷新后重试")
        if "name" in body.model_fields_set:
            name = (getattr(body, "name", None) or "").strip()
            if not name:
                raise AppException("VALIDATION_ERROR", "姓名必填")
            body.name = name
        if "contactType" in body.model_fields_set:
            ctype = getattr(body, "contactType", None)
            if ctype not in CONTACT_TYPE_LABEL:
                raise AppException("VALIDATION_ERROR", "非法联系人类型")
        for src, col in [("name", "name"), ("title", "title"), ("email", "email"),
                         ("remark", "remark"), ("contactType", "contact_type")]:
            if src in body.model_fields_set:
                setattr(t, col, getattr(body, src))
        if "phone" in body.model_fields_set:
            t.phone_encrypted = encrypt_field(getattr(body, "phone", None))
        if "isPrimary" in body.model_fields_set:
            is_primary = getattr(body, "isPrimary", None)
            if is_primary:
                _unset_primary(db, c.id, t.contact_type)
                t.is_primary = True
            else:
                t.is_primary = False
        t.version = int(t.version or 0) + 1
        _trail(db, c.id, "CONTACT_UPDATE", {"contactId": str(t.id)})
        db.commit()
        db.refresh(t)
        return _contact_row(t)
''', flags=re.S)

# Schemas: expose/accept expectedVersion without changing unrelated endpoints.
S = "backend/app/modules/internship/schemas/internship.py"
replace_once(S,
'''class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None''',
'''class EnterpriseUpdate(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="企业乐观锁版本")
    name: Optional[str] = None''')
replace_once(S,
'''class EnterpriseReview(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    comment: Optional[str] = ""''',
'''class EnterpriseReview(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT")
    comment: Optional[str] = ""
    expectedVersion: Optional[int] = Field(None, ge=0, description="企业乐观锁版本")''')
replace_once(S,
'''class CoopActionRequest(BaseModel):
    action: str = Field(..., description="SUSPEND / RESUME / ARCHIVE")
    reason: Optional[str] = ""''',
'''class CoopActionRequest(BaseModel):
    action: str = Field(..., description="SUSPEND / RESUME / ARCHIVE")
    reason: Optional[str] = ""
    expectedVersion: Optional[int] = Field(None, ge=0, description="企业乐观锁版本")''')
replace_once(S,
'''class BlacklistRequest(BaseModel):
    on: bool = Field(..., description="true 拉黑 / false 移出黑名单")
    reason: Optional[str] = ""''',
'''class BlacklistRequest(BaseModel):
    on: bool = Field(..., description="true 拉黑 / false 移出黑名单")
    reason: Optional[str] = ""
    expectedVersion: Optional[int] = Field(None, ge=0, description="企业乐观锁版本")''')
replace_once(S,
'''class ContactUpdate(BaseModel):
    contactType: Optional[str] = None''',
'''class ContactUpdate(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="联系人乐观锁版本")
    contactType: Optional[str] = None''')

R = "backend/app/modules/internship/routers/internship.py"
replace_once(R, 'result = ent.review_enterprise(company_id, body.action, body.comment or "")',
             'result = ent.review_enterprise(company_id, body.action, body.comment or "", body.expectedVersion)')
replace_once(R, 'result = ent.set_cooperation(company_id, body.action, body.reason or "")',
             'result = ent.set_cooperation(company_id, body.action, body.reason or "", body.expectedVersion)')
replace_once(R, 'result = ent.set_blacklist(company_id, body.on, body.reason or "")',
             'result = ent.set_blacklist(company_id, body.on, body.reason or "", body.expectedVersion)')

API = "frontend/src/modules/internship/api/internship.api.js"
replace_once(API,
'''  reviewEnterprise(id, { action, comment }) {
    return call(() => request(`/internship/enterprises/${id}/review`, { method: 'POST', body: { action, comment } }))
  },''',
'''  reviewEnterprise(id, { action, comment, expectedVersion }) {
    return call(() => request(`/internship/enterprises/${id}/review`, { method: 'POST', body: { action, comment, expectedVersion } }))
  },''')
replace_once(API,
'''  setEnterpriseCooperation(id, { action, reason }) {
    return call(() => request(`/internship/enterprises/${id}/cooperation`, { method: 'POST', body: { action, reason } }))
  },''',
'''  setEnterpriseCooperation(id, { action, reason, expectedVersion }) {
    return call(() => request(`/internship/enterprises/${id}/cooperation`, { method: 'POST', body: { action, reason, expectedVersion } }))
  },''')
replace_once(API,
'''  setEnterpriseBlacklist(id, { on, reason }) {
    return call(() => request(`/internship/enterprises/${id}/blacklist`, { method: 'POST', body: { on, reason } }))
  },''',
'''  setEnterpriseBlacklist(id, { on, reason, expectedVersion }) {
    return call(() => request(`/internship/enterprises/${id}/blacklist`, { method: 'POST', body: { on, reason, expectedVersion } }))
  },''')

V = "frontend/src/modules/internship/views/InternshipEnterpriseDetailView.vue"
replace_once(V,
'await internshipApi.updateEnterpriseContact(this.detail.id, this.editingContact.id, this.cform)',
'await internshipApi.updateEnterpriseContact(this.detail.id, this.editingContact.id, { ...this.cform, expectedVersion: this.editingContact.version })')
replace_once(V,
"await internshipApi.reviewEnterprise(this.detail.id, { action: 'APPROVE', comment: reason || '' })",
"await internshipApi.reviewEnterprise(this.detail.id, { action: 'APPROVE', comment: reason || '', expectedVersion: this.detail.version })")
replace_once(V,
"await internshipApi.reviewEnterprise(this.detail.id, { action: 'REJECT', comment: reason || '' })",
"await internshipApi.reviewEnterprise(this.detail.id, { action: 'REJECT', comment: reason || '', expectedVersion: this.detail.version })")
replace_once(V,
"await internshipApi.setEnterpriseCooperation(this.detail.id, { action: action.slice(5), reason: reason || '' })",
"await internshipApi.setEnterpriseCooperation(this.detail.id, { action: action.slice(5), reason: reason || '', expectedVersion: this.detail.version })")
replace_once(V,
"await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: true, reason: reason || '' })",
"await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: true, reason: reason || '', expectedVersion: this.detail.version })")
replace_once(V,
"await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: false })",
"await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: false, expectedVersion: this.detail.version })")
replace_once(V, "移出黑名单？恢复为合作中。", "移出黑名单？系统将恢复拉黑前状态，缺少历史状态时回到待审核。")

# ---------------------------------------------------------------------------
# 3/4/F: position edits must preserve batch integrity and re-run compliance.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_position_service.py"
old = '''        hc = getattr(body, "headcount", None)
        if hc is not None:
            if hc < p.allocated_count:
                raise AppException("VALIDATION_ERROR", f"容量不能小于已分配人数（{p.allocated_count}）")
            p.headcount = hc
        bid = getattr(body, "batchId", None)
        if bid is not None:
            p.batch_id = _opt_int(bid, "批次")
        mc = getattr(body, "mentorContactId", None)
        if mc is not None:
            p.mentor_contact_id, p.mentor_name = _resolve_mentor(db, p.company_id, mc) if mc else (None, None)
        after = {name: getattr(p, name) for name in before}
        changed = [name for name in before if before[name] != after[name]]
        rec_ids = db.scalars(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.position_id == p.id,
            InternshipRecord.is_deleted.is_(False))).all() if changed else []
        if changed and rec_ids:
            from app.modules.internship.services.internship_consent_service import supersede_for_major_change
            for rec_id in rec_ids:
                supersede_for_major_change(db, rec_id)
                for filing in db.scalars(select(InternshipSpecialFiling).where(
                    InternshipSpecialFiling.tenant_id == _tid(),
                    InternshipSpecialFiling.internship_id == rec_id,
                    InternshipSpecialFiling.status == "APPROVED",
                    InternshipSpecialFiling.is_deleted.is_(False)).with_for_update()).all():
                    filing.status = "SUPERSEDED"
                    filing.version = int(filing.version or 0) + 1
            p.rights_status = "UNKNOWN"
            p.rights_checked_at = None
            p.rights_rule_version = None
'''
new = '''        hc = getattr(body, "headcount", None)
        headcount_changed = hc is not None and int(hc) != int(p.headcount or 0)
        if hc is not None:
            if hc < p.allocated_count:
                raise AppException("VALIDATION_ERROR", f"容量不能小于已分配人数（{p.allocated_count}）")
            p.headcount = hc
        bid = getattr(body, "batchId", None)
        if bid is not None:
            new_batch_id = _opt_int(bid, "批次")
            if new_batch_id != p.batch_id and (
                    int(p.allocated_count or 0) > 0 or p.publish_at is not None
                    or p.status not in ("DRAFT", "PENDING")):
                raise AppException("DATA_CONFLICT", "岗位已发布或存在学生分配记录，不可变更所属实习批次")
            p.batch_id = new_batch_id
        mc = getattr(body, "mentorContactId", None)
        if mc is not None:
            p.mentor_contact_id, p.mentor_name = _resolve_mentor(db, p.company_id, mc) if mc else (None, None)
        after = {name: getattr(p, name) for name in before}
        changed = [name for name in before if before[name] != after[name]]
        rec_ids = db.scalars(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.position_id == p.id,
            InternshipRecord.is_deleted.is_(False))).all() if changed else []
        if changed:
            if rec_ids:
                from app.modules.internship.services.internship_consent_service import supersede_for_major_change
                for rec_id in rec_ids:
                    supersede_for_major_change(db, rec_id)
                    for filing in db.scalars(select(InternshipSpecialFiling).where(
                        InternshipSpecialFiling.tenant_id == _tid(),
                        InternshipSpecialFiling.internship_id == rec_id,
                        InternshipSpecialFiling.status == "APPROVED",
                        InternshipSpecialFiling.is_deleted.is_(False)).with_for_update()).all():
                        filing.status = "SUPERSEDED"
                        filing.version = int(filing.version or 0) + 1
            company = _company(db, p.company_id)
            batch = db.get(InternshipBatch, p.batch_id) if p.batch_id else None
            from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
            rights = evaluate_position_publishability(p, company, batch, operation="PUBLISH", db=db)
            p.rights_status = "COMPLIANT" if rights["passed"] else "NON_COMPLIANT"
            p.rights_checked_at = datetime.utcnow()
            p.rights_rule_version = rights["ruleVersion"]
            if p.status in ("PUBLISHED", "FULL") and not rights["passed"]:
                p.status = "OFFLINE"
            elif p.status == "FULL" and rights["passed"] and int(p.headcount or 0) > int(p.allocated_count or 0):
                p.status = "PUBLISHED"
        elif headcount_changed and p.status == "FULL" and int(p.headcount or 0) > int(p.allocated_count or 0):
            company = _company(db, p.company_id)
            batch = db.get(InternshipBatch, p.batch_id) if p.batch_id else None
            from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
            rights = evaluate_position_publishability(p, company, batch, operation="PUBLISH", db=db)
            p.rights_status = "COMPLIANT" if rights["passed"] else "NON_COMPLIANT"
            p.rights_checked_at = datetime.utcnow()
            p.rights_rule_version = rights["ruleVersion"]
            p.status = "PUBLISHED" if rights["passed"] else "OFFLINE"
'''
replace_once(P, old, new)

# ---------------------------------------------------------------------------
# 5/6: remove name-based authorization/notification fallbacks.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_communication_service.py"
replace_once(P,
'''    if c.internship_id:
        rec = db.get(InternshipRecord, c.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if rec and stu and _rec_in_scope(scope, db, rec, stu):
            return True
    return (c.advisor_name or "") in (scope.get("advisorNames") or set())''',
'''    if not c.internship_id:
        return False
    rec = db.get(InternshipRecord, c.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return bool(rec and stu and _rec_in_scope(scope, db, rec, stu))''')
replace_once(P,
'''    names = scope.get("advisorNames") or set()
    with session() as db:''',
'''    with session() as db:''')
replace_once(P,
'''                if not ok and (c.advisor_name or "") not in names:
                    continue
            items.append(_row(c))''',
'''                if not ok:
                    continue
            items.append(_row(c))''')

P = "backend/app/modules/internship/services/internship_risk_service.py"
sub_once(P,
    r'\n            if not advisor and \(rec\.advisor_name or ""\)\.strip\(\):\n                advisor = db\.scalars\(select\(User\)\.where\(\n                    User\.tenant_id == _tid\(\), User\.real_name == rec\.advisor_name\.strip\(\),\n                    User\.user_type == "TEACHER", User\.is_deleted\.is_\(False\),\n                    User\.status == "ACTIVE"\)\)\.first\(\)',
    '')

# ---------------------------------------------------------------------------
# 7: evidence package audit must be typed, not raw-id joined.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_evidence_package_service.py"
old = '''    audits = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_id == rec.id).order_by(InternshipAuditTrail.id)).all()'''
new = '''    audits = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "INTERN_STUDENT",
        InternshipAuditTrail.target_id == rec.id).order_by(InternshipAuditTrail.id)).all()'''
text = read(P)
if text.count(old) != 2:
    raise RuntimeError(f"{P}: expected two raw audit joins, got {text.count(old)}")
write(P, text.replace(old, new))

# ---------------------------------------------------------------------------
# 8 + emergency P2: incident must bind to a scoped internship; plan refs/files/dates validated.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_incident_service.py"
replace_once(P,
'''    with session() as db:
        if b.get("internshipId"):
            from app.modules.internship.services.internship_scope import assert_internship_record_scope
            rec = assert_internship_record_scope(db, b["internshipId"], user, "事故上报")
            b["studentId"], b["batchId"], b["companyId"] = (
                rec.student_id, rec.batch_id, rec.enterprise_id)
        existing = _find_by_idempotency_key(db, key)''',
'''    if not b.get("internshipId"):
        raise AppException("VALIDATION_ERROR", "学生事故上报必须关联 internshipId")
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, b["internshipId"], user, "事故上报")
        b["studentId"], b["batchId"], b["companyId"] = (
            rec.student_id, rec.batch_id, rec.enterprise_id)
        existing = _find_by_idempotency_key(db, key)''')

# create_plan: validate canonical refs, dates and evidence before persisting.
replace_once(P,
'''    with session() as db:
        x = InternshipEmergencyPlan(
            tenant_id=_tid(),
            company_id=_as_id(b["companyId"]) if b.get("companyId") else None,
            batch_id=_as_id(b["batchId"]) if b.get("batchId") else None,
            plan_name=name,''',
'''    with session() as db:
        from app.models import EmpCompany, InternshipBatch
        from app.services import file_service
        company_id = _as_id(b["companyId"]) if b.get("companyId") else None
        batch_id = _as_id(b["batchId"]) if b.get("batchId") else None
        if company_id:
            company = db.get(EmpCompany, company_id)
            if not company or company.is_deleted or company.tenant_id != _tid():
                raise not_found("应急预案关联企业不存在或不在当前租户")
        if batch_id:
            batch = db.get(InternshipBatch, batch_id)
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                raise not_found("应急预案关联批次不存在或不在当前租户")
        def _plan_dt(value, label):
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "")[:19])
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", f"{label}格式不正确") from None
        valid_from = _plan_dt(b.get("validFrom"), "生效日期")
        valid_until = _plan_dt(b.get("validUntil"), "失效日期")
        if valid_from and valid_until and valid_from > valid_until:
            raise AppException("VALIDATION_ERROR", "应急预案生效日期不能晚于失效日期")
        file_ids = [str(v) for v in (b.get("fileIds") or []) if v]
        for fid in file_ids:
            if not file_service.get_file_meta(fid, user=user):
                raise AppException("VALIDATION_ERROR", "应急预案附件不存在或无权访问")
        x = InternshipEmergencyPlan(
            tenant_id=_tid(),
            company_id=company_id,
            batch_id=batch_id,
            plan_name=name,''')
replace_once(P,
'''            valid_from=b.get("validFrom"), valid_until=b.get("validUntil"),
            file_ids=b.get("fileIds") or [], status="DRAFT")
        db.add(x)
        db.flush()''',
'''            valid_from=valid_from, valid_until=valid_until,
            file_ids=file_ids, status="DRAFT")
        db.add(x)
        db.flush()
        for fid in file_ids:
            file_service.bind_file_biz(fid, "INTERNSHIP", str(x.id), user=user, db=db)''')
replace_once(P,
'''        if expected_version is not None and int(expected_version) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "应急预案版本已变化，请刷新后重试")''',
'''        if expected_version is None or int(expected_version) != int(x.version or 0):
            raise AppException("DATA_CONFLICT", "应急预案版本已变化，请刷新后重试")''')

# ---------------------------------------------------------------------------
# 9/10/12: special-filing trigger coverage, school region, stable advisor id.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_compliance_rules.py"
replace_once(P,
'''        "crossProvinceRequired": True, "highRiskPositionRequired": True, "nightShiftRequired": True,
    },''',
'''        "crossProvinceRequired": True, "highRiskPositionRequired": True, "nightShiftRequired": True,
        "schoolRegion": None,
    },''')

P = "backend/app/modules/internship/services/internship_compliance_service.py"
sub_once(P,
    r'        # 7 特殊备案\n.*?(?=        # 8 岗位权益)',
'''        # 7 特殊备案
        cfg = rules["specialFiling"]
        from app.modules.internship.services.internship_special_filing_service import evaluate_triggers
        pos = db.get(InternshipPosition, rec.position_id) if rec.position_id else None
        school_region = str(cfg.get("schoolRegion") or "").strip()
        trigger_tuples = evaluate_triggers(pos, stu, school_region) if cfg.get("required") else []
        enabled = {
            "CROSS_PROVINCE": bool(cfg.get("crossProvinceRequired", True)),
            "HIGH_RISK": bool(cfg.get("highRiskPositionRequired", True)),
            "NIGHT_SHIFT": bool(cfg.get("nightShiftRequired", True)),
        }
        trigger_tuples = [t for t in trigger_tuples if enabled.get(t[0], True)]
        triggers = [t[0] for t in trigger_tuples]
        labels_by_type = {t[0]: t[1] for t in trigger_tuples}
        location = ((getattr(pos, "work_location", None) or getattr(pos, "work_address", None) or "").strip()
                    if pos else "")
        region_unknown = bool(cfg.get("required") and cfg.get("crossProvinceRequired", True)
                              and location and not school_region)
        filings = db.scalars(select(InternshipSpecialFiling).where(
            InternshipSpecialFiling.tenant_id == _tid(),
            InternshipSpecialFiling.internship_id == rec.id,
            InternshipSpecialFiling.is_deleted.is_(False),
        )).all()
        if not cfg.get("required"):
            items.append(_item("specialFiling", cfg, "NOT_APPLICABLE", "规则未要求"))
        elif region_unknown:
            items.append(_item("specialFiling", cfg, "MISSING",
                               "学校所在地未配置，无法判定跨省备案要求"))
        elif not triggers:
            na = next((x for x in filings if x.status in ("NOT_REQUIRED", "NOT_APPLICABLE")), None)
            items.append(_item("specialFiling", cfg, "NOT_APPLICABLE", "无需特殊备案",
                               getattr(na, "id", None)))
        else:
            approved = {
                str(x.filing_type).upper(): x for x in filings
                if x.status == "APPROVED" and (not x.valid_until or x.valid_until >= datetime.utcnow())
            }
            missing_types = [code for code in triggers if code not in approved]
            pending_types = {
                str(x.filing_type).upper() for x in filings
                if str(x.status).startswith("PENDING")
            }
            if not missing_types:
                first = approved[triggers[0]]
                status, reason, evid = "VALID", "", first.id
            elif any(code in pending_types for code in missing_types):
                status, reason, evid = "PENDING", "特殊备案审批中：" + ",".join(missing_types), None
            else:
                labels = [labels_by_type.get(code, code) for code in missing_types]
                status, reason, evid = "MISSING", "缺少对应类型特殊备案：" + ",".join(labels), None
            status, reason, evid = apply_exemption("specialFiling", status, reason, evid)
            items.append(_item("specialFiling", cfg, status, reason, evid))

''', flags=re.S)
replace_once(P,
'''            ok = bool(rec.advisor_user_id or (rec.advisor_name or "").strip())
            status, reason, evid = (("VALID", "", None) if ok else ("MISSING", "未分配校内指导教师", None))''',
'''            ok = bool(rec.advisor_user_id)
            status, reason, evid = (("VALID", "", None) if ok else ("MISSING", "未分配稳定的校内指导教师账号", None))''')

# ---------------------------------------------------------------------------
# 11: special filing evidence must be authorized and bound.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_special_filing_service.py"
replace_once(P,
'''    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, internship_id, user, "创建特殊备案")''',
'''    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        from app.services import file_service
        rec = assert_internship_record_scope(db, internship_id, user, "创建特殊备案")
        for fid in file_ids:
            if not file_service.get_file_meta(fid, user=user):
                raise AppException("VALIDATION_ERROR", "特殊备案依据材料不存在或无权访问")''')
replace_once(P,
'''        db.add(row)
        db.flush()
        _audit(db, row, "CREATE", user, {''',
'''        db.add(row)
        db.flush()
        for fid in file_ids:
            file_service.bind_file_biz(fid, "INTERNSHIP", str(row.id), user=user, db=db)
        _audit(db, row, "CREATE", user, {''')
replace_once(P,
'''        if not row.file_ids or not (row.trigger_reason or "").strip():
            raise AppException("VALIDATION_ERROR", "提交前必须具备触发原因和依据材料")
        before = row.status''',
'''        if not row.file_ids or not (row.trigger_reason or "").strip():
            raise AppException("VALIDATION_ERROR", "提交前必须具备触发原因和依据材料")
        from app.services import file_service
        for fid in row.file_ids:
            if not file_service.get_file_meta(str(fid), user=user):
                raise AppException("DATA_CONFLICT", "特殊备案依据材料已失效或无权访问，请重新上传")
        before = row.status''')

# ---------------------------------------------------------------------------
# 13/14: process report resubmission advances version; RETURNED cannot be approved directly.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_process_report_service.py"
replace_once(P,
'''            dup.review_comment = None
            _trail(db, dup.id, "RESUBMIT", {"reportType": rt, "periodKey": pk})
            db.commit()
            return {"id": str(dup.id), "status": dup.status, "message": "已重新提交"}''',
'''            dup.review_comment = None
            dup.version = int(dup.version or 0) + 1
            _trail(db, dup.id, "RESUBMIT", {"reportType": rt, "periodKey": pk,
                                             "version": int(dup.version or 0)})
            db.commit()
            return {"id": str(dup.id), "status": dup.status, "version": int(dup.version or 0),
                    "message": "已重新提交"}''')
replace_once(P,
'''        if r.status not in ("PENDING_REVIEW", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可批阅")''',
'''        if r.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅学生已提交/重交后的待批阅报告可审核")''')

# ---------------------------------------------------------------------------
# 15: makeup strict date/range and malformed-date-safe compliance counting.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_makeup_service.py"
replace_once(P, 'from datetime import datetime', 'from datetime import date, datetime')
replace_once(P,
'''    evidence_file_id = _validate_evidence_file(evidence_file_id)
    if _evidence_required(makeup_type) and not evidence_file_id:
        raise AppException("VALIDATION_ERROR", _evidence_requirement_label(makeup_type))
    with session() as db:
        rec, stu = _student_record(db, user, for_write=True)''',
'''    try:
        makeup_day = date.fromisoformat((checkin_date or "").strip())
    except ValueError:
        raise AppException("VALIDATION_ERROR", "补卡日期必须为 YYYY-MM-DD") from None
    if makeup_day > datetime.utcnow().date():
        raise AppException("VALIDATION_ERROR", "不能申请未来日期补卡")
    evidence_file_id = _validate_evidence_file(evidence_file_id)
    if _evidence_required(makeup_type) and not evidence_file_id:
        raise AppException("VALIDATION_ERROR", _evidence_requirement_label(makeup_type))
    with session() as db:
        rec, stu = _student_record(db, user, for_write=True)
        def _as_day(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                return None
        start_day, end_day = _as_day(rec.intern_start_date), _as_day(rec.intern_end_date)
        if start_day and makeup_day < start_day:
            raise AppException("VALIDATION_ERROR", "补卡日期早于本次实习开始日期")
        if end_day and makeup_day > end_day:
            raise AppException("VALIDATION_ERROR", "补卡日期晚于本次实习结束日期")
        canonical_date = makeup_day.isoformat()
        if makeup_type == "MISSING":
            existing_checkin = db.scalars(select(InternshipCheckin).where(
                InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
                InternshipCheckin.checkin_date == canonical_date,
                InternshipCheckin.result.in_(("NORMAL", "RECORDED")),
                InternshipCheckin.is_deleted.is_(False))).first()
            if existing_checkin:
                raise AppException("DATA_CONFLICT", "该日期已有有效打卡记录，无需补卡")''')
replace_once(P, 'InternshipMakeup.checkin_date == checkin_date.strip(),',
                'InternshipMakeup.checkin_date == canonical_date,')
replace_once(P, 'checkin_date=checkin_date.strip(), makeup_type=makeup_type,',
                'checkin_date=canonical_date, makeup_type=makeup_type,')

P = "backend/app/modules/internship/services/internship_compliance_facts.py"
replace_once(P,
'''    valid_checkin_dates = {
        value for value in valid_checkin_dates
        if value is not None
        and (not start or _date(value) >= start)
        and (not end or _date(value) <= end)
    }''',
'''    normalized_checkins = set()
    for value in valid_checkin_dates:
        parsed = _date(value)
        if parsed is None:
            continue
        if start and parsed < start:
            continue
        if end and parsed > end:
            continue
        normalized_checkins.add(parsed.isoformat())
    valid_checkin_dates = normalized_checkins''')

# ---------------------------------------------------------------------------
# 16: participant list/summary/remove must enforce row-level scope.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/routers/internship_participant.py"
replace_once(P, 'svc.list_participants(batchId, page, pageSize, keyword, includeRemoved)',
                'svc.list_participants(batchId, page, pageSize, keyword, includeRemoved, user=user)')
replace_once(P, 'return success(svc.summary(batchId))', 'return success(svc.summary(batchId, user=user))')
replace_once(P, 'svc.remove_participant(batchId, participantId, body.reason, body.version)',
                'svc.remove_participant(batchId, participantId, body.reason, body.version, user=user)')

P = "backend/app/modules/internship/services/internship_participant_service.py"
replace_once(P,
'''def list_participants(batch_id, page: int = 1, page_size: int = 20,
                      keyword: str | None = None, include_removed: bool = False) -> tuple[list, int]:''',
'''def list_participants(batch_id, page: int = 1, page_size: int = 20,
                      keyword: str | None = None, include_removed: bool = False,
                      user: dict | None = None) -> tuple[list, int]:''')
replace_once(P,
'''        profiles = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in rows] or [0]))).all()}
        cache: dict = {}''',
'''        requested_ids = [int(r.student_id) for r in rows]
        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": requested_ids}),
                                user=user, limit=None) if requested_ids else None
        allowed_ids = {int(s.id) for s in allowed.students} if allowed else set()
        rows = [r for r in rows if int(r.student_id) in allowed_ids]
        profiles = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in rows] or [0]))).all()}
        cache: dict = {}''')
replace_once(P,
'''def remove_participant(batch_id, participant_id, reason: str, expected_version) -> dict:''',
'''def remove_participant(batch_id, participant_id, reason: str, expected_version, user: dict | None = None) -> dict:''')
replace_once(P,
'''        if int(row.version or 0) != expected:
            raise AppException("APPROVAL_VERSION_CONFLICT", "数据已被他人修改，请刷新后重试")''',
'''        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": [int(row.student_id)]}),
                                user=user, limit=None)
        if int(row.student_id) not in {int(s.id) for s in allowed.students}:
            from app.core.exceptions import no_permission
            raise no_permission("该参与人不在你的数据范围内")
        if int(row.version or 0) != expected:
            raise AppException("APPROVAL_VERSION_CONFLICT", "数据已被他人修改，请刷新后重试")''')
sub_once(P,
    r'def summary\(batch_id\) -> dict:\n.*?\Z',
'''def summary(batch_id, user: dict | None = None) -> dict:
    from app.models import InternshipBatchParticipant

    with session() as db:
        b = _get_batch(db, batch_id)
        rule = _get_or_create_rule(db, batch_id)
        rows = db.scalars(select(InternshipBatchParticipant).where(
            InternshipBatchParticipant.tenant_id == _tid(),
            InternshipBatchParticipant.batch_id == int(batch_id),
            InternshipBatchParticipant.is_deleted.is_(False))).all()
        requested_ids = [int(r.student_id) for r in rows]
        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": requested_ids}),
                                user=user, limit=None) if requested_ids else None
        allowed_ids = {int(s.id) for s in allowed.students} if allowed else set()
        visible = [r for r in rows if int(r.student_id) in allowed_ids]
        active = sum(1 for r in visible if r.status == "ACTIVE")
        removed = sum(1 for r in visible if r.status == "REMOVED")
        db.commit()
        return {"batchId": str(b.id), "batchName": b.batch_name, "batchStatus": b.status,
                "frozen": rule.frozen_at is not None, "frozenAt": _iso(rule.frozen_at),
                "activeCount": active, "removedCount": removed,
                "plannedCount": int(b.planned_count or 0)}
''', flags=re.S)

# ---------------------------------------------------------------------------
# C: core InternshipRecord staff writes carry expectedVersion end-to-end.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/schemas/internship_student.py"
replace_once(P,
'''class StudentRecordUpdate(BaseModel):
    advisorName: Optional[str] = None''',
'''class StudentRecordUpdate(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="实习记录乐观锁版本")
    advisorName: Optional[str] = None''')
replace_once(P,
'''class StudentStatusRequest(BaseModel):
    action: str = Field(..., pattern="^(READY|ONBOARD|ASSESS)$",''',
'''class StudentStatusRequest(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="实习记录乐观锁版本")
    action: str = Field(..., pattern="^(READY|ONBOARD|ASSESS)$",''')
replace_once(P,
'''class EligibilityRequest(BaseModel):
    status: str = Field(..., description="QUALIFIED / UNQUALIFIED / PENDING")''',
'''class EligibilityRequest(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="实习记录乐观锁版本")
    status: str = Field(..., description="QUALIFIED / UNQUALIFIED / PENDING")''')
replace_once(P,
'''class DestinationRequest(BaseModel):
    destination: str = Field(..., description="SELF_ARRANGED / EXEMPTED / NONE")''',
'''class DestinationRequest(BaseModel):
    expectedVersion: Optional[int] = Field(None, ge=0, description="实习记录乐观锁版本")
    destination: str = Field(..., description="SELF_ARRANGED / EXEMPTED / NONE")''')
replace_once(P,
'''class AdvisorAssignmentRequest(BaseModel):
    advisorUserId: str = Field(..., description="Active teacher user id")''',
'''class AdvisorAssignmentRequest(BaseModel):
    advisorUserId: str = Field(..., description="Active teacher user id")
    expectedVersion: Optional[int] = Field(None, ge=0, description="实习记录乐观锁版本")''')

P = "backend/app/modules/internship/routers/internship_student.py"
replace_once(P, 'svc.assign_advisor(record_id, body.advisorUserId, body.reason or "", user=user)',
                'svc.assign_advisor(record_id, body.advisorUserId, body.reason or "", user=user, expected_version=body.expectedVersion)')
replace_once(P, 'svc.set_status(record_id, body.action, body.reason or "", user=user)',
                'svc.set_status(record_id, body.action, body.reason or "", user=user, expected_version=body.expectedVersion)')
replace_once(P, 'svc.set_eligibility(record_id, body.status, body.reason or "", user=user)',
                'svc.set_eligibility(record_id, body.status, body.reason or "", user=user, expected_version=body.expectedVersion)')
replace_once(P, 'svc.set_destination(record_id, body.destination, body.reason or "", user=user)',
                'svc.set_destination(record_id, body.destination, body.reason or "", user=user, expected_version=body.expectedVersion)')

P = "backend/app/modules/internship/services/internship_student_service.py"
# central guard; optional for legacy direct callers, all formal HTTP paths now send it.
replace_once(P,
'''def _assert_write_scope(db, r: InternshipRecord, user) -> None:''',
'''def _require_record_version(r: InternshipRecord, expected_version) -> None:
    if expected_version is None:
        return
    if int(expected_version) != int(r.version or 0):
        raise AppException("DATA_CONFLICT", "实习记录已被其他用户修改，请刷新后重试")


def _assert_write_scope(db, r: InternshipRecord, user) -> None:''')
replace_once(P,
'''        _assert_write_scope(db, r, user)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可编辑")''',
'''        _assert_write_scope(db, r, user)
        _require_record_version(r, getattr(body, "expectedVersion", None))
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可编辑")''')
replace_once(P,
'''def assign_advisor(rec_id, advisor_user_id, reason: str = "", user=None) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)''',
'''def assign_advisor(rec_id, advisor_user_id, reason: str = "", user=None, expected_version=None) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        _require_record_version(r, expected_version)''')
replace_once(P,
'''def set_status(rec_id, action: str, reason: str = "", user=None) -> dict:
    """普通状态流转仅 READY / ONBOARD / ASSESS；归档必须走 archive_student。"""
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)''',
'''def set_status(rec_id, action: str, reason: str = "", user=None, expected_version=None) -> dict:
    """普通状态流转仅 READY / ONBOARD / ASSESS；归档必须走 archive_student。"""
    with session() as db:
        r = _get(db, rec_id)
        _assert_write_scope(db, r, user)
        _require_record_version(r, expected_version)''')
sub_once(P,
    r'def set_eligibility\(rec_id, status: str, reason: str = "", user=None\) -> dict:',
    'def set_eligibility(rec_id, status: str, reason: str = "", user=None, expected_version=None) -> dict:')
# add guard to first occurrence inside eligibility after its signature
text = read(P)
marker = 'def set_eligibility(rec_id, status: str, reason: str = "", user=None, expected_version=None) -> dict:'
pos = text.index(marker)
chunk = text[pos:]
needle = '        _assert_write_scope(db, r, user)\n'
idx = chunk.index(needle)
chunk = chunk[:idx] + needle + '        _require_record_version(r, expected_version)\n' + chunk[idx + len(needle):]
write(P, text[:pos] + chunk)
sub_once(P,
    r'def set_destination\(rec_id, destination: str, reason: str = "", user=None\) -> dict:',
    'def set_destination(rec_id, destination: str, reason: str = "", user=None, expected_version=None) -> dict:')
text = read(P)
pos = text.index('def set_destination(rec_id, destination: str, reason: str = "", user=None, expected_version=None) -> dict:')
chunk = text[pos:]
idx = chunk.index(needle)
chunk = chunk[:idx] + needle + '        _require_record_version(r, expected_version)\n' + chunk[idx + len(needle):]
write(P, text[:pos] + chunk)

# ---------------------------------------------------------------------------
# D: enterprise evaluation only in assessment stage.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_enterprise_eval_service.py"
replace_once(P,
'''def _assert_review_authority(user):
    if not _is_review_admin(user):
        raise no_permission("企业评价学校审核仅限学校或学院授权管理员")


def create''',
'''def _assert_review_authority(user):
    if not _is_review_admin(user):
        raise no_permission("企业评价学校审核仅限学校或学院授权管理员")


def _assert_assessing(record):
    if not record or record.status != "ASSESSING":
        raise AppException("DATA_CONFLICT", "仅处于考核中的实习记录可录入、重交或审核企业评价")


def create''')
replace_once(P,
'''        student = db.get(StudentProfile, record.student_id)
        if not in_scope(scope, db, record, student):''',
'''        student = db.get(StudentProfile, record.student_id)
        _assert_assessing(record)
        if not in_scope(scope, db, record, student):''')
# resubmit and review both obtain record from _assert_scope
text = read(P)
for anchor in ['record, _student = _assert_scope(db, row, user, "只能修改本人指导或授权范围内企业评价")',
               'record, _student = _assert_scope(db, row, user, "只能审核本人数据范围内的企业评价")']:
    if text.count(anchor) != 1:
        raise RuntimeError(f"{P}: stage anchor missing: {anchor}")
    text = text.replace(anchor, anchor + '\n        _assert_assessing(record)', 1)
write(P, text)

# ---------------------------------------------------------------------------
# G: unresolved matching conflicts cannot be silently confirmed.
# ---------------------------------------------------------------------------
P = "backend/app/modules/internship/services/internship_match_service.py"
replace_once(P,
'''        if m.status not in ("RECOMMENDED", "PENDING_CONFIRM", "CONFLICT"):
            raise AppException("DATA_CONFLICT", f"当前状态不可确认（{m.status}）")
        if m.conflict_flag and m.status == "CONFLICT":
            pass''',
'''        if m.status not in ("RECOMMENDED", "PENDING_CONFIRM"):
            raise AppException("DATA_CONFLICT", f"当前状态不可确认（{m.status}）")
        if m.conflict_flag:
            raise AppException("DATA_CONFLICT", "该匹配仍存在冲突，请先处理冲突后再确认")''')

# Static regression contracts: cheap, deterministic protection for the exact prelaunch holes.
TEST = "backend/tests/test_internship_prelaunch_static_contracts.py"
(ROOT / TEST).write_text('''from pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef src(rel):\n    return (ROOT / rel).read_text(encoding="utf-8")\n\ndef test_no_name_fallback_in_communication_scope():\n    text = src("app/modules/internship/services/internship_communication_service.py")\n    assert 'return (c.advisor_name or "") in' not in text\n\ndef test_evidence_audit_is_type_scoped():\n    text = src("app/modules/internship/services/internship_evidence_package_service.py")\n    assert text.count('InternshipAuditTrail.target_type == "INTERN_STUDENT"') >= 2\n\ndef test_incident_requires_internship_id():\n    text = src("app/modules/internship/services/internship_incident_service.py")\n    assert '学生事故上报必须关联 internshipId' in text\n\ndef test_special_filing_is_type_covered():\n    text = src("app/modules/internship/services/internship_compliance_service.py")\n    assert 'missing_types = [code for code in triggers if code not in approved]' in text\n    assert 'ok = bool(rec.advisor_user_id)' in text\n\ndef test_process_report_returned_requires_resubmit():\n    text = src("app/modules/internship/services/internship_process_report_service.py")\n    assert 'if r.status != "PENDING_REVIEW"' in text\n    assert 'dup.version = int(dup.version or 0) + 1' in text\n\ndef test_match_conflict_cannot_be_confirmed():\n    text = src("app/modules/internship/services/internship_match_service.py")\n    assert 'if m.conflict_flag:' in text\n    assert '该匹配仍存在冲突' in text\n''', encoding="utf-8")
changed.add(TEST)

print("PATCHED FILES")
for path in sorted(changed):
    print(path)
