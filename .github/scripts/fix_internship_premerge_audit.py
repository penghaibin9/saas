from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")


def rep(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one match, got {n}")
    return text.replace(old, new, 1)


# 1. Enterprise DTOs: public mutations must carry an optimistic-lock version.
p = "backend/app/modules/internship/schemas/internship.py"
t = read(p)
for cls in ("EnterpriseUpdate", "EnterpriseReview", "CoopActionRequest", "BlacklistRequest", "ContactUpdate"):
    marker = 'expectedVersion: Optional[int] = Field(None, ge=0, description="'
    start = t.index(f"class {cls}(BaseModel):")
    end = t.find("\n\nclass ", start + 1)
    if end < 0:
        end = len(t)
    block = t[start:end]
    if marker not in block:
        raise SystemExit(f"{cls}: optional expectedVersion marker missing")
    block = block.replace(marker, 'expectedVersion: int = Field(..., ge=0, description="', 1)
    t = t[:start] + block + t[end:]
write(p, t)

# 2. Enterprise services: defensive fail-closed version checks + primary-contact type transition.
p = "backend/app/modules/internship/services/internship_enterprise_service.py"
t = read(p)
t = rep(t,
'''        expected = getattr(body, "expectedVersion", None)\n        if expected is not None and int(expected) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业信息已被其他用户修改，请刷新后重试")\n''',
'''        expected = getattr(body, "expectedVersion", None)\n        if expected is None:\n            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")\n        if int(expected) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业信息已被其他用户修改，请刷新后重试")\n''', "enterprise update version")
for old_msg, new_msg in [
    ('        if expected_version is not None and int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业资质状态已变化，请刷新后重试")\n',
     '        if expected_version is None:\n            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")\n        if int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业资质状态已变化，请刷新后重试")\n'),
    ('        if expected_version is not None and int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业合作状态已变化，请刷新后重试")\n',
     '        if expected_version is None:\n            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")\n        if int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业合作状态已变化，请刷新后重试")\n'),
    ('        if expected_version is not None and int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业黑名单状态已变化，请刷新后重试")\n',
     '        if expected_version is None:\n            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")\n        if int(expected_version) != int(c.version or 0):\n            raise AppException("DATA_CONFLICT", "企业黑名单状态已变化，请刷新后重试")\n')]:
    t = rep(t, old_msg, new_msg, "enterprise state version")
t = rep(t,
'''        expected = getattr(body, "expectedVersion", None)\n        if expected is not None and int(expected) != int(t.version or 0):\n            raise AppException("DATA_CONFLICT", "联系人已被其他用户修改，请刷新后重试")\n''',
'''        expected = getattr(body, "expectedVersion", None)\n        if expected is None:\n            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（联系人乐观锁），请刷新后重试")\n        if int(expected) != int(t.version or 0):\n            raise AppException("DATA_CONFLICT", "联系人已被其他用户修改，请刷新后重试")\n        old_contact_type = t.contact_type\n        was_primary = bool(t.is_primary)\n''', "contact update version")
t = rep(t,
'''        if "isPrimary" in body.model_fields_set:\n            is_primary = getattr(body, "isPrimary", None)\n            if is_primary:\n                _unset_primary(db, c.id, t.contact_type)\n                t.is_primary = True\n            else:\n                t.is_primary = False\n        t.version = int(t.version or 0) + 1\n''',
'''        if "isPrimary" in body.model_fields_set:\n            is_primary = getattr(body, "isPrimary", None)\n            if is_primary:\n                _unset_primary(db, c.id, t.contact_type)\n                t.is_primary = True\n            else:\n                t.is_primary = False\n        elif "contactType" in body.model_fields_set and t.contact_type != old_contact_type and was_primary:\n            # 主联系人换类型时仍保持“主联系人”语义，但新类型原主联系人必须被降级，\n            # 否则同一企业同一联系人类型会出现两个主联系人。\n            _unset_primary(db, c.id, t.contact_type)\n            t.is_primary = True\n        t.version = int(t.version or 0) + 1\n''', "contact primary type transition")
write(p, t)

# 3. Enterprise edit page sends the version just loaded from detail.
p = "frontend/src/modules/internship/views/EnterpriseFormView.vue"
t = read(p)
t = rep(t,
'''      if (!this.isEdit || (f.contactPhone || '').trim()) body.contactPhone = (f.contactPhone || '').trim()\n      this.submitting = true\n''',
'''      if (!this.isEdit || (f.contactPhone || '').trim()) body.contactPhone = (f.contactPhone || '').trim()\n      if (this.isEdit) body.expectedVersion = this.detail?.version\n      this.submitting = true\n''', "enterprise edit expectedVersion")
write(p, t)

# 4. Student record DTOs and service: make stale-write protection mandatory.
p = "backend/app/modules/internship/schemas/internship_student.py"
t = read(p)
for cls in ("StudentRecordUpdate", "StudentStatusRequest", "EligibilityRequest", "DestinationRequest", "AdvisorAssignmentRequest"):
    start = t.index(f"class {cls}(BaseModel):")
    end = t.find("\n\nclass ", start + 1)
    if end < 0:
        end = len(t)
    block = t[start:end]
    old = 'expectedVersion: Optional[int] = Field(None, ge=0, description="'
    if old not in block:
        raise SystemExit(f"{cls}: optional expectedVersion marker missing")
    block = block.replace(old, 'expectedVersion: int = Field(..., ge=0, description="', 1)
    t = t[:start] + block + t[end:]
write(p, t)

p = "backend/app/modules/internship/services/internship_student_service.py"
t = read(p)
t = rep(t,
'''def _require_record_version(r: InternshipRecord, expected_version) -> None:\n    if expected_version is None:\n        return\n    if int(expected_version) != int(r.version or 0):\n        raise AppException("DATA_CONFLICT", "实习记录已被其他用户修改，请刷新后重试")\n''',
'''def _require_record_version(r: InternshipRecord, expected_version) -> None:\n    if expected_version is None:\n        raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（实习记录乐观锁），请刷新后重试")\n    if int(expected_version) != int(r.version or 0):\n        raise AppException("DATA_CONFLICT", "实习记录已被其他用户修改，请刷新后重试")\n''', "student service required version")
write(p, t)

# 5. Staff student API must not destructure-and-drop versions.
p = "frontend/src/modules/internship/api/internship-student.api.js"
t = read(p)
t = rep(t,
'''  setStatus(id, { action, reason }) {\n    return call(() => request(`${BASE}/${id}/status`, { method: 'POST', body: { action, reason } }))\n''',
'''  setStatus(id, { action, reason, expectedVersion }) {\n    return call(() => request(`${BASE}/${id}/status`, { method: 'POST', body: { action, reason, expectedVersion } }))\n''', "student API status")
t = rep(t,
'''  setEligibility(id, { status, reason }) {\n    return call(() => request(`${BASE}/${id}/eligibility`, { method: 'POST', body: { status, reason } }))\n''',
'''  setEligibility(id, { status, reason, expectedVersion }) {\n    return call(() => request(`${BASE}/${id}/eligibility`, { method: 'POST', body: { status, reason, expectedVersion } }))\n''', "student API eligibility")
t = rep(t,
'''  setDestination(id, { destination, reason }) {\n    return call(() => request(`${BASE}/${id}/destination`, { method: 'POST', body: { destination, reason } }))\n''',
'''  setDestination(id, { destination, reason, expectedVersion }) {\n    return call(() => request(`${BASE}/${id}/destination`, { method: 'POST', body: { destination, reason, expectedVersion } }))\n''', "student API destination")
t = rep(t,
'''  assignAdvisor(id, { advisorUserId, reason = '' }) {\n    return call(() => request(`${BASE}/${id}/advisor`, { method: 'POST', body: { advisorUserId, reason } }))\n''',
'''  assignAdvisor(id, { advisorUserId, reason = '', expectedVersion }) {\n    return call(() => request(`${BASE}/${id}/advisor`, { method: 'POST', body: { advisorUserId, reason, expectedVersion } }))\n''', "student API advisor")
write(p, t)

# 6. Student list/detail callers pass row/detail versions and the correct destination field.
p = "frontend/src/modules/internship/views/InternshipStudentListView.vue"
t = read(p)
t = rep(t,
'''        const res = await internStudentApi.assignAdvisor(this.advisorRow.id, {\n          advisorUserId: this.advisorAssignmentUserId,\n          reason: this.advisorAssignmentReason\n        })\n''',
'''        const res = await internStudentApi.assignAdvisor(this.advisorRow.id, {\n          advisorUserId: this.advisorAssignmentUserId,\n          reason: this.advisorAssignmentReason,\n          expectedVersion: this.advisorRow.version\n        })\n''', "list advisor version")
t = rep(t,
'''        if (action === 'ELIG_QUALIFIED') res = await internStudentApi.setEligibility(row.id, { status: 'QUALIFIED', reason: reason || '' })\n''',
'''        if (action === 'ELIG_QUALIFIED') res = await internStudentApi.setEligibility(row.id, {\n          status: 'QUALIFIED', reason: reason || '', expectedVersion: row.version\n        })\n''', "list eligibility version")
write(p, t)

p = "frontend/src/modules/internship/views/InternshipStudentDetailView.vue"
t = read(p)
t = rep(t,
'''        if (action === 'ELIG') res = await internStudentApi.setEligibility(this.detail.id, { status: 'QUALIFIED', reason: reason || '' })\n''',
'''        if (action === 'ELIG') res = await internStudentApi.setEligibility(this.detail.id, {\n          status: 'QUALIFIED', reason: reason || '', expectedVersion: this.detail.version\n        })\n''', "detail eligibility version")
t = rep(t,
'''        else if (action === 'DEST') res = await internStudentApi.setDestination(this.detail.id, { destinationType: extra, expectedVersion: this.detail.version })\n''',
'''        else if (action === 'DEST') res = await internStudentApi.setDestination(this.detail.id, {\n          destination: extra, reason: reason || '', expectedVersion: this.detail.version\n        })\n''', "detail destination contract")
write(p, t)

# 7. Participant summary: never expose the school-wide planned target to a scoped college role.
p = "backend/app/modules/internship/services/internship_participant_service.py"
t = read(p)
t = rep(t,
'''        visible = [r for r in rows if int(r.student_id) in allowed_ids]\n        active = sum(1 for r in visible if r.status == "ACTIVE")\n        removed = sum(1 for r in visible if r.status == "REMOVED")\n        db.commit()\n        return {"batchId": str(b.id), "batchName": b.batch_name, "batchStatus": b.status,\n                "frozen": rule.frozen_at is not None, "frozenAt": _iso(rule.frozen_at),\n                "activeCount": active, "removedCount": removed,\n                "plannedCount": int(b.planned_count or 0)}\n''',
'''        visible = [r for r in rows if int(r.student_id) in allowed_ids]\n        active = sum(1 for r in visible if r.status == "ACTIVE")\n        removed = sum(1 for r in visible if r.status == "REMOVED")\n        from app.core.affairs_security import student_directory_scope\n        allow_classes, allow_students = student_directory_scope(user) if user is not None else (None, None)\n        scoped_view = allow_classes is not None or allow_students is not None\n        # 批次 planned_count 是校级总目标，学院角色不能借 summary 反推出全校规模。\n        # 对受限角色返回其可见正式名单规模，并显式告诉前端这是“当前范围人数”。\n        planned_count = len(visible) if scoped_view else int(b.planned_count or 0)\n        db.commit()\n        return {"batchId": str(b.id), "batchName": b.batch_name, "batchStatus": b.status,\n                "frozen": rule.frozen_at is not None, "frozenAt": _iso(rule.frozen_at),\n                "activeCount": active, "removedCount": removed,\n                "plannedCount": planned_count, "plannedCountScoped": scoped_view}\n''', "participant planned scope")
write(p, t)

p = "frontend/src/modules/internship/views/components/BatchParticipantScope.vue"
t = read(p)
t = rep(t,
'''            <div><strong>{{ summary.plannedCount || 0 }}</strong><span>批次计划人数</span></div>\n''',
'''            <div><strong>{{ summary.plannedCount || 0 }}</strong><span>{{ summary.plannedCountScoped ? '当前范围人数' : '批次计划人数' }}</span></div>\n''', "participant scoped label")
write(p, t)

# 8. Extend static regression contracts so these omissions cannot silently return.
p = "backend/tests/test_internship_prelaunch_static_contracts.py"
t = read(p)
extra = '''\n\ndef test_enterprise_and_student_mutations_require_versions():\n    enterprise_schema = src("app/modules/internship/schemas/internship.py")\n    student_schema = src("app/modules/internship/schemas/internship_student.py")\n    enterprise_service = src("app/modules/internship/services/internship_enterprise_service.py")\n    student_service = src("app/modules/internship/services/internship_student_service.py")\n    assert enterprise_schema.count('expectedVersion: int = Field(...') >= 5\n    assert student_schema.count('expectedVersion: int = Field(...') >= 7\n    assert '必须提供 expectedVersion（企业乐观锁）' in enterprise_service\n    assert '必须提供 expectedVersion（实习记录乐观锁）' in student_service\n\ndef test_staff_student_api_forwards_versions_and_destination_contract():\n    api = (ROOT.parent / "frontend/src/modules/internship/api/internship-student.api.js").read_text(encoding="utf-8")\n    detail = (ROOT.parent / "frontend/src/modules/internship/views/InternshipStudentDetailView.vue").read_text(encoding="utf-8")\n    listing = (ROOT.parent / "frontend/src/modules/internship/views/InternshipStudentListView.vue").read_text(encoding="utf-8")\n    assert api.count('expectedVersion') >= 8\n    assert 'destination: extra' in detail\n    assert 'destinationType: extra' not in detail\n    assert 'expectedVersion: this.advisorRow.version' in listing\n    assert 'expectedVersion: row.version' in listing\n\ndef test_enterprise_edit_and_contact_type_keep_concurrency_invariants():\n    form = (ROOT.parent / "frontend/src/modules/internship/views/EnterpriseFormView.vue").read_text(encoding="utf-8")\n    service = src("app/modules/internship/services/internship_enterprise_service.py")\n    assert 'body.expectedVersion = this.detail?.version' in form\n    assert 'was_primary = bool(t.is_primary)' in service\n    assert 't.contact_type != old_contact_type and was_primary' in service\n\ndef test_participant_summary_hides_global_plan_for_scoped_roles():\n    service = src("app/modules/internship/services/internship_participant_service.py")\n    view = (ROOT.parent / "frontend/src/modules/internship/views/components/BatchParticipantScope.vue").read_text(encoding="utf-8")\n    assert 'planned_count = len(visible) if scoped_view' in service\n    assert '"plannedCountScoped": scoped_view' in service\n    assert "summary.plannedCountScoped ? '当前范围人数' : '批次计划人数'" in view\n'''
if "test_enterprise_and_student_mutations_require_versions" not in t:
    t += extra
write(p, t)

print("premerge audit repair applied")
