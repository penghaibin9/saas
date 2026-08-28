from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(p): return (ROOT / p).read_text(encoding='utf-8')
def write(p, s): (ROOT / p).write_text(s, encoding='utf-8')
def rep(s, a, b, label):
    n = s.count(a)
    if n != 1: raise SystemExit(f'{label}: expected one match, got {n}')
    return s.replace(a, b, 1)

# 1) Stable advisor identity in the common SQL scope gate: never authorize by teacher name.
p = 'backend/app/modules/internship/services/internship_scope.py'
t = read(p)
t = rep(t,
'''    advisor_names = list(scope.get("advisorNames", set()))\n    if role in advisor_roles:\n        clauses = []\n        if advisor_ids:\n            clauses.append(InternshipRecord.advisor_user_id.in_(advisor_ids))\n        if advisor_names:\n            clauses.append(\n                InternshipRecord.advisor_user_id.is_(None)\n                & InternshipRecord.advisor_name.in_(advisor_names))\n        return query.where(or_(*clauses) if clauses else false())\n''',
'''    if role in advisor_roles:\n        # 运行时授权只认稳定 user_id；历史只有 advisor_name 的记录必须先治理数据，\n        # 不能因为同名教师存在就扩大数据范围。\n        return query.where(\n            InternshipRecord.advisor_user_id.in_(advisor_ids) if advisor_ids else false()\n        )\n''', 'advisor-role stable scope')
t = rep(t,
'''    if advisor_names:\n        clauses.append(InternshipRecord.advisor_name.in_(advisor_names))\n    return query.where(or_(*clauses) if clauses else false())\n''',
'''    if advisor_ids:\n        clauses.append(InternshipRecord.advisor_user_id.in_(advisor_ids))\n    return query.where(or_(*clauses) if clauses else false())\n''', 'general stable advisor scope')
write(p, t)

# 2) Match statistics use the same row-level scope as the result ledger.
p = 'backend/app/modules/internship/services/internship_match_service.py'
t = read(p)
old = '''def match_stats(batch_id=None) -> dict:\n    with session() as db:\n        from app.modules.internship.services.internship_batch_context import batch_record_ids, resolve_batch\n        batch, record_ids = batch_record_ids(db, batch_id)\n        base = [InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),\n                InternshipMatch.record_id.in_(record_ids or [0])]\n'''
new = '''def match_stats(batch_id=None, user=None) -> dict:\n    with session() as db:\n        from app.modules.internship.services.internship_batch_context import resolve_batch\n        from app.modules.internship.services.internship_scope import apply_internship_record_scope\n        batch = resolve_batch(db, batch_id)\n        record_query = apply_internship_record_scope(\n            select(InternshipRecord.id).where(\n                InternshipRecord.tenant_id == _tid(),\n                InternshipRecord.batch_id == batch.id,\n                InternshipRecord.is_deleted.is_(False),\n            ),\n            user,\n        ).subquery()\n        scoped_record_ids = select(record_query.c.id)\n        base = [InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),\n                InternshipMatch.record_id.in_(scoped_record_ids)]\n'''
t = rep(t, old, new, 'match stats scoped records')
t = rep(t,
'''            InternshipIntention.batch_id == batch.id,\n            InternshipIntention.status == "SUBMITTED")) or 0)\n''',
'''            InternshipIntention.batch_id == batch.id,\n            InternshipIntention.record_id.in_(scoped_record_ids),\n            InternshipIntention.status == "SUBMITTED")) or 0)\n''', 'match stats intention scope')
write(p, t)

p = 'backend/app/modules/internship/routers/internship_match.py'
t = read(p)
t = rep(t,
'''def stats(batchId: Optional[str] = None, user=Depends(require_permission(_P_RESULT))):\n    return success(svc.match_stats(batch_id=batchId))\n''',
'''def stats(batchId: Optional[str] = None, user=Depends(require_permission(_P_RESULT))):\n    return success(svc.match_stats(batch_id=batchId, user=user))\n''', 'match stats router user')
write(p, t)

# 3) Batch date/count parsing: malformed input must be 4xx validation, never silently NULL/500.
p = 'backend/app/modules/internship/services/internship_service.py'
t = read(p)
t = rep(t,
'''def _parse_dt(v):\n    if not v:\n        return None\n    s = str(v).strip().replace("Z", "").replace("/", "-")\n    if not s:\n        return None\n    try:\n        return datetime.fromisoformat(s[:19])\n    except ValueError:\n        try:\n            return datetime.strptime(s[:10], "%Y-%m-%d")\n        except ValueError:\n            return None\n''',
'''def _parse_dt(v, label: str = "日期"):\n    if v in (None, ""):\n        return None\n    s = str(v).strip().replace("Z", "").replace("/", "-")\n    if not s:\n        return None\n    try:\n        return datetime.fromisoformat(s[:19])\n    except ValueError:\n        try:\n            return datetime.strptime(s[:10], "%Y-%m-%d")\n        except ValueError:\n            raise AppException("VALIDATION_ERROR", f"{label}格式不正确，请使用 YYYY-MM-DD") from None\n\n\ndef _parse_nonnegative_int(v, label: str) -> int:\n    try:\n        value = int(v or 0)\n    except (TypeError, ValueError):\n        raise AppException("VALIDATION_ERROR", f"{label}必须为非负整数") from None\n    if value < 0:\n        raise AppException("VALIDATION_ERROR", f"{label}必须为非负整数")\n    return value\n''', 'strict batch parser')
t = rep(t,
'''    _assert_batch_dates(_parse_dt(body.get("startDate")), _parse_dt(body.get("endDate")),\n                        _parse_dt(body.get("signupStartDate")), _parse_dt(body.get("signupEndDate")))\n    with session() as db:\n''',
'''    start = _parse_dt(body.get("startDate"), "实习开始日期")\n    end = _parse_dt(body.get("endDate"), "实习结束日期")\n    signup_start = _parse_dt(body.get("signupStartDate"), "报名开始日期")\n    signup_end = _parse_dt(body.get("signupEndDate"), "报名截止日期")\n    _assert_batch_dates(start, end, signup_start, signup_end)\n    planned_count = _parse_nonnegative_int(body.get("plannedCount"), "计划人数")\n    with session() as db:\n''', 'create batch parse once')
t = rep(t,
'''            start_date=_parse_dt(body.get("startDate")), end_date=_parse_dt(body.get("endDate")),\n            signup_start_date=_parse_dt(body.get("signupStartDate")),\n            signup_end_date=_parse_dt(body.get("signupEndDate")),\n            planned_count=int(body.get("plannedCount") or 0), remark=body.get("remark"),\n''',
'''            start_date=start, end_date=end,\n            signup_start_date=signup_start, signup_end_date=signup_end,\n            planned_count=planned_count, remark=body.get("remark"),\n''', 'create batch canonical values')
t = rep(t,
'''        for k, col in {"startDate": "start_date", "endDate": "end_date",\n                       "signupStartDate": "signup_start_date",\n                       "signupEndDate": "signup_end_date"}.items():\n            if body.get(k) is not None:\n                values[col] = _parse_dt(body[k])\n''',
'''        for k, col, label in (\n            ("startDate", "start_date", "实习开始日期"),\n            ("endDate", "end_date", "实习结束日期"),\n            ("signupStartDate", "signup_start_date", "报名开始日期"),\n            ("signupEndDate", "signup_end_date", "报名截止日期"),\n        ):\n            if body.get(k) is not None:\n                values[col] = _parse_dt(body[k], label)\n''', 'update batch date labels')
t = rep(t,
'''        if body.get("plannedCount") is not None:\n            values["planned_count"] = int(body["plannedCount"] or 0)\n''',
'''        if body.get("plannedCount") is not None:\n            values["planned_count"] = _parse_nonnegative_int(body["plannedCount"], "计划人数")\n''', 'update planned count validation')
# Legacy detail compatibility endpoint must also avoid bare target-id audit collisions.
t = rep(t,
'''        trail = db.scalars(select(InternshipAuditTrail).where(\n            InternshipAuditTrail.tenant_id == _tid(),\n            InternshipAuditTrail.target_id == r.id).order_by(\n''',
'''        trail = db.scalars(select(InternshipAuditTrail).where(\n            InternshipAuditTrail.tenant_id == _tid(),\n            InternshipAuditTrail.target_type == "INTERN_STUDENT",\n            InternshipAuditTrail.target_id == r.id).order_by(\n''', 'legacy internship detail audit type')
write(p, t)

# 4) Regression contracts.
p = 'backend/tests/test_internship_prelaunch_static_contracts.py'
t = read(p)
extra = '''\n\ndef test_common_sql_scope_never_authorizes_advisor_by_name():\n    text = src("app/modules/internship/services/internship_scope.py")\n    assert 'InternshipRecord.advisor_user_id.in_(advisor_ids)' in text\n    assert 'InternshipRecord.advisor_name.in_(advisor_names)' not in text\n\ndef test_match_stats_uses_row_level_scope():\n    svc = src("app/modules/internship/services/internship_match_service.py")\n    router = src("app/modules/internship/routers/internship_match.py")\n    assert 'def match_stats(batch_id=None, user=None)' in svc\n    assert 'apply_internship_record_scope' in svc\n    assert 'InternshipIntention.record_id.in_(scoped_record_ids)' in svc\n    assert 'svc.match_stats(batch_id=batchId, user=user)' in router\n\ndef test_batch_invalid_dates_and_counts_fail_validation():\n    text = src("app/modules/internship/services/internship_service.py")\n    assert 'f"{label}格式不正确，请使用 YYYY-MM-DD"' in text\n    assert 'def _parse_nonnegative_int' in text\n    assert '_parse_nonnegative_int(body["plannedCount"], "计划人数")' in text\n\ndef test_legacy_internship_detail_audit_is_type_scoped():\n    text = src("app/modules/internship/services/internship_service.py")\n    anchor = text.index('def get_internship_student_detail')\n    tail = text[anchor:anchor + 5000]\n    assert 'InternshipAuditTrail.target_type == "INTERN_STUDENT"' in tail\n'''
if 'test_common_sql_scope_never_authorizes_advisor_by_name' not in t:
    t += extra
write(p, t)
print('final scope validation repair applied')
